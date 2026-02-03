#!/usr/bin/env python3
"""
Generate API documentation using pdoc.

This script generates HTML API documentation from Python docstrings
for all modules in the tools/ directory.

Usage:
    python generate_api_docs.py

Output:
    Creates api_docs/ directory with HTML documentation
"""

import sys
import os
import subprocess
from pathlib import Path


def check_pdoc_installed() -> bool:
    """
    Check if pdoc is installed.
    
    Returns:
        bool: True if pdoc is available, False otherwise
    """
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pdoc', '--version'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def install_pdoc():
    """Install pdoc if not already installed."""
    print("Installing pdoc...")
    try:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'pdoc'],
            check=True
        )
        print("✓ pdoc installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install pdoc: {e}")
        sys.exit(1)


def generate_docs():
    """Generate API documentation using pdoc."""
    # Check if pdoc is installed
    if not check_pdoc_installed():
        print("pdoc is not installed.")
        response = input("Install pdoc now? (y/n): ").lower()
        if response == 'y':
            install_pdoc()
        else:
            print("Cannot generate documentation without pdoc.")
            sys.exit(1)
    
    # Create output directory
    output_dir = Path('api_docs')
    output_dir.mkdir(exist_ok=True)
    
    # Modules to document
    modules = [
        'tools.sheets.sheets_client',
        'tools.sheets.schema_validator',
        'tools.sheets.data_quality_checker',
        'tools.qa.cypress_runner',
        'tools.cache.cache_manager',
        'tools.metrics.metrics_collector',
        'tools.utils.logger',
        'tools.utils.url_validator',
        'tools.utils.exceptions',
        'tools.utils.error_metrics',
        'tools.utils.circuit_breaker',
        'tools.utils.retry',
        'tools.security.service_account_validator',
        'tools.security.rate_limiter',
        'tools.security.url_filter',
        'tools.security.audit_trail',
        'run_audit',
        'generate_report',
    ]
    
    print("Generating API documentation...")
    print(f"Output directory: {output_dir.absolute()}")
    print()
    
    # Generate documentation
    try:
        cmd = [
            sys.executable, '-m', 'pdoc',
            '--html',
            '--output-dir', str(output_dir),
            '--force'
        ] + modules
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode == 0:
            print("✓ API documentation generated successfully!")
            print()
            print(f"View documentation:")
            print(f"  Open: {output_dir.absolute()}/index.html")
            print()
            print("Generated modules:")
            for module in modules:
                module_file = module.replace('.', '/') + '.html'
                print(f"  - {module}")
        else:
            print("✗ Documentation generation failed:")
            print(result.stderr)
            sys.exit(1)
    
    except Exception as e:
        print(f"✗ Error generating documentation: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    print("=" * 70)
    print("API Documentation Generator")
    print("=" * 70)
    print()
    
    generate_docs()
    
    print()
    print("=" * 70)
    print("Documentation generation complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
