# PageSpeed Insights Audit Tool

Automated tool for running PageSpeed Insights audits on URLs from Google Sheets.

## Quick Reference

### Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright and Chromium browser
pip install playwright
playwright install chromium
```

### Basic Usage

```bash
python run_audit.py --tab "SheetName" --service-account service-account.json --concurrency 15
```

### Expected Performance

- **600-800 URLs per hour** with 15 concurrent workers
- **~4-6 seconds per URL** average processing time
- **Scalable**: 1-20+ concurrent workers depending on system resources

### System Requirements

| Workers | Minimum RAM | Recommended RAM | CPU Cores |
|---------|-------------|-----------------|-----------|
| 1-5     | 4GB         | 8GB             | 2+        |
| 6-10    | 8GB         | 16GB            | 4+        |
| 11-15   | 16GB        | 32GB            | 8+        |
| 16-20   | 32GB        | 64GB            | 16+       |

## Setup

### 1. Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a service account
3. Download JSON key and save as `service-account.json`
4. Enable Google Sheets API
5. Share your spreadsheet with the service account email (found in JSON file)

### 2. Spreadsheet Format

The tool expects:
- **Column A**: URLs to analyze (starting from row 2)
- **Column F**: Mobile results (populated by tool)
- **Column G**: Desktop results (populated by tool)

Results:
- Scores ≥80: `"passed"`
- Scores <80: PageSpeed Insights URL

## Usage Examples

```bash
# Basic usage with 15 workers (recommended for production)
python run_audit.py --tab "Production Sites" --concurrency 15

# Conservative mode for limited resources (8GB RAM)
python run_audit.py --tab "Test Sites" --concurrency 5

# Maximum throughput mode (32GB+ RAM)
python run_audit.py --tab "Large Audit" --concurrency 20

# Increase timeout for slow connections
python run_audit.py --tab "Sites" --timeout 1200 --concurrency 15

# Start from specific row (resume interrupted audit)
python run_audit.py --tab "Sites" --start-row 100 --concurrency 15
```

## Command-Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--tab` | (required) | Spreadsheet tab name |
| `--service-account` | `service-account.json` | Path to service account JSON |
| `--concurrency` | `5` | Number of parallel workers (1-20+) |
| `--timeout` | `600` | Timeout per URL in seconds |
| `--start-row` | `2` | Starting row number |
| `--debug-mode` | `False` | Enable debug logging and screenshots |

## Troubleshooting

### PageSpeed Insights Selector Issues

**Problem**: "Failed to find Mobile/Desktop toggle buttons"

**Solution**:
- Increase timeout: `--timeout 1200`
- Enable debug mode: `--debug-mode` to capture screenshots
- Check `debug_screenshots/` directory for page state

**Problem**: "Score extraction failed"

**Solution**:
- Enable debug mode to capture page HTML
- Verify PageSpeed Insights is accessible at https://pagespeed.web.dev
- Check for UI changes to the PageSpeed Insights interface

**Problem**: "Analysis timeout after 30 seconds"

**Solution**:
- Increase overall timeout to allow retries: `--timeout 1200`
- Check if target URL is accessible and responding
- Test URL manually at https://pagespeed.web.dev

### Timeout Adjustments

Recommended timeout values based on network conditions:
- **Fast connection**: 600 seconds (default)
- **Average connection**: 900 seconds
- **Slow connection**: 1200 seconds
- **Very slow connection**: 1800 seconds

### Memory Issues

**Problem**: System running out of memory with high concurrency

**Solution**:
- Reduce concurrency to match available RAM (see requirements table)
- Use 8GB RAM → `--concurrency 5`
- Use 16GB RAM → `--concurrency 10`
- Use 32GB+ RAM → `--concurrency 15-20`

### Rate Limiting

**Problem**: "Rate limit exceeded" errors

**Solution**:
- Reduce concurrency: `--concurrency 10`
- PageSpeed Insights may be throttling requests
- Wait a few minutes and retry

## How It Works

1. **Read URLs**: Reads URLs from column A of specified spreadsheet tab
2. **Parallel Processing**: Distributes URLs across worker pool (configurable concurrency)
3. **PageSpeed Analysis**: Each worker automates PageSpeed Insights via Playwright
4. **Extract Scores**: Extracts mobile and desktop performance scores
5. **Write Results**: Updates columns F and G with "passed" or PageSpeed URLs

## Architecture

### Parallel Processing

- **Worker Pool**: Multiple workers process URLs concurrently
- **Independent Browsers**: Each worker has its own Chromium instance
- **Thread Isolation**: Each worker runs in dedicated event loop thread
- **Result Aggregation**: Main thread collects and writes results

### Performance Optimization

- Parallel execution with configurable worker pool
- Optimized Playwright wait times and timeouts
- Headless Chromium for efficiency
- Incremental spreadsheet updates

## Project Structure

```
.
├── run_audit.py              # Main entry point
├── list_tabs.py              # List spreadsheet tabs
├── requirements.txt          # Python dependencies
├── service-account.json      # Google credentials (not in repo)
└── tools/
    ├── sheets/
    │   └── sheets_client.py  # Google Sheets API wrapper
    └── qa/
        └── playwright_runner.py  # Playwright automation
```

## Common Issues

**Service account file not found**
- Verify `service-account.json` exists in project root
- Use `--service-account` to specify custom path

**Tab not found**
- Run `python list_tabs.py` to see available tabs
- Verify tab name matches exactly (case-sensitive)

**Permission denied**
- Ensure spreadsheet is shared with service account email
- Grant "Editor" permissions

**Browser not found**
- Run: `playwright install chromium`

## Utilities

```bash
# List all tabs in spreadsheet
python list_tabs.py --service-account service-account.json

# Get service account email (for sharing spreadsheet)
python get_service_account_email.py
```

## Performance Tuning

### Finding Optimal Concurrency

Start conservative and increase gradually:

```bash
# Step 1: Start low
python run_audit.py --tab "Test" --concurrency 5

# Step 2: Monitor system resources (CPU 60-80%, stable memory)

# Step 3: Increase if stable
python run_audit.py --tab "Test" --concurrency 10

# Step 4: Continue until throughput plateaus or system becomes unstable
python run_audit.py --tab "Test" --concurrency 15
```

### Recommended Starting Points by System

- **4GB RAM, 2 cores**: `--concurrency 2`
- **8GB RAM, 4 cores**: `--concurrency 5` (default)
- **16GB RAM, 8 cores**: `--concurrency 10`
- **32GB+ RAM, 16+ cores**: `--concurrency 15-20`

## License

(Add your license information here)
