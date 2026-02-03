# API Documentation

Complete API reference for programmatic usage of the PageSpeed Insights Audit Tool.

## Table of Contents
- [Installation](#installation)
- [Core Modules](#core-modules)
- [Usage Examples](#usage-examples)
- [Authentication](#authentication)
- [Working with Google Sheets](#working-with-google-sheets)
- [Running Analyses](#running-analyses)
- [Caching](#caching)
- [Metrics & Monitoring](#metrics--monitoring)
- [Security Features](#security-features)
- [Error Handling](#error-handling)

## Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install

# Optional: Install Redis for production caching
# See CACHE_GUIDE.md for details
```

## Core Modules

### Sheets Client (`tools.sheets.sheets_client`)

#### `authenticate(service_account_file: str) -> Resource`

Authenticate with Google Sheets API using a service account.

**Parameters:**
- `service_account_file` (str): Path to service account JSON file

**Returns:**
- `Resource`: Authorized Google Sheets service object

**Raises:**
- `PermanentError`: If authentication fails

**Example:**
```python
from tools.sheets import sheets_client

service = sheets_client.authenticate('service-account.json')
```

#### `read_urls(spreadsheet_id: str, tab_name: str, service=None, service_account_file=None) -> List[Tuple]`

Read URLs and existing results from a spreadsheet tab.

**Parameters:**
- `spreadsheet_id` (str): Google Spreadsheet ID
- `tab_name` (str): Name of the tab/sheet
- `service` (Resource, optional): Authenticated service object
- `service_account_file` (str, optional): Path to service account file

**Returns:**
- List of tuples: `(row_index, url, mobile_psi_url, desktop_psi_url, should_skip)`

**Example:**
```python
urls = sheets_client.read_urls(
    '1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I',
    'My Tab',
    service=service
)

for row_idx, url, mobile, desktop, skip in urls:
    print(f"Row {row_idx}: {url}")
```

#### `batch_write_psi_urls(spreadsheet_id: str, tab_name: str, updates: List[Tuple], service=None, dry_run=False)`

Write PSI results to multiple cells in batch.

**Parameters:**
- `spreadsheet_id` (str): Google Spreadsheet ID
- `tab_name` (str): Name of the tab/sheet
- `updates` (List[Tuple]): List of `(row_index, column, url)` tuples
- `service` (Resource, optional): Authenticated service object
- `dry_run` (bool): If True, simulate without writing

**Example:**
```python
updates = [
    (2, 'F', 'https://pagespeed.web.dev/...'),  # Row 2, column F
    (2, 'G', 'https://pagespeed.web.dev/...'),  # Row 2, column G
    (3, 'F', 'passed'),  # Row 3, column F (passed)
]

sheets_client.batch_write_psi_urls(
    spreadsheet_id='1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I',
    tab_name='My Tab',
    updates=updates,
    service=service
)
```

### Cypress Runner (`tools.qa.cypress_runner`)

#### `run_analysis(url: str, timeout: int = 600, max_retries: int = 3, skip_cache: bool = False) -> Dict`

Run PageSpeed Insights analysis for a URL.

**Parameters:**
- `url` (str): URL to analyze
- `timeout` (int): Maximum seconds to wait (default: 600)
- `max_retries` (int): Maximum retry attempts (default: 3)
- `skip_cache` (bool): Bypass cache if True (default: False)

**Returns:**
- `Dict` with keys:
  - `mobile_score` (int): Mobile score (0-100)
  - `desktop_score` (int): Desktop score (0-100)
  - `mobile_psi_url` (str): Mobile report URL
  - `desktop_psi_url` (str): Desktop report URL
  - `_from_cache` (bool): Whether result came from cache

**Raises:**
- `CypressRunnerError`: If analysis fails
- `CypressTimeoutError`: If analysis times out
- `PermanentError`: If unrecoverable error occurs

**Example:**
```python
from tools.qa import cypress_runner

result = cypress_runner.run_analysis('https://example.com', timeout=600)

print(f"Mobile score: {result['mobile_score']}")
print(f"Desktop score: {result['desktop_score']}")
print(f"From cache: {result['_from_cache']}")

if result['mobile_score'] < 80:
    print(f"Mobile report: {result['mobile_psi_url']}")
```

#### `shutdown_pool()`

Shutdown the Cypress instance pool. Call on application exit.

**Example:**
```python
import atexit
from tools.qa import cypress_runner

atexit.register(cypress_runner.shutdown_pool)
```

### Cache Manager (`tools.cache.cache_manager`)

#### `get_cache_manager(enabled: bool = True) -> CacheManager`

Get the global cache manager instance.

**Parameters:**
- `enabled` (bool): Whether caching is enabled (default: True)

**Returns:**
- `CacheManager`: Global cache manager instance

**Example:**
```python
from tools.cache.cache_manager import get_cache_manager

cache = get_cache_manager(enabled=True)
```

#### `CacheManager.get(url: str) -> Optional[Dict]`

Retrieve cached results for a URL.

**Parameters:**
- `url` (str): URL to lookup

**Returns:**
- `Dict` or `None`: Cached results if found

**Example:**
```python
cache = get_cache_manager()
result = cache.get('https://example.com')

if result:
    print("Cache hit!")
    print(result)
else:
    print("Cache miss")
```

#### `CacheManager.set(url: str, value: Dict, ttl: Optional[int] = None) -> bool`

Store results in cache.

**Parameters:**
- `url` (str): URL to cache
- `value` (Dict): Results to store
- `ttl` (int, optional): Time-to-live in seconds (default: 86400)

**Returns:**
- `bool`: True if successful

**Example:**
```python
cache = get_cache_manager()
result = {
    'mobile_score': 92,
    'desktop_score': 95,
    'mobile_psi_url': None,
    'desktop_psi_url': None
}

cache.set('https://example.com', result, ttl=86400)
```

#### `CacheManager.invalidate(url: str) -> bool`

Remove a URL from cache.

**Example:**
```python
cache = get_cache_manager()
cache.invalidate('https://example.com')
```

#### `CacheManager.invalidate_all() -> bool`

Clear all cache entries.

**Example:**
```python
cache = get_cache_manager()
cache.invalidate_all()
```

### Metrics Collector (`tools.metrics.metrics_collector`)

#### `get_metrics_collector() -> MetricsCollector`

Get the global metrics collector instance.

**Returns:**
- `MetricsCollector`: Global metrics collector

**Example:**
```python
from tools.metrics.metrics_collector import get_metrics_collector

metrics = get_metrics_collector()
```

#### `MetricsCollector.get_metrics() -> Dict`

Get all collected metrics.

**Returns:**
- `Dict` with metric keys:
  - `uptime_seconds`
  - `total_urls`
  - `successful_urls`
  - `failed_urls`
  - `skipped_urls`
  - `success_rate_percent`
  - `failure_rate_percent`
  - `cache_hits`
  - `cache_misses`
  - `cache_hit_ratio_percent`
  - `api_calls_sheets`
  - `api_calls_cypress`
  - `avg_processing_time_seconds`
  - `failure_reasons`

**Example:**
```python
metrics = get_metrics_collector()
data = metrics.get_metrics()

print(f"Success rate: {data['success_rate_percent']:.1f}%")
print(f"Cache hit ratio: {data['cache_hit_ratio_percent']:.1f}%")
```

#### `MetricsCollector.export_prometheus() -> str`

Export metrics in Prometheus text format.

**Returns:**
- `str`: Prometheus-formatted metrics

**Example:**
```python
metrics = get_metrics_collector()
prom_data = metrics.export_prometheus()

with open('metrics.prom', 'w') as f:
    f.write(prom_data)
```

#### `MetricsCollector.save_json_metrics(filepath: str = 'metrics.json')`

Save metrics to JSON file.

**Example:**
```python
metrics = get_metrics_collector()
metrics.save_json_metrics('metrics.json')
```

### URL Validator (`tools.utils.url_validator`)

#### `URLValidator.validate_url(url: str, check_dns: bool = True, check_redirects: bool = True) -> Tuple[bool, dict]`

Validate a URL with multiple checks.

**Parameters:**
- `url` (str): URL to validate
- `check_dns` (bool): Check DNS resolution (default: True)
- `check_redirects` (bool): Check redirect chains (default: True)

**Returns:**
- Tuple of `(is_valid, results_dict)`

**Example:**
```python
from tools.utils.url_validator import URLValidator

validator = URLValidator(dns_timeout=5.0, redirect_timeout=10.0)
is_valid, results = validator.validate_url('https://example.com')

if is_valid:
    print("URL is valid")
    if results['redirect_count'] > 0:
        print(f"Warning: {results['redirect_count']} redirects")
else:
    print("URL is invalid:")
    for error in results['errors']:
        print(f"  - {error}")
```

#### `URLNormalizer.normalize_url(url: str) -> str`

Normalize a URL for consistent comparison.

**Parameters:**
- `url` (str): URL to normalize

**Returns:**
- `str`: Normalized URL

**Example:**
```python
from tools.utils.url_validator import URLNormalizer

normalized = URLNormalizer.normalize_url('HTTPS://Example.COM/path/')
print(normalized)  # https://example.com/path
```

### Logger (`tools.utils.logger`)

#### `setup_logger(name: str = 'audit', log_dir: str = 'logs') -> logging.Logger`

Set up a logger with file and console handlers.

**Parameters:**
- `name` (str): Logger name (default: 'audit')
- `log_dir` (str): Directory for log files (default: 'logs')

**Returns:**
- `logging.Logger`: Configured logger

**Example:**
```python
from tools.utils import logger

log = logger.setup_logger(name='my_audit', log_dir='logs')
log.info("Starting audit")
```

#### `get_logger(name: str = 'audit') -> logging.Logger`

Get an existing logger instance.

**Example:**
```python
from tools.utils.logger import get_logger

log = get_logger()
log.info("Log message")
```

#### `log_error_with_context(logger, message, exception=None, context=None, include_traceback=True)`

Log an error with structured context.

**Example:**
```python
from tools.utils.logger import get_logger, log_error_with_context

log = get_logger()

try:
    # some operation
    pass
except Exception as e:
    log_error_with_context(
        log,
        "Operation failed",
        exception=e,
        context={'url': 'https://example.com', 'row': 2},
        include_traceback=True
    )
```

## Usage Examples

### Complete Audit Script

```python
#!/usr/bin/env python3
import sys
from tools.sheets import sheets_client
from tools.qa import cypress_runner
from tools.cache.cache_manager import get_cache_manager
from tools.metrics.metrics_collector import get_metrics_collector
from tools.utils.logger import setup_logger

def main():
    log = setup_logger()
    cache = get_cache_manager(enabled=True)
    metrics = get_metrics_collector()
    
    # Authenticate
    service = sheets_client.authenticate('service-account.json')
    
    # Read URLs
    spreadsheet_id = '1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I'
    tab_name = 'My Tab'
    urls = sheets_client.read_urls(spreadsheet_id, tab_name, service=service)
    
    log.info(f"Found {len(urls)} URLs to analyze")
    
    # Process URLs
    updates = []
    for row_idx, url, mobile_psi, desktop_psi, should_skip in urls:
        if should_skip:
            continue
        
        log.info(f"Analyzing {url}...")
        
        try:
            # Run analysis (with caching)
            result = cypress_runner.run_analysis(url, timeout=600)
            
            # Prepare updates
            if result['mobile_score'] >= 80:
                updates.append((row_idx, 'F', 'passed'))
            elif result['mobile_psi_url']:
                updates.append((row_idx, 'F', result['mobile_psi_url']))
            
            if result['desktop_score'] >= 80:
                updates.append((row_idx, 'G', 'passed'))
            elif result['desktop_psi_url']:
                updates.append((row_idx, 'G', result['desktop_psi_url']))
            
            log.info(f"  Mobile: {result['mobile_score']} | Desktop: {result['desktop_score']}")
            
        except Exception as e:
            log.error(f"Failed to analyze {url}: {e}")
    
    # Write results
    if updates:
        sheets_client.batch_write_psi_urls(
            spreadsheet_id, tab_name, updates, service=service
        )
        log.info(f"Updated {len(updates)} cells")
    
    # Export metrics
    metrics.save_json_metrics('metrics.json')
    log.info("Audit complete!")
    
    # Cleanup
    cypress_runner.shutdown_pool()

if __name__ == '__main__':
    main()
```

### Concurrent Processing

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from tools.qa import cypress_runner

def process_url(url):
    return cypress_runner.run_analysis(url, timeout=600)

urls = ['https://example1.com', 'https://example2.com', 'https://example3.com']

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {executor.submit(process_url, url): url for url in urls}
    
    for future in as_completed(futures):
        url = futures[future]
        try:
            result = future.result()
            print(f"{url}: {result['mobile_score']} / {result['desktop_score']}")
        except Exception as e:
            print(f"{url}: Failed - {e}")
```

### Custom Cache Configuration

```python
from tools.cache.cache_manager import CacheManager, RedisBackend, FileCacheBackend

# Use Redis backend
redis_backend = RedisBackend(
    host='localhost',
    port=6379,
    db=0,
    password=None,
    key_prefix='psi:'
)
cache = CacheManager(backend=redis_backend, enabled=True)

# Or use file backend
file_backend = FileCacheBackend(
    cache_dir='.cache',
    max_entries=1000
)
cache = CacheManager(backend=file_backend, enabled=True)
```

### Data Quality Checks

```python
from tools.sheets.data_quality_checker import DataQualityChecker

checker = DataQualityChecker()
urls = sheets_client.read_urls(spreadsheet_id, tab_name, service=service)

# Extract just the URL strings
url_list = [(row, url) for row, url, _, _, _ in urls]

# Run quality checks
results = checker.perform_quality_checks(url_list)

print(f"Exact duplicates: {results['exact_duplicate_count']}")
print(f"Normalized duplicates: {results['normalized_duplicate_count']}")
print(f"Empty URLs: {results['empty_count']}")
```

### Schema Validation

```python
from tools.sheets.schema_validator import SpreadsheetSchemaValidator

validator = SpreadsheetSchemaValidator()
is_valid, errors = validator.validate_schema(
    spreadsheet_id,
    tab_name,
    service
)

if not is_valid:
    print("Schema validation failed:")
    for error in errors:
        print(f"  - {error}")
```

## Authentication

### Service Account Setup

1. Create service account in Google Cloud Console
2. Download JSON key file
3. Enable Google Sheets API
4. Share spreadsheet with service account email

**Code Example:**
```python
from tools.sheets import sheets_client

# Authenticate
service = sheets_client.authenticate('service-account.json')

# Use for multiple operations (connection pooled)
urls = sheets_client.read_urls(spreadsheet_id, tab_name, service=service)
sheets_client.batch_write_psi_urls(spreadsheet_id, tab_name, updates, service=service)
```

### Service Account Validation

```python
from tools.security.service_account_validator import ServiceAccountValidator

is_valid, errors = ServiceAccountValidator.validate('service-account.json')

if not is_valid:
    for error in errors:
        print(f"Validation error: {error}")
```

## Working with Google Sheets

### Reading Data

```python
# Read all tabs
tabs = sheets_client.list_tabs(spreadsheet_id, service=service)
print(f"Available tabs: {tabs}")

# Read URLs from specific tab
urls = sheets_client.read_urls(spreadsheet_id, 'My Tab', service=service)

# URLs returned as: (row_index, url, mobile_psi_url, desktop_psi_url, should_skip)
for row_idx, url, mobile, desktop, skip in urls:
    print(f"Row {row_idx}: {url}")
    if skip:
        print("  (marked to skip)")
```

### Writing Results

```python
# Single cell write
sheets_client.write_psi_url(
    spreadsheet_id,
    tab_name,
    row_index=2,
    column='F',
    url='https://pagespeed.web.dev/...',
    service=service
)

# Batch write (recommended)
updates = [
    (2, 'F', 'https://pagespeed.web.dev/...'),
    (2, 'G', 'passed'),
    (3, 'F', 'passed'),
    (3, 'G', 'passed'),
]

sheets_client.batch_write_psi_urls(
    spreadsheet_id,
    tab_name,
    updates,
    service=service
)
```

### Rate Limiting

```python
from tools.security.rate_limiter import get_spreadsheet_rate_limiter

rate_limiter = get_spreadsheet_rate_limiter()

# Get current usage
usage = rate_limiter.get_usage(spreadsheet_id)
print(f"Current requests: {usage['current_requests']}/{usage['max_requests']}")
print(f"Remaining: {usage['remaining']}")

# Rate limiter automatically enforces limits on write operations
```

## Running Analyses

### Basic Analysis

```python
from tools.qa import cypress_runner

result = cypress_runner.run_analysis('https://example.com')
print(result)
# {
#     'mobile_score': 92,
#     'desktop_score': 95,
#     'mobile_psi_url': None,
#     'desktop_psi_url': None,
#     '_from_cache': False
# }
```

### With Custom Timeout

```python
# Slower sites may need more time
result = cypress_runner.run_analysis(
    'https://slow-site.com',
    timeout=900  # 15 minutes
)
```

### Skip Cache

```python
# Force fresh analysis
result = cypress_runner.run_analysis(
    'https://example.com',
    skip_cache=True
)
```

### Error Handling

```python
from tools.qa.cypress_runner import CypressRunnerError, CypressTimeoutError

try:
    result = cypress_runner.run_analysis('https://example.com')
except CypressTimeoutError as e:
    print(f"Analysis timed out: {e}")
except CypressRunnerError as e:
    print(f"Analysis failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Caching

### Configure Cache Backend

```bash
# Environment variables (.env file)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password

# Or for file cache
CACHE_DIR=.cache
CACHE_MAX_ENTRIES=1000
```

### Programmatic Cache Control

```python
from tools.cache.cache_manager import get_cache_manager

cache = get_cache_manager(enabled=True)

# Check cache
result = cache.get('https://example.com')

# Manual cache store
cache.set('https://example.com', {
    'mobile_score': 92,
    'desktop_score': 95
}, ttl=86400)

# Check existence
if cache.exists('https://example.com'):
    print("URL is cached")

# Invalidate single URL
cache.invalidate('https://example.com')

# Clear all cache
cache.invalidate_all()
```

## Metrics & Monitoring

### Collect Metrics

```python
from tools.metrics.metrics_collector import get_metrics_collector

metrics = get_metrics_collector()

# Get current metrics
data = metrics.get_metrics()
print(f"Success rate: {data['success_rate_percent']:.1f}%")
print(f"Failed URLs: {data['failed_urls']}")
print(f"Cache hit ratio: {data['cache_hit_ratio_percent']:.1f}%")

# Get failure breakdown
for reason, count in data['failure_reasons'].items():
    print(f"  {reason}: {count}")
```

### Export Metrics

```python
metrics = get_metrics_collector()

# Prometheus format
prom_text = metrics.export_prometheus()
with open('metrics.prom', 'w') as f:
    f.write(prom_text)

# JSON format
metrics.save_json_metrics('metrics.json')

# Or get as dict
json_data = metrics.export_json()
```

### Generate Dashboard

```python
from generate_report import generate_html_dashboard

metrics = get_metrics_collector()
data = metrics.get_metrics()

generate_html_dashboard(data, output_file='dashboard.html')
```

## Security Features

### URL Filtering

```python
from tools.security.url_filter import URLFilter

# Create filter with whitelist and blacklist
url_filter = URLFilter(
    whitelist=['https://example.com/*', 'https://*.mydomain.com/*'],
    blacklist=['http://*', 'https://blocked.com/*']
)

# Check if URL is allowed
if url_filter.is_allowed('https://example.com/page'):
    print("URL is allowed")
else:
    print("URL is blocked by filter")
```

### Audit Trail

```python
from tools.security.audit_trail import get_audit_trail

audit = get_audit_trail()

# Audit trail automatically logs all spreadsheet modifications

# Query audit trail programmatically
# (See query_audit_trail.py for command-line querying)
```

## Error Handling

### Exception Types

```python
from tools.utils.exceptions import PermanentError, RetryableError
from tools.qa.cypress_runner import CypressRunnerError, CypressTimeoutError

# PermanentError: No retry, operation failed permanently
# RetryableError: Can be retried (transient failure)
# CypressRunnerError: Cypress execution failure
# CypressTimeoutError: Analysis exceeded timeout
```

### Error Metrics

```python
from tools.utils.error_metrics import get_global_metrics

error_metrics = get_global_metrics()

# Get error statistics
error_metrics.print_summary()

# Get specific metrics
stats = error_metrics.get_statistics()
print(f"Total errors: {stats['total_errors']}")
print(f"Retryable errors: {stats['retryable_errors']}")
print(f"Permanent errors: {stats['permanent_errors']}")
```

### Circuit Breaker

```python
from tools.utils.circuit_breaker import CircuitBreaker

# Circuit breaker is automatically used in cypress_runner
# It protects against cascading failures

# Manual circuit breaker usage
circuit = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=300.0,
    expected_exception=Exception,
    name="MyService"
)

def my_operation():
    # Your code here
    pass

result = circuit.call(my_operation)
```

## Best Practices

1. **Always use service account authentication** for production
2. **Enable caching** to reduce API calls and improve performance
3. **Use batch writes** instead of single cell writes
4. **Monitor metrics** to detect issues early
5. **Set appropriate timeouts** based on your URLs
6. **Use concurrent processing** for large audits (3-5 workers)
7. **Validate URLs** before analysis to catch issues early
8. **Handle errors gracefully** with proper retry logic
9. **Log errors with context** for easier debugging
10. **Clean up resources** by calling `cypress_runner.shutdown_pool()` on exit

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture and design
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development setup and guidelines
- [SECURITY.md](../SECURITY.md) - Security features and best practices
- [CACHE_GUIDE.md](../CACHE_GUIDE.md) - Caching configuration
- [AGENTS.md](../AGENTS.md) - Developer guide
