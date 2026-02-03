# Security Hardening Features

This document describes the security hardening features implemented in the PageSpeed Insights audit system.

## Overview

The following security features have been implemented:

1. **Service Account Validation** - Validates service account JSON files before use
2. **API Rate Limiting** - Per-spreadsheet rate limiting to prevent API quota exhaustion
3. **URL Filtering** - Whitelist/blacklist support for URL filtering
4. **URL Sanitization** - Validates and sanitizes URLs before processing
5. **Audit Trail** - Logs all spreadsheet modifications with timestamps
6. **Dry Run Mode** - Simulates operations without making changes

## 1. Service Account Validation

### Features

The service account validator performs the following checks:

- **Required Fields Validation**: Ensures all required fields are present:
  - `type`
  - `project_id`
  - `private_key_id`
  - `private_key`
  - `client_email`
  - `client_id`
  - `auth_uri`
  - `token_uri`

- **Account Type Check**: Verifies the type is `service_account`
- **Private Key Format**: Validates private key has proper header/footer
- **Email Format**: Validates service account email format (*.iam.gserviceaccount.com)

### Usage

Validation happens automatically during authentication. If validation fails, the audit will not proceed.

### Example Error

```
Service account validation failed:
  - Missing required field: private_key
  - Invalid service account email format: invalid@example.com
```

## 2. API Rate Limiting

### Features

Per-spreadsheet rate limiting prevents excessive API calls:

- **Token Bucket Algorithm**: Smooth rate limiting with burst tolerance
- **Default Limit**: 60 requests per minute per spreadsheet
- **Automatic Throttling**: Blocks until tokens are available
- **Thread-Safe**: Works correctly with concurrent workers

### Configuration

Set the rate limit in `.env`:

```bash
RATE_LIMIT_REQUESTS_PER_MINUTE=60
```

### Implementation Details

- Each spreadsheet has its own rate limiter
- Uses sliding window of 60 seconds
- Automatically refills tokens over time
- Integrates with existing retry logic

## 3. URL Filtering

### Whitelist

Restrict processing to only allowed URL patterns:

```bash
python run_audit.py --tab "My Tab" --whitelist "https://example.com/*" "https://*.trusted.com/*"
```

**Behavior:**
- Only URLs matching the whitelist patterns will be processed
- All other URLs will be skipped and logged
- Supports wildcard patterns (`*`)

### Blacklist

Block specific URL patterns from processing:

```bash
python run_audit.py --tab "My Tab" --blacklist "http://*" "https://malicious.com/*"
```

**Behavior:**
- URLs matching blacklist patterns will be skipped
- Takes precedence over processing (checked after whitelist)
- Useful for blocking insecure HTTP URLs

### Combined Usage

```bash
python run_audit.py --tab "My Tab" \
  --whitelist "https://*.example.com/*" \
  --blacklist "https://old.example.com/*"
```

### Pattern Syntax

- `*` - Matches any sequence of characters
- `.` - Matches literal dot (automatically escaped)
- Case-insensitive matching
- Full URL matching (must match entire URL)

### Examples

| Pattern | Matches | Doesn't Match |
|---------|---------|---------------|
| `https://example.com/*` | `https://example.com/path` | `http://example.com/path` |
| `https://*.example.com/*` | `https://sub.example.com/` | `https://example.com/` |
| `http://*` | Any HTTP URL | Any HTTPS URL |

## 4. URL Sanitization

### Features

All URLs are automatically sanitized before processing:

- **Protocol Normalization**: Adds `https://` if missing
- **Format Validation**: Checks URL structure
- **Scheme Validation**: Only allows `http://` and `https://`
- **Domain Validation**: Ensures valid domain exists
- **Dangerous Character Detection**: Blocks URLs with dangerous characters

### Blocked Characters

The following characters are blocked in URLs:
- `<` `>` `"` `'` `` ` `` `{` `}` `|` `\` `^` `[` `]`

### Examples

| Input | Output | Result |
|-------|--------|--------|
| `example.com` | `https://example.com` | ✓ Sanitized |
| `http://example.com` | `http://example.com` | ✓ Valid |
| `<script>` | - | ✗ Rejected |
| `example` | - | ✗ Invalid domain |

### Error Handling

Invalid URLs are:
- Logged with error details
- Counted in failure metrics
- Skipped (processing continues with next URL)

## 5. Audit Trail

### Features

All spreadsheet modifications are logged to `audit_trail.jsonl`:

- **Timestamp**: UTC timestamp for each modification
- **Operation Type**: `update` or `batch_update`
- **Spreadsheet Details**: ID and tab name
- **Cell Location**: Row and column
- **Value Written**: The actual value written
- **User**: User identifier (defaults to "system")
- **Metadata**: Optional additional context

### Log Format

Each log entry is a JSON line:

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

### Configuration

Set custom audit trail path in `.env`:

```bash
AUDIT_TRAIL_PATH=audit_trail.jsonl
```

### Viewing Audit Trail

```bash
# View all entries
cat audit_trail.jsonl

# Pretty print JSON
cat audit_trail.jsonl | python -m json.tool

# Count modifications
wc -l audit_trail.jsonl

# Filter by spreadsheet
grep "1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I" audit_trail.jsonl
```

### Security Considerations

- **No PII**: Audit trail should not contain personal data
- **Append-only**: File is only appended, never modified
- **Rotation**: Consider rotating logs periodically
- **Backup**: Include in backup strategy
- **Access Control**: Restrict file permissions appropriately

## 6. Dry Run Mode

### Features

Simulate the entire audit process without making any changes:

```bash
python run_audit.py --tab "My Tab" --dry-run
```

**Behavior:**
- Reads URLs from spreadsheet
- Validates and sanitizes URLs
- Applies whitelist/blacklist filters
- **Does NOT** analyze URLs (skips Cypress)
- **Does NOT** write to spreadsheet
- **Does NOT** write to audit trail
- Logs all operations that would be performed

### Use Cases

1. **Testing Filters**: Verify whitelist/blacklist configuration
2. **Validation**: Check which URLs will be processed
3. **Safety**: Review changes before executing
4. **Debugging**: Understand processing flow

### Output

Dry run mode produces detailed logs:

```
[1/10] Analyzing https://example.com...
  [DRY RUN MODE] - No changes will be made
  [DRY RUN] Would analyze https://example.com

[DRY RUN] Would write to My Tab!F5: passed
```

### Summary

The audit summary shows dry run counts:

```
Total URLs processed: 10
URLs skipped: 2
URLs simulated (dry run): 8
URLs analyzed: 0
```

## Combined Usage Example

Use all security features together:

```bash
python run_audit.py \
  --tab "Production URLs" \
  --whitelist "https://*.mycompany.com/*" \
  --blacklist "https://staging.mycompany.com/*" \
  --dry-run
```

This will:
1. Validate service account (automatic)
2. Read URLs from spreadsheet
3. Sanitize all URLs
4. Filter to only mycompany.com (excluding staging)
5. Simulate processing without changes
6. Log everything that would happen

## Environment Variables

All security features can be configured via `.env`:

```bash
# Service Account
GOOGLE_SERVICE_ACCOUNT_PATH=service-account.json

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# URL Filtering (comma-separated patterns)
URL_WHITELIST=https://*.example.com/*,https://trusted.com/*
URL_BLACKLIST=http://*,https://blocked.com/*

# Audit Trail
AUDIT_TRAIL_PATH=audit_trail.jsonl
```

## Security Best Practices

1. **Service Account**
   - Use dedicated service account with minimal permissions
   - Rotate keys regularly
   - Never commit JSON files to version control

2. **Rate Limiting**
   - Keep default limits unless you have quota increases
   - Monitor API usage in Google Cloud Console
   - Adjust concurrency based on rate limits

3. **URL Filtering**
   - Always use whitelist in production
   - Block HTTP URLs if only HTTPS is allowed
   - Log rejected URLs for monitoring

4. **Audit Trail**
   - Review logs regularly
   - Set up log rotation
   - Monitor for unexpected modifications
   - Include in security audits

5. **Dry Run**
   - Always dry run before production
   - Review logs for unexpected behavior
   - Test filter configurations

## Troubleshooting

### Service Account Validation Fails

**Problem**: Validation errors prevent authentication

**Solutions**:
- Verify JSON file is valid (use `python -m json.tool service-account.json`)
- Ensure all required fields are present
- Re-download from Google Cloud Console if corrupted
- Check email format matches `*.iam.gserviceaccount.com`

### Rate Limiting Too Aggressive

**Problem**: Processing is too slow due to rate limiting

**Solutions**:
- Increase `RATE_LIMIT_REQUESTS_PER_MINUTE` in `.env`
- Reduce concurrency with `--concurrency` flag
- Check if you have API quota increases available
- Spread processing across multiple time windows

### URLs Being Filtered Unexpectedly

**Problem**: Valid URLs are being rejected

**Solutions**:
- Use `--dry-run` to see which URLs are filtered
- Check pattern syntax (use `*` for wildcards)
- Verify URL sanitization isn't rejecting URLs
- Test patterns independently
- Review logs for rejection reasons

### Audit Trail Not Writing

**Problem**: No entries in audit trail file

**Solutions**:
- Check file permissions
- Verify `AUDIT_TRAIL_PATH` is writable
- Look for errors in logs
- Ensure directory exists
- Check disk space

## Migration Guide

If you have existing scripts or workflows:

1. **Service Account Validation**: Automatic, no changes needed
2. **Rate Limiting**: Automatic, may slow processing slightly
3. **URL Filtering**: Optional, add flags as needed
4. **Audit Trail**: Automatic, new file created
5. **Dry Run**: Optional, use for testing

All features are backward compatible. Existing workflows continue to work without modification.
