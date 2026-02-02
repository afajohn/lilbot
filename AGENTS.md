# Agent Development Guide

## Commands

**Setup:**
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install
```

**Validate Setup:**
```bash
python validate_setup.py
```

**List Spreadsheet Tabs:**
```bash
python list_tabs.py --spreadsheet-id "YOUR_ID" --service-account "service-account.json"
```

**Run Audit:**
```bash
python run_audit.py --tab "TAB_NAME" --service-account "service-account.json"
# Optional: Specify custom timeout (default: 900 seconds)
python run_audit.py --tab "TAB_NAME" --timeout 1200
```

**Build:** Not applicable (Python script)

**Lint:** Not configured

**Test:** Not configured

**Dev Server:** Not applicable (CLI tool)

## Tech Stack

- **Language**: Python 3.7+
- **Browser Automation**: Cypress (JavaScript/Node.js)
- **APIs**: Google Sheets API v4
- **Key Libraries**:
  - `google-api-python-client` - Google Sheets integration
  - `google-auth` - Authentication
  - Cypress - Browser automation for PageSpeed Insights

## Architecture

### Project Structure

```
.
├── run_audit.py              # Main entry point - orchestrates the audit
├── list_tabs.py              # Utility to list spreadsheet tabs
├── get_service_account_email.py  # Utility to get service account email
├── validate_setup.py         # Setup validation script
├── tools/
│   ├── sheets/
│   │   └── sheets_client.py  # Google Sheets API wrapper
│   ├── qa/
│   │   └── cypress_runner.py # Cypress automation wrapper
│   └── utils/
│       └── logger.py         # Logging utilities
└── cypress/
    ├── e2e/
    │   └── analyze-url.cy.js # PageSpeed Insights test automation
    └── results/              # Generated JSON results (gitignored)
```

### Data Flow

1. **Input**: URLs from Google Sheets column A (starting row 2)
2. **Processing**:
   - `run_audit.py` reads URLs via `sheets_client.py`
   - For each URL, `cypress_runner.py` launches Cypress (retries up to 10 times on failure)
   - Cypress navigates to PageSpeed Insights and extracts scores from `.lh-exp-gauge__percentage`
   - Results saved to JSON files in `cypress/results/`
3. **Output**: 
   - For scores >= 80: Cell is filled with the text "passed"
   - For scores < 80: PSI URLs written to columns F (mobile) and G (desktop)

### Key Components

#### run_audit.py
- Main orchestrator
- Handles command-line arguments
- Manages the audit loop
- Collects and reports statistics

#### sheets_client.py
- Authenticates with Google Sheets API
- Reads URLs from spreadsheet (range A2:A)
- Writes PSI URLs back to spreadsheet
- Handles errors (permissions, missing tabs, etc.)

#### cypress_runner.py
- Finds npx executable
- Runs Cypress tests with proper encoding (UTF-8)
- Handles timeouts and retries (up to 10 retry attempts with exponential backoff)
- Parses JSON results
- Default timeout: 900 seconds (15 minutes)
- **Critical Fix**: Uses `encoding='utf-8', errors='replace'` to prevent Windows UnicodeDecodeError

#### analyze-url.cy.js
- Cypress test that automates PageSpeed Insights
- Visits pagespeed.web.dev
- Enters URL and runs mobile/desktop analysis
- Extracts scores from `.lh-exp-gauge__percentage` text
- Collects report URLs for scores < 80
- Saves results to JSON
- Configured with 5 automatic retries on failure
- Tripled timeout values (defaultCommandTimeout: 30s, pageLoadTimeout: 180s)

#### logger.py
- Sets up logging to both console and file
- Creates timestamped log files in `logs/` directory

## Code Style

- Follow PEP 8 for Python code
- No comments unless necessary for complex logic
- Use type hints for function parameters and returns
- Handle errors gracefully with informative messages
- Use f-strings for string formatting
- Keep functions focused and single-purpose

## Important Implementation Details

### Unicode Encoding Fix
All subprocess calls must include:
```python
subprocess.run(
    [...],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace'
)
```
This prevents `UnicodeDecodeError` on Windows when Cypress outputs non-ASCII characters.

### Spreadsheet Range
URLs are read from `A2:A` (not `A:A`) to skip the header row. Row enumeration starts at 2 to maintain correct row numbers when writing results back.

### Error Handling
- Catch specific exceptions (FileNotFoundError, PermissionError, ValueError)
- Provide actionable error messages
- Log full tracebacks for debugging
- Continue processing remaining URLs even if one fails

### Retry Logic
Cypress runs can fail transiently. The system has multiple layers of retry:
- Cypress internal retries: 5 attempts per run (configured in cypress.config.js)
- Python runner retries: Up to 10 attempts with exponential backoff (5s, 10s, 15s, up to 30s)
- Total possible attempts: Up to 60 (5 × 10 + initial attempt)

### Results File Management
- Each Cypress run generates a timestamped JSON file
- The runner tracks existing files before running and identifies new files after
- This prevents race conditions when running multiple audits

## Configuration

### Constants in run_audit.py
- `DEFAULT_SPREADSHEET_ID`: Default Google Sheets ID
- `SERVICE_ACCOUNT_FILE`: Default service account path
- `MOBILE_COLUMN`: Column for mobile results (default: 'F')
- `DESKTOP_COLUMN`: Column for desktop results (default: 'G')
- `SCORE_THRESHOLD`: Minimum passing score (default: 80)
- Default timeout: 900 seconds (can be overridden with --timeout flag)

### Environment Variables
Not currently used, but the code supports them via python-dotenv.

## Common Tasks

### Adding a New Column
1. Define a new column constant in `run_audit.py`
2. Modify the results processing logic
3. Add the value to the `updates` list
4. Update README documentation

### Changing Score Threshold
Edit `SCORE_THRESHOLD` in `run_audit.py`.

### Modifying Cypress Selectors
If PageSpeed Insights UI changes:
1. Edit `cypress/e2e/analyze-url.cy.js`
2. Update selectors to match new DOM structure
3. Current key selectors:
   - Analyze button: `button` containing text matching `/analyze/i`
   - Score display: `.lh-exp-gauge__percentage` (extracts text directly)
   - Mobile/Desktop toggle: `button` containing 'Mobile' or 'Desktop'
4. Test with `npx cypress open`

### Adding More Retry Attempts
1. Modify `max_retries` parameter in `cypress_runner.py` `run_analysis()` function (default: 10)
2. Modify `retries.runMode` in `cypress.config.js` (default: 5)
3. Adjust timeout with `--timeout` flag when running `run_audit.py` (default: 900 seconds)

## Testing

No formal test suite exists. Manual testing workflow:

1. Run `python validate_setup.py` to verify setup
2. Run `python list_tabs.py` to verify Google Sheets access
3. Run `python run_audit.py --tab "Test Tab"` with a small set of URLs
4. Verify results in spreadsheet
5. Check logs in `logs/` directory

## Debugging

### Enable Verbose Logging
Logs are automatically saved to `logs/audit_YYYYMMDD_HHMMSS.log`.

### Test Cypress Manually
```bash
npx cypress open
```
Run the `analyze-url.cy.js` test in the Cypress UI to see what's happening.

### Check Results Files
Results JSON files in `cypress/results/` show what data was extracted.

### Common Issues
1. **UnicodeDecodeError**: Fixed by adding `encoding='utf-8', errors='replace'` to subprocess calls
2. **No results file found**: Cypress failed silently - check Cypress logs
3. **Timeout errors**: Increase timeout with `--timeout 600`
4. **Permission denied**: Verify spreadsheet is shared with service account email

## Dependencies

### Python (requirements.txt)
- `google-auth`: Authentication
- `google-auth-oauthlib`: OAuth2 flows
- `google-auth-httplib2`: HTTP transport
- `google-api-python-client`: Google Sheets API
- `python-dotenv`: Environment variables (optional)
- `argparse`: Command-line parsing (built-in)

### Node.js (package.json)
- `cypress`: Browser automation

## Security

- Service account credentials (`service-account.json`) must never be committed
- `.gitignore` excludes all `*service-account*.json` files
- Service accounts should have minimal permissions (only Sheets access needed)
- Spreadsheets should only be shared with necessary service accounts

## Limitations

- Rate limits: Google Sheets API has quotas (100 requests per 100 seconds per user)
- PageSpeed Insights may rate-limit high-volume usage
- Cypress requires a browser and graphics environment (use Xvfb on headless Linux)
- Windows encoding issues are mitigated but may still occur with exotic characters
- URLs must be in column A starting at row 2
- Results always written to columns F and G (not configurable via CLI)
