# Threading Diagnostics Guide

This document explains how to use the comprehensive threading diagnostics built into the Playwright runner to troubleshoot threading issues.

## Overview

The Playwright runner uses a dedicated event loop thread to ensure all browser operations execute on a single thread, avoiding greenlet and threading conflicts. The system includes extensive logging, metrics tracking, and health monitoring to diagnose threading issues.

## Quick Start

### Run Full Diagnostics

```bash
python diagnose_playwright_threading.py
```

This prints a comprehensive report including:
- Python version and asyncio configuration
- Thread information (main, current, event loop, all active threads)
- Threading metrics (greenlet errors, thread conflicts, event loop failures)
- Event loop health status
- Playwright pool statistics

### Export Diagnostics to JSON

```bash
python diagnose_playwright_threading.py --json diagnostics.json
```

### View Specific Components

```bash
# Only threading metrics
python diagnose_playwright_threading.py --metrics-only

# Only event loop health
python diagnose_playwright_threading.py --health-only

# Only pool statistics
python diagnose_playwright_threading.py --pool-only
```

## Understanding the Output

### Threading Metrics

- **Greenlet Errors**: Count of greenlet-related errors detected
- **Thread Conflicts**: Count of thread conflict errors
- **Event Loop Failures**: Count of event loop failures
- **Context Creations by Thread**: Shows which threads created browser contexts (should only be event loop thread)
- **Page Creations by Thread**: Shows which threads created pages (should only be event loop thread)
- **Async Operations by Thread**: Shows which threads ran async operations (should only be event loop thread)

### Event Loop Health

- **Last Heartbeat**: Timestamp of last event loop heartbeat
- **Time Since Heartbeat**: Seconds since last heartbeat (should be < 30s)
- **Heartbeat Failures**: Number of consecutive heartbeat failures
- **Is Responsive**: Whether event loop is responsive (should be True)
- **Thread ID**: Thread ID of event loop thread

### Expected Behavior

In a healthy system:
- All browser contexts should be created on the event loop thread
- All pages should be created on the event loop thread
- All async operations should run on the event loop thread
- Event loop heartbeat should update every 5 seconds
- Greenlet errors and thread conflicts should be 0

## Interpreting Issues

### Greenlet Errors

If you see greenlet errors:
- Error message contains "greenlet" or "gr_frame"
- Indicates Playwright objects accessed from wrong thread
- Check which threads are creating contexts/pages

**Fix**: Ensure all Playwright operations go through the event loop thread via `submit_analysis()`

### Thread Conflicts

If you see thread conflicts:
- Error message contains "thread" and "conflict"
- Indicates operations attempted from multiple threads
- Check thread IDs in logs

**Fix**: Review code to ensure single-threaded access to Playwright objects

### Event Loop Failures

If event loop is unresponsive:
- Time since heartbeat > 30 seconds
- Is Responsive = False
- Heartbeat failures > 0

**Fix**: Check for blocking operations in event loop thread; system will attempt automatic recovery

## Log Output

When running audits with verbose logging, you'll see thread IDs in log messages:

```
[Thread-12345:PlaywrightEventLoop] Creating new page - Context ID: 140123456789
[Thread-12345:PlaywrightEventLoop] Page created - Page ID: 140123456790
```

This confirms operations are running on the correct thread.

## Integration with Metrics

Threading metrics are automatically exported with other metrics:

```bash
# View in JSON metrics
python generate_report.py --export-json metrics.json

# View in Prometheus metrics
python generate_report.py --export-prometheus metrics.prom
```

The metrics include:
```
psi_audit_threading_errors_total{type="greenlet"} 0
psi_audit_threading_errors_total{type="conflict"} 0
psi_audit_threading_errors_total{type="event_loop_failure"} 0
```

## Programmatic Access

You can access threading diagnostics programmatically:

```python
from tools.qa.playwright_runner import (
    diagnose_threading_issues,
    get_threading_metrics,
    get_event_loop_health,
    reset_threading_metrics
)

# Get full diagnostic report
diagnosis = diagnose_threading_issues()
print(diagnosis)

# Get only metrics
metrics = get_threading_metrics()
print(f"Greenlet errors: {metrics['greenlet_errors']}")

# Check event loop health
health = get_event_loop_health()
print(f"Event loop responsive: {health['is_responsive']}")

# Reset metrics
reset_threading_metrics()
```

## Troubleshooting Tips

1. **Run diagnostics before and after audits** to compare threading state
2. **Check thread IDs** in logs to verify single-thread execution
3. **Monitor event loop health** during long-running audits
4. **Export diagnostics to JSON** for detailed analysis
5. **Review threading metrics** in generated reports

## Health Checks

The system includes automatic health checks:
- Periodic heartbeat every 5 seconds
- Automatic detection of unresponsive event loops
- Automatic restart of dead event loop threads
- Health checks before submitting new requests

If health checks fail, the system will:
1. Log the health issue
2. Attempt to restart the event loop thread
3. Record the failure in metrics
4. Retry the operation if possible

## Best Practices

1. **Enable debug mode** for detailed threading logs during development
2. **Monitor threading metrics** in production
3. **Set up alerts** for greenlet errors or thread conflicts
4. **Review diagnostics** after unexpected failures
5. **Check event loop health** if seeing timeout issues
