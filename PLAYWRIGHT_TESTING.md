# Playwright Testing Guide

This document provides comprehensive information about testing the Playwright integration for PageSpeed Insights automation.

## Overview

The Playwright runner (`tools/qa/playwright_runner.py`) is thoroughly tested with unit tests that cover:

- Single URL analysis
- Mobile and desktop score extraction
- Timeout handling
- Retry logic
- Cache integration
- Instance pooling
- Circuit breaker functionality
- Error handling and metrics collection

## Test Structure

### Test File Location
- **File**: `tests/unit/test_playwright_runner.py`
- **Framework**: pytest with unittest.mock
- **Coverage**: All critical functionality including edge cases

### Test Classes

#### 1. `TestSingleURLAnalysis`
Tests the main `run_analysis()` function for single URL processing.

**Test Cases:**
- `test_successful_analysis_mobile_and_desktop`: Verifies successful extraction of both mobile and desktop scores
- `test_analysis_with_low_score_returns_psi_url`: Verifies PSI URLs are returned when scores < 80

#### 2. `TestScoreExtraction`
Tests score extraction from PageSpeed Insights page elements.

**Test Cases:**
- `test_extract_score_with_primary_selector`: Tests score extraction with primary CSS selector
- `test_extract_score_with_fallback_selector`: Tests fallback to alternative selectors
- `test_extract_score_returns_none_when_no_elements`: Tests behavior when score elements not found
- `test_extract_score_handles_invalid_score_text`: Tests handling of non-numeric score text

#### 3. `TestTimeoutHandling`
Tests timeout configuration and progressive timeout functionality.

**Test Cases:**
- `test_analysis_respects_timeout_parameter`: Verifies timeout parameter is respected
- `test_timeout_error_raises_playwright_timeout_error`: Tests timeout exception handling
- `test_progressive_timeout_increases_after_failure`: Tests progressive timeout mechanism
- `test_wait_for_analysis_completion_success`: Tests successful analysis completion wait
- `test_wait_for_analysis_completion_timeout`: Tests timeout during analysis wait

#### 4. `TestRetryLogic`
Tests retry mechanism for transient failures.

**Test Cases:**
- `test_successful_retry_after_transient_failure`: Tests successful retry after initial failure
- `test_exhausted_retries_raises_error`: Tests behavior when all retries exhausted
- `test_permanent_error_no_retry`: Tests that permanent errors are not retried

#### 5. `TestCacheIntegration`
Tests integration with the caching layer.

**Test Cases:**
- `test_cache_hit_returns_cached_result`: Tests cache hit scenario
- `test_cache_miss_performs_analysis_and_caches`: Tests cache miss with subsequent caching
- `test_skip_cache_bypasses_cache_lookup`: Tests cache bypass with `skip_cache=True`

#### 6. `TestPlaywrightPool`
Tests the instance pooling mechanism for warm starts.

**Test Cases:**
- `test_pool_creates_instance_on_first_request`: Tests instance creation
- `test_pool_reuses_idle_instance`: Tests instance reuse for warm starts
- `test_pool_removes_high_memory_instance`: Tests automatic removal of high-memory instances
- `test_pool_removes_instance_after_failures`: Tests removal after consecutive failures
- `test_pool_shutdown_closes_all_instances`: Tests pool cleanup on shutdown

#### 7. `TestPlaywrightInstance`
Tests individual instance functionality.

**Test Cases:**
- `test_instance_is_alive_when_connected`: Tests alive check for connected instances
- `test_instance_not_alive_when_browser_none`: Tests alive check when browser is None
- `test_instance_get_memory_usage`: Tests memory usage monitoring

#### 8. `TestPSIReportURL`
Tests PSI report URL extraction.

**Test Cases:**
- `test_get_psi_report_url_success`: Tests successful URL extraction
- `test_get_psi_report_url_not_psi_page`: Tests handling of non-PSI pages

#### 9. `TestCircuitBreaker`
Tests circuit breaker integration.

**Test Cases:**
- `test_circuit_breaker_opens_after_failures`: Tests circuit opening after threshold failures

#### 10. `TestPlaywrightNotInstalled`
Tests behavior when Playwright is not installed.

**Test Cases:**
- `test_raises_permanent_error_when_not_installed`: Tests PermanentError when Playwright missing

#### 11. `TestMetricsCollection`
Tests metrics collection during analysis.

**Test Cases:**
- `test_metrics_recorded_on_success`: Tests metrics recording on successful analysis
- `test_metrics_recorded_on_failure`: Tests metrics recording on failed analysis

## Running Tests

### Run All Playwright Tests
```bash
pytest tests/unit/test_playwright_runner.py -v
```

### Run Specific Test Class
```bash
pytest tests/unit/test_playwright_runner.py::TestSingleURLAnalysis -v
```

### Run Specific Test
```bash
pytest tests/unit/test_playwright_runner.py::TestSingleURLAnalysis::test_successful_analysis_mobile_and_desktop -v
```

### Run with Coverage
```bash
pytest tests/unit/test_playwright_runner.py --cov=tools.qa.playwright_runner --cov-report=term-missing
```

### Run with Detailed Output
```bash
pytest tests/unit/test_playwright_runner.py -vv -s
```

## Validation Script

### Validate Playwright Setup

Before running tests, validate your Playwright installation:

```bash
python validate_playwright_setup.py
```

This script checks:
- Python version (>= 3.7)
- Playwright package installation
- Playwright Python API imports
- Chromium browser installation
- Required dependencies (psutil, pytest, pytest-mock)

**Example Output:**
```
================================================================================
PLAYWRIGHT SETUP VALIDATION
================================================================================

✓ PASS     | Python Version            | Python 3.11.5
✓ PASS     | Playwright Package        | playwright 1.40.0
✓ PASS     | Playwright Import         | Playwright Python API imports successfully
✓ PASS     | Playwright Browsers       | Playwright Version 1.40.0, Chromium browser installed
✓ PASS     | psutil Package            | psutil 5.9.0
✓ PASS     | pytest Package            | pytest 7.4.0
✓ PASS     | pytest-mock Package       | pytest-mock 3.11.1

================================================================================
✓ All checks passed! Playwright setup is complete.
================================================================================
```

## Test Fixtures

### Mocking Fixtures

The test suite uses comprehensive mocking to avoid actual Playwright browser launches:

- `mock_playwright_available`: Patches `PLAYWRIGHT_AVAILABLE` flag
- `mock_cache_manager`: Mocks the cache manager
- `mock_metrics`: Mocks global error metrics
- `mock_metrics_collector`: Mocks metrics collector
- `mock_page`: Mocks Playwright page object
- `mock_context`: Mocks Playwright browser context
- `mock_browser`: Mocks Playwright browser instance
- `mock_playwright`: Mocks sync_playwright entry point

### Data Fixtures

From `conftest.py`:

- `sample_playwright_result`: Sample passing scores (85 mobile, 90 desktop)
- `sample_playwright_result_failing`: Sample failing scores (65 mobile, 70 desktop)

## Coverage Goals

The test suite aims for **>90% code coverage** of `playwright_runner.py`:

**Covered Areas:**
- ✓ Main `run_analysis()` function
- ✓ Internal `_run_analysis_once()` function
- ✓ Score extraction (`_extract_score_from_element`)
- ✓ PSI URL extraction (`_get_psi_report_url`)
- ✓ Analysis completion wait (`_wait_for_analysis_completion`)
- ✓ Instance pooling (PlaywrightPool)
- ✓ Instance management (PlaywrightInstance)
- ✓ Progressive timeout (ProgressiveTimeout)
- ✓ Cache integration
- ✓ Retry logic
- ✓ Circuit breaker integration
- ✓ Error handling and metrics

## Comparison with Cypress Behavior

The tests verify that Playwright implementation matches the expected Cypress behavior:

| Feature | Cypress | Playwright | Test Coverage |
|---------|---------|------------|---------------|
| Single URL analysis | ✓ | ✓ | ✓ |
| Mobile score extraction | ✓ | ✓ | ✓ |
| Desktop score extraction | ✓ | ✓ | ✓ |
| Timeout handling | ✓ | ✓ | ✓ |
| Retry on failure | ✓ | ✓ | ✓ |
| Cache integration | ✓ | ✓ | ✓ |
| PSI URL generation | ✓ | ✓ | ✓ |
| Instance pooling | ✗ | ✓ | ✓ |
| Memory monitoring | ✗ | ✓ | ✓ |
| Circuit breaker | ✗ | ✓ | ✓ |

## Best Practices

### Writing New Playwright Tests

1. **Mock External Dependencies**: Always mock Playwright browser instances to avoid launching actual browsers in tests
2. **Test Edge Cases**: Include tests for timeouts, failures, retries, and error conditions
3. **Use Descriptive Names**: Test names should clearly describe the scenario being tested
4. **Verify Side Effects**: Check that metrics, cache, and logging are called appropriately
5. **Reset Globals**: Use the `reset_globals` fixture to ensure test isolation

### Example Test Pattern

```python
def test_new_feature(mock_playwright_available, mock_cache_manager, mock_metrics):
    # Arrange
    with patch('tools.qa.playwright_runner._run_analysis_once') as mock_run:
        mock_run.return_value = {
            'mobile_score': 85,
            'desktop_score': 90,
            'mobile_psi_url': None,
            'desktop_psi_url': None,
            '_warm_start': False
        }
        
        # Act
        result = run_analysis('https://example.com')
        
        # Assert
        assert result['mobile_score'] == 85
        mock_metrics.record_success.assert_called()
```

## Troubleshooting

### Tests Fail with ImportError

**Problem**: `ImportError: No module named 'playwright'`

**Solution**:
```bash
pip install -r requirements.txt
playwright install chromium
```

### Tests Fail with "Playwright not available"

**Problem**: Playwright installation incomplete

**Solution**:
```bash
python validate_playwright_setup.py
```

Follow the recommendations from the validation script.

### Mock Assertions Fail

**Problem**: Mock method not called as expected

**Solution**: Verify you're patching at the correct import location. Use `patch('module.where.used')` not `patch('module.where.defined')`.

### Global State Pollution

**Problem**: Tests fail when run together but pass individually

**Solution**: Ensure the `reset_globals` fixture is used (it's autouse, so should be automatic). Check for any state that persists between tests.

## CI/CD Integration

The Playwright tests run automatically in CI/CD pipelines:

```bash
# In CI pipeline
pytest tests/unit/test_playwright_runner.py --cov=tools.qa.playwright_runner --cov-report=xml
```

Coverage reports are generated and can be uploaded to coverage tracking services.

## Future Enhancements

Potential test improvements:

1. **Integration Tests**: Add tests that use real Playwright browsers (marked as `@pytest.mark.slow`)
2. **Performance Tests**: Add tests to verify warm start performance improvements
3. **Stress Tests**: Add tests for concurrent instance pool usage
4. **Visual Regression**: Add screenshot comparison tests for PSI page structure changes

## References

- [Playwright Documentation](https://playwright.dev/python/)
- [pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [pytest-mock Documentation](https://pytest-mock.readthedocs.io/)
