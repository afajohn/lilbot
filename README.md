# PageSpeed Insights Audit Tool

Automated tool for running PageSpeed Insights audits on URLs from Google Sheets and writing results back to the spreadsheet.

## 📚 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes
- **[INSTALL.md](INSTALL.md)** - Detailed installation guide
- **[README.md](README.md)** - Full documentation (this file)
- **[AGENTS.md](AGENTS.md)** - Developer guide
- **[CACHE_GUIDE.md](CACHE_GUIDE.md)** - Caching configuration and usage
- **[PERFORMANCE_OPTIMIZATIONS.md](PERFORMANCE_OPTIMIZATIONS.md)** - Performance improvements and benchmarks
- **[SECURITY.md](SECURITY.md)** - Security hardening features (detailed)
- **[SECURITY_QUICK_REFERENCE.md](SECURITY_QUICK_REFERENCE.md)** - Security quick reference guide
- **[VALIDATION.md](VALIDATION.md)** - Input validation and data quality guide

## Overview

This tool reads URLs from a Google Spreadsheet, analyzes each URL using PageSpeed Insights (via Playwright automation), and writes PageSpeed report URLs back to the spreadsheet for URLs with scores below 80.

### ⚡ Performance Optimizations (v2.0)

**Processing Speed Improved by ~40%**:
- Reduced default timeout from 900s to 600s
- Optimized Playwright wait times (from 5-15s to 2s between actions)
- Reduced retry attempts (Playwright: 5→2, Python: 10→3)
- Incremental spreadsheet updates (see results immediately, not after all URLs complete)
- Explicit headless mode execution
- Instance pooling for browser context reuse

**Key Features:**
- ✅ Batch process URLs from Google Sheets
- ✅ Automated PageSpeed Insights analysis via Playwright
- ✅ **Result caching with Redis/file backend (24-hour TTL)**
- ✅ Real-time progress tracking with incremental spreadsheet updates
- ✅ Automatic retry on transient failures
- ✅ Comprehensive logging
- ✅ Windows Unicode encoding fix
- ✅ Optimized for faster processing (~10 minutes per URL instead of 15+)
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
| `--concurrency` | No | `3` | Number of concurrent workers (1-5) |
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

**Use multiple concurrent workers:**
```bash
python run_audit.py --tab "Website 1" --concurrency 5
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

**Cause**: Browser instance consumed too much memory (>1GB) or experienced failures.

**Solution**:
- The tool automatically monitors memory and restarts browser contexts
- This is expected behavior and should resolve automatically
- If persistent, try reducing `--concurrency` to limit parallel browsers

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

### Permission denied when writing to spreadsheet

**Cause**: Service account doesn't have Editor permissions.

**Solution**:
- Open the spreadsheet
- Click Share
- Find the service account email
- Change permission to "Editor"

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

## Limitations

- Requires active internet connection
- PageSpeed Insights rate limits may apply for high-volume usage
- Analysis time depends on website complexity and server response time (typically 5-10 minutes per URL after optimizations)
- Browser automation depends on PageSpeed Insights UI structure (may need updates if Google changes their interface)
- URLs must start from row 2 (row 1 is treated as header)

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review the logs in the `logs/` directory
3. Verify all setup steps were completed correctly
4. Ensure URLs in the spreadsheet are valid and accessible

## License

(Add your license information here)
