import time
import os
import threading
import traceback
import psutil
from typing import Dict, Optional, Set, List
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, Route, Request
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightTimeoutError = Exception

from tools.utils.exceptions import RetryableError, PermanentError
from tools.utils.circuit_breaker import CircuitBreaker
from tools.utils.error_metrics import get_global_metrics
from tools.utils.logger import get_logger
from tools.cache.cache_manager import get_cache_manager


class PlaywrightRunnerError(Exception):
    pass


class PlaywrightTimeoutError(PlaywrightRunnerError):
    pass


class InstanceState(Enum):
    IDLE = "idle"
    BUSY = "busy"
    DEAD = "dead"


BLOCKED_RESOURCE_TYPES = {
    'image',
    'media',
    'font',
    'stylesheet',
    'websocket'
}

BLOCKED_URL_PATTERNS = [
    'google-analytics.com',
    'googletagmanager.com',
    'facebook.com/tr',
    'doubleclick.net',
    'googleadservices.com',
    'googlesyndication.com',
    'adservice.google.com',
    'advertising.com',
    'analytics.',
    '/ads/',
    '/ad/',
    'ads.',
    'ad.',
    'metrics.',
    'tracking.',
    'pixel.',
    'analytics',
    'beacon',
    'telemetry'
]


def should_block_resource(url: str, resource_type: str) -> bool:
    """
    Determine if a resource should be blocked based on type and URL patterns.
    
    Args:
        url: Resource URL
        resource_type: Resource type (image, script, stylesheet, etc.)
        
    Returns:
        True if resource should be blocked
    """
    if resource_type in BLOCKED_RESOURCE_TYPES:
        return True
    
    url_lower = url.lower()
    for pattern in BLOCKED_URL_PATTERNS:
        if pattern in url_lower:
            return True
    
    return False


@dataclass
class ResourceBlockingStats:
    """Statistics for resource blocking"""
    total_requests: int = 0
    blocked_requests: int = 0
    blocked_by_type: Dict[str, int] = field(default_factory=dict)
    blocked_by_pattern: int = 0
    
    def record_request(self):
        self.total_requests += 1
    
    def record_blocked(self, resource_type: str, is_pattern_block: bool = False):
        self.blocked_requests += 1
        if resource_type not in self.blocked_by_type:
            self.blocked_by_type[resource_type] = 0
        self.blocked_by_type[resource_type] += 1
        if is_pattern_block:
            self.blocked_by_pattern += 1
    
    def get_blocking_ratio(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.blocked_requests / self.total_requests
    
    def reset(self):
        self.total_requests = 0
        self.blocked_requests = 0
        self.blocked_by_type.clear()
        self.blocked_by_pattern = 0


@dataclass
class PlaywrightInstance:
    browser: Optional[Browser]
    context: Optional[BrowserContext]
    state: InstanceState
    memory_mb: float
    last_used: float
    warm_start: bool
    failures: int
    pid: Optional[int]
    request_blocking_enabled: bool = True
    blocking_stats: ResourceBlockingStats = field(default_factory=ResourceBlockingStats)
    total_analyses: int = 0
    total_page_load_time: float = 0.0
    startup_time: float = 0.0
    
    def is_alive(self) -> bool:
        if self.browser is None:
            return False
        try:
            return self.browser.is_connected()
        except Exception:
            return False
    
    def get_memory_usage(self) -> float:
        if self.pid is None or not self.is_alive():
            return 0.0
        try:
            proc = psutil.Process(self.pid)
            mem_info = proc.memory_info()
            self.memory_mb = mem_info.rss / (1024 * 1024)
            return self.memory_mb
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0
    
    def record_analysis(self, page_load_time: float):
        self.total_analyses += 1
        self.total_page_load_time += page_load_time
    
    def get_avg_page_load_time(self) -> float:
        if self.total_analyses == 0:
            return 0.0
        return self.total_page_load_time / self.total_analyses
    
    def kill(self):
        if self.browser and self.is_alive():
            try:
                if self.context:
                    self.context.close()
                self.browser.close()
            except Exception:
                pass
        self.state = InstanceState.DEAD


class PlaywrightPool:
    MAX_MEMORY_MB = 1024
    POOL_SIZE = 3
    
    def __init__(self):
        self.instances = []
        self.lock = threading.Lock()
        self.logger = get_logger()
        self._shutdown = False
        self._playwright = None
        self._total_warm_starts = 0
        self._total_cold_starts = 0
        self._total_startup_time = 0.0
    
    def _get_playwright(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise PermanentError(
                "Playwright is not installed. Install it with: pip install playwright && playwright install chromium"
            )
        
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        return self._playwright
    
    def get_instance(self) -> Optional[PlaywrightInstance]:
        with self.lock:
            for instance in self.instances:
                if instance.state == InstanceState.IDLE and instance.is_alive():
                    mem = instance.get_memory_usage()
                    if mem < self.MAX_MEMORY_MB:
                        instance.state = InstanceState.BUSY
                        instance.last_used = time.time()
                        self._total_warm_starts += 1
                        return instance
                    else:
                        self.logger.info(f"Killing instance due to high memory: {mem:.1f}MB")
                        instance.kill()
                        self.instances.remove(instance)
        return None
    
    def return_instance(self, instance: PlaywrightInstance, success: bool = True):
        with self.lock:
            if not success:
                instance.failures += 1
            
            mem = instance.get_memory_usage()
            if instance.failures >= 3 or mem >= self.MAX_MEMORY_MB or not instance.is_alive():
                if instance in self.instances:
                    self.instances.remove(instance)
                instance.kill()
                return
            
            instance.state = InstanceState.IDLE
    
    def create_instance(self) -> PlaywrightInstance:
        startup_start = time.time()
        try:
            pw = self._get_playwright()
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                java_script_enabled=True,
                bypass_csp=True,
                ignore_https_errors=True
            )
            
            browser_process = browser._impl_obj._connection._transport._proc if hasattr(browser, '_impl_obj') else None
            pid = browser_process.pid if browser_process else None
            
            startup_time = time.time() - startup_start
            
            instance = PlaywrightInstance(
                browser=browser,
                context=context,
                state=InstanceState.IDLE,
                memory_mb=0.0,
                last_used=time.time(),
                warm_start=False,
                failures=0,
                pid=pid,
                request_blocking_enabled=True,
                startup_time=startup_time
            )
            
            with self.lock:
                if len(self.instances) < self.POOL_SIZE:
                    self.instances.append(instance)
                self._total_cold_starts += 1
                self._total_startup_time += startup_time
            
            self.logger.info(f"Created new Playwright instance (PID: {pid}, startup time: {startup_time:.2f}s)")
            return instance
        except Exception as e:
            raise PermanentError(f"Failed to create Playwright instance: {e}", original_exception=e)
    
    def cleanup_dead_instances(self):
        with self.lock:
            dead_instances = [i for i in self.instances if not i.is_alive() or i.state == InstanceState.DEAD]
            for instance in dead_instances:
                instance.kill()
                self.instances.remove(instance)
    
    def get_pool_stats(self) -> Dict:
        with self.lock:
            return {
                'total_instances': len(self.instances),
                'idle_instances': sum(1 for i in self.instances if i.state == InstanceState.IDLE),
                'busy_instances': sum(1 for i in self.instances if i.state == InstanceState.BUSY),
                'total_warm_starts': self._total_warm_starts,
                'total_cold_starts': self._total_cold_starts,
                'avg_startup_time': self._total_startup_time / self._total_cold_starts if self._total_cold_starts > 0 else 0.0,
                'instances': [
                    {
                        'pid': i.pid,
                        'state': i.state.value,
                        'memory_mb': i.get_memory_usage(),
                        'total_analyses': i.total_analyses,
                        'avg_page_load_time': i.get_avg_page_load_time(),
                        'failures': i.failures,
                        'blocking_stats': {
                            'total_requests': i.blocking_stats.total_requests,
                            'blocked_requests': i.blocking_stats.blocked_requests,
                            'blocking_ratio': i.blocking_stats.get_blocking_ratio()
                        }
                    }
                    for i in self.instances
                ]
            }
    
    def shutdown(self):
        self._shutdown = True
        with self.lock:
            for instance in self.instances:
                instance.kill()
            self.instances.clear()
            if self._playwright:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None


_pool = None
_pool_lock = threading.Lock()


def _get_pool() -> PlaywrightPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = PlaywrightPool()
        return _pool


_circuit_breaker = None
_circuit_breaker_lock = threading.Lock()


def _get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker
    with _circuit_breaker_lock:
        if _circuit_breaker is None:
            logger = get_logger()
            _circuit_breaker = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=300.0,
                expected_exception=PlaywrightRunnerError,
                name="PageSpeedInsights",
                logger=logger
            )
        return _circuit_breaker


class ProgressiveTimeout:
    def __init__(self, initial_timeout: int = 300):
        self.initial_timeout = initial_timeout
        self.current_timeout = initial_timeout
        self.max_timeout = 600
        self.failure_count = 0
        self.lock = threading.Lock()
    
    def get_timeout(self) -> int:
        with self.lock:
            return self.current_timeout
    
    def record_failure(self):
        with self.lock:
            self.failure_count += 1
            if self.failure_count >= 1 and self.current_timeout < self.max_timeout:
                old_timeout = self.current_timeout
                self.current_timeout = self.max_timeout
                logger = get_logger()
                logger.info(f"Progressive timeout: increased from {old_timeout}s to {self.current_timeout}s after failure")
    
    def record_success(self):
        pass


_progressive_timeout = None
_progressive_timeout_lock = threading.Lock()


def _get_progressive_timeout() -> ProgressiveTimeout:
    global _progressive_timeout
    with _progressive_timeout_lock:
        if _progressive_timeout is None:
            _progressive_timeout = ProgressiveTimeout()
        return _progressive_timeout


def _setup_request_interception(page: Page, instance: PlaywrightInstance) -> None:
    """
    Set up request interception to block unnecessary resources.
    
    Args:
        page: Playwright page object
        instance: PlaywrightInstance to track blocking stats
    """
    def handle_route(route: Route, request: Request):
        url = request.url
        resource_type = request.resource_type
        
        instance.blocking_stats.record_request()
        
        if should_block_resource(url, resource_type):
            is_pattern_block = any(pattern in url.lower() for pattern in BLOCKED_URL_PATTERNS)
            instance.blocking_stats.record_blocked(resource_type, is_pattern_block)
            route.abort()
        else:
            route.continue_()
    
    if instance.request_blocking_enabled:
        page.route('**/*', handle_route)


def run_analysis(url: str, timeout: int = 600, max_retries: int = 3, skip_cache: bool = False) -> Dict[str, Optional[int | str]]:
    """
    Run Playwright analysis for a given URL to get PageSpeed Insights scores.
    Includes circuit breaker protection, error metrics collection, caching, and optimizations.
    
    Args:
        url: The URL to analyze
        timeout: Maximum time in seconds to wait for analysis to complete (default: 600)
        max_retries: Maximum number of retry attempts for transient errors (default: 3)
        skip_cache: If True, bypass cache and force fresh analysis (default: False)
        
    Returns:
        Dictionary with keys:
            - mobile_score: Integer score for mobile (0-100)
            - desktop_score: Integer score for desktop (0-100)
            - mobile_psi_url: URL to mobile PSI report (if score < 80, else None)
            - desktop_psi_url: URL to desktop PSI report (if score < 80, else None)
            
    Raises:
        PlaywrightRunnerError: If Playwright execution fails
        PlaywrightTimeoutError: If analysis exceeds timeout
        PermanentError: If there's a permanent error (e.g., Playwright not installed)
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise PermanentError(
            "Playwright is not installed. Install it with: pip install playwright && playwright install chromium"
        )
    
    metrics = get_global_metrics()
    metrics.increment_total_operations()
    logger = get_logger()
    cache_manager = get_cache_manager(enabled=not skip_cache)
    
    from tools.metrics.metrics_collector import get_metrics_collector
    metrics_collector = get_metrics_collector()
    
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
    
    last_exception = None
    was_retried = False
    
    for attempt in range(max_retries + 1):
        try:
            result = _run_analysis_once(url, timeout)
            metrics.record_success('run_analysis', was_retried=was_retried)
            metrics_collector.record_api_call_cypress()
            progressive_timeout.record_success()
            
            if not skip_cache:
                cache_manager.set(url, result)
            
            result['_from_cache'] = False
            return result
            
        except PermanentError:
            metrics.record_failure('run_analysis')
            progressive_timeout.record_failure()
            raise
            
        except PlaywrightTimeoutError as e:
            last_exception = e
            progressive_timeout.record_failure()
            metrics.record_error(
                error_type='PlaywrightTimeoutError',
                function_name='run_analysis',
                error_message=str(e),
                is_retryable=False,
                attempt=attempt + 1,
                traceback=traceback.format_exc()
            )
            metrics.record_failure('run_analysis')
            raise
            
        except (PlaywrightRunnerError, Exception) as e:
            last_exception = e
            was_retried = True
            progressive_timeout.record_failure()
            
            metrics.record_error(
                error_type=type(e).__name__,
                function_name='run_analysis',
                error_message=str(e),
                is_retryable=True,
                attempt=attempt + 1,
                traceback=traceback.format_exc()
            )
            
            if attempt < max_retries:
                wait_time = 5
                logger.warning(
                    f"Retrying analysis for {url} after error (attempt {attempt + 1}/{max_retries + 1})",
                    extra={
                        'url': url,
                        'attempt': attempt + 1,
                        'error_type': type(e).__name__,
                        'retry_delay': wait_time
                    }
                )
                time.sleep(wait_time)
                continue
            else:
                metrics.record_failure('run_analysis')
                raise
    
    if last_exception:
        metrics.record_failure('run_analysis')
        raise last_exception


def _monitor_process_memory(instance: PlaywrightInstance, max_memory_mb: float = 1024) -> bool:
    memory_mb = instance.get_memory_usage()
    return memory_mb >= max_memory_mb


def _click_analyze_button(page: Page, timeout_ms: int = 10000) -> bool:
    """
    Click the Analyze button using multiple selector strategies with retry logic.
    
    Args:
        page: Playwright page object
        timeout_ms: Timeout in milliseconds for each selector attempt
        
    Returns:
        True if button was clicked successfully, False otherwise
    """
    logger = get_logger()
    
    selectors = [
        'button:has-text("Analyze")',
        '[aria-label*="Analyze"]',
        'button.lh-button--primary',
        'button[type="submit"]',
        'button:has-text("analyze")',
        '[aria-label*="analyze"]',
        'button.analyze-button',
        'button[class*="analyze"]',
        'button[class*="primary"]',
        'form button[type="submit"]'
    ]
    
    for i, selector in enumerate(selectors, 1):
        try:
            logger.debug(f"Attempting to click analyze button with selector {i}/{len(selectors)}: {selector}")
            button = page.locator(selector).first
            button.click(timeout=timeout_ms)
            logger.info(f"Successfully clicked analyze button using selector: {selector}")
            return True
        except Exception as e:
            logger.debug(f"Selector {selector} failed: {e}")
            continue
    
    logger.error(f"All {len(selectors)} analyze button selectors failed")
    return False


def _wait_for_device_buttons(page: Page, timeout_seconds: int = 30) -> bool:
    """
    Poll for mobile and desktop buttons to appear on PageSpeed Insights page.
    Uses multiple selector strategies to maximize detection success.
    
    Args:
        page: Playwright page object
        timeout_seconds: Maximum time to wait (default: 30)
        
    Returns:
        True if buttons are found and visible, False if timeout
    """
    logger = get_logger()
    start_time = time.time()
    poll_interval = 1
    
    button_selectors = [
        'button:has-text("Mobile")',
        'button:has-text("Desktop")',
        '[role="tab"]:has-text("Mobile")',
        '[role="tab"]:has-text("Desktop")'
    ]
    
    while time.time() - start_time < timeout_seconds:
        for selector in button_selectors:
            try:
                button = page.locator(selector).first
                if button.is_visible(timeout=500):
                    logger.debug(f"Found device button using selector: {selector}")
                    return True
            except Exception:
                continue
        
        time.sleep(poll_interval)
    
    logger.warning(f"Device buttons not found within {timeout_seconds}s timeout")
    return False


def _wait_for_analysis_completion(page: Page, timeout_seconds: int = 180) -> bool:
    """
    Smart polling to wait for PageSpeed Insights analysis to complete.
    Waits for mobile/desktop buttons to appear before proceeding.
    
    Args:
        page: Playwright page object
        timeout_seconds: Maximum time to wait (default: 180)
        
    Returns:
        True if analysis completed, False if timeout
    """
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
                
                try:
                    mobile_button = page.locator('button:has-text("Mobile"), [role="tab"]:has-text("Mobile")').first
                    desktop_button = page.locator('button:has-text("Desktop"), [role="tab"]:has-text("Desktop")').first
                    
                    mobile_visible = mobile_button.is_visible(timeout=1000)
                    desktop_visible = desktop_button.is_visible(timeout=1000)
                    
                    if mobile_visible or desktop_visible:
                        logger.debug(f"Mobile/Desktop buttons are visible (mobile: {mobile_visible}, desktop: {desktop_visible})")
                        return True
                    else:
                        logger.debug("Score elements found but mobile/desktop buttons not yet visible, continuing to poll...")
                except Exception as e:
                    logger.debug(f"Mobile/Desktop buttons not yet visible: {e}")
            
        except Exception as e:
            logger.debug(f"Polling error: {e}")
        
        time.sleep(poll_interval)
    
    return False


def _extract_score_from_element(page: Page, view_type: str, max_retries: int = 5, retry_delay: float = 1.0) -> Optional[int]:
    """
    Extract score from PageSpeed Insights page for given view type with enhanced reliability.
    
    Implements retry logic with delays to handle cases where score elements exist but are not yet populated.
    Validates that extracted scores are valid integers between 0-100.
    Uses multiple fallback selectors including text content parsing from gauge elements.
    
    Args:
        page: Playwright page object
        view_type: 'mobile' or 'desktop'
        max_retries: Maximum number of retry attempts (default: 5)
        retry_delay: Delay in seconds between retries (default: 1.0)
        
    Returns:
        Score as integer (0-100) or None if not found after all retries
    """
    logger = get_logger()
    
    primary_selectors = [
        '.lh-exp-gauge__percentage',
        '.lh-gauge__percentage'
    ]
    
    fallback_selectors = [
        '[data-testid="lh-gauge"]',
        '[data-testid="score-gauge"]',
        '.lh-gauge__wrapper .lh-gauge__percentage',
        '.lh-exp-gauge__wrapper .lh-exp-gauge__percentage',
        '[class*="gauge"][class*="percentage"]',
        '[class*="score"][class*="value"]'
    ]
    
    all_selectors = primary_selectors + fallback_selectors
    
    for attempt in range(max_retries):
        for selector in all_selectors:
            try:
                elements = page.locator(selector).all()
                if not elements:
                    continue
                
                score_text = elements[0].inner_text().strip()
                
                if not score_text or score_text == '':
                    logger.debug(f"Selector {selector} found element but content is empty (attempt {attempt + 1}/{max_retries})")
                    continue
                
                score_text = score_text.replace('%', '').strip()
                
                try:
                    score = int(score_text)
                except ValueError:
                    logger.debug(f"Could not parse score text '{score_text}' as integer for selector {selector}")
                    continue
                
                if score < 0 or score > 100:
                    logger.warning(f"Invalid score {score} extracted for {view_type} (must be 0-100), selector: {selector}")
                    continue
                
                logger.debug(f"Successfully extracted {view_type} score: {score} using selector {selector} (attempt {attempt + 1}/{max_retries})")
                return score
                
            except Exception as e:
                logger.debug(f"Failed to extract score with selector {selector} (attempt {attempt + 1}/{max_retries}): {e}")
                continue
        
        if attempt < max_retries - 1:
            logger.debug(f"No valid score found in attempt {attempt + 1}/{max_retries}, retrying after {retry_delay}s delay...")
            time.sleep(retry_delay)
    
    logger.warning(f"Failed to extract {view_type} score after {max_retries} attempts with all selectors")
    return None


def _get_psi_report_url(page: Page) -> Optional[str]:
    """Extract PSI report URL from current page"""
    try:
        current_url = page.url
        if 'pagespeed.web.dev' in current_url:
            return current_url
    except Exception:
        pass
    return None


def _run_analysis_once(url: str, timeout: int) -> Dict[str, Optional[int | str]]:
    """
    Internal function to run a single Playwright analysis attempt with circuit breaker protection,
    result caching, memory monitoring, and resource blocking optimizations.
    """
    circuit_breaker = _get_circuit_breaker()
    logger = get_logger()
    pool = _get_pool()
    
    from tools.metrics.metrics_collector import get_metrics_collector
    metrics_collector = get_metrics_collector()
    
    def _execute_playwright():
        instance = pool.get_instance()
        warm_start = instance is not None and instance.warm_start
        
        analysis_start_time = time.time()
        
        if warm_start:
            logger.debug(f"Using warm Playwright instance for {url}")
        else:
            logger.debug(f"Cold start Playwright instance for {url}")
            if instance is None:
                instance = pool.create_instance()
        
        page = None
        page_load_start = None
        try:
            context = instance.context
            page = context.new_page()
            
            _setup_request_interception(page, instance)
            
            page.set_default_timeout(timeout * 1000)
            
            instance.warm_start = True
            
            logger.debug(f"Navigating to PageSpeed Insights...")
            nav_start = time.time()
            page.goto('https://pagespeed.web.dev/', wait_until='domcontentloaded', timeout=30000)
            nav_time = time.time() - nav_start
            
            logger.debug(f"Entering URL: {url}")
            url_input = page.locator('input[type="url"], input[name="url"], input[placeholder*="URL"]').first
            url_input.fill(url)
            time.sleep(0.5)
            
            logger.debug("Clicking analyze button...")
            page_load_start = time.time()
            button_clicked = _click_analyze_button(page, timeout_ms=10000)
            if not button_clicked:
                pool.return_instance(instance, success=False)
                raise PlaywrightRunnerError("Failed to click analyze button - all selectors failed")
            
            logger.debug("Waiting for analysis to complete...")
            analysis_completed = _wait_for_analysis_completion(page, timeout_seconds=min(180, timeout))
            
            if not analysis_completed:
                elapsed = time.time() - analysis_start_time
                if elapsed >= timeout:
                    pool.return_instance(instance, success=False)
                    raise PlaywrightTimeoutError(f"Analysis exceeded {timeout} seconds timeout")
                pool.return_instance(instance, success=False)
                raise PlaywrightRunnerError("Analysis did not complete - score elements not found")
            
            page_load_time = time.time() - page_load_start if page_load_start else 0.0
            
            if _monitor_process_memory(instance, max_memory_mb=PlaywrightPool.MAX_MEMORY_MB):
                logger.warning(f"Playwright process exceeded memory limit ({PlaywrightPool.MAX_MEMORY_MB}MB)")
                pool.return_instance(instance, success=False)
                raise PlaywrightRunnerError("Playwright process exceeded memory limit")
            
            logger.debug("Waiting for device buttons to be available...")
            buttons_found = _wait_for_device_buttons(page, timeout_seconds=30)
            
            if not buttons_found:
                logger.warning("Device buttons not found within 30s, attempting score extraction anyway...")
            
            time.sleep(2)
            
            logger.debug("Extracting mobile score...")
            mobile_score = _extract_score_from_element(page, 'mobile')
            mobile_psi_url = _get_psi_report_url(page) if mobile_score and mobile_score < 80 else None
            
            logger.debug("Switching to desktop view...")
            desktop_button_selectors = [
                'button:has-text("Desktop")',
                '[role="tab"]:has-text("Desktop")'
            ]
            
            desktop_score = None
            desktop_psi_url = None
            desktop_switched = False
            
            for selector in desktop_button_selectors:
                try:
                    desktop_button = page.locator(selector).first
                    desktop_button.click(timeout=5000)
                    desktop_switched = True
                    logger.debug(f"Successfully switched to desktop view using selector: {selector}")
                    break
                except Exception as e:
                    logger.debug(f"Failed to switch to desktop with selector {selector}: {e}")
                    continue
            
            if desktop_switched:
                time.sleep(2)
                logger.debug("Extracting desktop score...")
                desktop_score = _extract_score_from_element(page, 'desktop')
                desktop_psi_url = _get_psi_report_url(page) if desktop_score and desktop_score < 80 else None
            else:
                logger.warning("Failed to switch to desktop view with all selectors")
            
            if mobile_score is None and desktop_score is None:
                pool.return_instance(instance, success=False)
                raise PlaywrightRunnerError("Failed to extract any scores from PageSpeed Insights")
            
            instance.record_analysis(page_load_time)
            
            browser_startup_time = instance.startup_time if not warm_start else 0.0
            metrics_collector.record_playwright_metrics(
                page_load_time=page_load_time,
                browser_startup_time=browser_startup_time,
                memory_mb=instance.get_memory_usage(),
                warm_start=warm_start,
                blocked_requests=instance.blocking_stats.blocked_requests,
                total_requests=instance.blocking_stats.total_requests
            )
            
            page.close()
            pool.return_instance(instance, success=True)
            
            return {
                'mobile_score': mobile_score,
                'desktop_score': desktop_score,
                'mobile_psi_url': mobile_psi_url,
                'desktop_psi_url': desktop_psi_url,
                '_warm_start': warm_start,
                '_page_load_time': page_load_time,
                '_browser_startup_time': browser_startup_time,
                '_memory_mb': instance.get_memory_usage(),
                '_blocked_requests': instance.blocking_stats.blocked_requests,
                '_total_requests': instance.blocking_stats.total_requests
            }
            
        except PlaywrightTimeoutError:
            if page:
                try:
                    page.close()
                except Exception:
                    pass
            pool.return_instance(instance, success=False)
            raise
            
        except Exception as e:
            if page:
                try:
                    page.close()
                except Exception:
                    pass
            pool.return_instance(instance, success=False)
            
            if isinstance(e, PlaywrightRunnerError):
                raise
            
            raise PlaywrightRunnerError(f"Playwright execution failed: {e}") from e
    
    try:
        return circuit_breaker.call(_execute_playwright)
    except Exception as e:
        if "Circuit breaker" in str(e) and "is OPEN" in str(e):
            logger.error(
                f"Circuit breaker is open - PageSpeed Insights unavailable",
                extra={
                    'circuit_state': str(circuit_breaker.state.value),
                    'failure_count': circuit_breaker.failure_count,
                    'url': url
                }
            )
            raise PlaywrightRunnerError(str(e)) from e
        raise


def shutdown_pool():
    """Shutdown the Playwright pool (call on application exit)"""
    pool = _get_pool()
    pool.shutdown()


def get_pool_stats() -> Dict:
    """Get current pool statistics for monitoring"""
    pool = _get_pool()
    return pool.get_pool_stats()
