# PageSpeed Insights Audit Tool

Automated tool for running PageSpeed Insights audits on URLs from Google Sheets and writing results back to the spreadsheet.

## 📚 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes
- **[INSTALL.md](INSTALL.md)** - Detailed installation guide
- **[README.md](README.md)** - Full documentation (this file)
- **[AGENTS.md](AGENTS.md)** - Developer guide (includes threading architecture, async Playwright explanation, greenlet error troubleshooting)
- **[CACHE_GUIDE.md](CACHE_GUIDE.md)** - Caching configuration and usage
- **[PERFORMANCE_OPTIMIZATIONS.md](PERFORMANCE_OPTIMIZATIONS.md)** - Performance improvements and benchmarks
- **[SECURITY.md](SECURITY.md)** - Security hardening features (detailed)
- **[SECURITY_QUICK_REFERENCE.md](SECURITY_QUICK_REFERENCE.md)** - Security quick reference guide
- **[VALIDATION.md](VALIDATION.md)** - Input validation and data quality guide

**Key Topics in This File:**
- [Skip Logic](#skip-logic) - When URLs are skipped vs re-analyzed
- [Cell Value Examples](#cell-value-examples) - Expected spreadsheet cell values for all scenarios
- [Threading Architecture](#threading-architecture) - Why async Playwright is used and how threading works
- [Troubleshooting Greenlet Errors](#error-greenlet-error-cannot-switch-to-a-different-thread) - Complete guide to debugging threading issues

## Overview

This tool reads URLs from a Google Spreadsheet, analyzes each URL using PageSpeed Insights (via Playwright automation), and writes PageSpeed report URLs back to the spreadsheet for URLs with scores below 80.

### ⚡ Performance Characteristics

**Parallel Processing for Maximum Throughput (Default)**:
- URLs processed concurrently using worker pool (default: 5 workers)
- Each worker has dedicated browser instance and event loop thread
- **~2-3 minutes per URL** with parallel processing (5 workers)
- **20-30 URLs per hour** with default 5 workers
- **Up to 400 URLs per hour** with 10-15 workers on high-performance systems
- Configurable concurrency: `--concurrency 1` (sequential) to `--concurrency 20+` (highly parallel)
- 20-30x faster than sequential mode with proper resource allocation

**Sequential Processing Mode (--concurrency 1)**:
- URLs processed one at a time for maximum reliability
- Predictable execution flow and easy to debug
- No threading issues, race conditions, or resource contention
- Expected: ~10-15 minutes per URL, 4-6 URLs per hour
- Ideal for memory-constrained systems (4-8GB RAM)

**Core Optimizations**:
- Reduced default timeout from 900s to 600s
- Optimized Playwright wait times (from 5-15s to 2s between actions)
- Reduced retry attempts for faster failure recovery
- Incremental spreadsheet updates (see results immediately)
- Explicit headless mode execution
- Browser instance refresh to prevent memory leaks
- Configurable delays between URLs for rate limiting
- Result caching with 24-hour TTL (Redis/file backend)

**Key Features:**
- ✅ Batch process URLs from Google Sheets
- ✅ Automated PageSpeed Insights analysis via Playwright
- ✅ **Parallel processing with worker pool (5 workers default, up to 20+)**
- ✅ **Result caching with Redis/file backend (24-hour TTL)**
- ✅ **~2-3 min/URL, up to 400 URLs/hour with parallel mode**
- ✅ Real-time progress tracking with incremental spreadsheet updates
- ✅ Automatic retry on transient failures
- ✅ Comprehensive logging
- ✅ Windows Unicode encoding fix
- ✅ Multi-sheet processing with batch verification
- ✅ Configurable browser refresh interval to prevent memory leaks
- ✅ Optional delays between URLs for rate limiting
- ✅ **Security hardening: service account validation, rate limiting, URL filtering, audit trail**
- ✅ **Dry run mode for safe testing**

## Prerequisites

- **Python 3.7+** - Download from [python.org](https://www.python.org/downloads/)
- **Google Cloud service account** with Sheets API access

## Setup Instructions

### 1. Install Python Dependencies

Open a terminal/command prompt in the project directory and run:

```bash
pip install -r requirements.txt
```

This installs:
- `google-auth` - Google authentication library
- `google-auth-oauthlib` - OAuth2 support
- `google-auth-httplib2` - HTTP transport for Google APIs
- `google-api-python-client` - Google Sheets API client
- `playwright` - Browser automation library

### 2. Install Playwright Browsers

After installing Python dependencies, install the Playwright browsers:

```bash
playwright install chromium
```

This downloads the Chromium browser required for automated PageSpeed Insights analysis.

### 3. Google Cloud Service Account Setup

#### Create a Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select or create a project
3. Navigate to **IAM & Admin** > **Service Accounts**
4. Click **Create Service Account**
5. Enter a name (e.g., "pagespeed-audit") and click **Create**
6. Skip the optional role assignment steps (click **Continue**, then **Done**)

#### Generate Service Account Key

1. Click on the newly created service account
2. Go to the **Keys** tab
3. Click **Add Key** > **Create new key**
4. Select **JSON** format
5. Click **Create** - the key file will download automatically
6. **Save the file as `service-account.json`** in the project root directory

#### Enable Google Sheets API

1. In Google Cloud Console, go to **APIs & Services** > **Library**
2. Search for "Google Sheets API"
3. Click on it and click **Enable**

#### Share Spreadsheet with Service Account

1. Open the `service-account.json` file
2. Copy the `client_email` value (looks like `your-service-account@project-id.iam.gserviceaccount.com`)
3. Open your Google Spreadsheet
4. Click **Share**
5. Paste the service account email
6. Give it **Editor** permissions
7. Uncheck "Notify people" and click **Share**

**Tip**: You can also get the service account email by running:
```bash
python get_service_account_email.py
```

## Usage

### Basic Usage

```bash
python run_audit.py --tab "Barranquilla Singles" --service-account "service-account.json"
```

### Command-Line Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--tab` | Yes | - | Name of the spreadsheet tab to read URLs from |
| `--spreadsheet-id` | No | `1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I` | Google Spreadsheet ID |
| `--service-account` | No | `service-account.json` | Path to service account JSON file |
| `--timeout` | No | `600` | Timeout in seconds for each URL analysis (recommend 900-1200 for production) |
| `--concurrency` | No | `5` | Number of parallel workers (1-20+, higher = faster but more memory) |
| `--fast-mode` | No | `False` | Enable fast mode with aggressive timeouts (90s) |
| `--sheets` | No | - | Process multiple sheets (comma-separated names or "all") |
| `--start-row` | No | `2` | Row number to start reading URLs from |
| `--verify-batch-size` | No | `100` | Batch size for verification (50-200) |
| `--auto-continue` | No | `False` | Skip confirmation prompts during verification and multi-sheet processing |
| `--refresh-interval` | No | `10` | Browser refresh interval (number of URLs before restarting browser) |
| `--url-delay` | No | `0` | Delay in seconds between processing each URL (for rate limiting) |
| `--skip-cache` | No | `False` | Skip cache and force fresh analysis |
| `--whitelist` | No | - | URL whitelist patterns (space-separated) |
| `--blacklist` | No | - | URL blacklist patterns (space-separated) |
| `--dry-run` | No | `False` | Simulate operations without making changes |
| `--validate-only` | No | `False` | Run validation checks without audit execution |
| `--skip-dns-validation` | No | `False` | Skip DNS resolution validation |
| `--skip-redirect-validation` | No | `False` | Skip redirect chain validation |
| `--dns-timeout` | No | `5.0` | DNS resolution timeout in seconds |
| `--redirect-timeout` | No | `10.0` | Redirect check timeout in seconds |

### Examples

**Analyze URLs from a specific tab:**
```bash
python run_audit.py --tab "Barranquilla Singles"
```

**Use a different spreadsheet:**
```bash
python run_audit.py --tab "Production Sites" --spreadsheet-id "abc123xyz"
```

**Use a custom service account file location:**
```bash
python run_audit.py --tab "Website 1" --service-account "C:\path\to\credentials.json"
```

**Increase timeout for slow-loading sites:**
```bash
# Recommended for most production use (15 minutes)
python run_audit.py --tab "Website 1" --timeout 900

# For slow connections or complex sites (20 minutes)
python run_audit.py --tab "Website 1" --timeout 1200
```

**Skip cache for fresh analysis:**
```bash
python run_audit.py --tab "Website 1" --skip-cache
```

**Configure parallel processing:**
```bash
# Use default parallel mode (5 workers)
python run_audit.py --tab "Website 1"

# High-performance parallel mode (10 workers, requires 16GB+ RAM)
python run_audit.py --tab "Website 1" --concurrency 10

# Sequential mode (1 worker, maximum reliability)
python run_audit.py --tab "Website 1" --concurrency 1

# Fast mode with high concurrency (maximum speed)
python run_audit.py --tab "Website 1" --fast-mode --concurrency 15
```

**Process multiple sheets:**
```bash
# Process specific sheets
python run_audit.py --sheets "Sheet1,Sheet2,Sheet3"

# Process all sheets in spreadsheet
python run_audit.py --sheets all

# Multi-sheet with auto-continue (no prompts)
python run_audit.py --sheets all --auto-continue --concurrency 10
```

**Configure browser refresh and URL delay:**
```bash
# Refresh browser every 5 URLs (good for memory-constrained systems)
python run_audit.py --tab "Website 1" --refresh-interval 5

# Add 2-second delay between URLs (for rate limiting)
python run_audit.py --tab "Website 1" --url-delay 2

# Combined: aggressive refresh and delay
python run_audit.py --tab "Website 1" --refresh-interval 5 --url-delay 1
```

**Batch verification:**
```bash
# Verify in batches of 100 URLs
python run_audit.py --tab "Website 1" --verify-batch-size 100

# Auto-continue without prompts
python run_audit.py --tab "Website 1" --auto-continue

# Start from specific row
python run_audit.py --tab "Website 1" --start-row 500
```

**Filter URLs with whitelist/blacklist:**
```bash
python run_audit.py --tab "Website 1" --whitelist "https://example.com/*" --blacklist "http://*"
```

**Dry run (simulate without changes):**
```bash
python run_audit.py --tab "Website 1" --dry-run
```

### List Available Tabs

To see all available tabs in your spreadsheet:
```bash
python list_tabs.py --spreadsheet-id "YOUR_SPREADSHEET_ID" --service-account "service-account.json"
```

### Cache Management

The tool caches PageSpeed Insights results for 24 hours to improve performance:

**Invalidate cache for a specific URL:**
```bash
python invalidate_cache.py --url "https://example.com"
```

**Clear all cached results:**
```bash
python invalidate_cache.py --all
```

**Note**: By default, the tool uses a file-based cache in `.cache/` directory. For production use with Redis, see [CACHE_GUIDE.md](CACHE_GUIDE.md).

### Security Features

**Validate service account:**
```bash
python validate_service_account.py service-account.json
```

**Query audit trail:**
```bash
# View all modifications
python query_audit_trail.py

# Filter by date and tab
python query_audit_trail.py --tab "Website 1" --start-date "2024-01-01" --format detailed
```

**For complete security documentation, see [SECURITY.md](SECURITY.md)**.

## Google Sheets Format

### Required Column Structure

The tool expects your spreadsheet to have the following structure:

| Column | Purpose | Access | Notes |
|--------|---------|--------|-------|
| **A** | URLs to analyze | **Read** | Starting from row 2 (A2:A) |
| **F** | Mobile PageSpeed Insights URLs | **Write** | Only for scores < 80 |
| **G** | Desktop PageSpeed Insights URLs | **Write** | Only for scores < 80 |

### Example Spreadsheet Layout

```
| A (URL)                         | B    | C    | D    | E    | F (Mobile PSI)     | G (Desktop PSI)    |
|---------------------------------|------|------|------|------|--------------------|--------------------|
| URL                             |      |      |      |      |                    |                    | <- Row 1 (Header - Skipped)
| https://example.com             |      |      |      |      | [PSI URL if < 80]  | [PSI URL if < 80]  | <- Row 2 (First URL)
| https://example.com/about       |      |      |      |      | [PSI URL if < 80]  | [PSI URL if < 80]  | <- Row 3
| https://example.com/contact     |      |      |      |      | [PSI URL if < 80]  | [PSI URL if < 80]  | <- Row 4
```

**Important Notes:**
- **Row 1 is treated as a header and is skipped** - the tool reads from A2:A onwards
- Column A must contain valid URLs starting with `http://` or `https://`
- Empty cells in column A are automatically skipped
- Columns F and G are only populated when scores are below 80 (threshold configurable in code)
- The tool preserves the exact row numbers when writing PSI URLs

## How It Works

### Workflow Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    1. AUTHENTICATION                         │
│  Authenticate with Google Sheets using service account      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    2. READ URLS                              │
│  Read all URLs from column A (starting at A2)               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    3. ANALYZE EACH URL                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ a) Check cache for existing results                  │  │
│  │ b) If cache miss: Launch Chromium browser            │  │
│  │ c) Navigate to https://pagespeed.web.dev             │  │
│  │ d) Enter URL and start analysis                      │  │
│  │ e) Wait up to 30 seconds for analysis to complete    │  │
│  │ f) Wait for Mobile/Desktop toggle buttons to appear  │  │
│  │ g) Click "Mobile" button and extract score           │  │
│  │ h) Click "Desktop" button and extract score          │  │
│  │ i) Capture PSI URLs for scores < 80                  │  │
│  │ j) Cache results for 24 hours                        │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    4. UPDATE SPREADSHEET                     │
│  Immediately write results after each URL:                  │
│  • Column F: "passed" (if score ≥ 80) OR PSI URL (< 80)    │
│  • Column G: "passed" (if score ≥ 80) OR PSI URL (< 80)    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    5. SUMMARY                                │
│  Display audit summary with pass/fail statistics            │
└─────────────────────────────────────────────────────────────┘
```

### Detailed PageSpeed Insights Automation

The tool automates PageSpeed Insights analysis using Playwright with the following sequence:

1. **Launch Browser**: Chromium browser launched in headless mode
2. **Navigate**: Opens https://pagespeed.web.dev
3. **Enter URL**: Inputs the target URL into the analysis field
4. **Start Analysis**: Clicks the "Analyze" button
5. **Wait for Results**: Waits up to 30 seconds for the analysis to complete
6. **Extract Mobile Score**:
   - Waits for Mobile/Desktop toggle buttons to appear
   - Clicks the "Mobile" button (if not already selected)
   - Extracts score from `.lh-exp-gauge__percentage` selector
   - Captures the PageSpeed Insights URL for the mobile report
7. **Extract Desktop Score**:
   - Clicks the "Desktop" button to switch views
   - Extracts score from `.lh-exp-gauge__percentage` selector
   - Captures the PageSpeed Insights URL for the desktop report
8. **Return Results**: Returns scores and URLs to the audit processor

### Spreadsheet Output Logic

After analyzing each URL, the tool writes results to columns F and G:

**For scores ≥ 80 (passing):**
- Column F (Mobile): Cell contains the text `"passed"`
- Column G (Desktop): Cell contains the text `"passed"`

**For scores < 80 (failing):**
- Column F (Mobile): Full PageSpeed Insights URL (e.g., `https://pagespeed.web.dev/analysis?url=https://example.com`)
- Column G (Desktop): Full PageSpeed Insights URL with desktop parameter

**Examples of cell values:**

| Score | Column F (Mobile) | Column G (Desktop) |
|-------|-------------------|-------------------|
| Mobile: 92, Desktop: 95 | `passed` | `passed` |
| Mobile: 65, Desktop: 85 | `https://pagespeed.web.dev/analysis?url=https://example.com` | `passed` |
| Mobile: 82, Desktop: 72 | `passed` | `https://pagespeed.web.dev/analysis?url=https://example.com` |
| Mobile: 65, Desktop: 70 | `https://pagespeed.web.dev/analysis?url=https://example.com` | `https://pagespeed.web.dev/analysis?url=https://example.com` |

## Output

The tool provides real-time progress updates and logs to both console and a log file:

```
Logging to file: logs\audit_20260202_163038.log
Authenticating with Google Sheets...
Authentication successful
Reading URLs from spreadsheet tab 'Barranquilla Singles'...
Successfully read URLs from spreadsheet
Found 251 URLs to analyze.

[1/251] Analyzing https://barranquillasingles.com...
  Mobile: 92 (PASS)
  Desktop: 95 (PASS)
Successfully analyzed https://barranquillasingles.com

[2/251] Analyzing https://barranquillasingles.com/about...
  Mobile: 65 (FAIL)
  Desktop: 72 (FAIL)
Successfully analyzed https://barranquillasingles.com/about

...

Updating spreadsheet with 4 PSI URLs...
Spreadsheet updated successfully.

================================================================================
AUDIT SUMMARY
================================================================================
Total URLs analyzed: 251
Successful analyses: 250
Failed analyses: 1

Mobile scores >= 80: 180
Mobile scores < 80: 70
Desktop scores >= 80: 200
Desktop scores < 80: 50

PSI URLs for failing scores written to columns F (mobile) and G (desktop).
================================================================================
```

Logs are saved in the `logs/` directory with timestamps for future reference.

## Skip Logic

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

**Testing Skip Logic:**

```bash
# Validate skip logic with all scenarios
python validate_skip_logic.py

# Generate test spreadsheet with skip logic examples
python generate_test_spreadsheet_scenarios.py
```

## Cell Value Examples

**Expected cell values for different scenarios:**

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

## Threading Architecture

**Why Async Playwright with Parallel Workers?**

The system uses async Playwright with parallel workers for maximum throughput:

1. **Browser Automation is I/O-Bound**: Network requests, page loads, DOM queries are ideal for concurrent execution
2. **Parallel Worker Pool**: Multiple workers (default: 5) process URLs concurrently for 20-30x performance improvement
3. **Isolated Event Loops**: Each worker has its own event loop thread, preventing cross-thread conflicts
4. **Independent Browser Instances**: Each worker manages its own browser context independently
5. **Playwright Design**: The library is designed for async-first parallel execution

**Parallel Worker Pool Architecture:**

The system uses multiple worker threads for parallel processing:

- **Main Thread**: Handles application logic, distributes URLs to workers, collects results
- **Worker Pool**: Multiple worker threads (default: 5), each with its own event loop and browser instance
- **Worker Thread**: Each worker runs asyncio event loop for its own Playwright operations
- **Thread-Safe Communication**: Requests submitted via `concurrent.futures.ThreadPoolExecutor`
- **Synchronous Interface**: Main thread blocks on `Future` objects to collect results from workers

**Parallel Threading Flow:**

```
Main Thread                          Worker 1                Worker 2                Worker N
-----------                          --------                --------                --------
1. Submit URLs to pool               (Event loop running)    (Event loop running)    (Event loop running)
   submit(url1) -->                  
   submit(url2) -->                                          
   submit(url3) -->                                                                  
                                     Process url1            Process url2            Process url3
                                     - await page.goto()     - await page.goto()     - await page.goto()
                                     - await page.click()    - await page.click()    - await page.click()
2. Collect results                   
<-- Result 1
<-- Result 2
<-- Result 3
3. Update spreadsheet (batched)
4. Repeat with next batch
```

**Why This Prevents Greenlet Errors:**

Each worker's Playwright operations execute on that worker's dedicated thread, preventing "greenlet.error: cannot switch to a different thread" errors. Workers maintain strict thread isolation with independent event loops.

**Parallel vs Sequential Processing:**

- **Parallel Mode** (default: `--concurrency 5`): 20-30 URLs/hour, ideal for large audits
- **Sequential Mode** (`--concurrency 1`): 4-6 URLs/hour, maximum reliability for debugging
- **High-Performance Mode** (`--concurrency 10-15`): Up to 400 URLs/hour on high-memory systems

For detailed threading diagnostics, see the **Troubleshooting** section below.

## Troubleshooting

### Error: UnicodeDecodeError: 'charmap' codec can't decode byte

**Cause**: Windows encoding issue when running subprocess commands.

**Solution**: This has been fixed in the latest version. The code now explicitly uses UTF-8 encoding for subprocess operations.

### Error: Service account file not found

**Cause**: The `service-account.json` file doesn't exist at the specified path.

**Solution**:
- Ensure you've downloaded the service account key from Google Cloud Console
- Verify the file is named `service-account.json` and is in the project root
- Or use `--service-account` flag to specify the correct path

### Error: Failed to authenticate

**Cause**: Invalid service account credentials or incorrect permissions.

**Solution**:
- Verify the JSON file is valid and not corrupted
- Ensure Google Sheets API is enabled in your Google Cloud project
- Regenerate the service account key if necessary

### Error: Tab 'X' not found in spreadsheet

**Cause**: The tab name doesn't exist or is misspelled.

**Solution**:
- Run `python list_tabs.py` to see all available tabs
- Verify the tab name matches exactly (case-sensitive)
- Ensure the spreadsheet is shared with the service account email

### Error: Failed to read URLs

**Possible Causes**:
- Spreadsheet ID is incorrect
- Tab name doesn't exist or is misspelled
- Service account doesn't have access to the spreadsheet

**Solution**:
- Verify the spreadsheet ID (found in the URL: `https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit`)
- Check tab name matches exactly (case-sensitive)
- Ensure the spreadsheet is shared with the service account email with **Editor** permissions

### Error: Timeout - Playwright execution exceeded X seconds

**Cause**: The website took too long to load or PageSpeed Insights analysis timed out.

**Solution**:
- Increase timeout: `python run_audit.py --tab "Website 1" --timeout 900`
- For slow connections or complex websites, use `--timeout 1200` (20 minutes) or higher
- Check if the URL is accessible and loads properly
- Verify your internet connection is stable

**Recommended timeout values:**
- Fast connection, simple sites: 600 seconds (default)
- Average connection/sites: 900 seconds (15 minutes)
- Slow connection or complex sites: 1200 seconds (20 minutes)
- Very slow connections: 1800 seconds (30 minutes)

### Error: Playwright browser not found

**Cause**: Playwright browsers are not installed.

**Solution**:
```bash
playwright install chromium
```

If still not working, try reinstalling Playwright:
```bash
pip uninstall playwright
pip install playwright
playwright install chromium
```

### Error: Browser process failed to launch

**Possible Causes**:
- Missing system dependencies for browser
- Insufficient permissions
- Corrupted browser installation

**Solution (Linux)**:
```bash
# Install system dependencies
playwright install-deps chromium
```

**Solution (Windows/Mac)**:
```bash
# Reinstall browsers
playwright install chromium --force
```

### Error: Page crashed or browser context exceeded memory limit

**Cause**: Browser instance consumed too much memory (>1GB) or experienced failures during long-running audits.

**Solution**:
- The tool automatically monitors memory and refreshes the browser instance
- This is expected behavior and should resolve automatically
- If persistent, use more aggressive refresh: `--refresh-interval 5` or `--refresh-interval 3`
- For parallel mode, reduce concurrency: `--concurrency 3` (fewer workers = less memory)
- See the **Memory Issues and Browser Refresh** section below for detailed guidance

### Error: Workers not starting or hanging

**Cause**: Worker pool initialization failure, insufficient system resources, or threading issues.

**Solution**:
```bash
# Check worker pool status
python get_pool_stats.py

# Reduce concurrency to troubleshoot
python run_audit.py --tab "Website 1" --concurrency 1

# Enable debug mode to see worker activity
python run_audit.py --tab "Website 1" --debug-mode --concurrency 3

# Check threading diagnostics
python diagnose_playwright_threading.py
```

### Error: Rate limit exceeded

**Cause**: Too many concurrent requests to PageSpeed Insights or Google Sheets API with parallel processing.

**Solution**:
```bash
# Reduce concurrency to stay within rate limits
python run_audit.py --tab "Website 1" --concurrency 3

# Add delay between URL processing
python run_audit.py --tab "Website 1" --url-delay 2 --concurrency 5

# Use slower mode for API-sensitive scenarios
python run_audit.py --tab "Website 1" --concurrency 3 --url-delay 3
```

### PageSpeed Insights Selector Issues

**Common Issues and Solutions:**

#### 1. Error: Failed to find Mobile/Desktop toggle buttons

**Cause**: PageSpeed Insights UI changed, or buttons didn't appear after analysis.

**Solutions**:
- Wait longer for analysis to complete (buttons appear after results load)
- Increase timeout: `--timeout 900` or higher
- Enable debug mode to capture screenshots: `--debug-mode`
- Check debug screenshots in `debug_screenshots/` directory

#### 2. Error: Score extraction failed

**Cause**: Selector `.lh-exp-gauge__percentage` not found or page structure changed.

**Solutions**:
- Enable debug mode: `--debug-mode` to capture page HTML
- Check if PageSpeed Insights UI has been updated
- Update selectors in `tools/qa/playwright_runner.py` if needed
- Try manual navigation to confirm PSI is working: https://pagespeed.web.dev

#### 3. Error: Analysis timeout after 30 seconds

**Cause**: URL took too long to analyze or PageSpeed Insights is slow.

**Solutions**:
- This is the PageSpeed Insights analysis timeout (not the overall timeout)
- Increase overall timeout: `--timeout 1200` to allow multiple retries
- Check if the target website is accessible and responding
- Try analyzing the URL manually at https://pagespeed.web.dev

#### 4. Error: Button click failed or no response

**Cause**: Playwright couldn't interact with Mobile/Desktop toggle.

**Solutions**:
- Page may still be loading; increase `--timeout`
- Enable debug mode to see page state: `--debug-mode`
- Check for JavaScript errors on the PageSpeed Insights page
- The tool automatically retries with page reload (up to 3 attempts)

#### 5. Debugging Selector Issues

**Enable debug mode for detailed diagnostics:**
```bash
python run_audit.py --tab "Website 1" --debug-mode
```

This captures:
- Full-page screenshots on errors (saved to `debug_screenshots/`)
- Complete page HTML for inspection
- List of all visible buttons and elements
- Detailed error messages with page state

**Manual testing with Playwright:**
```bash
playwright codegen https://pagespeed.web.dev
```

This opens an interactive browser where you can test selectors and generate code.

### Error: greenlet.error: cannot switch to a different thread

**What is a Greenlet Error?**

Greenlet is a lightweight cooperative threading library used internally by Playwright's async implementation. This error occurs when Playwright tries to switch execution context between threads, which violates the single-thread requirement for asyncio event loops.

**Cause**: Playwright operations are being executed from different threads instead of the dedicated event loop thread.

**How the System Prevents This:**

The system uses a dedicated event loop thread architecture where:
1. All Playwright operations run on a single dedicated thread
2. Main thread submits requests via `asyncio.run_coroutine_threadsafe()`
3. All browser contexts and pages are created within the event loop thread

**If You Encounter Greenlet Errors:**

1. **Check Threading Diagnostics**:
   ```bash
   python diagnose_playwright_threading.py
   ```
   Look for:
   - `greenlet_errors` count in metrics
   - Multiple thread IDs in `context_creation_by_thread` or `page_creation_by_thread`
   - Event loop health status showing unresponsive (>30s since last heartbeat)

2. **Enable Debug Logging**:
   ```bash
   python run_audit.py --tab "TAB_NAME" --debug-mode
   ```
   This shows thread IDs for all Playwright operations. All should have the same thread ID (the event loop thread).

3. **Common Fixes**:
   - **Restart the application**: Event loop may be corrupted
   - **System uses sequential processing**: No concurrent execution, should not have threading issues
   - **Check event loop health**: Verify event loop thread is responsive
   - **Review custom modifications**: Ensure you haven't added code that calls Playwright from wrong thread

4. **Verify Single Thread Execution**:
   - All Playwright operations should log the same thread ID
   - Main thread should have a different thread ID
   - Check diagnostics output for thread conflicts

**Example Error:**
```
greenlet.error: cannot switch to a different thread

Stack trace pattern:
File "playwright/_impl/_browser_context.py", line X, in new_page
File "greenlet/__init__.py", line Y, in switch
greenlet.error: cannot switch to a different thread
```

**Prevention Best Practices:**
- System uses sequential processing (no concurrent execution)
- Always use the provided `run_analysis()` function which handles threading correctly
- Don't modify Playwright code to use sync APIs
- Keep all browser context and page creation within the event loop thread
- Never call Playwright operations from custom threads

**Diagnostic Tools:**

```bash
# Full diagnostics with all metrics
python diagnose_playwright_threading.py

# Export diagnostics to JSON for analysis
python diagnose_playwright_threading.py --json diagnostics.json

# View only specific components
python diagnose_playwright_threading.py --metrics-only
python diagnose_playwright_threading.py --health-only
python diagnose_playwright_threading.py --pool-only
```

### Permission denied when writing to spreadsheet

**Cause**: Service account doesn't have Editor permissions.

**Solution**:
- Open the spreadsheet
- Click Share
- Find the service account email
- Change permission to "Editor"

### Memory Issues and Browser Refresh

**Symptoms of Memory Issues:**

Browser memory leaks can manifest as:
- Browser process memory steadily increasing over time
- Analysis becoming slower after processing many URLs
- Browser crashes with "Out of memory" errors
- System becoming unresponsive during long audits
- Error messages about memory limits exceeded

**Browser Refresh Strategy:**

The tool automatically refreshes the browser instance every N URLs to prevent memory leaks:

```bash
# Default: refresh every 10 URLs
python run_audit.py --tab "TAB_NAME"

# For memory-constrained systems (4GB RAM or less): refresh every 3 URLs
python run_audit.py --tab "TAB_NAME" --refresh-interval 3

# For medium memory systems (8GB RAM): refresh every 5 URLs
python run_audit.py --tab "TAB_NAME" --refresh-interval 5

# For high memory systems (16GB+ RAM): use default or increase to 20
python run_audit.py --tab "TAB_NAME" --refresh-interval 20

# Disable auto-refresh (NOT RECOMMENDED for audits >20 URLs)
python run_audit.py --tab "TAB_NAME" --refresh-interval 0
```

**How Refresh Works:**
- Browser instance is cleanly shut down after N analyses
- New browser instance created for next URL
- Memory is released back to operating system
- No impact on audit results or accuracy
- Minimal performance impact (1-2 seconds per refresh)

**Memory Threshold Auto-Refresh:**

In addition to interval-based refresh, the system automatically refreshes when:
- Browser memory usage exceeds 1GB
- Logged as "Memory threshold exceeded" in debug output
- Happens regardless of `--refresh-interval` setting

**System Requirements:**

| System Memory | Recommended Refresh Interval | Notes |
|--------------|------------------------------|-------|
| 4GB RAM | `--refresh-interval 3` | Aggressive refresh for limited memory |
| 8GB RAM | `--refresh-interval 5-10` | Balanced performance and reliability |
| 16GB+ RAM | `--refresh-interval 10-20` | Default or higher for best performance |

**Long-Running Audit Best Practices (200+ URLs):**
- Use `--refresh-interval 5` or lower
- Enable debug mode to monitor: `--debug-mode`
- Run during off-hours to avoid resource competition
- Monitor system memory during first few URLs
- Consider splitting into smaller batches if system struggles

**Emergency Memory Recovery:**

If the system becomes unresponsive:
1. Stop the audit (Ctrl+C)
2. Kill remaining browser processes:
   - Windows: `taskkill /F /IM chromium.exe`
   - Linux/Mac: `pkill chromium`
3. Wait 30 seconds for memory to be released
4. Resume audit with lower `--refresh-interval`

**Monitoring Memory Usage:**

```bash
# Windows (PowerShell)
Get-Process python | Select-Object WorkingSet64

# Linux/Mac
ps aux | grep -E 'python|chromium'

# Check browser memory via tool
python get_pool_stats.py
```

## Configuration

### Modifying Score Threshold

The default threshold for "failing" scores is 80. To change it, edit `run_audit.py`:

```python
SCORE_THRESHOLD = 80  # Change this value (e.g., 70, 90)
```

### Changing Column Mappings

To write PSI URLs to different columns, edit `run_audit.py`:

```python
MOBILE_COLUMN = 'F'   # Change to desired column letter
DESKTOP_COLUMN = 'G'  # Change to desired column letter
```

### Adjusting Playwright Settings

Modify `tools/qa/playwright_runner.py` to change:
- Timeouts
- Retry attempts
- Viewport size
- Headless mode
- Browser context settings

## Project Structure

```
.
├── run_audit.py                 # Main entry point
├── list_tabs.py                 # Utility to list spreadsheet tabs
├── get_service_account_email.py # Utility to get service account email
├── validate_service_account.py  # Service account validator
├── query_audit_trail.py         # Audit trail query utility
├── requirements.txt             # Python dependencies
├── service-account.json         # Google Cloud credentials (not in repo)
├── audit_trail.jsonl            # Audit trail log (gitignored)
├── README.md                    # This file
├── SECURITY.md                  # Security documentation
├── tools/
│   ├── sheets/
│   │   └── sheets_client.py    # Google Sheets API wrapper
│   ├── qa/
│   │   └── playwright_runner.py # Playwright automation wrapper
│   ├── security/
│   │   ├── service_account_validator.py  # Service account validation
│   │   ├── url_filter.py       # URL filtering (whitelist/blacklist)
│   │   ├── audit_trail.py      # Audit trail logging
│   │   └── rate_limiter.py     # Per-spreadsheet rate limiting
│   ├── cache/
│   │   └── cache_manager.py    # Cache management
│   ├── metrics/
│   │   └── metrics_collector.py # Metrics collection
│   └── utils/
│       ├── logger.py            # Logging utilities
│       └── url_validator.py    # URL validation
└── logs/                        # Audit logs (gitignored)
```

## Advanced Tips

### Batch Processing Multiple Tabs

**Windows (PowerShell):**
```powershell
$tabs = @("Barranquilla Singles", "Website 2", "Website 3")
foreach ($tab in $tabs) {
    Write-Host "Processing tab: $tab"
    python run_audit.py --tab $tab --service-account "service-account.json"
}
```

**Linux/Mac (Bash):**
```bash
#!/bin/bash
tabs=("Barranquilla Singles" "Website 2" "Website 3")
for tab in "${tabs[@]}"; do
    echo "Processing tab: $tab"
    python run_audit.py --tab "$tab" --service-account "service-account.json"
done
```

### Schedule Regular Audits

**Windows (Task Scheduler):**
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., weekly on Monday at 9 AM)
4. Action: Start a program
5. Program: `python.exe`
6. Arguments: `run_audit.py --tab "Barranquilla Singles"`
7. Start in: Project directory path

**Linux/Mac (cron):**
```bash
# Run every Monday at 9 AM
0 9 * * 1 cd /path/to/project && python run_audit.py --tab "Production Sites"
```

## Quick Start Guide

1. **Install Python 3.7+** (if not already installed)
   - Python: [python.org/downloads](https://www.python.org/downloads/)

2. **Clone/download this project**

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Set up Google Cloud service account:**
   - Create service account at [console.cloud.google.com](https://console.cloud.google.com/)
   - Download JSON key and save as `service-account.json` in the project root
   - Enable Google Sheets API
   - Share spreadsheet with service account email (found in the JSON file)

5. **Verify setup (optional but recommended):**
   ```bash
   python validate_setup.py
   ```

6. **Run the audit:**
   ```bash
   python run_audit.py --tab "Barranquilla Singles" --service-account "service-account.json"
   ```

## Performance Scaling Examples

**Sequential Mode (--concurrency 1):**
- 100 URLs: ~16-25 hours
- 500 URLs: ~80-125 hours
- 1000 URLs: ~160-250 hours

**Parallel Mode (--concurrency 5, default):**
- 100 URLs: ~5-8 hours
- 500 URLs: ~25-40 hours
- 1000 URLs: ~50-80 hours

**High-Performance Parallel Mode (--concurrency 10):**
- 100 URLs: ~2.5-5 hours
- 500 URLs: ~12.5-25 hours
- 1000 URLs: ~25-50 hours

**Maximum Throughput (--concurrency 15-20):**
- 100 URLs: ~1.5-3 hours
- 500 URLs: ~7.5-15 hours
- 1000 URLs: ~15-30 hours

Note: Actual performance depends on system resources, network speed, and target site complexity.

## System Requirements for Parallel Processing

| Concurrency Level | Minimum RAM | Recommended RAM | CPU Cores |
|------------------|-------------|-----------------|-----------|
| 1-3 workers      | 4GB         | 8GB             | 2+        |
| 4-7 workers      | 8GB         | 16GB            | 4+        |
| 8-12 workers     | 16GB        | 32GB            | 8+        |
| 13-20 workers    | 32GB        | 64GB            | 16+       |

**Recommended Starting Points:**
- **4GB RAM, 2 cores**: `--concurrency 2`
- **8GB RAM, 4 cores**: `--concurrency 3-5` (default)
- **16GB RAM, 8 cores**: `--concurrency 8-10`
- **32GB+ RAM, 16+ cores**: `--concurrency 15-20`

## Limitations

- **Parallel Processing Overhead**: Worker pool requires 16GB+ RAM for 10+ workers
- **Performance**: ~2-3 minutes per URL (parallel mode), 4-6 URLs per hour (sequential mode)
- **Internet Connection**: Requires active internet connection
- **PageSpeed Insights**: May rate-limit high-volume usage (reduce concurrency if encountered)
- **Memory**: Parallel processing requires more memory; use `--refresh-interval` to manage
- **Browser Automation**: Depends on PageSpeed Insights UI structure (may need updates if Google changes their interface)
- **URLs**: Must be in column A starting from row 2 (row 1 is treated as header)
- **Results**: Always written to columns F and G (not configurable via CLI)
- **Concurrency**: Maximum practical concurrency depends on system resources (typically 15-20 workers)

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review the logs in the `logs/` directory
3. Verify all setup steps were completed correctly
4. Ensure URLs in the spreadsheet are valid and accessible

## License

(Add your license information here)
