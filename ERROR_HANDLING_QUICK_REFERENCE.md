# Error Handling Quick Reference

## Enable Debug Mode

```bash
python run_audit.py --tab "TAB_NAME" --debug-mode
```

## Debug Artifacts Location

- **Screenshots**: `debug_screenshots/*.png`
- **HTML Files**: `debug_screenshots/*.html`
- **Filename Format**: `YYYYMMDD_HHMMSS_sanitized-url_reason.{png|html}`

## Key Features

### 1. Page Reload Recovery
- ✅ Automatic reload on selector failures
- ✅ Up to 3 reload attempts
- ✅ Fresh start on each reload

### 2. Screenshot Capture
- ✅ Full-page screenshots on errors
- ✅ Timestamp + URL in filename
- ✅ Captured for all error types

### 3. HTML Source Capture
- ✅ Complete page HTML saved
- ✅ Post-mortem analysis
- ✅ Verify selector availability

### 4. Enhanced Error Messages
- ✅ Current page URL + title
- ✅ Available buttons/elements
- ✅ Last successful step
- ✅ Paths to debug artifacts

### 5. Page Diagnostics
- ✅ Extracts buttons, inputs, links
- ✅ Shows visibility status
- ✅ Includes element attributes

## Recovery Strategies

| Error Type | Strategy | Retries |
|------------|----------|---------|
| Selector Timeout | Page reload + retry | Up to 3 |
| Analysis Timeout | Immediate abort | 0 |
| Button Not Found | Multiple selectors + reload | 2 attempts |
| Score Extraction | Multiple selectors + delay | 5 attempts |

## Error Messages

### Without Debug Mode
```
Failed to click analyze button - all selectors failed
```

### With Debug Mode
```
Failed to click analyze button after 2 attempts - all selectors failed

Last successful step: Entered URL in input field

Current page URL: https://pagespeed.web.dev/
Page title: PageSpeed Insights

Available buttons:
  1. Analyze (visible)
  2. Settings (hidden)

Available inputs:
  1. url input (visible) - Enter a web page URL

Debug screenshot saved: debug_screenshots/20240115_143022_example_com_button_not_found.png
Debug HTML saved: debug_screenshots/20240115_143022_example_com_button_not_found.html
```

## Usage Examples

### Basic Debug Mode
```bash
python run_audit.py --tab "Test" --debug-mode
```

### Debug Mode + Other Flags
```bash
# Skip cache
python run_audit.py --tab "Test" --debug-mode --skip-cache

# Force retry
python run_audit.py --tab "Test" --debug-mode --force-retry

# Resume from row
python run_audit.py --tab "Test" --debug-mode --resume-from-row 50

# Dry run
python run_audit.py --tab "Test" --debug-mode --dry-run

# Filter URLs
python run_audit.py --tab "Test" --debug-mode --filter "https://example\.com/.*"
```

### Config File
```yaml
# config.yaml
tab: "Production URLs"
debug_mode: true
timeout: 900
```

```bash
python run_audit.py --config config.yaml
```

## Cleanup

### Remove All Debug Artifacts
```bash
# Unix/Linux/Mac
rm -rf debug_screenshots/

# Windows PowerShell
Remove-Item -Recurse -Force debug_screenshots/
```

### Remove Old Artifacts (7+ days)
```bash
# Unix/Linux/Mac
find debug_screenshots/ -type f -mtime +7 -delete

# Windows PowerShell
Get-ChildItem debug_screenshots/ -Recurse | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item
```

## Troubleshooting

### Debug Mode Not Enabled
**Check**: Look for "Debug mode enabled" in logs
```
2024-01-15 14:30:22 [INFO] Debug mode enabled: verbose logging, screenshots, and HTML capture on errors
```

### No Screenshots Created
**Causes**:
- Missing `debug_screenshots/` directory
- Permission issues
- Disk full
- Error occurs before page loads

**Fix**:
```bash
mkdir debug_screenshots
chmod 755 debug_screenshots
```

### Screenshots Too Large
**Solution**: Artifacts are saved efficiently, but cleanup regularly:
- Screenshots: ~100-500 KB each
- HTML: ~50-200 KB each
- 100 errors ≈ 15-70 MB

## Performance Impact

| Mode | Overhead per Error |
|------|-------------------|
| Debug OFF | 0ms |
| Debug ON | ~650ms |

**Recommendation**: 
- ✅ Use during development/troubleshooting
- ⛔ Disable for high-volume production audits

## API Usage

### Enable Debug Mode Programmatically
```python
from tools.qa import playwright_runner

# Enable debug mode
playwright_runner.set_debug_mode(True)

# Check status
if playwright_runner.get_debug_mode():
    print("Debug mode active")
```

## When to Use Debug Mode

### ✅ Use Debug Mode When:
- Troubleshooting new URLs
- Investigating failure patterns
- Testing configuration changes
- Debugging selector issues
- Analyzing PageSpeed Insights changes

### ⛔ Avoid Debug Mode When:
- Running large audits (1000+ URLs)
- Production scheduled runs
- CI/CD pipelines
- Limited disk space

## Log Integration

Debug mode adds verbose logging:

```
[DEBUG] Navigating to PageSpeed Insights...
[DEBUG] Page navigation took 2.34s
[DEBUG] Entering URL: https://example.com
[DEBUG] Attempting to click analyze button with selector 1/10
[INFO] Successfully clicked analyze button
[DEBUG] Found 1 score elements
[DEBUG] Successfully extracted mobile score: 85
[INFO] Debug screenshot saved: debug_screenshots/...
```

## Security Notes

⚠️ **Screenshots and HTML may contain**:
- Sensitive page content
- API keys in inline scripts
- Session tokens
- Private information

**Best Practices**:
1. Review before sharing
2. Clean up regularly
3. Never commit to version control (already in `.gitignore`)
4. Restrict directory access

## Related Files

| File | Purpose |
|------|---------|
| `tools/qa/playwright_runner.py` | Main implementation |
| `.gitignore` | Ignores debug artifacts |
| `ERROR_HANDLING_DEBUGGING.md` | Complete guide |
| `AGENTS.md` | Development documentation |

## Command Reference

```bash
# Enable debug mode
--debug-mode

# Disable progress bar (useful with debug mode)
--no-progress-bar

# Force retry (bypass circuit breaker)
--force-retry

# Combined example
python run_audit.py \
  --tab "Test" \
  --debug-mode \
  --force-retry \
  --no-progress-bar \
  --skip-cache
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |

Debug artifacts are saved regardless of exit code.

## Support Checklist

When reporting issues with error handling:

- [ ] Command used
- [ ] Error message (full text)
- [ ] Log excerpt (with timestamps)
- [ ] Screenshot (if available)
- [ ] HTML file (if available)
- [ ] System info (OS, Python version)
- [ ] Playwright version

## Quick Diagnosis

### Problem: Analyze button not found
1. Check screenshot for button visibility
2. Review HTML for button selectors
3. Verify PageSpeed Insights didn't change UI

### Problem: Score extraction fails
1. Check screenshot for score elements
2. Review HTML for gauge elements
3. Verify PageSpeed Insights score format

### Problem: Analysis timeout
1. Check URL accessibility
2. Verify PageSpeed Insights performance
3. Consider increasing `--timeout`

### Problem: Page reload loops
1. Check if URL is valid
2. Verify PageSpeed Insights availability
3. Review logs for patterns

## Version Info

Debug mode introduced in: **v1.0.0**

For latest features, see: [ERROR_HANDLING_DEBUGGING.md](ERROR_HANDLING_DEBUGGING.md)
