import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import run_audit
from sheets import sheets_client
from qa import cypress_runner


@pytest.mark.integration
class TestEndToEndScenarios:
    @patch('sheets.sheets_client.authenticate')
    @patch('sheets.sheets_client.read_urls')
    @patch('qa.cypress_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_full_audit_workflow_passing(self, mock_batch_write, mock_run_analysis, mock_read_urls, mock_auth):
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        mock_read_urls.return_value = [
            (2, 'https://example.com', None, None, False),
            (3, 'https://google.com', None, None, False),
        ]
        
        mock_run_analysis.return_value = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        results = []
        for url_data in mock_read_urls.return_value:
            result = run_audit.process_url(
                url_data,
                'test-spreadsheet-id',
                'Sheet1',
                mock_service,
                600,
                len(mock_read_urls.return_value),
                processed_count
            )
            results.append(result)
        
        assert len(results) == 2
        assert all('error' not in r for r in results)
        assert all(r['mobile_score'] >= 80 for r in results)
        assert mock_batch_write.call_count == 2
        
        for call in mock_batch_write.call_args_list:
            updates = call[0][2]
            assert all(update[2] == 'passed' for update in updates)
    
    @patch('sheets.sheets_client.authenticate')
    @patch('sheets.sheets_client.read_urls')
    @patch('qa.cypress_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_full_audit_workflow_failing(self, mock_batch_write, mock_run_analysis, mock_read_urls, mock_auth):
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        mock_read_urls.return_value = [
            (2, 'https://slow-site.com', None, None, False),
        ]
        
        mock_run_analysis.return_value = {
            'mobile_score': 65,
            'desktop_score': 70,
            'mobile_psi_url': 'https://pagespeed.web.dev/mobile',
            'desktop_psi_url': 'https://pagespeed.web.dev/desktop'
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        result = run_audit.process_url(
            mock_read_urls.return_value[0],
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        assert 'error' not in result
        assert result['mobile_score'] < 80
        assert result['desktop_score'] < 80
        assert result['mobile_psi_url'] is not None
        assert result['desktop_psi_url'] is not None
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 2
        assert updates[0][2].startswith('https://')
        assert updates[1][2].startswith('https://')
    
    @patch('sheets.sheets_client.authenticate')
    @patch('sheets.sheets_client.read_urls')
    @patch('qa.cypress_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_mixed_results_workflow(self, mock_batch_write, mock_run_analysis, mock_read_urls, mock_auth):
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        mock_read_urls.return_value = [
            (2, 'https://fast-site.com', None, None, False),
            (3, 'https://slow-site.com', None, None, False),
            (4, 'https://medium-site.com', None, None, False),
        ]
        
        results_sequence = [
            {
                'mobile_score': 90,
                'desktop_score': 95,
                'mobile_psi_url': None,
                'desktop_psi_url': None
            },
            {
                'mobile_score': 65,
                'desktop_score': 70,
                'mobile_psi_url': 'https://psi.mobile',
                'desktop_psi_url': 'https://psi.desktop'
            },
            {
                'mobile_score': 80,
                'desktop_score': 75,
                'mobile_psi_url': None,
                'desktop_psi_url': 'https://psi.desktop2'
            }
        ]
        
        mock_run_analysis.side_effect = results_sequence
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        results = []
        for url_data in mock_read_urls.return_value:
            result = run_audit.process_url(
                url_data,
                'test-spreadsheet-id',
                'Sheet1',
                mock_service,
                600,
                len(mock_read_urls.return_value),
                processed_count
            )
            results.append(result)
        
        assert len(results) == 3
        
        assert results[0]['mobile_score'] >= 80
        assert results[0]['desktop_score'] >= 80
        
        assert results[1]['mobile_score'] < 80
        assert results[1]['desktop_score'] < 80
        
        assert results[2]['mobile_score'] >= 80
        assert results[2]['desktop_score'] < 80
        
        assert mock_batch_write.call_count == 3
    
    @patch('sheets.sheets_client.authenticate')
    @patch('sheets.sheets_client.read_urls')
    @patch('qa.cypress_runner.run_analysis')
    def test_partial_existing_data_workflow(self, mock_run_analysis, mock_read_urls, mock_auth):
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        mock_read_urls.return_value = [
            (2, 'https://example.com', 'https://existing-mobile', None, False),
            (3, 'https://google.com', None, 'https://existing-desktop', False),
        ]
        
        mock_run_analysis.return_value = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        with patch('sheets.sheets_client.batch_write_psi_urls') as mock_batch_write:
            result1 = run_audit.process_url(
                mock_read_urls.return_value[0],
                'test-spreadsheet-id',
                'Sheet1',
                mock_service,
                600,
                2,
                processed_count
            )
            
            updates1 = mock_batch_write.call_args[0][2]
            assert len(updates1) == 1
            assert updates1[0][1] == 'G'
            
            result2 = run_audit.process_url(
                mock_read_urls.return_value[1],
                'test-spreadsheet-id',
                'Sheet1',
                mock_service,
                600,
                2,
                processed_count
            )
            
            updates2 = mock_batch_write.call_args[0][2]
            assert len(updates2) == 1
            assert updates2[0][1] == 'F'
    
    @patch('sheets.sheets_client.authenticate')
    @patch('sheets.sheets_client.read_urls')
    def test_skip_conditions_workflow(self, mock_read_urls, mock_auth):
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        mock_read_urls.return_value = [
            (2, 'https://example.com', None, None, True),
            (3, 'https://google.com', 'passed', 'passed', True),
        ]
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        results = []
        for url_data in mock_read_urls.return_value:
            result = run_audit.process_url(
                url_data,
                'test-spreadsheet-id',
                'Sheet1',
                mock_service,
                600,
                len(mock_read_urls.return_value),
                processed_count
            )
            results.append(result)
        
        assert all(r['skipped'] for r in results)
        assert processed_count['count'] == 2
    
    @patch('sheets.sheets_client.authenticate')
    @patch('sheets.sheets_client.read_urls')
    @patch('qa.cypress_runner.run_analysis')
    def test_error_handling_workflow(self, mock_run_analysis, mock_read_urls, mock_auth):
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        mock_read_urls.return_value = [
            (2, 'https://example.com', None, None, False),
            (3, 'https://timeout-site.com', None, None, False),
            (4, 'https://error-site.com', None, None, False),
        ]
        
        mock_run_analysis.side_effect = [
            {
                'mobile_score': 85,
                'desktop_score': 90,
                'mobile_psi_url': None,
                'desktop_psi_url': None
            },
            cypress_runner.CypressTimeoutError("Timeout after 600s"),
            cypress_runner.CypressRunnerError("Cypress failed"),
        ]
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        results = []
        for url_data in mock_read_urls.return_value:
            result = run_audit.process_url(
                url_data,
                'test-spreadsheet-id',
                'Sheet1',
                mock_service,
                600,
                len(mock_read_urls.return_value),
                processed_count
            )
            results.append(result)
        
        assert 'error' not in results[0]
        assert 'error' in results[1]
        assert 'Timeout' in results[1]['error']
        assert 'error' in results[2]
        assert 'Cypress failed' in results[2]['error']
    
    @patch('sheets.sheets_client.authenticate')
    @patch('time.sleep')
    def test_rate_limiting_workflow(self, mock_sleep, mock_auth):
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        call_counts = {'values_get': 0, 'spreadsheet_get': 0}
        
        def values_get_side_effect():
            call_counts['values_get'] += 1
            if call_counts['values_get'] == 1:
                raise Exception("Rate limit exceeded")
            return {'values': [['https://example.com']]}
        
        def spreadsheet_get_side_effect():
            call_counts['spreadsheet_get'] += 1
            return {'sheets': [{'data': [{'rowData': [{'values': [{}] * 7}]}]}]}
        
        mock_service.spreadsheets().values().get().execute.side_effect = values_get_side_effect
        mock_service.spreadsheets().get().execute.side_effect = spreadsheet_get_side_effect
        
        sheets_client.read_urls('test-id', 'Sheet1', service=mock_service)
        
        assert call_counts['values_get'] == 2
        assert mock_sleep.call_count >= 1


@pytest.mark.integration
class TestConcurrentExecution:
    @patch('sheets.sheets_client.authenticate')
    @patch('sheets.sheets_client.read_urls')
    @patch('qa.cypress_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_concurrent_url_processing(self, mock_batch_write, mock_run_analysis, mock_read_urls, mock_auth):
        from concurrent.futures import ThreadPoolExecutor
        
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        urls = [
            (2, f'https://site{i}.com', None, None, False)
            for i in range(5)
        ]
        
        mock_read_urls.return_value = urls
        
        mock_run_analysis.return_value = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for url_data in urls:
                future = executor.submit(
                    run_audit.process_url,
                    url_data,
                    'test-spreadsheet-id',
                    'Sheet1',
                    mock_service,
                    600,
                    len(urls),
                    processed_count
                )
                futures.append(future)
            
            results = [f.result() for f in futures]
        
        assert len(results) == 5
        assert all('error' not in r for r in results)
        assert processed_count['count'] == 5
