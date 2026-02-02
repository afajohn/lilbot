#!/usr/bin/env python3
import argparse
import sys
import os
from typing import List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from sheets import sheets_client
from qa import cypress_runner


DEFAULT_SPREADSHEET_ID = '1vF4ySHs3nZVD6hkb8CWH7evRAy2V93DhS3wQ9rO3MhU'
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
        default=300,
        help='Timeout in seconds for each Cypress run (default: 300)'
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.service_account):
        print(f"Error: Service account file not found: {args.service_account}")
        sys.exit(1)
    
    print(f"Authenticating with Google Sheets...")
    try:
        service = sheets_client.authenticate(args.service_account)
    except Exception as e:
        print(f"Error: Failed to authenticate: {e}")
        sys.exit(1)
    
    print(f"Reading URLs from spreadsheet tab '{args.tab}'...")
    try:
        urls = sheets_client.read_urls(args.spreadsheet_id, args.tab, service=service)
    except Exception as e:
        print(f"Error: Failed to read URLs: {e}")
        sys.exit(1)
    
    if not urls:
        print("No URLs found in the spreadsheet.")
        sys.exit(0)
    
    print(f"Found {len(urls)} URLs to analyze.\n")
    
    results = []
    updates = []
    
    for idx, (row_index, url) in enumerate(urls, start=1):
        print(f"[{idx}/{len(urls)}] Analyzing {url}...")
        
        try:
            result = cypress_runner.run_analysis(url, timeout=args.timeout)
            
            mobile_score = result.get('mobile_score')
            desktop_score = result.get('desktop_score')
            mobile_psi_url = result.get('mobile_psi_url')
            desktop_psi_url = result.get('desktop_psi_url')
            
            mobile_status = "PASS" if mobile_score is not None and mobile_score >= SCORE_THRESHOLD else "FAIL"
            desktop_status = "PASS" if desktop_score is not None and desktop_score >= SCORE_THRESHOLD else "FAIL"
            
            print(f"  Mobile: {mobile_score if mobile_score is not None else 'N/A'} ({mobile_status})")
            print(f"  Desktop: {desktop_score if desktop_score is not None else 'N/A'} ({desktop_status})")
            
            results.append({
                'row': row_index,
                'url': url,
                'mobile_score': mobile_score,
                'desktop_score': desktop_score,
                'mobile_psi_url': mobile_psi_url,
                'desktop_psi_url': desktop_psi_url
            })
            
            if mobile_score is not None and mobile_score < SCORE_THRESHOLD and mobile_psi_url:
                updates.append((row_index, MOBILE_COLUMN, mobile_psi_url))
            
            if desktop_score is not None and desktop_score < SCORE_THRESHOLD and desktop_psi_url:
                updates.append((row_index, DESKTOP_COLUMN, desktop_psi_url))
            
        except cypress_runner.CypressTimeoutError as e:
            print(f"  ERROR: Timeout - {e}")
            results.append({
                'row': row_index,
                'url': url,
                'error': str(e)
            })
        except cypress_runner.CypressRunnerError as e:
            print(f"  ERROR: Cypress failed - {e}")
            results.append({
                'row': row_index,
                'url': url,
                'error': str(e)
            })
        except Exception as e:
            print(f"  ERROR: Unexpected error - {e}")
            results.append({
                'row': row_index,
                'url': url,
                'error': str(e)
            })
        
        print()
    
    if updates:
        print(f"Updating spreadsheet with {len(updates)} PSI URLs...")
        try:
            sheets_client.batch_write_psi_urls(
                args.spreadsheet_id,
                args.tab,
                updates,
                service=service
            )
            print("Spreadsheet updated successfully.\n")
        except Exception as e:
            print(f"Error: Failed to update spreadsheet: {e}\n")
    else:
        print("No failing scores to report.\n")
    
    print("=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)
    
    total_urls = len(results)
    successful = sum(1 for r in results if 'error' not in r)
    failed = total_urls - successful
    
    mobile_pass = sum(1 for r in results if r.get('mobile_score') is not None and r['mobile_score'] >= SCORE_THRESHOLD)
    mobile_fail = sum(1 for r in results if r.get('mobile_score') is not None and r['mobile_score'] < SCORE_THRESHOLD)
    desktop_pass = sum(1 for r in results if r.get('desktop_score') is not None and r['desktop_score'] >= SCORE_THRESHOLD)
    desktop_fail = sum(1 for r in results if r.get('desktop_score') is not None and r['desktop_score'] < SCORE_THRESHOLD)
    
    print(f"Total URLs analyzed: {total_urls}")
    print(f"Successful analyses: {successful}")
    print(f"Failed analyses: {failed}")
    print()
    print(f"Mobile scores >= {SCORE_THRESHOLD}: {mobile_pass}")
    print(f"Mobile scores < {SCORE_THRESHOLD}: {mobile_fail}")
    print(f"Desktop scores >= {SCORE_THRESHOLD}: {desktop_pass}")
    print(f"Desktop scores < {SCORE_THRESHOLD}: {desktop_fail}")
    print()
    
    if failed > 0:
        print("Failed URLs:")
        for r in results:
            if 'error' in r:
                print(f"  Row {r['row']}: {r['url']}")
                print(f"    Error: {r['error']}")
        print()
    
    if mobile_fail > 0 or desktop_fail > 0:
        print(f"PSI URLs for failing scores written to columns {MOBILE_COLUMN} (mobile) and {DESKTOP_COLUMN} (desktop).")
    
    print("=" * 80)


if __name__ == '__main__':
    main()
