from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Tuple, Optional
import time

from tools.utils.exceptions import PermanentError
from tools.security.service_account_validator import ServiceAccountValidator


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def authenticate(service_account_file: str):
    """
    Authenticate using a service account JSON file.
    
    Args:
        service_account_file: Path to the service account JSON credentials file
        
    Returns:
        Authorized Google Sheets service object
        
    Raises:
        PermanentError: If service account file doesn't exist or is invalid
    """
    import os
    
    if not os.path.exists(service_account_file):
        raise PermanentError(
            f"Service account file not found: {service_account_file}\n"
            f"Please download your service account JSON file from Google Cloud Console "
            f"and save it as '{service_account_file}'"
        )
    
    valid, errors = ServiceAccountValidator.validate(service_account_file)
    if not valid:
        error_msg = "Service account validation failed:\n" + "\n".join(f"  - {err}" for err in errors)
        raise PermanentError(error_msg)
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=credentials)
        return service
    except Exception as e:
        raise PermanentError(f"Invalid service account file: {e}", original_exception=e)


def list_tabs(spreadsheet_id: str, service) -> List[str]:
    """
    List all available tabs in a spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the Google Spreadsheet
        service: Authenticated service object from authenticate()
        
    Returns:
        List of tab names
        
    Raises:
        PermanentError: If spreadsheet not found or permission denied
    """
    try:
        sheet = service.spreadsheets()
        spreadsheet = sheet.get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        return [s['properties']['title'] for s in sheets]
    except HttpError as e:
        if e.resp.status == 404:
            raise PermanentError(
                f"Spreadsheet not found (ID: {spreadsheet_id}).\n"
                f"Please verify the spreadsheet ID is correct and the spreadsheet exists.",
                original_exception=e
            )
        elif e.resp.status == 403:
            raise PermanentError(
                f"Access denied to spreadsheet (ID: {spreadsheet_id}).\n"
                f"Please share the spreadsheet with your service account email.",
                original_exception=e
            )
        raise


def read_urls(
    spreadsheet_id: str, 
    tab_name: str, 
    service, 
    start_row: int = 2
) -> List[Tuple[int, str, Optional[str], Optional[str]]]:
    """
    Read URLs from column A of a spreadsheet tab.
    Also reads existing values from columns F and G.
    
    Args:
        spreadsheet_id: The ID of the Google Spreadsheet
        tab_name: The name of the tab/sheet to read from
        service: Authenticated service object from authenticate()
        start_row: Starting row number (1-based, default: 2 to skip header)
        
    Returns:
        List of tuples containing (row_index, url, existing_f, existing_g) where:
        - row_index is 1-based
        - existing_f is the current value in column F (or None if empty)
        - existing_g is the current value in column G (or None if empty)
        
    Raises:
        PermanentError: If tab doesn't exist or permission denied
    """
    if start_row < 1:
        raise ValueError(f"start_row must be >= 1, got {start_row}")
    
    sheet = service.spreadsheets()
    range_name = f"{tab_name}!A{start_row}:G"
    
    try:
        result = sheet.values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
    except HttpError as e:
        if e.resp.status == 404:
            raise PermanentError(f"Tab '{tab_name}' not found in spreadsheet", original_exception=e)
        elif e.resp.status == 403:
            raise PermanentError(
                f"Access denied to spreadsheet (ID: {spreadsheet_id}).\n"
                f"Please share the spreadsheet with your service account email.",
                original_exception=e
            )
        raise
    
    values = result.get('values', [])
    urls = []
    
    for idx, row in enumerate(values, start=start_row):
        if row and row[0]:
            url = row[0].strip()
            if url:
                existing_f = row[5].strip() if len(row) > 5 and row[5] else None
                existing_g = row[6].strip() if len(row) > 6 and row[6] else None
                urls.append((idx, url, existing_f, existing_g))
    
    return urls


def write_result(
    spreadsheet_id: str,
    tab_name: str,
    row_index: int,
    column: str,
    value: str,
    service
) -> None:
    """
    Write a value to a specific cell in the spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the Google Spreadsheet
        tab_name: The name of the tab/sheet to write to
        row_index: The row number (1-based) to write to
        column: The column letter (e.g., 'F' or 'G')
        value: The value to write
        service: Authenticated service object from authenticate()
        
    Raises:
        PermanentError: If there's a permission or resource error
    """
    sheet = service.spreadsheets()
    range_name = f"{tab_name}!{column}{row_index}"
    
    body = {'values': [[value]]}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            sheet.values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            return
        except HttpError as e:
            if e.resp.status == 403:
                raise PermanentError(
                    "Permission denied. Check service account permissions.",
                    original_exception=e
                )
            elif e.resp.status == 404:
                raise PermanentError("Resource not found.", original_exception=e)
            elif e.resp.status == 429 or e.resp.status >= 500:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            raise


def batch_write_results(
    spreadsheet_id: str,
    tab_name: str,
    updates: List[Tuple[int, str, str]],
    service
) -> None:
    """
    Write multiple cell values to the spreadsheet in a single batch request.
    
    Args:
        spreadsheet_id: The ID of the Google Spreadsheet
        tab_name: The name of the tab/sheet to write to
        updates: List of tuples (row_index, column, value) where:
                 - row_index is 1-based
                 - column is a column letter (e.g., 'F' or 'G')
                 - value is the value to write
        service: Authenticated service object from authenticate()
        
    Raises:
        PermanentError: If there's a permission or resource error
    """
    if not updates:
        return
    
    sheet = service.spreadsheets()
    
    # Build the data array for batchUpdate
    data = []
    for row_index, column, value in updates:
        range_name = f"{tab_name}!{column}{row_index}"
        data.append({
            'range': range_name,
            'values': [[value]]
        })
    
    body = {
        'valueInputOption': 'RAW',
        'data': data
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            sheet.values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()
            return
        except HttpError as e:
            if e.resp.status == 403:
                raise PermanentError(
                    "Permission denied. Check service account permissions.",
                    original_exception=e
                )
            elif e.resp.status == 404:
                raise PermanentError("Resource not found.", original_exception=e)
            elif e.resp.status == 429 or e.resp.status >= 500:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            raise
