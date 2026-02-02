# Quick Start Guide

## First Time Setup (5 minutes)

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   npm install
   ```

2. **Get service account key:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create service account → Generate JSON key
   - Save as `service-account.json` in project root
   - Enable Google Sheets API

3. **Share your spreadsheet:**
   ```bash
   python get_service_account_email.py  # Get the email to share with
   ```
   - Share Google Spreadsheet with that email (Editor permission)

4. **Validate setup:**
   ```bash
   python validate_setup.py
   ```

## Daily Usage

### See available tabs:
```bash
python list_tabs.py
```

### Run audit:
```bash
python run_audit.py --tab "TAB_NAME"
```

## Common Commands

```bash
# Run audit with custom spreadsheet
python run_audit.py --tab "Website 1" --spreadsheet-id "YOUR_ID"

# Run audit with longer timeout
python run_audit.py --tab "Website 1" --timeout 600

# List tabs from different spreadsheet
python list_tabs.py --spreadsheet-id "YOUR_ID"
```

## Spreadsheet Format

| Column A | B-E | Column F | Column G |
|----------|-----|----------|----------|
| URLs to audit | Your data | Mobile PSI (auto) | Desktop PSI (auto) |

- Put URLs in Column A
- Tool writes PageSpeed URLs to F & G when score < 80

## Troubleshooting

**Tab not found?**
```bash
python list_tabs.py  # See exact tab names
```

**Service account issues?**
```bash
python validate_setup.py  # Run diagnostics
```

**Need help?** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## Full Documentation

- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Complete setup instructions
- [README.md](README.md) - Full feature documentation
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Error solutions
