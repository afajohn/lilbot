#!/usr/bin/env python3
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from sheets import sheets_client


DEFAULT_SPREADSHEET_ID = '1vF4ySHs3nZVD6hkb8CWH7evRAy2V93DhS3wQ9rO3MhU'
SERVICE_ACCOUNT_FILE = 'service-account.json'


def main():
    parser = argparse.ArgumentParser(
        description='List all tabs in a Google Spreadsheet'
    )
    parser.add_argument(
        '--spreadsheet-id',
        default=DEFAULT_SPREADSHEET_ID,
        help=f'Google Spreadsheet ID (default: {DEFAULT_SPREADSHEET_ID})'
    )
    parser.add_argument(
        '--service-account',
        default=SERVICE_ACCOUNT_FILE,
        help=f'Path to service account JSON file (default: {SERVICE_ACCOUNT_FILE})'
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.service_account):
        print(f"ERROR: Service account file not found: {args.service_account}")
        print("\nSetup Instructions:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a service account and download the JSON key")
        print(f"3. Save it as '{args.service_account}' in the project root")
        print("4. Enable Google Sheets API in your project")
        print("5. Share your spreadsheet with the service account email")
        sys.exit(1)
    
    print(f"Authenticating with Google Sheets...")
    try:
        service = sheets_client.authenticate(args.service_account)
        print("Authentication successful\n")
    except Exception as e:
        print(f"Failed to authenticate: {e}")
        sys.exit(1)
    
    print(f"Fetching tabs from spreadsheet (ID: {args.spreadsheet_id})...")
    try:
        tabs = sheets_client.list_tabs(args.spreadsheet_id, service=service)
        
        if not tabs:
            print("No tabs found in the spreadsheet.")
        else:
            print(f"\nFound {len(tabs)} tab(s):\n")
            for i, tab in enumerate(tabs, 1):
                print(f"  {i}. {tab}")
            
            print(f"\nTo run audit on a tab, use:")
            print(f'  python run_audit.py --tab "TAB_NAME"')
            
    except ValueError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
    except PermissionError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to fetch tabs: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
