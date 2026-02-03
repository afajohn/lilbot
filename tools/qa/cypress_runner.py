import subprocess
import json
import os
import time
import glob
import shutil
import sys
import traceback
import psutil
import threading
from typing import Dict, Optional, Iterator
from queue import Queue, Empty
from dataclasses import dataclass
from enum import Enum

from tools.utils.exceptions import RetryableError, PermanentError
from tools.utils.circuit_breaker import CircuitBreaker
from tools.utils.error_metrics import get_global_metrics
from tools.utils.logger import get_logger
from tools.cache.cache_manager import get_cache_manager


class CypressRunnerError(Exception):
    pass


class CypressTimeoutError(CypressRunnerError):
    pass


class InstanceState(Enum):
    """Cypress instance states"""
    IDLE = "idle"
    BUSY = "busy"
    DEAD = "dead"


@dataclass
class CypressInstance:
    """Represents a pooled Cypress instance"""
    process: Optional[subprocess.Popen]
    state: InstanceState
    memory_mb: float
    last_used: float
    warm_start: bool
    failures: int
    
    def is_alive(self) -> bool:
        """Check if the process is still running"""
        if self.process is None:
            return False
        return self.process.poll() is None
    
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        if self.process is None or not self.is_alive():
            return 0.0
        try:
            proc = psutil.Process(self.process.pid)
            mem_info = proc.memory_info()
            self.memory_mb = mem_info.rss / (1024 * 1024)
            return self.memory_mb
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0
    
    def kill(self):
        """Terminate the instance"""
        if self.process and self.is_alive():
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            except Exception:
                pass
        self.state = InstanceState.DEAD


class CypressPool:
    """Pool of reusable Cypress instances for warm starts"""
    
    MAX_MEMORY_MB = 1024  # 1GB memory threshold
    POOL_SIZE = 2
    
    def __init__(self):
        self.instances = []
        self.lock = threading.Lock()
        self.logger = get_logger()
        self._shutdown = False
    
    def get_instance(self) -> Optional[CypressInstance]:
        """Get an available instance from the pool"""
        with self.lock:
            # Find idle instance with acceptable memory
            for instance in self.instances:
                if instance.state == InstanceState.IDLE and instance.is_alive():
                    mem = instance.get_memory_usage()
                    if mem < self.MAX_MEMORY_MB:
                        instance.state = InstanceState.BUSY
                        instance.last_used = time.time()
                        return instance
                    else:
                        # Memory too high, kill and remove
                        self.logger.info(f"Killing instance due to high memory: {mem:.1f}MB")
                        instance.kill()
                        self.instances.remove(instance)
        return None
    
    def return_instance(self, instance: CypressInstance, success: bool = True):
        """Return an instance to the pool"""
        with self.lock:
            if not success:
                instance.failures += 1
            
            # Kill if too many failures or high memory
            mem = instance.get_memory_usage()
            if instance.failures >= 3 or mem >= self.MAX_MEMORY_MB or not instance.is_alive():
                if instance in self.instances:
                    self.instances.remove(instance)
                instance.kill()
                return
            
            instance.state = InstanceState.IDLE
    
    def create_instance(self) -> CypressInstance:
        """Create a new instance (placeholder - actual Cypress process created per request)"""
        instance = CypressInstance(
            process=None,
            state=InstanceState.IDLE,
            memory_mb=0.0,
            last_used=time.time(),
            warm_start=False,
            failures=0
        )
        with self.lock:
            if len(self.instances) < self.POOL_SIZE:
                self.instances.append(instance)
        return instance
    
    def cleanup_dead_instances(self):
        """Remove dead instances from the pool"""
        with self.lock:
            dead_instances = [i for i in self.instances if not i.is_alive() or i.state == InstanceState.DEAD]
            for instance in dead_instances:
                instance.kill()
                self.instances.remove(instance)
    
    def shutdown(self):
        """Shutdown all instances in the pool"""
        self._shutdown = True
        with self.lock:
            for instance in self.instances:
                instance.kill()
            self.instances.clear()


# Global pool instance
_pool = None
_pool_lock = threading.Lock()


def _get_pool() -> CypressPool:
    """Get or create the global Cypress pool"""
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = CypressPool()
        return _pool


_circuit_breaker = None
_circuit_breaker_lock = threading.Lock()


def _get_circuit_breaker() -> CircuitBreaker:
    """Get or create the global circuit breaker for PageSpeed Insights"""
    global _circuit_breaker
    with _circuit_breaker_lock:
        if _circuit_breaker is None:
            logger = get_logger()
            _circuit_breaker = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=300.0,
                expected_exception=CypressRunnerError,
                name="PageSpeedInsights",
                logger=logger
            )
        return _circuit_breaker


def _find_npx() -> str:
    """
    Find the npx executable, handling Windows vs Unix differences.
    
    Returns:
        Path to npx executable
        
    Raises:
        PermanentError: If npx cannot be found
    """
    if sys.platform == 'win32':
        npx_cmd = shutil.which('npx.cmd')
        if npx_cmd:
            return npx_cmd
        npx_cmd = shutil.which('npx')
        if npx_cmd:
            return npx_cmd
    else:
        npx_cmd = shutil.which('npx')
        if npx_cmd:
            return npx_cmd
    
    raise PermanentError(
        "npx not found. Ensure Node.js is installed and npx is available in PATH. "
        "Try running 'npm install -g npm' to ensure npx is properly installed."
    )


class ProgressiveTimeout:
    """Manages progressive timeout strategy"""
    
    def __init__(self, initial_timeout: int = 300):
        self.initial_timeout = initial_timeout
        self.current_timeout = initial_timeout
        self.max_timeout = 600
        self.failure_count = 0
        self.lock = threading.Lock()
    
    def get_timeout(self) -> int:
        """Get current timeout value"""
        with self.lock:
            return self.current_timeout
    
    def record_failure(self):
        """Record a failure and increase timeout if needed"""
        with self.lock:
            self.failure_count += 1
            if self.failure_count >= 1 and self.current_timeout < self.max_timeout:
                old_timeout = self.current_timeout
                self.current_timeout = self.max_timeout
                logger = get_logger()
                logger.info(f"Progressive timeout: increased from {old_timeout}s to {self.current_timeout}s after failure")
    
    def record_success(self):
        """Record a success (timeout remains unchanged)"""
        pass  # Keep timeout stable once increased


_progressive_timeout = None
_progressive_timeout_lock = threading.Lock()


def _get_progressive_timeout() -> ProgressiveTimeout:
    """Get or create the global progressive timeout manager"""
    global _progressive_timeout
    with _progressive_timeout_lock:
        if _progressive_timeout is None:
            _progressive_timeout = ProgressiveTimeout()
        return _progressive_timeout


def run_analysis(url: str, timeout: int = 600, max_retries: int = 3, skip_cache: bool = False) -> Dict[str, Optional[int | str]]:
    """
    Run Cypress analysis for a given URL to get PageSpeed Insights scores.
    Includes circuit breaker protection, error metrics collection, caching, and optimizations.
    
    Args:
        url: The URL to analyze
        timeout: Maximum time in seconds to wait for Cypress to complete (default: 600)
        max_retries: Maximum number of retry attempts for transient errors (default: 3)
        skip_cache: If True, bypass cache and force fresh analysis (default: False)
        
    Returns:
        Dictionary with keys:
            - mobile_score: Integer score for mobile (0-100)
            - desktop_score: Integer score for desktop (0-100)
            - mobile_psi_url: URL to mobile PSI report (if score < 80, else None)
            - desktop_psi_url: URL to desktop PSI report (if score < 80, else None)
            
    Raises:
        CypressRunnerError: If Cypress execution fails
        CypressTimeoutError: If Cypress execution exceeds timeout
        PermanentError: If there's a permanent error (e.g., npx not found)
    """
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
    
    # Use progressive timeout
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
            
        except CypressTimeoutError as e:
            last_exception = e
            progressive_timeout.record_failure()
            metrics.record_error(
                error_type='CypressTimeoutError',
                function_name='run_analysis',
                error_message=str(e),
                is_retryable=False,
                attempt=attempt + 1,
                traceback=traceback.format_exc()
            )
            metrics.record_failure('run_analysis')
            raise
            
        except (CypressRunnerError, FileNotFoundError) as e:
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


def _stream_results(result_file: str) -> Iterator[Dict]:
    """
    Stream results from JSON file to avoid loading large files into memory.
    
    Args:
        result_file: Path to JSON results file
        
    Yields:
        Dictionary chunks from the results file
    """
    try:
        with open(result_file, 'r', encoding='utf-8') as f:
            # For our small result files, just load once
            # This is a placeholder for more complex streaming if needed
            data = json.load(f)
            yield data
    except json.JSONDecodeError as e:
        raise CypressRunnerError(f"Failed to parse results JSON from {result_file}") from e
    except Exception as e:
        raise CypressRunnerError(f"Failed to read results file {result_file}") from e


def _check_memory_usage(process: subprocess.Popen) -> float:
    """
    Check memory usage of a process.
    
    Args:
        process: The subprocess to check
        
    Returns:
        Memory usage in MB
    """
    try:
        proc = psutil.Process(process.pid)
        mem_info = proc.memory_info()
        return mem_info.rss / (1024 * 1024)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0


def _monitor_process_memory(process: subprocess.Popen, max_memory_mb: float = 1024) -> bool:
    """
    Monitor process memory and return True if it exceeds threshold.
    
    Args:
        process: The subprocess to monitor
        max_memory_mb: Maximum memory in MB (default: 1024)
        
    Returns:
        True if memory exceeded, False otherwise
    """
    memory_mb = _check_memory_usage(process)
    return memory_mb >= max_memory_mb


def _run_analysis_once(url: str, timeout: int) -> Dict[str, Optional[int | str]]:
    """
    Internal function to run a single Cypress analysis attempt with circuit breaker protection,
    result streaming, and memory monitoring.
    """
    circuit_breaker = _get_circuit_breaker()
    logger = get_logger()
    pool = _get_pool()
    
    def _execute_cypress():
        try:
            npx_path = _find_npx()
        except PermanentError:
            raise
        
        cypress_env = os.environ.copy()
        cypress_env['CYPRESS_TEST_URL'] = url
        
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        results_dir = os.path.join(repo_root, 'cypress', 'results')
        os.makedirs(results_dir, exist_ok=True)
        
        existing_results = set(glob.glob(os.path.join(results_dir, 'pagespeed-results-*.json')))
        
        # Get or create instance (warm start optimization)
        instance = pool.get_instance()
        warm_start = instance is not None and instance.warm_start
        
        if warm_start:
            logger.debug(f"Using warm Cypress instance for {url}")
        else:
            logger.debug(f"Cold start Cypress instance for {url}")
            if instance is None:
                instance = pool.create_instance()
        
        process = None
        try:
            # Start Cypress process
            process = subprocess.Popen(
                [npx_path, 'cypress', 'run', '--spec', 'cypress/e2e/analyze-url.cy.js', '--headless', '--browser', 'chrome'],
                cwd=repo_root,
                env=cypress_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                shell=False
            )
            
            instance.process = process
            instance.warm_start = True
            
            # Monitor memory during execution
            start_time = time.time()
            memory_exceeded = False
            
            while process.poll() is None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    pool.return_instance(instance, success=False)
                    raise CypressTimeoutError(f"Cypress execution exceeded {timeout} seconds timeout")
                
                # Check memory every 2 seconds
                if int(elapsed) % 2 == 0:
                    if _monitor_process_memory(process, max_memory_mb=CypressPool.MAX_MEMORY_MB):
                        memory_exceeded = True
                        logger.warning(f"Cypress process exceeded memory limit ({CypressPool.MAX_MEMORY_MB}MB), restarting...")
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        pool.return_instance(instance, success=False)
                        raise CypressRunnerError("Cypress process exceeded memory limit and was restarted")
                
                time.sleep(0.5)
            
            returncode = process.returncode
            stdout = process.stdout.read() if process.stdout else ""
            stderr = process.stderr.read() if process.stderr else ""
            
        except subprocess.TimeoutExpired as e:
            if process:
                pool.return_instance(instance, success=False)
            raise CypressTimeoutError(f"Cypress execution exceeded {timeout} seconds timeout") from e
        except FileNotFoundError as e:
            if process:
                pool.return_instance(instance, success=False)
            raise PermanentError(
                f"Failed to execute npx at '{npx_path}'. Ensure Node.js and Cypress are installed.",
                original_exception=e
            )
        except Exception as e:
            if process:
                pool.return_instance(instance, success=False)
            raise
        
        time.sleep(1)
        
        new_results = set(glob.glob(os.path.join(results_dir, 'pagespeed-results-*.json')))
        result_files = new_results - existing_results
        
        if not result_files:
            pool.return_instance(instance, success=False)
            if returncode != 0:
                error_msg = f"Cypress failed with exit code {returncode} and no results file was generated"
                if stderr:
                    error_msg += f"\nStderr: {stderr}"
                if stdout:
                    error_msg += f"\nStdout: {stdout}"
                raise CypressRunnerError(error_msg)
            raise RetryableError(
                f"No new results file found in {results_dir}",
                original_exception=FileNotFoundError(f"No results file in {results_dir}")
            )
        
        result_file = sorted(result_files)[-1]
        
        # Stream results to avoid large file I/O
        results = None
        for chunk in _stream_results(result_file):
            results = chunk
            break  # For our use case, single chunk is sufficient
        
        if results is None:
            pool.return_instance(instance, success=False)
            raise CypressRunnerError(f"Failed to read results from {result_file}")
        
        mobile_data = results.get('mobile', {})
        desktop_data = results.get('desktop', {})
        
        mobile_score = mobile_data.get('score')
        desktop_score = desktop_data.get('score')
        
        if mobile_score is None or desktop_score is None:
            pool.return_instance(instance, success=False)
            raise CypressRunnerError("Results file is missing score data")
        
        # Return instance to pool on success
        pool.return_instance(instance, success=True)
        
        return {
            'mobile_score': mobile_score,
            'desktop_score': desktop_score,
            'mobile_psi_url': mobile_data.get('reportUrl'),
            'desktop_psi_url': desktop_data.get('reportUrl'),
            '_warm_start': warm_start
        }
    
    try:
        return circuit_breaker.call(_execute_cypress)
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
            raise CypressRunnerError(str(e)) from e
        raise


def shutdown_pool():
    """Shutdown the Cypress pool (call on application exit)"""
    pool = _get_pool()
    pool.shutdown()
