# PageSpeed Insights Audit Tool

Automated tool for running PageSpeed Insights audits on URLs from Google Sheets and writing results back to the spreadsheet.

## Overview

This tool reads URLs from a Google Spreadsheet, analyzes each URL using PageSpeed Insights (via Cypress automation), and writes PageSpeed report URLs back to the spreadsheet for URLs with scores below 80.

## Prerequisites

- Python 3.7+
- Node.js 14+ and npm
- Google Cloud service account with Sheets API access

## Setup Instructions

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `google-auth` - Google authentication library
- `google-auth-oauthlib` - OAuth2 support
- `google-auth-httplib2` - HTTP transport for Google APIs
- `google-api-python-client` - Google Sheets API client
- `python-dotenv` - Environment variable management
- `argparse` - Command-line argument parsing

### 2. Install Node.js Dependencies

```bash
npm install
```

This installs Cypress for browser automation.

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
6. Save the file as `service-account.json` in the project root directory

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

### 4. Environment Variables (Optional)

Copy `.env.example` to `.env` and customize if needed:

```bash
cp .env.example .env
```

Edit `.env`:
```
GOOGLE_SHEETS_ID=your-spreadsheet-id-here
GOOGLE_SERVICE_ACCOUNT_PATH=path/to/service-account.json
```

**Note:** Environment variables are optional. You can provide spreadsheet ID and service account path via command-line arguments.

## Usage

### Basic Usage

```bash
python run_audit.py --tab "Barranquilla Singles"
```

### Advanced Options

```bash
python run_audit.py --tab "Barranquilla Singles" \
  --spreadsheet-id "1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I" \
  --service-account "service-account.json" \
  --timeout 300
```

### Command-Line Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--tab` | Yes | - | Name of the spreadsheet tab to read URLs from |
| `--spreadsheet-id` | No | `1vF4ySHs3nZVD6hkb8CWH7evRAy2V93DhS3wQ9rO3MhU` | Google Spreadsheet ID |
| `--service-account` | No | `service-account.json` | Path to service account JSON file |
| `--timeout` | No | `300` | Timeout in seconds for each URL analysis |

### Examples

Analyze URLs from "Q1 2024" tab:
```bash
python run_audit.py --tab "Q1 2024"
```

Use a different spreadsheet:
```bash
python run_audit.py --tab "Production Sites" --spreadsheet-id "abc123xyz"
```

Use a custom service account file location:
```bash
python run_audit.py --tab "Website 1" --service-account "/path/to/credentials.json"
```

Increase timeout for slow-loading sites:
```bash
python run_audit.py --tab "Website 1" --timeout 600
```

## Google Sheets Column Mapping

The tool expects and writes to the following columns:

| Column | Purpose | Access |
|--------|---------|--------|
| **A** | URLs to analyze | **Read** |
| **F** | Mobile PageSpeed Insights URLs | **Write** (only for scores < 80) |
| **G** | Desktop PageSpeed Insights URLs | **Write** (only for scores < 80) |

### Spreadsheet Format

Your spreadsheet tab should be structured as:

```
| A (URL)                    | B    | C    | D    | E    | F (Mobile PSI)     | G (Desktop PSI)    |
|----------------------------|------|------|------|------|--------------------|--------------------|
| https://example.com        |      |      |      |      | [PSI URL if < 80]  | [PSI URL if < 80]  |
| https://example.com/about  |      |      |      |      | [PSI URL if < 80]  | [PSI URL if < 80]  |
| https://example.com/contact|      |      |      |      | [PSI URL if < 80]  | [PSI URL if < 80]  |
```

**Important Notes:**
- Column A must contain valid URLs (with `http://` or `https://`)
- The tool starts reading from row 1 (no header row required)
- Empty cells in column A are skipped
- Columns F and G are only populated when scores are below 80 (threshold configurable in code)

## How It Works

1. **Authentication**: Authenticates with Google Sheets using the service account credentials
2. **Read URLs**: Reads all URLs from column A of the specified tab
3. **Analysis**: For each URL:
   - Launches Cypress to automate PageSpeed Insights
   - Navigates to pagespeed.web.dev
   - Analyzes the URL for both mobile and desktop
   - Extracts performance scores (0-100)
   - Captures report URLs for failing scores (< 80)
4. **Write Results**: Batch updates the spreadsheet:
   - Mobile PSI URLs → Column F (only if score < 80)
   - Desktop PSI URLs → Column G (only if score < 80)
5. **Summary**: Displays audit summary with pass/fail statistics

## Output

The tool provides real-time progress updates:

```
Authenticating with Google Sheets...
Reading URLs from spreadsheet tab 'Website 1'...
Found 5 URLs to analyze.

[1/5] Analyzing https://example.com...
  Mobile: 92 (PASS)
  Desktop: 95 (PASS)

[2/5] Analyzing https://slow-site.com...
  Mobile: 65 (FAIL)
  Desktop: 72 (FAIL)

...

Updating spreadsheet with 4 PSI URLs...
Spreadsheet updated successfully.

================================================================================
AUDIT SUMMARY
================================================================================
Total URLs analyzed: 5
Successful analyses: 5
Failed analyses: 0

Mobile scores >= 80: 3
Mobile scores < 80: 2
Desktop scores >= 80: 4
Desktop scores < 80: 1

PSI URLs for failing scores written to columns F (mobile) and G (desktop).
================================================================================
```

## Troubleshooting

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

### Error: Failed to read URLs

**Possible Causes**:
- Spreadsheet ID is incorrect
- Tab name doesn't exist or is misspelled
- Service account doesn't have access to the spreadsheet

**Solution**:
- Verify the spreadsheet ID (found in the URL: `https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit`)
- Check tab name matches exactly (case-sensitive)
- Ensure the spreadsheet is shared with the service account email

### Error: Timeout - Cypress execution exceeded X seconds

**Cause**: The website took too long to load or PageSpeed Insights analysis timed out.

**Solution**:
- Increase timeout: `python run_audit.py --tab "Website 1" --timeout 600`
- Check if the URL is accessible and loads properly
- Verify your internet connection is stable

### Error: npx or Cypress not found

**Cause**: Node.js or Cypress is not installed.

**Solution**:
```bash
npm install
```

### Error: No new results file found

**Cause**: Cypress ran but didn't generate a results file.

**Solution**:
- Check if `cypress/results/` directory exists
- Review Cypress logs for errors
- Verify the URL is accessible
- Try running manually: `npx cypress open` and check the test

### Cypress test fails with element not found

**Cause**: PageSpeed Insights website structure may have changed.

**Solution**:
- This indicates the PageSpeed Insights UI may have been updated
- Check `cypress/e2e/analyze-url.cy.js` for outdated selectors
- Update selectors to match current PageSpeed Insights DOM structure

### Permission denied when writing to spreadsheet

**Cause**: Service account doesn't have Editor permissions.

**Solution**:
- Open the spreadsheet
- Click Share
- Find the service account email
- Change permission to "Editor"

### Invalid spreadsheet ID

**Cause**: The spreadsheet ID format is incorrect.

**Solution**:
- Get the ID from your spreadsheet URL
- URL format: `https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit`
- Copy only the ID portion between `/d/` and `/edit`

## Configuration

### Modifying Score Threshold

The default threshold for "failing" scores is 80. To change it, edit `run_audit.py`:

```python
SCORE_THRESHOLD = 80  # Change this value
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
├── requirements.txt             # Python dependencies
├── package.json                 # Node.js dependencies
├── cypress.config.js            # Cypress configuration
├── service-account.json         # Google Cloud credentials (not in repo)
├── .env.example                 # Environment variable template
├── tools/
│   ├── sheets/
│   │   └── sheets_client.py    # Google Sheets API wrapper
│   └── qa/
│       └── cypress_runner.py   # Cypress automation wrapper
└── cypress/
    ├── e2e/
    │   └── analyze-url.cy.js   # PageSpeed Insights test
    └── results/                 # Generated results (gitignored)
```

## Advanced Tips

### Batch Processing Multiple Tabs

Create a shell script to process multiple tabs:

```bash
#!/bin/bash
tabs=("Website 1" "Website 2" "Website 3")
for tab in "${tabs[@]}"; do
    echo "Processing tab: $tab"
    python run_audit.py --tab "$tab"
done
```

### Schedule Regular Audits

Use cron (Linux/Mac) or Task Scheduler (Windows) to run audits automatically:

```bash
# Run every Monday at 9 AM
0 9 * * 1 cd /path/to/project && python run_audit.py --tab "Production Sites"
```

## Limitations

- Requires active internet connection
- PageSpeed Insights rate limits may apply for high-volume usage
- Analysis time depends on website complexity and server response time
- Browser automation depends on PageSpeed Insights UI structure

## License

(Add your license information here)
