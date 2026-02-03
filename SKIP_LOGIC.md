# Skip Logic Documentation

## Overview

The skip logic in `sheets_client.py` determines which spreadsheet rows should be skipped during audit processing. This prevents re-auditing URLs that have already been successfully processed.

## Skip Rules

A row is **ONLY** skipped when **BOTH** columns F (mobile) AND G (desktop) are complete.

### What Constitutes "Complete"?

A column is considered complete if it has **either**:
1. Text containing the word "passed" (case-insensitive)
2. Background color `#b7e1cd` (light green)

### Skip Scenarios

| Column F (Mobile) | Column G (Desktop) | Action | Reason |
|-------------------|-------------------|--------|--------|
| "passed" | "passed" | **SKIP** | Both complete |
| "passed" | Empty | **PROCESS** | Only F complete, G needs processing |
| Empty | "passed" | **PROCESS** | Only G complete, F needs processing |
| Green background | Green background | **SKIP** | Both complete |
| Green background | Empty | **PROCESS** | Only F complete, G needs processing |
| Empty | Green background | **PROCESS** | Only G complete, F needs processing |
| "passed" | Green background | **SKIP** | Both complete (mixed indicators) |
| Green background | "passed" | **SKIP** | Both complete (mixed indicators) |
| PSI URL | Empty | **PROCESS** | F has URL but not "passed" marker |
| Empty | PSI URL | **PROCESS** | G has URL but not "passed" marker |
| PSI URL | PSI URL | **PROCESS** | Neither has "passed" marker |
| Empty | Empty | **PROCESS** | Both need processing |

## Implementation Details

### Function: `_check_skip_conditions()`

Located in `tools/sheets/sheets_client.py`, this function:

1. **Checks text content**: Looks for "passed" in columns F and G (case-insensitive, substring match)
2. **Checks background color**: Looks for RGB value `#b7e1cd` (183, 225, 205)
3. **Combines indicators**: A column is complete if it has "passed" text OR green background
4. **Applies AND logic**: Returns `True` (skip) only if BOTH columns are complete

### Debug Logging

The function logs detailed information for each row:

**When skipping:**
```
DEBUG: Skipping row 5: Both columns complete - F5 contains 'passed' text, G5 has #b7e1cd background
```

**When processing:**
```
DEBUG: Processing row 7: F complete, G incomplete - partial fill allows processing
```

Log extra data includes:
- `row`: Row number (1-based, matches spreadsheet)
- `mobile_complete`: Boolean indicating if F is complete
- `desktop_complete`: Boolean indicating if G is complete
- `mobile_passed_text`: Boolean indicating if F contains "passed"
- `mobile_green_bg`: Boolean indicating if F has green background
- `desktop_passed_text`: Boolean indicating if G contains "passed"
- `desktop_green_bg`: Boolean indicating if G has green background

### Enabling Debug Logging

To see skip logic debug messages, set the logger level to DEBUG:

```python
import logging
from tools.utils.logger import get_logger

logger = get_logger()
logger.setLevel(logging.DEBUG)
```

Or via environment variable (if implemented):
```bash
export LOG_LEVEL=DEBUG
python run_audit.py --tab "Sheet1"
```

## Testing

### Unit Tests

Comprehensive unit tests are in `tests/unit/test_sheets_client.py`:

- `TestCheckSkipConditions`: Tests all skip scenarios
  - Both columns complete (various combinations)
  - Only F complete
  - Only G complete
  - Neither complete
  - Edge cases

Run tests:
```bash
pytest tests/unit/test_sheets_client.py::TestCheckSkipConditions -v
```

### Validation Script

Run the standalone validation script to test all scenarios:

```bash
python validate_skip_logic.py
```

This script tests:
- Both columns complete (6 scenarios) → Should SKIP
- Only F complete (3 scenarios) → Should NOT skip
- Only G complete (3 scenarios) → Should NOT skip
- Neither complete (5 scenarios) → Should NOT skip
- Edge cases (3 scenarios)
- Background color detection (3 tests)

Expected output:
```
================================================================================
Skip Logic Validation Tests
================================================================================

Scenario Group 1: Both columns complete (SHOULD SKIP)
--------------------------------------------------------------------------------
✓ PASS - Both F and G have 'passed' text
✓ PASS - Both F and G have green background
...
✓ ALL TESTS PASSED!
```

## Usage in Audit Pipeline

The skip logic is automatically applied in `read_urls()`:

```python
urls = read_urls(spreadsheet_id, tab_name, service=service)

for row_idx, url, mobile_psi, desktop_psi, should_skip in urls:
    if should_skip:
        logger.info(f"Skipping row {row_idx}: Already processed")
        continue
    
    # Process URL...
```

## Common Questions

### Q: Why doesn't a row with only F filled skip?

**A:** The system allows partial completion. If only F is filled, G still needs processing. This enables:
- Re-running audits when one platform fails
- Processing only mobile or only desktop
- Recovering from interrupted audits

### Q: What if F has a PSI URL but not "passed"?

**A:** The row will be processed. A PSI URL without the "passed" marker or green background indicates the audit ran but may not have passed the threshold (score < 80).

### Q: Can I mark a column complete manually?

**A:** Yes, either:
1. Type "passed" in the cell
2. Set the cell background color to `#b7e1cd`
3. Let the audit complete (it will write "passed" for scores ≥ 80)

### Q: Is "passed" case-sensitive?

**A:** No. "passed", "PASSED", "Passed" are all recognized.

### Q: Does it have to be exactly "passed"?

**A:** No. Any text containing "passed" is recognized (e.g., "Test passed", "URL passed validation").

## Color Reference

The target background color `#b7e1cd` is a light green/mint color:
- **Hex**: `#b7e1cd`
- **RGB**: `rgb(183, 225, 205)`
- **Decimal**: `red=0.718, green=0.882, blue=0.804`

This color is commonly used in spreadsheets to indicate success or completion.

## Troubleshooting

### Issue: Rows are being skipped unexpectedly

**Check:**
1. Enable DEBUG logging to see skip reasons
2. Verify both F and G don't have "passed" text or green background
3. Check for invisible characters or formatting

### Issue: Rows are not being skipped

**Check:**
1. Verify BOTH F and G have completion markers
2. Check the background color is exactly `#b7e1cd`
3. Verify "passed" text is present (case-insensitive)

### Issue: Want to re-process a completed row

**Solutions:**
1. Clear both F and G cells
2. Change the text to something other than "passed"
3. Change the background color

## Future Enhancements

Potential improvements to the skip logic:

1. **Configurable markers**: Allow custom text instead of "passed"
2. **Date-based re-processing**: Auto-reprocess after N days
3. **Score-based skipping**: Only skip if score meets threshold
4. **Selective re-processing**: Flag to force re-audit even if complete
5. **Skip report**: Generate report of skipped vs processed rows
