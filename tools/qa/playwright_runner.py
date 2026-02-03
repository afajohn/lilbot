import time
import os
import threading
import traceback
import psutil
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
from queue import Queue, Empty

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
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
    POOL_SIZE = 2
    
    def __init__(self):
        self.instances = []
        self.lock = threading.Lock()
        self.logger = get_logger()
        self._shutdown = False
        self._playwright = None
    
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
        try:
            pw = self._get_playwright()
            browser = pw.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            browser_process = browser._impl_obj._connection._transport._proc if hasattr(browser, '_impl_obj') else None
            pid = browser_process.pid if browser_process else None
            
            instance = PlaywrightInstance(
                browser=browser,
                context=context,
                state=InstanceState.IDLE,
                memory_mb=0.0,
                last_used=time.time(),
                warm_start=False,
                failures=0,
                pid=pid
            )
            
            with self.lock:
                if len(self.instances) < self.POOL_SIZE:
                    self.instances.append(instance)
            
            return instance
        except Exception as e:
            raise PermanentError(f"Failed to create Playwright instance: {e}", original_exception=e)
    
    def cleanup_dead_instances(self):
        with self.lock:
            dead_instances = [i for i in self.instances if not i.is_alive() or i.state == InstanceState.DEAD]
            for instance in dead_instances:
                instance.kill()
                self.instances.remove(instance)
    
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


def _wait_for_analysis_completion(page: Page, timeout_seconds: int = 180) -> bool:
    """
    Smart polling to wait for PageSpeed Insights analysis to complete.
    
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
                return True
            
        except Exception as e:
            logger.debug(f"Polling error: {e}")
        
        time.sleep(poll_interval)
    
    return False


def _extract_score_from_element(page: Page, view_type: str) -> Optional[int]:
    """
    Extract score from PageSpeed Insights page for given view type.
    
    Args:
        page: Playwright page object
        view_type: 'mobile' or 'desktop'
        
    Returns:
        Score as integer (0-100) or None if not found
    """
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
    result caching, and memory monitoring.
    """
    circuit_breaker = _get_circuit_breaker()
    logger = get_logger()
    pool = _get_pool()
    
    def _execute_playwright():
        instance = pool.get_instance()
        warm_start = instance is not None and instance.warm_start
        
        if warm_start:
            logger.debug(f"Using warm Playwright instance for {url}")
        else:
            logger.debug(f"Cold start Playwright instance for {url}")
            if instance is None:
                instance = pool.create_instance()
        
        page = None
        try:
            context = instance.context
            page = context.new_page()
            
            page.set_default_timeout(timeout * 1000)
            
            instance.warm_start = True
            
            start_time = time.time()
            
            logger.debug(f"Navigating to PageSpeed Insights...")
            page.goto('https://pagespeed.web.dev/', wait_until='networkidle', timeout=30000)
            
            logger.debug(f"Entering URL: {url}")
            url_input = page.locator('input[type="url"], input[name="url"], input[placeholder*="URL"]').first
            url_input.fill(url)
            time.sleep(1)
            
            logger.debug("Clicking analyze button...")
            analyze_button = page.locator('button:has-text("Analyze"), button[type="submit"]').first
            analyze_button.click()
            
            logger.debug("Waiting for analysis to complete...")
            analysis_completed = _wait_for_analysis_completion(page, timeout_seconds=min(180, timeout))
            
            if not analysis_completed:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    pool.return_instance(instance, success=False)
                    raise PlaywrightTimeoutError(f"Analysis exceeded {timeout} seconds timeout")
                pool.return_instance(instance, success=False)
                raise PlaywrightRunnerError("Analysis did not complete - score elements not found")
            
            if _monitor_process_memory(instance, max_memory_mb=PlaywrightPool.MAX_MEMORY_MB):
                logger.warning(f"Playwright process exceeded memory limit ({PlaywrightPool.MAX_MEMORY_MB}MB)")
                pool.return_instance(instance, success=False)
                raise PlaywrightRunnerError("Playwright process exceeded memory limit")
            
            logger.debug("Extracting mobile score...")
            mobile_score = _extract_score_from_element(page, 'mobile')
            mobile_psi_url = _get_psi_report_url(page) if mobile_score and mobile_score < 80 else None
            
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
            
            if mobile_score is None and desktop_score is None:
                pool.return_instance(instance, success=False)
                raise PlaywrightRunnerError("Failed to extract any scores from PageSpeed Insights")
            
            page.close()
            pool.return_instance(instance, success=True)
            
            return {
                'mobile_score': mobile_score,
                'desktop_score': desktop_score,
                'mobile_psi_url': mobile_psi_url,
                'desktop_psi_url': desktop_psi_url,
                '_warm_start': warm_start
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
