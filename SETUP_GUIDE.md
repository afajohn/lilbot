# Complete Setup Guide

This guide walks you through setting up the PageSpeed Insights Audit Tool from scratch.

## Prerequisites

- Python 3.7 or higher
- Node.js 14 or higher
- npm (comes with Node.js)
- Google Cloud account (free tier is sufficient)
- Google Spreadsheet with URLs to audit

## Step-by-Step Setup

### Step 1: Clone or Download the Project

```bash
cd /path/to/project
```

### Step 2: Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `google-auth` - Google authentication
- `google-auth-oauthlib` - OAuth2 support
- `google-auth-httplib2` - HTTP transport
- `google-api-python-client` - Google Sheets API
- `python-dotenv` - Environment variables

### Step 3: Install Node.js Dependencies

```bash
npm install
```

This installs Cypress for browser automation.

### Step 4: Create Google Cloud Service Account

#### 4.1 Create Google Cloud Project (if you don't have one)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" dropdown at the top
3. Click "New Project"
4. Enter project name (e.g., "pagespeed-audit")
5. Click "Create"

#### 4.2 Enable Google Sheets API

1. In Google Cloud Console, ensure your project is selected
2. Navigate to **APIs & Services** > **Library**
3. Search for "Google Sheets API"
4. Click on it
5. Click **Enable**

#### 4.3 Create Service Account

1. Navigate to **IAM & Admin** > **Service Accounts**
2. Click **Create Service Account**
3. Enter:
   - **Name**: `pagespeed-audit` (or any name you prefer)
   - **Description**: `Service account for PageSpeed audit tool`
4. Click **Create and Continue**
5. Skip the optional steps (click **Continue**, then **Done**)

#### 4.4 Generate Service Account Key

1. Click on the newly created service account email
2. Go to the **Keys** tab
3. Click **Add Key** > **Create new key**
4. Select **JSON** format
5. Click **Create**
6. The key file will download automatically
7. **Rename the downloaded file to `service-account.json`**
8. **Move it to your project root directory**

⚠️ **IMPORTANT:** Keep this file secure! Never commit it to git or share it publicly.

#### 4.5 Note Your Service Account Email

In the `service-account.json` file, find the `client_email` field:
```json
{
  "type": "service_account",
  "project_id": "your-project",
  "client_email": "pagespeed-audit@your-project.iam.gserviceaccount.com",
  ...
}
```

Copy this email address - you'll need it in the next step.

### Step 5: Prepare Your Google Spreadsheet

#### 5.1 Spreadsheet Structure

Your spreadsheet should have this structure:

| Column A (URL) | ... | Column F (Mobile PSI) | Column G (Desktop PSI) |
|----------------|-----|-----------------------|------------------------|
| https://example.com | | (auto-filled) | (auto-filled) |
| https://example.com/about | | (auto-filled) | (auto-filled) |

- **Column A**: URLs to audit (required)
- **Columns B-E**: Your own data (optional)
- **Column F**: Mobile PageSpeed Insights URLs (auto-written by tool)
- **Column G**: Desktop PageSpeed Insights URLs (auto-written by tool)

#### 5.2 Share Spreadsheet with Service Account

1. Open your Google Spreadsheet
2. Click the **Share** button (top right)
3. Paste the service account email from step 4.5
4. Set permission to **Editor**
5. **Uncheck** "Notify people"
6. Click **Share**

#### 5.3 Get Your Spreadsheet ID

The spreadsheet ID is in the URL:
```
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit
```

Copy the ID between `/d/` and `/edit`.

#### 5.4 Update Default Spreadsheet ID (Optional)

If you want to use your own spreadsheet by default, edit `run_audit.py` and `list_tabs.py`:

```python
DEFAULT_SPREADSHEET_ID = 'YOUR_SPREADSHEET_ID_HERE'
```

Or always use the `--spreadsheet-id` argument when running commands.

### Step 6: Validate Your Setup

Run the validation script to check everything is configured correctly:

```bash
python validate_setup.py
```

This will check:
- ✓ All required files exist
- ✓ Python dependencies are installed
- ✓ Node.js and npm are installed
- ✓ Cypress is installed
- ✓ Service account file is valid
- ✓ Can authenticate with Google Sheets
- ✓ Can access your spreadsheet
- ✓ Can list tabs in your spreadsheet

If all checks pass, you're ready to go! If any fail, see the error messages and [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

### Step 7: List Available Tabs

See all tabs in your spreadsheet:

```bash
python list_tabs.py
```

This will output:
```
Found 3 tab(s):

  1. Website 1
  2. Website 2
  3. Production Sites

To run audit on a tab, use:
  python run_audit.py --tab "TAB_NAME"
```

### Step 8: Run Your First Audit

Run an audit on a specific tab:

```bash
python run_audit.py --tab "Website 1"
```

The tool will:
1. Authenticate with Google Sheets
2. Read URLs from Column A
3. Analyze each URL using PageSpeed Insights
4. Write failing URLs to Columns F and G
5. Display a summary

## Configuration Options

### Command-Line Arguments

**run_audit.py:**
```bash
python run_audit.py \
  --tab "TAB_NAME" \              # Required: tab name
  --spreadsheet-id "ID" \          # Optional: spreadsheet ID
  --service-account "path.json" \  # Optional: service account path
  --timeout 600                    # Optional: timeout in seconds
```

**list_tabs.py:**
```bash
python list_tabs.py \
  --spreadsheet-id "ID" \          # Optional: spreadsheet ID
  --service-account "path.json"    # Optional: service account path
```

### Environment Variables (Optional)

Create a `.env` file:
```bash
cp .env.example .env
```

Edit `.env`:
```
GOOGLE_SHEETS_ID=your-spreadsheet-id
GOOGLE_SERVICE_ACCOUNT_PATH=service-account.json
```

⚠️ **Note:** Command-line arguments override environment variables.

## Customization

### Change Score Threshold

Edit `run_audit.py`:
```python
SCORE_THRESHOLD = 80  # Change to 70, 90, etc.
```

### Change Column Mappings

Edit `run_audit.py`:
```python
MOBILE_COLUMN = 'F'   # Change to any column letter
DESKTOP_COLUMN = 'G'  # Change to any column letter
```

### Adjust Timeouts

Cypress test timeout (edit `cypress.config.js`):
```javascript
defaultCommandTimeout: 30000,  // 30 seconds
pageLoadTimeout: 60000         // 60 seconds
```

Script timeout (command-line):
```bash
python run_audit.py --tab "Website 1" --timeout 600
```

## Scheduled Audits (Optional)

### Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., weekly)
4. Set action: Start a program
   - Program: `python`
   - Arguments: `C:\path\to\run_audit.py --tab "Website 1"`
   - Start in: `C:\path\to\project`

### Linux/Mac Cron

Add to crontab:
```bash
# Run every Monday at 9 AM
0 9 * * 1 cd /path/to/project && python run_audit.py --tab "Website 1"
```

## Security Best Practices

1. **Never commit service-account.json** - it's already in `.gitignore`
2. **Rotate keys regularly** - create new keys every 90 days
3. **Use least privilege** - service account only needs Sheets API access
4. **Secure the key file** - restrict file permissions:
   ```bash
   chmod 600 service-account.json  # Unix/Mac
   ```
5. **Don't share keys** - each user should have their own service account

## Next Steps

- Read [README.md](README.md) for usage details
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if you encounter issues
- Run `python validate_setup.py` periodically to verify setup

## Getting Help

If you encounter issues:

1. Run `python validate_setup.py` to diagnose
2. Check logs in `logs/` directory
3. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
4. Review Google Cloud Console for API quotas and errors

## Uninstallation

To remove the tool:

1. Delete service account from Google Cloud Console
2. Remove spreadsheet sharing with service account
3. Delete project directory
4. (Optional) Delete Google Cloud project if no longer needed
