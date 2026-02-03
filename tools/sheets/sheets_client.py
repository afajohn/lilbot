from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Tuple, Optional
import threading


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


_auth_lock = threading.Lock()
_service_cache = {}


def authenticate(service_account_file: str):
    """
    Authenticate using a service account JSON file with connection pooling.
    
    Args:
        service_account_file: Path to the service account JSON credentials file
        
    Returns:
        Authorized Google Sheets service object
        
    Raises:
        FileNotFoundError: If service account file doesn't exist
        ValueError: If service account file is invalid
    """
    import os
    
    with _auth_lock:
        if service_account_file in _service_cache:
            return _service_cache[service_account_file]
        
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
            _service_cache[service_account_file] = service
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


def read_urls(spreadsheet_id: str, tab_name: str, service=None, service_account_file: Optional[str] = None) -> List[Tuple[int, str, Optional[str], Optional[str], bool]]:
    """
    Read URLs from column A of a spreadsheet tab, starting from row 2 (skipping header).
    Also reads existing PSI URLs from columns F and G and checks for skip conditions.
    
    Args:
        spreadsheet_id: The ID of the Google Spreadsheet
        tab_name: The name of the tab/sheet to read from
        service: Optional authenticated service object. If not provided, service_account_file must be provided
        service_account_file: Optional path to service account JSON file. Used if service is not provided
        
    Returns:
        List of tuples containing (row_index, url, mobile_psi_url, desktop_psi_url, should_skip) where:
        - row_index is 1-based
        - should_skip is True if either F or G cell contains "passed" or has background color #b7e1cd
        
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
        
        spreadsheet_data = sheet.get(
            spreadsheetId=spreadsheet_id,
            ranges=[range_name],
            fields='sheets(data(rowData(values(effectiveFormat(backgroundColor),formattedValue))))'
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
    
    row_data = []
    sheets_data = spreadsheet_data.get('sheets', [])
    if sheets_data and 'data' in sheets_data[0]:
        sheet_data = sheets_data[0]['data'][0]
        row_data = sheet_data.get('rowData', [])
    
    urls = []
    for idx, row in enumerate(values, start=2):
        if row and row[0]:
            url = row[0].strip()
            if url:
                mobile_psi_url = row[5].strip() if len(row) > 5 and row[5] else None
                desktop_psi_url = row[6].strip() if len(row) > 6 and row[6] else None
                
                should_skip = _check_skip_conditions(row_data, idx - 2, row)
                
                urls.append((idx, url, mobile_psi_url, desktop_psi_url, should_skip))
    
    return urls


def _check_skip_conditions(row_data: List, row_idx: int, row_values: List) -> bool:
    """
    Check if a row should be skipped based on:
    1. Cells F or G containing the word "passed"
    2. Cells F or G having background color #b7e1cd
    
    Args:
        row_data: Formatted row data from the spreadsheet
        row_idx: Index in the row_data list (0-based)
        row_values: Raw values from the row
        
    Returns:
        True if the row should be skipped, False otherwise
    """
    mobile_value = row_values[5] if len(row_values) > 5 else None
    desktop_value = row_values[6] if len(row_values) > 6 else None
    
    if mobile_value and 'passed' in str(mobile_value).lower():
        return True
    if desktop_value and 'passed' in str(desktop_value).lower():
        return True
    
    if row_idx < len(row_data):
        row_cells = row_data[row_idx].get('values', [])
        
        if len(row_cells) > 5:
            mobile_cell = row_cells[5]
            if _has_target_background_color(mobile_cell):
                return True
        
        if len(row_cells) > 6:
            desktop_cell = row_cells[6]
            if _has_target_background_color(desktop_cell):
                return True
    
    return False


def _has_target_background_color(cell: dict) -> bool:
    """
    Check if a cell has the target background color #b7e1cd.
    
    Args:
        cell: Cell data with formatting information
        
    Returns:
        True if the cell has background color #b7e1cd, False otherwise
    """
    if 'effectiveFormat' in cell and 'backgroundColor' in cell['effectiveFormat']:
        bg_color = cell['effectiveFormat']['backgroundColor']
        
        red = bg_color.get('red', 0)
        green = bg_color.get('green', 0)
        blue = bg_color.get('blue', 0)
        
        red_int = int(red * 255)
        green_int = int(green * 255)
        blue_int = int(blue * 255)
        
        if red_int == 0xb7 and green_int == 0xe1 and blue_int == 0xcd:
            return True
    
    return False


_write_lock = threading.Lock()


def write_psi_url(spreadsheet_id: str, tab_name: str, row_index: int, column: str, url: str, service=None, service_account_file: Optional[str] = None) -> None:
    """
    Write a PSI URL to a specific cell in the spreadsheet (thread-safe).
    
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
    
    with _write_lock:
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
    Batch write PSI URLs to multiple cells in the spreadsheet (thread-safe).
    
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
    
    with _write_lock:
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
