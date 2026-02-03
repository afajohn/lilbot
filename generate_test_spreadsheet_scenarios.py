#!/usr/bin/env python3
"""
Generate test spreadsheet scenarios for skip logic validation.

This script creates example data structures that simulate different spreadsheet
configurations for testing the skip logic. It can be used to:
1. Understand the expected data format from Google Sheets API
2. Create test fixtures for unit tests
3. Debug skip logic issues
"""

import json
from typing import List, Dict, Any


def create_cell_with_green_bg() -> Dict[str, Any]:
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


def create_cell_with_text(text: str) -> Dict[str, Any]:
    """Create a cell with formatted text."""
    return {
        'formattedValue': text,
        'effectiveFormat': {}
    }


def create_empty_cell() -> Dict[str, Any]:
    """Create an empty cell."""
    return {}


def generate_scenario_1_both_passed_text() -> Dict[str, Any]:
    """
    Scenario 1: Both F and G have 'passed' text
    Expected: SKIP
    """
    return {
        'description': 'Both F and G have "passed" text',
        'expected_skip': True,
        'row_values': ['https://example.com', '', '', '', '', 'passed', 'passed'],
        'row_data': [{
            'values': [
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_cell_with_text('passed'),
                create_cell_with_text('passed')
            ]
        }]
    }


def generate_scenario_2_both_green_bg() -> Dict[str, Any]:
    """
    Scenario 2: Both F and G have green background
    Expected: SKIP
    """
    return {
        'description': 'Both F and G have #b7e1cd background',
        'expected_skip': True,
        'row_values': ['https://example.com', '', '', '', '', '', ''],
        'row_data': [{
            'values': [
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_cell_with_green_bg(),
                create_cell_with_green_bg()
            ]
        }]
    }


def generate_scenario_3_mixed_complete() -> Dict[str, Any]:
    """
    Scenario 3: F has 'passed' text, G has green background
    Expected: SKIP
    """
    return {
        'description': 'F has "passed" text, G has green background',
        'expected_skip': True,
        'row_values': ['https://example.com', '', '', '', '', 'passed', ''],
        'row_data': [{
            'values': [
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_cell_with_text('passed'),
                create_cell_with_green_bg()
            ]
        }]
    }


def generate_scenario_4_only_f_passed() -> Dict[str, Any]:
    """
    Scenario 4: Only F has 'passed' text, G empty
    Expected: DO NOT SKIP (process G)
    """
    return {
        'description': 'Only F has "passed" text, G empty',
        'expected_skip': False,
        'row_values': ['https://example.com', '', '', '', '', 'passed', ''],
        'row_data': [{
            'values': [
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_cell_with_text('passed'),
                create_empty_cell()
            ]
        }]
    }


def generate_scenario_5_only_g_passed() -> Dict[str, Any]:
    """
    Scenario 5: Only G has 'passed' text, F empty
    Expected: DO NOT SKIP (process F)
    """
    return {
        'description': 'Only G has "passed" text, F empty',
        'expected_skip': False,
        'row_values': ['https://example.com', '', '', '', '', '', 'passed'],
        'row_data': [{
            'values': [
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_cell_with_text('passed')
            ]
        }]
    }


def generate_scenario_6_only_f_green() -> Dict[str, Any]:
    """
    Scenario 6: Only F has green background, G empty
    Expected: DO NOT SKIP (process G)
    """
    return {
        'description': 'Only F has green background, G empty',
        'expected_skip': False,
        'row_values': ['https://example.com', '', '', '', '', '', ''],
        'row_data': [{
            'values': [
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_cell_with_green_bg(),
                create_empty_cell()
            ]
        }]
    }


def generate_scenario_7_psi_urls() -> Dict[str, Any]:
    """
    Scenario 7: Both F and G have PSI URLs (not 'passed')
    Expected: DO NOT SKIP (URLs indicate audit ran but may not have passed)
    """
    return {
        'description': 'Both F and G have PSI URLs (not "passed")',
        'expected_skip': False,
        'row_values': [
            'https://example.com',
            '', '', '', '',
            'https://pagespeed.web.dev/?url=https://example.com&mobile',
            'https://pagespeed.web.dev/?url=https://example.com&desktop'
        ],
        'row_data': [{
            'values': [
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_cell_with_text('https://pagespeed.web.dev/?url=https://example.com&mobile'),
                create_cell_with_text('https://pagespeed.web.dev/?url=https://example.com&desktop')
            ]
        }]
    }


def generate_scenario_8_both_empty() -> Dict[str, Any]:
    """
    Scenario 8: Both F and G empty
    Expected: DO NOT SKIP (both need processing)
    """
    return {
        'description': 'Both F and G empty',
        'expected_skip': False,
        'row_values': ['https://example.com', '', '', '', '', '', ''],
        'row_data': [{
            'values': [
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell(),
                create_empty_cell()
            ]
        }]
    }


def generate_all_scenarios() -> List[Dict[str, Any]]:
    """Generate all test scenarios."""
    return [
        generate_scenario_1_both_passed_text(),
        generate_scenario_2_both_green_bg(),
        generate_scenario_3_mixed_complete(),
        generate_scenario_4_only_f_passed(),
        generate_scenario_5_only_g_passed(),
        generate_scenario_6_only_f_green(),
        generate_scenario_7_psi_urls(),
        generate_scenario_8_both_empty(),
    ]


def print_scenario(scenario: Dict[str, Any], index: int):
    """Print a scenario in a readable format."""
    print(f"\n{'='*80}")
    print(f"Scenario {index + 1}: {scenario['description']}")
    print(f"{'='*80}")
    print(f"Expected Skip: {scenario['expected_skip']}")
    print(f"\nRow Values (A-G):")
    print(f"  {scenario['row_values']}")
    print(f"\nColumn F (Mobile):")
    if len(scenario['row_values']) > 5 and scenario['row_values'][5]:
        print(f"  Text: {scenario['row_values'][5]}")
    else:
        print(f"  Text: (empty)")
    
    if scenario['row_data'] and len(scenario['row_data'][0]['values']) > 5:
        f_cell = scenario['row_data'][0]['values'][5]
        if 'effectiveFormat' in f_cell and 'backgroundColor' in f_cell['effectiveFormat']:
            bg = f_cell['effectiveFormat']['backgroundColor']
            print(f"  Background: rgb({int(bg['red']*255)}, {int(bg['green']*255)}, {int(bg['blue']*255)})")
        else:
            print(f"  Background: (none)")
    
    print(f"\nColumn G (Desktop):")
    if len(scenario['row_values']) > 6 and scenario['row_values'][6]:
        print(f"  Text: {scenario['row_values'][6]}")
    else:
        print(f"  Text: (empty)")
    
    if scenario['row_data'] and len(scenario['row_data'][0]['values']) > 6:
        g_cell = scenario['row_data'][0]['values'][6]
        if 'effectiveFormat' in g_cell and 'backgroundColor' in g_cell['effectiveFormat']:
            bg = g_cell['effectiveFormat']['backgroundColor']
            print(f"  Background: rgb({int(bg['red']*255)}, {int(bg['green']*255)}, {int(bg['blue']*255)})")
        else:
            print(f"  Background: (none)")


def export_scenarios_json(scenarios: List[Dict[str, Any]], filename: str = 'test_scenarios.json'):
    """Export scenarios to JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(scenarios, f, indent=2, default=str)
    print(f"\nExported {len(scenarios)} scenarios to {filename}")


def main():
    """Generate and display test scenarios."""
    print("="*80)
    print("Test Spreadsheet Scenarios for Skip Logic Validation")
    print("="*80)
    
    scenarios = generate_all_scenarios()
    
    for i, scenario in enumerate(scenarios):
        print_scenario(scenario, i)
    
    print(f"\n{'='*80}")
    print(f"Total Scenarios: {len(scenarios)}")
    print(f"{'='*80}")
    
    export_choice = input("\nExport scenarios to JSON? (y/n): ").strip().lower()
    if export_choice == 'y':
        export_scenarios_json(scenarios)
    
    print("\nScenario Summary:")
    print(f"  Should SKIP: {sum(1 for s in scenarios if s['expected_skip'])}")
    print(f"  Should NOT SKIP: {sum(1 for s in scenarios if not s['expected_skip'])}")


if __name__ == '__main__':
    main()
