#!/usr/bin/env python3
import argparse
import sys
import os
import signal
import traceback
import re
import time
from typing import List, Tuple, Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from sheets import sheets_client
from sheets.schema_validator import SpreadsheetSchemaValidator
from sheets.data_quality_checker import DataQualityChecker
from qa import playwright_runner
from utils import logger
from utils.error_metrics import get_global_metrics
from utils.exceptions import RetryableError, PermanentError
from utils.url_validator import URLValidator, URLNormalizer
from utils.config_loader import ConfigLoader
from utils.result_exporter import ResultExporter
from metrics.metrics_collector import get_metrics_collector
from security.url_filter import URLFilter

try:
    from version import __version__
except ImportError:
    __version__ = "1.0.0"


DEFAULT_SPREADSHEET_ID = '1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I'
SERVICE_ACCOUNT_FILE = 'service-account.json'
MOBILE_COLUMN = 'F'
DESKTOP_COLUMN = 'G'
SCORE_THRESHOLD = 80


shutdown_requested = False


def signal_handler(signum, frame):
    global shutdown_requested
    log = logger.get_logger()
    log.info("\nReceived shutdown signal. Stopping after current URL...")
    shutdown_requested = True


def process_url(
    url_data: Tuple[int, str, Optional[str], Optional[str], bool],
    spreadsheet_id: str,
    tab_name: str,
    service,
    timeout: int,
    total_urls: int,
    current_idx: int,
    skip_cache: bool = False,
    url_filter: Optional[URLFilter] = None,
    dry_run: bool = False,
    url_validator: Optional[URLValidator] = None,
    validate_dns: bool = True,
    validate_redirects: bool = True,
    force_retry: bool = False
) -> Dict[str, Any]:
    log = logger.get_logger()
    metrics = get_global_metrics()
    metrics_collector = get_metrics_collector()
    row_index, url, existing_mobile_psi, existing_desktop_psi, should_skip = url_data
    
    start_time = metrics_collector.record_url_start()
    
    if shutdown_requested:
        return {
            'row': row_index,
            'url': url,
            'skipped': True,
            'shutdown': True
        }
    
    if should_skip:
        log.info(f"[{current_idx}/{total_urls}] Skipping {url} (contains 'passed' or has green background in column F or G)")
        log.info("")
        metrics_collector.record_url_skipped()
        return {
            'row': row_index,
            'url': url,
            'skipped': True
        }
    
    if existing_mobile_psi and existing_desktop_psi:
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
            log.warning(f"  URL has {validation_results['redirect_count']} redirect(s)")
    
    try:
        normalized_url = URLNormalizer.normalize_url(sanitized_url)
        if normalized_url != sanitized_url:
            log.info(f"  Normalized URL: {normalized_url}")
            sanitized_url = normalized_url
    except Exception as e:
        log.warning(f"  Could not normalize URL: {e}")
    
    if url_filter and not url_filter.is_allowed(sanitized_url):
        log.info(f"[{current_idx}/{total_urls}] URL rejected by filter: {sanitized_url}")
        log.info("")
        metrics_collector.record_url_skipped()
        return {
            'row': row_index,
            'url': url,
            'skipped': True,
            'reason': 'filtered'
        }
    
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
        log.info(f"  [DRY RUN] Would analyze {sanitized_url}")
        log.info("")
        return {
            'row': row_index,
            'url': url,
            'dry_run': True
        }
    
    try:
        result = playwright_runner.run_analysis(sanitized_url, timeout=timeout, skip_cache=skip_cache, force_retry=force_retry)
        
        mobile_score = result.get('mobile_score')
        desktop_score = result.get('desktop_score')
        mobile_psi_url = result.get('mobile_psi_url')
        desktop_psi_url = result.get('desktop_psi_url')
        
        mobile_status = "PASS" if mobile_score is not None and mobile_score >= SCORE_THRESHOLD else "FAIL"
        desktop_status = "PASS" if desktop_score is not None and desktop_score >= SCORE_THRESHOLD else "FAIL"
        
        log.info(f"  Mobile: {mobile_score if mobile_score is not None else 'N/A'} ({mobile_status})")
        log.info(f"  Desktop: {desktop_score if desktop_score is not None else 'N/A'} ({desktop_status})")
        
        updates = []
        
        if not existing_mobile_psi and mobile_score is not None:
            if mobile_score >= SCORE_THRESHOLD:
                updates.append((row_index, MOBILE_COLUMN, 'passed'))
            else:
                if mobile_psi_url:
                    updates.append((row_index, MOBILE_COLUMN, mobile_psi_url))
        
        if not existing_desktop_psi and desktop_score is not None:
            if desktop_score >= SCORE_THRESHOLD:
                updates.append((row_index, DESKTOP_COLUMN, 'passed'))
            else:
                if desktop_psi_url:
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
                log.info(f"  Updated spreadsheet with {len(updates)} value(s)")
            except PermanentError as e:
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
        
        log.info(f"Successfully analyzed {url}")
        log.info("")
        
        from_cache = result.get('_from_cache', False)
        metrics_collector.record_url_success(start_time, from_cache=from_cache)
        
        if not from_cache:
            metrics_collector.record_sequential_url_processed()
        
        return {
            'row': row_index,
            'url': url,
            'mobile_score': mobile_score,
            'desktop_score': desktop_score,
            'mobile_psi_url': mobile_psi_url,
            'desktop_psi_url': desktop_psi_url,
            'success': True
        }
        
    except playwright_runner.PlaywrightAnalysisTimeoutError as e:
        error_msg = f"Timeout - {e}"
        short_error = f"ERROR: Analysis timeout ({timeout}s)"
        logger.log_error_with_context(
            log,
            f"  ERROR: {error_msg}",
            exception=e,
            context={'url': url, 'row': row_index, 'timeout': timeout}
        )
        log.error(f"Failed to analyze {url} due to timeout", exc_info=True)
        log.info("")
        metrics.record_error(
            error_type='PlaywrightAnalysisTimeoutError',
            function_name='process_url',
            error_message=str(e),
            is_retryable=False,
            traceback=traceback.format_exc()
        )
        metrics_collector.record_url_failure(start_time, reason='timeout')
        
        updates = []
        if not existing_mobile_psi:
            updates.append((row_index, MOBILE_COLUMN, short_error))
        if not existing_desktop_psi:
            updates.append((row_index, DESKTOP_COLUMN, short_error))
        
        if updates:
            try:
                sheets_client.batch_write_psi_urls(
                    spreadsheet_id,
                    tab_name,
                    updates,
                    service=service,
                    dry_run=dry_run
                )
                log.info(f"  Wrote error indicator to spreadsheet")
            except Exception as write_error:
                log.error(f"  Failed to write error indicator: {write_error}")
        
        return {
            'row': row_index,
            'url': url,
            'error': str(e),
            'error_type': 'timeout',
            'failed': True
        }
        
    except playwright_runner.PlaywrightRunnerError as e:
        error_msg = f"Playwright failed - {e}"
        short_error = f"ERROR: Playwright failed"
        logger.log_error_with_context(
            log,
            f"  ERROR: {error_msg}",
            exception=e,
            context={'url': url, 'row': row_index}
        )
        log.error(f"Failed to analyze {url} due to Playwright error", exc_info=True)
        log.info("")
        metrics.record_error(
            error_type='PlaywrightRunnerError',
            function_name='process_url',
            error_message=str(e),
            is_retryable=True,
            traceback=traceback.format_exc()
        )
        metrics_collector.record_url_failure(start_time, reason='playwright')
        
        updates = []
        if not existing_mobile_psi:
            updates.append((row_index, MOBILE_COLUMN, short_error))
        if not existing_desktop_psi:
            updates.append((row_index, DESKTOP_COLUMN, short_error))
        
        if updates:
            try:
                sheets_client.batch_write_psi_urls(
                    spreadsheet_id,
                    tab_name,
                    updates,
                    service=service,
                    dry_run=dry_run
                )
                log.info(f"  Wrote error indicator to spreadsheet")
            except Exception as write_error:
                log.error(f"  Failed to write error indicator: {write_error}")
        
        return {
            'row': row_index,
            'url': url,
            'error': str(e),
            'error_type': 'playwright',
            'failed': True
        }
        
    except PermanentError as e:
        error_msg = f"Permanent error - {e}"
        short_error = f"ERROR: Permanent error"
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
        
        updates = []
        if not existing_mobile_psi:
            updates.append((row_index, MOBILE_COLUMN, short_error))
        if not existing_desktop_psi:
            updates.append((row_index, DESKTOP_COLUMN, short_error))
        
        if updates:
            try:
                sheets_client.batch_write_psi_urls(
                    spreadsheet_id,
                    tab_name,
                    updates,
                    service=service,
                    dry_run=dry_run
                )
                log.info(f"  Wrote error indicator to spreadsheet")
            except Exception as write_error:
                log.error(f"  Failed to write error indicator: {write_error}")
        
        return {
            'row': row_index,
            'url': url,
            'error': str(e),
            'error_type': 'permanent',
            'failed': True
        }
        
    except RetryableError as e:
        error_msg = f"Retryable error - {e}"
        short_error = f"ERROR: Retryable error"
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
        
        updates = []
        if not existing_mobile_psi:
            updates.append((row_index, MOBILE_COLUMN, short_error))
        if not existing_desktop_psi:
            updates.append((row_index, DESKTOP_COLUMN, short_error))
        
        if updates:
            try:
                sheets_client.batch_write_psi_urls(
                    spreadsheet_id,
                    tab_name,
                    updates,
                    service=service,
                    dry_run=dry_run
                )
                log.info(f"  Wrote error indicator to spreadsheet")
            except Exception as write_error:
                log.error(f"  Failed to write error indicator: {write_error}")
        
        return {
            'row': row_index,
            'url': url,
            'error': str(e),
            'error_type': 'retryable',
            'failed': True
        }
        
    except Exception as e:
        error_msg = f"Unexpected error - {e}"
        short_error = f"ERROR: Unexpected error"
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
        
        updates = []
        if not existing_mobile_psi:
            updates.append((row_index, MOBILE_COLUMN, short_error))
        if not existing_desktop_psi:
            updates.append((row_index, DESKTOP_COLUMN, short_error))
        
        if updates:
            try:
                sheets_client.batch_write_psi_urls(
                    spreadsheet_id,
                    tab_name,
                    updates,
                    service=service,
                    dry_run=dry_run
                )
                log.info(f"  Wrote error indicator to spreadsheet")
            except Exception as write_error:
                log.error(f"  Failed to write error indicator: {write_error}")
        
        return {
            'row': row_index,
            'url': url,
            'error': str(e),
            'error_type': 'unexpected',
            'failed': True
        }


def main():
    parser = argparse.ArgumentParser(
        description='Run PageSpeed Insights audit on URLs from a Google Spreadsheet'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )
    parser.add_argument(
        '--tab',
        required=False,
        help='Name of the spreadsheet tab to read URLs from'
    )
    parser.add_argument(
        '--spreadsheet-id',
        default=None,
        help=f'Google Spreadsheet ID (default: {DEFAULT_SPREADSHEET_ID})'
    )
    parser.add_argument(
        '--service-account',
        default=None,
        help=f'Path to service account JSON file (default: {SERVICE_ACCOUNT_FILE})'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=None,
        help='Timeout in seconds for each Cypress run (default: 600)'
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
        default=None,
        help='DNS resolution timeout in seconds (default: 5.0)'
    )
    parser.add_argument(
        '--redirect-timeout',
        type=float,
        default=None,
        help='Redirect check timeout in seconds (default: 10.0)'
    )
    parser.add_argument(
        '--resume-from-row',
        type=int,
        default=None,
        help='Resume audit from specific row number (1-based)'
    )
    parser.add_argument(
        '--filter',
        type=str,
        default=None,
        help='Process only URLs matching this regex pattern'
    )
    parser.add_argument(
        '--export-json',
        type=str,
        default=None,
        help='Export results to JSON file'
    )
    parser.add_argument(
        '--export-csv',
        type=str,
        default=None,
        help='Export results to CSV file'
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to YAML configuration file'
    )
    parser.add_argument(
        '--force-retry',
        action='store_true',
        help='Bypass circuit breaker and force retries during critical runs'
    )
    parser.add_argument(
        '--debug-mode',
        action='store_true',
        help='Enable debug mode with verbose Playwright logging, screenshots, and HTML capture on errors'
    )
    parser.add_argument(
        '--url-delay',
        type=int,
        default=5,
        help='Inter-URL delay in seconds (default: 5, range: 0-60)'
    )
    parser.add_argument(
        '--refresh-interval',
        type=int,
        default=10,
        help='Browser instance refresh interval in number of analyses (default: 10, 0 to disable auto-refresh)'
    )
    parser.add_argument(
        '--fast-mode',
        action='store_true',
        help='Enable fast mode with aggressive timeouts (90s analysis timeout) for faster but potentially less reliable results'
    )
    
    args = parser.parse_args()
    
    if args.config:
        try:
            config = ConfigLoader.load_config(args.config)
            args = ConfigLoader.merge_config_with_args(config, args)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error loading config file: {e}")
            sys.exit(1)
    
    if args.spreadsheet_id is None:
        args.spreadsheet_id = DEFAULT_SPREADSHEET_ID
    if args.service_account is None:
        args.service_account = SERVICE_ACCOUNT_FILE
    if args.timeout is None:
        args.timeout = 600
    
    # Fast mode overrides: aggressive timeouts for faster execution
    if args.fast_mode:
        args.timeout = 90  # Reduced from 600s default to 90s for fast mode
        if args.dns_timeout is None:
            args.dns_timeout = 2.0  # Reduced from 5.0s to 2.0s
        if args.redirect_timeout is None:
            args.redirect_timeout = 5.0  # Reduced from 10.0s to 5.0s
    else:
        if args.dns_timeout is None:
            args.dns_timeout = 5.0
        if args.redirect_timeout is None:
            args.redirect_timeout = 10.0
    
    if args.url_delay < 0 or args.url_delay > 60:
        print("Error: --url-delay must be between 0 and 60 seconds")
        sys.exit(1)
    
    if args.refresh_interval < 0:
        print("Error: --refresh-interval must be >= 0")
        sys.exit(1)
    
    if not args.tab:
        print("Error: --tab is required (or specify in config file)")
        sys.exit(1)
    
    if args.filter:
        try:
            url_filter_pattern = re.compile(args.filter)
        except re.error as e:
            print(f"Error: Invalid regex pattern for --filter: {e}")
            sys.exit(1)
    else:
        url_filter_pattern = None
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    log = logger.setup_logger()
    metrics = get_global_metrics()
    
    playwright_runner.set_refresh_interval(args.refresh_interval)
    
    if args.debug_mode:
        playwright_runner.set_debug_mode(True)
        log.info("Debug mode enabled: verbose logging, screenshots, and HTML capture on errors")
    
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
    
    if args.resume_from_row:
        original_count = len(urls)
        urls = [(row_idx, url, m_psi, d_psi, skip) for row_idx, url, m_psi, d_psi, skip in urls 
                if row_idx >= args.resume_from_row]
        log.info(f"Resuming from row {args.resume_from_row}: {len(urls)} URLs remaining (skipped {original_count - len(urls)} earlier rows)")
    
    if url_filter_pattern:
        original_count = len(urls)
        urls = [(row_idx, url, m_psi, d_psi, skip) for row_idx, url, m_psi, d_psi, skip in urls 
                if url_filter_pattern.search(url)]
        log.info(f"Applied URL filter pattern '{args.filter}': {len(urls)} URLs matched (filtered out {original_count - len(urls)} URLs)")
    
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
    if args.fast_mode:
        log.info(f"FAST MODE: Aggressive timeouts enabled (analysis: {args.timeout}s, DNS: {args.dns_timeout}s, redirects: {args.redirect_timeout}s)")
    if args.skip_cache:
        log.info("Cache is disabled (--skip-cache flag)")
    if args.dry_run:
        log.info("DRY RUN MODE: No changes will be made to the spreadsheet")
    if args.force_retry:
        log.info("FORCE RETRY MODE: Circuit breaker will be bypassed")
    if args.debug_mode:
        log.info("DEBUG MODE: Screenshots and HTML capture enabled on errors")
    if args.refresh_interval > 0:
        log.info(f"Browser instance auto-refresh: every {args.refresh_interval} analyse{'s' if args.refresh_interval != 1 else ''}")
    else:
        log.info("Browser instance auto-refresh: disabled")
    if args.whitelist:
        log.info(f"URL whitelist: {args.whitelist}")
    if args.blacklist:
        log.info(f"URL blacklist: {args.blacklist}")
    if not validate_dns:
        log.info("DNS validation: disabled")
    if not validate_redirects:
        log.info("Redirect validation: disabled")
    if args.resume_from_row:
        log.info(f"Resuming from row: {args.resume_from_row}")
    if url_filter_pattern:
        log.info(f"URL filter pattern: {args.filter}")
    if args.url_delay > 0:
        log.info(f"Inter-URL delay: {args.url_delay} second{'s' if args.url_delay != 1 else ''}")
    log.info("")
    
    metrics_collector = get_metrics_collector()
    metrics_collector.start_sequential_processing()
    
    results = []
    
    try:
        for idx, url_data in enumerate(urls, start=1):
            if shutdown_requested:
                log.info("Shutdown requested. Stopping...")
                break
            
            result = process_url(
                url_data,
                args.spreadsheet_id,
                args.tab,
                service,
                args.timeout,
                len(urls),
                idx,
                args.skip_cache,
                url_filter,
                args.dry_run,
                url_validator,
                validate_dns,
                validate_redirects,
                args.force_retry
            )
            results.append(result)
            
            # Apply inter-URL delay (skip for first URL and skipped URLs)
            if args.url_delay > 0 and idx < len(urls):
                # Skip delay if this was the first URL
                is_first_url = (idx == 1)
                # Skip delay if URL was skipped (has 'skipped' key set to True)
                was_skipped = result.get('skipped', False)
                
                if not is_first_url and not was_skipped:
                    delay_start = time.time()
                    log.info(f"Waiting {args.url_delay} second{'s' if args.url_delay != 1 else ''} before next URL...")
                    time.sleep(args.url_delay)
                    actual_delay = time.time() - delay_start
                    metrics_collector.record_inter_url_delay(actual_delay)
            
            # Print sequential processing stats every 10 URLs
            if idx % 10 == 0 and idx > 0:
                seq_stats = metrics_collector.get_sequential_processing_stats()
                if seq_stats['active']:
                    urls_remaining = len(urls) - idx
                    if seq_stats['urls_per_minute'] > 0:
                        estimated_minutes = urls_remaining / seq_stats['urls_per_minute']
                        log.info(f"Sequential processing: {seq_stats['urls_per_minute']:.2f} URLs/min, estimated {estimated_minutes:.1f} minutes remaining")
                    else:
                        log.info(f"Sequential processing: calculating rate...")
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received. Shutting down...")
    
    if shutdown_requested:
        log.info("\nAudit interrupted by user. Partial results below.\n")
    
    log.info("=" * 80)
    log.info("AUDIT SUMMARY")
    log.info("=" * 80)
    
    total_urls = len(results)
    skipped_already_passed = sum(1 for r in results if r.get('skipped', False) and not r.get('error'))
    dry_run_count = sum(1 for r in results if r.get('dry_run', False))
    successfully_analyzed = sum(1 for r in results if r.get('success', False))
    failed_analyses = sum(1 for r in results if r.get('failed', False))
    validation_failed = sum(1 for r in results if r.get('error_type') == 'validation_failed')
    invalid_url = sum(1 for r in results if r.get('error_type') == 'invalid_url')
    
    mobile_pass = sum(1 for r in results if r.get('mobile_score') is not None and r['mobile_score'] >= SCORE_THRESHOLD)
    mobile_fail = sum(1 for r in results if r.get('mobile_score') is not None and r['mobile_score'] < SCORE_THRESHOLD)
    desktop_pass = sum(1 for r in results if r.get('desktop_score') is not None and r['desktop_score'] >= SCORE_THRESHOLD)
    desktop_fail = sum(1 for r in results if r.get('desktop_score') is not None and r['desktop_score'] < SCORE_THRESHOLD)
    
    log.info(f"Total URLs processed: {total_urls}")
    log.info(f"URLs skipped (already passed): {skipped_already_passed}")
    if args.dry_run:
        log.info(f"URLs simulated (dry run): {dry_run_count}")
    log.info(f"URLs successfully analyzed: {successfully_analyzed}")
    log.info(f"Failed analyses (ERROR written to cells): {failed_analyses}")
    if validation_failed > 0:
        log.info(f"URLs failed validation: {validation_failed}")
    if invalid_url > 0:
        log.info(f"Invalid URLs: {invalid_url}")
    log.info("")
    log.info(f"Mobile scores >= {SCORE_THRESHOLD}: {mobile_pass}")
    log.info(f"Mobile scores < {SCORE_THRESHOLD}: {mobile_fail}")
    log.info(f"Desktop scores >= {SCORE_THRESHOLD}: {desktop_pass}")
    log.info(f"Desktop scores < {SCORE_THRESHOLD}: {desktop_fail}")
    log.info("")
    
    if failed_analyses > 0:
        log.info("Failed Analyses (with ERROR indicators written to spreadsheet):")
        error_types = {}
        for r in results:
            if r.get('failed', False):
                error_type = r.get('error_type', 'unknown')
                error_types[error_type] = error_types.get(error_type, 0) + 1
                log.info(f"  Row {r['row']}: {r['url']}")
                log.info(f"    Error Type: {error_type}")
                log.info(f"    Error: {r.get('error', 'Unknown error')}")
        
        log.info("")
        log.info("Error Types Summary:")
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            log.info(f"  {error_type}: {count}")
        log.info("")
    
    if validation_failed > 0 or invalid_url > 0:
        log.info("URLs with Validation/Format Errors:")
        for r in results:
            if r.get('error_type') in ['validation_failed', 'invalid_url']:
                log.info(f"  Row {r['row']}: {r['url']}")
                log.info(f"    Error: {r.get('error', 'Unknown error')}")
        log.info("")
    
    if mobile_pass > 0 or desktop_pass > 0:
        log.info(f"Cells with score >= {SCORE_THRESHOLD} marked as 'passed'.")
    if mobile_fail > 0 or desktop_fail > 0:
        log.info(f"PSI URLs for failing scores written to columns {MOBILE_COLUMN} (mobile) and {DESKTOP_COLUMN} (desktop).")
    if failed_analyses > 0:
        log.info(f"ERROR indicators written to cells for {failed_analyses} failed analyses.")
    
    log.info("=" * 80)
    
    seq_stats = metrics_collector.get_sequential_processing_stats()
    if seq_stats['active'] and seq_stats['urls_processed'] > 0:
        log.info("")
        log.info("=" * 80)
        log.info("SEQUENTIAL PROCESSING STATISTICS")
        log.info("=" * 80)
        log.info(f"Total URLs processed: {seq_stats['urls_processed']}")
        log.info(f"Total elapsed time: {seq_stats['elapsed_time_seconds'] / 60:.2f} minutes")
        log.info(f"Processing rate: {seq_stats['urls_per_minute']:.2f} URLs per minute")
        
        inter_url_stats = metrics_collector.get_metrics()['inter_url_delays']
        if inter_url_stats['count'] > 0:
            log.info(f"Average inter-URL delay: {inter_url_stats['avg_delay_seconds']:.2f} seconds")
            log.info(f"Total inter-URL delay time: {inter_url_stats['total_delay_seconds'] / 60:.2f} minutes")
        log.info("=" * 80)
    
    if args.export_json:
        try:
            ResultExporter.export_to_json(results, args.export_json)
            log.info(f"Results exported to JSON: {args.export_json}")
        except Exception as e:
            log.error(f"Failed to export results to JSON: {e}")
    
    if args.export_csv:
        try:
            ResultExporter.export_to_csv(results, args.export_csv)
            log.info(f"Results exported to CSV: {args.export_csv}")
        except Exception as e:
            log.error(f"Failed to export results to CSV: {e}")
    
    log.info("")
    metrics.print_summary()
    
    log.info("")
    metrics_collector = get_metrics_collector()
    metrics_collector.save_json_metrics('metrics.json')
    metrics_collector.save_prometheus_metrics('metrics.prom')
    log.info("Metrics saved to metrics.json and metrics.prom")
    log.info("Generate HTML dashboard with: python generate_report.py")
    
    playwright_runner.shutdown_pool()


if __name__ == '__main__':
    try:
        main()
    finally:
        playwright_runner.shutdown_pool()
