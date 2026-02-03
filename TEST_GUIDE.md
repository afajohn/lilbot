# Testing Guide

This document provides a comprehensive guide for running and understanding the test suite.

## Table of Contents
- [Quick Start](#quick-start)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Coverage Reports](#coverage-reports)
- [Writing Tests](#writing-tests)
- [Continuous Integration](#continuous-integration)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Installation
```bash
# Install all dependencies including test dependencies
pip install -r requirements.txt
npm install
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tools --cov=run_audit --cov-report=term-missing

# Run and check 70% coverage threshold
coverage report --fail-under=70
```

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures and test configuration
├── unit/                            # Unit tests (isolated component tests)
│   ├── test_sheets_client.py       # Google Sheets API wrapper tests (13 test classes, 30+ tests)
│   ├── test_cypress_runner.py      # Cypress automation tests (4 test classes, 15+ tests)
│   └── test_logger.py              # Logging utilities tests (3 test classes, 10+ tests)
└── integration/                     # Integration tests (multi-component tests)
    ├── test_run_audit.py           # Main audit orchestration tests (4 test classes, 15+ tests)
    └── test_end_to_end.py          # End-to-end workflow tests (2 test classes, 10+ tests)
```

### Test Categories

- **Unit Tests**: Test individual functions and classes in isolation
  - Mock all external dependencies (API calls, file I/O, subprocess)
  - Fast execution (< 1 second per test)
  - Focus on edge cases and error handling
  
- **Integration Tests**: Test interactions between components
  - Test complete workflows
  - Verify component integration
  - Test concurrent execution scenarios

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run specific test file
pytest tests/unit/test_sheets_client.py

# Run specific test class
pytest tests/unit/test_sheets_client.py::TestAuthenticate

# Run specific test method
pytest tests/unit/test_sheets_client.py::TestAuthenticate::test_authenticate_success

# Run with verbose output
pytest -v

# Run and stop at first failure
pytest -x

# Run tests matching a pattern
pytest -k "authenticate"
```

### Using Convenience Scripts

#### Windows (PowerShell)
```powershell
# Run all tests
.\run_tests.ps1

# Run unit tests with verbose output
.\run_tests.ps1 unit -Verbose

# Run integration tests
.\run_tests.ps1 integration

# Run with coverage and HTML report
.\run_tests.ps1 coverage -Html

# Install dependencies
.\run_tests.ps1 install

# Clean test artifacts
.\run_tests.ps1 clean
```

#### Unix/Linux/Mac (Bash)
```bash
# Make script executable (first time only)
chmod +x run_tests.sh

# Run all tests
./run_tests.sh

# Run unit tests with verbose output
./run_tests.sh unit --verbose

# Run integration tests
./run_tests.sh integration

# Run with coverage and HTML report
./run_tests.sh coverage --html

# Install dependencies
./run_tests.sh install

# Clean test artifacts
./run_tests.sh clean
```

#### Using Make (Unix/Linux/Mac)
```bash
# Run all tests
make test

# Run unit tests
make test-unit

# Run integration tests
make test-integration

# Run with coverage
make test-cov

# Run with HTML coverage report
make test-cov-html

# Run and check 70% threshold
make test-cov-check

# Install dependencies
make install

# Clean artifacts
make clean
```

## Coverage Reports

### Generating Coverage Reports

```bash
# Terminal report
pytest --cov=tools --cov=run_audit --cov-report=term-missing

# XML report (for CI/CD)
pytest --cov=tools --cov=run_audit --cov-report=xml

# HTML report (most detailed)
pytest --cov=tools --cov=run_audit --cov-report=html

# Multiple report formats
pytest --cov=tools --cov=run_audit --cov-report=term-missing --cov-report=html --cov-report=xml
```

### Viewing Coverage Reports

**Terminal Report**: Displayed directly in console with missing lines highlighted

**HTML Report**: 
```bash
# Generate report
pytest --cov=tools --cov=run_audit --cov-report=html

# Open in browser (Windows)
start htmlcov/index.html

# Open in browser (Mac)
open htmlcov/index.html

# Open in browser (Linux)
xdg-open htmlcov/index.html
```

**XML Report**: Located at `coverage.xml`, used by CI/CD tools and Codecov

### Coverage Threshold

The project has a **70% code coverage** target:

```bash
# Check if coverage meets threshold
coverage report --fail-under=70

# Exit code 0 if >= 70%, non-zero otherwise
```

### Current Coverage Areas

- ✅ **sheets_client.py**: Authentication, URL reading/writing, rate limiting, error handling
- ✅ **cypress_runner.py**: Cypress execution, retries, timeout handling, result parsing
- ✅ **logger.py**: Logger setup, file/console handlers, thread safety
- ✅ **run_audit.py**: URL processing, concurrent execution, error handling, signal handling

## Writing Tests

### Test Naming Convention

```python
# Class names: Test<ComponentName>
class TestAuthenticate:
    pass

# Method names: test_<function_name>_<scenario>
def test_authenticate_success(self):
    pass

def test_authenticate_file_not_found(self):
    pass

def test_authenticate_invalid_credentials(self):
    pass
```

### Test Structure (AAA Pattern)

```python
def test_example(self, mock_dependency):
    # Arrange - Set up test data and mocks
    mock_dependency.return_value = "expected"
    input_data = {"key": "value"}
    
    # Act - Execute the function being tested
    result = function_under_test(input_data)
    
    # Assert - Verify the results
    assert result == "expected"
    mock_dependency.assert_called_once_with(input_data)
```

### Using Fixtures

```python
# Use fixtures from conftest.py
def test_with_fixtures(self, mock_google_service, sample_urls):
    # mock_google_service and sample_urls are automatically provided
    result = process_urls(sample_urls, mock_google_service)
    assert len(result) > 0
```

### Mocking External Dependencies

```python
from unittest.mock import Mock, patch, MagicMock

# Mock a function
@patch('module.function')
def test_with_mock(mock_function):
    mock_function.return_value = "mocked"
    result = call_function()
    assert result == "mocked"

# Mock a class
@patch('module.MyClass')
def test_with_mock_class(MockClass):
    mock_instance = MockClass.return_value
    mock_instance.method.return_value = "value"
    # Test code here

# Mock multiple functions
@patch('module.function2')
@patch('module.function1')
def test_multiple_mocks(mock_func1, mock_func2):
    # Note: decorators are applied bottom-up
    pass
```

### Testing Exceptions

```python
import pytest

def test_raises_exception(self):
    with pytest.raises(ValueError, match="Invalid input"):
        function_that_raises("invalid")

def test_specific_exception(self):
    with pytest.raises(FileNotFoundError):
        open_nonexistent_file()
```

### Testing Async/Threading

```python
import threading

def test_thread_safe_function(self):
    results = []
    
    def worker():
        result = thread_safe_function()
        results.append(result)
    
    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(results) == 10
    assert all(r is not None for r in results)
```

## Continuous Integration

### GitHub Actions Workflow

Tests run automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches
- Manual workflow dispatch

### CI Pipeline Steps

1. **Setup**: Install Python and Node.js dependencies
2. **Unit Tests**: Run with coverage tracking
3. **Integration Tests**: Run with coverage (appended)
4. **Coverage Check**: Verify 70% threshold
5. **Upload Reports**: Send to Codecov
6. **Lint**: Run flake8, black, isort

### Matrix Testing

Tests run on multiple Python versions:
- Python 3.8
- Python 3.9
- Python 3.10
- Python 3.11

### Viewing CI Results

1. Go to GitHub repository
2. Click "Actions" tab
3. Select workflow run
4. View test results and coverage reports

## Troubleshooting

### Common Issues

#### ImportError: No module named 'X'
```bash
# Solution: Install test dependencies
pip install -r requirements.txt
```

#### Coverage below 70% threshold
```bash
# Solution: Check what's missing
pytest --cov=tools --cov=run_audit --cov-report=term-missing

# Lines with "missing" indicators need tests
```

#### Test failures due to mocking
```bash
# Issue: Patching at wrong import path
# Wrong:
@patch('sheets.sheets_client.authenticate')  # Where defined

# Correct:
@patch('run_audit.sheets_client.authenticate')  # Where used
```

#### Fixtures not found
```bash
# Issue: conftest.py not in test directory tree
# Solution: Ensure conftest.py exists in tests/ directory
pytest --fixtures  # List available fixtures
```

#### Tests pass locally but fail in CI
```bash
# Issue: Python version incompatibility
# Solution: Test locally with different Python versions
python3.8 -m pytest
python3.9 -m pytest
python3.10 -m pytest
python3.11 -m pytest
```

### Debug Options

```bash
# Print stdout/stderr during tests
pytest -s

# Show local variables on failures
pytest -l

# Full traceback
pytest --tb=long

# Disable warnings
pytest --disable-warnings

# Run last failed tests only
pytest --lf

# Step through debugger on failure
pytest --pdb
```

### Getting Help

```bash
# Show available pytest options
pytest --help

# Show available fixtures
pytest --fixtures

# Show test collection tree
pytest --collect-only

# Show test markers
pytest --markers
```

## Best Practices

1. **Write tests first** (TDD) or immediately after implementing features
2. **Keep tests independent** - each test should run in isolation
3. **Mock external dependencies** - don't make real API calls or write real files
4. **Test edge cases** - empty inputs, None values, maximum values
5. **Test error paths** - exceptions, timeouts, rate limits
6. **Use descriptive names** - test names should describe what they test
7. **Keep tests fast** - unit tests should run in milliseconds
8. **Maintain high coverage** - aim for 70%+ overall, 100% for critical paths
9. **Review coverage reports** - identify untested code paths
10. **Update tests when code changes** - keep tests synchronized with implementation

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Python unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Testing Best Practices](https://docs.pytest.org/en/stable/goodpractices.html)
