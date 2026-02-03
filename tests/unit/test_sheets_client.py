import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock, call
from googleapiclient.errors import HttpError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))

from sheets import sheets_client


class TestAuthenticate:
    @patch('sheets.sheets_client.service_account.Credentials.from_service_account_file')
    @patch('sheets.sheets_client.build')
    def test_authenticate_success(self, mock_build, mock_from_file, temp_service_account_file):
        mock_credentials = Mock()
        mock_from_file.return_value = mock_credentials
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        sheets_client._service_cache.clear()
        
        service = sheets_client.authenticate(temp_service_account_file)
        
        assert service == mock_service
        mock_from_file.assert_called_once_with(
            temp_service_account_file,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        mock_build.assert_called_once_with('sheets', 'v4', credentials=mock_credentials)
    
    def test_authenticate_file_not_found(self):
        sheets_client._service_cache.clear()
        
        with pytest.raises(FileNotFoundError, match="Service account file not found"):
            sheets_client.authenticate('nonexistent.json')
    
    @patch('sheets.sheets_client.service_account.Credentials.from_service_account_file')
    def test_authenticate_invalid_credentials(self, mock_from_file, temp_service_account_file):
        mock_from_file.side_effect = Exception("Invalid JSON")
        sheets_client._service_cache.clear()
        
        with pytest.raises(ValueError, match="Invalid service account file"):
            sheets_client.authenticate(temp_service_account_file)
    
    @patch('sheets.sheets_client.service_account.Credentials.from_service_account_file')
    @patch('sheets.sheets_client.build')
    def test_authenticate_caching(self, mock_build, mock_from_file, temp_service_account_file):
        mock_credentials = Mock()
        mock_from_file.return_value = mock_credentials
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        sheets_client._service_cache.clear()
        
        service1 = sheets_client.authenticate(temp_service_account_file)
        service2 = sheets_client.authenticate(temp_service_account_file)
        
        assert service1 == service2
        assert mock_from_file.call_count == 1
        assert mock_build.call_count == 1


class TestListTabs:
    def test_list_tabs_success(self, mock_google_service):
        spreadsheet_data = {
            'sheets': [
                {'properties': {'title': 'Tab1'}},
                {'properties': {'title': 'Tab2'}},
                {'properties': {'title': 'Tab3'}},
            ]
        }
        
        mock_google_service.spreadsheets().get().execute.return_value = spreadsheet_data
        
        with patch('sheets.sheets_client._execute_with_retry', side_effect=lambda f: f()):
            tabs = sheets_client.list_tabs('test-spreadsheet-id', service=mock_google_service)
        
        assert tabs == ['Tab1', 'Tab2', 'Tab3']
    
    def test_list_tabs_not_found(self, mock_google_service):
        error_response = Mock()
        error_response.status = 404
        error = HttpError(resp=error_response, content=b'Not Found')
        
        mock_google_service.spreadsheets().get().execute.side_effect = error
        
        with patch('sheets.sheets_client._execute_with_retry', side_effect=error):
            with pytest.raises(ValueError, match="Spreadsheet not found"):
                sheets_client.list_tabs('invalid-id', service=mock_google_service)
    
    def test_list_tabs_permission_denied(self, mock_google_service):
        error_response = Mock()
        error_response.status = 403
        error = HttpError(resp=error_response, content=b'Forbidden')
        
        mock_google_service.spreadsheets().get().execute.side_effect = error
        
        with patch('sheets.sheets_client._execute_with_retry', side_effect=error):
            with pytest.raises(PermissionError, match="Access denied"):
                sheets_client.list_tabs('test-id', service=mock_google_service)
    
    @patch('sheets.sheets_client.authenticate')
    def test_list_tabs_with_service_account_file(self, mock_auth):
        mock_service = Mock()
        mock_auth.return_value = mock_service
        spreadsheet_data = {'sheets': [{'properties': {'title': 'Tab1'}}]}
        mock_service.spreadsheets().get().execute.return_value = spreadsheet_data
        
        with patch('sheets.sheets_client._execute_with_retry', side_effect=lambda f: f()):
            tabs = sheets_client.list_tabs('test-id', service_account_file='test.json')
        
        mock_auth.assert_called_once_with('test.json')
        assert tabs == ['Tab1']


class TestReadUrls:
    def test_read_urls_success(self, mock_google_service):
        values_data = {
            'values': [
                ['https://example.com'],
                ['https://google.com'],
                ['https://github.com', '', '', '', '', 'passed', ''],
            ]
        }
        
        spreadsheet_data = {
            'sheets': [{
                'data': [{
                    'rowData': [
                        {'values': [{}] * 7},
                        {'values': [{}] * 7},
                        {'values': [{}] * 7},
                    ]
                }]
            }]
        }
        
        mock_sheets = mock_google_service.spreadsheets()
        mock_sheets.values().get().execute.return_value = values_data
        mock_sheets.get().execute.return_value = spreadsheet_data
        
        def execute_with_retry_side_effect(func):
            result = func()
            if isinstance(result, tuple):
                return result
            return result
        
        with patch('sheets.sheets_client._execute_with_retry', side_effect=execute_with_retry_side_effect):
            urls = sheets_client.read_urls('test-id', 'Sheet1', service=mock_google_service)
        
        assert len(urls) == 3
        assert urls[0] == (2, 'https://example.com', None, None, False)
        assert urls[1] == (3, 'https://google.com', None, None, False)
    
    def test_read_urls_with_existing_psi_urls(self, mock_google_service):
        values_data = {
            'values': [
                ['https://example.com', '', '', '', '', 'https://psi.mobile', 'https://psi.desktop'],
            ]
        }
        
        spreadsheet_data = {
            'sheets': [{
                'data': [{
                    'rowData': [{'values': [{}] * 7}]
                }]
            }]
        }
        
        mock_sheets = mock_google_service.spreadsheets()
        mock_sheets.values().get().execute.return_value = values_data
        mock_sheets.get().execute.return_value = spreadsheet_data
        
        def execute_with_retry_side_effect(func):
            result = func()
            if isinstance(result, tuple):
                return result
            return result
        
        with patch('sheets.sheets_client._execute_with_retry', side_effect=execute_with_retry_side_effect):
            urls = sheets_client.read_urls('test-id', 'Sheet1', service=mock_google_service)
        
        assert len(urls) == 1
        assert urls[0] == (2, 'https://example.com', 'https://psi.mobile', 'https://psi.desktop', False)
    
    def test_read_urls_empty_spreadsheet(self, mock_google_service):
        values_data = {'values': []}
        spreadsheet_data = {'sheets': [{'data': [{'rowData': []}]}]}
        
        mock_sheets = mock_google_service.spreadsheets()
        mock_sheets.values().get().execute.return_value = values_data
        mock_sheets.get().execute.return_value = spreadsheet_data
        
        def execute_with_retry_side_effect(func):
            result = func()
            if isinstance(result, tuple):
                return result
            return result
        
        with patch('sheets.sheets_client._execute_with_retry', side_effect=execute_with_retry_side_effect):
            urls = sheets_client.read_urls('test-id', 'Sheet1', service=mock_google_service)
        
        assert urls == []
    
    def test_read_urls_tab_not_found(self, mock_google_service):
        error_response = Mock()
        error_response.status = 404
        error = HttpError(resp=error_response, content=b'Not Found')
        
        mock_sheets = mock_google_service.spreadsheets()
        mock_sheets.values().get().execute.side_effect = error
        
        with patch('sheets.sheets_client.list_tabs', return_value=['Sheet1', 'Sheet2']):
            with patch('sheets.sheets_client._execute_with_retry', side_effect=error):
                with pytest.raises(ValueError, match="Tab 'InvalidTab' not found"):
                    sheets_client.read_urls('test-id', 'InvalidTab', service=mock_google_service)
    
    @patch('sheets.sheets_client.authenticate')
    def test_read_urls_with_service_account_file(self, mock_auth, mock_google_service):
        mock_auth.return_value = mock_google_service
        values_data = {'values': [['https://example.com']]}
        spreadsheet_data = {'sheets': [{'data': [{'rowData': [{'values': [{}] * 7}]}]}]}
        
        mock_sheets = mock_google_service.spreadsheets()
        mock_sheets.values().get().execute.return_value = values_data
        mock_sheets.get().execute.return_value = spreadsheet_data
        
        def execute_with_retry_side_effect(func):
            result = func()
            if isinstance(result, tuple):
                return result
            return result
        
        with patch('sheets.sheets_client._execute_with_retry', side_effect=execute_with_retry_side_effect):
            urls = sheets_client.read_urls('test-id', 'Sheet1', service_account_file='test.json')
        
        mock_auth.assert_called_once_with('test.json')


class TestCheckSkipConditions:
    def test_skip_with_passed_in_mobile(self):
        row_data = []
        row_values = ['https://example.com', '', '', '', '', 'passed', '']
        
        result = sheets_client._check_skip_conditions(row_data, 0, row_values)
        
        assert result is True
    
    def test_skip_with_passed_in_desktop(self):
        row_data = []
        row_values = ['https://example.com', '', '', '', '', '', 'passed']
        
        result = sheets_client._check_skip_conditions(row_data, 0, row_values)
        
        assert result is True
    
    def test_skip_with_green_background(self):
        row_data = [{
            'values': [
                {}, {}, {}, {}, {},
                {
                    'effectiveFormat': {
                        'backgroundColor': {
                            'red': 0xb7 / 255,
                            'green': 0xe1 / 255,
                            'blue': 0xcd / 255
                        }
                    }
                },
                {}
            ]
        }]
        row_values = ['https://example.com', '', '', '', '', '', '']
        
        result = sheets_client._check_skip_conditions(row_data, 0, row_values)
        
        assert result is True
    
    def test_no_skip(self):
        row_data = [{'values': [{}] * 7}]
        row_values = ['https://example.com', '', '', '', '', '', '']
        
        result = sheets_client._check_skip_conditions(row_data, 0, row_values)
        
        assert result is False


class TestHasTargetBackgroundColor:
    def test_has_target_color(self):
        cell = {
            'effectiveFormat': {
                'backgroundColor': {
                    'red': 0xb7 / 255,
                    'green': 0xe1 / 255,
                    'blue': 0xcd / 255
                }
            }
        }
        
        result = sheets_client._has_target_background_color(cell)
        
        assert result is True
    
    def test_different_color(self):
        cell = {
            'effectiveFormat': {
                'backgroundColor': {
                    'red': 1.0,
                    'green': 0.0,
                    'blue': 0.0
                }
            }
        }
        
        result = sheets_client._has_target_background_color(cell)
        
        assert result is False
    
    def test_no_background_color(self):
        cell = {'effectiveFormat': {}}
        
        result = sheets_client._has_target_background_color(cell)
        
        assert result is False
    
    def test_no_format(self):
        cell = {}
        
        result = sheets_client._has_target_background_color(cell)
        
        assert result is False


class TestWritePsiUrl:
    def test_write_psi_url_success(self, mock_google_service):
        mock_sheets = mock_google_service.spreadsheets()
        mock_update = Mock()
        mock_update.execute.return_value = {'updatedCells': 1}
        mock_sheets.values().update.return_value = mock_update
        
        with patch('sheets.sheets_client._execute_with_retry', side_effect=lambda f: f()):
            sheets_client.write_psi_url(
                'test-id',
                'Sheet1',
                2,
                'F',
                'https://psi.url',
                service=mock_google_service
            )
        
        mock_sheets.values().update.assert_called()
        call_args = mock_sheets.values().update.call_args
        assert call_args[1]['range'] == 'Sheet1!F2'
        assert call_args[1]['body']['values'] == [['https://psi.url']]
    
    @patch('sheets.sheets_client.authenticate')
    def test_write_psi_url_with_service_account_file(self, mock_auth, mock_google_service):
        mock_auth.return_value = mock_google_service
        mock_sheets = mock_google_service.spreadsheets()
        mock_sheets.values().update().execute.return_value = {'updatedCells': 1}
        
        with patch('sheets.sheets_client._execute_with_retry', side_effect=lambda f: f()):
            sheets_client.write_psi_url(
                'test-id',
                'Sheet1',
                2,
                'F',
                'https://psi.url',
                service_account_file='test.json'
            )
        
        mock_auth.assert_called_once_with('test.json')


class TestBatchWritePsiUrls:
    def test_batch_write_success(self, mock_google_service):
        mock_sheets = mock_google_service.spreadsheets()
        mock_batch_update = Mock()
        mock_batch_update.execute.return_value = {'totalUpdatedCells': 3}
        mock_sheets.values().batchUpdate.return_value = mock_batch_update
        
        updates = [
            (2, 'F', 'https://psi.mobile/1'),
            (2, 'G', 'https://psi.desktop/1'),
            (3, 'F', 'passed'),
        ]
        
        with patch('sheets.sheets_client._execute_with_retry', side_effect=lambda f: f()):
            sheets_client.batch_write_psi_urls(
                'test-id',
                'Sheet1',
                updates,
                service=mock_google_service
            )
        
        mock_sheets.values().batchUpdate.assert_called()
        call_args = mock_sheets.values().batchUpdate.call_args
        body = call_args[1]['body']
        assert len(body['data']) == 3
        assert body['data'][0]['range'] == 'Sheet1!F2'
        assert body['data'][0]['values'] == [['https://psi.mobile/1']]
    
    def test_batch_write_empty_updates(self, mock_google_service):
        sheets_client.batch_write_psi_urls(
            'test-id',
            'Sheet1',
            [],
            service=mock_google_service
        )
        
        mock_google_service.spreadsheets().values().batchUpdate.assert_not_called()
    
    def test_batch_write_chunking(self, mock_google_service):
        mock_sheets = mock_google_service.spreadsheets()
        mock_batch_update = Mock()
        mock_batch_update.execute.return_value = {'totalUpdatedCells': 101}
        mock_sheets.values().batchUpdate.return_value = mock_batch_update
        
        updates = [(i, 'F', f'url-{i}') for i in range(2, 103)]
        
        with patch('sheets.sheets_client._execute_with_retry', side_effect=lambda f: f()):
            sheets_client.batch_write_psi_urls(
                'test-id',
                'Sheet1',
                updates,
                service=mock_google_service
            )
        
        assert mock_sheets.values().batchUpdate.call_count >= 2


class TestRateLimiter:
    def test_rate_limiter_acquire(self):
        limiter = sheets_client.RateLimiter(max_tokens=10, refill_period=1.0)
        
        limiter.acquire(5)
        
        assert limiter.tokens <= 5
    
    def test_rate_limiter_refill(self):
        import time
        limiter = sheets_client.RateLimiter(max_tokens=10, refill_period=0.1)
        
        limiter.acquire(10)
        time.sleep(0.15)
        limiter.acquire(1)
        
        assert True


class TestExecuteWithRetry:
    def test_execute_with_retry_success_first_try(self):
        mock_func = Mock(return_value='success')
        
        with patch('sheets.sheets_client._rate_limiter.acquire'):
            result = sheets_client._execute_with_retry(mock_func)
        
        assert result == 'success'
        assert mock_func.call_count == 1
    
    def test_execute_with_retry_success_after_retries(self):
        mock_func = Mock(side_effect=[Exception('Error 1'), Exception('Error 2'), 'success'])
        
        with patch('sheets.sheets_client._rate_limiter.acquire'):
            with patch('time.sleep'):
                result = sheets_client._execute_with_retry(mock_func, max_retries=3)
        
        assert result == 'success'
        assert mock_func.call_count == 3
    
    def test_execute_with_retry_all_fail(self):
        mock_func = Mock(side_effect=Exception('Persistent Error'))
        
        with patch('sheets.sheets_client._rate_limiter.acquire'):
            with patch('time.sleep'):
                with pytest.raises(Exception, match='Persistent Error'):
                    sheets_client._execute_with_retry(mock_func, max_retries=3)
        
        assert mock_func.call_count == 3
