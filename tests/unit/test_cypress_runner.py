import pytest
import os
import sys
import json
import subprocess
from unittest.mock import Mock, patch, MagicMock, mock_open

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))

from qa import cypress_runner


class TestFindNpx:
    @patch('shutil.which')
    @patch('sys.platform', 'win32')
    def test_find_npx_windows_cmd(self, mock_which):
        mock_which.side_effect = lambda cmd: 'C:\\npx.cmd' if cmd == 'npx.cmd' else None
        
        result = cypress_runner._find_npx()
        
        assert result == 'C:\\npx.cmd'
    
    @patch('shutil.which')
    @patch('sys.platform', 'win32')
    def test_find_npx_windows_exe(self, mock_which):
        mock_which.side_effect = lambda cmd: 'C:\\npx.exe' if cmd == 'npx' else None
        
        result = cypress_runner._find_npx()
        
        assert result == 'C:\\npx.exe'
    
    @patch('shutil.which')
    @patch('sys.platform', 'linux')
    def test_find_npx_linux(self, mock_which):
        mock_which.return_value = '/usr/bin/npx'
        
        result = cypress_runner._find_npx()
        
        assert result == '/usr/bin/npx'
        mock_which.assert_called_once_with('npx')
    
    @patch('shutil.which')
    def test_find_npx_not_found(self, mock_which):
        from tools.utils.exceptions import PermanentError
        mock_which.return_value = None
        
        with pytest.raises(PermanentError, match="npx not found"):
            cypress_runner._find_npx()


class TestRunAnalysis:
    @patch('qa.cypress_runner.get_cache_manager')
    @patch('qa.cypress_runner._run_analysis_once')
    def test_run_analysis_success_first_try(self, mock_run_once, mock_cache_mgr):
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_mgr.return_value = mock_cache
        
        mock_run_once.return_value = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        result = cypress_runner.run_analysis('https://example.com')
        
        assert result['mobile_score'] == 85
        assert result['desktop_score'] == 90
        assert mock_run_once.call_count == 1
    
    @patch('qa.cypress_runner.get_cache_manager')
    @patch('qa.cypress_runner._run_analysis_once')
    @patch('time.sleep')
    def test_run_analysis_retry_success(self, mock_sleep, mock_run_once, mock_cache_mgr):
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_mgr.return_value = mock_cache
        
        mock_run_once.side_effect = [
            cypress_runner.CypressRunnerError("Transient error"),
            {
                'mobile_score': 85,
                'desktop_score': 90,
                'mobile_psi_url': None,
                'desktop_psi_url': None
            }
        ]
        
        result = cypress_runner.run_analysis('https://example.com')
        
        assert result['mobile_score'] == 85
        assert mock_run_once.call_count == 2
        mock_sleep.assert_called_once_with(5)
    
    @patch('qa.cypress_runner.get_cache_manager')
    @patch('qa.cypress_runner._run_analysis_once')
    @patch('time.sleep')
    def test_run_analysis_max_retries_exceeded(self, mock_sleep, mock_run_once, mock_cache_mgr):
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_mgr.return_value = mock_cache
        
        mock_run_once.side_effect = cypress_runner.CypressRunnerError("Persistent error")
        
        with pytest.raises(cypress_runner.CypressRunnerError, match="Persistent error"):
            cypress_runner.run_analysis('https://example.com', max_retries=2)
        
        assert mock_run_once.call_count == 3
        assert mock_sleep.call_count == 2
    
    @patch('qa.cypress_runner.get_cache_manager')
    @patch('qa.cypress_runner._run_analysis_once')
    def test_run_analysis_timeout_no_retry(self, mock_run_once, mock_cache_mgr):
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_mgr.return_value = mock_cache
        
        mock_run_once.side_effect = cypress_runner.CypressTimeoutError("Timeout")
        
        with pytest.raises(cypress_runner.CypressTimeoutError):
            cypress_runner.run_analysis('https://example.com', max_retries=0)
        
        assert mock_run_once.call_count == 1


class TestRunAnalysisOnce:
    @patch('qa.cypress_runner._find_npx')
    @patch('subprocess.run')
    @patch('os.makedirs')
    @patch('glob.glob')
    @patch('builtins.open', new_callable=mock_open)
    def test_run_analysis_once_success(self, mock_file, mock_glob, mock_makedirs, mock_subprocess, mock_find_npx):
        mock_find_npx.return_value = '/usr/bin/npx'
        
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='Success',
            stderr=''
        )
        
        mock_glob.side_effect = [
            [],
            ['/path/to/results/pagespeed-results-12345.json']
        ]
        
        result_data = {
            'mobile': {'score': 85, 'reportUrl': None},
            'desktop': {'score': 90, 'reportUrl': None}
        }
        mock_file.return_value.read.return_value = json.dumps(result_data)
        
        with patch('json.load', return_value=result_data):
            result = cypress_runner._run_analysis_once('https://example.com', 600)
        
        assert result['mobile_score'] == 85
        assert result['desktop_score'] == 90
        assert result['mobile_psi_url'] is None
        assert result['desktop_psi_url'] is None
    
    @patch('qa.cypress_runner._find_npx')
    @patch('subprocess.run')
    @patch('os.makedirs')
    @patch('glob.glob')
    @patch('builtins.open', new_callable=mock_open)
    def test_run_analysis_once_with_failing_scores(self, mock_file, mock_glob, mock_makedirs, mock_subprocess, mock_find_npx):
        mock_find_npx.return_value = '/usr/bin/npx'
        
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='Success',
            stderr=''
        )
        
        mock_glob.side_effect = [
            [],
            ['/path/to/results/pagespeed-results-12345.json']
        ]
        
        result_data = {
            'mobile': {'score': 65, 'reportUrl': 'https://psi.mobile'},
            'desktop': {'score': 70, 'reportUrl': 'https://psi.desktop'}
        }
        mock_file.return_value.read.return_value = json.dumps(result_data)
        
        with patch('json.load', return_value=result_data):
            result = cypress_runner._run_analysis_once('https://example.com', 600)
        
        assert result['mobile_score'] == 65
        assert result['desktop_score'] == 70
        assert result['mobile_psi_url'] == 'https://psi.mobile'
        assert result['desktop_psi_url'] == 'https://psi.desktop'
    
    @patch('qa.cypress_runner._find_npx')
    @patch('subprocess.run')
    def test_run_analysis_once_timeout(self, mock_subprocess, mock_find_npx):
        mock_find_npx.return_value = '/usr/bin/npx'
        mock_subprocess.side_effect = subprocess.TimeoutExpired('npx', 600)
        
        with pytest.raises(cypress_runner.CypressTimeoutError, match="exceeded 600 seconds"):
            cypress_runner._run_analysis_once('https://example.com', 600)
    
    @patch('qa.cypress_runner._find_npx')
    def test_run_analysis_once_npx_not_found(self, mock_find_npx):
        mock_find_npx.side_effect = cypress_runner.CypressRunnerError("npx not found")
        
        with pytest.raises(cypress_runner.CypressRunnerError):
            cypress_runner._run_analysis_once('https://example.com', 600)
    
    @patch('qa.cypress_runner._find_npx')
    @patch('subprocess.run')
    @patch('os.makedirs')
    @patch('glob.glob')
    def test_run_analysis_once_no_results_file(self, mock_glob, mock_makedirs, mock_subprocess, mock_find_npx):
        from tools.utils.exceptions import RetryableError
        mock_find_npx.return_value = '/usr/bin/npx'
        
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='Success',
            stderr=''
        )
        
        mock_glob.side_effect = [[], []]
        
        with pytest.raises(RetryableError, match="No new results file found"):
            cypress_runner._run_analysis_once('https://example.com', 600)
    
    @patch('qa.cypress_runner._find_npx')
    @patch('subprocess.run')
    @patch('os.makedirs')
    @patch('glob.glob')
    def test_run_analysis_once_cypress_failed_no_results(self, mock_glob, mock_makedirs, mock_subprocess, mock_find_npx):
        mock_find_npx.return_value = '/usr/bin/npx'
        
        mock_subprocess.return_value = Mock(
            returncode=1,
            stdout='Test failed',
            stderr='Error output'
        )
        
        mock_glob.side_effect = [[], []]
        
        with pytest.raises(cypress_runner.CypressRunnerError, match="Cypress failed with exit code 1"):
            cypress_runner._run_analysis_once('https://example.com', 600)
    
    @patch('qa.cypress_runner._find_npx')
    @patch('subprocess.run')
    @patch('os.makedirs')
    @patch('glob.glob')
    @patch('builtins.open', new_callable=mock_open)
    def test_run_analysis_once_invalid_json(self, mock_file, mock_glob, mock_makedirs, mock_subprocess, mock_find_npx):
        mock_find_npx.return_value = '/usr/bin/npx'
        
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='Success',
            stderr=''
        )
        
        mock_glob.side_effect = [
            [],
            ['/path/to/results/pagespeed-results-12345.json']
        ]
        
        with patch('json.load', side_effect=json.JSONDecodeError("Invalid", "", 0)):
            with pytest.raises(cypress_runner.CypressRunnerError, match="Failed to parse results JSON"):
                cypress_runner._run_analysis_once('https://example.com', 600)
    
    @patch('qa.cypress_runner._find_npx')
    @patch('subprocess.run')
    @patch('os.makedirs')
    @patch('glob.glob')
    @patch('builtins.open', new_callable=mock_open)
    def test_run_analysis_once_missing_score_data(self, mock_file, mock_glob, mock_makedirs, mock_subprocess, mock_find_npx):
        mock_find_npx.return_value = '/usr/bin/npx'
        
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='Success',
            stderr=''
        )
        
        mock_glob.side_effect = [
            [],
            ['/path/to/results/pagespeed-results-12345.json']
        ]
        
        result_data = {
            'mobile': {'score': 85},
            'desktop': {}
        }
        
        with patch('json.load', return_value=result_data):
            with pytest.raises(cypress_runner.CypressRunnerError, match="missing score data"):
                cypress_runner._run_analysis_once('https://example.com', 600)
    
    @patch('qa.cypress_runner._get_circuit_breaker')
    @patch('qa.cypress_runner._find_npx')
    @patch('subprocess.run')
    @patch('os.makedirs')
    @patch('os.environ', {})
    def test_run_analysis_once_sets_environment(self, mock_makedirs, mock_subprocess, mock_find_npx, mock_get_cb):
        mock_cb = Mock()
        mock_get_cb.return_value = mock_cb
        mock_find_npx.return_value = '/usr/bin/npx'
        
        captured_env = {}
        
        def capture_env(*args, **kwargs):
            captured_env.update(kwargs.get('env', {}))
            raise subprocess.TimeoutExpired('npx', 1)
        
        def mock_call(func):
            try:
                return func()
            except subprocess.TimeoutExpired as e:
                raise cypress_runner.CypressTimeoutError(f"Cypress execution exceeded 1 seconds timeout") from e
        
        mock_cb.call.side_effect = mock_call
        mock_subprocess.side_effect = capture_env
        
        try:
            cypress_runner._run_analysis_once('https://example.com', 1)
        except cypress_runner.CypressTimeoutError:
            pass
        
        assert captured_env.get('CYPRESS_TEST_URL') == 'https://example.com'


class TestCypressExceptions:
    def test_cypress_runner_error(self):
        error = cypress_runner.CypressRunnerError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_cypress_timeout_error(self):
        error = cypress_runner.CypressTimeoutError("Timeout error")
        assert str(error) == "Timeout error"
        assert isinstance(error, cypress_runner.CypressRunnerError)
