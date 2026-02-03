# Error Handling Features

## Quick Start

The audit system now includes comprehensive error handling with 5 key features:

1. **RetryableError & PermanentError** - Smart exception classification
2. **Exponential Backoff Retry** - Automatic retry with configurable delays
3. **Circuit Breaker** - Protects PageSpeed Insights (5 failures = 5 min pause)
4. **Structured Logging** - Rich context and tracebacks in logs
5. **Error Metrics** - Track and analyze error patterns

## Files

### Core Implementation
- `tools/utils/exceptions.py` - Custom exception classes
- `tools/utils/retry.py` - Retry decorator with exponential backoff
- `tools/utils/circuit_breaker.py` - Circuit breaker pattern
- `tools/utils/error_metrics.py` - Error metrics collection
- `tools/utils/logger.py` - Enhanced structured logging

### Documentation
- `ERROR_HANDLING_GUIDE.md` - Complete usage guide
- `ERROR_HANDLING_IMPLEMENTATION.md` - Implementation details
- `error_handling_demo.py` - Demo script showing all features

### Modified Files
- `run_audit.py` - Integrated metrics reporting
- `tools/qa/cypress_runner.py` - Circuit breaker + metrics
- `tools/sheets/sheets_client.py` - Enhanced error handling

## Quick Examples

### Custom Exceptions
```python
from utils.exceptions import RetryableError, PermanentError

# Transient failure - will be retried
raise RetryableError("Temporary network issue")

# Permanent failure - will not be retried
raise PermanentError("Invalid credentials")
```

### Retry Decorator
```python
from utils.retry import retry_with_backoff

@retry_with_backoff(max_retries=3, initial_delay=1.0)
def api_call():
    # Automatically retries on RetryableError
    pass
```

### Circuit Breaker
```python
from utils.circuit_breaker import CircuitBreaker

circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=300.0)
result = circuit.call(pagespeed_insights_call, url)
```

### Error Metrics
```python
from utils.error_metrics import get_global_metrics

metrics = get_global_metrics()
metrics.print_summary()  # Shows error statistics
```

## Key Features

### 1. Automatic PageSpeed Insights Protection
The circuit breaker automatically protects PageSpeed Insights:
- Opens after 5 consecutive failures
- Pauses requests for 5 minutes
- Tests recovery automatically
- Logs all state transitions

### 2. Smart Error Classification
- HTTP 403/404 → PermanentError (no retry)
- HTTP 429/5xx → RetryableError (automatic retry)
- Timeout → CypressTimeoutError (no retry, logged)
- npx not found → PermanentError (setup issue)

### 3. Comprehensive Metrics
Displayed at end of each audit run:
- Success/failure rates
- Errors by type and function
- Retry effectiveness
- Recent error history

### 4. Rich Logging
All errors logged with:
- Full context (URL, attempt, timeout)
- Complete traceback
- Error type classification
- Retry delays and attempts

## Running the Demo

```bash
python error_handling_demo.py
```

Demonstrates:
- Exception class usage
- Retry behavior with backoff
- Circuit breaker states
- Metrics collection
- Structured logging
- Full integration

## Configuration

### Circuit Breaker
Located in `tools/qa/cypress_runner.py`:
```python
CircuitBreaker(
    failure_threshold=5,      # Failures before opening
    recovery_timeout=300.0,    # 5 minute pause
    name="PageSpeedInsights"
)
```

### Retry Defaults
In `tools/utils/retry.py`:
```python
@retry_with_backoff(
    max_retries=3,
    initial_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True
)
```

### Sheets API Retry
In `tools/sheets/sheets_client.py`:
```python
_execute_with_retry(
    func,
    max_retries=3,
    initial_delay=2.0
)
```

## Metrics Output Example

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

Errors by Function:
  run_analysis: 8
  batch_write_psi_urls: 3
================================================================================
```

## Integration Points

### In Your Code
```python
from utils.exceptions import RetryableError, PermanentError
from utils.error_metrics import get_global_metrics
from utils.logger import log_error_with_context

# Record operations
metrics = get_global_metrics()
metrics.increment_total_operations()

try:
    result = risky_operation()
    metrics.record_success('risky_operation')
except Exception as e:
    metrics.record_error('ErrorType', 'risky_operation', str(e))
    log_error_with_context(logger, "Failed", exception=e)
    raise
```

## Benefits

✅ **Reliability** - Automatic retry of transient failures  
✅ **Resilience** - Circuit breaker prevents cascading failures  
✅ **Observability** - Comprehensive metrics and structured logs  
✅ **Debuggability** - Full context and tracebacks for all errors  
✅ **Production Ready** - Thread-safe, configurable, battle-tested patterns

## Documentation

- **ERROR_HANDLING_GUIDE.md** - Complete guide with examples
- **ERROR_HANDLING_IMPLEMENTATION.md** - Technical implementation details
- **error_handling_demo.py** - Working demonstration
- **AGENTS.md** - Updated with error handling info (if needed)

## Testing

Run the demo to verify installation:
```bash
python error_handling_demo.py
```

Test with actual audit:
```bash
python run_audit.py --tab "YourTab"
```

Check logs in `logs/` directory for structured error context.

## Support

All error handling features are fully integrated and production-ready. The system:
- Handles transient failures automatically
- Protects external services with circuit breaker
- Provides detailed metrics for monitoring
- Logs all errors with full context

For questions, refer to ERROR_HANDLING_GUIDE.md.
