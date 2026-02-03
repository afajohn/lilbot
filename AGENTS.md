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
# Optional: Dry run mode (simulate without changes)
python run_audit.py --tab "TAB_NAME" --dry-run
# Optional: URL filtering
python run_audit.py --tab "TAB_NAME" --whitelist "https://example.com/*" --blacklist "http://*"
# Optional: Validation only mode (no audit execution)
python run_audit.py --tab "TAB_NAME" --validate-only
# Optional: Skip DNS and redirect validation
python run_audit.py --tab "TAB_NAME" --skip-dns-validation --skip-redirect-validation
# Optional: Custom DNS and redirect timeouts
python run_audit.py --tab "TAB_NAME" --dns-timeout 10 --redirect-timeout 15
```

**Validate Service Account:**
```bash
python validate_service_account.py service-account.json
```

**Query Audit Trail:**
```bash
# View all modifications
python query_audit_trail.py

# Filter by spreadsheet and date
python query_audit_trail.py --spreadsheet-id "YOUR_ID" --start-date "2024-01-01"

# Show detailed output
python query_audit_trail.py --format detailed --limit 10
```

**Cache Management:**
```bash
# Invalidate specific URL cache
python invalidate_cache.py --url "https://example.com"
# Clear all cache entries
python invalidate_cache.py --all
```

**Metrics and Monitoring:**
```bash
# Metrics are automatically collected during audits
# Generate HTML dashboard with charts
python generate_report.py
# Generate from specific metrics file
python generate_report.py --input metrics.json --output dashboard.html
# Export Prometheus metrics
python generate_report.py --export-prometheus metrics.prom
# Export JSON metrics
python generate_report.py --export-json metrics.json
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
- **Monitoring**: Prometheus-compatible metrics, Plotly dashboards
- **Security**: Service account validation, rate limiting, URL filtering, audit trail
- **Key Libraries**:
  - `google-api-python-client` - Google Sheets integration
  - `google-auth` - Authentication
  - `redis` - Redis caching backend (optional)
  - `plotly` - Interactive dashboard charts
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
├── generate_report.py        # Generate HTML metrics dashboard
├── list_tabs.py              # Utility to list spreadsheet tabs
├── get_service_account_email.py  # Utility to get service account email
├── validate_setup.py         # Setup validation script
├── invalidate_cache.py       # Cache invalidation utility
├── tools/
│   ├── metrics/
│   │   └── metrics_collector.py  # Prometheus-compatible metrics collection
│   ├── sheets/
│   │   ├── sheets_client.py  # Google Sheets API wrapper
│   │   ├── schema_validator.py  # Spreadsheet schema validation
│   │   └── data_quality_checker.py  # Duplicate URL and data quality checks
│   ├── qa/
│   │   └── cypress_runner.py # Cypress automation wrapper
│   ├── cache/
│   │   └── cache_manager.py  # Cache layer (Redis + file backend)
│   ├── security/
│   │   ├── service_account_validator.py  # Service account validation
│   │   ├── url_filter.py     # URL whitelist/blacklist filtering
│   │   ├── audit_trail.py    # Audit trail logging
│   │   └── rate_limiter.py   # Per-spreadsheet rate limiting
│   └── utils/
│       ├── logger.py         # Logging utilities
│       └── url_validator.py  # URL validation (regex, DNS, redirects) and normalization
├── cypress/
│   ├── e2e/
│   │   └── analyze-url.cy.js # PageSpeed Insights test automation
│   └── results/              # Generated JSON results (gitignored)
├── .cache/                   # File cache storage (gitignored)
├── metrics.json              # JSON metrics export (gitignored)
├── metrics.prom              # Prometheus metrics export (gitignored)
├── dashboard.html            # HTML metrics dashboard (gitignored)
├── audit_trail.jsonl         # Audit trail log (gitignored)
├── validate_service_account.py  # Service account validator utility
├── query_audit_trail.py      # Audit trail query utility
└── SECURITY.md               # Security features documentation
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
   - **Metrics export**: `metrics.json` and `metrics.prom` files generated
   - **Dashboard**: HTML dashboard can be generated with `generate_report.py`
   - **Alerting**: Warnings logged if failure rate exceeds 20%

### Key Components

#### run_audit.py
- Main orchestrator
- Handles command-line arguments
- Performs schema and data quality validation on startup
- URL validation with DNS and redirect checks
- URL normalization before analysis
- Manages the audit loop
- Collects and reports statistics
- Supports `--validate-only` mode for validation without audit execution

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

#### url_validator.py
- URL format validation with comprehensive regex
- DNS resolution validation with configurable timeout
- Redirect chain detection (flags chains >3 redirects)
- URL normalization (trailing slashes, query params, case)
- URLNormalizer class for consistent URL formatting

#### schema_validator.py
- Validates spreadsheet schema on startup
- Checks for required columns (A-G)
- Verifies header row presence
- Ensures data rows exist

#### data_quality_checker.py
- Detects exact duplicate URLs
- Detects normalized duplicates (URLs that normalize to same value)
- Reports empty URLs
- Generates detailed duplicate reports with row numbers

#### metrics_collector.py
- Thread-safe metrics collection
- Tracks success/failure rates, processing time, cache efficiency
- Monitors API quota usage (Sheets and Cypress)
- Prometheus-compatible export format
- JSON export for dashboards
- Automatic alerting when failure rate exceeds 20%
- Records failure reasons for analysis

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

## Input Validation and Data Quality

### Validation Features

The system includes comprehensive input validation and data quality checks:

1. **URL Format Validation**
   - Regex-based URL format checking
   - Scheme validation (http/https)
   - Domain/hostname validation
   - Dangerous character detection

2. **DNS Resolution**
   - Verifies domain resolves to IP address
   - Configurable timeout (default: 5s, use `--dns-timeout`)
   - Can be disabled with `--skip-dns-validation`

3. **Redirect Chain Detection**
   - Detects HTTP redirects
   - Flags URLs with >3 redirects
   - Configurable timeout (default: 10s, use `--redirect-timeout`)
   - Can be disabled with `--skip-redirect-validation`

4. **URL Normalization**
   - Converts scheme and domain to lowercase
   - Normalizes trailing slashes
   - Sorts query parameters alphabetically
   - Applied automatically before analysis

5. **Duplicate URL Detection**
   - Detects exact duplicates
   - Detects normalized duplicates (minor variations)
   - Reports duplicate groups with row numbers
   - Runs on every audit startup

6. **Spreadsheet Schema Validation**
   - Validates column structure (A-G required)
   - Checks header row presence
   - Ensures data rows exist
   - Runs automatically on startup

### Validation-Only Mode

Use `--validate-only` to run validations without executing the audit:

```bash
python run_audit.py --tab "TAB_NAME" --validate-only
```

This mode performs:
- Schema validation
- Data quality checks (duplicates, empty URLs)
- URL validation (format, DNS, redirects) for all URLs
- Detailed validation report with pass/fail status

Useful for:
- Pre-flight checks before running expensive audits
- Identifying data quality issues
- Testing URL accessibility
- Detecting redirect chains

## Configuration

### Constants in run_audit.py
- `DEFAULT_SPREADSHEET_ID`: Default Google Sheets ID
- `SERVICE_ACCOUNT_FILE`: Default service account path
- `MOBILE_COLUMN`: Column for mobile results (default: 'F')
- `DESKTOP_COLUMN`: Column for desktop results (default: 'G')
- `SCORE_THRESHOLD`: Minimum passing score (default: 80)
- Default timeout: 600 seconds (can be overridden with --timeout flag)

### Validation Configuration
- `--dns-timeout`: DNS resolution timeout in seconds (default: 5.0)
- `--redirect-timeout`: Redirect check timeout in seconds (default: 10.0)
- `--skip-dns-validation`: Disable DNS resolution checks
- `--skip-redirect-validation`: Disable redirect chain checks
- `--validate-only`: Run validation without audit execution

### Security Configuration
- `RATE_LIMIT_REQUESTS_PER_MINUTE`: API rate limit per spreadsheet (default: 60)
- `AUDIT_TRAIL_PATH`: Path to audit trail log file (default: audit_trail.jsonl)
- `URL_WHITELIST`: Comma-separated URL patterns to allow
- `URL_BLACKLIST`: Comma-separated URL patterns to block

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
- `plotly`: Interactive dashboard charts and visualizations
- `argparse`: Command-line parsing (built-in)

### Node.js (package.json)
- `cypress`: Browser automation

## Security

### Credentials
- Service account credentials (`service-account.json`) must never be committed
- `.gitignore` excludes all `*service-account*.json` files
- Service accounts should have minimal permissions (only Sheets access needed)
- Spreadsheets should only be shared with necessary service accounts

### Security Features
See `SECURITY.md` for detailed documentation on:

1. **Service Account Validation**
   - Validates required fields in service account JSON
   - Checks private key format and email format
   - Automatic validation during authentication

2. **API Rate Limiting**
   - Per-spreadsheet rate limiting (60 req/min default)
   - Token bucket algorithm with burst tolerance
   - Prevents API quota exhaustion

3. **URL Filtering**
   - Whitelist support: `--whitelist "https://example.com/*"`
   - Blacklist support: `--blacklist "http://*"`
   - Pattern-based with wildcard support

4. **URL Sanitization**
   - Validates URL format before processing
   - Blocks dangerous characters
   - Normalizes protocols

5. **Audit Trail**
   - Logs all spreadsheet modifications
   - JSON Lines format with timestamps
   - Includes user, operation, location, and value
   - Query with `query_audit_trail.py`

6. **Dry Run Mode**
   - Simulate operations without changes: `--dry-run`
   - Test filters and validation
   - Review before execution

## Monitoring and Metrics

The system includes comprehensive monitoring:

### Metrics Collected
- **Success/Failure Rates**: Track audit success percentage and identify issues
- **Processing Time**: Monitor average time per URL analysis
- **API Quota Usage**: Count Sheets API and Cypress API calls to stay within limits
- **Cache Hit Ratio**: Measure cache efficiency (target >70%)
- **Failure Reasons**: Categorize failures (timeout, cypress, permanent, etc.)
- **Alerting**: Automatic alerts when failure rate exceeds 20%

### Metrics Formats
- **Prometheus**: Text format compatible with Prometheus monitoring
- **JSON**: Structured data for dashboards and analysis
- **HTML Dashboard**: Interactive charts using Plotly

### Usage
```bash
# Run audit (metrics collected automatically)
python run_audit.py --tab "Your Tab"

# Generate interactive dashboard
python generate_report.py

# View metrics
cat metrics.json | python -m json.tool
cat metrics.prom
```

For detailed metrics documentation, see `METRICS_GUIDE.md` and `METRICS_QUICK_REFERENCE.md`.

## Limitations

- Rate limits: Google Sheets API has quotas (100 requests per 100 seconds per user)
- PageSpeed Insights may rate-limit high-volume usage
- Cypress requires a browser and graphics environment (use Xvfb on headless Linux)
- Windows encoding issues are mitigated but may still occur with exotic characters
- URLs must be in column A starting at row 2
- Results always written to columns F and G (not configurable via CLI)
- Dashboard requires plotly library for chart generation
