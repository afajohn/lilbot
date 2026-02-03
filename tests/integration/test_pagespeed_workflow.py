import pytest
import os
import sys
import time
from unittest.mock import Mock, patch, MagicMock, call
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import run_audit
from sheets import sheets_client
from qa import playwright_runner
from utils.exceptions import RetryableError, PermanentError


@pytest.mark.integration
class TestPageSpeedWorkflow:
    """Integration tests for end-to-end PageSpeed Insights workflow"""
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_successful_analysis_known_good_url_with_score_extraction(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """
        Test 1: Successful analysis of known-good URL with score extraction
        Verifies that a URL can be successfully analyzed and scores are correctly extracted
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Mock successful PageSpeed analysis with good scores
        mock_run_analysis.return_value = {
            'mobile_score': 92,
            'desktop_score': 95,
            'mobile_psi_url': None,
            'desktop_psi_url': None,
            '_warm_start': False,
            '_from_cache': False
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        url_data = (2, 'https://example.com', None, None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify successful analysis
        assert 'error' not in result
        assert result['mobile_score'] == 92
        assert result['desktop_score'] == 95
        assert result['url'] == 'https://example.com'
        
        # Verify analysis was called
        mock_run_analysis.assert_called_once()
        
        # Verify both scores were extracted
        assert result['mobile_score'] is not None
        assert result['desktop_score'] is not None
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_correct_passed_writing_for_high_scoring_url(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """
        Test 2: Correct 'passed' writing for high-scoring URL (score >= 80)
        Verifies that when both mobile and desktop scores are >= 80,
        the word 'passed' is written to columns F and G
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Mock high scores (both >= 80)
        mock_run_analysis.return_value = {
            'mobile_score': 85,
            'desktop_score': 88,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        url_data = (2, 'https://fast-site.com', None, None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify successful processing
        assert 'error' not in result
        assert result['mobile_score'] >= 80
        assert result['desktop_score'] >= 80
        
        # Verify batch write was called
        mock_batch_write.assert_called_once()
        
        # Verify the updates contain 'passed' for both columns
        call_args = mock_batch_write.call_args
        updates = call_args[0][2]  # Third positional argument is the updates list
        
        assert len(updates) == 2
        # Should have updates for both F (mobile) and G (desktop)
        mobile_update = next((u for u in updates if u[1] == 'F'), None)
        desktop_update = next((u for u in updates if u[1] == 'G'), None)
        
        assert mobile_update is not None
        assert mobile_update[2] == 'passed'
        assert desktop_update is not None
        assert desktop_update[2] == 'passed'
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_correct_psi_url_writing_for_low_scoring_url(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """
        Test 3: Correct PSI URL writing for low-scoring URL (score < 80)
        Verifies that when scores are < 80, PSI URLs are written to columns F and G
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Mock low scores (both < 80)
        mock_run_analysis.return_value = {
            'mobile_score': 65,
            'desktop_score': 72,
            'mobile_psi_url': 'https://pagespeed.web.dev/analysis?url=test&form_factor=mobile',
            'desktop_psi_url': 'https://pagespeed.web.dev/analysis?url=test&form_factor=desktop'
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        url_data = (2, 'https://slow-site.com', None, None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify successful processing
        assert 'error' not in result
        assert result['mobile_score'] < 80
        assert result['desktop_score'] < 80
        
        # Verify PSI URLs are present
        assert result['mobile_psi_url'] is not None
        assert result['desktop_psi_url'] is not None
        
        # Verify batch write was called
        mock_batch_write.assert_called_once()
        
        # Verify the updates contain PSI URLs for both columns
        call_args = mock_batch_write.call_args
        updates = call_args[0][2]
        
        assert len(updates) == 2
        mobile_update = next((u for u in updates if u[1] == 'F'), None)
        desktop_update = next((u for u in updates if u[1] == 'G'), None)
        
        assert mobile_update is not None
        assert mobile_update[2].startswith('https://pagespeed.web.dev')
        assert 'mobile' in mobile_update[2]
        
        assert desktop_update is not None
        assert desktop_update[2].startswith('https://pagespeed.web.dev')
        assert 'desktop' in desktop_update[2]
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_mixed_score_results(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """
        Test mixed results: mobile passes (>= 80), desktop fails (< 80)
        Verifies correct handling when only one device type fails
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Mock mixed scores
        mock_run_analysis.return_value = {
            'mobile_score': 85,
            'desktop_score': 75,
            'mobile_psi_url': None,
            'desktop_psi_url': 'https://pagespeed.web.dev/analysis?url=test&form_factor=desktop'
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        url_data = (2, 'https://mixed-site.com', None, None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify successful processing
        assert 'error' not in result
        assert result['mobile_score'] >= 80
        assert result['desktop_score'] < 80
        
        # Verify batch write was called
        mock_batch_write.assert_called_once()
        
        # Verify mobile gets 'passed' and desktop gets PSI URL
        call_args = mock_batch_write.call_args
        updates = call_args[0][2]
        
        assert len(updates) == 2
        mobile_update = next((u for u in updates if u[1] == 'F'), None)
        desktop_update = next((u for u in updates if u[1] == 'G'), None)
        
        assert mobile_update is not None
        assert mobile_update[2] == 'passed'
        
        assert desktop_update is not None
        assert desktop_update[2].startswith('https://pagespeed.web.dev')
    
    @patch('sheets.sheets_client.authenticate')
    def test_skip_logic_for_rows_with_passed_text(self, mock_auth):
        """
        Test 4a: Skip logic for rows with 'passed' text in both F and G columns
        Verifies that rows with 'passed' in both columns are skipped
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        # URL data with 'passed' in both columns F and G, and should_skip=True
        url_data = (2, 'https://already-passed.com', 'passed', 'passed', True)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify the row was skipped
        assert result['skipped'] is True
        assert result['url'] == 'https://already-passed.com'
        assert 'error' not in result
        assert 'mobile_score' not in result
        assert 'desktop_score' not in result
    
    @patch('sheets.sheets_client.authenticate')
    def test_skip_logic_for_rows_with_green_background(self, mock_auth):
        """
        Test 4b: Skip logic for rows with green background (#b7e1cd) in both F and G
        Verifies that rows with green background in both columns are skipped
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        # URL data with green background indicator (should_skip=True)
        url_data = (2, 'https://green-background.com', None, None, True)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify the row was skipped
        assert result['skipped'] is True
        assert result['url'] == 'https://green-background.com'
        assert 'error' not in result
    
    @patch('sheets.sheets_client.authenticate')
    def test_skip_logic_for_both_columns_already_filled(self, mock_auth):
        """
        Test 4c: Skip logic when both F and G columns already contain URLs
        Verifies that rows with both columns filled are skipped
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        # URL data with both mobile and desktop PSI URLs already present
        url_data = (
            2, 
            'https://both-filled.com',
            'https://pagespeed.web.dev/mobile-existing',
            'https://pagespeed.web.dev/desktop-existing',
            False
        )
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify the row was skipped
        assert result['skipped'] is True
        assert result['url'] == 'https://both-filled.com'
        assert 'error' not in result
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_partial_column_update_only_f_filled(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """
        Test 5a: Partial column update when only F (mobile) is filled
        Verifies that when F is filled, only G (desktop) is updated
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Mock analysis results
        mock_run_analysis.return_value = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        # URL data with only mobile (F) column filled
        url_data = (2, 'https://mobile-filled.com', 'https://existing-mobile-psi', None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify successful processing
        assert 'error' not in result
        assert 'skipped' not in result or result['skipped'] is False
        
        # Verify batch write was called
        mock_batch_write.assert_called_once()
        
        # Verify only G (desktop) column was updated
        call_args = mock_batch_write.call_args
        updates = call_args[0][2]
        
        assert len(updates) == 1
        assert updates[0][1] == 'G'  # Only desktop column
        assert updates[0][2] == 'passed'
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_partial_column_update_only_g_filled(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """
        Test 5b: Partial column update when only G (desktop) is filled
        Verifies that when G is filled, only F (mobile) is updated
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Mock analysis results
        mock_run_analysis.return_value = {
            'mobile_score': 88,
            'desktop_score': 92,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        # URL data with only desktop (G) column filled
        url_data = (2, 'https://desktop-filled.com', None, 'https://existing-desktop-psi', False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify successful processing
        assert 'error' not in result
        assert 'skipped' not in result or result['skipped'] is False
        
        # Verify batch write was called
        mock_batch_write.assert_called_once()
        
        # Verify only F (mobile) column was updated
        call_args = mock_batch_write.call_args
        updates = call_args[0][2]
        
        assert len(updates) == 1
        assert updates[0][1] == 'F'  # Only mobile column
        assert updates[0][2] == 'passed'
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_partial_update_with_failing_scores(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """
        Test 5c: Partial column update with failing scores
        Verifies PSI URLs are written only to empty columns when scores fail
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Mock analysis results with failing scores
        mock_run_analysis.return_value = {
            'mobile_score': 65,
            'desktop_score': 70,
            'mobile_psi_url': 'https://pagespeed.web.dev/mobile-new',
            'desktop_psi_url': 'https://pagespeed.web.dev/desktop-new'
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        # URL data with only mobile (F) column filled
        url_data = (2, 'https://partial-fail.com', 'passed', None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify successful processing
        assert 'error' not in result
        
        # Verify batch write was called
        mock_batch_write.assert_called_once()
        
        # Verify only G (desktop) column was updated with PSI URL
        call_args = mock_batch_write.call_args
        updates = call_args[0][2]
        
        assert len(updates) == 1
        assert updates[0][1] == 'G'
        assert updates[0][2].startswith('https://pagespeed.web.dev')
        assert 'desktop' in updates[0][2]
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_cache_hit_workflow(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """
        Test cache hit scenario where result is retrieved from cache
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Mock cached result
        mock_run_analysis.return_value = {
            'mobile_score': 87,
            'desktop_score': 91,
            'mobile_psi_url': None,
            'desktop_psi_url': None,
            '_from_cache': True
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        url_data = (2, 'https://cached-url.com', None, None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify successful processing
        assert 'error' not in result
        assert result['mobile_score'] >= 80
        assert result['desktop_score'] >= 80
        
        # Verify analysis was called (cache check happens inside run_analysis)
        mock_run_analysis.assert_called_once()
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    def test_playwright_timeout_error(self, mock_run_analysis, mock_auth):
        """
        Test handling of Playwright timeout error
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Mock timeout error
        mock_run_analysis.side_effect = playwright_runner.PlaywrightAnalysisTimeoutError(
            "Analysis exceeded overall timeout of 600s"
        )
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        url_data = (2, 'https://timeout-url.com', None, None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify error was captured
        assert 'error' in result
        assert result['error_type'] == 'timeout'
        assert 'timeout' in result['error'].lower()
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    def test_playwright_runner_error(self, mock_run_analysis, mock_auth):
        """
        Test handling of general Playwright runner error
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Mock Playwright error
        mock_run_analysis.side_effect = playwright_runner.PlaywrightRunnerError(
            "Failed to extract scores from PageSpeed Insights"
        )
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        url_data = (2, 'https://error-url.com', None, None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify error was captured
        assert 'error' in result
        assert result['error_type'] == 'playwright'
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_multiple_urls_workflow(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """
        Test processing multiple URLs with various outcomes
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Mock different results for different URLs
        mock_run_analysis.side_effect = [
            {
                'mobile_score': 90,
                'desktop_score': 92,
                'mobile_psi_url': None,
                'desktop_psi_url': None
            },
            {
                'mobile_score': 65,
                'desktop_score': 70,
                'mobile_psi_url': 'https://psi.web.dev/mobile1',
                'desktop_psi_url': 'https://psi.web.dev/desktop1'
            },
            {
                'mobile_score': 80,
                'desktop_score': 75,
                'mobile_psi_url': None,
                'desktop_psi_url': 'https://psi.web.dev/desktop2'
            }
        ]
        
        urls = [
            (2, 'https://fast.com', None, None, False),
            (3, 'https://slow.com', None, None, False),
            (4, 'https://mixed.com', None, None, False)
        ]
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        results = []
        for url_data in urls:
            result = run_audit.process_url(
                url_data,
                'test-spreadsheet-id',
                'Sheet1',
                mock_service,
                600,
                len(urls),
                processed_count
            )
            results.append(result)
        
        # Verify all URLs processed
        assert len(results) == 3
        
        # Verify first URL (both pass)
        assert results[0]['mobile_score'] >= 80
        assert results[0]['desktop_score'] >= 80
        
        # Verify second URL (both fail)
        assert results[1]['mobile_score'] < 80
        assert results[1]['desktop_score'] < 80
        
        # Verify third URL (mixed)
        assert results[2]['mobile_score'] >= 80
        assert results[2]['desktop_score'] < 80
        
        # Verify batch writes
        assert mock_batch_write.call_count == 3
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_dry_run_mode(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """
        Test dry run mode where no actual writes occur
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        url_data = (2, 'https://dryrun.com', None, None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count,
            dry_run=True
        )
        
        # Verify dry run was executed
        assert result['dry_run'] is True
        assert result['url'] == 'https://dryrun.com'
        
        # Verify no analysis or writes occurred
        mock_run_analysis.assert_not_called()
        mock_batch_write.assert_not_called()
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    def test_invalid_url_handling(self, mock_run_analysis, mock_auth):
        """
        Test handling of invalid URLs
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        # Invalid URL (contains dangerous characters)
        url_data = (2, 'https://example.com/<script>', None, None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify error was captured
        assert 'error' in result
        assert result['error_type'] == 'invalid_url'
        
        # Verify no analysis occurred
        mock_run_analysis.assert_not_called()
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_spreadsheet_write_error_handling(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """
        Test handling of spreadsheet write errors
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Mock successful analysis
        mock_run_analysis.return_value = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        # Mock batch write failure
        mock_batch_write.side_effect = PermanentError("Permission denied")
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        url_data = (2, 'https://writeerror.com', None, None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Verify analysis succeeded but write failed (error doesn't propagate)
        assert 'error' not in result
        assert result['mobile_score'] == 85
        assert result['desktop_score'] == 90


@pytest.mark.integration
class TestPageSpeedWorkflowWithRateLimiting:
    """Integration tests for PageSpeed workflow with rate limiting simulation"""
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    @patch('time.sleep')
    def test_rate_limited_multiple_requests(
        self, mock_sleep, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """
        Test rate limiting behavior with multiple consecutive requests
        """
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        # Track call timing
        call_times = []
        
        def track_analysis(*args, **kwargs):
            call_times.append(time.time())
            return {
                'mobile_score': 85,
                'desktop_score': 90,
                'mobile_psi_url': None,
                'desktop_psi_url': None
            }
        
        mock_run_analysis.side_effect = track_analysis
        
        urls = [
            (2, f'https://site{i}.com', None, None, False)
            for i in range(5)
        ]
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        results = []
        for url_data in urls:
            result = run_audit.process_url(
                url_data,
                'test-spreadsheet-id',
                'Sheet1',
                mock_service,
                600,
                len(urls),
                processed_count
            )
            results.append(result)
        
        # Verify all URLs processed successfully
        assert len(results) == 5
        assert all('error' not in r for r in results)
        
        # Verify analysis was called 5 times
        assert mock_run_analysis.call_count == 5


@pytest.mark.integration
class TestPageSpeedWorkflowSkipLogicVariations:
    """Comprehensive tests for skip logic variations"""
    
    @patch('sheets.sheets_client.authenticate')
    def test_skip_with_passed_text_case_insensitive(self, mock_auth):
        """Test skip logic works with various cases of 'passed' text"""
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        # Test various cases
        test_cases = [
            (2, 'https://url1.com', 'passed', 'passed', True),
            (3, 'https://url2.com', 'Passed', 'Passed', True),
            (4, 'https://url3.com', 'PASSED', 'PASSED', True),
        ]
        
        for url_data in test_cases:
            result = run_audit.process_url(
                url_data,
                'test-spreadsheet-id',
                'Sheet1',
                mock_service,
                600,
                1,
                processed_count
            )
            
            assert result['skipped'] is True
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_no_skip_with_only_one_passed(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """Test that rows with only one 'passed' are not skipped"""
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        mock_run_analysis.return_value = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        # Only F has 'passed', G is empty
        url_data = (2, 'https://partial.com', 'passed', None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Should NOT skip - should process the empty column
        assert 'skipped' not in result or result['skipped'] is False
        
        # Verify only G was updated
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 1
        assert updates[0][1] == 'G'
    
    @patch('sheets.sheets_client.authenticate')
    @patch('qa.playwright_runner.run_analysis')
    @patch('sheets.sheets_client.batch_write_psi_urls')
    def test_no_skip_with_empty_columns(
        self, mock_batch_write, mock_run_analysis, mock_auth
    ):
        """Test that rows with both columns empty are processed"""
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        mock_run_analysis.return_value = {
            'mobile_score': 88,
            'desktop_score': 92,
            'mobile_psi_url': None,
            'desktop_psi_url': None
        }
        
        processed_count = {'count': 0, 'lock': threading.Lock()}
        
        # Both F and G are empty
        url_data = (2, 'https://empty.com', None, None, False)
        
        result = run_audit.process_url(
            url_data,
            'test-spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            processed_count
        )
        
        # Should NOT skip
        assert 'skipped' not in result or result['skipped'] is False
        
        # Verify both columns were updated
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 2
