# Troubleshooting Guide

This guide helps resolve common issues when running the PageSpeed Insights Audit Tool.

## Quick Diagnostics

### 1. List Available Tabs

Before running the audit, list all available tabs in your spreadsheet:

```bash
python list_tabs.py
```

This will show you all tab names and verify your setup is working.

### 2. Check Service Account Setup

```bash
python -c "import os; print('Service account file exists:', os.path.exists('service-account.json'))"
```

## Common Errors and Solutions

### Error: "Service account file not found"

**Symptom:**
```
ERROR: Service account file not found: service-account.json
```

**Cause:** The service account JSON file is missing.

**Solution:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **IAM & Admin** > **Service Accounts**
3. Select or create a service account
4. Click **Keys** tab > **Add Key** > **Create new key** > **JSON**
5. Download the file and save it as `service-account.json` in your project root

### Error: "Tab 'X' not found in spreadsheet"

**Symptom:**
```
Tab 'Barranquilla Singles' not found in spreadsheet.
Available tabs: Sheet1, Website Data, Production Sites
```

**Causes:**
- Tab name is misspelled or has different capitalization
- Tab doesn't exist in the spreadsheet
- Extra spaces in tab name

**Solutions:**

1. **List all tabs** to see exact names:
   ```bash
   python list_tabs.py
   ```

2. **Use exact tab name** (case-sensitive):
   ```bash
   python run_audit.py --tab "Sheet1"
   ```

3. **Check for extra spaces** in tab name:
   - In Google Sheets, right-click the tab and select "Rename"
   - Remove any leading or trailing spaces

### Error: "Requested entity was not found" (404)

**Symptom:**
```
HttpError 404: Requested entity was not found
```

**Causes:**
- Spreadsheet ID is incorrect
- Tab name doesn't exist
- Service account doesn't have access

**Solutions:**

1. **Verify Spreadsheet ID:**
   - Open your Google Sheet
   - Copy the ID from the URL: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`
   - The ID is the long string between `/d/` and `/edit`
   
2. **Check default spreadsheet ID** in `run_audit.py`:
   ```python
   DEFAULT_SPREADSHEET_ID = '1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I'
   ```
   Update this if you're using a different spreadsheet.

3. **Use custom spreadsheet ID:**
   ```bash
   python run_audit.py --tab "Website 1" --spreadsheet-id "YOUR_SPREADSHEET_ID"
   ```

### Error: "Access denied" (403)

**Symptom:**
```
PermissionError: Access denied to spreadsheet
```

**Cause:** Service account doesn't have permission to access the spreadsheet.

**Solution:**

1. **Get service account email:**
   - Open `service-account.json`
   - Find the `client_email` field
   - Copy the email (format: `name@project.iam.gserviceaccount.com`)

2. **Share spreadsheet:**
   - Open your Google Spreadsheet
   - Click **Share** button (top right)
   - Paste the service account email
   - Select **Editor** permission
   - Uncheck "Notify people"
   - Click **Share**

### Error: "Invalid service account file"

**Symptom:**
```
ValueError: Invalid service account file
```

**Causes:**
- JSON file is corrupted
- Wrong file format
- File is incomplete

**Solutions:**

1. **Verify JSON structure:**
   ```bash
   python -c "import json; json.load(open('service-account.json'))"
   ```

2. **Re-download the key:**
   - Go to Google Cloud Console
   - Create a new service account key
   - Replace the old file

### Error: "Google Sheets API not enabled"

**Symptom:**
```
Error: The API is not enabled
```

**Solution:**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Navigate to **APIs & Services** > **Library**
4. Search for "Google Sheets API"
5. Click it and click **Enable**

### Error: "npx or Cypress not found"

**Symptom:**
```
CypressRunnerError: npx or Cypress not found
```

**Cause:** Node.js or Cypress is not installed.

**Solution:**

```bash
# Install Node.js dependencies
npm install

# Verify installation
npx cypress version
```

### Error: "Cypress execution exceeded timeout"

**Symptom:**
```
CypressTimeoutError: Cypress execution exceeded 300 seconds timeout
```

**Causes:**
- Website is very slow to load
- PageSpeed Insights is taking longer than expected
- Network issues

**Solutions:**

1. **Increase timeout:**
   ```bash
   python run_audit.py --tab "Website 1" --timeout 600
   ```

2. **Check URL is accessible:**
   - Open the URL in a browser
   - Verify it loads properly

3. **Test manually:**
   - Visit https://pagespeed.web.dev/
   - Paste the URL and see if it analyzes successfully

### Error: "No URLs found in the spreadsheet"

**Symptom:**
```
No URLs found in the spreadsheet.
```

**Causes:**
- Column A is empty
- URLs are in a different column
- Tab is empty

**Solutions:**

1. **Verify URLs are in Column A:**
   - Open your spreadsheet
   - Ensure URLs are in Column A (first column)
   - Remove any header row or add URL to it

2. **Check URL format:**
   - URLs must start with `http://` or `https://`
   - Remove any spaces before/after URLs

## Environment Variables (.env)

The `.env` file is **optional**. If you want to use it:

1. **Create .env file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env:**
   ```
   GOOGLE_SHEETS_ID=1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I
   GOOGLE_SERVICE_ACCOUNT_PATH=service-account.json
   ```

**Note:** Command-line arguments override environment variables.

## Verification Checklist

Before running the audit, verify:

- [ ] `service-account.json` exists in project root
- [ ] Google Sheets API is enabled in Google Cloud Console
- [ ] Spreadsheet is shared with service account email
- [ ] Tab name is correct (use `python list_tabs.py` to verify)
- [ ] URLs are in Column A of the spreadsheet
- [ ] Node.js and npm are installed
- [ ] Cypress is installed (`npm install`)
- [ ] Python dependencies are installed (`pip install -r requirements.txt`)

## Testing Your Setup

Run these commands in order to test your setup:

```bash
# 1. Test authentication and list tabs
python list_tabs.py

# 2. If tabs are listed successfully, run audit on one tab
python run_audit.py --tab "TAB_NAME"
```

## Getting Help

If you still have issues:

1. Check the log file in `logs/` directory
2. Look for detailed error messages
3. Verify all setup steps from README.md
4. Ensure you have the latest version of all dependencies

## Example: Complete Setup from Scratch

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install Node.js dependencies
npm install

# 3. Download service account key from Google Cloud Console
# Save as service-account.json

# 4. Share spreadsheet with service account email

# 5. Enable Google Sheets API in Google Cloud Console

# 6. List available tabs
python list_tabs.py

# 7. Run audit
python run_audit.py --tab "Website 1"
```

## Advanced Troubleshooting

### Enable Debug Logging

Edit `tools/utils/logger.py` and change:
```python
logger.setLevel(logging.DEBUG)  # Change from INFO to DEBUG
```

### Test Cypress Manually

```bash
# Open Cypress UI
npx cypress open

# Run specific test
npx cypress run --spec cypress/e2e/analyze-url.cy.js
```

### Check Spreadsheet Permissions

```bash
python -c "
from tools.sheets import sheets_client
service = sheets_client.authenticate('service-account.json')
info = service.spreadsheets().get(spreadsheetId='YOUR_ID').execute()
print('Spreadsheet title:', info['properties']['title'])
"
```
