# Input Validation and Data Quality Guide

This document describes the input validation and data quality features available in the PageSpeed Insights audit tool.

## Overview

The system includes comprehensive validation to ensure data quality and prevent errors during audit execution:

1. **URL Format Validation** - Regex-based format checking
2. **DNS Resolution** - Verifies domains resolve to IP addresses
3. **Redirect Chain Detection** - Flags URLs with excessive redirects
4. **URL Normalization** - Standardizes URL format for consistency
5. **Duplicate Detection** - Identifies duplicate URLs in spreadsheet
6. **Schema Validation** - Validates spreadsheet structure

## URL Validation

### Format Validation

Every URL is validated against a comprehensive regex pattern that checks:
- Valid HTTP/HTTPS scheme
- Valid domain name or IP address
- Valid port number (if specified)
- Valid path and query parameters

**Example:**
```python
# Valid URLs
https://example.com
https://example.com/path
https://example.com:8080/path?query=value

# Invalid URLs
example.com  # Missing scheme (will be auto-fixed to https://)
htp://example.com  # Invalid scheme
https://  # Missing domain
```

### DNS Resolution

URLs are checked to ensure their domains resolve to valid IP addresses. This catches:
- Typos in domain names
- Non-existent domains
- DNS configuration issues

**Configuration:**
```bash
# Default timeout: 5 seconds
python run_audit.py --tab "TAB_NAME"

# Custom timeout
python run_audit.py --tab "TAB_NAME" --dns-timeout 10

# Disable DNS validation
python run_audit.py --tab "TAB_NAME" --skip-dns-validation
```

### Redirect Chain Detection

URLs are checked for redirect chains. Chains with more than 3 redirects are flagged as they:
- Slow down page load times
- May indicate configuration issues
- Can affect SEO

**Example:**
```
http://example.com → https://example.com → https://www.example.com → https://www.example.com/
                                                                      ^^^ 3 redirects: OK

http://a.com → http://b.com → http://c.com → http://d.com → http://e.com
                                                           ^^^ 4 redirects: FLAGGED
```

**Configuration:**
```bash
# Default timeout: 10 seconds
python run_audit.py --tab "TAB_NAME"

# Custom timeout
python run_audit.py --tab "TAB_NAME" --redirect-timeout 15

# Disable redirect validation
python run_audit.py --tab "TAB_NAME" --skip-redirect-validation
```

## URL Normalization

URLs are automatically normalized before analysis to ensure consistency:

1. **Scheme/Domain Lowercase**: `HTTPS://EXAMPLE.COM` → `https://example.com`
2. **Trailing Slash**: `https://example.com/path/` → `https://example.com/path`
3. **Query Parameter Sorting**: `?b=2&a=1` → `?a=1&b=2`

**Example:**
```
Original:  HTTPS://EXAMPLE.com/Path/?b=2&a=1
Normalized: https://example.com/Path?a=1&b=2
```

Normalization helps:
- Deduplicate similar URLs
- Ensure cache consistency
- Reduce redundant audits

## Duplicate Detection

The system detects two types of duplicates:

### 1. Exact Duplicates
Same URL appears multiple times in the spreadsheet.

**Example:**
```
Row 5:  https://example.com/page
Row 12: https://example.com/page
Row 18: https://example.com/page
```

### 2. Normalized Duplicates
Different URLs that normalize to the same value.

**Example:**
```
Row 3:  https://example.com/page/
Row 7:  HTTPS://EXAMPLE.COM/page
Row 11: https://example.com/page

All normalize to: https://example.com/page
```

**Output:**
```
================================================================================
DUPLICATE URLS DETECTED: 2 duplicate groups found
================================================================================

Exact Duplicates: 1
  URL: https://example.com/page
  Rows: 5, 12, 18
  Count: 3

Normalized Duplicates (same URL with minor variations): 1
  Normalized URL: https://example.com/page
  Original URLs:
    - Row 3: https://example.com/page/
    - Row 7: HTTPS://EXAMPLE.COM/page
    - Row 11: https://example.com/page

================================================================================
```

## Spreadsheet Schema Validation

The system validates the spreadsheet structure on startup:

1. **Column Count**: Ensures columns A through G exist
2. **Header Row**: Checks for header row (row 1)
3. **Data Rows**: Ensures URLs exist in column A (starting row 2)

**Expected Structure:**
```
Column A: URL
Column F: Mobile PSI (results written here)
Column G: Desktop PSI (results written here)
```

If validation fails, warnings are logged but the audit continues.

## Validation-Only Mode

Use `--validate-only` to run all validation checks without executing the audit:

```bash
python run_audit.py --tab "TAB_NAME" --validate-only
```

### What It Does

1. **Schema Validation**: Checks spreadsheet structure
2. **Data Quality**: Detects duplicates and empty URLs
3. **URL Validation**: Validates format, DNS, and redirects for every URL
4. **Detailed Report**: Shows pass/fail status for each URL

### Output Example

```
================================================================================
VALIDATION MODE: Performing URL validations without running audit
================================================================================
Total URLs to validate: 25
DNS validation: enabled
Redirect validation: enabled

[1/25] Validating https://example.com...
  ✓ Valid

[2/25] Validating https://nonexistent-domain-12345.com...
  ✗ Invalid
    - DNS resolution failed: [Errno 11001] getaddrinfo failed

[3/25] Validating http://old-redirect.com...
  ✓ Valid
  ⚠ Redirects: 5

...

================================================================================
VALIDATION SUMMARY
================================================================================
Total URLs validated: 25
Valid URLs: 22
Invalid URLs: 3
URLs with redirects: 8

Invalid URLs:
  Row 2: https://nonexistent-domain-12345.com
    - DNS resolution failed: [Errno 11001] getaddrinfo failed
  Row 5: invalid-url
    - URL format is invalid
  Row 12: https://example.com:99999/page
    - URL format is invalid

URLs with redirects:
  Row 3: http://old-redirect.com (5 redirects)
  Row 7: http://example.com (2 redirects)
  Row 11: http://www.example.com (1 redirect)
  ...
================================================================================
```

### Use Cases

- **Pre-flight checks**: Validate URLs before running expensive audits
- **Data cleanup**: Identify and fix data quality issues
- **URL testing**: Test URL accessibility without PageSpeed analysis
- **Redirect mapping**: Identify all URLs with redirects

## Command-Line Reference

### Basic Validation
```bash
# Run audit with default validation
python run_audit.py --tab "TAB_NAME"

# Validation only (no audit)
python run_audit.py --tab "TAB_NAME" --validate-only
```

### Customizing Validation
```bash
# Skip DNS validation
python run_audit.py --tab "TAB_NAME" --skip-dns-validation

# Skip redirect validation
python run_audit.py --tab "TAB_NAME" --skip-redirect-validation

# Skip both
python run_audit.py --tab "TAB_NAME" --skip-dns-validation --skip-redirect-validation

# Custom timeouts
python run_audit.py --tab "TAB_NAME" --dns-timeout 10 --redirect-timeout 15
```

### Combined Options
```bash
# Validate only with custom timeouts
python run_audit.py --tab "TAB_NAME" --validate-only --dns-timeout 10 --redirect-timeout 15

# Run audit without DNS validation
python run_audit.py --tab "TAB_NAME" --skip-dns-validation

# Dry run with validation
python run_audit.py --tab "TAB_NAME" --dry-run
```

## Error Types

### Validation Errors

| Error Type | Description | Retryable |
|------------|-------------|-----------|
| `invalid_url` | URL format is invalid | No |
| `validation_failed` | DNS or redirect validation failed | No |
| `dns_resolution_failed` | Domain does not resolve | No |
| `too_many_redirects` | More than 3 redirects detected | No |

### During Audit

URLs that fail validation are skipped and reported in the final summary:

```
================================================================================
AUDIT SUMMARY
================================================================================
Total URLs processed: 100
URLs skipped: 10
URLs analyzed: 85
Failed analyses: 5
URLs failed validation: 3
...
```

## Best Practices

1. **Run validation-only mode first**: Identify issues before running expensive audits
2. **Fix duplicates**: Remove or consolidate duplicate URLs
3. **Update redirects**: Update URLs to their final destination to avoid redirect chains
4. **Fix DNS issues**: Correct typos and ensure domains are valid
5. **Use normalization**: Let the system normalize URLs automatically
6. **Custom timeouts**: Increase timeouts for slow networks or large redirects

## Troubleshooting

### DNS Validation Fails for Valid URLs

**Problem**: DNS validation fails even though the URL works in a browser.

**Solutions**:
- Check your network connection
- Increase DNS timeout: `--dns-timeout 10`
- Skip DNS validation: `--skip-dns-validation`
- Check if domain requires VPN or special network access

### Too Many False Positives for Redirects

**Problem**: Many URLs are flagged for redirects but they're expected (e.g., http→https).

**Solutions**:
- This is informational, not an error
- Update URLs to their final destination to avoid redirects
- Skip redirect validation if not relevant: `--skip-redirect-validation`

### Validation Is Too Slow

**Problem**: Validation takes too long for large spreadsheets.

**Solutions**:
- Reduce timeouts: `--dns-timeout 2 --redirect-timeout 5`
- Skip validations: `--skip-dns-validation --skip-redirect-validation`
- Note: Validation happens per URL, so 1000 URLs × 5s = ~1.5 hours

### Duplicates Not Detected

**Problem**: Similar URLs aren't detected as duplicates.

**Solutions**:
- Check if URLs normalize to different values
- Manually review normalized duplicates report
- URLs with different paths/queries are not considered duplicates

## Implementation Details

### Validation Architecture

```
run_audit.py
    ├── SpreadsheetSchemaValidator (schema_validator.py)
    │   └── Validates spreadsheet structure
    │
    ├── DataQualityChecker (data_quality_checker.py)
    │   └── Detects duplicates and empty URLs
    │
    └── URLValidator (url_validator.py)
        ├── validate_url_format() - Regex validation
        ├── validate_dns() - DNS resolution
        ├── check_redirect_chain() - HTTP redirect detection
        └── URLNormalizer.normalize_url() - URL normalization
```

### Validation Flow

1. **Startup**: Schema validation + duplicate detection
2. **Per URL** (during audit):
   - URL sanitization
   - URL validation (format, DNS, redirects)
   - URL normalization
   - Processing or skipping based on validation results

### Thread Safety

All validation operations are thread-safe and can run concurrently during multi-threaded audits.
