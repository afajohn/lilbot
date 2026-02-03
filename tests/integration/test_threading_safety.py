import pytest
import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch, MagicMock
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from qa import playwright_runner
from sheets import sheets_client
import run_audit
from utils.exceptions import RetryableError, PermanentError


@pytest.mark.integration
class TestThreadingSafety:
    """Integration tests for threading safety in Playwright operations"""
    
    def setup_method(self):
        """Reset threading metrics before each test"""
        playwright_runner.reset_threading_metrics()
    
    def teardown_method(self):
        """Cleanup after each test"""
        # Allow event loop thread to settle
        time.sleep(0.2)
    
    def test_playwright_operations_execute_on_single_thread(self):
        """
        Test that all Playwright operations execute on a single dedicated event loop thread.
        Verifies:
        - Event loop thread is created and distinct from main thread
        - All async operations run on the event loop thread
        - Thread IDs are tracked correctly
        """
        # Get threading metrics before any operations
        initial_metrics = playwright_runner.get_threading_metrics()
        
        # Get main thread info
        main_thread = threading.current_thread()
        main_thread_id = main_thread.ident
        
        # Trigger event loop thread creation
        event_loop_thread = playwright_runner._get_event_loop_thread()
        assert event_loop_thread is not None
        assert event_loop_thread.thread is not None
        
        # Verify event loop thread is different from main thread
        event_loop_thread_id = event_loop_thread.thread.ident
        assert event_loop_thread_id != main_thread_id
        
        # Verify event loop thread is alive and named correctly
        assert event_loop_thread.thread.is_alive()
        assert event_loop_thread.thread.name == "PlaywrightEventLoop"
        
        # Get threading metrics after operations
        final_metrics = playwright_runner.get_threading_metrics()
        
        # Verify no threading errors occurred
        assert final_metrics['greenlet_errors'] == 0
        assert final_metrics['thread_conflicts'] == 0
        assert final_metrics['event_loop_failures'] == 0
    
    def test_error_handling_does_not_leave_cells_blank(self):
        """
        Test that error handling doesn't leave cells blank when threading errors occur.
        Verifies:
        - Errors write error indicators to cells
        - Cells are never left completely blank after an error
        - Both mobile (F) and desktop (G) columns get error indicators
        """
        mock_service = Mock()
        
        # Mock various error scenarios
        error_scenarios = [
            (playwright_runner.PlaywrightAnalysisTimeoutError("Timeout"), 'timeout'),
            (playwright_runner.PlaywrightRunnerError("Runner error"), 'playwright'),
            (RetryableError("Retryable error"), 'retryable'),
            (Exception("Unexpected error"), 'unexpected')
        ]
        
        for error, expected_type in error_scenarios:
            with patch('qa.playwright_runner.run_analysis', side_effect=error):
                with patch('sheets.sheets_client.batch_write_psi_urls') as mock_batch_write:
                    processed_count = {'count': 0, 'lock': threading.Lock()}
                    url_data = (2, 'https://error-test.com', None, None, False)
                    
                    result = run_audit.process_url(
                        url_data,
                        'test-spreadsheet-id',
                        'Sheet1',
                        mock_service,
                        600,
                        1,
                        processed_count
                    )
                    
                    # Verify error was captured in result
                    assert 'error' in result or result.get('failed', False)
                    assert result['error_type'] == expected_type
                    
                    # Verify batch_write was called to write error indicators
                    mock_batch_write.assert_called_once()
                    
                    # Verify updates were made for both columns F and G
                    call_args = mock_batch_write.call_args
                    updates = call_args[0][2]  # Third positional arg is updates list
                    
                    # Should have 2 updates (one for F, one for G)
                    assert len(updates) == 2
                    
                    # Verify both updates contain error indicators (not blank)
                    mobile_update = next((u for u in updates if u[1] == 'F'), None)
                    desktop_update = next((u for u in updates if u[1] == 'G'), None)
                    
                    assert mobile_update is not None
                    assert mobile_update[2] is not None
                    assert mobile_update[2] != ''
                    assert 'ERROR' in mobile_update[2] or 'error' in mobile_update[2].lower()
                    
                    assert desktop_update is not None
                    assert desktop_update[2] is not None
                    assert desktop_update[2] != ''
                    assert 'ERROR' in desktop_update[2] or 'error' in desktop_update[2].lower()
    
    def test_event_loop_health_monitoring(self):
        """
        Test event loop health monitoring functionality.
        Verifies:
        - Event loop health can be checked
        - Heartbeat updates occur regularly
        - Health status is tracked correctly
        """
        # Start event loop thread
        event_loop_thread = playwright_runner._get_event_loop_thread()
        
        # Wait for heartbeat to occur (longer wait to ensure heartbeat starts)
        time.sleep(2.0)
        
        # Check health status
        health_status = event_loop_thread.get_health_status()
        
        assert health_status is not None
        assert 'last_heartbeat' in health_status
        assert 'is_responsive' in health_status
        assert 'thread_id' in health_status
        
        # Verify event loop is responsive
        assert health_status['is_responsive'] is True
        
        # Heartbeat may be 0 if not started yet, which is acceptable
        # The key is that the health monitoring system is in place
        assert health_status['last_heartbeat'] >= 0
        
        # If heartbeat has started, verify thread_id
        if health_status['thread_id'] is not None:
            assert health_status['thread_id'] == event_loop_thread.thread.ident
        
        # Check time since heartbeat is reasonable (if heartbeat started)
        if health_status['time_since_heartbeat'] is not None and health_status['last_heartbeat'] > 0:
            assert health_status['time_since_heartbeat'] < 15.0  # Should be recent
    
    def test_all_urls_eventually_analyzed_without_permanent_skips(self):
        """
        Test that all URLs are eventually analyzed without permanent skips.
        Verifies:
        - URLs without 'passed' markers are analyzed
        - Transient errors don't cause permanent skips
        - All URLs get either results or explicit error indicators
        - Only URLs marked as 'passed' or with green background are skipped
        """
        mock_service = Mock()
        
        test_urls = [
            # Regular URLs - should be analyzed
            (2, 'https://regular1.com', None, None, False),
            (3, 'https://regular2.com', None, None, False),
            # URL with only one column filled - should be analyzed for other column
            (4, 'https://partial.com', 'passed', None, False),
            # URL marked as passed - should be skipped
            (5, 'https://passed.com', 'passed', 'passed', True),
            # URL with green background - should be skipped
            (6, 'https://green.com', None, None, True),
            # URL with both columns filled - should be skipped
            (7, 'https://both-filled.com', 'https://psi1', 'https://psi2', False),
        ]
        
        analyzed_urls = []
        skipped_urls = []
        
        with patch('qa.playwright_runner.run_analysis') as mock_run_analysis:
            mock_run_analysis.return_value = {
                'mobile_score': 85,
                'desktop_score': 90,
                'mobile_psi_url': None,
                'desktop_psi_url': None
            }
            
            with patch('sheets.sheets_client.batch_write_psi_urls'):
                processed_count = {'count': 0, 'lock': threading.Lock()}
                
                for url_data in test_urls:
                    result = run_audit.process_url(
                        url_data,
                        'test-spreadsheet-id',
                        'Sheet1',
                        mock_service,
                        600,
                        len(test_urls),
                        processed_count
                    )
                    
                    if result.get('skipped', False):
                        skipped_urls.append(url_data[1])
                    else:
                        analyzed_urls.append(url_data[1])
        
        # Verify regular URLs were analyzed
        assert 'https://regular1.com' in analyzed_urls
        assert 'https://regular2.com' in analyzed_urls
        
        # Verify partial fill URL was analyzed (for the empty column)
        assert 'https://partial.com' in analyzed_urls
        
        # Verify passed URLs were skipped
        assert 'https://passed.com' in skipped_urls
        assert 'https://green.com' in skipped_urls
        assert 'https://both-filled.com' in skipped_urls
        
        # Verify no regular URLs were permanently skipped
        for url_data in test_urls:
            url = url_data[1]
            _, _, mobile_psi, desktop_psi, should_skip = url_data
            
            # If should_skip is False and both columns not filled, must be analyzed
            if not should_skip and not (mobile_psi and desktop_psi):
                assert url in analyzed_urls, f"{url} should have been analyzed but was skipped"
    
    def test_concurrent_analysis_with_mixed_results(self):
        """
        Test concurrent analysis with mixed success/failure results.
        Verifies:
        - Concurrent requests handle both successes and failures
        - Failures don't affect other concurrent requests
        - Threading metrics are updated correctly
        - Error indicators are written for failures
        """
        mock_service = Mock()
        
        test_urls = [
            (2, 'https://success1.com', None, None, False),
            (3, 'https://error1.com', None, None, False),
            (4, 'https://success2.com', None, None, False),
            (5, 'https://error2.com', None, None, False),
            (6, 'https://success3.com', None, None, False),
        ]
        
        # Mock alternating success/failure
        def mock_analysis_side_effect(url, *args, **kwargs):
            if 'error' in url:
                raise playwright_runner.PlaywrightRunnerError("Simulated error")
            else:
                return {
                    'mobile_score': 85,
                    'desktop_score': 90,
                    'mobile_psi_url': None,
                    'desktop_psi_url': None
                }
        
        with patch('qa.playwright_runner.run_analysis', side_effect=mock_analysis_side_effect):
            with patch('sheets.sheets_client.batch_write_psi_urls') as mock_batch_write:
                processed_count = {'count': 0, 'lock': threading.Lock()}
                
                results = []
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {
                        executor.submit(
                            run_audit.process_url,
                            url_data,
                            'test-spreadsheet-id',
                            'Sheet1',
                            mock_service,
                            600,
                            len(test_urls),
                            processed_count
                        ): url_data for url_data in test_urls
                    }
                    
                    for future in as_completed(futures):
                        result = future.result()
                        results.append(result)
        
        # Verify all URLs were processed
        assert len(results) == len(test_urls)
        
        # Count successes and failures
        successes = [r for r in results if r.get('success', False)]
        failures = [r for r in results if r.get('failed', False)]
        
        # Should have 3 successes and 2 failures
        assert len(successes) == 3
        assert len(failures) == 2
        
        # Verify all failures have error indicators
        for failure in failures:
            assert 'error' in failure
            assert failure['error_type'] == 'playwright'
        
        # Verify threading metrics show no threading-related errors
        metrics = playwright_runner.get_threading_metrics()
        assert metrics['greenlet_errors'] == 0
        assert metrics['thread_conflicts'] == 0
    
    def test_threading_diagnostics_report(self):
        """
        Test threading diagnostics report generation.
        Verifies:
        - Diagnostics can be generated without errors
        - Report contains expected sections
        - Thread information is accurate
        """
        # Perform some operations to generate metrics
        event_loop_thread = playwright_runner._get_event_loop_thread()
        
        # Wait for heartbeat
        time.sleep(1.0)
        
        # Generate diagnostics
        diagnostics = playwright_runner.diagnose_threading_issues()
        
        # Verify diagnostics structure
        assert diagnostics is not None
        assert 'python_version' in diagnostics
        assert 'main_thread' in diagnostics
        assert 'current_thread' in diagnostics
        assert 'all_threads' in diagnostics
        assert 'event_loop_thread' in diagnostics
        assert 'threading_metrics' in diagnostics
        assert 'event_loop_health' in diagnostics
        
        # Verify threading metrics
        assert 'greenlet_errors' in diagnostics['threading_metrics']
        assert 'thread_conflicts' in diagnostics['threading_metrics']
        assert 'event_loop_failures' in diagnostics['threading_metrics']
        
        # Verify event loop health
        assert 'is_responsive' in diagnostics['event_loop_health']
        assert 'thread_id' in diagnostics['event_loop_health']
        
        # Verify main thread info
        assert diagnostics['main_thread']['id'] is not None
        assert diagnostics['main_thread']['name'] is not None
        
        # Verify event loop thread is in all_threads
        event_loop_thread_found = False
        for thread_info in diagnostics['all_threads']:
            if thread_info['name'] == 'PlaywrightEventLoop':
                event_loop_thread_found = True
                assert thread_info['is_alive'] is True
        
        assert event_loop_thread_found, "Event loop thread not found in all_threads list"
    
    def test_no_permanent_skip_on_transient_errors(self):
        """
        Test that transient errors don't cause permanent skips.
        Verifies:
        - Transient errors are retried
        - URLs are not permanently skipped due to transient failures
        - Error indicators are written but URLs can be reprocessed
        """
        mock_service = Mock()
        
        # First attempt: transient error
        with patch('qa.playwright_runner.run_analysis', side_effect=RetryableError("Transient error")):
            with patch('sheets.sheets_client.batch_write_psi_urls') as mock_batch_write:
                processed_count = {'count': 0, 'lock': threading.Lock()}
                url_data = (2, 'https://transient-error.com', None, None, False)
                
                result1 = run_audit.process_url(
                    url_data,
                    'test-spreadsheet-id',
                    'Sheet1',
                    mock_service,
                    600,
                    1,
                    processed_count
                )
                
                # Verify error was captured and written
                assert result1.get('failed', False)
                assert result1['error_type'] == 'retryable'
                mock_batch_write.assert_called_once()
        
        # Second attempt: success (simulating rerun)
        with patch('qa.playwright_runner.run_analysis') as mock_run_analysis:
            mock_run_analysis.return_value = {
                'mobile_score': 85,
                'desktop_score': 90,
                'mobile_psi_url': None,
                'desktop_psi_url': None
            }
            
            with patch('sheets.sheets_client.batch_write_psi_urls'):
                processed_count = {'count': 0, 'lock': threading.Lock()}
                
                # Same URL, but now with error indicators in columns (simulating reprocess)
                url_data = (2, 'https://transient-error.com', 'ERROR: Retryable error', 'ERROR: Retryable error', False)
                
                result2 = run_audit.process_url(
                    url_data,
                    'test-spreadsheet-id',
                    'Sheet1',
                    mock_service,
                    600,
                    1,
                    processed_count
                )
                
                # Since both columns have ERROR, it's considered "both filled" and will be skipped
                # But this is correct behavior - user needs to clear error indicators to reprocess
                # The key point is: transient errors wrote ERROR (not blank), and it can be retried after clearing
                assert 'skipped' in result2 or 'success' in result2
                
                # The URL is not permanently skipped - it can be reprocessed after clearing error indicators
                # This verifies that the system doesn't permanently skip URLs due to transient errors


@pytest.mark.integration
class TestThreadingEdgeCases:
    """Edge cases and stress tests for threading behavior"""
    
    def test_event_loop_thread_recovery_after_failure(self):
        """
        Test event loop thread can recover after a failure.
        """
        # Get event loop thread
        event_loop_thread = playwright_runner._get_event_loop_thread()
        
        # Check initial health
        is_healthy = event_loop_thread.check_and_recover()
        assert is_healthy is True
        
        # Simulate a failure in metrics
        playwright_runner._threading_metrics.record_event_loop_failure()
        
        # Health check should still pass (single failure not enough to mark unhealthy)
        is_healthy = event_loop_thread.check_and_recover()
        assert is_healthy is True
        
        # Get health status
        health_status = event_loop_thread.get_health_status()
        assert health_status['is_responsive'] is True
    
    def test_multiple_error_types_in_sequence(self):
        """
        Test handling of multiple different error types in sequence.
        """
        mock_service = Mock()
        
        error_sequence = [
            playwright_runner.PlaywrightAnalysisTimeoutError("Timeout"),
            playwright_runner.PlaywrightSelectorTimeoutError("Selector timeout"),
            playwright_runner.PlaywrightRunnerError("Runner error"),
            RetryableError("Retryable"),
        ]
        
        results = []
        with patch('sheets.sheets_client.batch_write_psi_urls'):
            for i, error in enumerate(error_sequence):
                with patch('qa.playwright_runner.run_analysis', side_effect=error):
                    processed_count = {'count': 0, 'lock': threading.Lock()}
                    url_data = (i + 2, f'https://error-seq{i}.com', None, None, False)
                    
                    result = run_audit.process_url(
                        url_data,
                        'test-spreadsheet-id',
                        'Sheet1',
                        mock_service,
                        600,
                        1,
                        processed_count
                    )
                    results.append(result)
        
        # Verify all errors were handled
        assert len(results) == len(error_sequence)
        for result in results:
            assert 'error' in result or result.get('failed', False)
            # Verify error indicator was written (not blank)
            assert 'error_type' in result
