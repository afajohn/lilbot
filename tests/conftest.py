import pytest
import os
import sys
from unittest.mock import Mock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))


@pytest.fixture
def mock_google_service():
    service = Mock()
    service.spreadsheets = Mock(return_value=Mock())
    return service


@pytest.fixture
def mock_credentials():
    credentials = Mock()
    credentials.expired = False
    credentials.valid = True
    return credentials


@pytest.fixture
def sample_spreadsheet_data():
    return {
        'spreadsheetId': 'test-spreadsheet-id',
        'sheets': [
            {'properties': {'title': 'Sheet1'}},
            {'properties': {'title': 'Sheet2'}},
        ]
    }


@pytest.fixture
def sample_urls():
    return [
        (2, 'https://example.com', None, None, False),
        (3, 'https://google.com', None, None, False),
        (4, 'https://github.com', 'https://psi.url/mobile', None, False),
    ]


@pytest.fixture
def sample_cypress_result():
    return {
        'mobile': {
            'score': 85,
            'reportUrl': None
        },
        'desktop': {
            'score': 90,
            'reportUrl': None
        }
    }


@pytest.fixture
def sample_cypress_result_failing():
    return {
        'mobile': {
            'score': 65,
            'reportUrl': 'https://pagespeed.web.dev/mobile-report'
        },
        'desktop': {
            'score': 70,
            'reportUrl': 'https://pagespeed.web.dev/desktop-report'
        }
    }


@pytest.fixture
def temp_service_account_file(tmp_path):
    service_account_data = {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "key-id",
        "private_key": "-----BEGIN PRIVATE KEY-----\\ntest\\n-----END PRIVATE KEY-----\\n",
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "client_id": "123456789",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
    }
    
    import json
    file_path = tmp_path / "test-service-account.json"
    file_path.write_text(json.dumps(service_account_data))
    return str(file_path)
