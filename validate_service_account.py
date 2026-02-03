#!/usr/bin/env python3
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from security.service_account_validator import ServiceAccountValidator


def main():
    parser = argparse.ArgumentParser(
        description='Validate a Google Cloud service account JSON file'
    )
    parser.add_argument(
        'service_account_file',
        help='Path to the service account JSON file'
    )
    
    args = parser.parse_args()
    
    print(f"Validating service account file: {args.service_account_file}")
    print()
    
    valid, errors = ServiceAccountValidator.validate(args.service_account_file)
    
    if valid:
        print("✓ Service account validation PASSED")
        print()
        print("The service account file is valid and ready to use.")
        return 0
    else:
        print("✗ Service account validation FAILED")
        print()
        print("Errors found:")
        for error in errors:
            print(f"  - {error}")
        print()
        print("Please fix these errors before using the service account.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
