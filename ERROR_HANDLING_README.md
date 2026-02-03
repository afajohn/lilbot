# Error Handling and Recovery - README

## Quick Start

Enable debug mode for better error diagnostics:

```bash
python run_audit.py --tab "TAB_NAME" --debug-mode
```

Debug artifacts are saved to `debug_screenshots/` directory.

## What's New

### 1. Page Reload Recovery ✨
Automatically reloads the page when selectors fail, providing a fresh start:
- Up to 3 reload attempts
- Smart retry logic
- Prevents infinite loops

### 2. Debug Mode (`--debug-mode`) 🔍
Comprehensive debugging with one flag:
- Full-page screenshots on errors
- Complete HTML source capture
- Verbose logging
- Enhanced error messages

### 3. Enhanced Error Messages 📝
Rich error context including:
- Current page URL and title
- Available buttons and elements
- Last successful step
- Visibility status of elements
- Paths to debug artifacts

### 4. Automatic Screenshot Capture 📸
Screenshots saved automatically on:
- Button not found
- Selector timeouts
- Score extraction failures
- Analysis timeouts
- Any unexpected errors

### 5. HTML Source Capture 💾
Complete page HTML saved alongside screenshots for:
- Post-mortem analysis
- Selector verification
- Understanding page structure
- JavaScript debugging

## Usage

### Basic Command

```bash
python run_audit.py --tab "Production URLs" --debug-mode
```

### Common Combinations

```bash
# Debug + Skip Cache
python run_audit.py --tab "Test" --debug-mode --skip-cache

# Debug + Force Retry
python run_audit.py --tab "Test" --debug-mode --force-retry

# Debug + Dry Run
python run_audit.py --tab "Test" --debug-mode --dry-run

# Debug + Resume from Row
python run_audit.py --tab "Test" --debug-mode --resume-from-row 100

# Debug + URL Filter
python run_audit.py --tab "Test" --debug-mode --filter "https://example\.com/.*"
```

### Config File

```yaml
# config.yaml
tab: "Production URLs"
debug_mode: true
timeout: 900
skip_cache: false
```

```bash
python run_audit.py --config config.yaml
```

## Features in Detail

### Page Reload Recovery

When selectors fail to find elements, the system:
1. Attempts to reload the page (up to 3 times)
2. Provides a fresh page state
3. Retries the failed operation
4. Captures debug artifacts on final failure

**Benefits**:
- Handles transient PageSpeed Insights rendering issues
- Automatic recovery from temporary page glitches
- No manual intervention needed

### Debug Screenshots

**Location**: `debug_screenshots/`

**Format**: `YYYYMMDD_HHMMSS_sanitized-url_reason.png`

**Examples**:
```
20240115_143022_example_com_button_not_found.png
20240115_143045_test_site_com_analysis_timeout.png
20240115_143102_staging_example_com_score_extraction_failed.png
```

**Captured On**:
- Input field not found
- Analyze button not found
- Device buttons timeout
- Analysis completion timeout
- Desktop switch failed
- Score extraction failed
- Unexpected errors

**Features**:
- Full-page screenshots (entire scrollable area)
- High quality PNG format
- Automatic filename with timestamp
- Sanitized URL (filesystem-safe)

### Debug HTML Files

**Location**: `debug_screenshots/`

**Format**: `YYYYMMDD_HHMMSS_sanitized-url_reason.html`

**Use Cases**:
- Verify selector availability in DOM
- Check dynamic content loading
- Debug JavaScript rendering
- Analyze page structure

**Content**: Complete HTML source including:
- All elements and attributes
- Inline scripts
- Style definitions
- Dynamic content state

### Enhanced Error Messages

**Without Debug Mode**:
```
Failed to click analyze button - all selectors failed
```

**With Debug Mode**:
```
Failed to click analyze button after 2 attempts - all selectors failed

Last successful step: Entered URL in input field

Current page URL: https://pagespeed.web.dev/
Page title: PageSpeed Insights

Available buttons:
  1. Analyze (visible)
  2. Learn more (visible)
  3. Settings (hidden)

Available inputs:
  1. url input (visible) - Enter a web page URL

Debug screenshot saved: debug_screenshots/20240115_143022_example_com_button_not_found.png
Debug HTML saved: debug_screenshots/20240115_143022_example_com_button_not_found.html
```

**Components**:
1. **Base Error**: Original error message
2. **Last Step**: Last successful operation
3. **Page Info**: URL, title
4. **Elements**: Buttons, inputs, links with visibility
5. **Artifacts**: Paths to screenshot and HTML

## When to Use Debug Mode

### ✅ Use When:
- First run on new spreadsheet
- Troubleshooting URL failures
- Investigating error patterns
- Testing configuration changes
- Debugging selector issues
- Analyzing PageSpeed Insights changes
- Development and testing

### ⛔ Avoid When:
- Large production audits (1000+ URLs)
- Scheduled automated runs
- CI/CD pipelines
- Limited disk space (<1 GB free)
- High-volume concurrent processing

## Performance

### Overhead

| Mode | Time per Error |
|------|---------------|
| Debug OFF | ~50ms |
| Debug ON | ~650ms |

**Components** (Debug ON):
- Screenshot: ~500ms
- HTML save: ~100ms
- Page diagnostics: ~50ms

### Disk Space

| Files | Size per Error |
|-------|---------------|
| Screenshot | ~100-500 KB |
| HTML | ~50-200 KB |
| **Total** | ~150-700 KB |

**100 errors ≈ 15-70 MB**

### Recommendations

✅ **Enable** for:
- Development (always)
- First-time audits
- Troubleshooting specific issues

⛔ **Disable** for:
- Production runs >100 URLs
- Automated scheduled jobs
- Performance-critical operations

## Cleanup

### Remove All Artifacts

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
Get-ChildItem debug_screenshots/ -Recurse | 
  Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | 
  Remove-Item
```

### Automated Cleanup Script

```bash
#!/bin/bash
# cleanup-debug.sh
find debug_screenshots/ -type f -mtime +7 -delete
echo "Cleaned debug artifacts older than 7 days"
```

```bash
chmod +x cleanup-debug.sh
./cleanup-debug.sh
```

Add to crontab for weekly cleanup:
```bash
# Run every Sunday at midnight
0 0 * * 0 /path/to/cleanup-debug.sh
```

## Troubleshooting

### Issue: Debug mode not enabled

**Symptoms**: No screenshots, standard errors

**Check**:
```bash
# Look for this in logs
grep "Debug mode enabled" logs/audit_*.log
```

**Solution**: Verify `--debug-mode` flag is set

### Issue: Screenshots not created

**Symptoms**: Error messages reference missing files

**Possible Causes**:
1. Permission issues
2. Disk full
3. Directory creation failed

**Solutions**:
```bash
# Check permissions
ls -la debug_screenshots/

# Check disk space
df -h

# Manually create directory
mkdir -p debug_screenshots
chmod 755 debug_screenshots
```

### Issue: Too many files

**Symptoms**: Directory contains thousands of files

**Solution**: Implement regular cleanup:
```bash
# Keep only last 24 hours
find debug_screenshots/ -type f -mtime +1 -delete
```

### Issue: Large file sizes

**Symptoms**: Screenshot files >5 MB

**Causes**: Very long pages or high-resolution

**Solution**: Normal for PageSpeed Insights pages, implement cleanup

## Security

### ⚠️ Screenshots May Contain

- Sensitive page content
- Private information
- User data in forms
- API responses
- Session identifiers

### ⚠️ HTML Files May Contain

- Inline JavaScript with API keys
- Hidden form fields with tokens
- Session cookies in attributes
- Private configuration data

### 🛡️ Best Practices

1. **Review before sharing** - Check content first
2. **Regular cleanup** - Don't keep forever
3. **Restrict access** - Limit directory permissions
4. **Never commit** - Already in `.gitignore`
5. **Sanitize** - Redact sensitive info before sharing

### 🔒 Recommended Permissions

```bash
# Linux/Mac
chmod 700 debug_screenshots/  # Owner only

# Verify
ls -la debug_screenshots/
# drwx------ ... debug_screenshots/
```

## Examples

### Example 1: First-Time Audit

```bash
# Enable debug mode for new spreadsheet
python run_audit.py \
  --tab "New Data" \
  --debug-mode \
  --validate-only

# Review validation results
ls -lh debug_screenshots/

# Run actual audit if validation passes
python run_audit.py \
  --tab "New Data" \
  --debug-mode
```

### Example 2: Troubleshooting Specific URL

```bash
# Filter and debug single URL
python run_audit.py \
  --tab "All URLs" \
  --filter "https://problematic-site\.com/.*" \
  --debug-mode \
  --skip-cache \
  --force-retry

# Review artifacts
ls -lh debug_screenshots/
```

### Example 3: Development Testing

```bash
# Test with dry run first
python run_audit.py \
  --tab "Test" \
  --debug-mode \
  --dry-run \
  --skip-cache

# Review and run real audit
python run_audit.py \
  --tab "Test" \
  --debug-mode
```

### Example 4: CI/CD Integration

```bash
# Production run without debug mode
python run_audit.py \
  --tab "Production" \
  --no-progress-bar

# Failed? Re-run failed URLs with debug
python run_audit.py \
  --tab "Production" \
  --filter "regex-of-failed-urls" \
  --debug-mode \
  --force-retry
```

## FAQ

### Q: Does debug mode slow down audits?
**A**: Yes, adds ~650ms per error. No impact on successful URLs.

### Q: Are screenshots safe to share?
**A**: Review first - may contain sensitive information.

### Q: How long should I keep debug artifacts?
**A**: 7 days is recommended, 24 hours for high-volume.

### Q: Can I use debug mode in production?
**A**: Yes, but only for troubleshooting, not regular runs.

### Q: Do I need to clean up manually?
**A**: Yes, automatic cleanup not implemented yet.

### Q: What if disk space runs out?
**A**: Playwright will fail, clean debug_screenshots/ first.

### Q: Are artifacts backed up?
**A**: No, local only. Backup manually if needed.

### Q: Can I disable screenshots but keep HTML?
**A**: Not currently, it's all-or-nothing with debug mode.

### Q: How do I report bugs with debug artifacts?
**A**: Sanitize sensitive data, then attach screenshot + HTML.

### Q: Does debug mode affect caching?
**A**: No, caching works the same way.

## Integration

### With Existing Features

Debug mode integrates seamlessly with:

- ✅ Result caching
- ✅ URL validation
- ✅ Circuit breaker
- ✅ Progress bar
- ✅ Force retry
- ✅ Concurrent workers
- ✅ Resume from row
- ✅ URL filtering
- ✅ Export to JSON/CSV

### With Logging

Debug mode enhances logs:

```
[INFO] Debug mode enabled: verbose logging, screenshots, and HTML capture on errors
[DEBUG] Navigating to PageSpeed Insights...
[DEBUG] Page navigation took 2.34s
[DEBUG] Entering URL: https://example.com
[DEBUG] Attempting to click analyze button with selector 1/10
[INFO] Successfully clicked analyze button
[INFO] Debug screenshot saved: debug_screenshots/...
```

### With Metrics

Debug artifacts don't affect metrics:
- Success/failure rates unchanged
- Timing excludes debug overhead
- Cache hit/miss unaffected

## Documentation

### Complete Guides

1. **ERROR_HANDLING_DEBUGGING.md** - Complete documentation
   - All features explained
   - API reference
   - Troubleshooting
   - Best practices

2. **ERROR_HANDLING_QUICK_REFERENCE.md** - Quick reference
   - Command examples
   - Common issues
   - Quick solutions

3. **ERROR_HANDLING_IMPLEMENTATION_SUMMARY.md** - Technical details
   - Implementation details
   - Architecture decisions
   - Testing recommendations

4. **AGENTS.md** - Development guide
   - Complete context
   - Command reference
   - Architecture overview

### Quick Links

- Commands: See `AGENTS.md` - Commands section
- Troubleshooting: See `ERROR_HANDLING_DEBUGGING.md` - Troubleshooting section
- API: See `ERROR_HANDLING_DEBUGGING.md` - API Reference section

## Support

### Getting Help

1. **Check documentation**: Start with this README
2. **Review logs**: Check `logs/audit_*.log`
3. **Examine artifacts**: Look at screenshots and HTML
4. **Search issues**: Check GitHub issues
5. **Create issue**: Include logs, screenshots, command used

### Reporting Issues

Include:
- [ ] Command used (sanitized)
- [ ] Error message (full text)
- [ ] Log excerpt (with timestamps)
- [ ] Screenshot (if available, sanitized)
- [ ] HTML file (if available, sanitized)
- [ ] System info (OS, Python version)
- [ ] Playwright version (`playwright --version`)

## Changelog

### v1.0.0 (Initial Release)
- ✨ Page reload recovery (up to 3 attempts)
- ✨ Debug mode flag (`--debug-mode`)
- ✨ Screenshot capture on errors
- ✨ HTML source capture
- ✨ Enhanced error messages
- ✨ Page diagnostics extraction
- ✨ Last successful step tracking
- 📝 Complete documentation

## Future Roadmap

### Planned Features
- 🔄 Configurable artifact retention
- 🎥 Video recording for complex failures
- 📊 HAR file capture for network debugging
- ☁️ Cloud upload option
- 📧 Email/Slack notifications with artifacts
- 🤖 ML-based failure prediction

### Under Consideration
- Real-time error dashboard
- Automated retry strategies
- Error correlation and grouping
- Screenshot comparison (before/after)

## Contributing

Contributions welcome! Areas needing help:
- Test coverage for error handling
- Additional recovery strategies
- Performance optimizations
- Documentation improvements

## License

Same as main project.

## Credits

Implemented as part of comprehensive error handling improvements.

---

**For more information**: See [ERROR_HANDLING_DEBUGGING.md](ERROR_HANDLING_DEBUGGING.md)

**Quick Reference**: See [ERROR_HANDLING_QUICK_REFERENCE.md](ERROR_HANDLING_QUICK_REFERENCE.md)

**Development Guide**: See [AGENTS.md](AGENTS.md)
