#!/usr/bin/env python3
"""
Lean CLI for parallel PageSpeed Insights audits.
Reads URLs from Google Sheets, analyzes in parallel, writes results immediately.
"""

import argparse
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from sheets import sheets_client
from qa import playwright_runner

DEFAULT_SPREADSHEET_ID = '1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I'
SERVICE_ACCOUNT_FILE = 'service-account.json'
MOBILE_COLUMN = 'F'
DESKTOP_COLUMN = 'G'
SCORE_THRESHOLD = 80


def main():
    parser = argparse.ArgumentParser(description='PageSpeed Insights audit tool')
    parser.add_argument('--tab', required=True, help='Spreadsheet tab name')
    parser.add_argument('--service-account', default=SERVICE_ACCOUNT_FILE, help=f'Service account JSON file (default: {SERVICE_ACCOUNT_FILE})')
    parser.add_argument('--spreadsheet-id', default=DEFAULT_SPREADSHEET_ID, help=f'Spreadsheet ID (default: {DEFAULT_SPREADSHEET_ID})')
    parser.add_argument('--concurrency', type=int, default=15, help='Parallel workers (default: 15)')
    parser.add_argument('--timeout', type=int, default=120, help='Timeout per URL in seconds (default: 120)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.service_account):
        print(f"Error: Service account file not found: {args.service_account}")
        sys.exit(1)
    
    # Authenticate
    print("Authenticating...")
    try:
        service = sheets_client.authenticate(args.service_account)
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)
    
    # Read URLs
    print(f"Reading URLs from tab '{args.tab}'...")
    try:
        url_data = sheets_client.read_urls(args.spreadsheet_id, args.tab, service=service)
    except Exception as e:
        print(f"Failed to read URLs: {e}")
        sys.exit(1)
    
    if not url_data:
        print("No URLs found")
        return
    
    # Filter out URLs that should be skipped or already have both scores
    urls_to_process = []
    url_metadata = {}
    
    for row_index, url, existing_mobile, existing_desktop in url_data:
        # Skip if both columns have 'passed'
        mobile_passed = existing_mobile and 'passed' in existing_mobile.lower()
        desktop_passed = existing_desktop and 'passed' in existing_desktop.lower()
        if mobile_passed and desktop_passed:
            continue
        
        urls_to_process.append(url)
        url_metadata[url] = {
            'row': row_index,
            'existing_mobile': existing_mobile,
            'existing_desktop': existing_desktop
        }
    
    if not urls_to_process:
        print("No URLs to process (all skipped or completed)")
        return
    
    print(f"Processing {len(urls_to_process)} URLs with {args.concurrency} workers...")
    
    # Run parallel analysis
    try:
        results = asyncio.run(playwright_runner.run_batch(urls_to_process, concurrency=args.concurrency))
    except Exception as e:
        print(f"Analysis failed: {e}")
        sys.exit(1)
    
    # Process results and write to sheet
    successful = 0
    failed = 0
    mobile_pass = 0
    mobile_fail = 0
    desktop_pass = 0
    desktop_fail = 0
    
    for result in results:
        url = result['url']
        metadata = url_metadata[url]
        row_index = metadata['row']
        existing_mobile = metadata['existing_mobile']
        existing_desktop = metadata['existing_desktop']
        
        updates = []
        
        if result['error']:
            # Write error to empty columns
            error_msg = f"ERROR: {result['error']}"
            if not existing_mobile:
                updates.append((row_index, MOBILE_COLUMN, error_msg))
            if not existing_desktop:
                updates.append((row_index, DESKTOP_COLUMN, error_msg))
            failed += 1
            print(f"✗ {url}: {result['error']}")
        else:
            mobile_score = result['mobile_score']
            desktop_score = result['desktop_score']
            psi_url = result['psi_url']
            
            # Write mobile result
            if not existing_mobile and mobile_score is not None:
                if mobile_score >= SCORE_THRESHOLD:
                    updates.append((row_index, MOBILE_COLUMN, 'passed'))
                    mobile_pass += 1
                else:
                    updates.append((row_index, MOBILE_COLUMN, psi_url or f"Score: {mobile_score}"))
                    mobile_fail += 1
            
            # Write desktop result
            if not existing_desktop and desktop_score is not None:
                if desktop_score >= SCORE_THRESHOLD:
                    updates.append((row_index, DESKTOP_COLUMN, 'passed'))
                    desktop_pass += 1
                else:
                    updates.append((row_index, DESKTOP_COLUMN, psi_url or f"Score: {desktop_score}"))
                    desktop_fail += 1
            
            successful += 1
            print(f"✓ {url}: Mobile={mobile_score}, Desktop={desktop_score}")
        
        # Write immediately
        for row_idx, col, val in updates:
            try:
                sheets_client.write_result(args.spreadsheet_id, args.tab, row_idx, col, val, service)
            except Exception as e:
                print(f"  Warning: Failed to write {col}{row_idx} for {url}: {e}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total URLs: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Mobile pass (>={SCORE_THRESHOLD}): {mobile_pass}")
    print(f"Mobile fail (<{SCORE_THRESHOLD}): {mobile_fail}")
    print(f"Desktop pass (>={SCORE_THRESHOLD}): {desktop_pass}")
    print(f"Desktop fail (<{SCORE_THRESHOLD}): {desktop_fail}")
    print("=" * 80)


if __name__ == '__main__':
    main()
