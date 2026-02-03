import sys
import subprocess
import importlib.util
from typing import Dict, List, Tuple


def check_python_version() -> Tuple[bool, str]:
    version = sys.version_info
    if version.major >= 3 and version.minor >= 7:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return False, f"Python {version.major}.{version.minor}.{version.micro} (requires >= 3.7)"


def check_module_installed(module_name: str, import_name: str = None) -> Tuple[bool, str]:
    if import_name is None:
        import_name = module_name
    
    spec = importlib.util.find_spec(import_name)
    if spec is not None:
        try:
            module = importlib.import_module(import_name)
            version = getattr(module, '__version__', 'unknown version')
            return True, f"{module_name} {version}"
        except Exception as e:
            return False, f"{module_name} found but import failed: {e}"
    return False, f"{module_name} not installed"


def check_playwright_browsers() -> Tuple[bool, str]:
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'playwright', '--version'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=10
        )
        
        if result.returncode == 0:
            version_info = result.stdout.strip()
            
            result_browsers = subprocess.run(
                [sys.executable, '-m', 'playwright', 'install', '--dry-run', 'chromium'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10
            )
            
            if 'is already installed' in result_browsers.stdout or 'is already installed' in result_browsers.stderr:
                return True, f"Playwright {version_info}, Chromium browser installed"
            else:
                return False, f"Playwright {version_info} installed, but Chromium browser missing. Run: playwright install chromium"
        else:
            return False, f"Playwright CLI not available: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Playwright check timed out"
    except FileNotFoundError:
        return False, "Playwright CLI not found"
    except Exception as e:
        return False, f"Error checking Playwright: {e}"


def check_playwright_import() -> Tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
        return True, "Playwright Python API imports successfully"
    except ImportError as e:
        return False, f"Playwright Python API import failed: {e}"


def validate_playwright_setup() -> Dict[str, Tuple[bool, str]]:
    checks = {
        'Python Version': check_python_version(),
        'Playwright Package': check_module_installed('playwright'),
        'Playwright Import': check_playwright_import(),
        'Playwright Browsers': check_playwright_browsers(),
        'psutil Package': check_module_installed('psutil'),
        'pytest Package': check_module_installed('pytest'),
        'pytest-mock Package': check_module_installed('pytest-mock', 'pytest_mock'),
    }
    
    return checks


def print_validation_results(results: Dict[str, Tuple[bool, str]]):
    print("\n" + "=" * 80)
    print("PLAYWRIGHT SETUP VALIDATION")
    print("=" * 80 + "\n")
    
    all_passed = True
    
    for check_name, (passed, message) in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status:10} | {check_name:25} | {message}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 80)
    
    if all_passed:
        print("[PASS] All checks passed! Playwright setup is complete.")
    else:
        print("[FAIL] Some checks failed. Please review the failures above.")
        print("\nTo fix missing dependencies:")
        print("  pip install -r requirements.txt")
        print("  playwright install chromium")
    
    print("=" * 80 + "\n")
    
    return all_passed


def main():
    results = validate_playwright_setup()
    all_passed = print_validation_results(results)
    
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
