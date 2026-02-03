# Test Suite Documentation

This directory contains comprehensive tests for the PageSpeed Insights Audit Tool.

## Structure

```
tests/
├── conftest.py              # Pytest fixtures and shared test configuration
├── unit/                    # Unit tests for individual components
│   ├── test_sheets_client.py    # Tests for Google Sheets API wrapper
│   ├── test_cypress_runner.py   # Tests for Cypress automation wrapper
│   └── test_logger.py           # Tests for logging utilities
└── integration/             # Integration tests
    └── test_run_audit.py        # Tests for main audit orchestration
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run unit tests only
```bash
pytest tests/unit/
```

### Run integration tests only
```bash
pytest tests/integration/
```

### Run tests with coverage
```bash
pytest --cov=tools --cov=run_audit --cov-report=html --cov-report=term-missing
```

### Run tests with coverage and check 70% threshold
```bash
pytest --cov=tools --cov=run_audit --cov-report=term-missing
coverage report --fail-under=70
```

### Run specific test file
```bash
pytest tests/unit/test_sheets_client.py
```

### Run specific test class
```bash
pytest tests/unit/test_sheets_client.py::TestAuthenticate
```

### Run specific test method
```bash
pytest tests/unit/test_sheets_client.py::TestAuthenticate::test_authenticate_success
```

### Run tests with verbose output
```bash
pytest -v
```

### Run tests and stop at first failure
```bash
pytest -x
```

## Test Coverage

The test suite aims for a minimum of 70% code coverage. Current coverage includes:

- **sheets_client.py**: Authentication, reading/writing URLs, rate limiting, error handling
- **cypress_runner.py**: Cypress execution, retries, timeout handling, result parsing
- **logger.py**: Logger setup, file/console handlers, thread safety
- **run_audit.py**: URL processing, error handling, concurrent execution, signal handling

## Fixtures

Shared fixtures are defined in `conftest.py`:

- `mock_google_service`: Mock Google Sheets API service
- `mock_credentials`: Mock Google service account credentials
- `sample_spreadsheet_data`: Sample spreadsheet metadata
- `sample_urls`: Sample URL data for testing
- `sample_cypress_result`: Sample Cypress result (passing scores)
- `sample_cypress_result_failing`: Sample Cypress result (failing scores)
- `temp_service_account_file`: Temporary service account JSON file

## Test Categories

Tests are marked with the following categories:

- `@pytest.mark.unit`: Unit tests (isolated component tests)
- `@pytest.mark.integration`: Integration tests (multi-component tests)
- `@pytest.mark.slow`: Tests that take longer to execute

Run specific categories:
```bash
pytest -m unit
pytest -m integration
```

## Writing New Tests

When adding new tests:

1. Follow the existing naming convention: `test_<function_name>_<scenario>`
2. Use descriptive test names that explain what is being tested
3. Mock external dependencies (API calls, file I/O, subprocess calls)
4. Test both success and failure scenarios
5. Test edge cases and error conditions
6. Add docstrings for complex test scenarios
7. Use fixtures for common test setup

### Example Test Structure

```python
class TestMyFunction:
    def test_my_function_success(self, mock_dependency):
        # Arrange
        mock_dependency.return_value = "expected"
        
        # Act
        result = my_function()
        
        # Assert
        assert result == "expected"
        mock_dependency.assert_called_once()
    
    def test_my_function_error(self, mock_dependency):
        mock_dependency.side_effect = Exception("Error")
        
        with pytest.raises(Exception, match="Error"):
            my_function()
```

## Continuous Integration

Tests run automatically on GitHub Actions for:
- Push to main/develop branches
- Pull requests to main/develop branches
- Multiple Python versions (3.8, 3.9, 3.10, 3.11)

The CI workflow:
1. Runs unit tests with coverage
2. Runs integration tests
3. Checks coverage threshold (70%)
4. Uploads coverage reports to Codecov
5. Runs linting checks (flake8, black, isort)

## Troubleshooting

### ImportError: No module named 'X'
Install test dependencies:
```bash
pip install -r requirements.txt
```

### Coverage below threshold
Run coverage report to see which lines are missing:
```bash
pytest --cov=tools --cov=run_audit --cov-report=term-missing
```

### Test failures due to mocking issues
Ensure you're patching at the correct import path. Use `patch('module.where.used')`, not `patch('module.where.defined')`.

### Tests pass locally but fail in CI
Check Python version compatibility. CI runs tests on multiple Python versions.

## Best Practices

1. **Keep tests fast**: Mock slow operations (API calls, file I/O, sleep)
2. **Keep tests isolated**: Each test should be independent
3. **Keep tests readable**: Use clear variable names and comments
4. **Keep tests maintainable**: Don't duplicate test code; use fixtures
5. **Test behavior, not implementation**: Focus on what the code does, not how
6. **Test error paths**: Test failure scenarios as thoroughly as success scenarios
