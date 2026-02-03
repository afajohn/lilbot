# Security Features Quick Reference

## Command-Line Options

### URL Filtering
```bash
# Whitelist (only allow specific patterns)
--whitelist "https://example.com/*" "https://*.trusted.com/*"

# Blacklist (block specific patterns)
--blacklist "http://*" "https://blocked.com/*"

# Combined
--whitelist "https://*.mysite.com/*" --blacklist "https://staging.mysite.com/*"
```

### Dry Run Mode
```bash
# Simulate without making changes
--dry-run
```

## Utility Scripts

### Validate Service Account
```bash
# Validate service account JSON file
python validate_service_account.py service-account.json
```

### Query Audit Trail
```bash
# View all modifications
python query_audit_trail.py

# Filter by spreadsheet
python query_audit_trail.py --spreadsheet-id "YOUR_ID"

# Filter by tab
python query_audit_trail.py --tab "Production URLs"

# Filter by date range
python query_audit_trail.py --start-date "2024-01-01" --end-date "2024-12-31"

# Filter by operation type
python query_audit_trail.py --operation update

# Show only count
python query_audit_trail.py --count

# Limit results (most recent)
python query_audit_trail.py --limit 10

# Output formats
python query_audit_trail.py --format summary    # Default
python query_audit_trail.py --format detailed
python query_audit_trail.py --format json

# Combined example
python query_audit_trail.py \
  --tab "Website 1" \
  --start-date "2024-02-01" \
  --format detailed \
  --limit 20
```

## Environment Variables

Add to `.env` file:

```bash
# Security Configuration
RATE_LIMIT_REQUESTS_PER_MINUTE=60
AUDIT_TRAIL_PATH=audit_trail.jsonl
URL_WHITELIST=https://*.example.com/*,https://trusted.com/*
URL_BLACKLIST=http://*,https://blocked.com/*
```

## Common Patterns

### Production Deployment
```bash
# Validate, filter, and log all operations
python validate_service_account.py service-account.json
python run_audit.py \
  --tab "Production URLs" \
  --whitelist "https://*.mycompany.com/*" \
  --blacklist "https://staging.mycompany.com/*"
```

### Testing New Configuration
```bash
# Use dry run to test filters
python run_audit.py \
  --tab "Test URLs" \
  --whitelist "https://example.com/*" \
  --dry-run
```

### Security Audit
```bash
# Review all modifications in last 7 days
python query_audit_trail.py \
  --start-date "2024-01-24" \
  --format detailed
```

### Block Insecure URLs
```bash
# Only allow HTTPS
python run_audit.py \
  --tab "URLs" \
  --blacklist "http://*"
```

## URL Pattern Syntax

| Pattern | Matches | Example |
|---------|---------|---------|
| `https://example.com/*` | All paths on domain | `https://example.com/path` |
| `https://*.example.com/*` | All subdomains | `https://sub.example.com/` |
| `http://*` | All HTTP URLs | `http://anything.com` |
| `https://example.com/path/*` | Specific path prefix | `https://example.com/path/sub` |

## Audit Trail Log Format

JSON Lines format (one JSON object per line):

```json
{
  "timestamp": "2024-02-03T10:30:45.123456Z",
  "operation": "batch_update",
  "spreadsheet_id": "1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I",
  "tab_name": "URLs",
  "row": 5,
  "column": "F",
  "value": "https://pagespeed.web.dev/...",
  "user": "system"
}
```

## Security Best Practices

1. **Always validate service accounts** before use
2. **Use whitelists** in production environments
3. **Test with dry run** before making changes
4. **Review audit trail** regularly
5. **Rotate service account keys** periodically
6. **Monitor rate limiting** to stay within quotas
7. **Block HTTP URLs** if only HTTPS is allowed

## Troubleshooting

### Service Account Validation Fails
```bash
# Check JSON validity
python -m json.tool service-account.json

# Validate
python validate_service_account.py service-account.json
```

### URLs Being Filtered Unexpectedly
```bash
# Use dry run to see what gets filtered
python run_audit.py --tab "URLs" --whitelist "pattern" --dry-run
```

### Audit Trail Not Writing
```bash
# Check file exists and is writable
ls -la audit_trail.jsonl

# Verify in logs
grep "audit" logs/audit_*.log
```

## Integration Examples

### CI/CD Pipeline
```bash
#!/bin/bash
set -e

# Validate service account
python validate_service_account.py $SERVICE_ACCOUNT_FILE || exit 1

# Run with production whitelist
python run_audit.py \
  --tab "$TAB_NAME" \
  --whitelist "https://*.production.com/*" \
  --service-account "$SERVICE_ACCOUNT_FILE"

# Archive audit trail
cp audit_trail.jsonl "audit_trail_$(date +%Y%m%d).jsonl"
```

### Scheduled Security Report
```bash
#!/bin/bash
# Run weekly security audit

# Get last week's modifications
python query_audit_trail.py \
  --start-date "$(date -d '7 days ago' +%Y-%m-%d)" \
  --format detailed > weekly_audit_report.txt

# Email report
mail -s "Weekly Security Audit" admin@example.com < weekly_audit_report.txt
```

## See Also

- [SECURITY.md](SECURITY.md) - Complete security documentation
- [AGENTS.md](AGENTS.md) - Developer guide
- [README.md](README.md) - Main documentation
