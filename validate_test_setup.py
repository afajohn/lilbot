#!/usr/bin/env python3
import os
import sys
import subprocess

def check_file_exists(filepath, description):
    if os.path.exists(filepath):
        print(f"✓ {description}: {filepath}")
        return True
    else:
        print(f"✗ {description}: {filepath} (NOT FOUND)")
        return False

def check_directory_exists(dirpath, description):
    if os.path.isdir(dirpath):
        print(f"✓ {description}: {dirpath}")
        return True
    else:
        print(f"✗ {description}: {dirpath} (NOT FOUND)")
        return False

def check_module_installed(module_name):
    try:
        __import__(module_name)
        print(f"✓ Python module installed: {module_name}")
        return True
    except ImportError:
        print(f"✗ Python module NOT installed: {module_name}")
        return False

def check_npm_package():
    try:
        result = subprocess.run(
            ['npm', 'list', 'cypress'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if 'cypress@' in result.stdout:
            print(f"✓ NPM package installed: cypress")
            return True
        else:
            print(f"✗ NPM package NOT installed: cypress")
            return False
    except Exception as e:
        print(f"✗ Error checking NPM packages: {e}")
        return False

def main():
    print("=" * 70)
    print("Test Setup Validation")
    print("=" * 70)
    print()
    
    checks_passed = 0
    checks_total = 0
    
    print("1. Checking Test Directories...")
    print("-" * 70)
    checks_total += 1
    if check_directory_exists('tests', 'Test directory'):
        checks_passed += 1
    checks_total += 1
    if check_directory_exists('tests/unit', 'Unit tests directory'):
        checks_passed += 1
    checks_total += 1
    if check_directory_exists('tests/integration', 'Integration tests directory'):
        checks_passed += 1
    print()
    
    print("2. Checking Test Files...")
    print("-" * 70)
    test_files = [
        ('tests/conftest.py', 'Test fixtures'),
        ('tests/unit/test_sheets_client.py', 'Sheets client tests'),
        ('tests/unit/test_cypress_runner.py', 'Cypress runner tests'),
        ('tests/unit/test_logger.py', 'Logger tests'),
        ('tests/integration/test_run_audit.py', 'Run audit tests'),
        ('tests/integration/test_end_to_end.py', 'End-to-end tests'),
    ]
    for filepath, description in test_files:
        checks_total += 1
        if check_file_exists(filepath, description):
            checks_passed += 1
    print()
    
    print("3. Checking Configuration Files...")
    print("-" * 70)
    config_files = [
        ('pytest.ini', 'Pytest configuration'),
        ('.coveragerc', 'Coverage configuration'),
        ('.github/workflows/ci.yml', 'CI/CD workflow'),
    ]
    for filepath, description in config_files:
        checks_total += 1
        if check_file_exists(filepath, description):
            checks_passed += 1
    print()
    
    print("4. Checking Convenience Scripts...")
    print("-" * 70)
    script_files = [
        ('Makefile', 'Make commands'),
        ('run_tests.ps1', 'PowerShell test runner'),
        ('run_tests.sh', 'Bash test runner'),
    ]
    for filepath, description in script_files:
        checks_total += 1
        if check_file_exists(filepath, description):
            checks_passed += 1
    print()
    
    print("5. Checking Documentation...")
    print("-" * 70)
    doc_files = [
        ('tests/README.md', 'Test README'),
        ('TEST_GUIDE.md', 'Test guide'),
        ('TESTING_SUMMARY.md', 'Testing summary'),
        ('TEST_IMPLEMENTATION_CHECKLIST.md', 'Implementation checklist'),
    ]
    for filepath, description in doc_files:
        checks_total += 1
        if check_file_exists(filepath, description):
            checks_passed += 1
    print()
    
    print("6. Checking Python Dependencies...")
    print("-" * 70)
    modules = ['pytest', 'pytest_cov', 'pytest_mock', 'google', 'googleapiclient']
    for module in modules:
        checks_total += 1
        if check_module_installed(module):
            checks_passed += 1
    print()
    
    print("7. Checking Node.js Dependencies...")
    print("-" * 70)
    checks_total += 1
    if check_npm_package():
        checks_passed += 1
    print()
    
    print("8. Running Quick Test Check...")
    print("-" * 70)
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', '--collect-only', '-q'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print(f"✓ Pytest can collect tests successfully")
            print(f"  {result.stdout.strip()}")
            checks_passed += 1
        else:
            print(f"✗ Pytest test collection failed")
            print(f"  {result.stderr}")
    except Exception as e:
        print(f"✗ Error running pytest: {e}")
    checks_total += 1
    print()
    
    print("=" * 70)
    print(f"Validation Results: {checks_passed}/{checks_total} checks passed")
    print("=" * 70)
    print()
    
    if checks_passed == checks_total:
        print("✓ All checks passed! Test suite is properly set up.")
        print()
        print("Next steps:")
        print("  1. Run tests: pytest")
        print("  2. Run with coverage: pytest --cov=tools --cov=run_audit --cov-report=term-missing")
        print("  3. Check coverage threshold: coverage report --fail-under=70")
        print()
        print("Or use convenience scripts:")
        print("  Windows: .\\run_tests.ps1")
        print("  Unix/Linux/Mac: ./run_tests.sh or make test")
        return 0
    else:
        print(f"✗ {checks_total - checks_passed} checks failed.")
        print()
        print("Please ensure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        print("  npm install")
        print()
        print("If files are missing, they may need to be created or restored.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
