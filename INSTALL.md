# Installation Guide

This guide will walk you through setting up the PageSpeed Insights Audit Tool step-by-step.

## Prerequisites

Before you begin, ensure you have the following installed:

### 1. Python 3.7 or higher

**Check if Python is installed:**
```bash
python --version
```

**If not installed:**
- **Windows**: Download from [python.org](https://www.python.org/downloads/)
  - During installation, check "Add Python to PATH"
- **Mac**: Use Homebrew: `brew install python3`
- **Linux**: Use your package manager: `sudo apt install python3 python3-pip`

### 2. Node.js 14+ and npm

**Check if Node.js is installed:**
```bash
node --version
npm --version
```

**If not installed:**
- Download from [nodejs.org](https://nodejs.org/) (LTS version recommended)
- npm is included with Node.js

## Step 1: Download the Project

Clone or download this repository to your local machine.

```bash
git clone <repository-url>
cd <project-directory>
```

## Step 2: Install Python Dependencies

Open a terminal/command prompt in the project directory and run:

```bash
pip install -r requirements.txt
```

This will install:
- `google-auth` - Authentication library
- `google-auth-oauthlib` - OAuth2 support
- `google-auth-httplib2` - HTTP transport
- `google-api-python-client` - Google Sheets API client

**If you see permission errors on Linux/Mac, try:**
```bash
pip install --user -r requirements.txt
```

## Step 3: Install Node.js Dependencies

In the same terminal, run:

```bash
npm install
```

This will install Cypress and related dependencies. This may take a few minutes.

## Step 4: Set Up Google Cloud Service Account

### 4.1 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Enter a project name (e.g., "PageSpeed Audit")
4. Click **Create**

### 4.2 Enable Google Sheets API

1. In the Google Cloud Console, ensure your project is selected
2. Go to **APIs & Services** → **Library**
3. Search for "Google Sheets API"
4. Click on it and click **Enable**

### 4.3 Create a Service Account

1. Go to **IAM & Admin** → **Service Accounts**
2. Click **Create Service Account**
3. Enter:
   - **Service account name**: `pagespeed-audit` (or any name you prefer)
   - **Service account ID**: Will auto-populate
   - **Description**: "Service account for PageSpeed audits"
4. Click **Create and Continue**
5. Skip the optional steps:
   - Click **Continue** (skip "Grant this service account access to project")
   - Click **Done** (skip "Grant users access to this service account")

### 4.4 Generate Service Account Key

1. Click on the newly created service account
2. Go to the **Keys** tab
3. Click **Add Key** → **Create new key**
4. Select **JSON** format
5. Click **Create**
6. A JSON file will download automatically
7. **Important**: Rename the file to `service-account.json` and move it to your project root directory

**Security Note**: This file contains sensitive credentials. Never commit it to version control or share it publicly.

### 4.5 Get Service Account Email

You need to share your Google Spreadsheet with this service account.

**Option 1: Check the JSON file**
- Open `service-account.json`
- Find the `client_email` field
- It looks like: `your-service-account@project-id.iam.gserviceaccount.com`

**Option 2: Use the helper script**
```bash
python get_service_account_email.py
```

Copy this email address.

### 4.6 Share Your Spreadsheet

1. Open your Google Spreadsheet
2. Click the **Share** button
3. Paste the service account email
4. Set permission to **Editor**
5. Uncheck "Notify people" (the service account is not a real person)
6. Click **Share**

## Step 5: Prepare Your Spreadsheet

Ensure your spreadsheet has the following format:

| Column A | Column F | Column G |
|----------|----------|----------|
| URL      | (Mobile PSI URL) | (Desktop PSI URL) |
| https://example.com | | |
| https://example.com/about | | |
| https://example.com/contact | | |

**Important:**
- Column A should contain URLs starting from row 2 (row 1 is treated as a header)
- URLs must include `http://` or `https://`
- Columns F and G will be automatically filled with PageSpeed Insights URLs for failing scores

## Step 6: Verify Installation

Run the validation script to check if everything is set up correctly:

```bash
python validate_setup.py
```

This will check:
- ✓ Project structure
- ✓ Python dependencies
- ✓ Node.js and npm
- ✓ Cypress installation
- ✓ Service account file
- ✓ Google Sheets access

If all checks pass, you're ready to run audits!

## Step 7: Run Your First Audit

### List Available Tabs

First, see what tabs are in your spreadsheet:

```bash
python list_tabs.py --spreadsheet-id "YOUR_SPREADSHEET_ID" --service-account "service-account.json"
```

**To find your spreadsheet ID:**
- Open your spreadsheet in Google Sheets
- Look at the URL: `https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit`
- The ID is the long string between `/d/` and `/edit`

### Run the Audit

```bash
python run_audit.py --tab "Barranquilla Singles" --service-account "service-account.json"
```

Replace `"Barranquilla Singles"` with your actual tab name.

## Troubleshooting Installation

### Error: pip not found

**Solution:**
- Windows: Reinstall Python and check "Add Python to PATH"
- Mac/Linux: Install pip: `sudo apt install python3-pip` or `brew install python3`

### Error: npm not found

**Solution:**
- Reinstall Node.js from [nodejs.org](https://nodejs.org/)
- Ensure it's added to your system PATH

### Error: Cannot install Cypress

**Possible causes:**
- Network issues
- Disk space (Cypress downloads a browser, needs ~500MB)
- Firewall blocking downloads

**Solution:**
```bash
npm cache clean --force
npm install
```

### Error: service-account.json not found

**Solution:**
- Verify the file is in the project root directory
- Verify the filename is exactly `service-account.json`
- Use `--service-account` flag to specify a different path

### Error: Permission denied (Google Sheets)

**Solution:**
- Verify you shared the spreadsheet with the service account email
- Verify the permission is set to **Editor**, not **Viewer**
- Wait a few minutes for permissions to propagate

### Error: UnicodeDecodeError

This error has been fixed in the latest version. If you still encounter it:
- Ensure you're using the latest code
- The fix includes explicit UTF-8 encoding in subprocess calls

## Windows-Specific Notes

### PowerShell Execution Policy

If you get an error about scripts being disabled:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Path Issues

If commands aren't found:
1. Search for "Environment Variables" in Windows
2. Edit the "Path" variable
3. Add Python and Node.js installation directories
4. Restart your terminal

## Mac-Specific Notes

### Python vs Python3

On Mac, use `python3` instead of `python`:

```bash
python3 --version
python3 run_audit.py --tab "Your Tab"
```

### XCode Command Line Tools

If you get compiler errors, install XCode tools:

```bash
xcode-select --install
```

## Linux-Specific Notes

### Python Headers

If installation fails, you may need Python development headers:

```bash
sudo apt update
sudo apt install python3-dev
```

### Cypress Dependencies

Cypress may require additional system libraries:

```bash
sudo apt install libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev libgconf-2-4 libnss3 libxss1 libasound2 libxtst6 xauth xvfb
```

## Next Steps

Once installation is complete:

1. Read the [README.md](README.md) for usage instructions
2. Check the [AGENTS.md](AGENTS.md) for development guidelines
3. Run `python validate_setup.py` before each audit session to ensure everything is configured

## Getting Help

If you encounter issues not covered here:

1. Check the Troubleshooting section in [README.md](README.md)
2. Review the logs in the `logs/` directory
3. Verify all setup steps were completed
4. Ensure your spreadsheet is properly formatted
