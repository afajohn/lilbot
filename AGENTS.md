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
# Optional: Specify custom timeout (default: 600 seconds)
python run_audit.py --tab "TAB_NAME" --timeout 1200
# Optional: Skip cache for fresh analysis
python run_audit.py --tab "TAB_NAME" --skip-cache
```

**Cache Management:**
```bash
# Invalidate specific URL cache
python invalidate_cache.py --url "https://example.com"
# Clear all cache entries
python invalidate_cache.py --all
```

**Build:** Not applicable (Python script)

**Lint:** Not configured

**Test:** 
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tools --cov=run_audit --cov-report=term-missing

# Using convenience scripts
python -m pytest  # Or use run_tests.ps1 (Windows) or ./run_tests.sh (Unix)
```

**Dev Server:** Not applicable (CLI tool)

## Tech Stack

- **Language**: Python 3.7+
- **Browser Automation**: Cypress (JavaScript/Node.js)
- **APIs**: Google Sheets API v4
- **Caching**: Redis (with file-based fallback)
- **Key Libraries**:
  - `google-api-python-client` - Google Sheets integration
  - `google-auth` - Authentication
  - `redis` - Redis caching backend (optional)
  - Cypress - Browser automation for PageSpeed Insights

## Performance Optimizations

The system has been optimized for faster URL processing:

1. **Result Caching**: Redis/file-based cache with 24-hour TTL and LRU eviction (1000 entries max)
2. **Reduced Timeouts**: Default timeout reduced from 900s to 600s with optimized Cypress timeouts
3. **Fewer Retries**: Cypress retries reduced from 5 to 2, Python retries from 10 to 3
4. **Faster Waits**: Inter-action waits reduced from 5-15s to 2s
5. **Incremental Updates**: Spreadsheet updates happen immediately after each URL (not batched at end)
6. **Explicit Headless Mode**: Cypress runs in headless mode with explicit flags
7. **Optimized Analysis**: PageSpeed Insights runs once, then switches between Mobile/Desktop views

**Key Issue Resolved**: Running `npx cypress open` while `run_audit.py` is executing blocks the headless Cypress instance. Always close the Cypress UI before running audits.

## Architecture

### Project Structure

```
.
├── run_audit.py              # Main entry point - orchestrates the audit
├── list_tabs.py              # Utility to list spreadsheet tabs
├── get_service_account_email.py  # Utility to get service account email
├── validate_setup.py         # Setup validation script
├── invalidate_cache.py       # Cache invalidation utility
├── tools/
│   ├── sheets/
│   │   └── sheets_client.py  # Google Sheets API wrapper
│   ├── qa/
│   │   └── cypress_runner.py # Cypress automation wrapper
│   ├── cache/
│   │   └── cache_manager.py  # Cache layer (Redis + file backend)
│   └── utils/
│       └── logger.py         # Logging utilities
├── cypress/
│   ├── e2e/
│   │   └── analyze-url.cy.js # PageSpeed Insights test automation
│   └── results/              # Generated JSON results (gitignored)
└── .cache/                   # File cache storage (gitignored)
```

### Data Flow

1. **Input**: URLs from Google Sheets column A (starting row 2)
2. **Processing**:
   - `run_audit.py` reads URLs via `sheets_client.py`
   - For each URL, `cypress_runner.py` checks cache first (unless `--skip-cache`)
   - On cache miss, launches Cypress (retries up to 3 times on failure)
   - Results are cached with 24-hour TTL for future runs
   - Cypress navigates to PageSpeed Insights and extracts scores from `.lh-exp-gauge__percentage`
   - Results saved to JSON files in `cypress/results/`
   - **Incremental updates**: Spreadsheet is updated immediately after each URL is analyzed (not batched at the end)
3. **Output**: 
   - For scores >= 80: Cell is filled with the text "passed"
   - For scores < 80: PSI URLs written to columns F (mobile) and G (desktop)
   - Each URL's results are written to the sheet immediately upon completion

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
- Handles timeouts and retries (up to 3 retry attempts with fixed 5s wait)
- Parses JSON results
- Default timeout: 600 seconds (10 minutes)
- **Critical Fix**: Uses `encoding='utf-8', errors='replace'` to prevent Windows UnicodeDecodeError
- Runs Cypress in explicit headless mode for better performance

#### analyze-url.cy.js
- Cypress test that automates PageSpeed Insights
- **URL Validation**: Pre-checks URL accessibility before analysis (30s timeout)
- Visits pagespeed.web.dev
- **Smart Selectors**: Uses data-testid attributes with fallbacks to brittle text-based selectors
- **Viewport Detection**: Detects and logs viewport changes for responsive UI handling
- Enters URL and triggers analysis (both mobile and desktop results available after single analysis)
- **Smart Wait**: Polls for score elements with configurable intervals (max 120s, poll every 2s)
- Switches between Mobile/Desktop views to extract scores with fallback selector hierarchy
- Collects report URLs for scores < 80
- **Screenshot on Failure**: Automatically captures full-page screenshots when tests fail
- Saves results to JSON
- Configured with 2 automatic retries on failure (reduced from 5)
- Optimized timeout values (defaultCommandTimeout: 10s, pageLoadTimeout: 120s)
- Reduced wait times between actions for faster execution

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
- Cypress internal retries: 2 attempts per run (configured in cypress.config.js)
- Python runner retries: Up to 3 attempts with fixed 5s wait between attempts
- Total possible attempts: Up to 12 (2 × 3 + initial attempts)

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
- Default timeout: 600 seconds (can be overridden with --timeout flag)

### Environment Variables
Cache behavior can be configured via environment variables (see `.env.example`):
- `REDIS_HOST`: Redis server host (default: localhost)
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_PASSWORD`: Redis authentication password (optional)
- `CACHE_DIR`: File cache directory (default: .cache)
- `CACHE_MAX_ENTRIES`: Maximum file cache entries (default: 1000)

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
3. Current key selectors (with fallback hierarchy):
   - URL input: `[data-testid="url-input"]` → `input[name="url"]`
   - Analyze button: `[data-testid*="analyze"]` → `button` containing text matching `/analyze/i`
   - Score display: `[data-testid="score-gauge"]` → `.lh-exp-gauge__percentage` → `.lh-gauge__percentage`
   - Mobile/Desktop toggle: `[data-testid*="mobile/desktop"]` → `button` containing 'Mobile' or 'Desktop'
4. Test with `npx cypress open`

### Adding More Retry Attempts
1. Modify `max_retries` parameter in `cypress_runner.py` `run_analysis()` function (default: 3)
2. Modify `retries.runMode` in `cypress.config.js` (default: 2)
3. Adjust timeout with `--timeout` flag when running `run_audit.py` (default: 600 seconds)

## Testing

### Automated Test Suite

A comprehensive test suite is available with 70% code coverage target:

**Quick Start:**
```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage report
pytest --cov=tools --cov=run_audit --cov-report=term-missing

# Check coverage threshold (70%)
pytest --cov=tools --cov=run_audit --cov-report=term-missing
coverage report --fail-under=70

# Generate HTML coverage report
pytest --cov=tools --cov=run_audit --cov-report=html
```

**Using Convenience Scripts:**
```bash
# Windows (PowerShell)
.\run_tests.ps1                  # Run all tests
.\run_tests.ps1 unit -Verbose    # Run unit tests with verbose output
.\run_tests.ps1 coverage -Html   # Run with HTML coverage report

# Unix/Linux/Mac
./run_tests.sh                   # Run all tests
./run_tests.sh unit --verbose    # Run unit tests with verbose output
./run_tests.sh coverage --html   # Run with HTML coverage report

# Or use Make (Unix/Linux/Mac)
make test                        # Run all tests
make test-unit                   # Run unit tests
make test-cov                    # Run with coverage
make test-cov-check              # Run and check 70% threshold
```

**Test Structure:**
- `tests/unit/test_sheets_client.py` - Google Sheets API wrapper tests
- `tests/unit/test_cypress_runner.py` - Cypress automation tests
- `tests/unit/test_logger.py` - Logging utilities tests
- `tests/integration/test_run_audit.py` - Main audit orchestration tests
- `tests/conftest.py` - Shared fixtures and test configuration

**Continuous Integration:**
Tests run automatically on GitHub Actions for every push and pull request, testing against Python 3.8, 3.9, 3.10, and 3.11.

### Manual Testing Workflow

For manual end-to-end testing:

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
3. **Timeout errors**: Increase timeout with `--timeout 900` or higher
4. **Permission denied**: Verify spreadsheet is shared with service account email
5. **Running `npx cypress open` while `run_audit.py` is running**: These conflict because Cypress can only run one instance at a time. Close the Cypress UI before running the audit script.
6. **Slow processing**: Ensure you're not running `npx cypress open` simultaneously, which blocks the headless execution
7. **Cache issues**: See CACHE_GUIDE.md for troubleshooting cache-related problems

## Dependencies

### Python (requirements.txt)
- `google-auth`: Authentication
- `google-auth-oauthlib`: OAuth2 flows
- `google-auth-httplib2`: HTTP transport
- `google-api-python-client`: Google Sheets API
- `python-dotenv`: Environment variables (optional)
- `redis`: Redis client for caching (optional, falls back to file cache)
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
