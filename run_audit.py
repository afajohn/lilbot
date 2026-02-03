#!/usr/bin/env python3
import argparse
import sys
import os
import signal
import threading
import traceback
from typing import List, Tuple, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from sheets import sheets_client
from sheets.schema_validator import SpreadsheetSchemaValidator
from sheets.data_quality_checker import DataQualityChecker
from qa import cypress_runner
from utils import logger
from utils.error_metrics import get_global_metrics
from utils.exceptions import RetryableError, PermanentError
from utils.url_validator import URLValidator, URLNormalizer
from metrics.metrics_collector import get_metrics_collector
from security.url_filter import URLFilter


DEFAULT_SPREADSHEET_ID = '1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I'
SERVICE_ACCOUNT_FILE = 'service-account.json'
MOBILE_COLUMN = 'F'
DESKTOP_COLUMN = 'G'
SCORE_THRESHOLD = 80
DEFAULT_CONCURRENCY = 3


shutdown_event = threading.Event()
log_lock = threading.Lock()


def signal_handler(signum, frame):
    """Handle SIGINT and SIGTERM signals for graceful shutdown."""
    with log_lock:
        log = logger.get_logger()
        log.info("\nReceived shutdown signal. Waiting for current tasks to complete...")
    shutdown_event.set()


def process_url(
    url_data: Tuple[int, str, Optional[str], Optional[str], bool],
    spreadsheet_id: str,
    tab_name: str,
    service,
    timeout: int,
    total_urls: int,
    processed_count: dict,
    skip_cache: bool = False,
    url_filter: Optional[URLFilter] = None,
    dry_run: bool = False,
    url_validator: Optional[URLValidator] = None,
    validate_dns: bool = True,
    validate_redirects: bool = True
) -> Dict[str, Any]:
    """
    Process a single URL with thread-safe logging and error metrics collection.
    
    Args:
        url_data: Tuple of (row_index, url, existing_mobile_psi, existing_desktop_psi, should_skip)
        spreadsheet_id: Google Sheets spreadsheet ID
        tab_name: Sheet tab name
        service: Shared Google Sheets service
        timeout: Cypress timeout in seconds
        total_urls: Total number of URLs to process
        processed_count: Shared counter dictionary with lock
        skip_cache: If True, bypass cache and force fresh analysis
        url_filter: Optional URL filter for whitelist/blacklist
        dry_run: If True, simulate operations without making changes
        
    Returns:
        Dictionary with result data
    """
    log = logger.get_logger()
    metrics = get_global_metrics()
    metrics_collector = get_metrics_collector()
    row_index, url, existing_mobile_psi, existing_desktop_psi, should_skip = url_data
    
    start_time = metrics_collector.record_url_start()
    
    if shutdown_event.is_set():
        return {
            'row': row_index,
            'url': url,
            'skipped': True,
            'shutdown': True
        }
    
    with processed_count['lock']:
        processed_count['count'] += 1
        current_idx = processed_count['count']
    
    if should_skip:
        with log_lock:
            log.info(f"[{current_idx}/{total_urls}] Skipping {url} (contains 'passed' or has green background in column F or G)")
            log.info("")
        metrics_collector.record_url_skipped()
        return {
            'row': row_index,
            'url': url,
            'skipped': True
        }
    
    if existing_mobile_psi and existing_desktop_psi:
        with log_lock:
            log.info(f"[{current_idx}/{total_urls}] Skipping {url} (both columns F and G already filled)")
            log.info("")
        metrics_collector.record_url_skipped()
        return {
            'row': row_index,
            'url': url,
            'skipped': True
        }
    
    try:
        sanitized_url = URLFilter.sanitize_url(url)
    except ValueError as e:
        with log_lock:
            log.error(f"[{current_idx}/{total_urls}] Invalid URL {url}: {e}")
            log.info("")
        metrics_collector.record_url_failure(start_time, reason='invalid_url')
        return {
            'row': row_index,
            'url': url,
            'error': str(e),
            'error_type': 'invalid_url'
        }
    
    if url_validator:
        is_valid, validation_results = url_validator.validate_url(
            sanitized_url, 
            check_dns=validate_dns, 
            check_redirects=validate_redirects
        )
        
        if not is_valid:
            error_msg = "; ".join(validation_results['errors'])
            with log_lock:
                log.error(f"[{current_idx}/{total_urls}] URL validation failed for {sanitized_url}")
                log.error(f"  Errors: {error_msg}")
                if validation_results.get('redirect_count'):
                    log.error(f"  Redirect count: {validation_results['redirect_count']}")
                log.info("")
            metrics_collector.record_url_failure(start_time, reason='validation_failed')
            return {
                'row': row_index,
                'url': url,
                'error': error_msg,
                'error_type': 'validation_failed',
                'validation_results': validation_results
            }
        
        if validation_results.get('redirect_count') and validation_results['redirect_count'] > 0:
            with log_lock:
                log.warning(f"  URL has {validation_results['redirect_count']} redirect(s)")
    
    try:
        normalized_url = URLNormalizer.normalize_url(sanitized_url)
        if normalized_url != sanitized_url:
            with log_lock:
                log.info(f"  Normalized URL: {normalized_url}")
            sanitized_url = normalized_url
    except Exception as e:
        with log_lock:
            log.warning(f"  Could not normalize URL: {e}")
    
    if url_filter and not url_filter.is_allowed(sanitized_url):
        with log_lock:
            log.info(f"[{current_idx}/{total_urls}] URL rejected by filter: {sanitized_url}")
            log.info("")
        metrics_collector.record_url_skipped()
        return {
            'row': row_index,
            'url': url,
            'skipped': True,
            'reason': 'filtered'
        }
    
    with log_lock:
        log.info(f"[{current_idx}/{total_urls}] Analyzing {sanitized_url}...")
        if dry_run:
            log.info(f"  [DRY RUN MODE] - No changes will be made")
        if existing_mobile_psi:
            log.info(f"  Mobile PSI URL already exists (column F filled), will only update desktop")
        if existing_desktop_psi:
            log.info(f"  Desktop PSI URL already exists (column G filled), will only update mobile")
        if skip_cache:
            log.info(f"  Cache disabled for this analysis")
    
    if dry_run:
        with log_lock:
            log.info(f"  [DRY RUN] Would analyze {sanitized_url}")
            log.info("")
        return {
            'row': row_index,
            'url': url,
            'dry_run': True
        }
    
    try:
        result = cypress_runner.run_analysis(sanitized_url, timeout=timeout, skip_cache=skip_cache)
        
        mobile_score = result.get('mobile_score')
        desktop_score = result.get('desktop_score')
        mobile_psi_url = result.get('mobile_psi_url')
        desktop_psi_url = result.get('desktop_psi_url')
        
        mobile_status = "PASS" if mobile_score is not None and mobile_score >= SCORE_THRESHOLD else "FAIL"
        desktop_status = "PASS" if desktop_score is not None and desktop_score >= SCORE_THRESHOLD else "FAIL"
        
        with log_lock:
            log.info(f"  Mobile: {mobile_score if mobile_score is not None else 'N/A'} ({mobile_status})")
            log.info(f"  Desktop: {desktop_score if desktop_score is not None else 'N/A'} ({desktop_status})")
        
        updates = []
        
        if not existing_mobile_psi and mobile_score is not None:
            if mobile_score >= SCORE_THRESHOLD:
                updates.append((row_index, MOBILE_COLUMN, 'passed'))
            elif mobile_psi_url:
                updates.append((row_index, MOBILE_COLUMN, mobile_psi_url))
        
        if not existing_desktop_psi and desktop_score is not None:
            if desktop_score >= SCORE_THRESHOLD:
                updates.append((row_index, DESKTOP_COLUMN, 'passed'))
            elif desktop_psi_url:
                updates.append((row_index, DESKTOP_COLUMN, desktop_psi_url))
        
        if updates:
            try:
                sheets_client.batch_write_psi_urls(
                    spreadsheet_id,
                    tab_name,
                    updates,
                    service=service,
                    dry_run=dry_run
                )
                with log_lock:
                    log.info(f"  Updated spreadsheet with {len(updates)} value(s)")
            except PermanentError as e:
                with log_lock:
                    logger.log_error_with_context(
                        log,
                        f"  PERMANENT ERROR: Failed to update spreadsheet: {e}",
                        exception=e,
                        context={'url': url, 'row': row_index}
                    )
                metrics.record_error(
                    error_type='PermanentError',
                    function_name='batch_write_psi_urls',
                    error_message=str(e),
                    is_retryable=False,
                    traceback=traceback.format_exc()
                )
            except Exception as e:
                with log_lock:
                    logger.log_error_with_context(
                        log,
                        f"  WARNING: Failed to update spreadsheet: {e}",
                        exception=e,
                        context={'url': url, 'row': row_index}
                    )
                metrics.record_error(
                    error_type=type(e).__name__,
                    function_name='batch_write_psi_urls',
                    error_message=str(e),
                    is_retryable=True,
                    traceback=traceback.format_exc()
                )
        
        with log_lock:
            log.info(f"Successfully analyzed {url}")
            log.info("")
        
        return {
            'row': row_index,
            'url': url,
            'mobile_score': mobile_score,
            'desktop_score': desktop_score,
            'mobile_psi_url': mobile_psi_url,
            'desktop_psi_url': desktop_psi_url
        }
        
    except cypress_runner.CypressTimeoutError as e:
        error_msg = f"Timeout - {e}"
        with log_lock:
            logger.log_error_with_context(
                log,
                f"  ERROR: {error_msg}",
                exception=e,
                context={'url': url, 'row': row_index, 'timeout': timeout}
            )
            log.error(f"Failed to analyze {url} due to timeout", exc_info=True)
            log.info("")
        metrics.record_error(
            error_type='CypressTimeoutError',
            function_name='process_url',
            error_message=str(e),
            is_retryable=False,
            traceback=traceback.format_exc()
        )
        metrics_collector.record_url_failure(start_time, reason='timeout')
        return {
            'row': row_index,
            'url': url,
            'error': str(e),
            'error_type': 'timeout'
        }
        
    except cypress_runner.CypressRunnerError as e:
        error_msg = f"Cypress failed - {e}"
        with log_lock:
            logger.log_error_with_context(
                log,
                f"  ERROR: {error_msg}",
                exception=e,
                context={'url': url, 'row': row_index}
            )
            log.error(f"Failed to analyze {url} due to Cypress error", exc_info=True)
            log.info("")
        metrics.record_error(
            error_type='CypressRunnerError',
            function_name='process_url',
            error_message=str(e),
            is_retryable=True,
            traceback=traceback.format_exc()
        )
        metrics_collector.record_url_failure(start_time, reason='cypress')
        return {
            'row': row_index,
            'url': url,
            'error': str(e),
            'error_type': 'cypress'
        }
        
    except PermanentError as e:
        error_msg = f"Permanent error - {e}"
        with log_lock:
            logger.log_error_with_context(
                log,
                f"  PERMANENT ERROR: {error_msg}",
                exception=e,
                context={'url': url, 'row': row_index}
            )
            log.error(f"Failed to analyze {url} due to permanent error", exc_info=True)
            log.info("")
        metrics.record_error(
            error_type='PermanentError',
            function_name='process_url',
            error_message=str(e),
            is_retryable=False,
            traceback=traceback.format_exc()
        )
        metrics_collector.record_url_failure(start_time, reason='permanent')
        return {
            'row': row_index,
            'url': url,
            'error': str(e),
            'error_type': 'permanent'
        }
        
    except RetryableError as e:
        error_msg = f"Retryable error - {e}"
        with log_lock:
            logger.log_error_with_context(
                log,
                f"  RETRYABLE ERROR: {error_msg}",
                exception=e,
                context={'url': url, 'row': row_index}
            )
            log.error(f"Failed to analyze {url} due to retryable error", exc_info=True)
            log.info("")
        metrics.record_error(
            error_type='RetryableError',
            function_name='process_url',
            error_message=str(e),
            is_retryable=True,
            traceback=traceback.format_exc()
        )
        metrics_collector.record_url_failure(start_time, reason='retryable')
        return {
            'row': row_index,
            'url': url,
            'error': str(e),
            'error_type': 'retryable'
        }
        
    except Exception as e:
        error_msg = f"Unexpected error - {e}"
        with log_lock:
            logger.log_error_with_context(
                log,
                f"  ERROR: {error_msg}",
                exception=e,
                context={'url': url, 'row': row_index}
            )
            log.error(f"Failed to analyze {url} due to unexpected error", exc_info=True)
            log.info("")
        metrics.record_error(
            error_type=type(e).__name__,
            function_name='process_url',
            error_message=str(e),
            is_retryable=False,
            traceback=traceback.format_exc()
        )
        metrics_collector.record_url_failure(start_time, reason='unexpected')
        return {
            'row': row_index,
            'url': url,
            'error': str(e),
            'error_type': 'unexpected'
        }


def main():
    parser = argparse.ArgumentParser(
        description='Run PageSpeed Insights audit on URLs from a Google Spreadsheet'
    )
    parser.add_argument(
        '--tab',
        required=True,
        help='Name of the spreadsheet tab to read URLs from'
    )
    parser.add_argument(
        '--spreadsheet-id',
        default=DEFAULT_SPREADSHEET_ID,
        help=f'Google Spreadsheet ID (default: {DEFAULT_SPREADSHEET_ID})'
    )
    parser.add_argument(
        '--service-account',
        default=SERVICE_ACCOUNT_FILE,
        help=f'Path to service account JSON file (default: {SERVICE_ACCOUNT_FILE})'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=600,
        help='Timeout in seconds for each Cypress run (default: 600)'
    )
    parser.add_argument(
        '--concurrency',
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f'Number of concurrent workers (default: {DEFAULT_CONCURRENCY}, range: 1-5)'
    )
    parser.add_argument(
        '--skip-cache',
        action='store_true',
        help='Skip cache and force fresh analysis for all URLs'
    )
    parser.add_argument(
        '--whitelist',
        nargs='*',
        help='URL whitelist patterns (e.g., https://example.com/* https://*.domain.com/*)'
    )
    parser.add_argument(
        '--blacklist',
        nargs='*',
        help='URL blacklist patterns (e.g., http://* https://blocked.com/*)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate the audit without making any changes to the spreadsheet'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Perform validation checks only without running the audit'
    )
    parser.add_argument(
        '--skip-dns-validation',
        action='store_true',
        help='Skip DNS resolution validation for URLs'
    )
    parser.add_argument(
        '--skip-redirect-validation',
        action='store_true',
        help='Skip redirect chain validation for URLs'
    )
    parser.add_argument(
        '--dns-timeout',
        type=float,
        default=5.0,
        help='DNS resolution timeout in seconds (default: 5.0)'
    )
    parser.add_argument(
        '--redirect-timeout',
        type=float,
        default=10.0,
        help='Redirect check timeout in seconds (default: 10.0)'
    )
    
    args = parser.parse_args()
    
    if args.concurrency < 1 or args.concurrency > 5:
        print("Error: --concurrency must be between 1 and 5")
        sys.exit(1)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    log = logger.setup_logger()
    metrics = get_global_metrics()
    
    if not os.path.exists(args.service_account):
        log.error(f"Service account file not found: {args.service_account}")
        sys.exit(1)
    
    log.info(f"Authenticating with Google Sheets...")
    try:
        service = sheets_client.authenticate(args.service_account)
        log.info("Authentication successful")
    except PermanentError as e:
        log.error(f"\n{e}")
        log.error("\nSetup Instructions:")
        log.error("1. Go to https://console.cloud.google.com/")
        log.error("2. Create a service account and download the JSON key")
        log.error(f"3. Save it as '{args.service_account}' in the project root")
        log.error("4. Enable Google Sheets API in your project")
        log.error("5. Share your spreadsheet with the service account email")
        sys.exit(1)
    except Exception as e:
        logger.log_error_with_context(
            log,
            f"Failed to authenticate: {e}",
            exception=e,
            context={'service_account_file': args.service_account}
        )
        sys.exit(1)
    
    log.info(f"Validating spreadsheet schema for tab '{args.tab}'...")
    schema_validator = SpreadsheetSchemaValidator()
    schema_valid, schema_errors = schema_validator.validate_schema(
        args.spreadsheet_id, 
        args.tab, 
        service
    )
    
    if not schema_valid:
        log.error("Schema validation failed:")
        for error in schema_errors:
            log.error(f"  - {error}")
        if not args.validate_only:
            log.error("\nContinuing with audit despite schema issues...")
    
    log.info(f"Reading URLs from spreadsheet tab '{args.tab}'...")
    try:
        urls = sheets_client.read_urls(args.spreadsheet_id, args.tab, service=service)
        log.info(f"Successfully read URLs from spreadsheet")
    except PermanentError as e:
        log.error(f"\n{e}")
        sys.exit(1)
    except Exception as e:
        logger.log_error_with_context(
            log,
            f"Failed to read URLs: {e}",
            exception=e,
            context={
                'spreadsheet_id': args.spreadsheet_id,
                'tab_name': args.tab
            }
        )
        sys.exit(1)
    
    if not urls:
        log.info("No URLs found in the spreadsheet.")
        sys.exit(0)
    
    log.info("")
    data_quality_checker = DataQualityChecker()
    quality_results = data_quality_checker.perform_quality_checks(urls)
    log.info("")
    
    url_filter = None
    if args.whitelist or args.blacklist:
        url_filter = URLFilter(whitelist=args.whitelist, blacklist=args.blacklist)
    
    url_validator = URLValidator(
        dns_timeout=args.dns_timeout,
        redirect_timeout=args.redirect_timeout
    )
    
    validate_dns = not args.skip_dns_validation
    validate_redirects = not args.skip_redirect_validation
    
    if args.validate_only:
        log.info("=" * 80)
        log.info("VALIDATION MODE: Performing URL validations without running audit")
        log.info("=" * 80)
        log.info(f"Total URLs to validate: {len(urls)}")
        log.info(f"DNS validation: {'enabled' if validate_dns else 'disabled'}")
        log.info(f"Redirect validation: {'enabled' if validate_redirects else 'disabled'}")
        log.info("")
        
        validation_results = []
        for idx, (row_index, url, _, _, should_skip) in enumerate(urls, start=1):
            log.info(f"[{idx}/{len(urls)}] Validating {url}...")
            
            try:
                sanitized_url = URLFilter.sanitize_url(url)
                normalized_url = URLNormalizer.normalize_url(sanitized_url)
                
                is_valid, val_result = url_validator.validate_url(
                    normalized_url,
                    check_dns=validate_dns,
                    check_redirects=validate_redirects
                )
                
                validation_results.append({
                    'row': row_index,
                    'url': url,
                    'normalized_url': normalized_url,
                    'valid': is_valid,
                    'results': val_result
                })
                
                if is_valid:
                    log.info(f"  ✓ Valid")
                    if val_result.get('redirect_count') and val_result['redirect_count'] > 0:
                        log.info(f"  ⚠ Redirects: {val_result['redirect_count']}")
                else:
                    log.error(f"  ✗ Invalid")
                    for error in val_result['errors']:
                        log.error(f"    - {error}")
                
            except Exception as e:
                log.error(f"  ✗ Error: {e}")
                validation_results.append({
                    'row': row_index,
                    'url': url,
                    'valid': False,
                    'error': str(e)
                })
            
            log.info("")
        
        log.info("=" * 80)
        log.info("VALIDATION SUMMARY")
        log.info("=" * 80)
        
        valid_count = sum(1 for r in validation_results if r.get('valid', False))
        invalid_count = len(validation_results) - valid_count
        redirect_count = sum(1 for r in validation_results 
                           if r.get('results', {}).get('redirect_count', 0) > 0)
        
        log.info(f"Total URLs validated: {len(validation_results)}")
        log.info(f"Valid URLs: {valid_count}")
        log.info(f"Invalid URLs: {invalid_count}")
        log.info(f"URLs with redirects: {redirect_count}")
        
        if invalid_count > 0:
            log.info("")
            log.info("Invalid URLs:")
            for r in validation_results:
                if not r.get('valid', False):
                    log.info(f"  Row {r['row']}: {r['url']}")
                    if 'results' in r and 'errors' in r['results']:
                        for error in r['results']['errors']:
                            log.info(f"    - {error}")
                    elif 'error' in r:
                        log.info(f"    - {r['error']}")
        
        if redirect_count > 0:
            log.info("")
            log.info("URLs with redirects:")
            for r in validation_results:
                if r.get('results', {}).get('redirect_count', 0) > 0:
                    redirect_num = r['results']['redirect_count']
                    log.info(f"  Row {r['row']}: {r['url']} ({redirect_num} redirect{'s' if redirect_num > 1 else ''})")
        
        log.info("=" * 80)
        sys.exit(0)
    
    log.info(f"Found {len(urls)} URLs to analyze.")
    log.info(f"Using {args.concurrency} concurrent workers.")
    if args.skip_cache:
        log.info("Cache is disabled (--skip-cache flag)")
    if args.dry_run:
        log.info("DRY RUN MODE: No changes will be made to the spreadsheet")
    if args.whitelist:
        log.info(f"URL whitelist: {args.whitelist}")
    if args.blacklist:
        log.info(f"URL blacklist: {args.blacklist}")
    if not validate_dns:
        log.info("DNS validation: disabled")
    if not validate_redirects:
        log.info("Redirect validation: disabled")
    log.info("")
    
    processed_count = {'count': 0, 'lock': threading.Lock()}
    results = []
    
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {
            executor.submit(
                process_url,
                url_data,
                args.spreadsheet_id,
                args.tab,
                service,
                args.timeout,
                len(urls),
                processed_count,
                args.skip_cache,
                url_filter,
                args.dry_run,
                url_validator,
                validate_dns,
                validate_redirects
            ): url_data for url_data in urls
        }
        
        try:
            for future in as_completed(futures):
                if shutdown_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    log.info("Shutdown requested. Cancelling remaining tasks...")
                    break
                
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    url_data = futures[future]
                    with log_lock:
                        logger.log_error_with_context(
                            log,
                            f"Unexpected error processing {url_data[1]}: {e}",
                            exception=e,
                            context={'url': url_data[1], 'row': url_data[0]}
                        )
                    metrics.record_error(
                        error_type=type(e).__name__,
                        function_name='process_url',
                        error_message=str(e),
                        is_retryable=False,
                        traceback=traceback.format_exc()
                    )
                    results.append({
                        'row': url_data[0],
                        'url': url_data[1],
                        'error': str(e),
                        'error_type': 'unexpected'
                    })
        except KeyboardInterrupt:
            executor.shutdown(wait=False, cancel_futures=True)
            log.info("Keyboard interrupt received. Shutting down...")
    
    if shutdown_event.is_set():
        log.info("\nAudit interrupted by user. Partial results below.\n")
    
    log.info("=" * 80)
    log.info("AUDIT SUMMARY")
    log.info("=" * 80)
    
    total_urls = len(results)
    skipped = sum(1 for r in results if r.get('skipped', False))
    dry_run_count = sum(1 for r in results if r.get('dry_run', False))
    analyzed = sum(1 for r in results if not r.get('skipped', False) and 'error' not in r and not r.get('dry_run', False))
    failed = sum(1 for r in results if 'error' in r)
    
    mobile_pass = sum(1 for r in results if r.get('mobile_score') is not None and r['mobile_score'] >= SCORE_THRESHOLD)
    mobile_fail = sum(1 for r in results if r.get('mobile_score') is not None and r['mobile_score'] < SCORE_THRESHOLD)
    desktop_pass = sum(1 for r in results if r.get('desktop_score') is not None and r['desktop_score'] >= SCORE_THRESHOLD)
    desktop_fail = sum(1 for r in results if r.get('desktop_score') is not None and r['desktop_score'] < SCORE_THRESHOLD)
    
    log.info(f"Total URLs processed: {total_urls}")
    log.info(f"URLs skipped: {skipped}")
    if args.dry_run:
        log.info(f"URLs simulated (dry run): {dry_run_count}")
    log.info(f"URLs analyzed: {analyzed}")
    log.info(f"Failed analyses: {failed}")
    log.info("")
    log.info(f"Mobile scores >= {SCORE_THRESHOLD}: {mobile_pass}")
    log.info(f"Mobile scores < {SCORE_THRESHOLD}: {mobile_fail}")
    log.info(f"Desktop scores >= {SCORE_THRESHOLD}: {desktop_pass}")
    log.info(f"Desktop scores < {SCORE_THRESHOLD}: {desktop_fail}")
    log.info("")
    
    validation_failed = sum(1 for r in results if r.get('error_type') == 'validation_failed')
    if validation_failed > 0:
        log.info(f"URLs failed validation: {validation_failed}")
    
    if failed > 0:
        log.info("Failed URLs:")
        error_types = {}
        for r in results:
            if 'error' in r:
                error_type = r.get('error_type', 'unknown')
                error_types[error_type] = error_types.get(error_type, 0) + 1
                log.info(f"  Row {r['row']}: {r['url']}")
                log.info(f"    Error Type: {error_type}")
                log.info(f"    Error: {r['error']}")
        
        log.info("")
        log.info("Error Types Summary:")
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            log.info(f"  {error_type}: {count}")
        log.info("")
    
    if mobile_pass > 0 or desktop_pass > 0:
        log.info(f"Cells with score >= {SCORE_THRESHOLD} marked as 'passed'.")
    if mobile_fail > 0 or desktop_fail > 0:
        log.info(f"PSI URLs for failing scores written to columns {MOBILE_COLUMN} (mobile) and {DESKTOP_COLUMN} (desktop).")
    
    log.info("=" * 80)
    
    log.info("")
    metrics.print_summary()
    
    log.info("")
    metrics_collector = get_metrics_collector()
    metrics_collector.save_json_metrics('metrics.json')
    metrics_collector.save_prometheus_metrics('metrics.prom')
    log.info("Metrics saved to metrics.json and metrics.prom")
    log.info("Generate HTML dashboard with: python generate_report.py")
    
    cypress_runner.shutdown_pool()


if __name__ == '__main__':
    try:
        main()
    finally:
        cypress_runner.shutdown_pool()
