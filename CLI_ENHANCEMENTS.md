# CLI Enhancements Guide

This document describes the enhanced command-line interface features added to the PageSpeed Insights audit tool.

## Overview

The audit tool now includes several powerful CLI enhancements to improve workflow efficiency and usability:

1. **Resume from Row** - Continue interrupted audits from a specific row
2. **URL Filtering** - Process only URLs matching a regex pattern
3. **Result Export** - Export results to JSON or CSV format
4. **Progress Bar** - Visual progress indicator with tqdm
5. **Config File Support** - Use YAML files to avoid long CLI arguments
6. **Version Flag** - Check the tool version

## Feature Details

### 1. Resume from Specific Row (`--resume-from-row`)

**Purpose:** Resume an interrupted audit from a specific row number.

**Usage:**
```bash
python run_audit.py --tab "TAB_NAME" --resume-from-row 50
```

**How it works:**
- Reads all URLs from the spreadsheet
- Filters to only include URLs at or after the specified row number (1-based)
- Continues processing from that point

**Use cases:**
- Recovering from interrupted audits (power failure, network issues, etc.)
- Re-running only remaining URLs after fixing issues
- Processing large spreadsheets in batches
- Debugging specific rows without reprocessing earlier ones

**Example:**
```bash
# Original audit interrupted at row 47
# Resume from row 45 to reprocess a few earlier rows
python run_audit.py --tab "Production" --resume-from-row 45
```

### 2. URL Filter by Regex (`--filter`)

**Purpose:** Process only URLs matching a regular expression pattern.

**Usage:**
```bash
python run_audit.py --tab "TAB_NAME" --filter "REGEX_PATTERN"
```

**How it works:**
- The filter is applied as a regex search on each URL
- Only URLs matching the pattern are processed
- Non-matching URLs are skipped

**Use cases:**
- Auditing specific subsets of URLs (e.g., only product pages)
- Testing changes on specific URL patterns
- Splitting large audits by URL pattern or domain
- Focusing on specific sections of a website

**Examples:**
```bash
# Only process URLs from a specific domain
python run_audit.py --tab "All URLs" --filter "https://example\.com/.*"

# Only process product pages
python run_audit.py --tab "All URLs" --filter "/products/"

# Only process URLs with specific path structure
python run_audit.py --tab "All URLs" --filter "https://.*\\.example\\.com/blog/.*"

# Case-insensitive match for PDFs (use Python regex flags in pattern)
python run_audit.py --tab "All URLs" --filter "(?i).*\\.pdf$"
```

**Combining with Resume:**
```bash
# Process only product URLs starting from row 100
python run_audit.py --tab "All URLs" --filter "/products/" --resume-from-row 100
```

### 3. Export Results (`--export-json`, `--export-csv`)

**Purpose:** Export audit results to JSON or CSV files for further analysis.

**Usage:**
```bash
# Export to JSON
python run_audit.py --tab "TAB_NAME" --export-json results.json

# Export to CSV
python run_audit.py --tab "TAB_NAME" --export-csv results.csv

# Export to both formats
python run_audit.py --tab "TAB_NAME" --export-json results.json --export-csv results.csv
```

**JSON Format:**
```json
[
  {
    "row": 2,
    "url": "https://example.com",
    "mobile_score": 85,
    "desktop_score": 92,
    "mobile_psi_url": null,
    "desktop_psi_url": null
  },
  {
    "row": 3,
    "url": "https://example.com/about",
    "mobile_score": 65,
    "desktop_score": 78,
    "mobile_psi_url": "https://pagespeed.web.dev/...",
    "desktop_psi_url": "https://pagespeed.web.dev/..."
  },
  {
    "row": 4,
    "url": "https://invalid-url",
    "error": "Invalid URL format",
    "error_type": "invalid_url"
  }
]
```

**CSV Format:**
```csv
row,url,mobile_score,desktop_score,mobile_psi_url,desktop_psi_url,error,error_type
2,https://example.com,85,92,,,
3,https://example.com/about,65,78,https://pagespeed.web.dev/...,https://pagespeed.web.dev/...,,
4,https://invalid-url,,,,Invalid URL format,invalid_url
```

**Exported Fields:**
- `row`: Row number in spreadsheet (1-based)
- `url`: Original URL
- `mobile_score`: Mobile PageSpeed score (0-100, or null)
- `desktop_score`: Desktop PageSpeed score (0-100, or null)
- `mobile_psi_url`: Mobile PageSpeed Insights URL (for failing scores)
- `desktop_psi_url`: Desktop PageSpeed Insights URL (for failing scores)
- `skipped`: Whether the URL was skipped (boolean)
- `error`: Error message (if any)
- `error_type`: Error type classification
- `dry_run`: Whether this was a dry run simulation
- `validation_results`: Validation details (JSON object in CSV)

**Use cases:**
- Post-processing results with custom scripts
- Creating custom reports and visualizations
- Importing into spreadsheet tools for analysis
- Archiving audit results
- Integration with CI/CD pipelines
- Comparing results across multiple audit runs

### 4. Configuration File Support (`--config`)

**Purpose:** Use a YAML configuration file to specify options instead of long CLI arguments.

**Usage:**
```bash
python run_audit.py --config config.yaml
```

**Configuration File Format:**

See `config.example.yaml` for a complete example. Here's a basic config file:

```yaml
# config.yaml
tab: "Production URLs"
timeout: 600
concurrency: 3
skip-cache: false
export-json: "results.json"
export-csv: "results.csv"
resume-from-row: 50
filter: "https://example\\.com/.*"
dns-timeout: 5.0
redirect-timeout: 10.0
```

**Available Config Options:**

All CLI flags can be specified in the config file using their long names with hyphens:

- `tab`: Spreadsheet tab name (required)
- `spreadsheet-id`: Google Spreadsheet ID
- `service-account`: Service account JSON file path
- `timeout`: Cypress timeout in seconds
- `concurrency`: Number of concurrent workers (1-5)
- `skip-cache`: Skip cache (true/false)
- `whitelist`: List of URL whitelist patterns
- `blacklist`: List of URL blacklist patterns
- `dry-run`: Dry run mode (true/false)
- `validate-only`: Validation-only mode (true/false)
- `skip-dns-validation`: Skip DNS validation (true/false)
- `skip-redirect-validation`: Skip redirect validation (true/false)
- `dns-timeout`: DNS timeout in seconds
- `redirect-timeout`: Redirect timeout in seconds
- `resume-from-row`: Row number to resume from
- `filter`: URL filter regex pattern
- `export-json`: JSON export file path
- `export-csv`: CSV export file path
- `no-progress-bar`: Disable progress bar (true/false)

**Precedence Rules:**

CLI arguments override config file values. This allows you to:
1. Set defaults in the config file
2. Override specific options on the command line

**Example:**
```bash
# Use config.yaml but override concurrency
python run_audit.py --config config.yaml --concurrency 5
```

**Use cases:**
- Standardizing audit configurations across team
- Creating different config profiles (production, staging, testing)
- Simplifying complex audit commands
- Version-controlling audit configurations
- Sharing audit settings with team members

**Multiple Config Files:**
```bash
# Production environment
python run_audit.py --config config.prod.yaml

# Staging environment
python run_audit.py --config config.staging.yaml

# Development environment
python run_audit.py --config config.dev.yaml
```

### 5. Progress Bar (`tqdm`)

**Purpose:** Display a visual progress indicator during audit execution.

**Default Behavior:**

When running an audit, a progress bar is displayed automatically:

```
Processing URLs: 45%|████████████████          | 45/100 [02:15<02:45, 0.33url/s]
```

The progress bar shows:
- Percentage complete
- Visual bar indicator
- Current count / total count
- Elapsed time
- Estimated time remaining
- Processing rate (URLs per second)
- Current operation (e.g., "Analyzing https://...")

**Disabling the Progress Bar:**

```bash
python run_audit.py --tab "TAB_NAME" --no-progress-bar
```

**When to disable:**
- Running in CI/CD environments
- Logging output to files
- Running as a background service
- When detailed logging is preferred over visual progress

**Progress Bar Features:**
- Thread-safe updates during concurrent processing
- Descriptive status messages (e.g., "Skipping (row 5)", "Analyzing...")
- Automatic cleanup on completion or error
- Graceful handling of Ctrl+C interrupts

### 6. Version Flag (`--version`)

**Purpose:** Display the tool version number.

**Usage:**
```bash
python run_audit.py --version
```

**Output:**
```
run_audit.py 1.0.0
```

**Use cases:**
- Verifying installed version
- Debugging compatibility issues
- Including version info in bug reports
- CI/CD version tracking

**Version Information:**

The version is defined in `version.py` and follows semantic versioning (MAJOR.MINOR.PATCH).

## Complete Examples

### Example 1: Resume with Export

Resume an interrupted audit from row 50 and export results:

```bash
python run_audit.py \
  --tab "Production URLs" \
  --resume-from-row 50 \
  --export-json results.json \
  --export-csv results.csv
```

### Example 2: Filter and Export

Audit only product pages and export results:

```bash
python run_audit.py \
  --tab "All URLs" \
  --filter "https://example\.com/products/.*" \
  --export-json product_audit.json
```

### Example 3: Config File with Overrides

Use a config file but override specific settings:

```bash
# config.yaml contains most settings
# Override concurrency and add JSON export
python run_audit.py \
  --config config.yaml \
  --concurrency 5 \
  --export-json override_results.json
```

### Example 4: Full-Featured Audit

Complete audit with all features:

```bash
python run_audit.py \
  --config config.yaml \
  --resume-from-row 100 \
  --filter "https://example\.com/blog/.*" \
  --export-json blog_audit.json \
  --export-csv blog_audit.csv \
  --concurrency 4 \
  --timeout 900
```

### Example 5: Batch Processing

Process a large spreadsheet in batches using resume:

```bash
# Batch 1: rows 2-100
python run_audit.py --tab "Large Dataset" --filter ".*" > batch1.log

# Batch 2: rows 101-200
python run_audit.py --tab "Large Dataset" --resume-from-row 101 > batch2.log

# Batch 3: rows 201+
python run_audit.py --tab "Large Dataset" --resume-from-row 201 > batch3.log
```

## Best Practices

### 1. Use Config Files for Complex Audits

Instead of this:
```bash
python run_audit.py --tab "URLs" --timeout 900 --concurrency 4 --skip-cache \
  --export-json results.json --export-csv results.csv --dns-timeout 10 \
  --redirect-timeout 15 --filter "https://example\.com/.*"
```

Do this:
```bash
# config.yaml
python run_audit.py --config config.yaml
```

### 2. Always Export Results

Export results for later analysis and record-keeping:
```bash
python run_audit.py --tab "URLs" --export-json results_$(date +%Y%m%d).json
```

### 3. Combine Resume with Checkpoints

For very large audits, create checkpoints:
```bash
# Process first 100 URLs
python run_audit.py --tab "Large" --resume-from-row 2 --filter ".*" --export-json checkpoint1.json

# Continue from row 101
python run_audit.py --tab "Large" --resume-from-row 101 --export-json checkpoint2.json
```

### 4. Use Filter for Targeted Testing

Test specific sections before full audit:
```bash
# Test just the homepage and about page
python run_audit.py --tab "URLs" --filter "(/$|/about$)" --dry-run

# After verification, run for real
python run_audit.py --tab "URLs" --filter "(/$|/about$)"
```

### 5. Disable Progress Bar for Logging

When logging to files or CI/CD:
```bash
python run_audit.py --tab "URLs" --no-progress-bar > audit.log 2>&1
```

## Troubleshooting

### Config File Not Loading

**Error:** `Error: Config file not found: config.yaml`

**Solution:** Ensure the config file path is correct (relative to current directory):
```bash
python run_audit.py --config ./configs/config.yaml
```

### Invalid Regex Pattern

**Error:** `Error: Invalid regex pattern for --filter: ...`

**Solution:** Escape special characters in regex:
```bash
# Incorrect
--filter "https://example.com/.*"

# Correct
--filter "https://example\\.com/.*"
```

### Resume Row Out of Range

**Warning:** If `--resume-from-row` is greater than total rows, no URLs will be processed.

**Solution:** Verify the row number is within the spreadsheet range.

### Export File Permissions

**Error:** `Failed to export results to JSON: Permission denied`

**Solution:** Ensure write permissions for the export directory:
```bash
# Use absolute path or verify directory exists
python run_audit.py --tab "URLs" --export-json ./results/output.json
```

## Integration Examples

### CI/CD Pipeline (GitHub Actions)

```yaml
name: Audit URLs
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run audit
        run: |
          python run_audit.py \
            --config .github/audit-config.yaml \
            --export-json results.json \
            --no-progress-bar
      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: audit-results
          path: results.json
```

### Cron Job

```bash
# crontab entry - daily audit at 2 AM
0 2 * * * cd /path/to/audit && python run_audit.py --config config.yaml --export-json results_$(date +\%Y\%m\%d).json --no-progress-bar >> audit.log 2>&1
```

### Shell Script Wrapper

```bash
#!/bin/bash
# audit_wrapper.sh

DATE=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="./results"
CONFIG="./config.yaml"

mkdir -p "$RESULTS_DIR"

python run_audit.py \
  --config "$CONFIG" \
  --export-json "$RESULTS_DIR/audit_$DATE.json" \
  --export-csv "$RESULTS_DIR/audit_$DATE.csv" \
  --no-progress-bar

if [ $? -eq 0 ]; then
  echo "Audit completed successfully: $DATE"
else
  echo "Audit failed: $DATE"
  exit 1
fi
```

## Summary

These CLI enhancements significantly improve the usability and flexibility of the audit tool:

- **Resume**: Never lose progress on long audits
- **Filter**: Target specific URLs for auditing
- **Export**: Get results in standard formats for analysis
- **Progress**: See real-time audit progress
- **Config**: Manage complex settings easily
- **Version**: Track tool versions

For more information, see:
- `config.example.yaml` - Example configuration file
- `AGENTS.md` - Complete agent development guide
- `README.md` - General project documentation
