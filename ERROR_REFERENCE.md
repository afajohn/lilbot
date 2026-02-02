# Error Reference - Quick Solutions

## Error Messages & Fixes

### 1. "Service account file not found"
**What it means:** Missing `service-account.json`

**Fix:**
```bash
# Download from Google Cloud Console and save as service-account.json
```

### 2. "Tab 'X' not found in spreadsheet"
**What it means:** Tab name doesn't exist or is misspelled

**Fix:**
```bash
python list_tabs.py  # See exact tab names
python run_audit.py --tab "EXACT_TAB_NAME"
```

### 3. "Access denied to spreadsheet"
**What it means:** Service account not shared with spreadsheet

**Fix:**
```bash
python get_service_account_email.py  # Get email
# Then share spreadsheet with that email (Editor permission)
```

### 4. "Authentication FAILED"
**What it means:** Invalid service account JSON file

**Fix:**
- Re-download key from Google Cloud Console
- Verify it's valid JSON
- Ensure Google Sheets API is enabled

### 5. "npx or Cypress not found"
**What it means:** Node.js dependencies not installed

**Fix:**
```bash
npm install
```

### 6. "No URLs found in the spreadsheet"
**What it means:** Column A is empty or URLs are elsewhere

**Fix:**
- Ensure URLs are in Column A (first column)
- Check URLs start with http:// or https://
- Remove empty rows at the top

### 7. "Cypress execution exceeded timeout"
**What it means:** Website too slow or PageSpeed taking too long

**Fix:**
```bash
python run_audit.py --tab "TAB_NAME" --timeout 600  # Increase timeout
```

### 8. "Package not installed"
**What it means:** Python dependency missing

**Fix:**
```bash
pip install -r requirements.txt
```

## Quick Diagnostic Commands

```bash
# Check everything
python validate_setup.py

# List tabs
python list_tabs.py

# Get service account email
python get_service_account_email.py

# Test with verbose logging
python run_audit.py --tab "TAB_NAME" 2>&1 | tee debug.log
```

## Common Workflow Issues

### Issue: "I don't know my tab name"
```bash
python list_tabs.py
```

### Issue: "I don't know my service account email"
```bash
python get_service_account_email.py
```

### Issue: "Setup not working"
```bash
python validate_setup.py
```

### Issue: "Still getting errors"
1. Check logs in `logs/` directory
2. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. Run `python validate_setup.py` for diagnostics

## HTTP Error Codes

- **404** - Not found (tab doesn't exist or spreadsheet ID wrong)
- **403** - Permission denied (share spreadsheet with service account)
- **401** - Authentication failed (invalid service account file)
- **429** - Rate limit exceeded (too many requests, wait and retry)

## Exit Codes

- **0** - Success
- **1** - Error occurred (check logs for details)

## Getting More Help

1. Run diagnostic: `python validate_setup.py`
2. Check logs: `logs/audit_*.log`
3. See full guide: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
