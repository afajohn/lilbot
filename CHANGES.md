# Changes Summary

## Issues Fixed

### 1. Unicode Decode Error (Primary Issue)
**Problem:** 
- Windows encoding error: `UnicodeDecodeError: 'charmap' codec can't decode byte 0x90`
- Occurred when running subprocess commands (Cypress)
- Windows default encoding (cp1252) couldn't handle non-ASCII characters in Cypress output

**Solution:**
- Added explicit UTF-8 encoding to all `subprocess.run()` calls
- Added `errors='replace'` to handle any remaining encoding issues gracefully
- Files modified:
  - `tools/qa/cypress_runner.py` - Line 105-115
  - `validate_setup.py` - Lines 43, 55, 83

**Code Changes:**
```python
# Before
subprocess.run([...], capture_output=True, text=True)

# After
subprocess.run([...], capture_output=True, text=True, encoding='utf-8', errors='replace')
```

### 2. Wrong Starting Row for URLs
**Problem:**
- URLs were read from A1:A (including header row)
- First URL in row 1 was being treated as data

**Solution:**
- Changed range from `A:A` to `A2:A` to skip header row
- Updated enumeration to start from row 2 instead of row 1
- Files modified:
  - `tools/sheets/sheets_client.py` - Lines 104, 130

**Code Changes:**
```python
# Before
range_name = f"{tab_name}!A:A"
for idx, row in enumerate(values, start=1):

# After
range_name = f"{tab_name}!A2:A"
for idx, row in enumerate(values, start=2):
```

## Documentation Updates

### New Files Created

1. **INSTALL.md** - Comprehensive installation guide
   - Step-by-step setup instructions
   - Platform-specific notes (Windows, Mac, Linux)
   - Troubleshooting for common installation issues

2. **QUICKSTART.md** - Quick reference guide
   - 5-minute setup overview
   - Common commands reference
   - Quick troubleshooting tips

3. **CHANGES.md** - This file
   - Summary of all changes made
   - Technical details for developers

### Updated Files

1. **README.md** - Enhanced with:
   - Links to all documentation files
   - Key features list
   - Clarification that row 1 is treated as header
   - Updated spreadsheet format examples
   - Windows encoding error fix documentation
   - Better organized sections

2. **AGENTS.md** - Updated with:
   - Actual tech stack details
   - Project architecture documentation
   - Code style guidelines
   - Important implementation details (encoding fix)
   - Common tasks and debugging info

## Technical Details

### Encoding Issue Deep Dive

**Root Cause:**
- Python's `subprocess` module on Windows defaults to `cp1252` encoding
- Cypress outputs contain UTF-8 characters (DevTools messages, URLs, etc.)
- Byte 0x90 is valid in UTF-8 but undefined in cp1252

**Why It Happened:**
- Cypress outputs browser messages containing special characters
- DevTools listening messages contain non-ASCII characters
- Without explicit encoding, Python uses system default (cp1252 on Windows)

**Complete Fix:**
```python
result = subprocess.run(
    [npx_path, 'cypress', 'run', '--spec', 'cypress/e2e/analyze-url.cy.js'],
    cwd=repo_root,
    env=cypress_env,
    capture_output=True,
    text=True,
    encoding='utf-8',      # Force UTF-8 encoding
    errors='replace',       # Replace undecodable bytes with �
    timeout=timeout,
    shell=False
)
```

### Row Enumeration Fix

**Why Row 2:**
- Google Sheets uses 1-based indexing
- Row 1 is the header ("URL", etc.)
- Data starts at row 2
- When writing PSI URLs back, we need correct row numbers

**Implementation:**
```python
# Reading
range_name = f"{tab_name}!A2:A"  # Start from A2
for idx, row in enumerate(values, start=2):  # Enumerate from 2
    urls.append((idx, url))  # idx will be 2, 3, 4, ...

# Writing
range_name = f"{tab_name}!{column}{row_index}"  # row_index is 2, 3, 4, ...
```

## Testing Recommendations

To verify the fixes:

1. **Unicode Fix:**
   ```bash
   python run_audit.py --tab "Barranquilla Singles" --service-account "service-account.json"
   ```
   Should no longer produce UnicodeDecodeError

2. **Row Number Fix:**
   - Check that PSI URLs are written to the correct rows
   - Row 2's PSI URL should appear in F2/G2, not F1/G1
   - Verify header row (row 1) is not overwritten

3. **Overall Verification:**
   ```bash
   python validate_setup.py
   ```
   Should pass all checks

## Files Modified

### Code Files
- `tools/qa/cypress_runner.py` - UTF-8 encoding fix
- `tools/sheets/sheets_client.py` - A2:A range and row enumeration fix
- `validate_setup.py` - UTF-8 encoding fix

### Documentation Files
- `README.md` - Enhanced and reorganized
- `AGENTS.md` - Complete rewrite with actual project details
- `INSTALL.md` - New comprehensive installation guide
- `QUICKSTART.md` - New quick reference guide
- `CHANGES.md` - New change log (this file)

## Backward Compatibility

These changes are **backward compatible**:
- Existing spreadsheets work with row 1 as header
- Encoding fix doesn't break non-Windows systems
- No API changes to any functions
- No configuration changes required

## Future Improvements

Potential enhancements not implemented in this fix:
1. Make starting row configurable (--start-row flag)
2. Make output columns configurable via CLI
3. Add formal test suite
4. Add progress bar for long audits
5. Support multiple spreadsheets in one run
6. Cache results to avoid re-analyzing unchanged URLs
