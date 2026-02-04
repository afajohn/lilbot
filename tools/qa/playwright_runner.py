import time
import os
import threading
import traceback
import psutil
import asyncio
import sys
from typing import Dict, Optional, Set, List, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from datetime import datetime
from concurrent.futures import Future
from collections import defaultdict

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, Route, Request, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightTimeoutError = Exception

from tools.utils.exceptions import RetryableError, PermanentError
from tools.utils.logger import get_logger


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


def _get_thread_info() -> str:
    """Get current thread ID and name for logging"""
    thread = threading.current_thread()
    return f"[Thread-{thread.ident}:{thread.name}]"


def _log_thread_operation(logger, operation: str, details: str = ""):
    """Log an operation with thread information"""
    thread_info = _get_thread_info()
    msg = f"{thread_info} {operation}"
    if details:
        msg += f" - {details}"
    logger.debug(msg)


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


async def _save_debug_screenshot(page: Page, url: str, reason: str = "error") -> Optional[str]:
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
        
        await page.screenshot(path=filepath, full_page=True)
        return filepath
    except Exception as e:
        logger = get_logger()
        logger.debug(f"Failed to save screenshot: {e}")
        return None


async def _save_debug_html(page: Page, url: str, reason: str = "error") -> Optional[str]:
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
        
        html_content = await page.content()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return filepath
    except Exception as e:
        logger = get_logger()
        logger.debug(f"Failed to save HTML: {e}")
        return None


async def _get_page_info(page: Page) -> Dict[str, any]:
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
        info['title'] = await page.title()
    except Exception:
        pass
    
    try:
        buttons = await page.locator('button').all()
        for btn in buttons[:10]:
            try:
                is_visible = await btn.is_visible()
                text = await btn.inner_text() if is_visible else '[hidden]'
                info['buttons'].append({
                    'text': text[:50],
                    'visible': is_visible
                })
            except Exception:
                pass
    except Exception:
        pass
    
    try:
        inputs = await page.locator('input').all()
        for inp in inputs[:10]:
            try:
                is_visible = await inp.is_visible()
                inp_type = await inp.get_attribute('type')
                placeholder = await inp.get_attribute('placeholder')
                info['inputs'].append({
                    'type': inp_type,
                    'placeholder': placeholder,
                    'visible': is_visible
                })
            except Exception:
                pass
    except Exception:
        pass
    
    try:
        links = await page.locator('a').all()
        for link in links[:10]:
            try:
                is_visible = await link.is_visible()
                text = await link.inner_text() if is_visible else '[hidden]'
                href = await link.get_attribute('href')
                info['links'].append({
                    'text': text[:50],
                    'href': href,
                    'visible': is_visible
                })
            except Exception:
                pass
    except Exception:
        pass
    
    return info


async def _create_enhanced_error_message(
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
        page_info = await _get_page_info(page)
        
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
class ThreadingMetrics:
    """Track threading-related metrics and issues"""
    greenlet_errors: int = 0
    thread_conflicts: int = 0
    event_loop_failures: int = 0
    browser_context_creation_threads: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    page_creation_threads: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    async_operation_threads: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    lock = threading.Lock()
    
    def record_greenlet_error(self):
        """Record a greenlet-related error"""
        with self.lock:
            self.greenlet_errors += 1
    
    def record_thread_conflict(self):
        """Record a thread conflict"""
        with self.lock:
            self.thread_conflicts += 1
    
    def record_event_loop_failure(self):
        """Record an event loop failure"""
        with self.lock:
            self.event_loop_failures += 1
    
    def record_context_creation(self, thread_id: int):
        """Record browser context creation on a thread"""
        with self.lock:
            self.browser_context_creation_threads[thread_id] += 1
    
    def record_page_creation(self, thread_id: int):
        """Record page creation on a thread"""
        with self.lock:
            self.page_creation_threads[thread_id] += 1
    
    def record_async_operation(self, thread_id: int):
        """Record async operation on a thread"""
        with self.lock:
            self.async_operation_threads[thread_id] += 1
    
    def get_metrics(self) -> Dict:
        """Get all threading metrics"""
        with self.lock:
            return {
                'greenlet_errors': self.greenlet_errors,
                'thread_conflicts': self.thread_conflicts,
                'event_loop_failures': self.event_loop_failures,
                'context_creation_by_thread': dict(self.browser_context_creation_threads),
                'page_creation_by_thread': dict(self.page_creation_threads),
                'async_operations_by_thread': dict(self.async_operation_threads)
            }
    
    def reset(self):
        """Reset all metrics"""
        with self.lock:
            self.greenlet_errors = 0
            self.thread_conflicts = 0
            self.event_loop_failures = 0
            self.browser_context_creation_threads.clear()
            self.page_creation_threads.clear()
            self.async_operation_threads.clear()


_threading_metrics = ThreadingMetrics()


def get_threading_metrics() -> Dict:
    """Get current threading metrics"""
    return _threading_metrics.get_metrics()


def reset_threading_metrics():
    """Reset threading metrics"""
    _threading_metrics.reset()


@dataclass
class EventLoopHealth:
    """Track event loop health status"""
    last_heartbeat: float = 0.0
    heartbeat_failures: int = 0
    is_responsive: bool = True
    thread_id: Optional[int] = None
    lock = threading.Lock()
    
    def update_heartbeat(self):
        """Update last heartbeat timestamp"""
        with self.lock:
            self.last_heartbeat = time.time()
            self.is_responsive = True
            self.heartbeat_failures = 0
    
    def record_failure(self):
        """Record a heartbeat failure"""
        with self.lock:
            self.heartbeat_failures += 1
            if self.heartbeat_failures >= 3:
                self.is_responsive = False
    
    def check_health(self, timeout_seconds: float = 30.0) -> Tuple[bool, str]:
        """
        Check if event loop is healthy
        
        Returns:
            Tuple of (is_healthy, status_message)
        """
        with self.lock:
            if self.last_heartbeat == 0.0:
                return True, "Event loop not yet initialized"
            
            time_since_heartbeat = time.time() - self.last_heartbeat
            
            if time_since_heartbeat > timeout_seconds:
                return False, f"Event loop unresponsive for {time_since_heartbeat:.1f}s"
            
            if not self.is_responsive:
                return False, f"Event loop marked as unresponsive after {self.heartbeat_failures} failures"
            
            return True, f"Healthy (last heartbeat {time_since_heartbeat:.1f}s ago)"
    
    def get_status(self) -> Dict:
        """Get detailed health status"""
        with self.lock:
            time_since_heartbeat = time.time() - self.last_heartbeat if self.last_heartbeat > 0.0 else None
            return {
                'last_heartbeat': self.last_heartbeat,
                'time_since_heartbeat': time_since_heartbeat,
                'heartbeat_failures': self.heartbeat_failures,
                'is_responsive': self.is_responsive,
                'thread_id': self.thread_id
            }


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
    analyses_since_refresh: int = 0
    context_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
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
        self.analyses_since_refresh += 1
    
    def get_avg_page_load_time(self) -> float:
        if self.total_analyses == 0:
            return 0.0
        return self.total_page_load_time / self.total_analyses
    
    def should_refresh(self, refresh_interval: int) -> bool:
        return refresh_interval > 0 and self.analyses_since_refresh >= refresh_interval
    
    async def kill(self):
        if self.browser and self.is_alive():
            try:
                if self.context:
                    await self.context.close()
                await self.browser.close()
            except Exception:
                pass
        self.state = InstanceState.DEAD


@dataclass
class AnalysisRequest:
    """Request to analyze a URL"""
    url: str
    timeout: int
    force_retry: bool
    force_fresh_instance: bool
    future: Future


@dataclass
class BatchAnalysisRequest:
    """Request to analyze multiple URLs in parallel"""
    urls: List[str]
    timeout: int
    force_retry: bool
    concurrency: int
    future: Future


class PlaywrightEventLoopThread:
    """Dedicated thread for running Playwright with its own event loop"""
    
    def __init__(self, refresh_interval: int = 10, max_concurrent_contexts: int = 3):
        self.thread = None
        self.loop = None
        self.request_queue: Queue[Optional[AnalysisRequest | BatchAnalysisRequest]] = Queue()
        self._shutdown = False
        self.logger = get_logger()
        self._playwright: Optional[Playwright] = None
        self._pool: Optional['PlaywrightPool'] = None
        self._health = EventLoopHealth()
        self._heartbeat_task = None
        self.refresh_interval = refresh_interval
        self.max_concurrent_contexts = max_concurrent_contexts
        
    def start(self):
        """Start the event loop thread"""
        if self.thread is None or not self.thread.is_alive():
            self._shutdown = False
            self.thread = threading.Thread(target=self._run_event_loop, daemon=True, name="PlaywrightEventLoop")
            self.thread.start()
            _log_thread_operation(self.logger, "Starting Playwright event loop thread", f"Thread ID: {self.thread.ident}")
            time.sleep(0.5)
    
    def _run_event_loop(self):
        """Run the event loop in a dedicated thread"""
        thread_id = threading.current_thread().ident
        _log_thread_operation(self.logger, "Event loop thread started", f"Thread ID: {thread_id}")
        
        self._health.thread_id = thread_id
        
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            _log_thread_operation(self.logger, "Event loop created", f"Loop ID: {id(self.loop)}")
            
            self.loop.run_until_complete(self._process_requests())
        except Exception as e:
            self.logger.error(f"{_get_thread_info()} Event loop thread error: {e}", exc_info=True)
            _threading_metrics.record_event_loop_failure()
        finally:
            _log_thread_operation(self.logger, "Event loop shutting down")
            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
            
            if self._pool:
                try:
                    self.loop.run_until_complete(self._pool.shutdown())
                except Exception as e:
                    self.logger.error(f"{_get_thread_info()} Error shutting down pool: {e}")
            
            if self._playwright:
                try:
                    self.loop.run_until_complete(self._playwright.stop())
                except Exception as e:
                    self.logger.error(f"{_get_thread_info()} Error stopping playwright: {e}")
            
            try:
                self.loop.close()
                _log_thread_operation(self.logger, "Event loop closed")
            except Exception as e:
                self.logger.error(f"{_get_thread_info()} Error closing loop: {e}")
    
    async def _heartbeat(self):
        """Send periodic heartbeat to track event loop health"""
        while not self._shutdown:
            try:
                self._health.update_heartbeat()
                _log_thread_operation(self.logger, "Event loop heartbeat", f"Thread ID: {threading.current_thread().ident}")
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"{_get_thread_info()} Heartbeat error: {e}")
                self._health.record_failure()
                _threading_metrics.record_event_loop_failure()
    
    async def _process_requests(self):
        """Process incoming analysis requests"""
        _log_thread_operation(self.logger, "Starting request processing", f"Loop: {id(self.loop)}")
        
        self._heartbeat_task = asyncio.create_task(self._heartbeat())
        
        while not self._shutdown:
            try:
                request = self.request_queue.get(timeout=0.1)
                
                if request is None:
                    _log_thread_operation(self.logger, "Received shutdown signal")
                    break
                
                _log_thread_operation(self.logger, f"Processing analysis request", f"URL: {request.url}")
                _threading_metrics.record_async_operation(threading.current_thread().ident)
                
                try:
                    if self._pool is None:
                        _log_thread_operation(self.logger, "Initializing Playwright pool")
                        self._pool = PlaywrightPool(self.loop, self.logger, self.refresh_interval, self.max_concurrent_contexts)
                        await self._pool.initialize()
                    
                    is_healthy, status = self._health.check_health()
                    if not is_healthy:
                        self.logger.warning(f"{_get_thread_info()} Event loop health check failed: {status}")
                        _threading_metrics.record_event_loop_failure()
                    
                    if isinstance(request, BatchAnalysisRequest):
                        _log_thread_operation(self.logger, f"Processing batch analysis request", f"URLs: {len(request.urls)}, Concurrency: {request.concurrency}")
                        result = await _run_analysis_batch_async(
                            request.urls,
                            request.timeout,
                            request.force_retry,
                            request.concurrency,
                            self._pool
                        )
                        request.future.set_result(result)
                        _log_thread_operation(self.logger, "Batch analysis completed successfully", f"URLs: {len(request.urls)}")
                    else:
                        _log_thread_operation(self.logger, f"Processing analysis request", f"URL: {request.url}")
                        result = await _run_analysis_once_async(
                            request.url,
                            request.timeout,
                            request.force_retry,
                            request.force_fresh_instance,
                            self._pool
                        )
                        request.future.set_result(result)
                        _log_thread_operation(self.logger, "Analysis completed successfully", f"URL: {request.url}")
                except Exception as e:
                    error_type = type(e).__name__
                    url_info = f"URL: {request.url}" if hasattr(request, 'url') else f"URLs: {len(request.urls)}"
                    _log_thread_operation(self.logger, f"Analysis failed with {error_type}", f"{url_info}, Error: {e}")
                    
                    if 'greenlet' in str(e).lower():
                        _threading_metrics.record_greenlet_error()
                        self.logger.error(f"{_get_thread_info()} Greenlet error detected: {e}", exc_info=True)
                    
                    request.future.set_exception(e)
                    
            except Empty:
                continue
            except Exception as e:
                self.logger.error(f"{_get_thread_info()} Error processing request: {e}", exc_info=True)
                _threading_metrics.record_event_loop_failure()
        
        _log_thread_operation(self.logger, "Request processing ended")
    
    def submit_analysis(self, url: str, timeout: int, force_retry: bool, force_fresh_instance: bool = False) -> Future:
        """Submit an analysis request and return a Future"""
        caller_thread_info = _get_thread_info()
        _log_thread_operation(self.logger, f"Submitting analysis request from {caller_thread_info}", f"URL: {url}")
        
        future = Future()
        request = AnalysisRequest(
            url=url,
            timeout=timeout,
            force_retry=force_retry,
            force_fresh_instance=force_fresh_instance,
            future=future
        )
        self.request_queue.put(request)
        return future
    
    def submit_batch_analysis(self, urls: List[str], timeout: int, force_retry: bool, concurrency: int = 2) -> Future:
        """Submit a batch analysis request and return a Future"""
        caller_thread_info = _get_thread_info()
        _log_thread_operation(self.logger, f"Submitting batch analysis request from {caller_thread_info}", f"URLs: {len(urls)}, Concurrency: {concurrency}")
        
        future = Future()
        request = BatchAnalysisRequest(
            urls=urls,
            timeout=timeout,
            force_retry=force_retry,
            concurrency=concurrency,
            future=future
        )
        self.request_queue.put(request)
        return future
    
    def get_health_status(self) -> Dict:
        """Get event loop health status"""
        return self._health.get_status()
    
    def check_and_recover(self) -> bool:
        """
        Check event loop health and attempt recovery if needed
        
        Returns:
            True if healthy or recovery successful, False if recovery failed
        """
        is_healthy, status = self._health.check_health()
        
        if not is_healthy:
            self.logger.error(f"{_get_thread_info()} Event loop unhealthy: {status}")
            _threading_metrics.record_event_loop_failure()
            
            if not self.thread or not self.thread.is_alive():
                self.logger.warning(f"{_get_thread_info()} Event loop thread is dead, attempting restart...")
                try:
                    self.start()
                    time.sleep(1.0)
                    
                    if self.thread and self.thread.is_alive():
                        self.logger.info(f"{_get_thread_info()} Event loop thread restarted successfully")
                        return True
                    else:
                        self.logger.error(f"{_get_thread_info()} Failed to restart event loop thread")
                        return False
                except Exception as e:
                    self.logger.error(f"{_get_thread_info()} Error restarting event loop thread: {e}", exc_info=True)
                    return False
            
            return False
        
        return True
    
    def shutdown(self):
        """Shutdown the event loop thread"""
        _log_thread_operation(self.logger, "Initiating event loop shutdown")
        self._shutdown = True
        self.request_queue.put(None)
        if self.thread:
            self.thread.join(timeout=5.0)
            _log_thread_operation(self.logger, "Event loop thread joined")


class PlaywrightPool:
    MAX_MEMORY_MB = 1024
    
    def __init__(self, loop: asyncio.AbstractEventLoop, logger, refresh_interval: int = 10, max_concurrent_contexts: int = 3):
        self.contexts: List[PlaywrightInstance] = []
        self.lock = asyncio.Lock()
        self.logger = logger
        self._shutdown = False
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._total_warm_starts = 0
        self._total_cold_starts = 0
        self._total_startup_time = 0.0
        self.loop = loop
        self.refresh_interval = refresh_interval
        self._total_refreshes = 0
        self.max_concurrent_contexts = max_concurrent_contexts
        self._semaphore = asyncio.Semaphore(max_concurrent_contexts)
    
    async def initialize(self):
        """Initialize the Playwright instance"""
        _log_thread_operation(self.logger, "Initializing Playwright pool")
        
        if not PLAYWRIGHT_AVAILABLE:
            raise PermanentError(
                "Playwright is not installed. Install it with: pip install playwright && playwright install chromium"
            )
        
        if self._playwright is None:
            _log_thread_operation(self.logger, "Starting Playwright instance")
            self._playwright = await async_playwright().start()
            _log_thread_operation(self.logger, "Playwright instance started", f"Instance ID: {id(self._playwright)}")
        
        if self._browser is None:
            _log_thread_operation(self.logger, "Launching shared browser")
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
            
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=launch_args
            )
            _log_thread_operation(self.logger, "Shared browser launched", f"Browser ID: {id(self._browser)}")
    
    async def get_instance(self) -> Optional[PlaywrightInstance]:
        """Get an available context instance or None if all are busy"""
        _log_thread_operation(self.logger, "Getting Playwright instance")
        
        async with self.lock:
            for instance in self.contexts:
                if instance.state == InstanceState.IDLE and instance.is_alive():
                    mem = instance.get_memory_usage()
                    if mem < self.MAX_MEMORY_MB:
                        instance.state = InstanceState.BUSY
                        instance.last_used = time.time()
                        self._total_warm_starts += 1
                        _log_thread_operation(self.logger, "Using warm instance", f"Memory: {mem:.1f}MB")
                        return instance
                    else:
                        self.logger.info(f"{_get_thread_info()} Killing instance due to high memory: {mem:.1f}MB")
                        self.contexts.remove(instance)
                        await instance.kill()
        
        _log_thread_operation(self.logger, "No instance available, will create new one")
        return None
    
    async def return_instance(self, instance: PlaywrightInstance, success: bool = True):
        """Return an instance to the pool"""
        _log_thread_operation(self.logger, "Returning instance", f"Success: {success}")
        
        async with self.lock:
            if not success:
                instance.failures += 1
                _log_thread_operation(self.logger, "Instance failure recorded", f"Total failures: {instance.failures}")
            
            mem = instance.get_memory_usage()
            if instance.failures >= 3 or mem >= self.MAX_MEMORY_MB or not instance.is_alive():
                _log_thread_operation(self.logger, "Killing instance", f"Failures: {instance.failures}, Memory: {mem:.1f}MB, Alive: {instance.is_alive()}")
                if instance in self.contexts:
                    self.contexts.remove(instance)
                await instance.kill()
                return
            
            instance.state = InstanceState.IDLE
            _log_thread_operation(self.logger, "Instance returned")
    
    async def create_instance(self) -> PlaywrightInstance:
        """Create a new browser context instance"""
        startup_start = time.time()
        logger = self.logger
        thread_id = threading.current_thread().ident
        
        _log_thread_operation(logger, "Creating new Playwright context instance")
        
        try:
            if self._browser is None:
                await self.initialize()
            
            _log_thread_operation(logger, "Creating browser context")
            _threading_metrics.record_context_creation(thread_id)
            
            context = await self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                java_script_enabled=True,
                bypass_csp=True,
                ignore_https_errors=True
            )
            _log_thread_operation(logger, "Browser context created", f"Context ID: {id(context)}")
            
            browser_process = self._browser._impl_obj._connection._transport._proc if hasattr(self._browser, '_impl_obj') else None
            pid = browser_process.pid if browser_process else None
            
            startup_time = time.time() - startup_start
            
            instance = PlaywrightInstance(
                browser=self._browser,
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
            
            async with self.lock:
                self.contexts.append(instance)
                self._total_cold_starts += 1
                self._total_startup_time += startup_time
            
            logger.info(f"{_get_thread_info()} Created new Playwright context instance (PID: {pid}, startup time: {startup_time:.2f}s)")
            return instance
        except Exception as e:
            logger.error(f"{_get_thread_info()} Failed to create Playwright context instance: {e}", exc_info=True)
            if 'greenlet' in str(e).lower():
                _threading_metrics.record_greenlet_error()
            raise PermanentError(f"Failed to create Playwright context instance: {e}", original_exception=e)
    
    async def force_refresh_instance(self, instance: PlaywrightInstance) -> PlaywrightInstance:
        """
        Force refresh a browser context instance by closing and recreating the context.
        
        Args:
            instance: The PlaywrightInstance to refresh
            
        Returns:
            A new PlaywrightInstance with fresh browser context
        """
        old_analyses_count = instance.analyses_since_refresh
        
        _log_thread_operation(self.logger, "Force refreshing Playwright context instance", f"Analyses since last refresh: {old_analyses_count}")
        
        async with self.lock:
            if instance in self.contexts:
                self.contexts.remove(instance)
        
        try:
            if instance.context:
                await instance.context.close()
        except Exception as e:
            self.logger.debug(f"Error closing context during refresh: {e}")
        
        new_instance = await self.create_instance()
        
        async with self.lock:
            self._total_refreshes += 1
        
        self.logger.info(f"{_get_thread_info()} Browser context instance refreshed - Analyses completed: {old_analyses_count}, Total refreshes: {self._total_refreshes}")
        
        return new_instance
    
    async def cleanup_dead_instances(self):
        """Clean up any dead instances"""
        async with self.lock:
            dead_instances = [inst for inst in self.contexts if not inst.is_alive() or inst.state == InstanceState.DEAD]
            for instance in dead_instances:
                self.contexts.remove(instance)
                try:
                    if instance.context:
                        await instance.context.close()
                except Exception:
                    pass
    
    async def get_pool_stats(self) -> Dict:
        """Get pool statistics"""
        async with self.lock:
            instances = [
                {
                    'context_id': id(inst.context),
                    'state': inst.state.value,
                    'memory_mb': inst.get_memory_usage(),
                    'total_analyses': inst.total_analyses,
                    'analyses_since_refresh': inst.analyses_since_refresh,
                    'avg_page_load_time': inst.get_avg_page_load_time(),
                    'failures': inst.failures,
                    'blocking_stats': {
                        'total_requests': inst.blocking_stats.total_requests,
                        'blocked_requests': inst.blocking_stats.blocked_requests,
                        'blocking_ratio': inst.blocking_stats.get_blocking_ratio()
                    }
                }
                for inst in self.contexts
            ]
            
            idle_count = sum(1 for inst in self.contexts if inst.state == InstanceState.IDLE)
            busy_count = sum(1 for inst in self.contexts if inst.state == InstanceState.BUSY)
            
            return {
                'mode': 'multi-context',
                'max_concurrent_contexts': self.max_concurrent_contexts,
                'total_contexts': len(self.contexts),
                'idle_contexts': idle_count,
                'busy_contexts': busy_count,
                'total_warm_starts': self._total_warm_starts,
                'total_cold_starts': self._total_cold_starts,
                'total_refreshes': self._total_refreshes,
                'refresh_interval': self.refresh_interval,
                'refresh_enabled': self.refresh_interval > 0,
                'avg_startup_time': self._total_startup_time / self._total_cold_starts if self._total_cold_starts > 0 else 0.0,
                'contexts': instances
            }
    
    async def shutdown(self):
        """Shutdown the pool"""
        self._shutdown = True
        async with self.lock:
            for instance in self.contexts:
                try:
                    if instance.context:
                        await instance.context.close()
                except Exception:
                    pass
            self.contexts.clear()
            
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
    
    async def drain_pool(self):
        """
        Explicitly shutdown and recreate all browser contexts.
        Useful for forcing a clean state or recovering from errors.
        """
        _log_thread_operation(self.logger, "Draining pool - shutting down and recreating contexts")
        
        async with self.lock:
            for instance in self.contexts:
                try:
                    if instance.context:
                        await instance.context.close()
                except Exception:
                    pass
            self.contexts.clear()
        
        _log_thread_operation(self.logger, "Pool drained")


_event_loop_thread = None
_event_loop_thread_lock = threading.Lock()
_refresh_interval = 10
_max_concurrent_contexts = 3


def set_refresh_interval(interval: int):
    """Set the global refresh interval for browser instances"""
    global _refresh_interval
    _refresh_interval = interval


def get_refresh_interval() -> int:
    """Get the current refresh interval"""
    return _refresh_interval


def set_max_concurrent_contexts(max_contexts: int):
    """Set the maximum number of concurrent browser contexts"""
    global _max_concurrent_contexts
    _max_concurrent_contexts = max(1, min(max_contexts, 5))


def get_max_concurrent_contexts() -> int:
    """Get the maximum number of concurrent browser contexts"""
    return _max_concurrent_contexts


def _get_event_loop_thread() -> PlaywrightEventLoopThread:
    global _event_loop_thread
    with _event_loop_thread_lock:
        if _event_loop_thread is None:
            _event_loop_thread = PlaywrightEventLoopThread(_refresh_interval, _max_concurrent_contexts)
            _event_loop_thread.start()
        return _event_loop_thread





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


async def _setup_request_interception(page: Page, instance: PlaywrightInstance) -> None:
    """
    Set up request interception to block unnecessary resources.
    
    Args:
        page: Playwright page object
        instance: PlaywrightInstance to track blocking stats
    """
    async def handle_route(route: Route):
        request = route.request
        url = request.url
        resource_type = request.resource_type
        
        instance.blocking_stats.record_request()
        
        if should_block_resource(url, resource_type):
            is_pattern_block = any(pattern in url.lower() for pattern in BLOCKED_URL_PATTERNS)
            instance.blocking_stats.record_blocked(resource_type, is_pattern_block)
            await route.abort()
        else:
            await route.continue_()
    
    if instance.request_blocking_enabled:
        await page.route('**/*', handle_route)


def run_analysis(url: str, timeout: int = 600, skip_cache: bool = False, force_retry: bool = False, force_fresh_instance: bool = False) -> Dict[str, Optional[int | str]]:
    """
    Run Playwright analysis for a given URL to get PageSpeed Insights scores.
    Implements persistent retry-until-success with exponential backoff for transient errors.
    
    Args:
        url: The URL to analyze
        timeout: Maximum time in seconds for overall operation (default: 600)
        skip_cache: If True, bypass cache and force fresh analysis (default: False)
        force_retry: If True, bypass circuit breaker during critical runs (default: False)
        force_fresh_instance: If True, force use of a fresh browser instance (default: False)
        
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
    logger = get_logger()
    _log_thread_operation(logger, f"run_analysis called for {url}")
    
    if not PLAYWRIGHT_AVAILABLE:
        raise PermanentError(
            "Playwright is not installed. Install it with: pip install playwright && playwright install chromium"
        )
    
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
            progressive_timeout.record_failure()
            raise PlaywrightAnalysisTimeoutError(f"Analysis exceeded overall timeout of {timeout}s")
        
        try:
            event_loop_thread = _get_event_loop_thread()
            
            if not event_loop_thread.check_and_recover():
                logger.warning(f"{_get_thread_info()} Event loop health check failed for {url}, retrying...")
                was_retried = True
                time.sleep(current_backoff)
                current_backoff = min(current_backoff * 2, max_backoff)
                continue
            
            _log_thread_operation(logger, f"Submitting analysis to event loop thread", f"URL: {url}, Attempt: {attempt}")
            
            future = event_loop_thread.submit_analysis(url, timeout, force_retry, force_fresh_instance)
            result = future.result(timeout=timeout)
            
            _log_thread_operation(logger, f"Analysis completed successfully", f"URL: {url}")
            
            progressive_timeout.record_success()
            
            result['_from_cache'] = False
            return result
            
        except PermanentError:
            progressive_timeout.record_failure()
            raise
            
        except PlaywrightAnalysisTimeoutError:
            progressive_timeout.record_failure()
            raise
            
        except PlaywrightSelectorTimeoutError as e:
            last_exception = e
            was_retried = True
            progressive_timeout.record_failure()
            
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
            error_str = str(e).lower()
            
            if 'greenlet' in error_str or 'gr_frame' in error_str:
                _threading_metrics.record_greenlet_error()
                logger.error(
                    f"{_get_thread_info()} Greenlet error detected in run_analysis",
                    extra={
                        'url': url,
                        'attempt': attempt,
                        'error': str(e)
                    },
                    exc_info=True
                )
            
            if 'thread' in error_str and 'conflict' in error_str:
                _threading_metrics.record_thread_conflict()
                logger.error(
                    f"{_get_thread_info()} Thread conflict detected in run_analysis",
                    extra={
                        'url': url,
                        'attempt': attempt,
                        'error': str(e)
                    },
                    exc_info=True
                )
            
            logger.warning(
                f"{_get_thread_info()} Retryable error for {url}, retrying (attempt {attempt})",
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


async def run_analysis_batch(urls: List[str], concurrency: int = 2, timeout: int = 600, skip_cache: bool = False, force_retry: bool = False) -> List[Dict[str, Optional[int | str]]]:
    """
    Run Playwright analysis for multiple URLs in parallel with bounded concurrency.
    
    Args:
        urls: List of URLs to analyze
        concurrency: Maximum number of concurrent analyses (default: 2)
        timeout: Maximum time in seconds for each URL analysis (default: 600)
        skip_cache: If True, bypass cache and force fresh analysis (default: False)
        force_retry: If True, bypass circuit breaker during critical runs (default: False)
        
    Returns:
        List of result dictionaries (one per URL), with errors represented as exceptions
        
    Note:
        This function uses asyncio.gather with return_exceptions=True, so failed
        analyses will return exception objects in the results list.
    """
    logger = get_logger()
    _log_thread_operation(logger, f"run_analysis_batch called for {len(urls)} URLs with concurrency {concurrency}")
    
    if not PLAYWRIGHT_AVAILABLE:
        raise PermanentError(
            "Playwright is not installed. Install it with: pip install playwright && playwright install chromium"
        )
    
    event_loop_thread = _get_event_loop_thread()
    
    if not event_loop_thread.check_and_recover():
        raise PlaywrightRunnerError("Event loop health check failed")
    
    _log_thread_operation(logger, f"Submitting batch analysis to event loop thread", f"URLs: {len(urls)}, Concurrency: {concurrency}")
    
    future = event_loop_thread.submit_batch_analysis(urls, timeout, force_retry, concurrency)
    results = future.result(timeout=timeout * len(urls))
    
    _log_thread_operation(logger, f"Batch analysis completed", f"URLs: {len(urls)}")
    
    return results


async def _run_analysis_batch_async(urls: List[str], timeout: int, force_retry: bool, concurrency: int, pool: PlaywrightPool) -> List[Dict[str, Optional[int | str]]]:
    """
    Internal async function to run batch analysis with bounded concurrency.
    
    Args:
        urls: List of URLs to analyze
        timeout: Maximum time in seconds for each URL analysis
        force_retry: If True, bypass circuit breaker
        concurrency: Maximum number of concurrent analyses
        pool: PlaywrightPool instance
        
    Returns:
        List of result dictionaries or exceptions
    """
    logger = get_logger()
    _log_thread_operation(logger, f"Starting batch analysis for {len(urls)} URLs with concurrency {concurrency}")
    
    semaphore = asyncio.Semaphore(concurrency)
    
    async def analyze_with_semaphore(url: str):
        async with semaphore:
            try:
                _log_thread_operation(logger, f"Starting analysis", f"URL: {url}")
                result = await _run_analysis_once_async(url, timeout, force_retry, False, pool)
                _log_thread_operation(logger, f"Completed analysis", f"URL: {url}")
                return result
            except Exception as e:
                _log_thread_operation(logger, f"Analysis failed", f"URL: {url}, Error: {type(e).__name__}")
                return e
    
    results = await asyncio.gather(*[analyze_with_semaphore(url) for url in urls], return_exceptions=True)
    
    _log_thread_operation(logger, f"Batch analysis complete", f"URLs: {len(urls)}, Success: {sum(1 for r in results if not isinstance(r, Exception))}")
    
    return results


def _monitor_process_memory(instance: PlaywrightInstance, max_memory_mb: float = 1024) -> bool:
    memory_mb = instance.get_memory_usage()
    return memory_mb >= max_memory_mb


async def _cleanup_browser_context(instance: PlaywrightInstance) -> Tuple[float, float]:
    """
    Clean up browser context after analysis to free memory and remove state.
    Clears cookies, localStorage, sessionStorage, and cache.
    
    Args:
        instance: PlaywrightInstance to clean up
        
    Returns:
        Tuple of (memory_before_mb, memory_after_mb)
    """
    logger = get_logger()
    
    memory_before = instance.get_memory_usage()
    
    try:
        context = instance.context
        if context is None:
            logger.debug(f"{_get_thread_info()} No context to clean up for instance PID {instance.pid}")
            return memory_before, memory_before
        
        _log_thread_operation(logger, f"Cleaning up browser context", f"PID: {instance.pid}, Memory before: {memory_before:.1f}MB")
        
        await context.clear_cookies()
        
        pages = context.pages
        for page in pages:
            try:
                await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            except Exception as e:
                if DEBUG_MODE:
                    logger.debug(f"Failed to clear storage for page: {e}")
        
        await asyncio.sleep(0.5)
        
        memory_after = instance.get_memory_usage()
        memory_saved = memory_before - memory_after
        
        _log_thread_operation(
            logger, 
            f"Browser context cleanup completed", 
            f"PID: {instance.pid}, Memory after: {memory_after:.1f}MB, Saved: {memory_saved:.1f}MB"
        )
        
        return memory_before, memory_after
        
    except Exception as e:
        logger.error(f"{_get_thread_info()} Error during browser context cleanup for PID {instance.pid}: {e}")
        memory_after = instance.get_memory_usage()
        return memory_before, memory_after


async def _reload_page_with_retry(page: Page, url: str, reload_tracker: PageReloadTracker, logger) -> bool:
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
        await page.reload(wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(2)
        return True
    except Exception as e:
        logger.error(f"Page reload failed: {e}")
        return False


async def _click_analyze_button(page: Page, url: str, reload_tracker: PageReloadTracker, timeout_ms: int = 10000) -> bool:
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
                await button.click(timeout=timeout_ms)
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
                screenshot_path = await _save_debug_screenshot(page, url, "button_not_found")
                html_path = await _save_debug_html(page, url, "button_not_found")
            
            if not await _reload_page_with_retry(page, url, reload_tracker, logger):
                error_msg = await _create_enhanced_error_message(
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
        screenshot_path = await _save_debug_screenshot(page, url, "button_not_found_final")
        html_path = await _save_debug_html(page, url, "button_not_found_final")
    
    error_msg = await _create_enhanced_error_message(
        f"Failed to click analyze button after {max_attempts} attempts - all selectors failed",
        url,
        page=page,
        last_successful_step="Navigated to PageSpeed Insights and entered URL",
        screenshot_path=screenshot_path,
        html_path=html_path
    )
    raise PlaywrightSelectorTimeoutError(error_msg)


async def _wait_for_device_buttons(page: Page, url: str, reload_tracker: PageReloadTracker, timeout_seconds: int = 30) -> bool:
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
                if await button.is_visible(timeout=500):
                    if DEBUG_MODE:
                        logger.debug(f"Found device button using selector: {selector}")
                    return True
            except Exception:
                continue
        
        await asyncio.sleep(poll_interval)
    
    logger.warning(f"Device buttons not found within {timeout_seconds}s timeout")
    
    if DEBUG_MODE or get_debug_mode():
        screenshot_path = await _save_debug_screenshot(page, url, "device_buttons_timeout")
        html_path = await _save_debug_html(page, url, "device_buttons_timeout")
        if screenshot_path:
            logger.info(f"Debug screenshot saved: {screenshot_path}")
        if html_path:
            logger.info(f"Debug HTML saved: {html_path}")
    
    return False


async def _wait_for_analysis_completion(page: Page, url: str, reload_tracker: PageReloadTracker, timeout_seconds: int = 120) -> bool:
    """
    Smart polling to wait for PageSpeed Insights analysis to complete.
    Waits for mobile/desktop buttons to appear before proceeding.
    
    Args:
        page: Playwright page object
        url: URL being analyzed
        reload_tracker: PageReloadTracker for page reload logic
        timeout_seconds: Maximum time to wait (default: 120)
        
    Returns:
        True if analysis completed, False if timeout
    """
    logger = get_logger()
    start_time = time.time()
    poll_interval = 2
    
    while time.time() - start_time < timeout_seconds:
        try:
            score_elements = await page.locator('.lh-exp-gauge__percentage').all()
            if not score_elements:
                score_elements = await page.locator('[data-testid="score-gauge"]').all()
            
            if len(score_elements) >= 1:
                if DEBUG_MODE:
                    logger.debug(f"Found {len(score_elements)} score elements")
                
                try:
                    mobile_button = page.locator('button:has-text("Mobile"), [role="tab"]:has-text("Mobile")').first
                    desktop_button = page.locator('button:has-text("Desktop"), [role="tab"]:has-text("Desktop")').first
                    
                    mobile_visible = await mobile_button.is_visible(timeout=1000)
                    desktop_visible = await desktop_button.is_visible(timeout=1000)
                    
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
        
        await asyncio.sleep(poll_interval)
    
    logger.warning(f"Analysis completion timeout after {timeout_seconds}s")
    
    if DEBUG_MODE or get_debug_mode():
        screenshot_path = await _save_debug_screenshot(page, url, "analysis_timeout")
        html_path = await _save_debug_html(page, url, "analysis_timeout")
        if screenshot_path:
            logger.info(f"Debug screenshot saved: {screenshot_path}")
        if html_path:
            logger.info(f"Debug HTML saved: {html_path}")
    
    return False


async def _extract_score_from_element(page: Page, view_type: str, url: str, max_retries: int = 3, retry_delay: float = 0.5) -> Optional[int]:
    """
    Extract score from PageSpeed Insights page for given view type with enhanced reliability.
    
    Implements retry logic with delays to handle cases where score elements exist but are not yet populated.
    Validates that extracted scores are valid integers between 0-100.
    Uses multiple fallback selectors including text content parsing from gauge elements.
    
    Args:
        page: Playwright page object
        view_type: 'mobile' or 'desktop'
        url: URL being analyzed (for error reporting)
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Delay in seconds between retries (default: 0.5)
        
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
                elements = await page.locator(selector).all()
                if not elements:
                    continue
                
                score_text = await elements[0].inner_text()
                score_text = score_text.strip()
                
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
            await asyncio.sleep(retry_delay)
    
    logger.warning(f"Failed to extract {view_type} score after {max_retries} attempts with all selectors")
    
    if DEBUG_MODE or get_debug_mode():
        screenshot_path = await _save_debug_screenshot(page, url, f"score_extraction_failed_{view_type}")
        html_path = await _save_debug_html(page, url, f"score_extraction_failed_{view_type}")
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


async def _run_analysis_once_async(url: str, timeout: int, force_retry: bool, force_fresh_instance: bool, pool: PlaywrightPool) -> Dict[str, Optional[int | str]]:
    """
    Internal async function to run a single Playwright analysis attempt with
    result caching, memory monitoring, resource blocking optimizations, and comprehensive error handling.
    """
    logger = get_logger()
    thread_id = threading.current_thread().ident
    
    _log_thread_operation(logger, f"Starting analysis for {url}")
    
    async def _execute_playwright():
        _log_thread_operation(logger, "Executing Playwright analysis", f"URL: {url}")
        
        # Get instance from pool (may be warm or None if pool empty)
        instance = await pool.get_instance()
        warm_start = instance is not None and instance.warm_start
        
        # Handle force fresh instance request (from force_fresh_instance parameter)
        if force_fresh_instance:
            if instance is not None:
                logger.info(f"{_get_thread_info()} Force fresh instance requested, refreshing instance for {url}")
                instance = await pool.force_refresh_instance(instance)
                warm_start = False
            else:
                logger.info(f"{_get_thread_info()} Force fresh instance requested, creating new instance for {url}")
                instance = await pool.create_instance()
                warm_start = False
        # Handle auto-refresh based on analysis count (if refresh_interval > 0)
        elif instance is not None and instance.should_refresh(pool.refresh_interval):
            logger.info(f"{_get_thread_info()} Auto-refresh triggered for instance (analyses: {instance.analyses_since_refresh}/{pool.refresh_interval}) for {url}")
            instance = await pool.force_refresh_instance(instance)
            warm_start = False
        
        analysis_start_time = time.time()
        last_successful_step = None
        
        if warm_start:
            logger.debug(f"{_get_thread_info()} Using warm Playwright instance for {url}")
        else:
            logger.debug(f"{_get_thread_info()} Cold start Playwright instance for {url}")
            if instance is None:
                instance = await pool.create_instance()
        
        page = None
        page_load_start = None
        reload_tracker = PageReloadTracker()
        
        try:
            context = instance.context
            _log_thread_operation(logger, "Creating new page", f"Context ID: {id(context)}")
            _threading_metrics.record_page_creation(thread_id)
            
            async with instance.context_lock:
                page = await context.new_page()
            _log_thread_operation(logger, "Page created", f"Page ID: {id(page)}")
            
            await _setup_request_interception(page, instance)
            
            page.set_default_timeout(timeout * 1000)
            
            instance.warm_start = True
            
            if DEBUG_MODE:
                logger.debug(f"Navigating to PageSpeed Insights...")
            
            nav_start = time.time()
            await page.goto('https://pagespeed.web.dev/', wait_until='domcontentloaded', timeout=30000)
            nav_time = time.time() - nav_start
            last_successful_step = "Navigated to PageSpeed Insights"
            
            if DEBUG_MODE:
                logger.debug(f"Page navigation took {nav_time:.2f}s")
                logger.debug(f"Entering URL: {url}")
            
            try:
                url_input = page.locator('input[type="url"], input[name="url"], input[placeholder*="URL"]').first
                await url_input.fill(url)
                last_successful_step = "Entered URL in input field"
            except Exception as e:
                screenshot_path = None
                html_path = None
                if DEBUG_MODE or get_debug_mode():
                    screenshot_path = await _save_debug_screenshot(page, url, "input_not_found")
                    html_path = await _save_debug_html(page, url, "input_not_found")
                
                try:
                    await _cleanup_browser_context(instance)
                except Exception as cleanup_error:
                    logger.debug(f"Cleanup failed during error handling: {cleanup_error}")
                
                await pool.return_instance(instance, success=False)
                error_msg = await _create_enhanced_error_message(
                    f"Failed to find URL input field: {e}",
                    url,
                    page=page,
                    last_successful_step=last_successful_step,
                    screenshot_path=screenshot_path,
                    html_path=html_path
                )
                raise PlaywrightSelectorTimeoutError(error_msg)
            
            await asyncio.sleep(1)
            
            if DEBUG_MODE:
                logger.debug("Clicking analyze button...")
            
            page_load_start = time.time()
            button_clicked = await _click_analyze_button(page, url, reload_tracker, timeout_ms=10000)
            if not button_clicked:
                try:
                    await _cleanup_browser_context(instance)
                except Exception as cleanup_error:
                    logger.debug(f"Cleanup failed during error handling: {cleanup_error}")
                
                await pool.return_instance(instance, success=False)
                raise PlaywrightSelectorTimeoutError("Failed to click analyze button - all selectors failed")
            
            last_successful_step = "Clicked analyze button"
            
            if DEBUG_MODE:
                logger.debug("Waiting for analysis to complete...")
            
            analysis_completed = await _wait_for_analysis_completion(page, url, reload_tracker, timeout_seconds=min(120, timeout))
            
            if not analysis_completed:
                elapsed = time.time() - analysis_start_time
                if elapsed >= timeout * 0.9:
                    screenshot_path = None
                    html_path = None
                    if DEBUG_MODE or get_debug_mode():
                        screenshot_path = await _save_debug_screenshot(page, url, "analysis_timeout")
                        html_path = await _save_debug_html(page, url, "analysis_timeout")
                    
                    try:
                        await _cleanup_browser_context(instance)
                    except Exception as cleanup_error:
                        logger.debug(f"Cleanup failed during error handling: {cleanup_error}")
                    
                    await pool.return_instance(instance, success=False)
                    error_msg = await _create_enhanced_error_message(
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
                    screenshot_path = await _save_debug_screenshot(page, url, "completion_timeout")
                    html_path = await _save_debug_html(page, url, "completion_timeout")
                
                try:
                    await _cleanup_browser_context(instance)
                except Exception as cleanup_error:
                    logger.debug(f"Cleanup failed during error handling: {cleanup_error}")
                
                await pool.return_instance(instance, success=False)
                error_msg = await _create_enhanced_error_message(
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
                
                try:
                    await _cleanup_browser_context(instance)
                except Exception as cleanup_error:
                    logger.debug(f"Cleanup failed during error handling: {cleanup_error}")
                
                await pool.return_instance(instance, success=False)
                raise PlaywrightRunnerError("Playwright process exceeded memory limit")
            
            if DEBUG_MODE:
                logger.debug("Waiting for device buttons to be available...")
            
            buttons_found = await _wait_for_device_buttons(page, url, reload_tracker, timeout_seconds=30)
            
            if not buttons_found:
                logger.warning("Device buttons not found within 30s, attempting score extraction anyway...")
            else:
                last_successful_step = "Device buttons loaded"
            
            await asyncio.sleep(1)
            
            if DEBUG_MODE:
                logger.debug("Extracting mobile score...")
            
            mobile_score = await _extract_score_from_element(page, 'mobile', url)
            if mobile_score is not None:
                last_successful_step = f"Extracted mobile score: {mobile_score}"
            
            mobile_psi_url = _get_psi_report_url(page) if mobile_score and mobile_score < 80 else None
            
            desktop_score = None
            desktop_psi_url = None
            desktop_switched = False
            
            # Early exit optimization: Check if we can extract both scores without switching views
            # Some PageSpeed Insights versions show both scores on the initial mobile view
            if DEBUG_MODE:
                logger.debug("Attempting early extraction of desktop score...")
            
            desktop_score_early = await _extract_score_from_element(page, 'desktop', url, max_retries=1, retry_delay=0.2)
            
            if desktop_score_early is not None and mobile_score is not None:
                # Both scores extracted without view switch - early exit!
                desktop_score = desktop_score_early
                desktop_psi_url = _get_psi_report_url(page) if desktop_score and desktop_score < 80 else None
                if DEBUG_MODE:
                    logger.debug(f"Early exit: Both scores extracted without view switch (mobile: {mobile_score}, desktop: {desktop_score})")
                last_successful_step = f"Extracted both scores (mobile: {mobile_score}, desktop: {desktop_score})"
                desktop_switched = True  # Mark as switched to skip error handling below
            else:
                # Need to switch to desktop view
                if DEBUG_MODE:
                    logger.debug("Switching to desktop view...")
                
                desktop_button_selectors = [
                    'button:has-text("Desktop")',
                    '[role="tab"]:has-text("Desktop")'
                ]
                
                for selector in desktop_button_selectors:
                    try:
                        desktop_button = page.locator(selector).first
                        await desktop_button.click(timeout=5000)
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
                    await asyncio.sleep(1)
                    if DEBUG_MODE:
                        logger.debug("Extracting desktop score...")
                    
                    desktop_score = await _extract_score_from_element(page, 'desktop', url)
                    if desktop_score is not None:
                        last_successful_step = f"Extracted desktop score: {desktop_score}"
                    
                    desktop_psi_url = _get_psi_report_url(page) if desktop_score and desktop_score < 80 else None
            
            if not desktop_switched:
                screenshot_path = None
                html_path = None
                if DEBUG_MODE or get_debug_mode():
                    screenshot_path = await _save_debug_screenshot(page, url, "desktop_switch_failed")
                    html_path = await _save_debug_html(page, url, "desktop_switch_failed")
                
                try:
                    await _cleanup_browser_context(instance)
                except Exception as cleanup_error:
                    logger.debug(f"Cleanup failed during error handling: {cleanup_error}")
                
                await pool.return_instance(instance, success=False)
                error_msg = await _create_enhanced_error_message(
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
                    screenshot_path = await _save_debug_screenshot(page, url, "no_scores_extracted")
                    html_path = await _save_debug_html(page, url, "no_scores_extracted")
                
                try:
                    await _cleanup_browser_context(instance)
                except Exception as cleanup_error:
                    logger.debug(f"Cleanup failed during error handling: {cleanup_error}")
                
                await pool.return_instance(instance, success=False)
                error_msg = await _create_enhanced_error_message(
                    "Failed to extract any scores from PageSpeed Insights",
                    url,
                    page=page,
                    last_successful_step=last_successful_step,
                    screenshot_path=screenshot_path,
                    html_path=html_path
                )
                raise PlaywrightSelectorTimeoutError(error_msg)
            
            instance.record_analysis(page_load_time)
            
            if DEBUG_MODE:
                logger.debug(f"{_get_thread_info()} Instance PID {instance.pid} completed analysis #{instance.analyses_since_refresh} (total: {instance.total_analyses})")
            
            await page.close()

            memory_before, memory_after = await _cleanup_browser_context(instance)
            
            await pool.return_instance(instance, success=True)
            
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
                '_total_requests': instance.blocking_stats.total_requests,
                '_memory_before_cleanup': memory_before,
                '_memory_after_cleanup': memory_after
            }
            
        except (PlaywrightAnalysisTimeoutError, PlaywrightSelectorTimeoutError):
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            
            try:
                await _cleanup_browser_context(instance)
            except Exception as cleanup_error:
                logger.debug(f"Cleanup failed during error handling: {cleanup_error}")
            
            await pool.return_instance(instance, success=False)
            raise
            
        except Exception as e:
            screenshot_path = None
            html_path = None
            if page:
                if DEBUG_MODE or get_debug_mode():
                    screenshot_path = await _save_debug_screenshot(page, url, "unexpected_error")
                    html_path = await _save_debug_html(page, url, "unexpected_error")
                
                try:
                    await page.close()
                except Exception:
                    pass
            
            try:
                await _cleanup_browser_context(instance)
            except Exception as cleanup_error:
                logger.debug(f"Cleanup failed during error handling: {cleanup_error}")
            
            await pool.return_instance(instance, success=False)
            
            if isinstance(e, (PlaywrightRunnerError, PermanentError)):
                raise
            
            error_msg = await _create_enhanced_error_message(
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
            return await _execute_playwright()
        except Exception as e:
            if "Circuit breaker" in str(e) and "is OPEN" in str(e):
                logger.warning(f"Circuit breaker bypassed due to --force-retry flag")
                return await _execute_playwright()
            raise
    else:
        try:
            return circuit_breaker.call(lambda: asyncio.run_coroutine_threadsafe(_execute_playwright(), pool.loop).result())
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
    event_loop_thread = _get_event_loop_thread()
    event_loop_thread.shutdown()


def get_pool_stats() -> Dict:
    """Get current pool statistics for monitoring"""
    event_loop_thread = _get_event_loop_thread()
    if event_loop_thread.loop and event_loop_thread._pool:
        future = asyncio.run_coroutine_threadsafe(
            event_loop_thread._pool.get_pool_stats(),
            event_loop_thread.loop
        )
        return future.result(timeout=5.0)
    return {
        'mode': 'multi-context',
        'max_concurrent_contexts': _max_concurrent_contexts,
        'total_contexts': 0,
        'idle_contexts': 0,
        'busy_contexts': 0,
        'total_warm_starts': 0,
        'total_cold_starts': 0,
        'total_refreshes': 0,
        'refresh_interval': _refresh_interval,
        'refresh_enabled': _refresh_interval > 0,
        'avg_startup_time': 0.0,
        'contexts': []
    }


def get_event_loop_health() -> Dict:
    """Get event loop health status"""
    event_loop_thread = _get_event_loop_thread()
    return event_loop_thread.get_health_status()


async def _force_refresh_all_instances_async(pool: PlaywrightPool) -> int:
    """
    Force refresh all instances in the pool (internal async function).
    
    Returns:
        Number of instances refreshed
    """
    logger = get_logger()
    logger.info(f"{_get_thread_info()} Force refreshing instances")
    
    async with pool.lock:
        instances_to_refresh = [inst for inst in pool.contexts if inst.is_alive()]
    
    refresh_count = 0
    for instance in instances_to_refresh:
        try:
            await pool.force_refresh_instance(instance)
            refresh_count += 1
        except Exception as e:
            logger.error(f"{_get_thread_info()} Failed to refresh instance: {e}")
    
    logger.info(f"{_get_thread_info()} Refreshed {refresh_count} instance(s)")
    return refresh_count


def force_refresh_all_instances() -> int:
    """
    Force refresh all browser instances in the pool.
    Useful for debugging or manual maintenance.
    
    Returns:
        Number of instances refreshed
    """
    event_loop_thread = _get_event_loop_thread()
    if event_loop_thread.loop and event_loop_thread._pool:
        future = asyncio.run_coroutine_threadsafe(
            _force_refresh_all_instances_async(event_loop_thread._pool),
            event_loop_thread.loop
        )
        return future.result(timeout=30.0)
    return 0


def drain_pool() -> bool:
    """
    Explicitly shutdown and recreate all browser contexts.
    Useful for forcing a clean state or recovering from errors.
    
    Returns:
        True if successful, False if pool not initialized
    """
    event_loop_thread = _get_event_loop_thread()
    if event_loop_thread.loop and event_loop_thread._pool:
        future = asyncio.run_coroutine_threadsafe(
            event_loop_thread._pool.drain_pool(),
            event_loop_thread.loop
        )
        future.result(timeout=30.0)
        return True
    return False


def diagnose_threading_issues() -> Dict:
    """
    Comprehensive diagnostic report for threading issues
    
    Returns a dictionary with:
    - Threading metrics (greenlet errors, thread conflicts, etc.)
    - Event loop health status
    - Pool statistics
    - Active thread information
    - Python/asyncio version info
    """
    logger = get_logger()
    
    main_thread = threading.main_thread()
    current_thread = threading.current_thread()
    all_threads = threading.enumerate()
    
    event_loop_thread = _get_event_loop_thread()
    
    try:
        loop_info = None
        if event_loop_thread.loop:
            try:
                loop_info = {
                    'loop_id': id(event_loop_thread.loop),
                    'is_running': event_loop_thread.loop.is_running(),
                    'is_closed': event_loop_thread.loop.is_closed(),
                }
            except Exception as e:
                loop_info = {'error': str(e)}
    except Exception as e:
        loop_info = {'error': str(e)}
    
    try:
        asyncio_debug = asyncio.get_event_loop().get_debug()
    except Exception:
        asyncio_debug = None
    
    diagnosis = {
        'python_version': sys.version,
        'asyncio_debug': asyncio_debug,
        'main_thread': {
            'id': main_thread.ident,
            'name': main_thread.name,
            'is_alive': main_thread.is_alive()
        },
        'current_thread': {
            'id': current_thread.ident,
            'name': current_thread.name,
            'is_alive': current_thread.is_alive(),
            'is_main': current_thread == main_thread
        },
        'all_threads': [
            {
                'id': t.ident,
                'name': t.name,
                'daemon': t.daemon,
                'is_alive': t.is_alive()
            }
            for t in all_threads
        ],
        'event_loop_thread': {
            'exists': event_loop_thread is not None,
            'thread_id': event_loop_thread.thread.ident if event_loop_thread.thread else None,
            'thread_name': event_loop_thread.thread.name if event_loop_thread.thread else None,
            'thread_is_alive': event_loop_thread.thread.is_alive() if event_loop_thread.thread else False,
            'loop_info': loop_info
        },
        'threading_metrics': get_threading_metrics(),
        'event_loop_health': get_event_loop_health(),
        'pool_stats': get_pool_stats(),
    }
    
    logger.info(f"{_get_thread_info()} Threading diagnostics generated")
    
    return diagnosis


def print_threading_diagnostics():
    """Print a formatted threading diagnostics report to stdout"""
    import json
    
    diagnosis = diagnose_threading_issues()
    
    print("\n" + "="*80)
    print("PLAYWRIGHT THREADING DIAGNOSTICS")
    print("="*80)
    
    print(f"\nPython Version: {diagnosis['python_version']}")
    print(f"Asyncio Debug: {diagnosis.get('asyncio_debug', 'N/A')}")
    
    print("\n--- Main Thread ---")
    print(f"  ID: {diagnosis['main_thread']['id']}")
    print(f"  Name: {diagnosis['main_thread']['name']}")
    print(f"  Alive: {diagnosis['main_thread']['is_alive']}")
    
    print("\n--- Current Thread ---")
    print(f"  ID: {diagnosis['current_thread']['id']}")
    print(f"  Name: {diagnosis['current_thread']['name']}")
    print(f"  Is Main: {diagnosis['current_thread']['is_main']}")
    
    print("\n--- All Threads ---")
    for t in diagnosis['all_threads']:
        print(f"  [{t['id']}] {t['name']} (daemon={t['daemon']}, alive={t['is_alive']})")
    
    print("\n--- Event Loop Thread ---")
    elt = diagnosis['event_loop_thread']
    print(f"  Exists: {elt['exists']}")
    print(f"  Thread ID: {elt['thread_id']}")
    print(f"  Thread Name: {elt['thread_name']}")
    print(f"  Thread Alive: {elt['thread_is_alive']}")
    if elt['loop_info']:
        print(f"  Loop Info: {json.dumps(elt['loop_info'], indent=4)}")
    
    print("\n--- Threading Metrics ---")
    metrics = diagnosis['threading_metrics']
    print(f"  Greenlet Errors: {metrics['greenlet_errors']}")
    print(f"  Thread Conflicts: {metrics['thread_conflicts']}")
    print(f"  Event Loop Failures: {metrics['event_loop_failures']}")
    print(f"  Context Creations by Thread: {metrics['context_creation_by_thread']}")
    print(f"  Page Creations by Thread: {metrics['page_creation_by_thread']}")
    print(f"  Async Operations by Thread: {metrics['async_operations_by_thread']}")
    
    print("\n--- Event Loop Health ---")
    health = diagnosis['event_loop_health']
    print(f"  Last Heartbeat: {health['last_heartbeat']}")
    print(f"  Time Since Heartbeat: {health['time_since_heartbeat']}")
    print(f"  Heartbeat Failures: {health['heartbeat_failures']}")
    print(f"  Is Responsive: {health['is_responsive']}")
    print(f"  Thread ID: {health['thread_id']}")
    
    print("\n--- Pool Stats ---")
    pool = diagnosis['pool_stats']
    print(f"  Total Instances: {pool['total_instances']}")
    print(f"  Idle Instances: {pool['idle_instances']}")
    print(f"  Busy Instances: {pool['busy_instances']}")
    print(f"  Warm Starts: {pool['total_warm_starts']}")
    print(f"  Cold Starts: {pool['total_cold_starts']}")
    print(f"  Avg Startup Time: {pool['avg_startup_time']:.2f}s")
    
    print("\n" + "="*80 + "\n")
