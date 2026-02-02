from google.oauth2 import service_account
from googleapiclient.discovery import build
from typing import List, Tuple, Optional


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def authenticate(service_account_file: str):
    """
    Authenticate using a service account JSON file.
    
    Args:
        service_account_file: Path to the service account JSON credentials file
        
    Returns:
        Authorized Google Sheets service object
    """
    credentials = service_account.Credentials.from_service_account_file(
        service_account_file, scopes=SCOPES
    )
    service = build('sheets', 'v4', credentials=credentials)
    return service


def read_urls(spreadsheet_id: str, tab_name: str, service=None, service_account_file: Optional[str] = None) -> List[Tuple[int, str]]:
    """
    Read URLs from column A of a spreadsheet tab.
    
    Args:
        spreadsheet_id: The ID of the Google Spreadsheet
        tab_name: The name of the tab/sheet to read from
        service: Optional authenticated service object. If not provided, service_account_file must be provided
        service_account_file: Optional path to service account JSON file. Used if service is not provided
        
    Returns:
        List of tuples containing (row_index, url) where row_index is 1-based
    """
    if service is None:
        if service_account_file is None:
            raise ValueError("Either service or service_account_file must be provided")
        service = authenticate(service_account_file)
    
    sheet = service.spreadsheets()
    range_name = f"{tab_name}!A:A"
    
    result = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()
    
    values = result.get('values', [])
    
    urls = []
    for idx, row in enumerate(values, start=1):
        if row and row[0]:
            urls.append((idx, row[0]))
    
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
