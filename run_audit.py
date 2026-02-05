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
from utils.logger import setup_logger

DEFAULT_SPREADSHEET_ID = '1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I'
SERVICE_ACCOUNT_FILE = 'service-account.json'
MOBILE_COLUMN = 'F'
DESKTOP_COLUMN = 'G'
SCORE_THRESHOLD = 80


async def analyze_single_url(url: str, timeout: int = 180, logger=None):
    """
    Analyze a single URL with retry support.
    
    Args:
        url: URL to analyze
        timeout: Timeout per URL in seconds (default: 180)
        logger: Optional logger instance
        
    Returns:
        Result dictionary with scores or error
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise Exception("Playwright is not installed. Install it with: pip install playwright && playwright install chromium")
    
    if logger:
        logger.info(f"Analyzing URL: {url}")
    
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        
        try:
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            # Use analyze_url_with_retry for full retry support
            initial_wait = 30
            poll_timeout = timeout - initial_wait - 10  # Reserve time for retries
            if poll_timeout < 30:
                poll_timeout = 30
            
            result = await playwright_runner.analyze_url_with_retry(
                page, 
                context, 
                url, 
                max_retries=3,
                initial_wait=initial_wait,
                poll_timeout=poll_timeout
            )
            result['url'] = url
            result['error'] = None
            return result
            
        except Exception as e:
            if logger:
                logger.error(f"Failed to analyze {url}: {e}")
            return {
                'url': url,
                'mobile_score': None,
                'desktop_score': None,
                'psi_url': None,
                'error': str(e)
            }
        finally:
            await browser.close()


def main():
    parser = argparse.ArgumentParser(description='PageSpeed Insights audit tool')
    parser.add_argument('--tab', help='Spreadsheet tab name')
    parser.add_argument('--service-account', default=SERVICE_ACCOUNT_FILE, help=f'Service account JSON file (default: {SERVICE_ACCOUNT_FILE})')
    parser.add_argument('--spreadsheet-id', default=DEFAULT_SPREADSHEET_ID, help=f'Spreadsheet ID (default: {DEFAULT_SPREADSHEET_ID})')
    parser.add_argument('--concurrency', type=int, default=5, help='Parallel workers (default: 5)')
    parser.add_argument('--timeout', type=int, default=180, help='Timeout per URL in seconds (default: 180)')
    parser.add_argument('--initial-wait', type=int, default=30, help='Initial wait before polling for scores in seconds (default: 30)')
    parser.add_argument('--poll-timeout', type=int, default=120, help='Maximum time to poll for scores in seconds (default: 120)')
    parser.add_argument('--urls-per-context', type=int, default=10, help='Number of URLs to process per browser context before recycling (default: 10)')
    parser.add_argument('--sequential', action='store_true', help='Process URLs one at a time (sets concurrency=1)')
    parser.add_argument('--url', help='Test a single URL directly without spreadsheet')
    
    args = parser.parse_args()
    
    # Setup logger
    logger = setup_logger('audit', log_dir='logs')
    
    # Handle single URL mode
    if args.url:
        logger.info(f"Single URL mode: {args.url}")
        logger.info(f"Timeout: {args.timeout}s")
        
        try:
            result = asyncio.run(analyze_single_url(args.url, timeout=args.timeout, logger=logger))
            
            if result['error']:
                logger.error(f"✗ {args.url}: {result['error']}")
                sys.exit(1)
            else:
                mobile_score = result['mobile_score']
                desktop_score = result['desktop_score']
                psi_url = result['psi_url']
                
                logger.info("=" * 80)
                logger.info("RESULTS")
                logger.info("=" * 80)
                logger.info(f"URL: {args.url}")
                logger.info(f"Mobile Score: {mobile_score}")
                logger.info(f"Desktop Score: {desktop_score}")
                logger.info(f"PageSpeed Insights URL: {psi_url}")
                logger.info(f"Mobile: {'✓ PASSED' if mobile_score >= SCORE_THRESHOLD else '✗ FAILED'} (threshold: {SCORE_THRESHOLD})")
                logger.info(f"Desktop: {'✓ PASSED' if desktop_score >= SCORE_THRESHOLD else '✗ FAILED'} (threshold: {SCORE_THRESHOLD})")
                logger.info("=" * 80)
                
                sys.exit(0 if mobile_score >= SCORE_THRESHOLD and desktop_score >= SCORE_THRESHOLD else 1)
        except Exception as e:
            logger.error(f"Failed to analyze URL: {e}")
            sys.exit(1)
    
    # Spreadsheet mode requires --tab
    if not args.tab:
        logger.error("Error: --tab is required when not using --url")
        parser.print_help()
        sys.exit(1)
    
    # Apply sequential mode
    if args.sequential:
        args.concurrency = 1
        logger.info("Sequential mode enabled (concurrency=1)")
    
    if not os.path.exists(args.service_account):
        logger.error(f"Error: Service account file not found: {args.service_account}")
        sys.exit(1)
    
    # Authenticate
    logger.info("Authenticating...")
    try:
        service = sheets_client.authenticate(args.service_account)
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        sys.exit(1)
    
    # Read URLs
    logger.info(f"Reading URLs from tab '{args.tab}'...")
    try:
        url_data = sheets_client.read_urls(args.spreadsheet_id, args.tab, service=service)
    except Exception as e:
        logger.error(f"Failed to read URLs: {e}")
        sys.exit(1)
    
    if not url_data:
        logger.info("No URLs found")
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
        logger.info("No URLs to process (all skipped or completed)")
        return
    
    logger.info(f"Processing {len(urls_to_process)} URLs with {args.concurrency} workers...")
    
    # Run parallel analysis
    try:
        results = asyncio.run(playwright_runner.run_batch(
            urls_to_process, 
            concurrency=args.concurrency,
            initial_wait=args.initial_wait,
            poll_timeout=args.poll_timeout,
            urls_per_context=args.urls_per_context
        ))
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)
    
    # Process results and collect updates for batch writing
    successful = 0
    failed = 0
    mobile_pass = 0
    mobile_fail = 0
    desktop_pass = 0
    desktop_fail = 0
    
    all_updates = []
    
    for result in results:
        url = result['url']
        metadata = url_metadata[url]
        row_index = metadata['row']
        existing_mobile = metadata['existing_mobile']
        existing_desktop = metadata['existing_desktop']
        
        if result['error']:
            # Collect error updates for empty columns
            error_msg = f"ERROR: {result['error']}"
            if not existing_mobile:
                all_updates.append((row_index, MOBILE_COLUMN, error_msg))
            if not existing_desktop:
                all_updates.append((row_index, DESKTOP_COLUMN, error_msg))
            failed += 1
            logger.info(f"✗ {url}: {result['error']}")
        else:
            mobile_score = result['mobile_score']
            desktop_score = result['desktop_score']
            psi_url = result['psi_url']
            
            # Collect mobile result
            if not existing_mobile and mobile_score is not None:
                if mobile_score >= SCORE_THRESHOLD:
                    all_updates.append((row_index, MOBILE_COLUMN, 'passed'))
                    mobile_pass += 1
                else:
                    all_updates.append((row_index, MOBILE_COLUMN, psi_url or f"Score: {mobile_score}"))
                    mobile_fail += 1
            
            # Collect desktop result
            if not existing_desktop and desktop_score is not None:
                if desktop_score >= SCORE_THRESHOLD:
                    all_updates.append((row_index, DESKTOP_COLUMN, 'passed'))
                    desktop_pass += 1
                else:
                    all_updates.append((row_index, DESKTOP_COLUMN, psi_url or f"Score: {desktop_score}"))
                    desktop_fail += 1
            
            successful += 1
            logger.info(f"✓ {url}: Mobile={mobile_score}, Desktop={desktop_score}")
    
    # Write updates in batches of 50-60 cells
    batch_size = 50
    total_updates = len(all_updates)
    logger.info(f"Writing {total_updates} updates in batches of {batch_size}...")
    
    for i in range(0, total_updates, batch_size):
        batch = all_updates[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_updates + batch_size - 1) // batch_size
        
        try:
            logger.info(f"Writing batch {batch_num}/{total_batches} ({len(batch)} cells)...")
            sheets_client.batch_write_results(args.spreadsheet_id, args.tab, batch, service)
        except Exception as e:
            logger.warning(f"Failed to write batch {batch_num}: {e}")
            # Fallback to individual writes for this batch
            logger.info(f"Falling back to individual writes for batch {batch_num}...")
            for row_idx, col, val in batch:
                try:
                    sheets_client.write_result(args.spreadsheet_id, args.tab, row_idx, col, val, service)
                except Exception as e2:
                    logger.warning(f"Failed to write {col}{row_idx}: {e2}")
    
    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total URLs: {len(results)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Mobile pass (>={SCORE_THRESHOLD}): {mobile_pass}")
    logger.info(f"Mobile fail (<{SCORE_THRESHOLD}): {mobile_fail}")
    logger.info(f"Desktop pass (>={SCORE_THRESHOLD}): {desktop_pass}")
    logger.info(f"Desktop fail (<{SCORE_THRESHOLD}): {desktop_fail}")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
