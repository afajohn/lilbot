# Playwright Testing Quick Start

Quick reference for validating and testing the Playwright implementation.

## Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Validation

### Validate Playwright Setup

```bash
python validate_playwright_setup.py
```

**What it checks:**
- ✓ Python version >= 3.7
- ✓ Playwright package installed
- ✓ Playwright Python API imports
- ✓ Chromium browser installed
- ✓ Required test dependencies (pytest, pytest-mock, psutil)

**Expected output:**
```
✓ PASS     | Python Version            | Python 3.11.5
✓ PASS     | Playwright Package        | playwright 1.40.0
✓ PASS     | Playwright Import         | Playwright Python API imports successfully
✓ PASS     | Playwright Browsers       | Playwright installed, Chromium browser installed
✓ PASS     | psutil Package            | psutil 5.9.0
✓ PASS     | pytest Package            | pytest 7.4.0
✓ PASS     | pytest-mock Package       | pytest-mock 3.11.1
```

## Running Tests

### Quick Test Commands

```bash
# Run all Playwright tests
pytest tests/unit/test_playwright_runner.py -v

# Run with coverage
pytest tests/unit/test_playwright_runner.py --cov=tools.qa.playwright_runner --cov-report=term-missing

# Run specific test class
pytest tests/unit/test_playwright_runner.py::TestSingleURLAnalysis -v

# Run specific test
pytest tests/unit/test_playwright_runner.py::TestSingleURLAnalysis::test_successful_analysis_mobile_and_desktop -v

# Run all unit tests
pytest tests/unit/ -v

# Run all tests (unit + integration)
pytest -v
```

## Test Categories

### 1. Single URL Analysis
Tests the main analysis function.

```bash
pytest tests/unit/test_playwright_runner.py::TestSingleURLAnalysis -v
```

**Covers:**
- Successful mobile/desktop score extraction
- PSI URL generation for failing scores
- Result structure validation

### 2. Score Extraction
Tests score extraction from PageSpeed Insights.

```bash
pytest tests/unit/test_playwright_runner.py::TestScoreExtraction -v
```

**Covers:**
- Primary selector usage
- Fallback selector usage
- Handling missing elements
- Handling invalid score text

### 3. Timeout Handling
Tests timeout configuration and progressive timeout.

```bash
pytest tests/unit/test_playwright_runner.py::TestTimeoutHandling -v
```

**Covers:**
- Timeout parameter respect
- Timeout error handling
- Progressive timeout increases
- Analysis completion wait

### 4. Retry Logic
Tests retry mechanism.

```bash
pytest tests/unit/test_playwright_runner.py::TestRetryLogic -v
```

**Covers:**
- Successful retry after transient failure
- Exhausted retries behavior
- Permanent error handling (no retry)

### 5. Cache Integration
Tests cache behavior.

```bash
pytest tests/unit/test_playwright_runner.py::TestCacheIntegration -v
```

**Covers:**
- Cache hits
- Cache misses
- Cache bypass with skip_cache flag
- Cache metrics recording

### 6. Instance Pooling
Tests Playwright instance pool.

```bash
pytest tests/unit/test_playwright_runner.py::TestPlaywrightPool -v
```

**Covers:**
- Instance creation
- Instance reuse (warm starts)
- High memory instance removal
- Failed instance removal
- Pool shutdown

## Test Results Interpretation

### All Passing
```
tests/unit/test_playwright_runner.py::TestSingleURLAnalysis::test_successful_analysis_mobile_and_desktop PASSED
tests/unit/test_playwright_runner.py::TestScoreExtraction::test_extract_score_with_primary_selector PASSED
...
===================== X passed in Y.ZZs =====================
```

✓ All tests passed - implementation is correct

### Failures
```
tests/unit/test_playwright_runner.py::TestSingleURLAnalysis::test_successful_analysis_mobile_and_desktop FAILED
...
AssertionError: assert 80 == 85
```

✗ Test failed - check the implementation

### Coverage Report
```
Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
tools/qa/playwright_runner.py        250     15    94%   123-125, 234
-----------------------------------------------------------------
TOTAL                                250     15    94%
```

✓ >90% coverage achieved - excellent test coverage

## Troubleshooting

### Problem: Playwright not installed
```
✗ FAIL     | Playwright Package        | playwright not installed
```

**Solution:**
```bash
pip install playwright
playwright install chromium
```

### Problem: Tests fail with ImportError
```
ImportError: No module named 'pytest_mock'
```

**Solution:**
```bash
pip install -r requirements.txt
```

### Problem: Mock assertions fail
```
AssertionError: Expected 'mock.method' to have been called once. Called 0 times.
```

**Solution:** Check that the mock is patched at the correct import location.

### Problem: Tests pass individually but fail together
**Solution:** Ensure test isolation. The `reset_globals` fixture should handle this automatically.

## Coverage Goals

| Component | Target | Current |
|-----------|--------|---------|
| run_analysis() | >90% | ✓ |
| _run_analysis_once() | >90% | ✓ |
| Score extraction | >90% | ✓ |
| Instance pooling | >90% | ✓ |
| Cache integration | >90% | ✓ |
| Retry logic | >90% | ✓ |
| Error handling | >90% | ✓ |

## Next Steps

1. **Validate setup**: `python validate_playwright_setup.py`
2. **Run tests**: `pytest tests/unit/test_playwright_runner.py -v`
3. **Check coverage**: `pytest tests/unit/test_playwright_runner.py --cov=tools.qa.playwright_runner --cov-report=term-missing`
4. **Review results**: Ensure all tests pass and coverage >90%

## Additional Resources

- Full testing guide: `PLAYWRIGHT_TESTING.md`
- Test suite documentation: `tests/README.md`
- Playwright runner implementation: `tools/qa/playwright_runner.py`
- Agents guide: `AGENTS.md`
