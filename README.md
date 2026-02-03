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

This tool reads URLs from a Google Spreadsheet, analyzes each URL using PageSpeed Insights (via Cypress automation), and writes PageSpeed report URLs back to the spreadsheet for URLs with scores below 80.

### ⚡ Performance Optimizations (v2.0)

**Processing Speed Improved by ~40%**:
- Reduced default timeout from 900s to 600s
- Optimized Cypress wait times (from 5-15s to 2s between actions)
- Reduced retry attempts (Cypress: 5→2, Python: 10→3)
- Incremental spreadsheet updates (see results immediately, not after all URLs complete)
- Explicit headless mode execution

**Critical Fix**: Running `npx cypress open` while the audit script is running will block execution. Always close Cypress UI before starting audits.

**Key Features:**
- ✅ Batch process URLs from Google Sheets
- ✅ Automated PageSpeed Insights analysis via Cypress
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
- **Node.js 14+ and npm** - Download from [nodejs.org](https://nodejs.org/)
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

### 2. Install Node.js Dependencies

In the same terminal, run:

```bash
npm install
```

This installs Cypress for browser automation and related dependencies.

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
| `--timeout` | No | `600` | Timeout in seconds for each URL analysis |
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
python run_audit.py --tab "Website 1" --timeout 900
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

1. **Authentication**: Authenticates with Google Sheets using the service account credentials
2. **Read URLs**: Reads all URLs from column A (starting at row 2, i.e., A2:A) of the specified tab
3. **Analysis**: For each URL:
   - Launches Cypress in headless mode to automate PageSpeed Insights
   - Navigates to pagespeed.web.dev
   - Analyzes the URL (both mobile and desktop results are available from single analysis)
   - Switches between Mobile/Desktop views to extract performance scores (0-100)
   - Captures report URLs for failing scores (< 80)
4. **Write Results**: Immediately updates the spreadsheet after each URL:
   - Mobile PSI URLs → Column F (only if score < 80, otherwise "passed")
   - Desktop PSI URLs → Column G (only if score < 80, otherwise "passed")
   - Updates are incremental (not batched), so progress is visible in real-time
5. **Summary**: Displays audit summary with pass/fail statistics

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

### Error: Timeout - Cypress execution exceeded X seconds

**Cause**: The website took too long to load or PageSpeed Insights analysis timed out.

**Solution**:
- Increase timeout: `python run_audit.py --tab "Website 1" --timeout 900`
- Check if the URL is accessible and loads properly
- Verify your internet connection is stable

### Issue: URLs taking too long to process or no spreadsheet updates

**Cause**: Running `npx cypress open` while `run_audit.py` is executing blocks the headless Cypress instance.

**Solution**:
- **Close the Cypress UI** (`npx cypress open`) before running `run_audit.py`
- Only one Cypress instance can run at a time
- The audit script runs Cypress in headless mode automatically
- With optimizations, each URL should complete in ~5-10 minutes (down from 15+ minutes)

### Error: npx or Cypress not found

**Cause**: Node.js or Cypress is not installed.

**Solution**:
```bash
npm install
```

If still not working, try:
```bash
npm install -g npm
npm install
```

### Error: No new results file found

**Cause**: Cypress ran but didn't generate a results file.

**Solution**:
- Check if `cypress/results/` directory exists
- Review Cypress logs for errors
- Verify the URL is accessible
- Try running manually: `npx cypress open` and check the test

### Cypress test fails with "Cypress failed with exit code 1"

**Possible Causes**:
- PageSpeed Insights website structure may have changed
- Network connectivity issues
- The URL is not accessible or returns an error

**Solution**:
- Check the detailed error output in the console
- Verify the URL is accessible in your browser
- Try running Cypress in headed mode for debugging: `npx cypress open`
- Check `cypress/e2e/analyze-url.cy.js` for outdated selectors if PageSpeed Insights UI has changed

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

### Adjusting Cypress Settings

Modify `cypress.config.js` to change:
- Timeouts
- Retry attempts
- Viewport size
- Video recording
- Screenshot settings

## Project Structure

```
.
├── run_audit.py                 # Main entry point
├── list_tabs.py                 # Utility to list spreadsheet tabs
├── get_service_account_email.py # Utility to get service account email
├── validate_service_account.py  # Service account validator
├── query_audit_trail.py         # Audit trail query utility
├── requirements.txt             # Python dependencies
├── package.json                 # Node.js dependencies
├── cypress.config.js            # Cypress configuration
├── service-account.json         # Google Cloud credentials (not in repo)
├── audit_trail.jsonl            # Audit trail log (gitignored)
├── README.md                    # This file
├── SECURITY.md                  # Security documentation
├── tools/
│   ├── sheets/
│   │   └── sheets_client.py    # Google Sheets API wrapper
│   ├── qa/
│   │   └── cypress_runner.py   # Cypress automation wrapper
│   ├── security/
│   │   ├── service_account_validator.py  # Service account validation
│   │   ├── url_filter.py       # URL filtering (whitelist/blacklist)
│   │   ├── audit_trail.py      # Audit trail logging
│   │   └── rate_limiter.py     # Per-spreadsheet rate limiting
│   └── utils/
│       └── logger.py            # Logging utilities
├── cypress/
│   ├── e2e/
│   │   └── analyze-url.cy.js   # PageSpeed Insights test
│   └── results/                 # Generated results (gitignored)
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

1. **Install Python 3.7+ and Node.js 14+** (if not already installed)
   - Python: [python.org/downloads](https://www.python.org/downloads/)
   - Node.js: [nodejs.org](https://nodejs.org/)

2. **Clone/download this project**

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   npm install
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
- Only one Cypress instance can run at a time (do not run `npx cypress open` while audit is running)

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review the logs in the `logs/` directory
3. Verify all setup steps were completed correctly
4. Ensure URLs in the spreadsheet are valid and accessible

## License

(Add your license information here)
