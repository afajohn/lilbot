from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Tuple, Optional


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def authenticate(service_account_file: str):
    """
    Authenticate using a service account JSON file.
    
    Args:
        service_account_file: Path to the service account JSON credentials file
        
    Returns:
        Authorized Google Sheets service object
        
    Raises:
        FileNotFoundError: If service account file doesn't exist
        ValueError: If service account file is invalid
    """
    import os
    if not os.path.exists(service_account_file):
        raise FileNotFoundError(
            f"Service account file not found: {service_account_file}\n"
            f"Please download your service account JSON file from Google Cloud Console "
            f"and save it as '{service_account_file}'"
        )
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=credentials)
        return service
    except Exception as e:
        raise ValueError(f"Invalid service account file: {e}")


def list_tabs(spreadsheet_id: str, service=None, service_account_file: Optional[str] = None) -> List[str]:
    """
    List all available tabs in a spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the Google Spreadsheet
        service: Optional authenticated service object
        service_account_file: Optional path to service account JSON file
        
    Returns:
        List of tab names
    """
    if service is None:
        if service_account_file is None:
            raise ValueError("Either service or service_account_file must be provided")
        service = authenticate(service_account_file)
    
    try:
        sheet = service.spreadsheets()
        spreadsheet = sheet.get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        return [s['properties']['title'] for s in sheets]
    except HttpError as e:
        if e.resp.status == 404:
            raise ValueError(
                f"Spreadsheet not found (ID: {spreadsheet_id}).\n"
                f"Please verify:\n"
                f"  1. The spreadsheet ID is correct\n"
                f"  2. The spreadsheet exists\n"
                f"  3. Your service account has access to this spreadsheet"
            )
        elif e.resp.status == 403:
            raise PermissionError(
                f"Access denied to spreadsheet (ID: {spreadsheet_id}).\n"
                f"Please share the spreadsheet with your service account email."
            )
        raise


def read_urls(spreadsheet_id: str, tab_name: str, service=None, service_account_file: Optional[str] = None) -> List[Tuple[int, str, Optional[str], Optional[str]]]:
    """
    Read URLs from column A of a spreadsheet tab, starting from row 2 (skipping header).
    Also reads existing PSI URLs from columns F and G.
    
    Args:
        spreadsheet_id: The ID of the Google Spreadsheet
        tab_name: The name of the tab/sheet to read from
        service: Optional authenticated service object. If not provided, service_account_file must be provided
        service_account_file: Optional path to service account JSON file. Used if service is not provided
        
    Returns:
        List of tuples containing (row_index, url, mobile_psi_url, desktop_psi_url) where row_index is 1-based
        
    Raises:
        ValueError: If tab doesn't exist or spreadsheet is not accessible
        PermissionError: If service account doesn't have access
    """
    if service is None:
        if service_account_file is None:
            raise ValueError("Either service or service_account_file must be provided")
        service = authenticate(service_account_file)
    
    sheet = service.spreadsheets()
    range_name = f"{tab_name}!A2:G"
    
    try:
        result = sheet.values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
    except HttpError as e:
        if e.resp.status == 404:
            available_tabs = list_tabs(spreadsheet_id, service=service)
            error_msg = f"Tab '{tab_name}' not found in spreadsheet.\n"
            if available_tabs:
                error_msg += f"Available tabs: {', '.join(available_tabs)}"
            else:
                error_msg += "No tabs found in spreadsheet."
            raise ValueError(error_msg)
        elif e.resp.status == 403:
            raise PermissionError(
                f"Access denied to spreadsheet (ID: {spreadsheet_id}).\n"
                f"Please share the spreadsheet with your service account email."
            )
        raise
    
    values = result.get('values', [])
    
    urls = []
    for idx, row in enumerate(values, start=2):
        if row and row[0]:
            url = row[0].strip()
            if url:
                mobile_psi_url = row[5].strip() if len(row) > 5 and row[5] else None
                desktop_psi_url = row[6].strip() if len(row) > 6 and row[6] else None
                urls.append((idx, url, mobile_psi_url, desktop_psi_url))
    
    return urls


def write_psi_url(spreadsheet_id: str, tab_name: str, row_index: int, column: str, url: str, service=None, service_account_file: Optional[str] = None) -> None:
    """
    Write a PSI URL to a specific cell in the spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the Google Spreadsheet
        tab_name: The name of the tab/sheet to write to
        row_index: The row number (1-based) to write to
        column: The column letter ('F' for mobile, 'G' for desktop)
        url: The PSI URL to write
        service: Optional authenticated service object. If not provided, service_account_file must be provided
        service_account_file: Optional path to service account JSON file. Used if service is not provided
    """
    if service is None:
        if service_account_file is None:
            raise ValueError("Either service or service_account_file must be provided")
        service = authenticate(service_account_file)
    
    sheet = service.spreadsheets()
    range_name = f"{tab_name}!{column}{row_index}"
    
    body = {
        'values': [[url]]
    }
    
    sheet.values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()


def batch_write_psi_urls(spreadsheet_id: str, tab_name: str, updates: List[Tuple[int, str, str]], service=None, service_account_file: Optional[str] = None) -> None:
    """
    Batch write PSI URLs to multiple cells in the spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the Google Spreadsheet
        tab_name: The name of the tab/sheet to write to
        updates: List of tuples containing (row_index, column, url)
        service: Optional authenticated service object. If not provided, service_account_file must be provided
        service_account_file: Optional path to service account JSON file. Used if service is not provided
    """
    if not updates:
        return
    
    if service is None:
        if service_account_file is None:
            raise ValueError("Either service or service_account_file must be provided")
        service = authenticate(service_account_file)
    
    sheet = service.spreadsheets()
    
    data = []
    for row_index, column, url in updates:
        range_name = f"{tab_name}!{column}{row_index}"
        data.append({
            'range': range_name,
            'values': [[url]]
        })
    
    body = {
        'valueInputOption': 'RAW',
        'data': data
    }
    
    sheet.values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=body
    ).execute()
