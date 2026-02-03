# Error Handling Guide

## Overview

The audit system includes comprehensive error handling with the following features:

1. **Custom Exception Classes** - `RetryableError` and `PermanentError` for precise error classification
2. **Exponential Backoff Retry** - Decorator-based retry logic with configurable backoff
3. **Circuit Breaker Pattern** - Prevents cascading failures for PageSpeed Insights (5 failures = 5 min pause)
4. **Structured Error Logging** - Rich context and traceback information in logs
5. **Error Metrics Collection** - Track, analyze, and report error patterns

## Custom Exception Classes

### RetryableError

Used for transient failures that can be safely retried:
- Network timeouts
- Rate limiting (429 errors)
- Temporary service unavailability (5xx errors)
- File not found (when results file is expected but delayed)

```python
from utils.exceptions import RetryableError

raise RetryableError(
    "Network timeout - can retry",
    original_exception=TimeoutError("Connection timed out")
)
```

### PermanentError

Used for errors that should NOT be retried:
- Invalid authentication/credentials
- Resource not found (404 errors)
- Permission denied (403 errors)
- Invalid input/configuration
- Missing required dependencies (e.g., npx not found)

```python
from utils.exceptions import PermanentError

raise PermanentError(
    "Invalid API key - cannot retry",
    original_exception=ValueError("API key is malformed")
)
```

## Exponential Backoff Retry

The `retry_with_backoff` decorator provides automatic retry with exponential backoff and jitter.

### Basic Usage

```python
from utils.retry import retry_with_backoff
from utils.exceptions import RetryableError, PermanentError

@retry_with_backoff(
    max_retries=3,
    initial_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True
)
def flaky_operation():
    # Your code here
    pass
```

### Configuration Options

- `max_retries` (default: 3) - Maximum retry attempts
- `initial_delay` (default: 1.0) - Initial delay in seconds
- `max_delay` (default: 60.0) - Maximum delay between retries
- `exponential_base` (default: 2.0) - Multiplier for exponential backoff
- `jitter` (default: True) - Add randomization to prevent thundering herd
- `retryable_exceptions` (default: `(RetryableError,)`) - Exceptions that trigger retry
- `permanent_exceptions` (default: `(PermanentError,)`) - Exceptions that skip retry
- `logger` (optional) - Logger instance for structured logging

### Backoff Calculation

Delay = min(initial_delay * (exponential_base ^ attempt), max_delay)

With jitter: Delay *= (0.5 + random())

Example with initial_delay=1.0, exponential_base=2.0:
- Attempt 1: 1.0s (with jitter: 0.5-1.5s)
- Attempt 2: 2.0s (with jitter: 1.0-3.0s)
- Attempt 3: 4.0s (with jitter: 2.0-6.0s)
- Attempt 4: 8.0s (with jitter: 4.0-12.0s)

## Circuit Breaker Pattern

The circuit breaker protects against cascading failures by "opening" after a threshold of failures and entering a recovery period.

### States

1. **CLOSED** - Normal operation, all requests pass through
2. **OPEN** - Failure threshold exceeded, requests fail fast without attempting operation
3. **HALF_OPEN** - Recovery period elapsed, testing if service has recovered

### Usage

```python
from utils.circuit_breaker import CircuitBreaker

circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=300.0,  # 5 minutes
    expected_exception=Exception,
    name="PageSpeedInsights",
    logger=logger
)

# Use as function wrapper
result = circuit_breaker.call(risky_operation, arg1, arg2)

# Or as decorator
@circuit_breaker
def risky_operation(arg1, arg2):
    # Your code here
    pass
```

### Configuration

- `failure_threshold` (default: 5) - Number of failures before opening circuit
- `recovery_timeout` (default: 300.0) - Seconds to wait before attempting recovery
- `expected_exception` (default: Exception) - Exception type that counts as failure
- `name` (default: "CircuitBreaker") - Name for logging purposes
- `logger` (optional) - Logger instance

### PageSpeed Insights Circuit Breaker

A global circuit breaker is automatically configured for PageSpeed Insights:
- Threshold: 5 failures
- Recovery timeout: 5 minutes (300 seconds)
- When open, requests fail immediately with informative error message

## Structured Error Logging

Enhanced logging with rich context and traceback information.

### Automatic Context in Decorators

The `retry_with_backoff` decorator automatically logs:
- Function name
- Attempt number
- Error type and exception type
- Retry delay
- Full traceback

### Manual Context Logging

```python
from utils.logger import log_error_with_context, get_logger

logger = get_logger()

try:
    risky_operation()
except Exception as e:
    log_error_with_context(
        logger,
        "Operation failed",
        exception=e,
        context={
            'function': 'risky_operation',
            'url': 'https://example.com',
            'attempt': 1,
            'timeout': 30
        },
        include_traceback=True
    )
```

### Log Output

Structured logs include:
- Timestamp
- Log level
- Message
- Context dictionary (formatted as JSON)
- Full traceback (if included)

Example:
```
2024-01-15 10:30:45 - audit - ERROR - Failed to analyze URL
  Context: {
    "function": "run_analysis",
    "url": "https://example.com",
    "attempt": 2,
    "error_type": "retryable",
    "exception_type": "CypressRunnerError",
    "retry_delay": 2.0
  }
  Traceback:
    File "cypress_runner.py", line 95, in _run_analysis_once
      raise CypressRunnerError("Cypress failed")
```

## Error Metrics Collection

Track and analyze error patterns across the system.

### Automatic Metrics Collection

Error metrics are automatically collected in:
- `cypress_runner.py` - Cypress execution errors
- `sheets_client.py` - Google Sheets API errors
- `run_audit.py` - Overall audit process errors

### Manual Metrics Recording

```python
from utils.error_metrics import get_global_metrics

metrics = get_global_metrics()

# Record operations
metrics.increment_total_operations()

# Record errors
metrics.record_error(
    error_type='NetworkError',
    function_name='api_call',
    error_message='Connection failed',
    is_retryable=True,
    attempt=1,
    traceback=traceback.format_exc()
)

# Record outcomes
metrics.record_success('api_call', was_retried=False)
metrics.record_failure('api_call')
```

### Metrics Summary

At the end of each audit run, a comprehensive metrics summary is displayed:

```
================================================================================
ERROR METRICS SUMMARY
================================================================================
Elapsed Time: 125.34s
Total Operations: 50
Successful: 45 (90.0%)
Failed: 5
Retried: 8 (16.0%)
Total Errors: 13

Errors by Type:
  CypressTimeoutError: 5
  RetryableHttpError: 4
  NetworkError: 3
  CypressRunnerError: 1

Errors by Function:
  run_analysis: 8
  batch_write_psi_urls: 3
  read_urls: 2

Recent Errors (last 10):
  [2024-01-15T10:30:45] CypressTimeoutError in run_analysis
    Cypress execution exceeded 600 seconds timeout
  [2024-01-15T10:32:15] RetryableHttpError in batch_write_psi_urls
    HTTP 429: Rate limit exceeded
================================================================================
```

### Export Metrics

```python
# Get summary dictionary
summary = metrics.get_summary()

# Export as JSON
json_output = metrics.to_json(indent=2)

# Print formatted summary
metrics.print_summary()

# Get detailed error list
errors = metrics.get_detailed_errors(limit=100)
```

## Integration in Modules

### cypress_runner.py

- Uses `RetryableError` and `PermanentError` for error classification
- Implements circuit breaker for PageSpeed Insights protection
- Collects detailed error metrics
- Provides structured error logging

Key behaviors:
- npx not found → `PermanentError` (no retry)
- Timeout → `CypressTimeoutError` (no retry, counted as failure)
- Results file missing → `RetryableError` (retry up to 3 times)
- Circuit breaker opens after 5 failures

### sheets_client.py

- Uses `PermanentError` for 403/404 errors
- Implements automatic retry for 429/5xx errors
- Integrates error metrics collection
- Rate limiting with token bucket algorithm

Key behaviors:
- 403 Forbidden → `PermanentError` (no retry)
- 404 Not Found → `PermanentError` (no retry)
- 429 Rate Limit → Automatic retry with exponential backoff
- 5xx Server Error → Automatic retry with exponential backoff

### run_audit.py

- Centralizes error handling and metrics reporting
- Distinguishes error types in final summary
- Provides error type breakdown
- Displays comprehensive metrics at end of run

## Best Practices

1. **Use Appropriate Exception Types**
   - Transient failures → `RetryableError`
   - Configuration/auth failures → `PermanentError`
   - Preserve original exception for debugging

2. **Configure Retry Wisely**
   - Don't retry on permanent errors
   - Use jitter to prevent thundering herd
   - Set reasonable max_delay to avoid long pauses

3. **Monitor Circuit Breaker**
   - Check logs when circuit opens
   - Investigate root cause during recovery period
   - Manually reset if needed: `circuit_breaker.reset()`

4. **Leverage Structured Logging**
   - Include relevant context (URL, attempt, timeout)
   - Enable tracebacks for unexpected errors
   - Review logs for patterns

5. **Analyze Metrics**
   - Monitor error rates and types
   - Identify functions with high error rates
   - Track retry effectiveness
   - Use metrics to tune retry configuration

## Demo Script

Run the demo script to see all features in action:

```bash
python error_handling_demo.py
```

The demo showcases:
- Custom exception classes
- Exponential backoff retry
- Circuit breaker states and recovery
- Error metrics collection
- Structured logging with context
- Integrated error handling

## Troubleshooting

### High Error Rate

1. Check error metrics summary for patterns
2. Review structured logs for context
3. Verify network connectivity and API quotas
4. Adjust retry configuration if needed

### Circuit Breaker Opens Frequently

1. Check if PageSpeed Insights is down
2. Review timeout settings (may be too aggressive)
3. Check network latency
4. Consider increasing `failure_threshold` or reducing `recovery_timeout`

### Retries Not Working

1. Verify exception type is in `retryable_exceptions`
2. Check that `max_retries > 0`
3. Review logs for "Permanent error" messages
4. Ensure exceptions are raised correctly

### Missing Metrics

1. Verify `get_global_metrics()` is called
2. Check that operations call `increment_total_operations()`
3. Ensure errors are recorded with `record_error()`
4. Run `metrics.print_summary()` at end of execution
