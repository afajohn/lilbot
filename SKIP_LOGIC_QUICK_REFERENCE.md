# Skip Logic Quick Reference Card

## Core Rule
**Skip row ONLY if BOTH columns F AND G are complete**

## What is "Complete"?
Column is complete if it has **EITHER**:
- Text containing "passed" (case-insensitive)
- Background color `#b7e1cd`

## Decision Matrix

```
F Complete?  |  G Complete?  |  Action
-------------|---------------|--------
     ✓       |       ✓       |  SKIP
     ✓       |       ✗       |  PROCESS
     ✗       |       ✓       |  PROCESS
     ✗       |       ✗       |  PROCESS
```

## Common Scenarios

| Scenario | Skip? |
|----------|-------|
| F="passed", G="passed" | ✓ SKIP |
| F="passed", G=empty | ✗ PROCESS |
| F=empty, G="passed" | ✗ PROCESS |
| F=green bg, G=green bg | ✓ SKIP |
| F=green bg, G=empty | ✗ PROCESS |
| F="passed", G=green bg | ✓ SKIP |
| F=PSI URL, G=PSI URL | ✗ PROCESS |
| F=empty, G=empty | ✗ PROCESS |

## Testing Commands

```bash
# Run unit tests
pytest tests/unit/test_sheets_client.py::TestCheckSkipConditions -v

# Run validation script
python validate_skip_logic.py

# Generate test scenarios
python generate_test_spreadsheet_scenarios.py
```

## Debugging

Enable debug logging to see skip decisions:
```python
import logging
from tools.utils.logger import get_logger

logger = get_logger()
logger.setLevel(logging.DEBUG)
```

## Key Files

- **Implementation**: `tools/sheets/sheets_client.py` → `_check_skip_conditions()`
- **Tests**: `tests/unit/test_sheets_client.py` → `TestCheckSkipConditions`
- **Documentation**: `SKIP_LOGIC.md`
- **Validation**: `validate_skip_logic.py`

## Color Reference

Target background color: `#b7e1cd`
- RGB: `(183, 225, 205)`
- Decimal: `(0.718, 0.882, 0.804)`
