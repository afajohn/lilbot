"""
Lean async Playwright module for PageSpeed Insights analysis.
Provides parallel URL processing with shared browser and multiple contexts.
"""

import asyncio
import logging
from typing import List, Dict, Optional

try:
    from playwright.async_api import async_playwright, Page, BrowserContext, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightTimeoutError = Exception

logger = logging.getLogger(__name__)


async def analyze_url(page: Page, url: str, initial_wait: int = 30, poll_timeout: int = 120) -> dict:
    """
    Analyze a URL using PageSpeed Insights.
    
    Args:
        page: Playwright page object
        url: URL to analyze
        initial_wait: Initial wait time in seconds before polling for scores (default: 30)
        poll_timeout: Maximum time to poll for scores in seconds (default: 120)
        
    Returns:
        Dictionary with mobile_score, desktop_score, psi_url
        
    Raises:
        Exception: If analysis fails
    """
    # Navigate to PageSpeed Insights with extended timeout
    await page.goto('https://pagespeed.web.dev/', wait_until='networkidle', timeout=60000)
    
    # Wait 2 seconds after page load before interacting
    await asyncio.sleep(2)
    
    # Expanded input selectors
    input_selectors = [
        'input[type="url"]',
        'input[name="url"]',
        'input[placeholder*="URL"]',
        '#i4',
        '[data-url-input]',
        'input[aria-label*="Enter"]'
    ]
    
    # Wait for URL input to be visible
    url_input = None
    for selector in input_selectors:
        try:
            await page.wait_for_selector(selector, state='visible', timeout=10000)
            url_input = page.locator(selector).first
            break
        except Exception:
            continue
    
    if not url_input:
        raise Exception("Failed to find URL input field")
    
    # Enter URL
    await url_input.fill(url)
    await asyncio.sleep(0.5)
    
    # Click Analyze button using robust selectors
    selectors = [
        'button:has-text("Analyze")',
        '[aria-label*="Analyze"]',
        'form button',
        'button[type="submit"]'
    ]
    
    clicked = False
    for selector in selectors:
        try:
            await page.locator(selector).first.click(timeout=5000)
            clicked = True
            break
        except Exception:
            continue
    
    if not clicked:
        raise Exception("Failed to click Analyze button")
    
    # Wait for initial analysis initialization
    logger.info(f"Waiting {initial_wait}s for initial analysis to complete...")
    await asyncio.sleep(initial_wait)
    
    # Poll for score elements with progress logging and error checking
    start_time = asyncio.get_event_loop().time()
    poll_interval = 2
    last_log_time = start_time
    
    # Score selectors to try (primary and alternatives)
    score_selectors = [
        '.lh-gauge__percentage',
        '[class*="gauge"][class*="percentage"]',
        '[data-testid*="score"]'
    ]
    
    # PSI error state selectors
    error_selectors = [
        '.lh-error',
        '[class*="error"]',
        '[data-testid*="error"]'
    ]
    
    while asyncio.get_event_loop().time() - start_time < poll_timeout:
        current_time = asyncio.get_event_loop().time()
        elapsed = current_time - start_time
        
        # Log progress every 30 seconds
        if current_time - last_log_time >= 30:
            logger.info(f"Polling progress: {elapsed:.0f}s elapsed, waiting for scores...")
            last_log_time = current_time
        
        # Check for PSI error states
        for error_selector in error_selectors:
            try:
                error_element = await page.locator(error_selector).first.is_visible(timeout=500)
                if error_element:
                    error_text = await page.locator(error_selector).first.inner_text(timeout=1000)
                    raise Exception(f"PageSpeed Insights error detected: {error_text}")
            except PlaywrightTimeoutError:
                # No error element found, continue
                pass
            except Exception as e:
                # If it's not a timeout, it might be an actual error
                if "PageSpeed Insights error detected" in str(e):
                    raise
        
        # Try to find score elements using alternative selectors
        score_elements = None
        for selector in score_selectors:
            try:
                elements = await page.locator(selector).all()
                if len(elements) >= 1:
                    score_elements = elements
                    logger.debug(f"Found score elements using selector: {selector}")
                    break
            except Exception:
                continue
        
        if score_elements:
            # Check if mobile/desktop buttons are visible
            try:
                mobile_button = page.locator('button:has-text("Mobile"), [role="tab"]:has-text("Mobile")').first
                desktop_button = page.locator('button:has-text("Desktop"), [role="tab"]:has-text("Desktop")').first
                
                mobile_visible = await mobile_button.is_visible(timeout=1000)
                desktop_visible = await desktop_button.is_visible(timeout=1000)
                
                if mobile_visible or desktop_visible:
                    logger.info(f"Score elements found after {elapsed:.0f}s")
                    break
            except Exception:
                pass
        
        await asyncio.sleep(poll_interval)
    else:
        raise Exception(f"Score elements not found within {poll_timeout}s")
    
    # Extract mobile score using alternative selectors
    mobile_score = None
    for selector in score_selectors:
        try:
            score_elements = await page.locator(selector).all()
            if score_elements:
                score_text = await score_elements[0].inner_text()
                mobile_score = int(score_text.strip().replace('%', ''))
                logger.debug(f"Extracted mobile score using selector: {selector}")
                break
        except Exception:
            continue
    
    if mobile_score is None:
        raise Exception("Failed to extract mobile score")
    
    # Get PSI URL
    psi_url = page.url if 'pagespeed.web.dev' in page.url else None
    
    # Click Desktop tab
    desktop_selectors = [
        'button:has-text("Desktop")',
        '[role="tab"]:has-text("Desktop")'
    ]
    
    desktop_clicked = False
    for selector in desktop_selectors:
        try:
            await page.locator(selector).first.click(timeout=5000)
            desktop_clicked = True
            break
        except Exception:
            continue
    
    if not desktop_clicked:
        raise Exception("Failed to click Desktop tab")
    
    await asyncio.sleep(1)
    
    # Extract desktop score using alternative selectors
    desktop_score = None
    for selector in score_selectors:
        try:
            score_elements = await page.locator(selector).all()
            if score_elements:
                score_text = await score_elements[0].inner_text()
                desktop_score = int(score_text.strip().replace('%', ''))
                logger.debug(f"Extracted desktop score using selector: {selector}")
                break
        except Exception:
            continue
    
    if desktop_score is None:
        raise Exception("Failed to extract desktop score")
    
    return {
        'mobile_score': mobile_score,
        'desktop_score': desktop_score,
        'psi_url': psi_url
    }


async def analyze_url_with_retry(page: Page, context: BrowserContext, url: str, max_retries: int = 3, initial_wait: int = 30, poll_timeout: int = 120) -> dict:
    """
    Analyze a URL with retry logic for selector timeouts and score extraction failures.
    
    Retries on PlaywrightTimeoutError and selector-related exceptions with exponential backoff.
    Reloads the page fresh via page.goto() before each retry.
    
    Args:
        page: Playwright page object
        context: Playwright browser context (not used, but kept for API compatibility)
        url: URL to analyze
        max_retries: Maximum number of retry attempts (default: 3)
        initial_wait: Initial wait time before polling for scores (default: 30)
        poll_timeout: Maximum time to poll for scores (default: 120)
        
    Returns:
        Dictionary with mobile_score, desktop_score, psi_url
        
    Raises:
        Exception: If all retry attempts fail or on permanent errors
    """
    backoff_delays = [5, 10, 20]
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} for URL: {url}")
            result = await analyze_url(page, url, initial_wait=initial_wait, poll_timeout=poll_timeout)
            logger.info(f"Successfully analyzed URL on attempt {attempt + 1}: {url}")
            return result
            
        except PlaywrightTimeoutError as e:
            error_msg = str(e).lower()
            
            if attempt < max_retries - 1:
                delay = backoff_delays[attempt] if attempt < len(backoff_delays) else 20
                logger.warning(f"Selector timeout on attempt {attempt + 1} for {url}: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
                
                try:
                    await page.goto('about:blank', wait_until='load', timeout=10000)
                except Exception:
                    pass
            else:
                logger.error(f"Failed after {max_retries} attempts for {url}: {e}")
                raise
                
        except Exception as e:
            error_msg = str(e).lower()
            
            is_selector_error = any(keyword in error_msg for keyword in [
                'selector', 'failed to find', 'not found', 'not visible',
                'failed to click', 'failed to extract', 'element'
            ])
            
            if is_selector_error and attempt < max_retries - 1:
                delay = backoff_delays[attempt] if attempt < len(backoff_delays) else 20
                logger.warning(f"Selector-related error on attempt {attempt + 1} for {url}: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
                
                try:
                    await page.goto('about:blank', wait_until='load', timeout=10000)
                except Exception:
                    pass
            else:
                logger.error(f"Non-retryable error or max retries reached for {url}: {e}")
                raise
    
    raise Exception(f"Failed to analyze {url} after {max_retries} attempts")


async def run_batch(urls: List[str], concurrency: int = 15, initial_wait: int = 30, poll_timeout: int = 120, urls_per_context: int = 10) -> List[dict]:
    """
    Process multiple URLs in parallel with shared browser and context recycling.
    
    Args:
        urls: List of URLs to analyze
        concurrency: Maximum number of concurrent analyses (default: 15)
        initial_wait: Initial wait time before polling for scores (default: 30)
        poll_timeout: Maximum time to poll for scores (default: 120)
        urls_per_context: Number of URLs to process per context before recycling (default: 10)
        
    Returns:
        List of result dictionaries (one per URL)
        
    Raises:
        Exception: If Playwright is not available
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise Exception(
            "Playwright is not installed. Install it with: pip install playwright && playwright install chromium"
        )
    
    semaphore = asyncio.Semaphore(concurrency)
    
    async def analyze_with_semaphore(url: str, playwright_instance, browser):
        async with semaphore:
            context = None
            try:
                # Create a new context for this URL
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = await context.new_page()
                result = await analyze_url(page, url, initial_wait=initial_wait, poll_timeout=poll_timeout)
                result['url'] = url
                result['error'] = None
                return result
            except Exception as e:
                return {
                    'url': url,
                    'mobile_score': None,
                    'desktop_score': None,
                    'psi_url': None,
                    'error': str(e)
                }
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass
    
    async def process_with_context_recycling(urls_batch: List[str], browser):
        """Process a batch of URLs with context recycling."""
        results = []
        context = None
        
        try:
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            for url in urls_batch:
                async with semaphore:
                    try:
                        result = await analyze_url(page, url, initial_wait=initial_wait, poll_timeout=poll_timeout)
                        result['url'] = url
                        result['error'] = None
                        results.append(result)
                    except Exception as e:
                        results.append({
                            'url': url,
                            'mobile_score': None,
                            'desktop_score': None,
                            'psi_url': None,
                            'error': str(e)
                        })
        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
        
        return results
    
    # Start Playwright and create shared browser
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
            # Split URLs into batches for context recycling
            url_batches = [urls[i:i + urls_per_context] for i in range(0, len(urls), urls_per_context)]
            
            # Process batches in parallel
            batch_results = await asyncio.gather(
                *[process_with_context_recycling(batch, browser) for batch in url_batches],
                return_exceptions=False
            )
            
            # Flatten results
            results = []
            for batch_result in batch_results:
                results.extend(batch_result)
            
            return results
        finally:
            await browser.close()
