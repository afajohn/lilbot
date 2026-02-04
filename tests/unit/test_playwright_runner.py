import pytest
import time
import asyncio
from unittest.mock import Mock, MagicMock, patch, call, AsyncMock
from typing import Dict, Optional

pytestmark = pytest.mark.playwright

from tools.qa.playwright_runner import (
    run_analysis,
    shutdown_pool,
    PlaywrightRunnerError,
    PlaywrightAnalysisTimeoutError,
    PlaywrightSelectorTimeoutError,
    PlaywrightPool,
    PlaywrightInstance,
    InstanceState,
    ProgressiveTimeout,
    _get_circuit_breaker,
    _get_progressive_timeout,
    _get_psi_report_url,
)
from tools.utils.exceptions import PermanentError, RetryableError
from tools.cache.cache_manager import CacheManager, FileCacheBackend


@pytest.fixture
def mock_playwright_available():
    with patch('tools.qa.playwright_runner.PLAYWRIGHT_AVAILABLE', True):
        yield


@pytest.fixture
def mock_cache_manager():
    cache = Mock(spec=CacheManager)
    cache.get.return_value = None
    cache.set.return_value = True
    
    with patch('tools.qa.playwright_runner.get_cache_manager', return_value=cache):
        yield cache


@pytest.fixture
def mock_metrics():
    metrics = Mock()
    metrics.increment_total_operations = Mock()
    metrics.record_success = Mock()
    metrics.record_failure = Mock()
    metrics.record_error = Mock()
    
    with patch('tools.qa.playwright_runner.get_global_metrics', return_value=metrics):
        yield metrics


@pytest.fixture
def mock_metrics_collector():
    collector = Mock()
    collector.record_cache_hit = Mock()
    collector.record_cache_miss = Mock()
    collector.record_api_call_cypress = Mock()
    collector.record_playwright_metrics = Mock()
    
    with patch('tools.metrics.metrics_collector.get_metrics_collector', return_value=collector):
        yield collector


@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.url = 'https://pagespeed.web.dev/analysis?url=https://example.com'
    page.goto = AsyncMock()
    page.close = AsyncMock()
    page.set_default_timeout = Mock()
    
    url_input = AsyncMock()
    url_input.fill = AsyncMock()
    page.locator = Mock(return_value=Mock(first=url_input))
    
    return page


@pytest.fixture
def mock_context(mock_page):
    context = AsyncMock()
    context.new_page = AsyncMock(return_value=mock_page)
    context.close = AsyncMock()
    return context


@pytest.fixture
def mock_browser(mock_context):
    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=mock_context)
    browser.close = AsyncMock()
    browser.is_connected = Mock(return_value=True)
    
    mock_proc = Mock()
    mock_proc.pid = 12345
    browser._impl_obj._connection._transport._proc = mock_proc
    
    return browser


@pytest.fixture
def mock_playwright(mock_browser):
    pw = AsyncMock()
    pw.chromium.launch = AsyncMock(return_value=mock_browser)
    pw.stop = AsyncMock()
    
    async_pw_context = AsyncMock()
    async_pw_context.__aenter__ = AsyncMock(return_value=pw)
    async_pw_context.__aexit__ = AsyncMock(return_value=None)
    async_pw_context.start = AsyncMock(return_value=pw)
    
    with patch('tools.qa.playwright_runner.async_playwright', return_value=async_pw_context):
        yield pw


@pytest.fixture(autouse=True)
def reset_globals():
    yield
    
    import tools.qa.playwright_runner as pr
    pr._event_loop_thread = None
    pr._circuit_breaker = None
    pr._progressive_timeout = None


@pytest.fixture
def mock_event_loop_thread():
    """Mock the event loop thread to return results immediately"""
    with patch('tools.qa.playwright_runner.PlaywrightEventLoopThread') as MockThread:
        thread_instance = Mock()
        
        def submit_analysis(url, timeout, force_retry):
            from concurrent.futures import Future
            future = Future()
            future.set_result({
                'mobile_score': 85,
                'desktop_score': 90,
                'mobile_psi_url': None,
                'desktop_psi_url': None,
                '_warm_start': False,
                '_page_load_time': 2.5,
                '_browser_startup_time': 0.5,
                '_memory_mb': 256.0,
                '_blocked_requests': 10,
                '_total_requests': 25
            })
            return future
        
        thread_instance.submit_analysis = submit_analysis
        thread_instance.start = Mock()
        thread_instance.shutdown = Mock()
        MockThread.return_value = thread_instance
        yield thread_instance


class TestSingleURLAnalysis:
    """Test single URL analysis functionality"""
    
    def test_successful_analysis_mobile_and_desktop(
        self, mock_playwright_available, mock_cache_manager, mock_metrics,
        mock_metrics_collector, mock_event_loop_thread
    ):
        result = run_analysis('https://example.com', timeout=600)
        
        assert result['mobile_score'] == 85
        assert result['desktop_score'] == 90
        assert result['mobile_psi_url'] is None
        assert result['desktop_psi_url'] is None
        assert result['_from_cache'] is False
    
    def test_analysis_with_low_score_returns_psi_url(
        self, mock_playwright_available, mock_cache_manager, mock_metrics,
        mock_metrics_collector
    ):
        with patch('tools.qa.playwright_runner.PlaywrightEventLoopThread') as MockThread:
            thread_instance = Mock()
            
            def submit_analysis(url, timeout, force_retry):
                from concurrent.futures import Future
                future = Future()
                future.set_result({
                    'mobile_score': 65,
                    'desktop_score': 70,
                    'mobile_psi_url': 'https://pagespeed.web.dev/mobile',
                    'desktop_psi_url': 'https://pagespeed.web.dev/desktop',
                    '_warm_start': False
                })
                return future
            
            thread_instance.submit_analysis = submit_analysis
            thread_instance.start = Mock()
            MockThread.return_value = thread_instance
            
            result = run_analysis('https://example.com')
            
            assert result['mobile_score'] == 65
            assert result['desktop_score'] == 70
            assert result['mobile_psi_url'] == 'https://pagespeed.web.dev/mobile'
            assert result['desktop_psi_url'] == 'https://pagespeed.web.dev/desktop'


class TestTimeoutHandling:
    """Test timeout handling"""
    
    def test_analysis_respects_timeout_parameter(
        self, mock_playwright_available, mock_cache_manager, mock_metrics,
        mock_metrics_collector, mock_event_loop_thread
    ):
        result = run_analysis('https://example.com', timeout=300)
        
        assert result['mobile_score'] == 85
    
    def test_timeout_error_raises_playwright_timeout_error(
        self, mock_playwright_available, mock_cache_manager, mock_metrics,
        mock_metrics_collector
    ):
        with patch('tools.qa.playwright_runner.PlaywrightEventLoopThread') as MockThread:
            thread_instance = Mock()
            
            def submit_analysis(url, timeout, force_retry):
                from concurrent.futures import Future
                future = Future()
                future.set_exception(PlaywrightAnalysisTimeoutError("Analysis timeout"))
                return future
            
            thread_instance.submit_analysis = submit_analysis
            thread_instance.start = Mock()
            MockThread.return_value = thread_instance
            
            with pytest.raises(PlaywrightAnalysisTimeoutError, match="Analysis timeout"):
                run_analysis('https://example.com', timeout=300)
    
    def test_progressive_timeout_increases_after_failure(self):
        pt = ProgressiveTimeout(initial_timeout=300)
        
        assert pt.get_timeout() == 300
        
        pt.record_failure()
        
        assert pt.get_timeout() == 600


class TestRetryLogic:
    """Test retry logic"""
    
    def test_successful_retry_after_transient_failure(
        self, mock_playwright_available, mock_cache_manager, mock_metrics,
        mock_metrics_collector
    ):
        with patch('tools.qa.playwright_runner.PlaywrightEventLoopThread') as MockThread:
            thread_instance = Mock()
            call_count = 0
            
            def submit_analysis(url, timeout, force_retry):
                nonlocal call_count
                call_count += 1
                from concurrent.futures import Future
                future = Future()
                if call_count == 1:
                    future.set_exception(PlaywrightRunnerError("Transient error"))
                else:
                    future.set_result({
                        'mobile_score': 85,
                        'desktop_score': 90,
                        'mobile_psi_url': None,
                        'desktop_psi_url': None,
                        '_warm_start': False
                    })
                return future
            
            thread_instance.submit_analysis = submit_analysis
            thread_instance.start = Mock()
            MockThread.return_value = thread_instance
            
            with patch('time.sleep'):
                result = run_analysis('https://example.com')
            
            assert result['mobile_score'] == 85
            assert call_count == 2
    
    def test_timeout_stops_infinite_retry(
        self, mock_playwright_available, mock_cache_manager, mock_metrics,
        mock_metrics_collector
    ):
        with patch('tools.qa.playwright_runner.PlaywrightEventLoopThread') as MockThread:
            thread_instance = Mock()
            
            def submit_analysis(url, timeout, force_retry):
                from concurrent.futures import Future
                future = Future()
                future.set_exception(PlaywrightRunnerError("Persistent error"))
                return future
            
            thread_instance.submit_analysis = submit_analysis
            thread_instance.start = Mock()
            MockThread.return_value = thread_instance
            
            with patch('time.sleep'):
                with patch('time.time') as mock_time:
                    mock_time.side_effect = [0, 0, 601, 601]
                    with pytest.raises(PlaywrightAnalysisTimeoutError, match="exceeded overall timeout"):
                        run_analysis('https://example.com', timeout=600)
    
    def test_permanent_error_no_retry(
        self, mock_playwright_available, mock_cache_manager, mock_metrics,
        mock_metrics_collector
    ):
        with patch('tools.qa.playwright_runner.PlaywrightEventLoopThread') as MockThread:
            thread_instance = Mock()
            call_count = 0
            
            def submit_analysis(url, timeout, force_retry):
                nonlocal call_count
                call_count += 1
                from concurrent.futures import Future
                future = Future()
                future.set_exception(PermanentError("Cannot install Playwright"))
                return future
            
            thread_instance.submit_analysis = submit_analysis
            thread_instance.start = Mock()
            MockThread.return_value = thread_instance
            
            with pytest.raises(PermanentError, match="Cannot install Playwright"):
                run_analysis('https://example.com')
            
            assert call_count == 1


class TestCacheIntegration:
    """Test cache integration"""
    
    def test_cache_hit_returns_cached_result(
        self, mock_playwright_available, mock_metrics, mock_metrics_collector
    ):
        cached_result = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        cache = Mock(spec=CacheManager)
        cache.get.return_value = cached_result
        cache.set.return_value = True
        
        with patch('tools.qa.playwright_runner.get_cache_manager', return_value=cache):
            result = run_analysis('https://example.com', skip_cache=False)
        
        assert result['mobile_score'] == 85
        assert result['_from_cache'] is True
        
        cache.get.assert_called_once_with('https://example.com')
        cache.set.assert_not_called()
        
        mock_metrics_collector.record_cache_hit.assert_called_once()
    
    def test_cache_miss_performs_analysis_and_caches(
        self, mock_playwright_available, mock_metrics, mock_metrics_collector, mock_event_loop_thread
    ):
        cache = Mock(spec=CacheManager)
        cache.get.return_value = None
        cache.set.return_value = True
        
        with patch('tools.qa.playwright_runner.get_cache_manager', return_value=cache):
            result = run_analysis('https://example.com', skip_cache=False)
        
        assert result['mobile_score'] == 85
        assert result['_from_cache'] is False
        
        cache.get.assert_called_once()
        cache.set.assert_called_once()
        
        mock_metrics_collector.record_cache_miss.assert_called_once()
    
    def test_skip_cache_bypasses_cache_lookup(
        self, mock_playwright_available, mock_metrics, mock_metrics_collector, mock_event_loop_thread
    ):
        cache = Mock(spec=CacheManager)
        cache.get.return_value = {
            'mobile_score': 75,
            'desktop_score': 80,
            'mobile_psi_url': 'https://psi.url',
            'desktop_psi_url': None
        }
        
        with patch('tools.qa.playwright_runner.get_cache_manager', return_value=cache):
            result = run_analysis('https://example.com', skip_cache=True)
        
        assert result['mobile_score'] == 85
        
        cache.get.assert_not_called()


class TestPlaywrightPool:
    """Test Playwright instance pooling"""
    
    def test_pool_creates_instance_on_first_request(self, mock_playwright):
        async def run_test():
            loop = asyncio.get_event_loop()
            pool = PlaywrightPool(loop, Mock())
            await pool.initialize()
            
            instance = await pool.create_instance()
            
            assert instance is not None
            assert instance.state == InstanceState.IDLE
            assert instance.warm_start is False
            assert instance.failures == 0
        
        asyncio.run(run_test())
    
    def test_pool_reuses_idle_instance(self, mock_playwright):
        async def run_test():
            loop = asyncio.get_event_loop()
            pool = PlaywrightPool(loop, Mock())
            await pool.initialize()
            
            instance1 = await pool.create_instance()
            await pool.return_instance(instance1, success=True)
            
            instance2 = await pool.get_instance()
            
            assert instance2 is instance1
            assert instance2.state == InstanceState.BUSY
        
        asyncio.run(run_test())
    
    def test_pool_removes_high_memory_instance(self, mock_playwright):
        async def run_test():
            loop = asyncio.get_event_loop()
            pool = PlaywrightPool(loop, Mock())
            await pool.initialize()
            
            instance = await pool.create_instance()
            
            with patch.object(instance, 'get_memory_usage', return_value=2048):
                await pool.return_instance(instance, success=True)
            
            assert instance not in pool.contexts
        
        asyncio.run(run_test())
    
    def test_pool_removes_instance_after_failures(self, mock_playwright):
        async def run_test():
            loop = asyncio.get_event_loop()
            pool = PlaywrightPool(loop, Mock())
            await pool.initialize()
            
            instance = await pool.create_instance()
            
            await pool.return_instance(instance, success=False)
            await pool.return_instance(instance, success=False)
            await pool.return_instance(instance, success=False)
            
            assert instance not in pool.contexts
        
        asyncio.run(run_test())
    
    def test_pool_shutdown_closes_all_instances(self, mock_playwright):
        async def run_test():
            loop = asyncio.get_event_loop()
            pool = PlaywrightPool(loop, Mock())
            await pool.initialize()
            
            instance1 = await pool.create_instance()
            
            await pool.shutdown()
            
            assert len(pool.contexts) == 0
        
        asyncio.run(run_test())


class TestPlaywrightInstance:
    """Test PlaywrightInstance functionality"""
    
    def test_instance_is_alive_when_connected(self, mock_browser):
        instance = PlaywrightInstance(
            browser=mock_browser,
            context=None,
            state=InstanceState.IDLE,
            memory_mb=100.0,
            last_used=time.time(),
            warm_start=False,
            failures=0,
            pid=12345
        )
        
        assert instance.is_alive() is True
    
    def test_instance_not_alive_when_browser_none(self):
        instance = PlaywrightInstance(
            browser=None,
            context=None,
            state=InstanceState.IDLE,
            memory_mb=0.0,
            last_used=time.time(),
            warm_start=False,
            failures=0,
            pid=None
        )
        
        assert instance.is_alive() is False
    
    def test_instance_get_memory_usage(self):
        mock_browser = AsyncMock()
        mock_browser.is_connected = Mock(return_value=True)
        
        instance = PlaywrightInstance(
            browser=mock_browser,
            context=None,
            state=InstanceState.IDLE,
            memory_mb=100.0,
            last_used=time.time(),
            warm_start=False,
            failures=0,
            pid=12345
        )
        
        with patch('psutil.Process') as mock_process:
            mock_proc = mock_process.return_value
            mock_proc.memory_info.return_value = Mock(rss=1024 * 1024 * 512)
            
            memory = instance.get_memory_usage()
            
            assert memory == 512.0


class TestPSIReportURL:
    """Test PSI report URL extraction"""
    
    def test_get_psi_report_url_success(self):
        page = Mock()
        page.url = 'https://pagespeed.web.dev/analysis?url=https://example.com'
        
        url = _get_psi_report_url(page)
        
        assert url == 'https://pagespeed.web.dev/analysis?url=https://example.com'
    
    def test_get_psi_report_url_not_psi_page(self):
        page = Mock()
        page.url = 'https://example.com'
        
        url = _get_psi_report_url(page)
        
        assert url is None


class TestCircuitBreaker:
    """Test circuit breaker integration"""
    
    def test_circuit_breaker_integration(
        self, mock_playwright_available, mock_cache_manager, mock_metrics,
        mock_metrics_collector
    ):
        circuit_breaker = _get_circuit_breaker()
        circuit_breaker.reset()
        
        with patch('tools.qa.playwright_runner.PlaywrightEventLoopThread') as MockThread:
            thread_instance = Mock()
            
            def submit_analysis(url, timeout, force_retry):
                from concurrent.futures import Future
                future = Future()
                future.set_exception(PlaywrightRunnerError("Service unavailable"))
                return future
            
            thread_instance.submit_analysis = submit_analysis
            thread_instance.start = Mock()
            MockThread.return_value = thread_instance
            
            with patch('time.sleep'):
                with patch('time.time') as mock_time:
                    failures = 0
                    for i in range(10):
                        mock_time.side_effect = [0, 0.1]
                        try:
                            run_analysis('https://example.com', timeout=1)
                        except (PlaywrightRunnerError, Exception) as e:
                            failures += 1
                            if "Circuit breaker" in str(e) and "is OPEN" in str(e):
                                break
                    
                    assert failures >= 5


class TestPlaywrightNotInstalled:
    """Test behavior when Playwright is not installed"""
    
    def test_raises_permanent_error_when_not_installed(self, mock_cache_manager, mock_metrics, mock_metrics_collector):
        with patch('tools.qa.playwright_runner.PLAYWRIGHT_AVAILABLE', False):
            with pytest.raises(PermanentError, match="Playwright is not installed"):
                run_analysis('https://example.com')


class TestMetricsCollection:
    """Test metrics collection during analysis"""
    
    def test_metrics_recorded_on_success(
        self, mock_playwright_available, mock_cache_manager, mock_metrics,
        mock_metrics_collector, mock_event_loop_thread
    ):
        run_analysis('https://example.com')
        
        mock_metrics.increment_total_operations.assert_called_once()
        mock_metrics.record_success.assert_called_once()
        mock_metrics_collector.record_api_call_cypress.assert_called()
    
    def test_metrics_recorded_on_failure(
        self, mock_playwright_available, mock_cache_manager, mock_metrics,
        mock_metrics_collector
    ):
        with patch('tools.qa.playwright_runner.PlaywrightEventLoopThread') as MockThread:
            thread_instance = Mock()
            
            def submit_analysis(url, timeout, force_retry):
                from concurrent.futures import Future
                future = Future()
                future.set_exception(PermanentError("Analysis failed"))
                return future
            
            thread_instance.submit_analysis = submit_analysis
            thread_instance.start = Mock()
            MockThread.return_value = thread_instance
            
            try:
                run_analysis('https://example.com')
            except PermanentError:
                pass
        
        mock_metrics.increment_total_operations.assert_called_once()
        mock_metrics.record_failure.assert_called()
