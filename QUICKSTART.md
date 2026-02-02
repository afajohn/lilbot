# Quick Start Guide

Get up and running with the PageSpeed Insights Audit Tool in 5 minutes.

## Prerequisites Check

Ensure you have:
- ✅ Python 3.7+ installed (`python --version`)
- ✅ Node.js 14+ installed (`node --version`)

## Installation (5 minutes)

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install Node.js dependencies
npm install

# 3. Verify installation
python validate_setup.py
```

## Google Cloud Setup (10 minutes)

### 1. Create Service Account
- Go to [console.cloud.google.com](https://console.cloud.google.com/)
- Create a new project (or select existing)
- Enable **Google Sheets API**
- Create a **Service Account**
- Download the **JSON key** and save as `service-account.json`

### 2. Get Service Account Email
```bash
python get_service_account_email.py
```

### 3. Share Your Spreadsheet
- Open your Google Spreadsheet
- Click **Share**
- Paste the service account email
- Set permission to **Editor**
- Click **Share**

## Prepare Your Spreadsheet

Your spreadsheet should look like this:

| A (URLs) | B | C | D | E | F (Mobile) | G (Desktop) |
|----------|---|---|---|---|------------|-------------|
| URL | | | | | | | ← Header (Row 1)
| https://example.com | | | | | | | ← First URL (Row 2)
| https://example.com/about | | | | | | |
| https://example.com/contact | | | | | | |

**Important:**
- URLs must be in **Column A**
- **Row 1 is treated as a header** and skipped
- URLs start from **Row 2** (A2, A3, A4, etc.)
- Columns F and G will be auto-filled with PSI URLs for scores < 80

## Run Your First Audit

### 1. List Your Tabs
```bash
python list_tabs.py --service-account "service-account.json"
```

### 2. Run the Audit
```bash
python run_audit.py --tab "Barranquilla Singles" --service-account "service-account.json"
```

Replace `"Barranquilla Singles"` with your actual tab name.

## What Happens Next?

The tool will:
1. ✅ Authenticate with Google Sheets
2. ✅ Read URLs from Column A (starting at A2)
3. ✅ Analyze each URL with PageSpeed Insights
4. ✅ Display real-time progress and scores
5. ✅ Write PSI URLs to columns F and G (for scores < 80)
6. ✅ Show a summary report

## Example Output

```
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

## Common Commands

### List all tabs in your spreadsheet
```bash
python list_tabs.py --service-account "service-account.json"
```

### Run audit with custom timeout (in seconds)
```bash
python run_audit.py --tab "Your Tab" --timeout 600 --service-account "service-account.json"
```

### Run audit with different spreadsheet
```bash
python run_audit.py --tab "Your Tab" --spreadsheet-id "YOUR_ID" --service-account "service-account.json"
```

### Verify your setup
```bash
python validate_setup.py
```

## Troubleshooting

### ❌ Error: service-account.json not found
**Fix:** Make sure the file is in the project root directory

### ❌ Error: Tab not found
**Fix:** Run `python list_tabs.py` to see available tabs (names are case-sensitive)

### ❌ Error: Permission denied
**Fix:** Share the spreadsheet with your service account email with Editor permissions

### ❌ Error: UnicodeDecodeError
**Fix:** This is already fixed in the latest version. Make sure you're using the updated code.

### ❌ Error: npx or Cypress not found
**Fix:** Run `npm install` to install Cypress

### ❌ Cypress timeout
**Fix:** Increase timeout: `--timeout 600` (600 seconds)

## Tips

### ⚡ Faster Audits
- Use a wired internet connection
- Close other applications
- Increase timeout for slow sites: `--timeout 600`

### 📊 Multiple Tabs
Process multiple tabs with a script:
```bash
# PowerShell
$tabs = @("Tab1", "Tab2", "Tab3")
foreach ($tab in $tabs) {
    python run_audit.py --tab $tab --service-account "service-account.json"
}
```

### 📝 Check Logs
Logs are saved in the `logs/` directory with timestamps.

## Next Steps

- Read the full [README.md](README.md) for detailed information
- Check [INSTALL.md](INSTALL.md) for detailed installation instructions
- Review [AGENTS.md](AGENTS.md) if you're developing/modifying the tool

## Need Help?

1. Run `python validate_setup.py` to diagnose issues
2. Check the logs in `logs/` directory
3. Review the Troubleshooting section in README.md
4. Ensure your spreadsheet format matches the requirements
