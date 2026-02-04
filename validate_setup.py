#!/usr/bin/env python3
"""
Setup validation script for PageSpeed Insights Audit Tool.
Checks all prerequisites: Python version, Playwright, service account, and Google Sheets API.
"""
import sys
import os
import subprocess
import json
import importlib.util
from typing import Tuple


def print_status(check_name: str, passed: bool, message: str = ""):
    """Print check result with pass/fail indicator"""
    status = "[PASS]" if passed else "[FAIL]"
    status_color = "\033[92m" if passed else "\033[91m"
    reset_color = "\033[0m"
    
    full_message = f"{check_name}: {message}" if message else check_name
    print(f"{status_color}{status:8}{reset_color} | {full_message}")


def check_python_version() -> Tuple[bool, str]:
    """Check Python version >= 3.7"""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    if version.major >= 3 and version.minor >= 7:
        return True, f"Python {version_str}"
    return False, f"Python {version_str} (requires >= 3.7)"


def check_playwright_installed() -> Tuple[bool, str]:
    """Check if Playwright Python package is installed"""
    spec = importlib.util.find_spec('playwright')
    if spec is not None:
        try:
            import playwright
            version = getattr(playwright, '__version__', 'unknown')
            return True, f"Playwright {version} installed"
        except Exception as e:
            return False, f"Playwright import failed: {e}"
    return False, "Playwright not installed (run: pip install playwright)"


def check_chromium_browser() -> Tuple[bool, str]:
    """Check if Chromium browser is installed for Playwright"""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'playwright', 'install', '--dry-run', 'chromium'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=10
        )
        
        # Check if already installed
        if 'is already installed' in result.stdout or 'is already installed' in result.stderr:
            return True, "Chromium browser installed"
        else:
            return False, "Chromium browser missing (run: playwright install chromium)"
    except subprocess.TimeoutExpired:
        return False, "Browser check timed out"
    except FileNotFoundError:
        return False, "Playwright CLI not found"
    except Exception as e:
        return False, f"Error checking browser: {e}"


def check_service_account_exists() -> Tuple[bool, str]:
    """Check if service-account.json exists"""
    if os.path.exists('service-account.json'):
        return True, "service-account.json found"
    return False, "service-account.json not found"


def check_service_account_valid_json() -> Tuple[bool, str]:
    """Check if service-account.json is valid JSON with required fields"""
    if not os.path.exists('service-account.json'):
        return False, "service-account.json not found"
    
    try:
        with open('service-account.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check required fields
        required_fields = [
            'type', 'project_id', 'private_key_id', 'private_key',
            'client_email', 'client_id', 'auth_uri', 'token_uri'
        ]
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return False, f"Missing fields: {', '.join(missing_fields)}"
        
        # Validate type
        if data.get('type') != 'service_account':
            return False, f"Invalid type: '{data.get('type')}' (expected 'service_account')"
        
        # Validate private key format
        private_key = data.get('private_key', '')
        if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
            return False, "Invalid private key format"
        if not private_key.rstrip().endswith('-----END PRIVATE KEY-----'):
            return False, "Invalid private key format"
        
        # Validate email format
        email = data.get('client_email', '')
        if '@' not in email or not email.endswith('.iam.gserviceaccount.com'):
            return False, f"Invalid service account email: {email}"
        
        return True, f"Valid JSON with email: {email}"
        
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except Exception as e:
        return False, f"Error reading file: {e}"


def check_google_sheets_api() -> Tuple[bool, str]:
    """Test Google Sheets API connection"""
    if not os.path.exists('service-account.json'):
        return False, "service-account.json not found"
    
    # Add tools to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))
    
    try:
        from sheets import sheets_client
        
        # Test authentication
        try:
            service = sheets_client.authenticate('service-account.json')
        except Exception as e:
            return False, f"Authentication failed: {e}"
        
        # Test spreadsheet access with default spreadsheet
        default_spreadsheet_id = '1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I'
        
        try:
            tabs = sheets_client.list_tabs(default_spreadsheet_id, service=service)
            return True, f"Connected successfully ({len(tabs)} tabs accessible)"
        except PermissionError:
            return False, "Access denied - share spreadsheet with service account"
        except Exception as e:
            return False, f"Spreadsheet access failed: {e}"
            
    except ImportError as e:
        return False, f"Cannot import sheets_client: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def main():
    """Run all validation checks and report results"""
    print("=" * 80)
    print("PAGESPEED INSIGHTS AUDIT TOOL - SETUP VALIDATION")
    print("=" * 80)
    print()
    
    # Run all checks
    checks = [
        ("Python Version", check_python_version),
        ("Playwright Package", check_playwright_installed),
        ("Chromium Browser", check_chromium_browser),
        ("Service Account File", check_service_account_exists),
        ("Service Account Valid", check_service_account_valid_json),
        ("Google Sheets API", check_google_sheets_api),
    ]
    
    results = {}
    for check_name, check_func in checks:
        try:
            passed, message = check_func()
            results[check_name] = passed
            print_status(check_name, passed, message)
        except Exception as e:
            results[check_name] = False
            print_status(check_name, False, f"Check error: {e}")
    
    # Print summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    all_passed = all(results.values())
    passed_count = sum(results.values())
    total_count = len(results)
    
    print(f"Checks passed: {passed_count}/{total_count}")
    print()
    
    if all_passed:
        print("\033[92m[PASS]\033[0m All checks passed! Setup is complete.")
        print()
        print("Next steps:")
        print("  1. List available tabs:")
        print("     python list_tabs.py")
        print()
        print("  2. Run an audit:")
        print('     python run_audit.py --tab "TAB_NAME"')
    else:
        print("\033[91m[FAIL]\033[0m Some checks failed. Please fix the issues above.")
        print()
        print("Common fixes:")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Install browsers: playwright install chromium")
        print("  - Download service-account.json from Google Cloud Console")
        print("  - Share spreadsheet with service account email")
    
    print("=" * 80)
    
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
