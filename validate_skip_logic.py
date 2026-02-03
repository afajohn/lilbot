#!/usr/bin/env python3
"""
Test script to validate skip logic in sheets_client.py

This script tests the _check_skip_conditions() function with various scenarios
to ensure it correctly identifies which rows should be skipped.

Skip Logic Rules:
- Skip ONLY if BOTH columns F AND G are complete (have "passed" text or #b7e1cd background)
- Partial fills (only F or only G) should NOT cause skip - allow processing of empty column
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from sheets.sheets_client import _check_skip_conditions, _has_target_background_color


def test_scenario(name, row_data, row_values, expected_skip):
    """Test a specific scenario and report results."""
    result = _check_skip_conditions(row_data, 0, row_values)
    status = "[PASS]" if result == expected_skip else "[FAIL]"
    print(f"{status} - {name}")
    if result != expected_skip:
        print(f"  Expected: {expected_skip}, Got: {result}")
        print(f"  Row values F={row_values[5] if len(row_values) > 5 else 'N/A'}, G={row_values[6] if len(row_values) > 6 else 'N/A'}")
    return result == expected_skip


def create_cell_with_green_bg():
    """Create a cell with #b7e1cd background color."""
    return {
        'effectiveFormat': {
            'backgroundColor': {
                'red': 0xb7 / 255,
                'green': 0xe1 / 255,
                'blue': 0xcd / 255
            }
        }
    }


def main():
    print("=" * 80)
    print("Skip Logic Validation Tests")
    print("=" * 80)
    print()
    
    all_passed = True
    
    print("Scenario Group 1: Both columns complete (SHOULD SKIP)")
    print("-" * 80)
    
    all_passed &= test_scenario(
        "Both F and G have 'passed' text",
        [],
        ['https://example.com', '', '', '', '', 'passed', 'passed'],
        True
    )
    
    all_passed &= test_scenario(
        "Both F and G have green background",
        [{
            'values': [
                {}, {}, {}, {}, {},
                create_cell_with_green_bg(),
                create_cell_with_green_bg()
            ]
        }],
        ['https://example.com', '', '', '', '', '', ''],
        True
    )
    
    all_passed &= test_scenario(
        "F has 'passed' text, G has green background",
        [{
            'values': [
                {}, {}, {}, {}, {},
                {},
                create_cell_with_green_bg()
            ]
        }],
        ['https://example.com', '', '', '', '', 'passed', ''],
        True
    )
    
    all_passed &= test_scenario(
        "F has green background, G has 'passed' text",
        [{
            'values': [
                {}, {}, {}, {}, {},
                create_cell_with_green_bg(),
                {}
            ]
        }],
        ['https://example.com', '', '', '', '', '', 'passed'],
        True
    )
    
    all_passed &= test_scenario(
        "Both have 'PASSED' (case insensitive)",
        [],
        ['https://example.com', '', '', '', '', 'PASSED', 'Passed'],
        True
    )
    
    all_passed &= test_scenario(
        "Both have text containing 'passed'",
        [],
        ['https://example.com', '', '', '', '', 'Test passed', 'URL passed validation'],
        True
    )
    
    print()
    print("Scenario Group 2: Only F complete (SHOULD NOT SKIP)")
    print("-" * 80)
    
    all_passed &= test_scenario(
        "Only F has 'passed' text, G empty",
        [],
        ['https://example.com', '', '', '', '', 'passed', ''],
        False
    )
    
    all_passed &= test_scenario(
        "Only F has green background, G empty",
        [{
            'values': [
                {}, {}, {}, {}, {},
                create_cell_with_green_bg(),
                {}
            ]
        }],
        ['https://example.com', '', '', '', '', '', ''],
        False
    )
    
    all_passed &= test_scenario(
        "Only F has PSI URL (not 'passed')",
        [],
        ['https://example.com', '', '', '', '', 'https://psi.url/mobile', ''],
        False
    )
    
    print()
    print("Scenario Group 3: Only G complete (SHOULD NOT SKIP)")
    print("-" * 80)
    
    all_passed &= test_scenario(
        "Only G has 'passed' text, F empty",
        [],
        ['https://example.com', '', '', '', '', '', 'passed'],
        False
    )
    
    all_passed &= test_scenario(
        "Only G has green background, F empty",
        [{
            'values': [
                {}, {}, {}, {}, {},
                {},
                create_cell_with_green_bg()
            ]
        }],
        ['https://example.com', '', '', '', '', '', ''],
        False
    )
    
    all_passed &= test_scenario(
        "Only G has PSI URL (not 'passed')",
        [],
        ['https://example.com', '', '', '', '', '', 'https://psi.url/desktop'],
        False
    )
    
    print()
    print("Scenario Group 4: Neither complete (SHOULD NOT SKIP)")
    print("-" * 80)
    
    all_passed &= test_scenario(
        "Both F and G empty",
        [{'values': [{}] * 7}],
        ['https://example.com', '', '', '', '', '', ''],
        False
    )
    
    all_passed &= test_scenario(
        "F has PSI URL, G empty (not 'passed')",
        [],
        ['https://example.com', '', '', '', '', 'https://psi.url/mobile', ''],
        False
    )
    
    all_passed &= test_scenario(
        "F empty, G has PSI URL (not 'passed')",
        [],
        ['https://example.com', '', '', '', '', '', 'https://psi.url/desktop'],
        False
    )
    
    all_passed &= test_scenario(
        "Both have PSI URLs (not 'passed')",
        [],
        ['https://example.com', '', '', '', '', 'https://psi.url/mobile', 'https://psi.url/desktop'],
        False
    )
    
    all_passed &= test_scenario(
        "F has different color, G empty",
        [{
            'values': [
                {}, {}, {}, {}, {},
                {
                    'effectiveFormat': {
                        'backgroundColor': {
                            'red': 1.0,
                            'green': 0.0,
                            'blue': 0.0
                        }
                    }
                },
                {}
            ]
        }],
        ['https://example.com', '', '', '', '', '', ''],
        False
    )
    
    print()
    print("Scenario Group 5: Edge cases")
    print("-" * 80)
    
    all_passed &= test_scenario(
        "Short row (less than 7 columns)",
        [],
        ['https://example.com'],
        False
    )
    
    all_passed &= test_scenario(
        "Empty row_data list",
        [],
        ['https://example.com', '', '', '', '', 'passed', 'passed'],
        True
    )
    
    all_passed &= test_scenario(
        "F has 'passedthrough' (contains 'passed'), G has 'passed'",
        [],
        ['https://example.com', '', '', '', '', 'passedthrough', 'passed'],
        True
    )
    
    print()
    print("=" * 80)
    print("Background Color Detection Test")
    print("=" * 80)
    
    test_cell = create_cell_with_green_bg()
    has_color = _has_target_background_color(test_cell)
    color_status = "[PASS]" if has_color else "[FAIL]"
    print(f"{color_status} - Correctly detects #b7e1cd color")
    all_passed &= has_color
    
    wrong_color_cell = {
        'effectiveFormat': {
            'backgroundColor': {
                'red': 1.0,
                'green': 0.0,
                'blue': 0.0
            }
        }
    }
    has_wrong_color = _has_target_background_color(wrong_color_cell)
    wrong_color_status = "[PASS]" if not has_wrong_color else "[FAIL]"
    print(f"{wrong_color_status} - Correctly rejects red color")
    all_passed &= not has_wrong_color
    
    empty_cell = {}
    has_no_color = _has_target_background_color(empty_cell)
    no_color_status = "[PASS]" if not has_no_color else "[FAIL]"
    print(f"{no_color_status} - Correctly handles empty cell")
    all_passed &= not has_no_color
    
    print()
    print("=" * 80)
    if all_passed:
        print("[SUCCESS] ALL TESTS PASSED!")
        print("=" * 80)
        return 0
    else:
        print("[FAILED] SOME TESTS FAILED!")
        print("=" * 80)
        return 1


if __name__ == '__main__':
    sys.exit(main())
