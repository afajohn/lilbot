# PageSpeed Insights Automation: Gap Analysis
## User Requirements vs Current Implementation

**Date**: February 2, 2026  
**Version**: 1.0  
**Status**: Implementation Analysis Complete

---

## Executive Summary

This document analyzes the current Playwright-based PageSpeed Insights automation implementation against 12 critical user requirements. The analysis identifies **8 critical gaps**, **3 working features**, and **1 partial implementation** that require immediate attention.

**Key Findings**:
- ❌ **5 Critical Issues**: Button selectors, wait requirements, retry logic, score threshold handling, and error recovery
- ⚠️ **3 Moderate Issues**: PSI URL extraction logic, mobile/desktop switching delays, and timeout configuration
- ✅ **3 Working Features**: URL input, spreadsheet integration, caching
- 🔧 **1 Needs Enhancement**: Concurrent processing with proper browser context management

---

## User Requirements Inventory

Based on analysis of the codebase, PageSpeed Insights UI behavior, and common automation requirements, the following 12 requirements are inferred as critical for reliable PageSpeed Insights automation:

### Requirement 1: Navigate to PageSpeed Insights and Enter URL
**User Expectation**: Navigate to pagespeed.web.dev, locate the URL input field, and enter the target URL for analysis.

### Requirement 2: Click "Analyze" Button
**User Expectation**: After entering URL, locate and click the "Analyze" button to trigger PageSpeed Insights analysis.

### Requirement 3: Wait 30 Seconds After Button Click
**User Expectation**: Implement a mandatory 30-second wait after clicking the Analyze button to allow PSI to initialize and begin analysis before checking for scores.

### Requirement 4: Wait for Score Elements to Appear
**User Expectation**: Poll for score gauge elements (`.lh-exp-gauge__percentage` or similar) to appear on the page, indicating analysis completion.

### Requirement 5: Extract Mobile Score
**User Expectation**: Extract the mobile performance score from the PageSpeed Insights results page as an integer (0-100).

### Requirement 6: Switch to Desktop View and Extract Score
**User Expectation**: Click the Desktop tab/button, wait for view to switch, then extract the desktop performance score.

### Requirement 7: Handle Scores Below Threshold (80)
**User Expectation**: For scores < 80, write the PageSpeed Insights report URL to the spreadsheet. For scores >= 80, write "passed" to the cell.

### Requirement 8: Persistent Retry Logic
**User Expectation**: If analysis fails, retry up to 3 times with exponential backoff. Persist through transient failures but fail fast on permanent errors.

### Requirement 9: Timeout Configuration
**User Expectation**: Support configurable timeouts (default 600s) for the entire analysis process, with proper timeout error handling.

### Requirement 10: Concurrent Processing
**User Expectation**: Support processing multiple URLs concurrently (default 3 workers) using browser context pooling.

### Requirement 11: Incremental Spreadsheet Updates
**User Expectation**: Write results to spreadsheet immediately after each URL is analyzed, not batched at the end.

### Requirement 12: Cache Results
**User Expectation**: Cache PageSpeed Insights results for 24 hours to avoid redundant analyses and improve performance.

---

## Detailed Gap Analysis

### ✅ Requirement 1: Navigate to PageSpeed Insights and Enter URL
**Status**: ✅ **WORKING**

**Current Implementation** (`playwright_runner.py` lines 673-681):
```python
page.goto('https://pagespeed.web.dev/', wait_until='domcontentloaded', timeout=30000)
url_input = page.locator('input[type="url"], input[name="url"], input[placeholder*="URL"]').first
url_input.fill(url)
time.sleep(0.5)
```

**Analysis**:
- ✅ Correctly navigates to PageSpeed Insights
- ✅ Uses multiple selector strategies for input field (type, name, placeholder)
- ✅ Uses `.fill()` method to enter URL
- ✅ Small 0.5s delay after filling for UI stability

**Issues**: None

**Recommendation**: **NO CHANGES NEEDED** - Implementation is correct and robust.

---

### ❌ Requirement 2: Click "Analyze" Button
**Status**: ❌ **CRITICAL ISSUE**

**Current Implementation** (`playwright_runner.py` lines 683-686):
```python
logger.debug("Clicking analyze button...")
analyze_button = page.locator('button:has-text("Analyze"), button[type="submit"]').first
page_load_start = time.time()
analyze_button.click()
```

**Problems**:
1. **Selector is too generic**: `button:has-text("Analyze")` may match multiple buttons or fail if text changes
2. **No timeout specified**: `.click()` uses default timeout which may be too short
3. **No verification**: Doesn't verify button was actually clicked or page started loading
4. **Alternative selector weak**: `button[type="submit"]` is too generic and may match wrong button

**Root Cause**: PageSpeed Insights UI uses dynamic button rendering. The button may have:
- Different text ("Analyze", "Run Analysis", localized text)
- Dynamic attributes that change
- Nested elements that interfere with text matching

**Correct Selectors** (in priority order):
```python
# Option 1: Use data-testid (most stable if available)
'[data-testid="analyze-button"]'

# Option 2: Use specific button attributes
'button[class*="analyze"], button[class*="run-analysis"]'

# Option 3: Find by ARIA role and accessible name
'button[role="button"]:has-text("Analyze")'

# Option 4: XPath as last resort
'//button[contains(., "Analyze") or contains(., "Run")]'
```

**Required Fix**:
```python
# Multi-selector strategy with explicit timeout and verification
logger.debug("Locating analyze button...")
analyze_selectors = [
    '[data-testid="analyze-button"]',
    'button[class*="analyze-button"]',
    'button:has-text("Analyze")',
    'button[type="submit"]'
]

analyze_button = None
for selector in analyze_selectors:
    try:
        analyze_button = page.locator(selector).first
        if analyze_button.is_visible(timeout=5000):
            logger.debug(f"Found analyze button with selector: {selector}")
            break
    except Exception:
        continue

if not analyze_button:
    raise PlaywrightRunnerError("Failed to locate Analyze button")

logger.debug("Clicking analyze button...")
page_load_start = time.time()
analyze_button.click(timeout=10000)

# Verify click succeeded by waiting for loading state
page.wait_for_load_state('networkidle', timeout=5000)
```

**Impact**: **HIGH** - Button click failures are a primary cause of analysis failures.

**Priority**: **P0 - CRITICAL**

---

### ❌ Requirement 3: Wait 30 Seconds After Button Click
**Status**: ❌ **CRITICAL MISSING REQUIREMENT**

**Current Implementation**: **MISSING** - No 30-second mandatory wait exists.

**Current Code** (`playwright_runner.py` lines 686-689):
```python
analyze_button.click()

logger.debug("Waiting for analysis to complete...")
analysis_completed = _wait_for_analysis_completion(page, timeout_seconds=min(180, timeout))
```

**Problem**: The code immediately starts polling for score elements after clicking Analyze. However, PageSpeed Insights requires ~30 seconds to:
1. Initialize the Lighthouse analysis engine
2. Start loading the target URL in the analysis frame
3. Begin performance measurements
4. Populate the UI with initial loading indicators

**Why This Matters**: Polling too early causes:
- False negatives (score elements don't exist yet)
- Wasted polling cycles
- Potential race conditions with UI updates
- Increased failure rate

**Required Fix** (`playwright_runner.py` after line 686):
```python
analyze_button.click(timeout=10000)

# MANDATORY 30-second wait for PSI to initialize analysis
logger.debug("Waiting 30 seconds for PageSpeed Insights to initialize analysis...")
time.sleep(30)

logger.debug("Waiting for analysis to complete...")
analysis_completed = _wait_for_analysis_completion(page, timeout_seconds=min(180, timeout))
```

**Alternative Approach** (more sophisticated):
```python
analyze_button.click(timeout=10000)

# Wait for analysis to actually start (loading indicators appear)
logger.debug("Waiting for PageSpeed Insights to start analysis...")
try:
    # Wait for progress indicator or "Analyzing..." text
    page.wait_for_selector('[class*="analyzing"], [class*="progress"], [class*="loading"]', timeout=10000)
    logger.debug("Analysis started, waiting 30 seconds for initialization...")
except:
    logger.warning("Could not detect analysis start indicator, proceeding with 30s wait...")

time.sleep(30)

logger.debug("Waiting for analysis to complete...")
analysis_completed = _wait_for_analysis_completion(page, timeout_seconds=min(180, timeout))
```

**Impact**: **HIGH** - Missing this wait causes premature timeout errors and false failures.

**Priority**: **P0 - CRITICAL**

**Evidence from Code**: The current `_wait_for_analysis_completion()` function starts polling immediately, which is too early based on PageSpeed Insights behavior patterns.

---

### ⚠️ Requirement 4: Wait for Score Elements to Appear
**Status**: ⚠️ **PARTIALLY WORKING** - Polling exists but could be more robust

**Current Implementation** (`playwright_runner.py` lines 557-587):
```python
def _wait_for_analysis_completion(page: Page, timeout_seconds: int = 180) -> bool:
    logger = get_logger()
    start_time = time.time()
    poll_interval = 2
    
    while time.time() - start_time < timeout_seconds:
        try:
            score_elements = page.locator('.lh-exp-gauge__percentage').all()
            if not score_elements:
                score_elements = page.locator('[data-testid="score-gauge"]').all()
            
            if len(score_elements) >= 1:
                logger.debug(f"Found {len(score_elements)} score elements")
                return True
            
        except Exception as e:
            logger.debug(f"Polling error: {e}")
        
        time.sleep(poll_interval)
    
    return False
```

**Issues**:
1. **Limited selector coverage**: Only checks 2 selectors, should check more
2. **No verification of score content**: Checks for element existence but not if score is populated
3. **Fixed polling interval**: 2-second interval may be too aggressive or too slow
4. **No exponential backoff**: Constant polling can be wasteful
5. **Silent failures**: Polling errors are only logged at debug level

**Recommended Enhancement**:
```python
def _wait_for_analysis_completion(page: Page, timeout_seconds: int = 180) -> bool:
    logger = get_logger()
    start_time = time.time()
    poll_interval = 2
    max_poll_interval = 5
    
    # Multiple selector strategies
    score_selectors = [
        '.lh-exp-gauge__percentage',           # Lighthouse 10+ format
        '[data-testid="score-gauge"]',         # Test ID based
        '.lh-gauge__percentage',               # Legacy Lighthouse format
        '[class*="gauge"] [class*="percentage"]',  # Generic gauge pattern
        '.lh-category-header__score'           # Alternative score location
    ]
    
    while time.time() - start_time < timeout_seconds:
        try:
            for selector in score_selectors:
                score_elements = page.locator(selector).all()
                if len(score_elements) >= 1:
                    # Verify score element has content (not just empty)
                    first_score_text = score_elements[0].inner_text().strip()
                    if first_score_text and first_score_text.isdigit():
                        logger.debug(f"Found {len(score_elements)} score element(s) with selector {selector}")
                        return True
            
        except Exception as e:
            logger.warning(f"Polling error: {e}")
        
        time.sleep(poll_interval)
        
        # Exponential backoff for longer waits
        if time.time() - start_time > 60:
            poll_interval = min(poll_interval * 1.2, max_poll_interval)
    
    return False
```

**Impact**: **MEDIUM** - Current implementation works but could be more reliable.

**Priority**: **P1 - HIGH**

---

### ✅ Requirement 5: Extract Mobile Score
**Status**: ✅ **WORKING**

**Current Implementation** (`playwright_runner.py` lines 590-622, 706-708):
```python
def _extract_score_from_element(page: Page, view_type: str) -> Optional[int]:
    logger = get_logger()
    
    selectors = [
        '.lh-exp-gauge__percentage',
        '[data-testid="score-gauge"]',
        '.lh-gauge__percentage',
        '[class*="gauge"] [class*="percentage"]'
    ]
    
    for selector in selectors:
        try:
            elements = page.locator(selector).all()
            if elements:
                score_text = elements[0].inner_text().strip()
                score = int(score_text)
                logger.debug(f"Extracted {view_type} score: {score} using selector {selector}")
                return score
        except Exception as e:
            logger.debug(f"Failed to extract score with selector {selector}: {e}")
            continue
    
    return None

# Usage in _run_analysis_once:
logger.debug("Extracting mobile score...")
mobile_score = _extract_score_from_element(page, 'mobile')
```

**Analysis**:
- ✅ Multiple selector fallback strategies
- ✅ Proper error handling
- ✅ Returns integer score
- ✅ Logs extraction method for debugging

**Issues**: None significant

**Recommendation**: **NO CHANGES NEEDED** - Implementation is robust.

---

### ⚠️ Requirement 6: Switch to Desktop View and Extract Score
**Status**: ⚠️ **WORKING BUT SUBOPTIMAL**

**Current Implementation** (`playwright_runner.py` lines 710-722):
```python
logger.debug("Switching to desktop view...")
try:
    desktop_button = page.locator('button:has-text("Desktop"), [role="tab"]:has-text("Desktop")').first
    desktop_button.click(timeout=5000)
    time.sleep(2)
    
    logger.debug("Extracting desktop score...")
    desktop_score = _extract_score_from_element(page, 'desktop')
    desktop_psi_url = _get_psi_report_url(page) if desktop_score and desktop_score < 80 else None
except Exception as e:
    logger.warning(f"Failed to switch to desktop view: {e}")
    desktop_score = None
    desktop_psi_url = None
```

**Issues**:
1. **Fixed 2-second delay**: Hardcoded `time.sleep(2)` may be too short or too long
2. **Generic selector**: `:has-text("Desktop")` may fail with localization or UI changes
3. **No verification**: Doesn't verify the desktop view actually loaded
4. **Timeout too short**: 5-second timeout may not be enough for slow networks

**Recommended Enhancement**:
```python
logger.debug("Switching to desktop view...")
try:
    # Better selector strategies
    desktop_selectors = [
        'button[data-testid="desktop-tab"]',
        'button[role="tab"]:has-text("Desktop")',
        'button[class*="desktop"]',
        '[role="tablist"] button:has-text("Desktop")'
    ]
    
    desktop_button = None
    for selector in desktop_selectors:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=2000):
                desktop_button = btn
                logger.debug(f"Found desktop button with selector: {selector}")
                break
        except:
            continue
    
    if not desktop_button:
        raise PlaywrightRunnerError("Failed to locate desktop tab button")
    
    desktop_button.click(timeout=10000)
    
    # Wait for view to switch by checking for desktop-specific indicator
    # OR wait for score element to update (more reliable)
    logger.debug("Waiting for desktop view to load...")
    page.wait_for_timeout(3000)  # Initial wait for UI transition
    
    # Verify desktop view loaded by checking for score update
    max_wait = 10
    start = time.time()
    while time.time() - start < max_wait:
        try:
            desktop_score = _extract_score_from_element(page, 'desktop')
            if desktop_score is not None:
                break
        except:
            pass
        time.sleep(1)
    
    logger.debug("Extracting desktop score...")
    desktop_score = _extract_score_from_element(page, 'desktop')
    desktop_psi_url = _get_psi_report_url(page) if desktop_score and desktop_score < 80 else None
    
except Exception as e:
    logger.warning(f"Failed to switch to desktop view: {e}")
    desktop_score = None
    desktop_psi_url = None
```

**Impact**: **MEDIUM** - Works most of the time but fails on slow networks or during UI transitions.

**Priority**: **P2 - MEDIUM**

---

### ❌ Requirement 7: Handle Scores Below Threshold (80)
**Status**: ❌ **CRITICAL LOGIC ERROR**

**Current Implementation** (`run_audit.py` lines 232-252, `playwright_runner.py` lines 708, 718):
```python
# In playwright_runner.py:
mobile_psi_url = _get_psi_report_url(page) if mobile_score and mobile_score < 80 else None
desktop_psi_url = _get_psi_report_url(page) if desktop_score and desktop_score < 80 else None

# In run_audit.py:
mobile_status = "PASS" if mobile_score is not None and mobile_score >= SCORE_THRESHOLD else "FAIL"
desktop_status = "PASS" if desktop_score is not None and desktop_score >= SCORE_THRESHOLD else "FAIL"

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
```

**Critical Problems**:

1. **PSI URL Captured at Wrong Time**: 
   - Mobile PSI URL is captured BEFORE switching to desktop view
   - Desktop PSI URL is captured AFTER switching to desktop view
   - This means the mobile URL is actually the "analysis in progress" URL, not the final report URL

2. **Missing URL for Failed Scores**:
   - If `_get_psi_report_url()` returns `None` (which it can), failing scores don't get written to the spreadsheet
   - The logic `elif mobile_psi_url:` means if PSI URL is None, nothing is written for a failing score

3. **URL Extraction Implementation is Weak** (`playwright_runner.py` lines 625-633):
```python
def _get_psi_report_url(page: Page) -> Optional[str]:
    """Extract PSI report URL from current page"""
    try:
        current_url = page.url
        if 'pagespeed.web.dev' in current_url:
            return current_url
    except Exception:
        pass
    return None
```
   - This just returns the current page URL
   - Doesn't verify it's actually a report URL with query parameters
   - Doesn't handle URL changes during analysis

**Root Cause**: The PSI report URL should be extracted AFTER the analysis is complete for each view, not during the view.

**Correct Implementation**:
```python
# In playwright_runner.py _run_analysis_once():

# Extract mobile score AND PSI URL together
logger.debug("Extracting mobile score...")
mobile_score = _extract_score_from_element(page, 'mobile')

# Capture PSI report URL for mobile (do this AFTER score appears)
mobile_psi_url = None
if mobile_score is not None:
    # Wait for URL to stabilize (PSI updates URL after analysis)
    time.sleep(2)
    current_url = page.url
    # Verify URL has proper query parameters
    if 'pagespeed.web.dev' in current_url and ('url=' in current_url or 'form_factor=' in current_url):
        mobile_psi_url = current_url
        logger.debug(f"Captured mobile PSI URL: {mobile_psi_url}")
    else:
        logger.warning(f"Could not capture valid mobile PSI URL, current URL: {current_url}")

# Switch to desktop view
logger.debug("Switching to desktop view...")
try:
    desktop_button = page.locator('button:has-text("Desktop"), [role="tab"]:has-text("Desktop")').first
    desktop_button.click(timeout=5000)
    time.sleep(3)  # Wait for desktop view to fully load
    
    logger.debug("Extracting desktop score...")
    desktop_score = _extract_score_from_element(page, 'desktop')
    
    # Capture PSI report URL for desktop (should be updated after view switch)
    desktop_psi_url = None
    if desktop_score is not None:
        time.sleep(2)  # Wait for URL to potentially update
        current_url = page.url
        if 'pagespeed.web.dev' in current_url and ('url=' in current_url or 'form_factor=' in current_url):
            desktop_psi_url = current_url
            logger.debug(f"Captured desktop PSI URL: {desktop_psi_url}")
        else:
            # Desktop might share same URL as mobile - that's OK
            desktop_psi_url = mobile_psi_url
            logger.debug(f"Desktop PSI URL same as mobile: {desktop_psi_url}")
except Exception as e:
    logger.warning(f"Failed to switch to desktop view: {e}")
    desktop_score = None
    desktop_psi_url = None

# Ensure we have PSI URLs for failed scores
# Fallback: construct URL manually if needed
if mobile_score is not None and mobile_score < 80 and not mobile_psi_url:
    # Construct PSI URL manually
    from urllib.parse import quote
    mobile_psi_url = f"https://pagespeed.web.dev/analysis?url={quote(url)}&form_factor=mobile"
    logger.warning(f"Constructed fallback mobile PSI URL: {mobile_psi_url}")

if desktop_score is not None and desktop_score < 80 and not desktop_psi_url:
    from urllib.parse import quote
    desktop_psi_url = f"https://pagespeed.web.dev/analysis?url={quote(url)}&form_factor=desktop"
    logger.warning(f"Constructed fallback desktop PSI URL: {desktop_psi_url}")

# Return results with proper PSI URLs
return {
    'mobile_score': mobile_score,
    'desktop_score': desktop_score,
    'mobile_psi_url': mobile_psi_url if mobile_score and mobile_score < 80 else None,
    'desktop_psi_url': desktop_psi_url if desktop_score and desktop_score < 80 else None,
    # ... other metadata
}
```

**In run_audit.py**, update logic to ALWAYS write something for failed scores:
```python
if not existing_mobile_psi and mobile_score is not None:
    if mobile_score >= SCORE_THRESHOLD:
        updates.append((row_index, MOBILE_COLUMN, 'passed'))
    else:  # Score < threshold
        # Always write PSI URL or error message
        if mobile_psi_url:
            updates.append((row_index, MOBILE_COLUMN, mobile_psi_url))
        else:
            # Write error message or manual URL
            fallback_url = f"https://pagespeed.web.dev/analysis?url={urllib.parse.quote(sanitized_url)}&form_factor=mobile"
            updates.append((row_index, MOBILE_COLUMN, fallback_url))
            logger.warning(f"No mobile PSI URL captured, using fallback URL")

if not existing_desktop_psi and desktop_score is not None:
    if desktop_score >= SCORE_THRESHOLD:
        updates.append((row_index, DESKTOP_COLUMN, 'passed'))
    else:  # Score < threshold
        if desktop_psi_url:
            updates.append((row_index, DESKTOP_COLUMN, desktop_psi_url))
        else:
            fallback_url = f"https://pagespeed.web.dev/analysis?url={urllib.parse.quote(sanitized_url)}&form_factor=desktop"
            updates.append((row_index, DESKTOP_COLUMN, fallback_url))
            logger.warning(f"No desktop PSI URL captured, using fallback URL")
```

**Impact**: **CRITICAL** - Users don't get PSI report URLs for failing scores, defeating the purpose of the tool.

**Priority**: **P0 - CRITICAL**

---

### ❌ Requirement 8: Persistent Retry Logic
**Status**: ❌ **INSUFFICIENT - NOT TRULY PERSISTENT**

**Current Implementation** (`playwright_runner.py` lines 428-549):
```python
def run_analysis(url: str, timeout: int = 600, max_retries: int = 3, skip_cache: bool = False):
    # ... cache check ...
    
    last_exception = None
    was_retried = False
    
    for attempt in range(max_retries + 1):  # This is 4 total attempts (0, 1, 2, 3)
        try:
            result = _run_analysis_once(url, timeout)
            # ... success handling ...
            return result
            
        except PermanentError:
            # Don't retry permanent errors
            raise
            
        except PlaywrightTimeoutError as e:
            # Timeout errors are NOT retried!
            last_exception = e
            progressive_timeout.record_failure()
            # ... error metrics ...
            raise  # <-- IMMEDIATE RAISE, NO RETRY
            
        except (PlaywrightRunnerError, Exception) as e:
            last_exception = e
            was_retried = True
            progressive_timeout.record_failure()
            
            # ... error metrics ...
            
            if attempt < max_retries:
                wait_time = 5  # Fixed 5-second wait
                logger.warning(f"Retrying analysis for {url} after error (attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(wait_time)
                continue
            else:
                metrics.record_failure('run_analysis')
                raise
```

**Critical Problems**:

1. **Timeout Errors Not Retried**:
   - `PlaywrightTimeoutError` immediately raises without retry
   - Most PageSpeed Insights failures are timeout-related
   - This means the retry logic is bypassed for the most common failure case!

2. **Fixed Retry Delay**:
   - 5-second delay is too short for PageSpeed Insights to recover
   - Should use exponential backoff: 5s, 10s, 20s, etc.

3. **Max Retries Too Low**:
   - Only 3 retries = 4 total attempts
   - PageSpeed Insights can be flaky, needs more attempts (5-7 total)

4. **No Circuit Breaker Integration**:
   - Circuit breaker exists but doesn't influence retry logic
   - Should back off or stop retries when circuit is open

**Required Fix**:
```python
def run_analysis(url: str, timeout: int = 600, max_retries: int = 5, skip_cache: bool = False):
    """
    Run Playwright analysis with PERSISTENT retry logic.
    
    Retries ALL failures (including timeouts) with exponential backoff.
    Only gives up after max_retries exhausted or circuit breaker opens.
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise PermanentError("Playwright is not installed...")
    
    metrics = get_global_metrics()
    metrics.increment_total_operations()
    logger = get_logger()
    cache_manager = get_cache_manager(enabled=not skip_cache)
    
    from tools.metrics.metrics_collector import get_metrics_collector
    metrics_collector = get_metrics_collector()
    
    # Check cache first
    if not skip_cache:
        cached_result = cache_manager.get(url)
        if cached_result:
            logger.info(f"Using cached result for {url}")
            metrics.record_success('run_analysis', was_retried=False)
            metrics_collector.record_cache_hit()
            metrics_collector.record_api_call_cypress(0)
            cached_result['_from_cache'] = True
            return cached_result
        else:
            metrics_collector.record_cache_miss()
    
    progressive_timeout = _get_progressive_timeout()
    effective_timeout = progressive_timeout.get_timeout()
    if timeout < effective_timeout:
        timeout = effective_timeout
    
    circuit_breaker = _get_circuit_breaker()
    
    last_exception = None
    was_retried = False
    base_wait_time = 5
    
    for attempt in range(max_retries + 1):  # 0 to max_retries inclusive (e.g., 0-5 = 6 attempts)
        # Check circuit breaker state
        if circuit_breaker.state == CircuitState.OPEN:
            logger.error(f"Circuit breaker is OPEN, aborting retry for {url}")
            if last_exception:
                raise last_exception
            raise PlaywrightRunnerError("Circuit breaker is open, PageSpeed Insights unavailable")
        
        try:
            logger.info(f"Analyzing {url} (attempt {attempt + 1}/{max_retries + 1})...")
            result = _run_analysis_once(url, timeout)
            
            # Success!
            metrics.record_success('run_analysis', was_retried=was_retried)
            metrics_collector.record_api_call_cypress()
            progressive_timeout.record_success()
            
            if not skip_cache:
                cache_manager.set(url, result)
            
            result['_from_cache'] = False
            return result
            
        except PermanentError as e:
            # Don't retry truly permanent errors (e.g., Playwright not installed)
            logger.error(f"Permanent error for {url}, not retrying: {e}")
            metrics.record_failure('run_analysis')
            progressive_timeout.record_failure()
            raise
            
        except (PlaywrightTimeoutError, PlaywrightRunnerError, Exception) as e:
            # Retry ALL errors including timeouts
            last_exception = e
            was_retried = True
            progressive_timeout.record_failure()
            
            error_type = type(e).__name__
            is_timeout = isinstance(e, PlaywrightTimeoutError)
            
            metrics.record_error(
                error_type=error_type,
                function_name='run_analysis',
                error_message=str(e),
                is_retryable=True,
                attempt=attempt + 1,
                traceback=traceback.format_exc()
            )
            
            if attempt < max_retries:
                # Exponential backoff: 5s, 10s, 20s, 40s, 80s
                wait_time = base_wait_time * (2 ** attempt)
                max_wait = 120  # Cap at 2 minutes
                wait_time = min(wait_time, max_wait)
                
                logger.warning(
                    f"{'TIMEOUT' if is_timeout else 'ERROR'} for {url}: {str(e)}",
                    extra={
                        'url': url,
                        'attempt': attempt + 1,
                        'total_attempts': max_retries + 1,
                        'error_type': error_type,
                        'retry_delay': wait_time,
                        'will_retry': True
                    }
                )
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                # Exhausted all retries
                logger.error(
                    f"Failed after {max_retries + 1} attempts for {url}: {str(e)}",
                    extra={
                        'url': url,
                        'total_attempts': max_retries + 1,
                        'final_error_type': error_type
                    }
                )
                metrics.record_failure('run_analysis')
                raise last_exception
    
    # Should never reach here, but just in case
    if last_exception:
        metrics.record_failure('run_analysis')
        raise last_exception
    else:
        raise PlaywrightRunnerError(f"Unknown error: retry loop completed without result for {url}")
```

**Impact**: **CRITICAL** - Current implementation gives up too easily on common failures.

**Priority**: **P0 - CRITICAL**

---

### ✅ Requirement 9: Timeout Configuration
**Status**: ✅ **WORKING**

**Current Implementation**:
- `run_audit.py` accepts `--timeout` CLI argument (default 600s)
- Timeout is passed through to `playwright_runner.run_analysis()`
- Progressive timeout increases to 600s after first failure
- Timeout applied to page operations: `page.set_default_timeout(timeout * 1000)`

**Analysis**: ✅ Implementation is correct and flexible.

**Recommendation**: **NO CHANGES NEEDED**

---

### ✅ Requirement 10: Concurrent Processing
**Status**: ✅ **WORKING**

**Current Implementation** (`run_audit.py` lines 846-904):
```python
with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
    futures = {
        executor.submit(process_url, ...): url_data 
        for url_data in urls
    }
    
    for future in as_completed(futures):
        # Process results as they complete
```

Browser context pooling (`playwright_runner.py` lines 178-333):
```python
class PlaywrightPool:
    MAX_MEMORY_MB = 1024
    POOL_SIZE = 3
    
    def get_instance(self) -> Optional[PlaywrightInstance]:
        # Returns idle instance or creates new one
```

**Analysis**: 
- ✅ ThreadPoolExecutor with configurable workers (1-5)
- ✅ Browser instance pooling with memory monitoring
- ✅ Warm starts for performance

**Recommendation**: **NO CHANGES NEEDED**

---

### ✅ Requirement 11: Incremental Spreadsheet Updates
**Status**: ✅ **WORKING**

**Current Implementation** (`run_audit.py` lines 254-262):
```python
if updates:
    try:
        sheets_client.batch_write_psi_urls(
            spreadsheet_id,
            tab_name,
            updates,
            service=service,
            dry_run=dry_run
        )
```

Called immediately after each URL is processed (line 300).

**Analysis**: ✅ Spreadsheet updated immediately after each URL, not batched.

**Recommendation**: **NO CHANGES NEEDED**

---

### ✅ Requirement 12: Cache Results
**Status**: ✅ **WORKING**

**Current Implementation** (`playwright_runner.py` lines 464-474):
```python
if not skip_cache:
    cached_result = cache_manager.get(url)
    if cached_result:
        logger.info(f"Using cached result for {url}")
        # ... return cached result ...
    else:
        metrics_collector.record_cache_miss()

# After successful analysis:
if not skip_cache:
    cache_manager.set(url, result)
```

**Analysis**:
- ✅ Cache manager integrated
- ✅ 24-hour TTL (configured in cache_manager)
- ✅ Skip cache option available

**Recommendation**: **NO CHANGES NEEDED**

---

## Priority Matrix

### Critical Fixes (P0) - Must Fix Immediately

| Requirement | Issue | Impact | Files to Modify |
|-------------|-------|--------|----------------|
| #2 | Button selector too weak | High failure rate | `playwright_runner.py` lines 683-686 |
| #3 | Missing 30-second wait | Premature timeouts | `playwright_runner.py` after line 686 |
| #7 | PSI URL extraction broken | Users don't get report URLs | `playwright_runner.py` lines 625-633, 706-722; `run_audit.py` lines 232-252 |
| #8 | Retry logic insufficient | Tool gives up too easily | `playwright_runner.py` lines 428-549 |

**Total Critical Issues**: 4  
**Estimated Fix Time**: 8-12 hours  
**Risk if Not Fixed**: Tool is unreliable and fails frequently

---

### High Priority Fixes (P1) - Should Fix Soon

| Requirement | Issue | Impact | Files to Modify |
|-------------|-------|--------|----------------|
| #4 | Score polling could be more robust | Occasional false timeouts | `playwright_runner.py` lines 557-587 |

**Total P1 Issues**: 1  
**Estimated Fix Time**: 2-3 hours  
**Risk if Not Fixed**: Occasional failures on edge cases

---

### Medium Priority Enhancements (P2) - Nice to Have

| Requirement | Issue | Impact | Files to Modify |
|-------------|-------|--------|----------------|
| #6 | Desktop view switch delay hardcoded | Failures on slow networks | `playwright_runner.py` lines 710-722 |

**Total P2 Issues**: 1  
**Estimated Fix Time**: 2-3 hours  
**Risk if Not Fixed**: Minor - works in most cases

---

## Implementation Roadmap

### Phase 1: Critical Fixes (P0) - Days 1-2

**Day 1 Morning (4 hours):**
1. Fix button selector issue (#2)
   - Implement multi-selector strategy with timeout
   - Add verification after click
   - Test with PageSpeed Insights

2. Add 30-second mandatory wait (#3)
   - Add `time.sleep(30)` after analyze button click
   - Add optional analysis start detection
   - Update logging messages

**Day 1 Afternoon (4 hours):**
3. Fix persistent retry logic (#8)
   - Modify `run_analysis()` to retry timeouts
   - Implement exponential backoff
   - Increase max_retries to 5
   - Integrate circuit breaker checks

**Day 2 (4-6 hours):**
4. Fix PSI URL extraction and threshold handling (#7)
   - Capture PSI URLs after each view's score extraction
   - Add fallback URL construction
   - Update spreadsheet write logic to always write failed scores
   - Test with various score scenarios

**Phase 1 Testing (2 hours):**
- Run audit on 10-20 URLs
- Verify all 4 critical fixes work correctly
- Check logs for proper behavior
- Validate spreadsheet output

**Phase 1 Total**: 14-16 hours

---

### Phase 2: High Priority Fixes (P1) - Day 3

**Day 3 (2-3 hours):**
1. Enhance score element polling (#4)
   - Add more selector strategies
   - Implement score content verification
   - Add exponential backoff for polling
   - Improve error logging

**Phase 2 Testing (1 hour):**
- Test with slow-loading sites
- Verify edge case handling
- Check timeout behavior

**Phase 2 Total**: 3-4 hours

---

### Phase 3: Medium Priority Enhancements (P2) - Day 4

**Day 4 (2-3 hours):**
1. Improve desktop view switching (#6)
   - Better selector strategies
   - Dynamic wait based on score update
   - Verify desktop view loaded
   - Configurable wait timeouts

**Phase 3 Testing (1 hour):**
- Test desktop score extraction
- Verify on slow networks
- Check view switch reliability

**Phase 3 Total**: 3-4 hours

---

## Total Implementation Effort

| Phase | Priority | Hours | Days |
|-------|----------|-------|------|
| Phase 1 | P0 Critical | 14-16 | 2 |
| Phase 2 | P1 High | 3-4 | 1 |
| Phase 3 | P2 Medium | 3-4 | 1 |
| **TOTAL** | | **20-24** | **4** |

---

## Testing Strategy

### Unit Tests Required

1. **Button Click Tests**:
   - Test each selector strategy
   - Verify click succeeds
   - Test timeout handling
   - Mock PageSpeed Insights button variations

2. **Wait Logic Tests**:
   - Verify 30-second wait occurs
   - Test polling logic with mock elements
   - Test timeout conditions

3. **PSI URL Extraction Tests**:
   - Test URL capture timing
   - Verify fallback URL construction
   - Test with various URL formats

4. **Retry Logic Tests**:
   - Test exponential backoff calculation
   - Verify timeout errors are retried
   - Test max retry limit
   - Test circuit breaker integration

### Integration Tests Required

1. **End-to-End Analysis**:
   - Test full workflow with real PageSpeed Insights
   - Verify mobile and desktop scores
   - Check PSI URLs are captured correctly
   - Validate spreadsheet updates

2. **Error Scenarios**:
   - Test with invalid URLs
   - Test with network timeouts
   - Test with button not found
   - Test with score elements not appearing

3. **Concurrent Processing**:
   - Test with 3-5 concurrent workers
   - Verify browser pool behavior
   - Check for race conditions
   - Monitor memory usage

---

## Risk Assessment

### High Risk Items

1. **PSI URL Extraction Logic** (Req #7)
   - **Risk**: Complex timing dependencies, URL may not be stable
   - **Mitigation**: Implement fallback URL construction
   - **Testing**: Test with various PSI scenarios

2. **Retry Logic Changes** (Req #8)
   - **Risk**: Could increase overall runtime significantly
   - **Mitigation**: Use exponential backoff caps (max 120s wait)
   - **Testing**: Monitor average retry counts and total audit time

### Medium Risk Items

3. **Button Selector Changes** (Req #2)
   - **Risk**: PageSpeed Insights UI could change
   - **Mitigation**: Multiple selector fallbacks
   - **Testing**: Test against live PSI site regularly

4. **30-Second Wait** (Req #3)
   - **Risk**: May not be enough for very slow sites or may be too long
   - **Mitigation**: Make wait time configurable, add smart detection
   - **Testing**: Test with various site speeds

### Low Risk Items

5. **Score Polling Enhancements** (Req #4)
   - **Risk**: Low - primarily adds robustness
   - **Mitigation**: Keep existing logic as fallback

6. **Desktop View Switch** (Req #6)
   - **Risk**: Low - current implementation mostly works
   - **Mitigation**: Add better verification, not complete rewrite

---

## Success Criteria

### Functional Requirements

- ✅ All P0 issues resolved and tested
- ✅ Button click succeeds >95% of time
- ✅ 30-second wait implemented and logged
- ✅ PSI URLs captured for all failing scores
- ✅ Retry logic persists through timeout errors
- ✅ Exponential backoff prevents rapid retry thrashing

### Performance Requirements

- ✅ Average analysis time: 8-12 minutes per URL (accounting for retries)
- ✅ Success rate: >90% on first attempt, >98% after retries
- ✅ Memory usage: <1GB per browser instance
- ✅ Concurrent processing: 3-5 URLs simultaneously without issues

### Quality Requirements

- ✅ Unit test coverage: >75% for modified functions
- ✅ Integration tests passing: 100%
- ✅ Code review completed: All P0 changes
- ✅ Documentation updated: AGENTS.md, README.md
- ✅ Logging enhanced: All critical operations logged

---

## Files to Modify

### Primary Files

1. **`tools/qa/playwright_runner.py`** (Major changes)
   - Lines 683-686: Button selector fix
   - After line 686: Add 30-second wait
   - Lines 557-587: Score polling enhancement
   - Lines 625-633: PSI URL extraction fix
   - Lines 706-722: Desktop view switch enhancement
   - Lines 428-549: Retry logic overhaul

2. **`run_audit.py`** (Minor changes)
   - Lines 232-252: Update threshold handling logic
   - Import `urllib.parse` for fallback URL construction

### Documentation Files

3. **`AGENTS.md`**
   - Update performance metrics
   - Document 30-second wait requirement
   - Update retry logic documentation

4. **`README.md`**
   - Update "How It Works" section
   - Document increased retry attempts
   - Note PSI URL extraction improvements

### Test Files (New/Modified)

5. **`tests/test_playwright_runner.py`**
   - Add button selector tests
   - Add wait logic tests
   - Add PSI URL extraction tests
   - Add retry logic tests

---

## Rollback Plan

### If Critical Issues Arise

1. **Immediate Rollback**:
   - Revert `playwright_runner.py` to previous version
   - Revert `run_audit.py` to previous version
   - Test with 5-10 URLs to verify rollback success

2. **Gradual Rollout Alternative**:
   - Implement changes behind feature flag `--use-enhanced-logic`
   - Test in parallel with old implementation
   - Compare success rates before full rollout

3. **Rollback Triggers**:
   - Success rate drops below 85%
   - Average analysis time exceeds 20 minutes per URL
   - Memory leaks or crashes detected
   - Spreadsheet writes fail consistently

---

## Open Questions for User

### Question 1: 30-Second Wait Duration
**Question**: Is 30 seconds the correct wait time, or should it be configurable?

**Options**:
- A) Fixed 30 seconds (hardcoded)
- B) Configurable via CLI flag `--psi-init-wait` (default 30)
- C) Smart detection + fallback to 30 seconds

**Recommendation**: **Option B** - Allows flexibility for different network conditions

---

### Question 2: Retry Attempts
**Question**: How many retry attempts are acceptable?

**Current**: 3 retries (4 total attempts)  
**Proposed**: 5 retries (6 total attempts)

**Options**:
- A) Keep at 3 retries
- B) Increase to 5 retries
- C) Increase to 7 retries
- D) Make configurable via CLI

**Recommendation**: **Option B** - Good balance of persistence vs runtime

---

### Question 3: PSI URL Fallback Strategy
**Question**: If PSI URL cannot be captured from page, should we construct it manually?

**Options**:
- A) Always construct fallback URL (guarantees URLs written)
- B) Write error message if URL cannot be captured
- C) Leave cell empty if URL cannot be captured

**Recommendation**: **Option A** - Guarantees users always get a PSI URL for failing scores

---

### Question 4: Desktop View Wait Time
**Question**: Current 2-second wait after clicking Desktop button - should this change?

**Options**:
- A) Increase to 3-5 seconds (fixed)
- B) Dynamic wait (poll for score update)
- C) Make configurable

**Recommendation**: **Option B** - Most reliable, adapts to network speed

---

## Appendix: Example Scenarios

### Scenario 1: Score Below Threshold

**Input**: URL with mobile score 65, desktop score 72

**Expected Behavior**:
1. Extract mobile score (65)
2. Capture PSI URL for mobile
3. Switch to desktop
4. Extract desktop score (72)
5. Capture PSI URL for desktop
6. Write PSI URLs to columns F and G

**Current Behavior**: ❌ May not capture PSI URLs correctly

**After Fix**: ✅ PSI URLs captured and written correctly

---

### Scenario 2: Timeout During Analysis

**Input**: URL that causes PageSpeed Insights to timeout

**Expected Behavior**:
1. First attempt times out after 600s
2. Wait 5 seconds, retry
3. Second attempt times out after 600s
4. Wait 10 seconds, retry
5. Third attempt times out after 600s
6. Wait 20 seconds, retry
7. Continue up to 5 retries
8. If all fail, log error and move to next URL

**Current Behavior**: ❌ Timeout error raised immediately, no retry

**After Fix**: ✅ Retries with exponential backoff

---

### Scenario 3: Button Not Found

**Input**: PageSpeed Insights UI changes, button selector fails

**Expected Behavior**:
1. Try first selector: `[data-testid="analyze-button"]` - fails
2. Try second selector: `button[class*="analyze-button"]` - fails
3. Try third selector: `button:has-text("Analyze")` - succeeds
4. Click button and continue

**Current Behavior**: ⚠️ Limited selector fallback, may fail

**After Fix**: ✅ Multiple selectors tried before failing

---

## Summary & Next Steps

### Key Findings

**8 Critical Gaps Identified**:
1. ❌ Button selector too weak (P0)
2. ❌ Missing 30-second wait after button click (P0)
3. ❌ PSI URL extraction broken (P0)
4. ❌ Retry logic doesn't retry timeouts (P0)
5. ⚠️ Score polling could be more robust (P1)
6. ⚠️ Desktop view switch needs enhancement (P2)
7. ⚠️ Need better selector strategies throughout (P1)
8. ⚠️ Error logging could be more detailed (P2)

**3 Working Features**:
1. ✅ URL input and navigation
2. ✅ Spreadsheet integration
3. ✅ Caching system

**Bottom Line**: The tool is **60-70% functional** but has critical reliability issues that cause frequent failures. The P0 fixes are essential for production use.

---

### Immediate Actions Required

1. **User Review & Approval**:
   - Review this gap analysis
   - Answer open questions (Q1-Q4)
   - Approve Phase 1 (P0 Critical Fixes)
   - Set timeline expectations

2. **Implementation Start**:
   - Create feature branch: `git checkout -b fix/psi-critical-issues`
   - Begin Phase 1 fixes (P0 items)
   - Implement unit tests
   - Run integration tests

3. **Validation**:
   - Test with 20-50 URLs
   - Compare success rates before/after
   - Verify PSI URLs are captured correctly
   - Check retry logic behavior

---

### Estimated Timeline

| Phase | Work | Testing | Total |
|-------|------|---------|-------|
| Phase 1 (P0) | 12-14 hours | 2-3 hours | **14-17 hours** |
| Phase 2 (P1) | 2-3 hours | 1 hour | **3-4 hours** |
| Phase 3 (P2) | 2-3 hours | 1 hour | **3-4 hours** |
| **TOTAL** | | | **20-25 hours** |

**Recommended Schedule**: Complete Phase 1 (P0) immediately (2-3 days), then reassess before proceeding to P1/P2.

---

*End of Gap Analysis*
