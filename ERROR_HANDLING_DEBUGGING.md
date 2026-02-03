# Error Handling and Debugging Guide

## Overview

The PageSpeed Insights audit tool includes comprehensive error handling and debugging capabilities in `playwright_runner.py`. These features help diagnose issues, recover from transient failures, and provide detailed context when errors occur.

## Key Features

### 1. Page Reload Recovery

When selectors fail to find elements on the page, the system automatically reloads and retries:

- **Automatic Reloading**: Up to 3 reload attempts per operation
- **Fresh Start Logic**: Each reload provides a clean page state
- **Tracking**: Reload attempts are tracked to prevent infinite loops
- **Smart Retry**: Only reloads when it makes sense (selector timeouts, button not found)

**Implementation**: `PageReloadTracker` class tracks reload attempts and prevents excessive reloading.

### 2. Debug Mode (`--debug-mode`)

Enable comprehensive debugging with the `--debug-mode` flag:

```bash
python run_audit.py --tab "TAB_NAME" --debug-mode
```

When enabled:
- ✅ Full-page screenshots captured on errors
- ✅ Complete HTML source saved for analysis
- ✅ Verbose logging to console and log files
- ✅ Diagnostic information extracted from page
- ✅ Enhanced error messages with context

### 3. Screenshot Capture

Screenshots are automatically saved when errors occur:

**Location**: `debug_screenshots/` directory (created automatically)

**Filename Format**: `YYYYMMDD_HHMMSS_sanitized-url_reason.png`

**Example**: `20240115_143022_example_com_button_not_found.png`

**Captured On**:
- Button not found (analyze button, device buttons)
- Selector timeouts
- Score extraction failures
- Analysis completion timeouts
- Unexpected errors

**Features**:
- Full-page screenshots (entire scrollable area)
- Timestamp for easy correlation with logs
- Sanitized URL in filename (safe for filesystem)
- Reason suffix indicates error type

### 4. HTML Source Capture

Complete page HTML is saved alongside screenshots:

**Location**: `debug_screenshots/` directory

**Filename Format**: `YYYYMMDD_HHMMSS_sanitized-url_reason.html`

**Example**: `20240115_143022_example_com_button_not_found.html`

**Benefits**:
- Post-mortem analysis of page structure
- Verify selector availability
- Inspect dynamic content loading
- Debug JavaScript rendering issues

### 5. Enhanced Error Messages

Error messages include rich diagnostic context:

**Components**:
1. **Original Error**: Base error message
2. **Last Successful Step**: Where the process was before failure
3. **Current Page Info**:
   - Page URL
   - Page title
4. **Available Elements**:
   - Buttons (text, visibility)
   - Input fields (type, placeholder, visibility)
   - Links (text, href, visibility)
5. **Debug Artifacts**:
   - Path to screenshot
   - Path to HTML file

**Example Enhanced Error**:
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
  2. search input (hidden) - 

Debug screenshot saved: debug_screenshots/20240115_143022_example_com_button_not_found.png
Debug HTML saved: debug_screenshots/20240115_143022_example_com_button_not_found.html
```

### 6. Page Diagnostics

The system extracts diagnostic information from the page automatically:

**Extracted Information**:
- Current page URL
- Page title
- All buttons with text and visibility
- All input fields with type, placeholder, visibility
- All links with text, href, visibility

**Limits**:
- Maximum 10 elements per type (prevents excessive output)
- Text truncated to 50 characters
- Only includes relevant attributes

**Use Cases**:
- Verify selectors are targeting correct elements
- Check if elements are hidden vs visible
- Understand page structure during failure
- Debug dynamic content loading

## Usage Examples

### Basic Usage with Debug Mode

```bash
# Enable debug mode for a single audit
python run_audit.py --tab "Production URLs" --debug-mode
```

### Combined with Other Flags

```bash
# Debug mode + skip cache + dry run
python run_audit.py --tab "Test URLs" --debug-mode --skip-cache --dry-run

# Debug mode + force retry + custom timeout
python run_audit.py --tab "Problematic URLs" --debug-mode --force-retry --timeout 1200

# Debug mode + resume from specific row
python run_audit.py --tab "Large Dataset" --debug-mode --resume-from-row 100
```

### Debug Mode in Config File

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

## Recovery Strategies

### 1. Selector Timeout Recovery

**Error**: `PlaywrightSelectorTimeoutError`

**Strategy**:
1. Retry with page reload (up to 3 attempts)
2. Try multiple selector strategies
3. Capture screenshot and HTML on final failure
4. Provide enhanced error with page context

**Example Flow**:
```
Attempt 1: Click button → Timeout
→ Reload page → Retry
Attempt 2: Click button → Timeout
→ Reload page → Retry
Attempt 3: Click button → Timeout
→ Capture debug artifacts → Fail with enhanced error
```

### 2. Analysis Timeout Recovery

**Error**: `PlaywrightAnalysisTimeoutError`

**Strategy**:
- Immediate abort (not retryable)
- Capture debug artifacts
- Report with enhanced context

**Reason**: Analysis timeouts indicate slow PageSpeed Insights processing, not transient selector issues.

### 3. Button Not Found Recovery

**Strategy**:
1. Try 10 different button selectors
2. If all fail, reload page
3. Retry with all selectors again (up to 2 total attempts)
4. Capture debug artifacts on final failure

### 4. Score Extraction Failure Recovery

**Strategy**:
1. Try multiple score selectors (primary + fallback)
2. Retry up to 5 times with 1s delay
3. Validate extracted scores (0-100 range)
4. Capture debug artifacts if all attempts fail

## Debug Artifacts Management

### Directory Structure

```
debug_screenshots/
├── 20240115_143022_example_com_button_not_found.png
├── 20240115_143022_example_com_button_not_found.html
├── 20240115_143045_test_site_com_analysis_timeout.png
├── 20240115_143045_test_site_com_analysis_timeout.html
└── ...
```

### Cleanup

Debug artifacts are **not** automatically deleted. Manage them manually:

```bash
# Remove all debug artifacts
rm -rf debug_screenshots/

# Remove artifacts older than 7 days (Unix/Linux)
find debug_screenshots/ -type f -mtime +7 -delete

# Remove artifacts older than 7 days (Windows PowerShell)
Get-ChildItem debug_screenshots/ -Recurse | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item
```

### Storage Considerations

- Screenshots: ~100-500 KB each
- HTML files: ~50-200 KB each
- 100 errors = ~15-70 MB total

**Recommendation**: Clean up debug artifacts regularly in production environments.

## Troubleshooting

### Debug Mode Not Working

**Check**:
1. Verify `--debug-mode` flag is set
2. Check write permissions on current directory
3. Verify disk space available
4. Check logs for "Debug mode enabled" message

### Screenshots Not Captured

**Possible Causes**:
1. Playwright page is None (error too early)
2. Permission issues creating `debug_screenshots/` directory
3. Disk full
4. Playwright not properly installed

**Solution**:
```bash
# Verify Playwright installation
playwright install chromium

# Check disk space
df -h  # Unix/Linux
Get-PSDrive  # Windows PowerShell

# Test directory creation
mkdir debug_screenshots
```

### Enhanced Errors Not Showing

**Possible Causes**:
1. Error occurs before page is available
2. Old version of `playwright_runner.py`

**Solution**:
```bash
# Verify latest version
git pull origin main

# Check for enhanced error creation
grep "_create_enhanced_error_message" tools/qa/playwright_runner.py
```

## Best Practices

### 1. Use Debug Mode During Development

```bash
# Always use debug mode when testing new features
python run_audit.py --tab "Test" --debug-mode --dry-run
```

### 2. Enable Debug Mode for First Run

```bash
# First run on new spreadsheet
python run_audit.py --tab "New Data" --debug-mode --validate-only
```

### 3. Debug Problematic URLs

```bash
# Isolate and debug specific URLs
python run_audit.py --tab "All URLs" --filter "https://problematic-site\.com/.*" --debug-mode
```

### 4. Review Debug Artifacts

After failures:
1. Check screenshots for visual confirmation
2. Review HTML for selector availability
3. Correlate with log timestamps
4. Identify patterns in failures

### 5. Clean Up Regularly

```bash
# Weekly cleanup script (Unix/Linux)
#!/bin/bash
find debug_screenshots/ -type f -mtime +7 -delete
echo "Cleaned debug artifacts older than 7 days"

# Add to crontab for automatic cleanup
# 0 0 * * 0 /path/to/cleanup-script.sh
```

## Integration with Logging

Debug mode integrates with the existing logging system:

**Log Levels**:
- `DEBUG`: Detailed selector attempts, page navigation
- `INFO`: Successful operations, debug artifact paths
- `WARNING`: Reload attempts, fallback strategies
- `ERROR`: Failures with enhanced context

**Example Log Output** (with debug mode):
```
2024-01-15 14:30:22 [INFO] Debug mode enabled: verbose logging, screenshots, and HTML capture on errors
2024-01-15 14:30:25 [DEBUG] Navigating to PageSpeed Insights...
2024-01-15 14:30:27 [DEBUG] Page navigation took 2.34s
2024-01-15 14:30:27 [DEBUG] Entering URL: https://example.com
2024-01-15 14:30:27 [DEBUG] Attempting to click analyze button with selector 1/10: button:has-text("Analyze")
2024-01-15 14:30:28 [INFO] Successfully clicked analyze button using selector: button:has-text("Analyze")
2024-01-15 14:30:32 [DEBUG] Found 1 score elements
2024-01-15 14:30:33 [DEBUG] Mobile/Desktop buttons are visible (mobile: True, desktop: True)
2024-01-15 14:30:35 [DEBUG] Successfully extracted mobile score: 85 using selector .lh-exp-gauge__percentage (attempt 1/5)
2024-01-15 14:30:37 [INFO] Debug screenshot saved: debug_screenshots/20240115_143037_example_com_screenshot_success.png
```

## API Reference

### Functions

#### `set_debug_mode(enabled: bool)`
Enable or disable debug mode globally.

```python
from tools.qa import playwright_runner

playwright_runner.set_debug_mode(True)
```

#### `get_debug_mode() -> bool`
Check if debug mode is currently enabled.

```python
if playwright_runner.get_debug_mode():
    print("Debug mode is active")
```

### Classes

#### `PageReloadTracker`
Track page reload attempts for recovery logic.

**Attributes**:
- `reload_count: int` - Number of reloads performed
- `max_reloads: int` - Maximum allowed reloads (default: 3)
- `last_reload_time: float` - Timestamp of last reload

**Methods**:
- `should_reload() -> bool` - Check if another reload is allowed
- `record_reload()` - Increment reload counter
- `reset()` - Reset reload counter

### Private Functions

#### `_save_debug_screenshot(page, url, reason) -> Optional[str]`
Capture and save a screenshot.

**Returns**: Path to saved screenshot or None

#### `_save_debug_html(page, url, reason) -> Optional[str]`
Save page HTML.

**Returns**: Path to saved HTML file or None

#### `_get_page_info(page) -> Dict`
Extract diagnostic information from page.

**Returns**: Dictionary with URL, title, buttons, inputs, links

#### `_create_enhanced_error_message(...) -> str`
Create an enhanced error message with context.

**Returns**: Formatted error message string

#### `_reload_page_with_retry(page, url, reload_tracker, logger) -> bool`
Reload page with retry logic.

**Returns**: True if reload successful

## Configuration

### Environment Variables

No environment variables are required for debug mode.

### File Locations

| File Type | Location | Pattern |
|-----------|----------|---------|
| Screenshots | `debug_screenshots/` | `*.png` |
| HTML | `debug_screenshots/` | `*.html` |
| Logs | `logs/` | `audit_*.log` |

### Gitignore

Debug artifacts are automatically ignored:

```gitignore
# Debug artifacts (playwright_runner.py)
debug_screenshots/
*.png
*.html
```

## Performance Impact

**Debug Mode ON**:
- Screenshot capture: ~500ms per error
- HTML save: ~100ms per error
- Page diagnostics: ~50ms per error
- Total overhead: ~650ms per error

**Debug Mode OFF**:
- No performance impact
- Standard error messages
- No artifact capture

**Recommendation**: 
- Use debug mode during development and troubleshooting
- Disable for production high-volume audits
- Enable selectively for problematic URLs

## Security Considerations

### Screenshot Content

Screenshots may contain:
- ⚠️ Sensitive page content
- ⚠️ Private information in page elements
- ⚠️ API responses in developer tools (if visible)

**Recommendations**:
1. Review screenshots before sharing
2. Redact sensitive information
3. Clean up artifacts regularly
4. Restrict access to `debug_screenshots/` directory

### HTML Content

HTML files may contain:
- ⚠️ Inline scripts with API keys
- ⚠️ Hidden form fields with tokens
- ⚠️ Session identifiers in attributes

**Recommendations**:
1. Never commit HTML files to version control
2. Sanitize before sharing with third parties
3. Automated cleanup after troubleshooting

## Changelog

### Version 1.0.0
- Initial implementation of page reload recovery
- Added debug mode with screenshot capture
- Implemented HTML source saving
- Created enhanced error messages
- Added page diagnostics extraction
- Integrated with CLI via `--debug-mode` flag

## Future Enhancements

Planned improvements:
1. **Configurable Retention**: Auto-delete debug artifacts after N days
2. **Selective Capture**: Only capture screenshots for specific error types
3. **Video Recording**: Capture full session video for complex failures
4. **HAR Files**: Save HTTP Archive files for network debugging
5. **Performance Profiling**: Capture browser performance metrics
6. **Cloud Upload**: Automatically upload debug artifacts to cloud storage
7. **Error Correlation**: Group similar errors and deduplicate screenshots

## Support

For issues with error handling or debugging:

1. Check this guide first
2. Review log files in `logs/` directory
3. Examine debug artifacts in `debug_screenshots/`
4. Open an issue with:
   - Error message
   - Log excerpt
   - Screenshots (if available)
   - Command used
   - System information

## Related Documentation

- [AGENTS.md](AGENTS.md) - Complete development guide
- [ERROR_HANDLING_GUIDE.md](ERROR_HANDLING_GUIDE.md) - Error handling overview
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - General troubleshooting
- [PLAYWRIGHT_TESTING.md](PLAYWRIGHT_TESTING.md) - Playwright testing guide
