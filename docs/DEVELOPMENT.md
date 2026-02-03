# Development Guide

Complete guide for setting up the development environment and contributing to the PageSpeed Insights Audit Tool.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Local Setup](#local-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style](#code-style)
- [Debugging](#debugging)
- [Common Development Tasks](#common-development-tasks)
- [Performance Profiling](#performance-profiling)
- [Contributing](#contributing)

## Prerequisites

### Required Software

- **Python 3.7+** ([Download](https://www.python.org/downloads/))
- **Node.js 14+** and npm ([Download](https://nodejs.org/))
- **Git** ([Download](https://git-scm.com/))
- **Redis** (optional, for cache development) ([Download](https://redis.io/download))

### Recommended Tools

- **Visual Studio Code** or **PyCharm** (IDE)
- **Postman** (API testing)
- **Redis Desktop Manager** (Redis GUI)
- **Chrome DevTools** (Cypress debugging)

## Local Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd pagespeed-audit-tool
```

### 2. Python Environment Setup

#### Option A: Using venv (Recommended)

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov pytest-mock black flake8 mypy pylint
```

#### Option B: Using conda

```bash
# Create conda environment
conda create -n psi-audit python=3.9

# Activate environment
conda activate psi-audit

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov pytest-mock black flake8 mypy pylint
```

### 3. Node.js Dependencies

```bash
# Install Node.js packages
npm install

# Verify Cypress installation
npx cypress verify
```

### 4. Google Cloud Setup

#### Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Navigate to **IAM & Admin > Service Accounts**
4. Click **Create Service Account**
5. Name it `psi-audit-dev`
6. Download JSON key and save as `service-account.json`

#### Enable APIs

```bash
# Enable Google Sheets API
gcloud services enable sheets.googleapis.com --project=YOUR_PROJECT_ID
```

#### Share Test Spreadsheet

1. Create a test spreadsheet in Google Sheets
2. Share with service account email (from JSON file)
3. Grant **Editor** permissions
4. Save spreadsheet ID for testing

### 5. Environment Configuration

Create `.env` file in project root:

```bash
# Cache configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# File cache (fallback)
CACHE_DIR=.cache
CACHE_MAX_ENTRIES=1000

# Development settings
SPREADSHEET_ID=your_test_spreadsheet_id
SERVICE_ACCOUNT_FILE=service-account.json
```

### 6. Redis Setup (Optional)

#### Windows

```bash
# Using WSL
wsl sudo apt-get install redis-server
wsl sudo service redis-server start
```

#### macOS

```bash
# Using Homebrew
brew install redis
brew services start redis
```

#### Linux

```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

#### Verify Redis

```bash
redis-cli ping
# Expected: PONG
```

### 7. Verify Setup

```bash
# Run setup validator
python validate_setup.py

# Expected output:
# ✓ Python version: 3.x.x
# ✓ Node.js version: 14.x.x
# ✓ Cypress installed
# ✓ Service account file exists
# ✓ All Python packages installed
# ✓ Redis connection (if configured)
```

## Project Structure

```
.
├── run_audit.py              # Main entry point
├── generate_report.py        # Metrics dashboard generator
├── list_tabs.py              # Utility to list spreadsheet tabs
├── invalidate_cache.py       # Cache management utility
├── query_audit_trail.py      # Audit trail query utility
├── validate_setup.py         # Setup validation script
│
├── tools/                    # Core library modules
│   ├── __init__.py
│   │
│   ├── sheets/              # Google Sheets integration
│   │   ├── __init__.py
│   │   ├── sheets_client.py          # API wrapper
│   │   ├── schema_validator.py       # Schema validation
│   │   └── data_quality_checker.py   # Duplicate detection
│   │
│   ├── qa/                  # Browser automation
│   │   ├── __init__.py
│   │   └── cypress_runner.py         # Cypress wrapper with pooling
│   │
│   ├── cache/               # Caching layer
│   │   ├── __init__.py
│   │   └── cache_manager.py          # Redis + file backends
│   │
│   ├── metrics/             # Metrics collection
│   │   ├── __init__.py
│   │   └── metrics_collector.py      # Prometheus metrics
│   │
│   ├── security/            # Security features
│   │   ├── __init__.py
│   │   ├── service_account_validator.py
│   │   ├── rate_limiter.py
│   │   ├── url_filter.py
│   │   └── audit_trail.py
│   │
│   └── utils/               # Utility modules
│       ├── __init__.py
│       ├── logger.py                 # Structured logging
│       ├── url_validator.py          # URL validation
│       ├── exceptions.py             # Custom exceptions
│       ├── error_metrics.py          # Error tracking
│       ├── circuit_breaker.py        # Circuit breaker pattern
│       └── retry.py                  # Retry logic
│
├── cypress/                 # Cypress test automation
│   ├── e2e/
│   │   └── analyze-url.cy.js        # PageSpeed Insights test
│   ├── results/             # Generated results (gitignored)
│   └── cypress.config.js    # Cypress configuration
│
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures
│   │
│   ├── unit/                # Unit tests
│   │   ├── test_sheets_client.py
│   │   ├── test_cypress_runner.py
│   │   ├── test_logger.py
│   │   └── test_security.py
│   │
│   └── integration/         # Integration tests
│       ├── test_run_audit.py
│       └── test_end_to_end.py
│
├── docs/                    # Documentation
│   ├── ARCHITECTURE.md
│   ├── API.md
│   └── DEVELOPMENT.md       # This file
│
├── logs/                    # Application logs (gitignored)
├── .cache/                  # File cache (gitignored)
├── .venv/                   # Virtual environment (gitignored)
│
├── requirements.txt         # Python dependencies
├── package.json             # Node.js dependencies
├── pytest.ini               # Pytest configuration
├── .gitignore              # Git ignore rules
└── README.md               # Main documentation
```

## Development Workflow

### 1. Feature Development

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes
# ... edit files ...

# Run tests
pytest tests/

# Run linter
flake8 tools/ run_audit.py

# Format code
black tools/ run_audit.py

# Commit changes
git add .
git commit -m "Add my feature"

# Push to remote
git push origin feature/my-feature
```

### 2. Running in Development Mode

```bash
# Run with verbose logging
python run_audit.py --tab "Test Tab" --service-account service-account.json

# Run with cache disabled (for testing)
python run_audit.py --tab "Test Tab" --skip-cache

# Run in dry-run mode (no spreadsheet writes)
python run_audit.py --tab "Test Tab" --dry-run

# Run with single worker (for debugging)
python run_audit.py --tab "Test Tab" --concurrency 1
```

### 3. Testing Changes

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_cypress_runner.py

# Run with coverage
pytest --cov=tools --cov=run_audit --cov-report=html

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x
```

### 4. Code Quality Checks

```bash
# Lint with flake8
flake8 tools/ run_audit.py --max-line-length=120

# Format with black
black tools/ run_audit.py --line-length=120

# Type check with mypy
mypy tools/ run_audit.py --ignore-missing-imports

# Full quality check
flake8 tools/ && black --check tools/ && mypy tools/
```

## Testing

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage report
pytest --cov=tools --cov=run_audit --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=tools --cov=run_audit --cov-report=html
# Open htmlcov/index.html in browser

# Using convenience scripts
# Windows
.\run_tests.ps1
# Unix/Linux
./run_tests.sh

# Using Make (Unix/Linux)
make test
make test-cov
```

### Writing Tests

#### Unit Test Example

```python
# tests/unit/test_my_module.py
import pytest
from tools.my_module import MyClass

@pytest.fixture
def my_fixture():
    return MyClass()

def test_my_function(my_fixture):
    result = my_fixture.my_method()
    assert result == expected_value

def test_error_handling(my_fixture):
    with pytest.raises(ValueError):
        my_fixture.invalid_method()
```

#### Integration Test Example

```python
# tests/integration/test_my_integration.py
import pytest
from tools.sheets import sheets_client
from tools.qa import cypress_runner

@pytest.mark.integration
def test_full_workflow(mock_service_account):
    # Setup
    service = sheets_client.authenticate(mock_service_account)
    
    # Execute
    urls = sheets_client.read_urls('test_id', 'Test Tab', service=service)
    result = cypress_runner.run_analysis(urls[0][1])
    
    # Verify
    assert result['mobile_score'] is not None
    assert result['desktop_score'] is not None
```

### Test Fixtures

Common fixtures are defined in `tests/conftest.py`:

```python
@pytest.fixture
def mock_sheets_service():
    """Mock Google Sheets service"""
    # Implementation
    pass

@pytest.fixture
def sample_urls():
    """Sample URL data for testing"""
    return [
        (2, 'https://example.com', None, None, False),
        (3, 'https://test.com', None, None, False),
    ]
```

### Mocking External Services

```python
from unittest.mock import Mock, patch

def test_with_mock():
    with patch('tools.sheets.sheets_client.build') as mock_build:
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        # Test code
        service = sheets_client.authenticate('fake.json')
        assert service == mock_service
```

## Code Style

### PEP 8 Guidelines

- Maximum line length: 120 characters
- 4 spaces for indentation (no tabs)
- 2 blank lines between top-level functions/classes
- 1 blank line between methods
- Use descriptive variable names

### Type Hints

Always use type hints for function parameters and returns:

```python
from typing import List, Dict, Optional, Tuple

def my_function(
    url: str,
    timeout: int = 600,
    options: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """
    Function description.
    
    Args:
        url: The URL to process
        timeout: Maximum wait time in seconds
        options: Optional configuration dictionary
        
    Returns:
        Tuple of (success, message)
    """
    pass
```

### Docstrings

Use Google-style docstrings:

```python
def complex_function(param1: str, param2: int) -> Dict[str, Any]:
    """
    Brief description of function.
    
    Longer description with details about what this function does,
    edge cases, and important notes.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
        
    Returns:
        Dictionary containing:
            - key1: Description
            - key2: Description
            
    Raises:
        ValueError: If param1 is empty
        RuntimeError: If operation fails
        
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result['key1'])
        value1
    """
    pass
```

### Error Handling

Use custom exception types:

```python
from tools.utils.exceptions import PermanentError, RetryableError

def my_operation():
    try:
        # Operation
        pass
    except NetworkError as e:
        # Transient error - can retry
        raise RetryableError("Network failed", original_exception=e)
    except InvalidDataError as e:
        # Permanent error - no retry
        raise PermanentError("Invalid data", original_exception=e)
```

### Logging

Use structured logging with context:

```python
from tools.utils.logger import get_logger, log_error_with_context

log = get_logger()

log.info("Starting operation", extra={'url': url, 'retry': attempt})

try:
    # Operation
    pass
except Exception as e:
    log_error_with_context(
        log,
        "Operation failed",
        exception=e,
        context={'url': url, 'attempt': attempt}
    )
```

## Debugging

### Python Debugging

#### Using pdb

```python
import pdb

def my_function():
    # Set breakpoint
    pdb.set_trace()
    
    # Code continues here
    pass
```

#### Using VS Code Debugger

Create `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Run Audit",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/run_audit.py",
            "args": ["--tab", "Test Tab", "--concurrency", "1"],
            "console": "integratedTerminal"
        },
        {
            "name": "Python: Current File",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal"
        }
    ]
}
```

### Cypress Debugging

#### Open Cypress UI

```bash
# Run Cypress in headed mode
npx cypress open

# Select test: analyze-url.cy.js
# Watch test execution in browser
```

#### Debug Specific URL

```bash
# Set environment variable
export CYPRESS_TEST_URL=https://example.com

# Run single test
npx cypress run --spec cypress/e2e/analyze-url.cy.js --headed --browser chrome
```

#### View Cypress Logs

```bash
# Enable debug logging
DEBUG=cypress:* npx cypress run

# View screenshots (on failure)
ls cypress/screenshots/

# View videos (if enabled)
ls cypress/videos/
```

### Redis Debugging

```bash
# Monitor Redis commands
redis-cli monitor

# Check keys
redis-cli keys "psi:*"

# Get specific key
redis-cli get "psi:abc123..."

# Check memory usage
redis-cli info memory
```

### Log Analysis

```bash
# View latest log
tail -f logs/audit_*.log

# Search for errors
grep -i "error" logs/audit_*.log

# Search for specific URL
grep "example.com" logs/audit_*.log

# Count errors by type
grep "ERROR" logs/audit_*.log | cut -d'-' -f4 | sort | uniq -c
```

## Common Development Tasks

### Add New Command-Line Argument

1. Edit `run_audit.py`:

```python
parser.add_argument(
    '--my-option',
    type=str,
    default='default_value',
    help='Description of my option'
)
```

2. Use in code:

```python
my_value = args.my_option
```

### Add New Metric

1. Edit `tools/metrics/metrics_collector.py`:

```python
def __init__(self):
    # Add new metric
    self._my_new_metric = 0

def record_my_metric(self, value: int):
    with self._lock:
        self._my_new_metric += value

def get_metrics(self):
    return {
        # ... existing metrics ...
        'my_new_metric': self._my_new_metric
    }
```

2. Use in code:

```python
from tools.metrics.metrics_collector import get_metrics_collector

metrics = get_metrics_collector()
metrics.record_my_metric(42)
```

### Add New Cache Backend

1. Create backend class in `tools/cache/cache_manager.py`:

```python
class MyBackend(CacheBackend):
    def get(self, key: str) -> Optional[Dict]:
        # Implementation
        pass
    
    def set(self, key: str, value: Dict, ttl: int) -> bool:
        # Implementation
        pass
```

2. Update `CacheManager._initialize_default_backend()`:

```python
def _initialize_default_backend(self):
    backend_type = os.environ.get('CACHE_BACKEND', 'redis')
    
    if backend_type == 'my_backend':
        return MyBackend(...)
    # ... existing backends ...
```

### Add New Validation Check

1. Edit `tools/utils/url_validator.py`:

```python
def my_validation_check(self, url: str) -> Tuple[bool, Optional[str]]:
    """
    New validation check.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Implementation
    if not valid:
        return False, "Error message"
    return True, None
```

2. Add to `validate_url()`:

```python
def validate_url(self, url: str) -> Tuple[bool, dict]:
    # ... existing checks ...
    
    my_valid, my_error = self.my_validation_check(url)
    results['my_check_valid'] = my_valid
    if my_error:
        results['errors'].append(my_error)
    
    # ... rest of validation ...
```

## Performance Profiling

### Python Profiling

```bash
# Profile with cProfile
python -m cProfile -o profile.stats run_audit.py --tab "Test Tab"

# View results
python -m pstats profile.stats
# Then: sort cumulative, stats 20
```

### Memory Profiling

```bash
# Install memory_profiler
pip install memory_profiler

# Profile specific function
python -m memory_profiler run_audit.py
```

### Benchmark Script

```python
import time
from tools.qa import cypress_runner

urls = ['https://example1.com', 'https://example2.com', 'https://example3.com']

start = time.time()
for url in urls:
    result = cypress_runner.run_analysis(url)
elapsed = time.time() - start

print(f"Processed {len(urls)} URLs in {elapsed:.2f}s")
print(f"Average: {elapsed/len(urls):.2f}s per URL")
```

## Contributing

### Pull Request Process

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### PR Checklist

- [ ] Tests pass (`pytest`)
- [ ] Code is formatted (`black`)
- [ ] No linter errors (`flake8`)
- [ ] Type hints added (`mypy`)
- [ ] Docstrings updated
- [ ] Documentation updated (if needed)
- [ ] CHANGELOG.md updated
- [ ] No secrets in code/commits

### Code Review Guidelines

- Keep PRs focused and small
- Write clear commit messages
- Add tests for new features
- Update documentation
- Respond to review comments promptly

### Development Principles

1. **Test-Driven Development**: Write tests before code
2. **Fail Fast**: Validate early, fail with clear errors
3. **Defensive Programming**: Check inputs, handle edge cases
4. **Logging**: Log important operations with context
5. **Error Handling**: Use custom exception types
6. **Performance**: Profile before optimizing
7. **Security**: Validate all inputs, never log secrets
8. **Documentation**: Code should be self-documenting

## Troubleshooting

### Common Issues

#### "npx not found"

```bash
# Reinstall Node.js or add to PATH
npm install -g npm
```

#### "Redis connection failed"

```bash
# Start Redis
redis-server

# Or use file cache
export REDIS_HOST=  # Empty to disable Redis
```

#### "Service account authentication failed"

```bash
# Validate JSON file
python validate_service_account.py service-account.json

# Re-download from Google Cloud Console
```

#### "Cypress test fails"

```bash
# Run in headed mode to see what's happening
npx cypress open

# Check PageSpeed Insights is accessible
curl https://pagespeed.web.dev

# Update selectors in analyze-url.cy.js if UI changed
```

#### "Import errors"

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check Python path
python -c "import sys; print(sys.path)"
```

## Resources

- [Python Documentation](https://docs.python.org/3/)
- [Cypress Documentation](https://docs.cypress.io/)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [Redis Documentation](https://redis.io/documentation)
- [Pytest Documentation](https://docs.pytest.org/)
- [Black Code Formatter](https://black.readthedocs.io/)
