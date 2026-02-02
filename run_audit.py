#!/usr/bin/env python3
import argparse
import sys
import os
from typing import List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from sheets import sheets_client
from qa import cypress_runner
from utils import logger


DEFAULT_SPREADSHEET_ID = '1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I'
SERVICE_ACCOUNT_FILE = 'service-account.json'
MOBILE_COLUMN = 'F'
DESKTOP_COLUMN = 'G'
SCORE_THRESHOLD = 80


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
        default=900,
        help='Timeout in seconds for each Cypress run (default: 900)'
    )
    
    args = parser.parse_args()
    
    log = logger.setup_logger()
    
    if not os.path.exists(args.service_account):
        log.error(f"Service account file not found: {args.service_account}")
        sys.exit(1)
    
    log.info(f"Authenticating with Google Sheets...")
    try:
        service = sheets_client.authenticate(args.service_account)
        log.info("Authentication successful")
    except FileNotFoundError as e:
        log.error(f"\n{e}")
        log.error("\nSetup Instructions:")
        log.error("1. Go to https://console.cloud.google.com/")
        log.error("2. Create a service account and download the JSON key")
        log.error(f"3. Save it as '{args.service_account}' in the project root")
        log.error("4. Enable Google Sheets API in your project")
        log.error("5. Share your spreadsheet with the service account email")
        sys.exit(1)
    except ValueError as e:
        log.error(f"Authentication error: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"Failed to authenticate: {e}", exc_info=True)
        sys.exit(1)
    
    log.info(f"Reading URLs from spreadsheet tab '{args.tab}'...")
    try:
        urls = sheets_client.read_urls(args.spreadsheet_id, args.tab, service=service)
        log.info(f"Successfully read URLs from spreadsheet")
    except ValueError as e:
        log.error(f"\n{e}")
        sys.exit(1)
    except PermissionError as e:
        log.error(f"\n{e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"Failed to read URLs: {e}", exc_info=True)
        sys.exit(1)
    
    if not urls:
        log.info("No URLs found in the spreadsheet.")
        sys.exit(0)
    
    log.info(f"Found {len(urls)} URLs to analyze.\n")
    
    results = []
    updates = []
    skipped_count = 0
    
    for idx, (row_index, url, existing_mobile_psi, existing_desktop_psi, should_skip) in enumerate(urls, start=1):
        if should_skip:
            log.info(f"[{idx}/{len(urls)}] Skipping {url} (contains 'passed' or has green background in column F or G)")
            skipped_count += 1
            results.append({
                'row': row_index,
                'url': url,
                'skipped': True
            })
            log.info("")
            continue
        
        if existing_mobile_psi and existing_desktop_psi:
            log.info(f"[{idx}/{len(urls)}] Skipping {url} (both columns F and G already filled)")
            skipped_count += 1
            results.append({
                'row': row_index,
                'url': url,
                'skipped': True
            })
            log.info("")
            continue
        
        log.info(f"[{idx}/{len(urls)}] Analyzing {url}...")
        if existing_mobile_psi:
            log.info(f"  Mobile PSI URL already exists (column F filled), will only update desktop")
        if existing_desktop_psi:
            log.info(f"  Desktop PSI URL already exists (column G filled), will only update mobile")
        
        try:
            result = cypress_runner.run_analysis(url, timeout=args.timeout)
            
            mobile_score = result.get('mobile_score')
            desktop_score = result.get('desktop_score')
            mobile_psi_url = result.get('mobile_psi_url')
            desktop_psi_url = result.get('desktop_psi_url')
            
            mobile_status = "PASS" if mobile_score is not None and mobile_score >= SCORE_THRESHOLD else "FAIL"
            desktop_status = "PASS" if desktop_score is not None and desktop_score >= SCORE_THRESHOLD else "FAIL"
            
            log.info(f"  Mobile: {mobile_score if mobile_score is not None else 'N/A'} ({mobile_status})")
            log.info(f"  Desktop: {desktop_score if desktop_score is not None else 'N/A'} ({desktop_status})")
            
            results.append({
                'row': row_index,
                'url': url,
                'mobile_score': mobile_score,
                'desktop_score': desktop_score,
                'mobile_psi_url': mobile_psi_url,
                'desktop_psi_url': desktop_psi_url
            })
            
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
            
            log.info(f"Successfully analyzed {url}")
            
        except cypress_runner.CypressTimeoutError as e:
            error_msg = f"Timeout - {e}"
            log.error(f"  ERROR: {error_msg}")
            log.error(f"Failed to analyze {url} due to timeout", exc_info=True)
            results.append({
                'row': row_index,
                'url': url,
                'error': str(e)
            })
        except cypress_runner.CypressRunnerError as e:
            error_msg = f"Cypress failed - {e}"
            log.error(f"  ERROR: {error_msg}")
            log.error(f"Failed to analyze {url} due to Cypress error", exc_info=True)
            results.append({
                'row': row_index,
                'url': url,
                'error': str(e)
            })
        except Exception as e:
            error_msg = f"Unexpected error - {e}"
            log.error(f"  ERROR: {error_msg}")
            log.error(f"Failed to analyze {url} due to unexpected error", exc_info=True)
            results.append({
                'row': row_index,
                'url': url,
                'error': str(e)
            })
        
        log.info("")
    
    if updates:
        log.info(f"Updating spreadsheet with {len(updates)} values...")
        try:
            sheets_client.batch_write_psi_urls(
                args.spreadsheet_id,
                args.tab,
                updates,
                service=service
            )
            log.info("Spreadsheet updated successfully.\n")
        except Exception as e:
            log.error(f"Failed to update spreadsheet: {e}", exc_info=True)
    else:
        log.info("No updates to write.\n")
    
    log.info("=" * 80)
    log.info("AUDIT SUMMARY")
    log.info("=" * 80)
    
    total_urls = len(results)
    skipped = sum(1 for r in results if r.get('skipped', False))
    analyzed = sum(1 for r in results if not r.get('skipped', False) and 'error' not in r)
    failed = sum(1 for r in results if 'error' in r)
    
    mobile_pass = sum(1 for r in results if r.get('mobile_score') is not None and r['mobile_score'] >= SCORE_THRESHOLD)
    mobile_fail = sum(1 for r in results if r.get('mobile_score') is not None and r['mobile_score'] < SCORE_THRESHOLD)
    desktop_pass = sum(1 for r in results if r.get('desktop_score') is not None and r['desktop_score'] >= SCORE_THRESHOLD)
    desktop_fail = sum(1 for r in results if r.get('desktop_score') is not None and r['desktop_score'] < SCORE_THRESHOLD)
    
    log.info(f"Total URLs found: {total_urls}")
    log.info(f"URLs skipped: {skipped}")
    log.info(f"URLs analyzed: {analyzed}")
    log.info(f"Failed analyses: {failed}")
    log.info("")
    log.info(f"Mobile scores >= {SCORE_THRESHOLD}: {mobile_pass}")
    log.info(f"Mobile scores < {SCORE_THRESHOLD}: {mobile_fail}")
    log.info(f"Desktop scores >= {SCORE_THRESHOLD}: {desktop_pass}")
    log.info(f"Desktop scores < {SCORE_THRESHOLD}: {desktop_fail}")
    log.info("")
    
    if failed > 0:
        log.info("Failed URLs:")
        for r in results:
            if 'error' in r:
                log.info(f"  Row {r['row']}: {r['url']}")
                log.info(f"    Error: {r['error']}")
        log.info("")
    
    if mobile_pass > 0 or desktop_pass > 0:
        log.info(f"Cells with score >= {SCORE_THRESHOLD} marked as 'passed'.")
    if mobile_fail > 0 or desktop_fail > 0:
        log.info(f"PSI URLs for failing scores written to columns {MOBILE_COLUMN} (mobile) and {DESKTOP_COLUMN} (desktop).")
    
    log.info("=" * 80)


if __name__ == '__main__':
    main()
