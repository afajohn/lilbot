"""
Lean async Playwright module for PageSpeed Insights analysis.
Provides parallel URL processing with shared browser and multiple contexts.
"""

import asyncio
from typing import List, Dict, Optional

try:
    from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightTimeoutError = Exception


async def analyze_url(page: Page, url: str) -> dict:
    """
    Analyze a URL using PageSpeed Insights.
    
    Args:
        page: Playwright page object
        url: URL to analyze
        
    Returns:
        Dictionary with mobile_score, desktop_score, psi_url
        
    Raises:
        Exception: If analysis fails
    """
    # Navigate to PageSpeed Insights
    await page.goto('https://pagespeed.web.dev/', wait_until='domcontentloaded', timeout=30000)
    
    # Enter URL
    url_input = page.locator('input[type="url"], input[name="url"], input[placeholder*="URL"]').first
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
    
    # Wait 30s for initialization
    await asyncio.sleep(30)
    
    # Poll for score elements (up to 120s)
    start_time = asyncio.get_event_loop().time()
    timeout = 120
    poll_interval = 2
    
    while asyncio.get_event_loop().time() - start_time < timeout:
        try:
            score_elements = await page.locator('.lh-gauge__percentage').all()
            if len(score_elements) >= 1:
                # Check if mobile/desktop buttons are visible
                try:
                    mobile_button = page.locator('button:has-text("Mobile"), [role="tab"]:has-text("Mobile")').first
                    desktop_button = page.locator('button:has-text("Desktop"), [role="tab"]:has-text("Desktop")').first
                    
                    mobile_visible = await mobile_button.is_visible(timeout=1000)
                    desktop_visible = await desktop_button.is_visible(timeout=1000)
                    
                    if mobile_visible or desktop_visible:
                        break
                except Exception:
                    pass
        except Exception:
            pass
        
        await asyncio.sleep(poll_interval)
    else:
        raise Exception(f"Score elements not found within {timeout}s")
    
    # Extract mobile score
    mobile_score = None
    score_elements = await page.locator('.lh-gauge__percentage').all()
    if score_elements:
        try:
            score_text = await score_elements[0].inner_text()
            mobile_score = int(score_text.strip().replace('%', ''))
        except Exception:
            pass
    
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
    
    # Extract desktop score
    desktop_score = None
    score_elements = await page.locator('.lh-gauge__percentage').all()
    if score_elements:
        try:
            score_text = await score_elements[0].inner_text()
            desktop_score = int(score_text.strip().replace('%', ''))
        except Exception:
            pass
    
    if desktop_score is None:
        raise Exception("Failed to extract desktop score")
    
    return {
        'mobile_score': mobile_score,
        'desktop_score': desktop_score,
        'psi_url': psi_url
    }


async def run_batch(urls: List[str], concurrency: int = 15) -> List[dict]:
    """
    Process multiple URLs in parallel with shared browser and multiple contexts.
    
    Args:
        urls: List of URLs to analyze
        concurrency: Maximum number of concurrent analyses (default: 15)
        
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
                result = await analyze_url(page, url)
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
            # Process all URLs in parallel with concurrency control
            results = await asyncio.gather(
                *[analyze_with_semaphore(url, playwright, browser) for url in urls],
                return_exceptions=False
            )
            return results
        finally:
            await browser.close()
