import subprocess
import json
import os
import time
import glob
import shutil
import sys
from typing import Dict, Optional


class CypressRunnerError(Exception):
    pass


class CypressTimeoutError(CypressRunnerError):
    pass


def _find_npx() -> str:
    """
    Find the npx executable, handling Windows vs Unix differences.
    
    Returns:
        Path to npx executable
        
    Raises:
        CypressRunnerError: If npx cannot be found
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
    
    raise CypressRunnerError(
        "npx not found. Ensure Node.js is installed and npx is available in PATH. "
        "Try running 'npm install -g npm' to ensure npx is properly installed."
    )


def run_analysis(url: str, timeout: int = 300, max_retries: int = 2) -> Dict[str, Optional[int | str]]:
    """
    Run Cypress analysis for a given URL to get PageSpeed Insights scores.
    
    Args:
        url: The URL to analyze
        timeout: Maximum time in seconds to wait for Cypress to complete (default: 300)
        max_retries: Maximum number of retry attempts for transient errors (default: 2)
        
    Returns:
        Dictionary with keys:
            - mobile_score: Integer score for mobile (0-100)
            - desktop_score: Integer score for desktop (0-100)
            - mobile_psi_url: URL to mobile PSI report (if score < 80, else None)
            - desktop_psi_url: URL to desktop PSI report (if score < 80, else None)
            
    Raises:
        CypressRunnerError: If Cypress execution fails
        CypressTimeoutError: If Cypress execution exceeds timeout
        FileNotFoundError: If results file cannot be found
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return _run_analysis_once(url, timeout)
        except (CypressRunnerError, FileNotFoundError) as e:
            last_exception = e
            if attempt < max_retries:
                time.sleep(2)
                continue
            raise
        except CypressTimeoutError:
            raise
    
    if last_exception:
        raise last_exception


def _run_analysis_once(url: str, timeout: int) -> Dict[str, Optional[int | str]]:
    """
    Internal function to run a single Cypress analysis attempt.
    """
    try:
        npx_path = _find_npx()
    except CypressRunnerError:
        raise
    
    cypress_env = os.environ.copy()
    cypress_env['CYPRESS_TEST_URL'] = url
    
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    results_dir = os.path.join(repo_root, 'cypress', 'results')
    os.makedirs(results_dir, exist_ok=True)
    
    existing_results = set(glob.glob(os.path.join(results_dir, 'pagespeed-results-*.json')))
    
    try:
        result = subprocess.run(
            [npx_path, 'cypress', 'run', '--spec', 'cypress/e2e/analyze-url.cy.js'],
            cwd=repo_root,
            env=cypress_env,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            shell=False
        )
        
        if result.returncode != 0:
            error_msg = f"Cypress failed with exit code {result.returncode}"
            if result.stderr:
                error_msg += f"\nStderr: {result.stderr}"
            if result.stdout:
                error_msg += f"\nStdout: {result.stdout}"
            raise CypressRunnerError(error_msg)
            
    except subprocess.TimeoutExpired as e:
        raise CypressTimeoutError(f"Cypress execution exceeded {timeout} seconds timeout") from e
    except FileNotFoundError as e:
        raise CypressRunnerError(f"Failed to execute npx at '{npx_path}'. Ensure Node.js and Cypress are installed.") from e
    
    time.sleep(1)
    
    new_results = set(glob.glob(os.path.join(results_dir, 'pagespeed-results-*.json')))
    result_files = new_results - existing_results
    
    if not result_files:
        raise FileNotFoundError(f"No new results file found in {results_dir}")
    
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
    
    return {
        'mobile_score': mobile_data.get('score'),
        'desktop_score': desktop_data.get('score'),
        'mobile_psi_url': mobile_data.get('reportUrl'),
        'desktop_psi_url': desktop_data.get('reportUrl')
    }
