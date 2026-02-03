# CLI Quick Reference

Quick reference guide for the enhanced PageSpeed Insights audit tool CLI.

## New Features

| Feature | Flag | Description |
|---------|------|-------------|
| **Resume** | `--resume-from-row N` | Continue from row N |
| **Filter** | `--filter "PATTERN"` | Process URLs matching regex |
| **Export JSON** | `--export-json FILE` | Export results to JSON |
| **Export CSV** | `--export-csv FILE` | Export results to CSV |
| **Config File** | `--config FILE` | Load settings from YAML |
| **Progress Bar** | (default on) | Visual progress indicator |
| **No Progress** | `--no-progress-bar` | Disable progress bar |
| **Version** | `--version` | Show version number |

## Common Commands

### Basic Audit
```bash
python run_audit.py --tab "TAB_NAME"
```

### Check Version
```bash
python run_audit.py --version
```

### Use Config File
```bash
python run_audit.py --config config.yaml
```

### Resume Interrupted Audit
```bash
python run_audit.py --tab "URLs" --resume-from-row 50
```

### Filter URLs
```bash
python run_audit.py --tab "URLs" --filter "https://example\.com/products/.*"
```

### Export Results
```bash
# JSON
python run_audit.py --tab "URLs" --export-json results.json

# CSV
python run_audit.py --tab "URLs" --export-csv results.csv

# Both
python run_audit.py --tab "URLs" --export-json results.json --export-csv results.csv
```

### Disable Progress Bar (for CI/logging)
```bash
python run_audit.py --tab "URLs" --no-progress-bar
```

## Combined Usage

### Resume + Export
```bash
python run_audit.py --tab "URLs" --resume-from-row 50 --export-json results.json
```

### Filter + Export
```bash
python run_audit.py --tab "URLs" --filter "/products/" --export-csv products.csv
```

### Config + Override
```bash
python run_audit.py --config config.yaml --concurrency 5
```

### Full Example
```bash
python run_audit.py \
  --config config.yaml \
  --resume-from-row 100 \
  --filter "https://example\.com/blog/.*" \
  --export-json blog_audit.json \
  --export-csv blog_audit.csv \
  --no-progress-bar
```

## Config File Template

```yaml
# config.yaml
tab: "Production URLs"
timeout: 600
concurrency: 3
export-json: "results.json"
export-csv: "results.csv"
resume-from-row: 50
filter: "https://example\\.com/.*"
```

## All CLI Flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--tab` | string | required | Spreadsheet tab name |
| `--spreadsheet-id` | string | (built-in) | Google Spreadsheet ID |
| `--service-account` | string | service-account.json | Service account file |
| `--timeout` | int | 600 | Cypress timeout (seconds) |
| `--concurrency` | int | 3 | Concurrent workers (1-5) |
| `--skip-cache` | flag | false | Skip cache |
| `--whitelist` | list | none | URL whitelist patterns |
| `--blacklist` | list | none | URL blacklist patterns |
| `--dry-run` | flag | false | Simulate without changes |
| `--validate-only` | flag | false | Validation only mode |
| `--skip-dns-validation` | flag | false | Skip DNS checks |
| `--skip-redirect-validation` | flag | false | Skip redirect checks |
| `--dns-timeout` | float | 5.0 | DNS timeout (seconds) |
| `--redirect-timeout` | float | 10.0 | Redirect timeout (seconds) |
| `--resume-from-row` | int | none | Resume from row number |
| `--filter` | string | none | URL filter regex pattern |
| `--export-json` | string | none | JSON export file |
| `--export-csv` | string | none | CSV export file |
| `--config` | string | none | YAML config file |
| `--no-progress-bar` | flag | false | Disable progress bar |
| `--version` | flag | - | Show version |

## Tips

- **Config files** simplify complex commands
- **Export results** for analysis and archiving
- **Filter** to test specific URL subsets
- **Resume** to recover from interruptions
- **Disable progress bar** in CI/CD environments
- **Combine flags** for powerful workflows

## More Information

- Full documentation: `CLI_ENHANCEMENTS.md`
- Example config: `config.example.yaml`
- Agent guide: `AGENTS.md`
