#!/usr/bin/env python3
"""
Extract service account email from service-account.json
"""
import json
import sys
import os

def main():
    service_account_file = 'service-account.json'
    
    if not os.path.exists(service_account_file):
        print(f"ERROR: {service_account_file} not found")
        print("\nPlease download your service account key from Google Cloud Console:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Navigate to IAM & Admin > Service Accounts")
        print("3. Click on your service account")
        print("4. Go to Keys tab > Add Key > Create new key > JSON")
        print(f"5. Save as {service_account_file} in this directory")
        sys.exit(1)
    
    try:
        with open(service_account_file, 'r') as f:
            data = json.load(f)
        
        email = data.get('client_email')
        
        if email:
            print("=" * 60)
            print("SERVICE ACCOUNT EMAIL")
            print("=" * 60)
            print(f"\n{email}\n")
            print("=" * 60)
            print("\nNext Steps:")
            print("1. Copy the email address above")
            print("2. Open your Google Spreadsheet")
            print("3. Click Share button")
            print("4. Paste this email")
            print("5. Set permission to 'Editor'")
            print("6. Uncheck 'Notify people'")
            print("7. Click Share")
            print("=" * 60)
        else:
            print("ERROR: 'client_email' field not found in service account file")
            sys.exit(1)
            
    except json.JSONDecodeError:
        print(f"ERROR: {service_account_file} is not valid JSON")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to read service account file: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
