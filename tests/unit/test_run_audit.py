import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import run_audit


class TestProcessUrlScoreThreshold:
    """Unit tests for score threshold logic in process_url function"""
    
    @patch('run_audit.playwright_runner.run_analysis')
    @patch('run_audit.sheets_client.batch_write_psi_urls')
    def test_score_79_writes_psi_url(self, mock_batch_write, mock_run_analysis):
        """Test that score of 79 (below threshold) writes PSI URL, not 'passed'"""
        mock_run_analysis.return_value = {
            'mobile_score': 79,
            'desktop_score': 79,
            'mobile_psi_url': 'https://pagespeed.web.dev/analysis?url=mobile79',
            'desktop_psi_url': 'https://pagespeed.web.dev/analysis?url=desktop79',
            '_from_cache': False
        }
        
        url_data = (5, 'https://example.com', None, None, False)
        current_idx = 1
        mock_service = Mock()
        
        result = run_audit.process_url(
            url_data,
            'spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            current_idx,
            skip_cache=False
        )
        
        assert result['mobile_score'] == 79
        assert result['desktop_score'] == 79
        assert result['mobile_psi_url'] == 'https://pagespeed.web.dev/analysis?url=mobile79'
        assert result['desktop_psi_url'] == 'https://pagespeed.web.dev/analysis?url=desktop79'
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 2
        assert (5, 'F', 'https://pagespeed.web.dev/analysis?url=mobile79') in updates
        assert (5, 'G', 'https://pagespeed.web.dev/analysis?url=desktop79') in updates
        assert (5, 'F', 'passed') not in updates
        assert (5, 'G', 'passed') not in updates
    
    @patch('run_audit.playwright_runner.run_analysis')
    @patch('run_audit.sheets_client.batch_write_psi_urls')
    def test_score_80_writes_passed(self, mock_batch_write, mock_run_analysis):
        """Test that score of 80 (at threshold) writes 'passed', not PSI URL"""
        mock_run_analysis.return_value = {
            'mobile_score': 80,
            'desktop_score': 80,
            'mobile_psi_url': None,
            'desktop_psi_url': None,
            '_from_cache': False
        }
        
        url_data = (5, 'https://example.com', None, None, False)
        current_idx = 1
        mock_service = Mock()
        
        result = run_audit.process_url(
            url_data,
            'spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            current_idx,
            skip_cache=False
        )
        
        assert result['mobile_score'] == 80
        assert result['desktop_score'] == 80
        assert result['mobile_psi_url'] is None
        assert result['desktop_psi_url'] is None
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 2
        assert (5, 'F', 'passed') in updates
        assert (5, 'G', 'passed') in updates
    
    @patch('run_audit.playwright_runner.run_analysis')
    @patch('run_audit.sheets_client.batch_write_psi_urls')
    def test_score_81_writes_passed(self, mock_batch_write, mock_run_analysis):
        """Test that score of 81 (above threshold) writes 'passed', not PSI URL"""
        mock_run_analysis.return_value = {
            'mobile_score': 81,
            'desktop_score': 81,
            'mobile_psi_url': None,
            'desktop_psi_url': None,
            '_from_cache': False
        }
        
        url_data = (5, 'https://example.com', None, None, False)
        current_idx = 1
        mock_service = Mock()
        
        result = run_audit.process_url(
            url_data,
            'spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            current_idx,
            skip_cache=False
        )
        
        assert result['mobile_score'] == 81
        assert result['desktop_score'] == 81
        assert result['mobile_psi_url'] is None
        assert result['desktop_psi_url'] is None
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 2
        assert (5, 'F', 'passed') in updates
        assert (5, 'G', 'passed') in updates
    
    @patch('run_audit.playwright_runner.run_analysis')
    @patch('run_audit.sheets_client.batch_write_psi_urls')
    def test_score_0_writes_psi_url(self, mock_batch_write, mock_run_analysis):
        """Test that score of 0 (far below threshold) writes PSI URL"""
        mock_run_analysis.return_value = {
            'mobile_score': 0,
            'desktop_score': 0,
            'mobile_psi_url': 'https://pagespeed.web.dev/analysis?url=mobile0',
            'desktop_psi_url': 'https://pagespeed.web.dev/analysis?url=desktop0',
            '_from_cache': False
        }
        
        url_data = (5, 'https://example.com', None, None, False)
        current_idx = 1
        mock_service = Mock()
        
        result = run_audit.process_url(
            url_data,
            'spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            current_idx,
            skip_cache=False
        )
        
        assert result['mobile_score'] == 0
        assert result['desktop_score'] == 0
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 2
        assert (5, 'F', 'https://pagespeed.web.dev/analysis?url=mobile0') in updates
        assert (5, 'G', 'https://pagespeed.web.dev/analysis?url=desktop0') in updates
    
    @patch('run_audit.playwright_runner.run_analysis')
    @patch('run_audit.sheets_client.batch_write_psi_urls')
    def test_score_100_writes_passed(self, mock_batch_write, mock_run_analysis):
        """Test that score of 100 (maximum score) writes 'passed'"""
        mock_run_analysis.return_value = {
            'mobile_score': 100,
            'desktop_score': 100,
            'mobile_psi_url': None,
            'desktop_psi_url': None,
            '_from_cache': False
        }
        
        url_data = (5, 'https://example.com', None, None, False)
        current_idx = 1
        mock_service = Mock()
        
        result = run_audit.process_url(
            url_data,
            'spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            current_idx,
            skip_cache=False
        )
        
        assert result['mobile_score'] == 100
        assert result['desktop_score'] == 100
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 2
        assert (5, 'F', 'passed') in updates
        assert (5, 'G', 'passed') in updates
    
    @patch('run_audit.playwright_runner.run_analysis')
    @patch('run_audit.sheets_client.batch_write_psi_urls')
    def test_mixed_scores_mobile_79_desktop_80(self, mock_batch_write, mock_run_analysis):
        """Test mixed boundary scores: mobile=79 (fail), desktop=80 (pass)"""
        mock_run_analysis.return_value = {
            'mobile_score': 79,
            'desktop_score': 80,
            'mobile_psi_url': 'https://pagespeed.web.dev/analysis?url=mobile79',
            'desktop_psi_url': None,
            '_from_cache': False
        }
        
        url_data = (5, 'https://example.com', None, None, False)
        current_idx = 1
        mock_service = Mock()
        
        result = run_audit.process_url(
            url_data,
            'spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            current_idx,
            skip_cache=False
        )
        
        assert result['mobile_score'] == 79
        assert result['desktop_score'] == 80
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 2
        assert (5, 'F', 'https://pagespeed.web.dev/analysis?url=mobile79') in updates
        assert (5, 'G', 'passed') in updates
    
    @patch('run_audit.playwright_runner.run_analysis')
    @patch('run_audit.sheets_client.batch_write_psi_urls')
    def test_mixed_scores_mobile_80_desktop_79(self, mock_batch_write, mock_run_analysis):
        """Test mixed boundary scores: mobile=80 (pass), desktop=79 (fail)"""
        mock_run_analysis.return_value = {
            'mobile_score': 80,
            'desktop_score': 79,
            'mobile_psi_url': None,
            'desktop_psi_url': 'https://pagespeed.web.dev/analysis?url=desktop79',
            '_from_cache': False
        }
        
        url_data = (5, 'https://example.com', None, None, False)
        current_idx = 1
        mock_service = Mock()
        
        result = run_audit.process_url(
            url_data,
            'spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            current_idx,
            skip_cache=False
        )
        
        assert result['mobile_score'] == 80
        assert result['desktop_score'] == 79
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 2
        assert (5, 'F', 'passed') in updates
        assert (5, 'G', 'https://pagespeed.web.dev/analysis?url=desktop79') in updates
    
    @patch('run_audit.playwright_runner.run_analysis')
    @patch('run_audit.sheets_client.batch_write_psi_urls')
    def test_mixed_scores_mobile_81_desktop_79(self, mock_batch_write, mock_run_analysis):
        """Test mixed boundary scores: mobile=81 (pass), desktop=79 (fail)"""
        mock_run_analysis.return_value = {
            'mobile_score': 81,
            'desktop_score': 79,
            'mobile_psi_url': None,
            'desktop_psi_url': 'https://pagespeed.web.dev/analysis?url=desktop79',
            '_from_cache': False
        }
        
        url_data = (5, 'https://example.com', None, None, False)
        current_idx = 1
        mock_service = Mock()
        
        result = run_audit.process_url(
            url_data,
            'spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            current_idx,
            skip_cache=False
        )
        
        assert result['mobile_score'] == 81
        assert result['desktop_score'] == 79
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 2
        assert (5, 'F', 'passed') in updates
        assert (5, 'G', 'https://pagespeed.web.dev/analysis?url=desktop79') in updates
    
    @patch('run_audit.playwright_runner.run_analysis')
    @patch('run_audit.sheets_client.batch_write_psi_urls')
    def test_score_below_threshold_no_psi_url_writes_nothing(self, mock_batch_write, mock_run_analysis):
        """Test that when score < 80 but no PSI URL exists, nothing is written (edge case)"""
        mock_run_analysis.return_value = {
            'mobile_score': 75,
            'desktop_score': 70,
            'mobile_psi_url': None,
            'desktop_psi_url': None,
            '_from_cache': False
        }
        
        url_data = (5, 'https://example.com', None, None, False)
        current_idx = 1
        mock_service = Mock()
        
        result = run_audit.process_url(
            url_data,
            'spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            current_idx,
            skip_cache=False
        )
        
        assert result['mobile_score'] == 75
        assert result['desktop_score'] == 70
        
        mock_batch_write.assert_not_called()
    
    @patch('run_audit.playwright_runner.run_analysis')
    @patch('run_audit.sheets_client.batch_write_psi_urls')
    def test_existing_mobile_psi_skips_mobile_update(self, mock_batch_write, mock_run_analysis):
        """Test that existing mobile PSI value prevents mobile column update"""
        mock_run_analysis.return_value = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None,
            '_from_cache': False
        }
        
        url_data = (5, 'https://example.com', 'https://existing.mobile.psi', None, False)
        current_idx = 1
        mock_service = Mock()
        
        result = run_audit.process_url(
            url_data,
            'spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            current_idx,
            skip_cache=False
        )
        
        assert result['mobile_score'] == 85
        assert result['desktop_score'] == 90
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 1
        assert (5, 'G', 'passed') in updates
        assert not any(update[1] == 'F' for update in updates)
    
    @patch('run_audit.playwright_runner.run_analysis')
    @patch('run_audit.sheets_client.batch_write_psi_urls')
    def test_existing_desktop_psi_skips_desktop_update(self, mock_batch_write, mock_run_analysis):
        """Test that existing desktop PSI value prevents desktop column update"""
        mock_run_analysis.return_value = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None,
            '_from_cache': False
        }
        
        url_data = (5, 'https://example.com', None, 'https://existing.desktop.psi', False)
        current_idx = 1
        mock_service = Mock()
        
        result = run_audit.process_url(
            url_data,
            'spreadsheet-id',
            'Sheet1',
            mock_service,
            600,
            1,
            current_idx,
            skip_cache=False
        )
        
        assert result['mobile_score'] == 85
        assert result['desktop_score'] == 90
        
        mock_batch_write.assert_called_once()
        updates = mock_batch_write.call_args[0][2]
        assert len(updates) == 1
        assert (5, 'F', 'passed') in updates
        assert not any(update[1] == 'G' for update in updates)


class TestScoreThresholdConstant:
    """Test the SCORE_THRESHOLD constant value"""
    
    def test_score_threshold_is_80(self):
        """Verify that the score threshold is set to 80"""
        assert run_audit.SCORE_THRESHOLD == 80

