# Agent Development Guide

**Key Topics:**
- [Threading and Concurrency](#threading-and-concurrency) - Single event loop thread architecture, why async Playwright is used
- [Troubleshooting Greenlet Errors](#troubleshooting-greenlet-errors) - Complete guide to debugging threading issues
- [Skip Logic](#skip-logic) - When URLs are skipped vs re-analyzed (with examples)
- [Data Flow](#data-flow) - Complete workflow from input to output with cell value examples
- [Performance Optimizations](#performance-optimizations) - Browser pooling, request blocking, concurrent processing
- [Error Handling and Recovery](#error-handling-and-recovery) - Debug mode, page reload logic, recovery strategies

## Commands

**Setup:**
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright and browsers
pip install playwright
playwright install chromium
```

**Validate Setup:**
```bash
python validate_setup.py
```

**List Spreadsheet Tabs:**
```bash
python list_tabs.py --spreadsheet-id "YOUR_ID" --service-account "service-account.json"
```

**Run Audit:**
```bash
# Basic usage
python run_audit.py --tab "TAB_NAME" --service-account "service-account.json"

# Check version
python run_audit.py --version

# Use config file to avoid long CLI arguments
python run_audit.py --config config.yaml

# Optional: Specify custom timeout (default: 600 seconds)
python run_audit.py --tab "TAB_NAME" --timeout 1200

# Optional: Skip cache for fresh analysis
python run_audit.py --tab "TAB_NAME" --skip-cache

# Optional: Dry run mode (simulate without changes)
python run_audit.py --tab "TAB_NAME" --dry-run

# Optional: URL filtering (whitelist/blacklist)
python run_audit.py --tab "TAB_NAME" --whitelist "https://example.com/*" --blacklist "http://*"

# Optional: Resume from specific row (for interrupted audits)
python run_audit.py --tab "TAB_NAME" --resume-from-row 50

# Optional: Process only URLs matching regex pattern
python run_audit.py --tab "TAB_NAME" --filter "https://example\.com/.*"

# Optional: Export results to JSON or CSV
python run_audit.py --tab "TAB_NAME" --export-json results.json --export-csv results.csv

# Optional: Validation only mode (no audit execution)
python run_audit.py --tab "TAB_NAME" --validate-only

# Optional: Skip DNS and redirect validation
python run_audit.py --tab "TAB_NAME" --skip-dns-validation --skip-redirect-validation

# Optional: Custom DNS and redirect timeouts
python run_audit.py --tab "TAB_NAME" --dns-timeout 10 --redirect-timeout 15

# Optional: Disable progress bar (useful for logging/CI)
python run_audit.py --tab "TAB_NAME" --no-progress-bar

# Optional: Force retry mode (bypass circuit breaker during critical runs)
python run_audit.py --tab "TAB_NAME" --force-retry

# Optional: Debug mode (verbose logging, screenshots, and HTML capture on errors)
python run_audit.py --tab "TAB_NAME" --debug-mode
```

**Validate Service Account:**
```bash
python validate_service_account.py service-account.json
```

**Validate Skip Logic:**
```bash
# Test skip logic with all scenarios
python validate_skip_logic.py

# Generate test spreadsheet scenarios for debugging
python generate_test_spreadsheet_scenarios.py
```

**Query Audit Trail:**
```bash
# View all modifications
python query_audit_trail.py

# Filter by spreadsheet and date
python query_audit_trail.py --spreadsheet-id "YOUR_ID" --start-date "2024-01-01"

# Show detailed output
python query_audit_trail.py --format detailed --limit 10
```

**Cache Management:**
```bash
# Invalidate specific URL cache
python invalidate_cache.py --url "https://example.com"
# Clear all cache entries
python invalidate_cache.py --all
```

**Metrics and Monitoring:**
```bash
# Metrics are automatically collected during audits
# Generate HTML dashboard with charts
python generate_report.py
# Generate from specific metrics file
python generate_report.py --input metrics.json --output dashboard.html
# Export Prometheus metrics
python generate_report.py --export-prometheus metrics.prom
# Export JSON metrics
python generate_report.py --export-json metrics.json

# View Playwright pool statistics
python get_pool_stats.py
# Export pool stats to JSON
python get_pool_stats.py --json pool_stats.json

# Diagnose threading issues
python diagnose_playwright_threading.py
# Export threading diagnostics to JSON
python diagnose_playwright_threading.py --json threading_diagnostics.json
# Show only specific diagnostics
python diagnose_playwright_threading.py --metrics-only
python diagnose_playwright_threading.py --health-only
python diagnose_playwright_threading.py --pool-only
```

**Build:** Not applicable (Python script)

**Lint:** Not configured

**Test:** 
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tools --cov=run_audit --cov-report=term-missing

# Using convenience scripts
python -m pytest  # Or use run_tests.ps1 (Windows) or ./run_tests.sh (Unix)
```

**Dev Server:** Not applicable (CLI tool)

## Tech Stack

- **Language**: Python 3.7+
- **Browser Automation**: Playwright (Python)
- **APIs**: Google Sheets API v4
- **Caching**: Redis (with file-based fallback)
- **Monitoring**: Prometheus-compatible metrics, Plotly dashboards
- **Security**: Service account validation, rate limiting, URL filtering, audit trail
- **Key Libraries**:
  - `google-api-python-client` - Google Sheets integration
  - `google-auth` - Authentication
  - `redis` - Redis caching backend (optional)
  - `plotly` - Interactive dashboard charts
  - `tqdm` - Progress bars for better UX
  - `pyyaml` - YAML configuration file support
  - `playwright` - Browser automation for PageSpeed Insights

## Error Handling and Recovery

The Playwright runner includes comprehensive error handling and recovery mechanisms:

### Page Reload Logic
- Automatically reloads page when selectors fail repeatedly (up to 3 attempts)
- Fresh start logic ensures clean state after failures
- Tracks reload attempts to prevent infinite loops

### Debug Mode (`--debug-mode`)
When enabled, the system:
- Captures screenshots on failures (saved to `debug_screenshots/`)
- Saves page HTML on errors for post-mortem analysis
- Enables verbose Playwright logging
- Includes timestamp and sanitized URL in filenames
- Creates enhanced error messages with diagnostic information

### Enhanced Error Messages
Error messages include:
- Current page URL and title
- Available buttons and elements on the page
- Last successful step before failure
- Paths to debug screenshots and HTML files
- Visibility status of page elements

### Recovery Strategies
1. **Selector Timeout**: Retries with page reload
2. **Analysis Timeout**: Aborts immediately (not retryable)
3. **Button Not Found**: Reloads page and retries with multiple selectors
4. **Score Extraction Failed**: Captures debug artifacts and provides detailed context

### Debug Artifacts
All debug files are saved with format: `YYYYMMDD_HHMMSS_sanitized-url_reason.{png|html}`
- Screenshots: Full-page captures in PNG format
- HTML: Complete page source at time of error
- Organized in `debug_screenshots/` directory (gitignored)

## Threading and Concurrency

The system uses a dedicated event loop thread for all Playwright operations to ensure thread safety:

### Threading Architecture

**Why Single Event Loop Thread?**

Playwright Python is built on async/await and requires all operations to run within the same event loop. The system implements a dedicated event loop thread architecture to:
- **Ensure Thread Safety**: All Playwright operations (browser contexts, pages, async calls) execute on a single thread
- **Enable Synchronous API**: Main thread can submit requests and receive results synchronously while Playwright runs asynchronously
- **Prevent Greenlet Errors**: Avoid "greenlet.error: cannot switch to a different thread" by guaranteeing all async operations share the same event loop
- **Support Concurrency**: Multiple requests can be queued and processed concurrently within the single event loop thread

**Architecture Components:**
- **Main Thread**: Handles application logic, submits analysis requests, processes results
- **Event Loop Thread**: Dedicated daemon thread running asyncio event loop for all Playwright operations
- **Single-Thread Guarantee**: All browser contexts, pages, and async operations execute on the event loop thread
- **Thread-Safe Queue**: Analysis requests are submitted via `asyncio.run_coroutine_threadsafe()` from main thread to event loop thread
- **Future Objects**: Requests return `concurrent.futures.Future` objects that block main thread until event loop completes the async operation

**Why Async Playwright Despite Synchronous API?**

Although `run_audit.py` appears to use a synchronous API (calling `run_analysis()` without `await`), Playwright internally uses async/await because:

1. **Browser Automation is Inherently Asynchronous**: Network requests, page loads, DOM queries, and user interactions are I/O-bound operations that benefit from async execution
2. **Performance**: Async allows multiple operations to run concurrently (e.g., multiple browser contexts analyzing different URLs simultaneously)
3. **Non-Blocking**: The event loop can handle multiple page interactions without blocking other operations
4. **Playwright Design**: The Playwright library is designed as async-first, with sync wrappers being secondary

The system bridges the gap by:
- Running async Playwright code on the dedicated event loop thread
- Exposing a synchronous interface to the main application thread
- Using `asyncio.run_coroutine_threadsafe()` to schedule async operations from the main thread
- Returning `Future` objects that the main thread can block on to get results

**Threading Flow Example:**

```
Main Thread                          Event Loop Thread
-----------                          -----------------
1. Submit request                    (Event loop running continuously)
   run_analysis(url) -->             
                                     2. Queue receives request
                                     3. Schedule async coroutine
                                     4. Execute async Playwright code:
                                        - await browser.new_context()
                                        - await page.goto()
                                        - await page.click()
                                        - await page.locator().text_content()
5. Block on Future.result()          
                                     6. Complete async operations
                                     7. Set Future result
<-- Return results
8. Process results
```

### Threading Diagnostics
Comprehensive logging and debugging for threading issues:

**Thread ID Logging**:
- All Playwright operations log thread ID and thread name
- Format: `[Thread-<ID>:<Name>]` prefix on all thread-related log messages
- Tracks which thread creates browser contexts, pages, and runs async operations

**Threading Metrics**:
- `greenlet_errors`: Count of greenlet-related errors
- `thread_conflicts`: Count of thread conflict errors
- `event_loop_failures`: Count of event loop failures
- `context_creation_by_thread`: Tracks browser context creation per thread ID
- `page_creation_by_thread`: Tracks page creation per thread ID
- `async_operations_by_thread`: Tracks async operations per thread ID

**Event Loop Health Checks**:
- Periodic heartbeat (every 5 seconds) to monitor event loop responsiveness
- Tracks last heartbeat timestamp and failures
- Automatic detection of unresponsive event loops (>30s since last heartbeat)
- Health status includes: last heartbeat, time since heartbeat, failure count, responsive status

**Error Detection**:
- Automatic detection of greenlet errors (searches for "greenlet" or "gr_frame" in error messages)
- Automatic detection of thread conflicts (searches for "thread" and "conflict" in error messages)
- Full stack traces logged for all threading-related errors
- Metrics automatically incremented when threading issues detected

**Diagnostic Tools**:
- `diagnose_threading_issues()`: Returns comprehensive threading diagnostic report
- `print_threading_diagnostics()`: Prints formatted diagnostic report to stdout
- `get_threading_metrics()`: Returns current threading metrics
- `get_event_loop_health()`: Returns event loop health status
- `reset_threading_metrics()`: Resets all threading metrics

**Diagnostic Script**:
```bash
# Full diagnostics report
python diagnose_playwright_threading.py

# Export to JSON for analysis
python diagnose_playwright_threading.py --json diagnostics.json

# View specific components
python diagnose_playwright_threading.py --metrics-only
python diagnose_playwright_threading.py --health-only
python diagnose_playwright_threading.py --pool-only
```

The diagnostic report includes:
- Python version and asyncio configuration
- Main thread information (ID, name, status)
- All active threads (ID, name, daemon status, alive status)
- Event loop thread details (ID, name, loop status)
- Threading metrics (errors, conflicts, operations by thread)
- Event loop health (heartbeat status, responsiveness)
- Pool statistics (instances, warm/cold starts)

### Troubleshooting Greenlet Errors

**What is a Greenlet Error?**

Greenlet is a lightweight cooperative threading library used internally by Playwright's async implementation. The error "greenlet.error: cannot switch to a different thread" occurs when Playwright tries to switch execution context between threads, which violates the single-thread requirement for asyncio event loops.

**Common Causes:**

1. **Multi-Threaded Playwright Usage**: Creating browser contexts or pages from different threads
2. **Mixed Event Loops**: Running Playwright operations across multiple asyncio event loops
3. **Thread Pool Executor Issues**: Submitting Playwright async operations directly to ThreadPoolExecutor without proper event loop management

**How the System Prevents Greenlet Errors:**

1. **Dedicated Event Loop Thread**: All Playwright operations run on a single dedicated thread
2. **Thread-Safe Submission**: Main thread submits requests via `asyncio.run_coroutine_threadsafe()` which properly schedules async operations on the event loop thread
3. **Single Browser Pool**: All browser contexts and pages are created and managed within the event loop thread
4. **Heartbeat Monitoring**: Event loop health checks ensure the loop is responsive and running on the correct thread

**If You Encounter Greenlet Errors:**

1. **Check Threading Diagnostics**:
   ```bash
   python diagnose_playwright_threading.py
   ```
   Look for:
   - `greenlet_errors` count in metrics
   - Multiple thread IDs in `context_creation_by_thread` or `page_creation_by_thread`
   - Event loop health status

2. **Enable Debug Logging**:
   ```bash
   python run_audit.py --tab "TAB_NAME" --debug-mode
   ```
   This will show thread IDs for all Playwright operations

3. **Verify Event Loop Thread**:
   - All Playwright operations should show the same thread ID (the event loop thread)
   - Main thread should have a different thread ID

4. **Common Fixes**:
   - Restart the application (event loop may be corrupted)
   - Reduce concurrency: `--concurrency 1` to eliminate threading complexity
   - Check for event loop unresponsiveness (>30s since last heartbeat)
   - Review custom code modifications that may call Playwright from wrong thread

5. **Reset Threading Metrics** (for testing):
   ```python
   from tools.qa.playwright_runner import reset_threading_metrics
   reset_threading_metrics()
   ```

**Example Error Message:**
```
greenlet.error: cannot switch to a different thread
```

**Typical Stack Trace Pattern:**
```
File "playwright/_impl/_browser_context.py", line X, in new_page
File "greenlet/__init__.py", line Y, in switch
greenlet.error: cannot switch to a different thread
```

**Prevention Best Practices:**
- Never call Playwright operations directly from ThreadPoolExecutor
- Always use `asyncio.run_coroutine_threadsafe()` to submit async Playwright operations from other threads
- Keep all browser context and page creation within the event loop thread
- Don't mix sync and async Playwright APIs

## Performance Optimizations

The system has been comprehensively optimized for faster URL processing:

### Core Optimizations
1. **Result Caching**: Redis/file-based cache with 24-hour TTL and LRU eviction (1000 entries max)
2. **Reduced Timeouts**: Default timeout reduced from 900s to 600s with optimized Playwright timeouts
3. **Fewer Retries**: Playwright retries reduced from 5 to 2, Python retries from 10 to 3
4. **Faster Waits**: Inter-action waits reduced from 5-15s to 2s
5. **Incremental Updates**: Spreadsheet updates happen immediately after each URL (not batched at end)
6. **Result Streaming**: Results are streamed to avoid large JSON file I/O operations
7. **Progressive Timeout**: Timeout starts at 300s, increases to 600s after first failure

### Playwright-Specific Optimizations

**Browser Instance Pooling (Up to 3 Concurrent Browsers)**:
- Pool maintains up to 3 persistent browser contexts for parallel processing
- Warm start instances reuse existing browser contexts for 2-3x faster execution
- Cold start instances are created on-demand with optimized launch flags
- Automatic memory monitoring with 1GB threshold per instance
- Instances are auto-killed after 3 consecutive failures or high memory usage
- Pool cleanup on application shutdown

**Network Request Interception & Resource Blocking**:
- Automatically blocks unnecessary resources to speed up page loads:
  - Images, media files, fonts, stylesheets (visual assets not needed for PSI)
  - Analytics scripts (Google Analytics, GTM, Facebook Pixel, etc.)
  - Advertising networks (DoubleClick, Google Ads, etc.)
  - Tracking beacons and telemetry endpoints
- Typical blocking ratio: 40-60% of requests blocked
- Reduces bandwidth usage and page load time by 30-50%

**Parallel Browser Management**:
- Default concurrency increased to 3 workers (up from 1)
- Each worker can use a separate browser instance from the pool
- ThreadPoolExecutor manages parallel URL processing
- Configurable via `--concurrency` flag (1-5 workers supported)

**Performance Monitoring**:
- Tracks page load time per URL analysis
- Measures browser startup time for cold starts
- Records memory usage per instance over time
- Monitors warm/cold start ratio
- Collects resource blocking statistics (total vs blocked requests)
- All metrics exported to Prometheus and JSON formats

**Additional Browser Optimizations**:
- Headless mode with GPU and extension disabling
- Disabled sandboxing for faster startup (safe in containerized environments)
- CSP bypass and HTTPS error ignoring for problematic sites
- DOM content loaded instead of full network idle (faster analysis start)

## Architecture

### Project Structure

```
.
├── run_audit.py              # Main entry point - orchestrates the audit
├── generate_report.py        # Generate HTML metrics dashboard
├── get_pool_stats.py         # Display Playwright pool statistics
├── list_tabs.py              # Utility to list spreadsheet tabs
├── get_service_account_email.py  # Utility to get service account email
├── validate_setup.py         # Setup validation script
├── invalidate_cache.py       # Cache invalidation utility
├── tools/
│   ├── metrics/
│   │   └── metrics_collector.py  # Prometheus-compatible metrics collection
│   ├── sheets/
│   │   ├── sheets_client.py  # Google Sheets API wrapper
│   │   ├── schema_validator.py  # Spreadsheet schema validation
│   │   └── data_quality_checker.py  # Duplicate URL and data quality checks
│   ├── qa/
│   │   └── playwright_runner.py # Playwright automation wrapper
│   ├── cache/
│   │   └── cache_manager.py  # Cache layer (Redis + file backend)
│   ├── security/
│   │   ├── service_account_validator.py  # Service account validation
│   │   ├── url_filter.py     # URL whitelist/blacklist filtering
│   │   ├── audit_trail.py    # Audit trail logging
│   │   └── rate_limiter.py   # Per-spreadsheet rate limiting
│   └── utils/
│       ├── logger.py         # Logging utilities
│       └── url_validator.py  # URL validation (regex, DNS, redirects) and normalization
├── .cache/                   # File cache storage (gitignored)
├── debug_screenshots/        # Debug screenshots and HTML files (gitignored)
├── metrics.json              # JSON metrics export (gitignored)
├── metrics.prom              # Prometheus metrics export (gitignored)
├── dashboard.html            # HTML metrics dashboard (gitignored)
├── audit_trail.jsonl         # Audit trail log (gitignored)
├── validate_service_account.py  # Service account validator utility
├── query_audit_trail.py      # Audit trail query utility
└── SECURITY.md               # Security features documentation
```

### Data Flow

1. **Input**: URLs from Google Sheets column A (starting row 2)
2. **Processing**:
   - `run_audit.py` reads URLs via `sheets_client.py`
   - For each URL, `playwright_runner.py` checks cache first (unless `--skip-cache`)
   - On cache miss, launches Playwright browser (retries up to 3 times on failure)
   - Results are cached with 24-hour TTL for future runs
   - **Playwright workflow**:
     1. Opens Chromium browser in headless mode
     2. Navigates to https://pagespeed.web.dev
     3. Enters target URL and starts analysis
     4. Waits up to 30 seconds for analysis to complete
     5. Waits for Mobile/Desktop toggle buttons to appear
     6. Clicks "Mobile" button and extracts score from `.lh-exp-gauge__percentage`
     7. Clicks "Desktop" button and extracts score from `.lh-exp-gauge__percentage`
     8. Captures PageSpeed Insights URLs for both views
   - Results returned as structured data
   - **Incremental updates**: Spreadsheet is updated immediately after each URL is analyzed (not batched at the end)
3. **Output**: 
   - For scores >= 80: Cell is filled with the text `"passed"`
   - For scores < 80: PSI URLs written to columns F (mobile) and G (desktop)
   - Each URL's results are written to the sheet immediately upon completion
   - **Metrics export**: `metrics.json` and `metrics.prom` files generated
   - **Dashboard**: HTML dashboard can be generated with `generate_report.py`
   - **Alerting**: Warnings logged if failure rate exceeds 20%

**Example Output Values:**

| Scenario | Column F (Mobile) | Column G (Desktop) |
|----------|-------------------|-------------------|
| Both pass (≥80) | `passed` | `passed` |
| Mobile fails, Desktop passes | `https://pagespeed.web.dev/analysis?url=...` | `passed` |
| Mobile passes, Desktop fails | `passed` | `https://pagespeed.web.dev/analysis?url=...` |
| Both fail (<80) | `https://pagespeed.web.dev/analysis?url=...` | `https://pagespeed.web.dev/analysis?url=...` |

### Skip Logic

The audit tool implements intelligent skip logic to avoid re-analyzing URLs that have already been successfully audited:

**When URLs are Skipped:**

A URL is **skipped** (not re-analyzed) when **BOTH** of the following conditions are true:
1. Column F (Mobile) contains the text `"passed"` **OR** has a green background color (RGB: 0, 255, 0)
2. Column G (Desktop) contains the text `"passed"` **OR** has a green background color (RGB: 0, 255, 0)

**When URLs are Analyzed:**

A URL is **analyzed** when **ANY** of the following conditions are true:
- Column F is empty
- Column G is empty
- Column F contains a PSI URL (e.g., `https://pagespeed.web.dev/analysis?url=...`)
- Column G contains a PSI URL
- Column F contains any text other than `"passed"` without green background
- Column G contains any text other than `"passed"` without green background
- Only ONE of the columns has `"passed"` or green background (both must pass to skip)

**Skip Logic Examples:**

| Column F (Mobile) | Column G (Desktop) | Skip? | Reason |
|-------------------|-------------------|-------|--------|
| `passed` | `passed` | ✅ YES | Both columns contain "passed" |
| `passed` (green bg) | `passed` (green bg) | ✅ YES | Both columns have green background |
| `passed` | `passed` (green bg) | ✅ YES | F has text "passed", G has green background |
| `passed` (green bg) | `passed` | ✅ YES | F has green background, G has text "passed" |
| `passed` | `https://pagespeed.web.dev/...` | ❌ NO | Desktop has PSI URL (failed score) |
| `https://pagespeed.web.dev/...` | `passed` | ❌ NO | Mobile has PSI URL (failed score) |
| `passed` | (empty) | ❌ NO | Desktop column is empty |
| (empty) | `passed` | ❌ NO | Mobile column is empty |
| (empty) | (empty) | ❌ NO | Both columns are empty |
| `https://pagespeed.web.dev/...` | `https://pagespeed.web.dev/...` | ❌ NO | Both have PSI URLs (failed scores) |
| `Error` | `passed` | ❌ NO | Mobile has error text (not "passed") |
| `passed` | `Error` | ❌ NO | Desktop has error text (not "passed") |

**Implementation Details:**

The skip logic checks both text content and cell background color:

1. **Text Check**: Looks for exact match of `"passed"` (case-sensitive)
2. **Color Check**: Looks for green background with RGB values (0, 255, 0)
3. **AND Logic**: Both columns F AND G must pass at least one check (text OR color) to skip the URL

**Validation Script:**

To test skip logic with various scenarios:
```bash
python validate_skip_logic.py
```

This validates all skip logic scenarios and reports which URLs would be skipped vs analyzed.

**Generate Test Spreadsheet:**

To create a spreadsheet with all skip logic test scenarios:
```bash
python generate_test_spreadsheet_scenarios.py
```

This creates a test tab with examples of every skip/analyze condition for manual verification.

**Quick Reference - Will This URL Be Skipped?**

Use this table to quickly determine if a URL will be skipped or analyzed:

| Column F | Column G | Skip? | Explanation |
|----------|----------|-------|-------------|
| ✅ passed | ✅ passed | **YES** | Both passed - skip |
| ✅ passed | 🟩 green | **YES** | Both passed - skip |
| 🟩 green | 🟩 green | **YES** | Both passed - skip |
| ✅ passed | ❌ PSI URL | **NO** | Desktop failed - analyze |
| ❌ PSI URL | ✅ passed | **NO** | Mobile failed - analyze |
| ✅ passed | ⬜ empty | **NO** | Desktop not done - analyze |
| ⬜ empty | ✅ passed | **NO** | Mobile not done - analyze |
| ⬜ empty | ⬜ empty | **NO** | Neither done - analyze |
| ❌ PSI URL | ❌ PSI URL | **NO** | Both failed - analyze |
| ⚠️ Error | ✅ passed | **NO** | Mobile error - analyze |
| ✅ passed | ⚠️ Error | **NO** | Desktop error - analyze |

**Legend**: ✅ = "passed" text, 🟩 = green background, ❌ = PSI URL, ⬜ = empty, ⚠️ = error message

**Cell Value Examples:**

| Scenario | Column F (Mobile) | Column G (Desktop) | Notes |
|----------|-------------------|-------------------|-------|
| **Success Cases** | | | |
| Both scores pass (≥80) | `passed` | `passed` | Most common success state |
| Both scores pass (green cells) | (green bg) | (green bg) | Alternative success indicator |
| Mixed indicators | `passed` | (green bg) | Either indicator works per column |
| **Failure Cases** | | | |
| Mobile fails, Desktop passes | `https://pagespeed.web.dev/analysis?url=https://example.com` | `passed` | PSI URL for failed score |
| Mobile passes, Desktop fails | `passed` | `https://pagespeed.web.dev/analysis?url=https://example.com` | PSI URL for failed score |
| Both fail (scores <80) | `https://pagespeed.web.dev/analysis?url=https://example.com` | `https://pagespeed.web.dev/analysis?url=https://example.com` | Both get PSI URLs |
| **Error Cases** | | | |
| Analysis timeout | `Error: Timeout` | `Error: Timeout` | Both columns show error |
| Browser error | `Error: Browser failed` | (empty) | Partial error state |
| Network error | `Error: Network timeout` | `Error: Network timeout` | Both columns show error |
| **Pending Cases** | | | |
| Not yet analyzed | (empty) | (empty) | Will be analyzed on next run |
| Previously failed, re-run | `https://pagespeed.web.dev/...` | `https://pagespeed.web.dev/...` | Will be re-analyzed |

### Key Components

#### run_audit.py
- Main orchestrator
- Handles command-line arguments
- Performs schema and data quality validation on startup
- URL validation with DNS and redirect checks
- URL normalization before analysis
- Manages the audit loop
- Collects and reports statistics
- Supports `--validate-only` mode for validation without audit execution

#### sheets_client.py
- Authenticates with Google Sheets API
- Reads URLs from spreadsheet (range A2:A)
- Writes PSI URLs back to spreadsheet
- Handles errors (permissions, missing tabs, etc.)

#### playwright_runner.py
- Manages Playwright browser instances with advanced pooling
- Runs PageSpeed Insights analysis with proper error handling
- **Persistent Retry Logic**: Infinite retry with exponential backoff (5s-60s) for retryable errors until success or explicit timeout
- **Smart Timeout Handling**: Distinguishes between analysis timeout (abort) vs selector timeout (retry with fresh page load)
- **Page Reload Recovery**: Automatically reloads page when selectors fail repeatedly (up to 3 attempts)
- **Circuit Breaker**: Protects against cascading failures, can be bypassed with `force_retry` flag
- **Enhanced Error Messages**: Includes current page URL, available elements, last successful step, and debug artifacts
- **Debug Mode Support**: Captures screenshots and HTML on errors when `--debug-mode` is enabled
- **Debug Screenshots**: Saves full-page screenshots to `debug_screenshots/` with timestamp and URL
- **Debug HTML**: Saves complete page source for post-mortem analysis
- **Page Diagnostics**: Extracts buttons, inputs, links, and their visibility status for debugging
- Returns structured results with performance metrics
- **Progressive Timeout**: Starts at 300s, increases to 600s after first failure
- **Instance Pooling**: Maintains pool of up to 3 reusable browser contexts for warm starts
- **Network Request Interception**: Blocks unnecessary resources (images, fonts, ads, analytics)
- **Memory Monitoring**: Monitors browser memory usage and auto-restarts on >1GB
- **Parallel Processing**: Supports up to 3 concurrent browser instances
- **Performance Tracking**: Records page load time, browser startup time, memory usage
- **Resource Blocking Stats**: Tracks total vs blocked requests per instance
- Runs Playwright in explicit headless mode with optimized launch flags
- Pool cleanup via `shutdown_pool()` called on application exit
- Pool statistics accessible via `get_pool_stats()` function

#### logger.py
- Sets up logging to both console and file
- Creates timestamped log files in `logs/` directory

#### url_validator.py
- URL format validation with comprehensive regex
- DNS resolution validation with configurable timeout
- Redirect chain detection (flags chains >3 redirects)
- URL normalization (trailing slashes, query params, case)
- URLNormalizer class for consistent URL formatting

#### schema_validator.py
- Validates spreadsheet schema on startup
- Checks for required columns (A-G)
- Verifies header row presence
- Ensures data rows exist

#### data_quality_checker.py
- Detects exact duplicate URLs
- Detects normalized duplicates (URLs that normalize to same value)
- Reports empty URLs
- Generates detailed duplicate reports with row numbers

#### metrics_collector.py
- Thread-safe metrics collection
- Tracks success/failure rates, processing time, cache efficiency
- Monitors API quota usage (Sheets and Playwright)
- **Playwright-Specific Metrics**:
  - Page load time (average, per URL)
  - Browser startup time (cold starts only)
  - Memory usage per instance (average, min, max)
  - Warm vs cold start ratio
  - Request blocking statistics (total, blocked, ratio)
- Prometheus-compatible export format
- JSON export for dashboards
- Automatic alerting when failure rate exceeds 20%
- Records failure reasons for analysis

## Code Style

- Follow PEP 8 for Python code
- No comments unless necessary for complex logic
- Use type hints for function parameters and returns
- Handle errors gracefully with informative messages
- Use f-strings for string formatting
- Keep functions focused and single-purpose

## Important Implementation Details

### Unicode Encoding Fix
All subprocess calls must include:
```python
subprocess.run(
    [...],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace'
)
```
This prevents `UnicodeDecodeError` on Windows when processing non-ASCII characters.

### Spreadsheet Range
URLs are read from `A2:A` (not `A:A`) to skip the header row. Row enumeration starts at 2 to maintain correct row numbers when writing results back.

### Error Handling
- Catch specific exceptions (FileNotFoundError, PermissionError, ValueError)
- Provide actionable error messages
- Log full tracebacks for debugging
- Continue processing remaining URLs even if one fails

### Retry Logic
Playwright runs can fail transiently. The system implements persistent retry-until-success:
- **Infinite retry with exponential backoff**: For retryable errors, the system retries indefinitely until successful or explicit timeout/permanent error
- **Exponential backoff**: Starts at 5s, doubles on each retry, max 60s between retries
- **Timeout handling**:
  - **Analysis timeout** (PlaywrightAnalysisTimeoutError): Overall operation timeout - aborts immediately, not retryable
  - **Selector timeout** (PlaywrightSelectorTimeoutError): Failed to find page elements - retries with fresh page load
- **Circuit breaker**: Protects against cascading failures by opening after 5 consecutive failures
- **Force retry mode**: Use `--force-retry` flag to bypass circuit breaker during critical runs

## Input Validation and Data Quality

### Validation Features

The system includes comprehensive input validation and data quality checks:

1. **URL Format Validation**
   - Regex-based URL format checking
   - Scheme validation (http/https)
   - Domain/hostname validation
   - Dangerous character detection

2. **DNS Resolution**
   - Verifies domain resolves to IP address
   - Configurable timeout (default: 5s, use `--dns-timeout`)
   - Can be disabled with `--skip-dns-validation`

3. **Redirect Chain Detection**
   - Detects HTTP redirects
   - Flags URLs with >3 redirects
   - Configurable timeout (default: 10s, use `--redirect-timeout`)
   - Can be disabled with `--skip-redirect-validation`

4. **URL Normalization**
   - Converts scheme and domain to lowercase
   - Normalizes trailing slashes
   - Sorts query parameters alphabetically
   - Applied automatically before analysis

5. **Duplicate URL Detection**
   - Detects exact duplicates
   - Detects normalized duplicates (minor variations)
   - Reports duplicate groups with row numbers
   - Runs on every audit startup

6. **Spreadsheet Schema Validation**
   - Validates column structure (A-G required)
   - Checks header row presence
   - Ensures data rows exist
   - Runs automatically on startup

### Validation-Only Mode

Use `--validate-only` to run validations without executing the audit:

```bash
python run_audit.py --tab "TAB_NAME" --validate-only
```

This mode performs:
- Schema validation
- Data quality checks (duplicates, empty URLs)
- URL validation (format, DNS, redirects) for all URLs
- Detailed validation report with pass/fail status

Useful for:
- Pre-flight checks before running expensive audits
- Identifying data quality issues
- Testing URL accessibility
- Detecting redirect chains

## CLI Enhancements

### Resume from Specific Row

Resume an interrupted audit from a specific row number:

```bash
python run_audit.py --tab "TAB_NAME" --resume-from-row 50
```

This will skip all URLs before row 50 and continue from there. Useful for:
- Recovering from interrupted audits
- Re-running only the remaining URLs after fixing issues
- Processing large spreadsheets in batches

### Filter URLs by Regex Pattern

Process only URLs matching a regex pattern:

```bash
python run_audit.py --tab "TAB_NAME" --filter "https://example\.com/products/.*"
```

The filter is applied as a regex search on the URL string. Useful for:
- Auditing specific subsets of URLs (e.g., only product pages)
- Testing changes on specific URL patterns
- Splitting large audits by URL pattern

### Export Results

Export audit results to JSON or CSV format:

```bash
# Export to JSON
python run_audit.py --tab "TAB_NAME" --export-json results.json

# Export to CSV
python run_audit.py --tab "TAB_NAME" --export-csv results.csv

# Export to both formats
python run_audit.py --tab "TAB_NAME" --export-json results.json --export-csv results.csv
```

Exported data includes:
- Row numbers
- URLs processed
- Mobile and desktop scores
- PSI URLs
- Error information (if any)
- Skip/validation status

### Configuration File Support

Use a YAML configuration file to avoid long command-line arguments:

```bash
# Create a config file (config.yaml)
# See config.example.yaml for all options
python run_audit.py --config config.yaml
```

Example `config.yaml`:
```yaml
tab: "Production URLs"
timeout: 600
concurrency: 3
export-json: "results.json"
export-csv: "results.csv"
resume-from-row: 50
filter: "https://example\\.com/.*"
```

CLI arguments override config file values, so you can use the config for defaults and override specific options:

```bash
python run_audit.py --config config.yaml --concurrency 5
```

### Progress Bar

A visual progress bar is displayed by default using `tqdm`:

```
Processing URLs: 45%|████████████████          | 45/100 [02:15<02:45, 0.33url/s]
```

To disable the progress bar (useful for logging or CI environments):

```bash
python run_audit.py --tab "TAB_NAME" --no-progress-bar
```

### Version Information

Check the tool version:

```bash
python run_audit.py --version
```

## Configuration

### Constants in run_audit.py
- `DEFAULT_SPREADSHEET_ID`: Default Google Sheets ID
- `SERVICE_ACCOUNT_FILE`: Default service account path
- `MOBILE_COLUMN`: Column for mobile results (default: 'F')
- `DESKTOP_COLUMN`: Column for desktop results (default: 'G')
- `SCORE_THRESHOLD`: Minimum passing score (default: 80)
- Default timeout: 600 seconds (can be overridden with --timeout flag)

**Timeout Recommendations:**
- Fast connection, simple sites: 600 seconds (default)
- Average connection/sites: 900 seconds (15 minutes) - recommended for most use cases
- Slow connection or complex sites: 1200 seconds (20 minutes)
- Very slow connections: 1800 seconds (30 minutes)

### Validation Configuration
- `--dns-timeout`: DNS resolution timeout in seconds (default: 5.0)
- `--redirect-timeout`: Redirect check timeout in seconds (default: 10.0)
- `--skip-dns-validation`: Disable DNS resolution checks
- `--skip-redirect-validation`: Disable redirect chain checks
- `--validate-only`: Run validation without audit execution

### Security Configuration
- `RATE_LIMIT_REQUESTS_PER_MINUTE`: API rate limit per spreadsheet (default: 60)
- `AUDIT_TRAIL_PATH`: Path to audit trail log file (default: audit_trail.jsonl)
- `URL_WHITELIST`: Comma-separated URL patterns to allow
- `URL_BLACKLIST`: Comma-separated URL patterns to block

### Environment Variables
Cache behavior can be configured via environment variables (see `.env.example`):
- `REDIS_HOST`: Redis server host (default: localhost)
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_PASSWORD`: Redis authentication password (optional)
- `CACHE_DIR`: File cache directory (default: .cache)
- `CACHE_MAX_ENTRIES`: Maximum file cache entries (default: 1000)

## Common Tasks

### Adding a New Column
1. Define a new column constant in `run_audit.py`
2. Modify the results processing logic
3. Add the value to the `updates` list
4. Update README documentation

### Changing Score Threshold
Edit `SCORE_THRESHOLD` in `run_audit.py`.

### Modifying PageSpeed Insights Automation
If PageSpeed Insights UI changes:
1. Edit `playwright_runner.py`
2. Update selectors to match new DOM structure
3. Current key selectors (with fallback hierarchy):
   - URL input: `[data-testid="url-input"]` → `input[name="url"]`
   - Analyze button: `[data-testid*="analyze"]` → `button` containing text matching `/analyze/i`
   - Score display: `[data-testid="score-gauge"]` → `.lh-exp-gauge__percentage` → `.lh-gauge__percentage`
   - Mobile/Desktop toggle: `[data-testid*="mobile/desktop"]` → `button` containing 'Mobile' or 'Desktop'
4. Test with Playwright codegen: `playwright codegen https://pagespeed.web.dev`

### Adding More Retry Attempts
1. Modify `max_retries` parameter in `playwright_runner.py` `run_analysis()` function (default: 3)
2. Adjust timeout with `--timeout` flag when running `run_audit.py` (default: 600 seconds)

## Testing

### Automated Test Suite

A comprehensive test suite is available with 70% code coverage target:

**Quick Start:**
```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage report
pytest --cov=tools --cov=run_audit --cov-report=term-missing

# Check coverage threshold (70%)
pytest --cov=tools --cov=run_audit --cov-report=term-missing
coverage report --fail-under=70

# Generate HTML coverage report
pytest --cov=tools --cov=run_audit --cov-report=html
```

**Using Convenience Scripts:**
```bash
# Windows (PowerShell)
.\run_tests.ps1                  # Run all tests
.\run_tests.ps1 unit -Verbose    # Run unit tests with verbose output
.\run_tests.ps1 coverage -Html   # Run with HTML coverage report

# Unix/Linux/Mac
./run_tests.sh                   # Run all tests
./run_tests.sh unit --verbose    # Run unit tests with verbose output
./run_tests.sh coverage --html   # Run with HTML coverage report

# Or use Make (Unix/Linux/Mac)
make test                        # Run all tests
make test-unit                   # Run unit tests
make test-cov                    # Run with coverage
make test-cov-check              # Run and check 70% threshold
```

**Test Structure:**
- `tests/unit/test_sheets_client.py` - Google Sheets API wrapper tests
- `tests/unit/test_playwright_runner.py` - Playwright automation tests
- `tests/unit/test_logger.py` - Logging utilities tests
- `tests/integration/test_run_audit.py` - Main audit orchestration tests
- `tests/conftest.py` - Shared fixtures and test configuration

**Continuous Integration:**
Tests run automatically on GitHub Actions for every push and pull request, testing against Python 3.8, 3.9, 3.10, and 3.11.

### Manual Testing Workflow

For manual end-to-end testing:

1. Run `python validate_setup.py` to verify setup
2. Run `python list_tabs.py` to verify Google Sheets access
3. Run `python run_audit.py --tab "Test Tab"` with a small set of URLs
4. Verify results in spreadsheet
5. Check logs in `logs/` directory

## Debugging

### Enable Verbose Logging
Logs are automatically saved to `logs/audit_YYYYMMDD_HHMMSS.log`.

### Test Playwright Manually
```bash
# Generate test code interactively
playwright codegen https://pagespeed.web.dev

# Run in headed mode for debugging
# Modify playwright_runner.py temporarily to set headless=False
```

### Common Issues
1. **UnicodeDecodeError**: Fixed by adding `encoding='utf-8', errors='replace'` to subprocess calls
2. **Timeout errors**: Increase timeout with `--timeout 900` or higher (see timeout recommendations above)
3. **Permission denied**: Verify spreadsheet is shared with service account email
4. **Slow processing**: Check network connectivity and PageSpeed Insights availability
5. **Cache issues**: See CACHE_GUIDE.md for troubleshooting cache-related problems
6. **Browser installation issues**: If Playwright browsers are not installed, run `playwright install chromium`
7. **Headless mode failures**: Some systems may have issues with headless browsers. Check system dependencies:
   - **Linux**: Install required system libraries: `playwright install-deps chromium`
   - **Docker/CI**: Use official Playwright Docker images or install dependencies
   - **WSL**: Ensure X11 forwarding is configured if running in headed mode
8. **Browser crashes**: Monitor memory usage; restart may be needed for long-running audits
9. **Selector failures**: PageSpeed Insights UI may have changed; update selectors in `playwright_runner.py`

### PageSpeed Insights Selector Troubleshooting

Common selector issues and their solutions:

#### Mobile/Desktop Toggle Button Not Found
- **Symptom**: Error message "Failed to find Mobile/Desktop toggle buttons"
- **Cause**: Buttons don't appear until PageSpeed analysis completes
- **Solution**: 
  - Increase overall timeout: `--timeout 1200` 
  - Enable debug mode: `--debug-mode` to capture screenshots
  - Check `debug_screenshots/` directory for page state at failure
  - The tool waits up to 30 seconds for buttons to appear; if consistently failing, may need longer analysis time

#### Score Extraction Failed
- **Symptom**: Error extracting score from `.lh-exp-gauge__percentage`
- **Cause**: PageSpeed Insights UI changed or element not visible
- **Solution**:
  - Enable debug mode to capture page HTML: `--debug-mode`
  - Inspect saved HTML in `debug_screenshots/` directory
  - Test manually at https://pagespeed.web.dev
  - Update selector hierarchy in `playwright_runner.py` if UI changed:
    - Primary: `.lh-exp-gauge__percentage`
    - Fallback: `.lh-gauge__percentage`
    - Custom: Add new selector based on current UI

#### Analysis Timeout (30 seconds)
- **Symptom**: "Analysis timeout after 30 seconds"
- **Cause**: Target website takes too long to analyze or PSI is overloaded
- **Solution**:
  - This is the PageSpeed Insights internal timeout (not configurable)
  - Increase overall tool timeout to allow retries: `--timeout 1200`
  - The tool will retry with exponential backoff
  - Check if target URL is accessible and responding quickly
  - Test manually at https://pagespeed.web.dev to confirm PSI can analyze the URL

#### Button Click Failed
- **Symptom**: Click on Mobile/Desktop button has no effect
- **Cause**: Page JavaScript not fully loaded or element not interactive
- **Solution**:
  - Tool automatically retries with page reload (up to 3 attempts)
  - Enable debug mode for diagnostics: `--debug-mode`
  - Check for JavaScript errors in debug screenshots
  - Ensure stable internet connection

#### Debug Mode Usage
Enable comprehensive diagnostics:
```bash
python run_audit.py --tab "TAB_NAME" --debug-mode
```

Debug mode captures:
- Full-page PNG screenshots on errors
- Complete HTML source code
- List of all buttons, inputs, and links on the page
- Visibility status of all elements
- Files saved to `debug_screenshots/` with format: `YYYYMMDD_HHMMSS_sanitized-url_reason.{png|html}`

#### Manual Selector Testing
Use Playwright codegen for interactive testing:
```bash
playwright codegen https://pagespeed.web.dev
```
This opens a browser with an inspector to test and generate selector code.

## Dependencies

### Python (requirements.txt)
- `google-auth`: Authentication
- `google-auth-oauthlib`: OAuth2 flows
- `google-auth-httplib2`: HTTP transport
- `google-api-python-client`: Google Sheets API
- `python-dotenv`: Environment variables (optional)
- `redis`: Redis client for caching (optional, falls back to file cache)
- `plotly`: Interactive dashboard charts and visualizations
- `playwright`: Browser automation
- `argparse`: Command-line parsing (built-in)

## Security

### Credentials
- Service account credentials (`service-account.json`) must never be committed
- `.gitignore` excludes all `*service-account*.json` files
- Service accounts should have minimal permissions (only Sheets access needed)
- Spreadsheets should only be shared with necessary service accounts

### Security Features
See `SECURITY.md` for detailed documentation on:

1. **Service Account Validation**
   - Validates required fields in service account JSON
   - Checks private key format and email format
   - Automatic validation during authentication

2. **API Rate Limiting**
   - Per-spreadsheet rate limiting (60 req/min default)
   - Token bucket algorithm with burst tolerance
   - Prevents API quota exhaustion

3. **URL Filtering**
   - Whitelist support: `--whitelist "https://example.com/*"`
   - Blacklist support: `--blacklist "http://*"`
   - Pattern-based with wildcard support

4. **URL Sanitization**
   - Validates URL format before processing
   - Blocks dangerous characters
   - Normalizes protocols

5. **Audit Trail**
   - Logs all spreadsheet modifications
   - JSON Lines format with timestamps
   - Includes user, operation, location, and value
   - Query with `query_audit_trail.py`

6. **Dry Run Mode**
   - Simulate operations without changes: `--dry-run`
   - Test filters and validation
   - Review before execution

## Monitoring and Metrics

The system includes comprehensive monitoring:

### Metrics Collected
- **Success/Failure Rates**: Track audit success percentage and identify issues
- **Processing Time**: Monitor average time per URL analysis
- **API Quota Usage**: Count Sheets API and Playwright API calls to stay within limits
- **Cache Hit Ratio**: Measure cache efficiency (target >70%)
- **Failure Reasons**: Categorize failures (timeout, browser, permanent, etc.)
- **Alerting**: Automatic alerts when failure rate exceeds 20%

### Metrics Formats
- **Prometheus**: Text format compatible with Prometheus monitoring
- **JSON**: Structured data for dashboards and analysis
- **HTML Dashboard**: Interactive charts using Plotly

### Usage
```bash
# Run audit (metrics collected automatically)
python run_audit.py --tab "Your Tab"

# Generate interactive dashboard
python generate_report.py

# View metrics
cat metrics.json | python -m json.tool
cat metrics.prom
```

For detailed metrics documentation, see `METRICS_GUIDE.md` and `METRICS_QUICK_REFERENCE.md`.

## Limitations

- Rate limits: Google Sheets API has quotas (100 requests per 100 seconds per user)
- PageSpeed Insights may rate-limit high-volume usage
- Playwright requires browser binaries to be installed via `playwright install chromium`
- Windows encoding issues are mitigated but may still occur with exotic characters
- URLs must be in column A starting at row 2
- Results always written to columns F and G (not configurable via CLI)
- Dashboard requires plotly library for chart generation
