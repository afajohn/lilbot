import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import run_audit


class TestProcessUrl:
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_process_url_passing_scores(self, mock_batch_write, mock_run_analysis, mock_google_service):
        mock_run_analysis.return_value = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        url_data = (2, 'https://example.com', None, None, False)
        processed_count = {'count': 0, 'lock': __import__('threading').Lock()}
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_google_service,
            600,
            1,
            processed_count
        )
        
        assert result['mobile_score'] == 85
        assert result['desktop_score'] == 90
        assert result['url'] == 'https://example.com'
        assert 'error' not in result
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 2
        assert (2, 'F', 'passed') in updates
        assert (2, 'G', 'passed') in updates
    
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_process_url_failing_scores(self, mock_batch_write, mock_run_analysis, mock_google_service):
        mock_run_analysis.return_value = {
            'mobile_score': 65,
            'desktop_score': 70,
            'mobile_psi_url': 'https://psi.mobile',
            'desktop_psi_url': 'https://psi.desktop'
        }
        
        url_data = (2, 'https://example.com', None, None, False)
        processed_count = {'count': 0, 'lock': __import__('threading').Lock()}
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_google_service,
            600,
            1,
            processed_count
        )
        
        assert result['mobile_score'] == 65
        assert result['desktop_score'] == 70
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 2
        assert (2, 'F', 'https://psi.mobile') in updates
        assert (2, 'G', 'https://psi.desktop') in updates
    
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_process_url_skip_existing_mobile(self, mock_batch_write, mock_run_analysis, mock_google_service):
        mock_run_analysis.return_value = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        url_data = (2, 'https://example.com', 'https://existing.mobile', None, False)
        processed_count = {'count': 0, 'lock': __import__('threading').Lock()}
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_google_service,
            600,
            1,
            processed_count
        )
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 1
        assert (2, 'G', 'passed') in updates
        assert not any(update[1] == 'F' for update in updates)
    
    def test_process_url_should_skip(self, mock_google_service):
        url_data = (2, 'https://example.com', None, None, True)
        processed_count = {'count': 0, 'lock': __import__('threading').Lock()}
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_google_service,
            600,
            1,
            processed_count
        )
        
        assert result['skipped'] is True
        assert result['url'] == 'https://example.com'
    
    def test_process_url_both_columns_filled(self, mock_google_service):
        url_data = (2, 'https://example.com', 'https://psi.mobile', 'https://psi.desktop', False)
        processed_count = {'count': 0, 'lock': __import__('threading').Lock()}
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_google_service,
            600,
            1,
            processed_count
        )
        
        assert result['skipped'] is True
    
    @patch('qa.playwright_runner.run_analysis')
    def test_process_url_playwright_timeout(self, mock_run_analysis, mock_google_service):
        from qa.playwright_runner import PlaywrightAnalysisTimeoutError
        mock_run_analysis.side_effect = PlaywrightAnalysisTimeoutError("Timeout after 600 seconds")
        
        url_data = (2, 'https://example.com', None, None, False)
        processed_count = {'count': 0, 'lock': __import__('threading').Lock()}
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_google_service,
            600,
            1,
            processed_count
        )
        
        assert 'error' in result
        assert 'Timeout' in result['error']
    
    @patch('qa.playwright_runner.run_analysis')
    def test_process_url_playwright_error(self, mock_run_analysis, mock_google_service):
        from qa.playwright_runner import PlaywrightRunnerError
        mock_run_analysis.side_effect = PlaywrightRunnerError("Playwright failed")
        
        url_data = (2, 'https://example.com', None, None, False)
        processed_count = {'count': 0, 'lock': __import__('threading').Lock()}
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_google_service,
            600,
            1,
            processed_count
        )
        
        assert 'error' in result
        assert 'Playwright failed' in result['error']
    
    @patch('qa.playwright_runner.run_analysis')
    def test_process_url_unexpected_error(self, mock_run_analysis, mock_google_service):
        mock_run_analysis.side_effect = Exception("Unexpected error")
        
        url_data = (2, 'https://example.com', None, None, False)
        processed_count = {'count': 0, 'lock': __import__('threading').Lock()}
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_google_service,
            600,
            1,
            processed_count
        )
        
        assert 'error' in result
        assert 'Unexpected error' in result['error']
    
    def test_process_url_shutdown_event(self, mock_google_service):
        url_data = (2, 'https://example.com', None, None, False)
        processed_count = {'count': 0, 'lock': __import__('threading').Lock()}
        
        run_audit.shutdown_event.set()
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_google_service,
            600,
            1,
            processed_count
        )
        
        assert result['skipped'] is True
        assert result.get('shutdown') is True
        
        run_audit.shutdown_event.clear()


class TestMainFunction:
    @patch('sys.argv', ['run_audit.py', '--tab', 'TestTab'])
    @patch('os.path.exists', return_value=True)
    @patch('sheets.sheets_client.authenticate')
    @patch('sheets.sheets_client.read_urls')
    @patch('run_audit.process_url')
    @patch('utils.logger.setup_logger')
    def test_main_success(self, mock_logger, mock_process, mock_read_urls, mock_auth, mock_exists):
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        mock_read_urls.return_value = [
            (2, 'https://example.com', None, None, False),
        ]
        
        mock_process.return_value = {
            'row': 2,
            'url': 'https://example.com',
            'mobile_score': 85,
            'desktop_score': 90
        }
        
        run_audit.main()
        
        mock_auth.assert_called_once()
        mock_read_urls.assert_called_once()
    
    @patch('sys.argv', ['run_audit.py', '--tab', 'TestTab'])
    @patch('os.path.exists', return_value=False)
    @patch('utils.logger.setup_logger')
    def test_main_service_account_not_found(self, mock_logger, mock_exists):
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        with pytest.raises(SystemExit) as exc_info:
            run_audit.main()
        
        assert exc_info.value.code == 1
        mock_log.error.assert_called()
    
    @patch('sys.argv', ['run_audit.py', '--tab', 'TestTab'])
    @patch('os.path.exists', return_value=True)
    @patch('sheets.sheets_client.authenticate')
    @patch('utils.logger.setup_logger')
    def test_main_authentication_failure(self, mock_logger, mock_auth, mock_exists):
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        mock_auth.side_effect = FileNotFoundError("Service account not found")
        
        with pytest.raises(SystemExit) as exc_info:
            run_audit.main()
        
        assert exc_info.value.code == 1
    
    @patch('sys.argv', ['run_audit.py', '--tab', 'TestTab'])
    @patch('os.path.exists', return_value=True)
    @patch('sheets.sheets_client.authenticate')
    @patch('sheets.sheets_client.read_urls')
    @patch('utils.logger.setup_logger')
    def test_main_no_urls_found(self, mock_logger, mock_read_urls, mock_auth, mock_exists):
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        mock_read_urls.return_value = []
        
        with pytest.raises(SystemExit) as exc_info:
            run_audit.main()
        
        assert exc_info.value.code == 0
        assert any("No URLs found" in str(call) for call in mock_log.info.call_args_list)
    
    @patch('sys.argv', ['run_audit.py', '--tab', 'TestTab', '--concurrency', '10'])
    @patch('utils.logger.setup_logger')
    def test_main_invalid_concurrency(self, mock_logger):
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        with pytest.raises(SystemExit) as exc_info:
            run_audit.main()
        
        assert exc_info.value.code == 1
    
    @patch('sys.argv', ['run_audit.py', '--tab', 'TestTab', '--timeout', '1200'])
    @patch('os.path.exists', return_value=True)
    @patch('sheets.sheets_client.authenticate')
    @patch('sheets.sheets_client.read_urls')
    @patch('run_audit.process_url')
    @patch('utils.logger.setup_logger')
    def test_main_custom_timeout(self, mock_logger, mock_process, mock_read_urls, mock_auth, mock_exists):
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        mock_read_urls.return_value = [
            (2, 'https://example.com', None, None, False),
        ]
        
        mock_process.return_value = {
            'row': 2,
            'url': 'https://example.com',
            'mobile_score': 85,
            'desktop_score': 90
        }
        
        run_audit.main()
        
        assert mock_process.call_args[0][4] == 1200


class TestSignalHandler:
    def test_signal_handler_sets_shutdown_event(self):
        run_audit.shutdown_event.clear()
        
        with patch('utils.logger.get_logger') as mock_get_logger:
            mock_log = Mock()
            mock_get_logger.return_value = mock_log
            
            run_audit.signal_handler(None, None)
        
        assert run_audit.shutdown_event.is_set()
        
        run_audit.shutdown_event.clear()


class TestConstants:
    def test_default_constants(self):
        assert run_audit.DEFAULT_SPREADSHEET_ID == '1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I'
        assert run_audit.SERVICE_ACCOUNT_FILE == 'service-account.json'
        assert run_audit.MOBILE_COLUMN == 'F'
        assert run_audit.DESKTOP_COLUMN == 'G'
        assert run_audit.SCORE_THRESHOLD == 80
        assert run_audit.DEFAULT_CONCURRENCY == 3
