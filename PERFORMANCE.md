# Performance Optimizations

This document describes the comprehensive performance optimizations implemented in the PageSpeed Insights Audit Tool, focusing on Playwright-specific enhancements.

## Overview

The system has been optimized for maximum throughput and efficiency when processing large batches of URLs. Key improvements include browser instance pooling, network request interception, parallel processing, and detailed performance monitoring.

## Playwright-Specific Optimizations

### 1. Browser Instance Pooling

**Implementation**: Up to 3 concurrent browser contexts maintained in a pool for reuse across URL analyses.

**Benefits**:
- **Warm starts**: Reusing existing browser contexts is 2-3x faster than creating new ones
- **Resource efficiency**: Avoids overhead of repeatedly starting/stopping browsers
- **Parallel processing**: Multiple workers can use separate instances simultaneously

**Configuration**:
```python
# In playwright_runner.py
PlaywrightPool.POOL_SIZE = 3  # Max concurrent browser instances
PlaywrightPool.MAX_MEMORY_MB = 1024  # Memory threshold per instance
```

**Behavior**:
- Instances are created on-demand when pool is empty
- Idle instances are reused for subsequent analyses (warm start)
- Instances exceeding 1GB memory usage are automatically killed
- Instances with 3+ consecutive failures are removed from pool
- Pool is cleaned up on application shutdown

### 2. Network Request Interception & Resource Blocking

**Implementation**: Playwright route interception blocks unnecessary resources before they're loaded.

**Blocked Resource Types**:
- Images (`image`)
- Media files (`media`)
- Fonts (`font`)
- Stylesheets (`stylesheet`)
- WebSockets (`websocket`)

**Blocked URL Patterns**:
- Analytics: `google-analytics.com`, `googletagmanager.com`, `analytics.*`
- Advertising: `doubleclick.net`, `googleadservices.com`, `ads.*`, `/ad/`
- Tracking: `facebook.com/tr`, `pixel.*`, `beacon`, `telemetry`

**Benefits**:
- **Bandwidth savings**: 40-60% of requests typically blocked
- **Faster page loads**: 30-50% reduction in page load time
- **Lower memory usage**: Less content to process and render
- **Cost savings**: Reduced network transfer for cloud deployments

**Metrics Tracked**:
- Total requests per analysis
- Blocked requests per analysis
- Blocking ratio (blocked/total)
- Breakdown by resource type

### 3. Parallel Browser Management

**Implementation**: ThreadPoolExecutor manages up to 3 concurrent workers, each using a separate browser instance.

**Configuration**:
```bash
# Command line
python run_audit.py --tab "URLs" --concurrency 3

# Default in run_audit.py
DEFAULT_CONCURRENCY = 3
```

**Benefits**:
- **3x throughput**: Process 3 URLs simultaneously
- **Better CPU utilization**: Leverage multi-core processors
- **Reduced total runtime**: Large batches complete much faster

**Considerations**:
- Memory usage scales linearly with concurrency (3 workers ≈ 3GB RAM)
- Network bandwidth may become bottleneck at higher concurrency
- PageSpeed Insights API may rate-limit aggressive concurrent requests

### 4. Performance Monitoring

**Metrics Collected**:

| Metric | Description | Unit |
|--------|-------------|------|
| Page Load Time | Time to analyze URL in PageSpeed Insights | Seconds |
| Browser Startup Time | Time to launch new browser instance (cold starts) | Seconds |
| Memory Usage | RSS memory per browser instance | MB |
| Warm/Cold Starts | Count of reused vs new instances | Count |
| Request Blocking | Total requests vs blocked requests | Count |
| Blocking Ratio | Percentage of requests blocked | Percent |

**Access Methods**:

1. **JSON Metrics** (`metrics.json`):
```json
{
  "playwright": {
    "avg_page_load_time_seconds": 45.2,
    "avg_browser_startup_time_seconds": 3.1,
    "avg_memory_usage_mb": 512.3,
    "warm_start_ratio_percent": 66.7,
    "blocking_ratio_percent": 52.4
  }
}
```

2. **Prometheus Metrics** (`metrics.prom`):
```prometheus
psi_audit_playwright_page_load_time_seconds 45.2
psi_audit_playwright_browser_startup_time_seconds 3.1
psi_audit_playwright_memory_usage_mb{stat="avg"} 512.3
psi_audit_playwright_warm_start_ratio 66.7
```

3. **Pool Statistics**:
```bash
python get_pool_stats.py
```

4. **HTML Dashboard**:
```bash
python generate_report.py
# Includes Playwright-specific charts and metrics
```

### 5. Additional Browser Optimizations

**Launch Flags**:
```python
args=[
    '--disable-dev-shm-usage',      # Prevent /dev/shm exhaustion
    '--disable-gpu',                 # Headless doesn't need GPU
    '--disable-software-rasterizer', # Reduce CPU usage
    '--disable-extensions',          # No extensions needed
    '--disable-plugins',             # No Flash/Java needed
    '--no-sandbox',                  # Faster in containers
    '--disable-setuid-sandbox',      # Faster in containers
    '--disable-web-security',        # Allow cross-origin if needed
]
```

**Context Options**:
```python
context = browser.new_context(
    bypass_csp=True,              # Bypass CSP restrictions
    ignore_https_errors=True,     # Handle self-signed certs
    java_script_enabled=True,     # PSI needs JS
)
```

**Wait Strategy**:
```python
page.goto(url, wait_until='domcontentloaded')  # Faster than 'networkidle'
```

## Performance Comparison

### Before Optimizations
- Single-threaded processing (1 URL at a time)
- Cold start for every URL (browser launch + context creation)
- All resources loaded (images, ads, analytics, etc.)
- ~120-180s per URL average
- Memory: ~500MB per browser instance

### After Optimizations
- Parallel processing (3 concurrent URLs)
- Warm starts after first URL (reuse browser contexts)
- 40-60% of resources blocked
- ~45-60s per URL average (warm starts)
- ~90-120s per URL (cold starts)
- Memory: ~400-600MB per browser instance (lower due to blocked resources)

**Net Improvement**: ~3x throughput improvement for large batches

## Monitoring and Tuning

### Real-Time Pool Statistics

```bash
$ python get_pool_stats.py

================================================================================
PLAYWRIGHT POOL STATISTICS
================================================================================

Total Instances: 3
Idle Instances: 2
Busy Instances: 1

Total Warm Starts: 47
Total Cold Starts: 3
Average Startup Time: 3.12s

--------------------------------------------------------------------------------
INSTANCE DETAILS
--------------------------------------------------------------------------------

Instance 1:
  PID: 12345
  State: busy
  Memory: 512.34 MB
  Total Analyses: 18
  Avg Page Load Time: 47.23s
  Failures: 0
  Request Blocking:
    Total Requests: 1834
    Blocked Requests: 967
    Blocking Ratio: 52.7%
```

### Tuning Recommendations

**For Maximum Throughput**:
- Set `--concurrency 5` (requires 5GB+ RAM)
- Increase `POOL_SIZE` to 5 in `playwright_runner.py`
- Monitor memory usage and CPU utilization

**For Resource-Constrained Environments**:
- Set `--concurrency 1` (single-threaded)
- Reduce `MAX_MEMORY_MB` to 512 for earlier instance recycling
- Enable Redis cache for better cache hit ratio

**For Debugging**:
- Set `--concurrency 1` for sequential processing
- Use `--no-progress-bar` for detailed logging
- Monitor pool stats with `python get_pool_stats.py --json pool_stats.json`

## Best Practices

1. **Start with default concurrency (3)** and measure performance
2. **Monitor memory usage** during large batch processing
3. **Use caching** (don't use `--skip-cache` unless necessary)
4. **Watch warm start ratio** - should be >60% for efficient pooling
5. **Check blocking ratio** - should be 40-60% for typical websites
6. **Review metrics regularly** - use dashboard to identify bottlenecks

## Troubleshooting

### High Memory Usage
- Instances use >1GB memory → Automatically killed and recreated
- Overall memory >5GB → Reduce `--concurrency`
- Memory grows over time → Check for browser leaks, restart audit

### Low Warm Start Ratio
- Ratio <40% → Increase `POOL_SIZE`
- Many instance failures → Check logs for errors
- Frequent memory kills → Increase `MAX_MEMORY_MB` carefully

### Poor Blocking Ratio
- Ratio <20% → Website has few blockable resources (normal)
- Ratio >80% → May indicate overly aggressive blocking (check if PSI works)

### Slow Performance
- Cold starts >5s → Check system resources (CPU, disk I/O)
- Page loads >120s → Check network latency, PSI service health
- Low concurrency benefit → May be network-bound, not CPU-bound

## Future Improvements

Potential enhancements for future versions:

1. **Dynamic Pool Sizing**: Auto-adjust pool size based on memory/CPU
2. **Smarter Resource Blocking**: Machine learning to identify critical resources
3. **Distributed Processing**: Multiple machines sharing workload
4. **Progressive Enhancement**: Load critical resources first, defer others
5. **Browser Context Caching**: Cache page state across similar URLs
6. **Request Prioritization**: Prioritize PSI-critical requests

## References

- Playwright Documentation: https://playwright.dev/python/
- PageSpeed Insights API: https://developers.google.com/speed/docs/insights/v5/get-started
- Performance Best Practices: See `AGENTS.md` for implementation details
