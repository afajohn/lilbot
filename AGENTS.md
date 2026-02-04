# Agent Development Guide

## Commands

**Setup:**
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright and browsers
pip install playwright
playwright install chromium
```

**Run Audit:**
```bash
# Basic usage
python run_audit.py --tab "TAB_NAME" --service-account "service-account.json"

# Recommended: High-performance mode with 15 workers
python run_audit.py --tab "TAB_NAME" --concurrency 15

# Optional: Custom timeout (default: 600 seconds)
python run_audit.py --tab "TAB_NAME" --timeout 1200

# Optional: Debug mode (verbose logging, screenshots on errors)
python run_audit.py --tab "TAB_NAME" --debug-mode

# Optional: Start from specific row
python run_audit.py --tab "TAB_NAME" --start-row 100

# Example: Maximum throughput
python run_audit.py --tab "TAB_NAME" --concurrency 20 --timeout 900
```

**List Spreadsheet Tabs:**
```bash
python list_tabs.py --spreadsheet-id "YOUR_ID" --service-account "service-account.json"
```

**Build:** Not applicable (Python script)

**Lint:** Not configured

**Test:** 
```bash
pytest
pytest --cov=tools --cov=run_audit --cov-report=term-missing
```

**Dev Server:** Not applicable (CLI tool)

## Tech Stack

- **Language**: Python 3.7+
- **Browser Automation**: Playwright (Python) with async/await
- **Parallel Execution**: Worker pool with concurrent URL processing
- **APIs**: Google Sheets API v4
- **Key Libraries**:
  - `google-api-python-client` - Google Sheets integration
  - `google-auth` - Authentication
  - `playwright` - Browser automation for PageSpeed Insights
  - `concurrent.futures` - Worker pool for parallel execution

## Architecture Overview

### Parallel Processing

The system uses a worker pool architecture for high-throughput URL processing:

**Components:**
- **Main Thread**: Distributes URLs to workers, collects results
- **Worker Pool**: Multiple workers (default: 5, configurable 1-20+)
- **Worker Thread**: Each runs asyncio event loop for Playwright operations
- **Browser Instances**: Each worker has its own independent Chromium instance
- **Thread Isolation**: Each worker maintains strict thread isolation

**Why Parallel Execution?**
- Browser automation is I/O-bound (ideal for concurrent execution)
- Each worker has isolated event loop thread (prevents threading conflicts)
- Independent browser instances (no resource contention)
- Scalable performance: 600-800 URLs/hour with 15 workers

**Threading Flow:**
```
Main Thread                 Worker 1              Worker 2              Worker N
-----------                 --------              --------              --------
1. Submit URLs to pool      (Event loop)          (Event loop)          (Event loop)
   → url1                   Process url1          Process url2          Process url3
   → url2                   - page.goto()         - page.goto()         - page.goto()
   → url3                   - click buttons       - click buttons       - click buttons
                            - extract scores      - extract scores      - extract scores
2. Collect results          ← Result 1            ← Result 2            ← Result N
3. Update spreadsheet
4. Repeat
```

### Performance Characteristics

**Expected Throughput:**
- **~4-6 seconds per URL** with parallel processing
- **600-800 URLs per hour** with 15 workers
- **400-500 URLs per hour** with 10 workers
- **200-300 URLs per hour** with 5 workers (default)
- **40-60 URLs per hour** with 1 worker (sequential mode)

**Concurrency Scaling:**
- Linear scaling up to 10-15 workers
- Diminishing returns beyond 15 workers (network/API bottleneck)
- Optimal: 10-15 workers for most systems

### System Requirements

| Workers | Minimum RAM | Recommended RAM | Expected Throughput |
|---------|-------------|-----------------|---------------------|
| 1-5     | 4GB         | 8GB             | 200-300 URLs/hour   |
| 6-10    | 8GB         | 16GB            | 400-500 URLs/hour   |
| 11-15   | 16GB        | 32GB            | 600-800 URLs/hour   |
| 16-20   | 32GB        | 64GB            | 700-900 URLs/hour   |

## Error Handling

### Debug Mode (`--debug-mode`)

When enabled:
- Captures screenshots on failures (`debug_screenshots/`)
- Saves page HTML for analysis
- Enables verbose Playwright logging
- Enhanced error messages with diagnostic information

### Recovery Strategies

1. **Selector Timeout**: Retries with page reload (up to 3 attempts)
2. **Analysis Timeout**: Aborts immediately (not retryable)
3. **Button Not Found**: Reloads page and retries
4. **Score Extraction Failed**: Captures debug artifacts

## Data Flow

1. **Input**: Read URLs from column A (starting row 2)
2. **Processing**:
   - Distribute URLs across worker pool
   - Each worker runs PageSpeed Insights analysis via Playwright
   - Extract mobile and desktop scores
   - Workers return results to main thread
3. **Output**:
   - Scores ≥80: Write `"passed"` to columns F/G
   - Scores <80: Write PageSpeed Insights URLs to columns F/G
   - Update spreadsheet immediately after each URL

**PageSpeed Insights Workflow:**
1. Open https://pagespeed.web.dev
2. Enter target URL and start analysis
3. Wait for analysis to complete (up to 30 seconds)
4. Click "Mobile" button and extract score
5. Click "Desktop" button and extract score
6. Return results

## Skip Logic

URLs are **skipped** when BOTH conditions are true:
1. Column F contains `"passed"` OR has green background (RGB: 0, 255, 0)
2. Column G contains `"passed"` OR has green background (RGB: 0, 255, 0)

URLs are **analyzed** when ANY of these are true:
- Either column F or G is empty
- Either column contains a PageSpeed Insights URL
- Either column contains text other than `"passed"` without green background

**Examples:**

| Column F | Column G | Skip? | Reason |
|----------|----------|-------|--------|
| `passed` | `passed` | ✅ YES | Both passed |
| `passed` | 🟩 green | ✅ YES | Both passed |
| `passed` | (empty) | ❌ NO | Desktop not done |
| `passed` | PSI URL | ❌ NO | Desktop failed |
| PSI URL | PSI URL | ❌ NO | Both failed |

## Troubleshooting

### PageSpeed Insights Selector Issues

**Problem**: "Failed to find Mobile/Desktop toggle buttons"
- **Cause**: Buttons don't appear until analysis completes
- **Solution**: Increase timeout (`--timeout 1200`), enable debug mode (`--debug-mode`)

**Problem**: "Score extraction failed"
- **Cause**: PageSpeed Insights UI changed or element not visible
- **Solution**: Enable debug mode, check saved HTML in `debug_screenshots/`, verify PSI is accessible

**Problem**: "Analysis timeout after 30 seconds"
- **Cause**: Target website takes too long to analyze
- **Solution**: Increase overall timeout for retries (`--timeout 1200`), test URL manually at https://pagespeed.web.dev

### Memory Issues

**Symptoms**:
- System running out of memory
- Browser crashes with "Out of memory" errors
- Analysis becoming slower over time

**Solutions**:
- Reduce concurrency to match available RAM
- 4GB RAM → `--concurrency 2`
- 8GB RAM → `--concurrency 5`
- 16GB RAM → `--concurrency 10`
- 32GB+ RAM → `--concurrency 15-20`

### Rate Limiting

**Problem**: "Rate limit exceeded" errors
- **Cause**: Too many concurrent requests to PageSpeed Insights
- **Solution**: Reduce concurrency (`--concurrency 10`), wait a few minutes and retry

### Worker Pool Issues

**Problem**: Workers not starting or hanging
- **Solution**: Check available memory, reduce concurrency, enable debug mode, restart application

**Problem**: Performance not scaling with concurrency
- **Cause**: CPU/network bottleneck, API rate limiting
- **Solution**: Find optimal concurrency by testing incrementally, monitor system resources

## Timeout Configuration

Recommended timeout values based on network conditions:

| Network Speed | Timeout | Command |
|--------------|---------|---------|
| Fast | 600s | `--timeout 600` (default) |
| Average | 900s | `--timeout 900` |
| Slow | 1200s | `--timeout 1200` |
| Very Slow | 1800s | `--timeout 1800` |

## Performance Tuning

### Finding Optimal Concurrency

1. **Start Conservative**: `--concurrency 5`
2. **Monitor Resources**: CPU 60-80%, stable memory
3. **Increase Gradually**: Add 2-5 workers at a time
4. **Find Sweet Spot**: Throughput plateaus = optimal found

### Recommended Starting Points

- **4GB RAM, 2 cores**: `--concurrency 2`
- **8GB RAM, 4 cores**: `--concurrency 5` (default)
- **16GB RAM, 8 cores**: `--concurrency 10`
- **32GB+ RAM, 16+ cores**: `--concurrency 15-20`

## Project Structure

```
.
├── run_audit.py              # Main entry point
├── list_tabs.py              # List spreadsheet tabs utility
├── get_service_account_email.py  # Get service account email
├── requirements.txt          # Python dependencies
├── tools/
│   ├── sheets/
│   │   └── sheets_client.py  # Google Sheets API wrapper
│   ├── qa/
│   │   └── playwright_runner.py  # Playwright automation
│   └── utils/
│       └── logger.py         # Logging utilities
└── logs/                     # Audit logs (gitignored)
```

## Key Components

### run_audit.py
- Main orchestrator
- Handles command-line arguments
- Manages worker pool and URL distribution
- Collects and reports statistics

### sheets_client.py
- Authenticates with Google Sheets API
- Reads URLs from spreadsheet (range A2:A)
- Writes results back to spreadsheet
- Handles API errors

### playwright_runner.py
- Manages Playwright browser instances
- Runs PageSpeed Insights analysis
- Automatic retry with exponential backoff
- Page reload recovery on failures
- Debug mode support with screenshots
- Performance tracking

### logger.py
- Sets up logging to console and file
- Creates timestamped log files in `logs/` directory

## Code Style

- Follow PEP 8 for Python code
- Use type hints for function parameters
- Handle errors gracefully with informative messages
- Use f-strings for string formatting
- Keep functions focused and single-purpose

## Important Implementation Details

### Unicode Encoding
All subprocess calls include `encoding='utf-8', errors='replace'` to prevent Windows encoding errors.

### Spreadsheet Range
URLs are read from `A2:A` (not `A:A`) to skip header row. Row enumeration starts at 2.

### Error Handling
- Catch specific exceptions
- Provide actionable error messages
- Log full tracebacks for debugging
- Continue processing remaining URLs even if one fails

### Retry Logic
- Infinite retry with exponential backoff for retryable errors
- Analysis timeout → aborts immediately (not retryable)
- Selector timeout → retries with fresh page load
- Exponential backoff: 5s → 10s → 20s → 60s max

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tools --cov=run_audit --cov-report=term-missing

# Using convenience scripts
python -m pytest
```

## Debugging

### Enable Verbose Logging
Logs are automatically saved to `logs/audit_YYYYMMDD_HHMMSS.log`.

### Test Playwright Manually
```bash
# Generate test code interactively
playwright codegen https://pagespeed.web.dev
```

### Common Issues
1. **Timeout errors**: Increase timeout with `--timeout 900`
2. **Permission denied**: Verify spreadsheet is shared with service account
3. **Browser not found**: Run `playwright install chromium`
4. **Memory issues**: Reduce concurrency to match available RAM

## Configuration

### Constants in run_audit.py
- `DEFAULT_SPREADSHEET_ID`: Default Google Sheets ID
- `SERVICE_ACCOUNT_FILE`: Default service account path
- `MOBILE_COLUMN`: Mobile results column (default: 'F')
- `DESKTOP_COLUMN`: Desktop results column (default: 'G')
- `SCORE_THRESHOLD`: Minimum passing score (default: 80)
- Default timeout: 600 seconds

## Limitations

- **Performance**: 4-6 seconds per URL (parallel), 600-800 URLs/hour with 15 workers
- **Memory**: Higher concurrency requires more RAM (see requirements table)
- **Internet Connection**: Requires active internet connection
- **PageSpeed Insights**: May rate-limit high-volume usage
- **URLs**: Must be in column A starting from row 2
- **Results**: Always written to columns F and G
- **Concurrency**: Maximum practical concurrency ~20 workers
