import subprocess
import json
import os
import time
import glob
import shutil
import sys
import traceback
from typing import Dict, Optional

from tools.utils.exceptions import RetryableError, PermanentError
from tools.utils.circuit_breaker import CircuitBreaker
from tools.utils.error_metrics import get_global_metrics
from tools.utils.logger import get_logger
from tools.cache.cache_manager import get_cache_manager


class CypressRunnerError(Exception):
    pass


class CypressTimeoutError(CypressRunnerError):
    pass


_circuit_breaker = None
_circuit_breaker_lock = __import__('threading').Lock()


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


def run_analysis(url: str, timeout: int = 600, max_retries: int = 3, skip_cache: bool = False) -> Dict[str, Optional[int | str]]:
    """
    Run Cypress analysis for a given URL to get PageSpeed Insights scores.
    Includes circuit breaker protection, error metrics collection, and caching.
    
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
    
    last_exception = None
    was_retried = False
    
    for attempt in range(max_retries + 1):
        try:
            result = _run_analysis_once(url, timeout)
            metrics.record_success('run_analysis', was_retried=was_retried)
            metrics_collector.record_api_call_cypress()
            
            if not skip_cache:
                cache_manager.set(url, result)
            
            result['_from_cache'] = False
            return result
            
        except PermanentError:
            metrics.record_failure('run_analysis')
            raise
            
        except CypressTimeoutError as e:
            last_exception = e
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


def _run_analysis_once(url: str, timeout: int) -> Dict[str, Optional[int | str]]:
    """
    Internal function to run a single Cypress analysis attempt with circuit breaker protection.
    """
    circuit_breaker = _get_circuit_breaker()
    logger = get_logger()
    
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
        
        try:
            result = subprocess.run(
                [npx_path, 'cypress', 'run', '--spec', 'cypress/e2e/analyze-url.cy.js', '--headless', '--browser', 'chrome'],
                cwd=repo_root,
                env=cypress_env,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout,
                shell=False
            )
            
        except subprocess.TimeoutExpired as e:
            raise CypressTimeoutError(f"Cypress execution exceeded {timeout} seconds timeout") from e
        except FileNotFoundError as e:
            raise PermanentError(
                f"Failed to execute npx at '{npx_path}'. Ensure Node.js and Cypress are installed.",
                original_exception=e
            )
        
        time.sleep(1)
        
        new_results = set(glob.glob(os.path.join(results_dir, 'pagespeed-results-*.json')))
        result_files = new_results - existing_results
        
        if not result_files:
            if result.returncode != 0:
                error_msg = f"Cypress failed with exit code {result.returncode} and no results file was generated"
                if result.stderr:
                    error_msg += f"\nStderr: {result.stderr}"
                if result.stdout:
                    error_msg += f"\nStdout: {result.stdout}"
                raise CypressRunnerError(error_msg)
            raise RetryableError(
                f"No new results file found in {results_dir}",
                original_exception=FileNotFoundError(f"No results file in {results_dir}")
            )
        
        result_file = sorted(result_files)[-1]
        
        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
        except json.JSONDecodeError as e:
            raise CypressRunnerError(f"Failed to parse results JSON from {result_file}") from e
        except Exception as e:
            raise CypressRunnerError(f"Failed to read results file {result_file}") from e
        
        mobile_data = results.get('mobile', {})
        desktop_data = results.get('desktop', {})
        
        mobile_score = mobile_data.get('score')
        desktop_score = desktop_data.get('score')
        
        if mobile_score is None or desktop_score is None:
            raise CypressRunnerError("Results file is missing score data")
        
        return {
            'mobile_score': mobile_score,
            'desktop_score': desktop_score,
            'mobile_psi_url': mobile_data.get('reportUrl'),
            'desktop_psi_url': desktop_data.get('reportUrl')
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
