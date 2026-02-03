import pytest
import os
import sys
import json
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))

from security.service_account_validator import ServiceAccountValidator
from security.url_filter import URLFilter
from security.audit_trail import AuditTrail
from security.rate_limiter import SpreadsheetRateLimiter


class TestServiceAccountValidator:
    def test_validate_success(self, temp_service_account_file):
        valid, errors = ServiceAccountValidator.validate(temp_service_account_file)
        assert valid is True
        assert len(errors) == 0
    
    def test_validate_missing_file(self):
        valid, errors = ServiceAccountValidator.validate('nonexistent.json')
        assert valid is False
        assert any('not found' in err for err in errors)
    
    def test_validate_invalid_json(self, tmp_path):
        file_path = tmp_path / "invalid.json"
        file_path.write_text("not valid json")
        
        valid, errors = ServiceAccountValidator.validate(str(file_path))
        assert valid is False
        assert any('Invalid JSON format' in err for err in errors)
    
    def test_validate_missing_required_field(self, tmp_path):
        data = {
            "type": "service_account",
            "project_id": "test-project"
        }
        file_path = tmp_path / "incomplete.json"
        file_path.write_text(json.dumps(data))
        
        valid, errors = ServiceAccountValidator.validate(str(file_path))
        assert valid is False
        assert any('Missing required field' in err for err in errors)
    
    def test_validate_wrong_type(self, tmp_path):
        data = {
            "type": "user_account",
            "project_id": "test-project",
            "private_key_id": "key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        file_path = tmp_path / "wrong_type.json"
        file_path.write_text(json.dumps(data))
        
        valid, errors = ServiceAccountValidator.validate(str(file_path))
        assert valid is False
        assert any('Invalid account type' in err for err in errors)


class TestURLFilter:
    def test_whitelist_allowed(self):
        url_filter = URLFilter(whitelist=['https://example.com/*'])
        assert url_filter.is_allowed('https://example.com/path') is True
    
    def test_whitelist_blocked(self):
        url_filter = URLFilter(whitelist=['https://example.com/*'])
        assert url_filter.is_allowed('https://other.com/path') is False
    
    def test_blacklist_blocked(self):
        url_filter = URLFilter(blacklist=['http://*'])
        assert url_filter.is_allowed('http://example.com') is False
    
    def test_blacklist_allowed(self):
        url_filter = URLFilter(blacklist=['http://*'])
        assert url_filter.is_allowed('https://example.com') is True
    
    def test_combined_filters(self):
        url_filter = URLFilter(
            whitelist=['https://*.example.com/*'],
            blacklist=['https://staging.example.com/*']
        )
        assert url_filter.is_allowed('https://www.example.com/path') is True
        assert url_filter.is_allowed('https://staging.example.com/path') is False
        assert url_filter.is_allowed('https://other.com/path') is False
    
    def test_sanitize_url_adds_protocol(self):
        url = URLFilter.sanitize_url('example.com')
        assert url == 'https://example.com'
    
    def test_sanitize_url_valid(self):
        url = URLFilter.sanitize_url('https://example.com/path')
        assert url == 'https://example.com/path'
    
    def test_sanitize_url_dangerous_chars(self):
        with pytest.raises(ValueError, match='dangerous character'):
            URLFilter.sanitize_url('https://example.com/<script>')
    
    def test_sanitize_url_empty(self):
        with pytest.raises(ValueError, match='cannot be empty'):
            URLFilter.sanitize_url('')
    
    def test_sanitize_url_no_domain(self):
        with pytest.raises(ValueError, match='valid domain'):
            URLFilter.sanitize_url('https://')


class TestAuditTrail:
    def test_log_modification(self, tmp_path):
        audit_file = tmp_path / "test_audit.jsonl"
        audit_trail = AuditTrail(str(audit_file))
        
        audit_trail.log_modification(
            spreadsheet_id='test-id',
            tab_name='TestTab',
            row_index=5,
            column='F',
            value='https://example.com',
            user='test_user'
        )
        
        assert audit_file.exists()
        content = audit_file.read_text()
        assert 'test-id' in content
        assert 'TestTab' in content
        assert 'test_user' in content
    
    def test_log_batch_modification(self, tmp_path):
        audit_file = tmp_path / "test_audit.jsonl"
        audit_trail = AuditTrail(str(audit_file))
        
        updates = [
            (5, 'F', 'https://example.com/1'),
            (6, 'G', 'https://example.com/2')
        ]
        
        audit_trail.log_batch_modification(
            spreadsheet_id='test-id',
            tab_name='TestTab',
            updates=updates
        )
        
        assert audit_file.exists()
        lines = audit_file.read_text().strip().split('\n')
        assert len(lines) == 2


class TestSpreadsheetRateLimiter:
    def test_rate_limiter_initial_state(self):
        rate_limiter = SpreadsheetRateLimiter(requests_per_minute=60)
        usage = rate_limiter.get_usage('test-id')
        
        assert usage['current_requests'] == 0
        assert usage['max_requests'] == 60
        assert usage['remaining'] == 60
    
    def test_rate_limiter_acquire(self):
        rate_limiter = SpreadsheetRateLimiter(requests_per_minute=60)
        
        rate_limiter.acquire('test-id')
        usage = rate_limiter.get_usage('test-id')
        
        assert usage['current_requests'] == 1
        assert usage['remaining'] == 59
    
    def test_rate_limiter_multiple_spreadsheets(self):
        rate_limiter = SpreadsheetRateLimiter(requests_per_minute=60)
        
        rate_limiter.acquire('spreadsheet-1')
        rate_limiter.acquire('spreadsheet-2')
        
        usage1 = rate_limiter.get_usage('spreadsheet-1')
        usage2 = rate_limiter.get_usage('spreadsheet-2')
        
        assert usage1['current_requests'] == 1
        assert usage2['current_requests'] == 1
