import time
import os
import threading
import traceback
import psutil
from typing import Dict, Optional, Set, List
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from datetime import datetime

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


class PlaywrightAnalysisTimeoutError(PlaywrightRunnerError):
    """Timeout during analysis - should abort, not retry"""
    pass


class PlaywrightSelectorTimeoutError(PlaywrightRunnerError):
    """Timeout finding selectors - should retry with fresh page load"""
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


DEBUG_MODE = False
DEBUG_SCREENSHOTS_DIR = 'debug_screenshots'


def set_debug_mode(enabled: bool):
    """Enable or disable debug mode globally"""
    global DEBUG_MODE
    DEBUG_MODE = enabled
    if enabled and not os.path.exists(DEBUG_SCREENSHOTS_DIR):
        os.makedirs(DEBUG_SCREENSHOTS_DIR, exist_ok=True)


def get_debug_mode() -> bool:
    """Check if debug mode is enabled"""
    return DEBUG_MODE


def _get_timestamp_filename(url: str, suffix: str = "") -> str:
    """
    Generate a filename with timestamp and sanitized URL.
    
    Args:
        url: The URL being processed
        suffix: Optional suffix for the filename (e.g., 'error', 'screenshot')
        
    Returns:
        Sanitized filename with timestamp
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    
    sanitized_url = url.replace('https://', '').replace('http://', '')
    sanitized_url = ''.join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in sanitized_url)
    sanitized_url = sanitized_url[:100]
    
    if suffix:
        return f"{timestamp}_{sanitized_url}_{suffix}"
    return f"{timestamp}_{sanitized_url}"


def _save_debug_screenshot(page: Page, url: str, reason: str = "error") -> Optional[str]:
    """
    Capture and save a screenshot for debugging purposes.
    
    Args:
        page: Playwright page object
        url: The URL being analyzed
        reason: Reason for screenshot (e.g., 'error', 'timeout')
        
    Returns:
        Path to saved screenshot or None if failed
    """
    try:
        if not os.path.exists(DEBUG_SCREENSHOTS_DIR):
            os.makedirs(DEBUG_SCREENSHOTS_DIR, exist_ok=True)
        
        filename = _get_timestamp_filename(url, f"screenshot_{reason}")
        filepath = os.path.join(DEBUG_SCREENSHOTS_DIR, f"{filename}.png")
        
        page.screenshot(path=filepath, full_page=True)
        return filepath
    except Exception as e:
        logger = get_logger()
        logger.debug(f"Failed to save screenshot: {e}")
        return None


def _save_debug_html(page: Page, url: str, reason: str = "error") -> Optional[str]:
    """
    Save page HTML for debugging purposes.
    
    Args:
        page: Playwright page object
        url: The URL being analyzed
        reason: Reason for saving HTML (e.g., 'error', 'timeout')
        
    Returns:
        Path to saved HTML file or None if failed
    """
    try:
        if not os.path.exists(DEBUG_SCREENSHOTS_DIR):
            os.makedirs(DEBUG_SCREENSHOTS_DIR, exist_ok=True)
        
        filename = _get_timestamp_filename(url, f"page_{reason}")
        filepath = os.path.join(DEBUG_SCREENSHOTS_DIR, f"{filename}.html")
        
        html_content = page.content()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return filepath
    except Exception as e:
        logger = get_logger()
        logger.debug(f"Failed to save HTML: {e}")
        return None


def _get_page_info(page: Page) -> Dict[str, any]:
    """
    Extract diagnostic information from the current page.
    
    Args:
        page: Playwright page object
        
    Returns:
        Dictionary containing page URL, title, and available buttons/elements
    """
    info = {
        'url': None,
        'title': None,
        'buttons': [],
        'inputs': [],
        'links': []
    }
    
    try:
        info['url'] = page.url
    except Exception:
        pass
    
    try:
        info['title'] = page.title()
    except Exception:
        pass
    
    try:
        buttons = page.locator('button').all()
        info['buttons'] = [
            {
                'text': btn.inner_text()[:50] if btn.is_visible() else '[hidden]',
                'visible': btn.is_visible()
            }
            for btn in buttons[:10]
        ]
    except Exception:
        pass
    
    try:
        inputs = page.locator('input').all()
        info['inputs'] = [
            {
                'type': inp.get_attribute('type'),
                'placeholder': inp.get_attribute('placeholder'),
                'visible': inp.is_visible()
            }
            for inp in inputs[:10]
        ]
    except Exception:
        pass
    
    try:
        links = page.locator('a').all()
        info['links'] = [
            {
                'text': link.inner_text()[:50] if link.is_visible() else '[hidden]',
                'href': link.get_attribute('href'),
                'visible': link.is_visible()
            }
            for link in links[:10]
        ]
    except Exception:
        pass
    
    return info


def _create_enhanced_error_message(
    base_message: str,
    url: str,
    page: Optional[Page] = None,
    last_successful_step: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    html_path: Optional[str] = None
) -> str:
    """
    Create an enhanced error message with debugging context.
    
    Args:
        base_message: Original error message
        url: URL being analyzed
        page: Playwright page object (optional)
        last_successful_step: Description of last successful step (optional)
        screenshot_path: Path to debug screenshot (optional)
        html_path: Path to saved HTML (optional)
        
    Returns:
        Enhanced error message with context
    """
    parts = [base_message]
    
    if last_successful_step:
        parts.append(f"\nLast successful step: {last_successful_step}")
    
    if page:
        page_info = _get_page_info(page)
        
        if page_info['url']:
            parts.append(f"\nCurrent page URL: {page_info['url']}")
        
        if page_info['title']:
            parts.append(f"Page title: {page_info['title']}")
        
        if page_info['buttons']:
            parts.append("\nAvailable buttons:")
            for i, btn in enumerate(page_info['buttons'][:5], 1):
                visibility = "visible" if btn['visible'] else "hidden"
                parts.append(f"  {i}. {btn['text']} ({visibility})")
        
        if page_info['inputs']:
            parts.append("\nAvailable inputs:")
            for i, inp in enumerate(page_info['inputs'][:5], 1):
                visibility = "visible" if inp['visible'] else "hidden"
                inp_type = inp['type'] or 'text'
                placeholder = inp['placeholder'] or ''
                parts.append(f"  {i}. {inp_type} input ({visibility}) - {placeholder}")
    
    if screenshot_path:
        parts.append(f"\nDebug screenshot saved: {screenshot_path}")
    
    if html_path:
        parts.append(f"Debug HTML saved: {html_path}")
    
    return '\n'.join(parts)


@dataclass
class PageReloadTracker:
    """Track page reload attempts for recovery logic"""
    reload_count: int = 0
    max_reloads: int = 3
    last_reload_time: float = 0.0
    
    def should_reload(self) -> bool:
        """Check if another reload attempt should be made"""
        return self.reload_count < self.max_reloads
    
    def record_reload(self):
        """Record a reload attempt"""
        self.reload_count += 1
        self.last_reload_time = time.time()
    
    def reset(self):
        """Reset reload counter"""
        self.reload_count = 0
        self.last_reload_time = 0.0


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
        logger = self.logger
        
        try:
            pw = self._get_playwright()
            
            launch_args = [
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
            
            if DEBUG_MODE:
                logger.debug("Creating Playwright instance with verbose logging enabled")
            
            browser = pw.chromium.launch(
                headless=True,
                args=launch_args
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
            
            logger.info(f"Created new Playwright instance (PID: {pid}, startup time: {startup_time:.2f}s)")
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


def run_analysis(url: str, timeout: int = 600, skip_cache: bool = False, force_retry: bool = False) -> Dict[str, Optional[int | str]]:
    """
    Run Playwright analysis for a given URL to get PageSpeed Insights scores.
    Implements persistent retry-until-success with exponential backoff for transient errors.
    
    Args:
        url: The URL to analyze
        timeout: Maximum time in seconds for overall operation (default: 600)
        skip_cache: If True, bypass cache and force fresh analysis (default: False)
        force_retry: If True, bypass circuit breaker during critical runs (default: False)
        
    Returns:
        Dictionary with keys:
            - mobile_score: Integer score for mobile (0-100)
            - desktop_score: Integer score for desktop (0-100)
            - mobile_psi_url: URL to mobile PSI report (if score < 80, else None)
            - desktop_psi_url: URL to desktop PSI report (if score < 80, else None)
            
    Raises:
        PlaywrightAnalysisTimeoutError: If overall analysis exceeds timeout (not retryable)
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
    
    overall_start_time = time.time()
    last_exception = None
    was_retried = False
    attempt = 0
    initial_backoff = 5
    max_backoff = 60
    current_backoff = initial_backoff
    
    while True:
        attempt += 1
        
        if time.time() - overall_start_time >= timeout:
            elapsed = time.time() - overall_start_time
            logger.error(f"Overall analysis timeout after {elapsed:.1f}s for {url}")
            metrics.record_failure('run_analysis')
            progressive_timeout.record_failure()
            raise PlaywrightAnalysisTimeoutError(f"Analysis exceeded overall timeout of {timeout}s")
        
        try:
            result = _run_analysis_once(url, timeout, force_retry=force_retry)
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
            
        except PlaywrightAnalysisTimeoutError:
            metrics.record_failure('run_analysis')
            progressive_timeout.record_failure()
            raise
            
        except PlaywrightSelectorTimeoutError as e:
            last_exception = e
            was_retried = True
            progressive_timeout.record_failure()
            
            metrics.record_error(
                error_type='PlaywrightSelectorTimeoutError',
                function_name='run_analysis',
                error_message=str(e),
                is_retryable=True,
                attempt=attempt,
                traceback=traceback.format_exc()
            )
            
            logger.warning(
                f"Selector timeout for {url}, retrying with fresh page load (attempt {attempt})",
                extra={
                    'url': url,
                    'attempt': attempt,
                    'error_type': 'PlaywrightSelectorTimeoutError',
                    'retry_delay': current_backoff
                }
            )
            
            time.sleep(current_backoff)
            current_backoff = min(current_backoff * 2, max_backoff)
            continue
            
        except (PlaywrightRunnerError, RetryableError, Exception) as e:
            last_exception = e
            was_retried = True
            progressive_timeout.record_failure()
            
            is_retryable = not isinstance(e, PermanentError)
            
            metrics.record_error(
                error_type=type(e).__name__,
                function_name='run_analysis',
                error_message=str(e),
                is_retryable=is_retryable,
                attempt=attempt,
                traceback=traceback.format_exc()
            )
            
            logger.warning(
                f"Retryable error for {url}, retrying (attempt {attempt})",
                extra={
                    'url': url,
                    'attempt': attempt,
                    'error_type': type(e).__name__,
                    'retry_delay': current_backoff,
                    'error_message': str(e)
                }
            )
            
            time.sleep(current_backoff)
            current_backoff = min(current_backoff * 2, max_backoff)
            continue


def _monitor_process_memory(instance: PlaywrightInstance, max_memory_mb: float = 1024) -> bool:
    memory_mb = instance.get_memory_usage()
    return memory_mb >= max_memory_mb


def _reload_page_with_retry(page: Page, url: str, reload_tracker: PageReloadTracker, logger) -> bool:
    """
    Reload the page with retry logic.
    
    Args:
        page: Playwright page object
        url: URL to reload
        reload_tracker: PageReloadTracker to track reload attempts
        logger: Logger instance
        
    Returns:
        True if reload successful, False otherwise
    """
    if not reload_tracker.should_reload():
        logger.error(f"Maximum page reload attempts ({reload_tracker.max_reloads}) reached")
        return False
    
    try:
        reload_tracker.record_reload()
        logger.info(f"Reloading page (attempt {reload_tracker.reload_count}/{reload_tracker.max_reloads})...")
        page.reload(wait_until='domcontentloaded', timeout=30000)
        time.sleep(2)
        return True
    except Exception as e:
        logger.error(f"Page reload failed: {e}")
        return False


def _click_analyze_button(page: Page, url: str, reload_tracker: PageReloadTracker, timeout_ms: int = 10000) -> bool:
    """
    Click the Analyze button using multiple selector strategies with retry logic and page reload on failure.
    
    Args:
        page: Playwright page object
        url: URL being analyzed (for error reporting)
        reload_tracker: PageReloadTracker for page reload logic
        timeout_ms: Timeout in milliseconds for each selector attempt
        
    Returns:
        True if button was clicked successfully, False otherwise
        
    Raises:
        PlaywrightSelectorTimeoutError: If all selectors fail after retries
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
    
    max_attempts = 2
    
    for attempt in range(max_attempts):
        for i, selector in enumerate(selectors, 1):
            try:
                if DEBUG_MODE:
                    logger.debug(f"Attempting to click analyze button with selector {i}/{len(selectors)}: {selector}")
                
                button = page.locator(selector).first
                button.click(timeout=timeout_ms)
                logger.info(f"Successfully clicked analyze button using selector: {selector}")
                return True
            except Exception as e:
                if DEBUG_MODE:
                    logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        if attempt < max_attempts - 1:
            logger.warning(f"All analyze button selectors failed on attempt {attempt + 1}, reloading page...")
            
            screenshot_path = None
            html_path = None
            if DEBUG_MODE or get_debug_mode():
                screenshot_path = _save_debug_screenshot(page, url, "button_not_found")
                html_path = _save_debug_html(page, url, "button_not_found")
            
            if not _reload_page_with_retry(page, url, reload_tracker, logger):
                error_msg = _create_enhanced_error_message(
                    f"Failed to click analyze button after {max_attempts} attempts - all selectors failed",
                    url,
                    page=page,
                    last_successful_step="Navigated to PageSpeed Insights and entered URL",
                    screenshot_path=screenshot_path,
                    html_path=html_path
                )
                raise PlaywrightSelectorTimeoutError(error_msg)
    
    screenshot_path = None
    html_path = None
    if DEBUG_MODE or get_debug_mode():
        screenshot_path = _save_debug_screenshot(page, url, "button_not_found_final")
        html_path = _save_debug_html(page, url, "button_not_found_final")
    
    error_msg = _create_enhanced_error_message(
        f"Failed to click analyze button after {max_attempts} attempts - all selectors failed",
        url,
        page=page,
        last_successful_step="Navigated to PageSpeed Insights and entered URL",
        screenshot_path=screenshot_path,
        html_path=html_path
    )
    raise PlaywrightSelectorTimeoutError(error_msg)


def _wait_for_device_buttons(page: Page, url: str, reload_tracker: PageReloadTracker, timeout_seconds: int = 30) -> bool:
    """
    Poll for mobile and desktop buttons to appear on PageSpeed Insights page.
    Uses multiple selector strategies to maximize detection success.
    
    Args:
        page: Playwright page object
        url: URL being analyzed
        reload_tracker: PageReloadTracker for page reload logic
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
                    if DEBUG_MODE:
                        logger.debug(f"Found device button using selector: {selector}")
                    return True
            except Exception:
                continue
        
        time.sleep(poll_interval)
    
    logger.warning(f"Device buttons not found within {timeout_seconds}s timeout")
    
    if DEBUG_MODE or get_debug_mode():
        screenshot_path = _save_debug_screenshot(page, url, "device_buttons_timeout")
        html_path = _save_debug_html(page, url, "device_buttons_timeout")
        if screenshot_path:
            logger.info(f"Debug screenshot saved: {screenshot_path}")
        if html_path:
            logger.info(f"Debug HTML saved: {html_path}")
    
    return False


def _wait_for_analysis_completion(page: Page, url: str, reload_tracker: PageReloadTracker, timeout_seconds: int = 180) -> bool:
    """
    Smart polling to wait for PageSpeed Insights analysis to complete.
    Waits for mobile/desktop buttons to appear before proceeding.
    
    Args:
        page: Playwright page object
        url: URL being analyzed
        reload_tracker: PageReloadTracker for page reload logic
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
                if DEBUG_MODE:
                    logger.debug(f"Found {len(score_elements)} score elements")
                
                try:
                    mobile_button = page.locator('button:has-text("Mobile"), [role="tab"]:has-text("Mobile")').first
                    desktop_button = page.locator('button:has-text("Desktop"), [role="tab"]:has-text("Desktop")').first
                    
                    mobile_visible = mobile_button.is_visible(timeout=1000)
                    desktop_visible = desktop_button.is_visible(timeout=1000)
                    
                    if mobile_visible or desktop_visible:
                        if DEBUG_MODE:
                            logger.debug(f"Mobile/Desktop buttons are visible (mobile: {mobile_visible}, desktop: {desktop_visible})")
                        return True
                    else:
                        if DEBUG_MODE:
                            logger.debug("Score elements found but mobile/desktop buttons not yet visible, continuing to poll...")
                except Exception as e:
                    if DEBUG_MODE:
                        logger.debug(f"Mobile/Desktop buttons not yet visible: {e}")
            
        except Exception as e:
            if DEBUG_MODE:
                logger.debug(f"Polling error: {e}")
        
        time.sleep(poll_interval)
    
    logger.warning(f"Analysis completion timeout after {timeout_seconds}s")
    
    if DEBUG_MODE or get_debug_mode():
        screenshot_path = _save_debug_screenshot(page, url, "analysis_timeout")
        html_path = _save_debug_html(page, url, "analysis_timeout")
        if screenshot_path:
            logger.info(f"Debug screenshot saved: {screenshot_path}")
        if html_path:
            logger.info(f"Debug HTML saved: {html_path}")
    
    return False


def _extract_score_from_element(page: Page, view_type: str, url: str, max_retries: int = 5, retry_delay: float = 1.0) -> Optional[int]:
    """
    Extract score from PageSpeed Insights page for given view type with enhanced reliability.
    
    Implements retry logic with delays to handle cases where score elements exist but are not yet populated.
    Validates that extracted scores are valid integers between 0-100.
    Uses multiple fallback selectors including text content parsing from gauge elements.
    
    Args:
        page: Playwright page object
        view_type: 'mobile' or 'desktop'
        url: URL being analyzed (for error reporting)
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
                    if DEBUG_MODE:
                        logger.debug(f"Selector {selector} found element but content is empty (attempt {attempt + 1}/{max_retries})")
                    continue
                
                score_text = score_text.replace('%', '').strip()
                
                try:
                    score = int(score_text)
                except ValueError:
                    if DEBUG_MODE:
                        logger.debug(f"Could not parse score text '{score_text}' as integer for selector {selector}")
                    continue
                
                if score < 0 or score > 100:
                    logger.warning(f"Invalid score {score} extracted for {view_type} (must be 0-100), selector: {selector}")
                    continue
                
                if DEBUG_MODE:
                    logger.debug(f"Successfully extracted {view_type} score: {score} using selector {selector} (attempt {attempt + 1}/{max_retries})")
                return score
                
            except Exception as e:
                if DEBUG_MODE:
                    logger.debug(f"Failed to extract score with selector {selector} (attempt {attempt + 1}/{max_retries}): {e}")
                continue
        
        if attempt < max_retries - 1:
            if DEBUG_MODE:
                logger.debug(f"No valid score found in attempt {attempt + 1}/{max_retries}, retrying after {retry_delay}s delay...")
            time.sleep(retry_delay)
    
    logger.warning(f"Failed to extract {view_type} score after {max_retries} attempts with all selectors")
    
    if DEBUG_MODE or get_debug_mode():
        screenshot_path = _save_debug_screenshot(page, url, f"score_extraction_failed_{view_type}")
        html_path = _save_debug_html(page, url, f"score_extraction_failed_{view_type}")
        if screenshot_path:
            logger.info(f"Debug screenshot saved: {screenshot_path}")
        if html_path:
            logger.info(f"Debug HTML saved: {html_path}")
    
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


def _run_analysis_once(url: str, timeout: int, force_retry: bool = False) -> Dict[str, Optional[int | str]]:
    """
    Internal function to run a single Playwright analysis attempt with circuit breaker protection,
    result caching, memory monitoring, resource blocking optimizations, and comprehensive error handling.
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
        last_successful_step = None
        
        if warm_start:
            logger.debug(f"Using warm Playwright instance for {url}")
        else:
            logger.debug(f"Cold start Playwright instance for {url}")
            if instance is None:
                instance = pool.create_instance()
        
        page = None
        page_load_start = None
        reload_tracker = PageReloadTracker()
        
        try:
            context = instance.context
            page = context.new_page()
            
            _setup_request_interception(page, instance)
            
            page.set_default_timeout(timeout * 1000)
            
            instance.warm_start = True
            
            if DEBUG_MODE:
                logger.debug(f"Navigating to PageSpeed Insights...")
            
            nav_start = time.time()
            page.goto('https://pagespeed.web.dev/', wait_until='domcontentloaded', timeout=30000)
            nav_time = time.time() - nav_start
            last_successful_step = "Navigated to PageSpeed Insights"
            
            if DEBUG_MODE:
                logger.debug(f"Page navigation took {nav_time:.2f}s")
                logger.debug(f"Entering URL: {url}")
            
            try:
                url_input = page.locator('input[type="url"], input[name="url"], input[placeholder*="URL"]').first
                url_input.fill(url)
                last_successful_step = "Entered URL in input field"
            except Exception as e:
                screenshot_path = None
                html_path = None
                if DEBUG_MODE or get_debug_mode():
                    screenshot_path = _save_debug_screenshot(page, url, "input_not_found")
                    html_path = _save_debug_html(page, url, "input_not_found")
                
                pool.return_instance(instance, success=False)
                error_msg = _create_enhanced_error_message(
                    f"Failed to find URL input field: {e}",
                    url,
                    page=page,
                    last_successful_step=last_successful_step,
                    screenshot_path=screenshot_path,
                    html_path=html_path
                )
                raise PlaywrightSelectorTimeoutError(error_msg)
            
            time.sleep(0.5)
            
            if DEBUG_MODE:
                logger.debug("Clicking analyze button...")
            
            page_load_start = time.time()
            button_clicked = _click_analyze_button(page, url, reload_tracker, timeout_ms=10000)
            if not button_clicked:
                pool.return_instance(instance, success=False)
                raise PlaywrightSelectorTimeoutError("Failed to click analyze button - all selectors failed")
            
            last_successful_step = "Clicked analyze button"
            
            if DEBUG_MODE:
                logger.debug("Waiting for analysis to complete...")
            
            analysis_completed = _wait_for_analysis_completion(page, url, reload_tracker, timeout_seconds=min(180, timeout))
            
            if not analysis_completed:
                elapsed = time.time() - analysis_start_time
                if elapsed >= timeout * 0.9:
                    screenshot_path = None
                    html_path = None
                    if DEBUG_MODE or get_debug_mode():
                        screenshot_path = _save_debug_screenshot(page, url, "analysis_timeout")
                        html_path = _save_debug_html(page, url, "analysis_timeout")
                    
                    pool.return_instance(instance, success=False)
                    error_msg = _create_enhanced_error_message(
                        f"Analysis exceeded {timeout} seconds timeout",
                        url,
                        page=page,
                        last_successful_step=last_successful_step,
                        screenshot_path=screenshot_path,
                        html_path=html_path
                    )
                    raise PlaywrightAnalysisTimeoutError(error_msg)
                
                screenshot_path = None
                html_path = None
                if DEBUG_MODE or get_debug_mode():
                    screenshot_path = _save_debug_screenshot(page, url, "completion_timeout")
                    html_path = _save_debug_html(page, url, "completion_timeout")
                
                pool.return_instance(instance, success=False)
                error_msg = _create_enhanced_error_message(
                    "Analysis did not complete - score elements not found",
                    url,
                    page=page,
                    last_successful_step=last_successful_step,
                    screenshot_path=screenshot_path,
                    html_path=html_path
                )
                raise PlaywrightSelectorTimeoutError(error_msg)
            
            last_successful_step = "Analysis completed successfully"
            page_load_time = time.time() - page_load_start if page_load_start else 0.0
            
            if _monitor_process_memory(instance, max_memory_mb=PlaywrightPool.MAX_MEMORY_MB):
                logger.warning(f"Playwright process exceeded memory limit ({PlaywrightPool.MAX_MEMORY_MB}MB)")
                pool.return_instance(instance, success=False)
                raise PlaywrightRunnerError("Playwright process exceeded memory limit")
            
            if DEBUG_MODE:
                logger.debug("Waiting for device buttons to be available...")
            
            buttons_found = _wait_for_device_buttons(page, url, reload_tracker, timeout_seconds=30)
            
            if not buttons_found:
                logger.warning("Device buttons not found within 30s, attempting score extraction anyway...")
            else:
                last_successful_step = "Device buttons loaded"
            
            time.sleep(2)
            
            if DEBUG_MODE:
                logger.debug("Extracting mobile score...")
            
            mobile_score = _extract_score_from_element(page, 'mobile', url)
            if mobile_score is not None:
                last_successful_step = f"Extracted mobile score: {mobile_score}"
            
            mobile_psi_url = _get_psi_report_url(page) if mobile_score and mobile_score < 80 else None
            
            if DEBUG_MODE:
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
                    if DEBUG_MODE:
                        logger.debug(f"Successfully switched to desktop view using selector: {selector}")
                    last_successful_step = "Switched to desktop view"
                    break
                except Exception as e:
                    if DEBUG_MODE:
                        logger.debug(f"Failed to switch to desktop with selector {selector}: {e}")
                    continue
            
            if desktop_switched:
                time.sleep(2)
                if DEBUG_MODE:
                    logger.debug("Extracting desktop score...")
                
                desktop_score = _extract_score_from_element(page, 'desktop', url)
                if desktop_score is not None:
                    last_successful_step = f"Extracted desktop score: {desktop_score}"
                
                desktop_psi_url = _get_psi_report_url(page) if desktop_score and desktop_score < 80 else None
            else:
                screenshot_path = None
                html_path = None
                if DEBUG_MODE or get_debug_mode():
                    screenshot_path = _save_debug_screenshot(page, url, "desktop_switch_failed")
                    html_path = _save_debug_html(page, url, "desktop_switch_failed")
                
                pool.return_instance(instance, success=False)
                error_msg = _create_enhanced_error_message(
                    "Failed to switch to desktop view with all selectors",
                    url,
                    page=page,
                    last_successful_step=last_successful_step,
                    screenshot_path=screenshot_path,
                    html_path=html_path
                )
                raise PlaywrightSelectorTimeoutError(error_msg)
            
            if mobile_score is None and desktop_score is None:
                screenshot_path = None
                html_path = None
                if DEBUG_MODE or get_debug_mode():
                    screenshot_path = _save_debug_screenshot(page, url, "no_scores_extracted")
                    html_path = _save_debug_html(page, url, "no_scores_extracted")
                
                pool.return_instance(instance, success=False)
                error_msg = _create_enhanced_error_message(
                    "Failed to extract any scores from PageSpeed Insights",
                    url,
                    page=page,
                    last_successful_step=last_successful_step,
                    screenshot_path=screenshot_path,
                    html_path=html_path
                )
                raise PlaywrightSelectorTimeoutError(error_msg)
            
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
            
        except (PlaywrightAnalysisTimeoutError, PlaywrightSelectorTimeoutError):
            if page:
                try:
                    page.close()
                except Exception:
                    pass
            pool.return_instance(instance, success=False)
            raise
            
        except Exception as e:
            screenshot_path = None
            html_path = None
            if page:
                if DEBUG_MODE or get_debug_mode():
                    screenshot_path = _save_debug_screenshot(page, url, "unexpected_error")
                    html_path = _save_debug_html(page, url, "unexpected_error")
                
                try:
                    page.close()
                except Exception:
                    pass
            
            pool.return_instance(instance, success=False)
            
            if isinstance(e, (PlaywrightRunnerError, PermanentError)):
                raise
            
            error_msg = _create_enhanced_error_message(
                f"Playwright execution failed: {e}",
                url,
                page=page,
                last_successful_step=last_successful_step,
                screenshot_path=screenshot_path,
                html_path=html_path
            )
            raise PlaywrightRunnerError(error_msg) from e
    
    if force_retry:
        if DEBUG_MODE:
            logger.debug(f"Force retry enabled - bypassing circuit breaker for {url}")
        try:
            return _execute_playwright()
        except Exception as e:
            if "Circuit breaker" in str(e) and "is OPEN" in str(e):
                logger.warning(f"Circuit breaker bypassed due to --force-retry flag")
                return _execute_playwright()
            raise
    else:
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
