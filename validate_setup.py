#!/usr/bin/env python3
"""
Setup validation script for PageSpeed Insights Audit Tool
Checks all prerequisites and configurations before running audits
"""
import sys
import os
import subprocess
import json

def print_status(message, status):
    symbols = {"pass": "✓", "fail": "✗", "warn": "⚠"}
    colors = {"pass": "\033[92m", "fail": "\033[91m", "warn": "\033[93m"}
    reset = "\033[0m"
    
    symbol = symbols.get(status, "?")
    color = colors.get(status, "")
    print(f"{color}[{symbol}]{reset} {message}")

def check_python_dependencies():
    print("\n=== Checking Python Dependencies ===")
    required_packages = [
        'google-auth',
        'google-auth-oauthlib',
        'google-auth-httplib2',
        'google-api-python-client'
    ]
    
    all_installed = True
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print_status(f"{package} installed", "pass")
        except ImportError:
            print_status(f"{package} NOT installed", "fail")
            all_installed = False
    
    return all_installed

def check_nodejs():
    print("\n=== Checking Node.js and npm ===")
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode == 0:
            print_status(f"Node.js {result.stdout.strip()} installed", "pass")
            node_ok = True
        else:
            print_status("Node.js NOT found", "fail")
            node_ok = False
    except FileNotFoundError:
        print_status("Node.js NOT found", "fail")
        node_ok = False
    
    try:
        result = subprocess.run(['npm', '--version'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode == 0:
            print_status(f"npm {result.stdout.strip()} installed", "pass")
            npm_ok = True
        else:
            print_status("npm NOT found", "fail")
            npm_ok = False
    except FileNotFoundError:
        print_status("npm NOT found", "fail")
        npm_ok = False
    
    return node_ok and npm_ok

def check_cypress():
    print("\n=== Checking Cypress ===")
    
    if not os.path.exists('node_modules'):
        print_status("node_modules NOT found - run 'npm install'", "fail")
        return False
    
    cypress_path = os.path.join('node_modules', 'cypress')
    if os.path.exists(cypress_path):
        print_status("Cypress installed in node_modules", "pass")
    else:
        print_status("Cypress NOT installed - run 'npm install'", "fail")
        return False
    
    try:
        result = subprocess.run(['npx', 'cypress', 'version'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
        if result.returncode == 0:
            print_status("Cypress executable working", "pass")
            return True
        else:
            print_status("Cypress executable NOT working", "fail")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print_status("Cypress executable NOT working", "fail")
        return False

def check_service_account():
    print("\n=== Checking Service Account ===")
    
    if not os.path.exists('service-account.json'):
        print_status("service-account.json NOT found", "fail")
        print("  → Download from Google Cloud Console")
        print("  → IAM & Admin > Service Accounts > Keys > Create new key (JSON)")
        return False
    
    print_status("service-account.json exists", "pass")
    
    try:
        with open('service-account.json', 'r') as f:
            data = json.load(f)
        
        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        all_fields_present = True
        
        for field in required_fields:
            if field in data:
                if field == 'client_email':
                    print_status(f"Service account email: {data[field]}", "pass")
                else:
                    print_status(f"Field '{field}' present", "pass")
            else:
                print_status(f"Field '{field}' MISSING", "fail")
                all_fields_present = False
        
        return all_fields_present
        
    except json.JSONDecodeError:
        print_status("service-account.json is NOT valid JSON", "fail")
        return False
    except Exception as e:
        print_status(f"Error reading service-account.json: {e}", "fail")
        return False

def check_google_sheets_access():
    print("\n=== Checking Google Sheets Access ===")
    
    if not os.path.exists('service-account.json'):
        print_status("Cannot test - service-account.json missing", "warn")
        return False
    
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))
    
    try:
        from sheets import sheets_client
        
        try:
            service = sheets_client.authenticate('service-account.json')
            print_status("Authentication successful", "pass")
        except Exception as e:
            print_status(f"Authentication FAILED: {e}", "fail")
            return False
        
        default_spreadsheet_id = '1_7XyowAcqKRISdMp71DQUeKA_2O2g5T89tJvsVt685I'
        
        try:
            tabs = sheets_client.list_tabs(default_spreadsheet_id, service=service)
            print_status(f"Can access spreadsheet (found {len(tabs)} tabs)", "pass")
            
            if tabs:
                print("  Available tabs:")
                for tab in tabs[:5]:
                    print(f"    - {tab}")
                if len(tabs) > 5:
                    print(f"    ... and {len(tabs) - 5} more")
            
            return True
            
        except PermissionError:
            print_status("Access DENIED - spreadsheet not shared with service account", "fail")
            print("  → Open spreadsheet and share with service account email")
            return False
        except ValueError as e:
            print_status(f"Spreadsheet access error: {e}", "fail")
            return False
            
    except ImportError as e:
        print_status(f"Cannot import sheets_client: {e}", "fail")
        return False

def check_project_structure():
    print("\n=== Checking Project Structure ===")
    
    required_files = [
        'run_audit.py',
        'list_tabs.py',
        'requirements.txt',
        'tools/sheets/sheets_client.py',
        'tools/qa/playwright_runner.py',
        'tools/utils/logger.py'
    ]
    
    all_present = True
    for file in required_files:
        if os.path.exists(file):
            print_status(f"{file}", "pass")
        else:
            print_status(f"{file} MISSING", "fail")
            all_present = False
    
    return all_present

def main():
    print("=" * 60)
    print("PageSpeed Insights Audit Tool - Setup Validation")
    print("=" * 60)
    
    results = {
        "Project Structure": check_project_structure(),
        "Python Dependencies": check_python_dependencies(),
        "Node.js & npm": check_nodejs(),
        "Cypress": check_cypress(),
        "Service Account": check_service_account(),
        "Google Sheets Access": check_google_sheets_access()
    }
    
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    for check, passed in results.items():
        if passed:
            print_status(f"{check}: OK", "pass")
        else:
            print_status(f"{check}: FAILED", "fail")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print_status("All checks passed! You're ready to run audits.", "pass")
        print("\nNext steps:")
        print("  1. python list_tabs.py")
        print('  2. python run_audit.py --tab "TAB_NAME"')
    else:
        print_status("Some checks failed. Please fix the issues above.", "fail")
        print("\nFor help, see:")
        print("  - README.md for setup instructions")
        print("  - TROUBLESHOOTING.md for common issues")
    print("=" * 60)
    
    sys.exit(0 if all_passed else 1)

if __name__ == '__main__':
    main()
