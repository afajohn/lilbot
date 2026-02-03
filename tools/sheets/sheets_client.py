from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Tuple, Optional
import threading
import time
import traceback

from tools.utils.exceptions import RetryableError, PermanentError
from tools.utils.retry import retry_with_backoff
from tools.utils.error_metrics import get_global_metrics
from tools.utils.logger import get_logger
from tools.security.service_account_validator import ServiceAccountValidator
from tools.security.rate_limiter import get_spreadsheet_rate_limiter
from tools.security.audit_trail import get_audit_trail


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


_auth_lock = threading.Lock()
_service_cache = {}


class RateLimiter:
    """Token bucket rate limiter for Google Sheets API calls."""
    
    def __init__(self, max_tokens: int = 90, refill_period: float = 100.0):
        """
        Initialize rate limiter with token bucket algorithm.
        
        Args:
            max_tokens: Maximum number of tokens (requests) allowed
            refill_period: Time period in seconds for refilling tokens
        """
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.refill_period = refill_period
        self.refill_rate = max_tokens / refill_period
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens, blocking if necessary until tokens are available.
        
        Args:
            tokens: Number of tokens to acquire
        """
        with self.lock:
            while True:
                now = time.time()
                elapsed = now - self.last_refill
                self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
                self.last_refill = now
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                
                wait_time = (tokens - self.tokens) / self.refill_rate
                time.sleep(min(wait_time, 1.0))


_rate_limiter = RateLimiter(max_tokens=90, refill_period=100.0)


def _execute_with_retry(func, max_retries: int = 3, initial_delay: float = 2.0):
    """
    Execute a function with exponential backoff retry logic.
    
    Args:
        func: Callable to execute
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds (doubles with each retry)
        
    Returns:
        Result of the function call
        
    Raises:
        Last exception if all retries fail
    """
    logger = get_logger()
    metrics = get_global_metrics()
    
    from tools.metrics.metrics_collector import get_metrics_collector
    metrics_collector = get_metrics_collector()
    
    delay = initial_delay
    last_exception = None
    was_retried = False
    func_name = getattr(func, '__name__', 'unknown_function')
    
    for attempt in range(max_retries + 1):
        try:
            _rate_limiter.acquire()
            metrics_collector.record_api_call_sheets()
            result = func()
            if was_retried:
                metrics.record_success(func_name, was_retried=True)
            return result
            
        except HttpError as e:
            last_exception = e
            was_retried = True
            
            if e.resp.status == 403:
                metrics.record_error(
                    error_type='PermissionError',
                    function_name=func_name,
                    error_message=f"Permission denied (HTTP 403)",
                    is_retryable=False,
                    attempt=attempt + 1,
                    traceback=traceback.format_exc()
                )
                raise PermanentError(
                    "Permission denied. Check service account permissions.",
                    original_exception=e
                )
            
            elif e.resp.status == 404:
                metrics.record_error(
                    error_type='NotFoundError',
                    function_name=func_name,
                    error_message=f"Resource not found (HTTP 404)",
                    is_retryable=False,
                    attempt=attempt + 1,
                    traceback=traceback.format_exc()
                )
                raise PermanentError(
                    "Resource not found.",
                    original_exception=e
                )
            
            elif e.resp.status == 429 or e.resp.status >= 500:
                metrics.record_error(
                    error_type='RetryableHttpError',
                    function_name=func_name,
                    error_message=f"HTTP {e.resp.status}: {str(e)}",
                    is_retryable=True,
                    attempt=attempt + 1,
                    traceback=traceback.format_exc()
                )
                
                if attempt < max_retries:
                    actual_delay = min(delay, 60.0)
                    logger.warning(
                        f"Retryable HTTP error (status {e.resp.status}) in {func_name} "
                        f"(attempt {attempt + 1}/{max_retries + 1}). Retrying in {actual_delay:.2f}s",
                        extra={
                            'function': func_name,
                            'attempt': attempt + 1,
                            'http_status': e.resp.status,
                            'retry_delay': actual_delay
                        }
                    )
                    time.sleep(actual_delay)
                    delay *= 2
                    continue
            else:
                metrics.record_error(
                    error_type='UnexpectedHttpError',
                    function_name=func_name,
                    error_message=f"HTTP {e.resp.status}: {str(e)}",
                    is_retryable=False,
                    attempt=attempt + 1,
                    traceback=traceback.format_exc()
                )
                raise
        
        except Exception as e:
            last_exception = e
            was_retried = True
            
            metrics.record_error(
                error_type=type(e).__name__,
                function_name=func_name,
                error_message=str(e),
                is_retryable=True,
                attempt=attempt + 1,
                traceback=traceback.format_exc()
            )
            
            if attempt < max_retries:
                logger.warning(
                    f"Error in {func_name} (attempt {attempt + 1}/{max_retries + 1}): {str(e)}. "
                    f"Retrying in {delay:.2f}s",
                    extra={
                        'function': func_name,
                        'attempt': attempt + 1,
                        'error_type': type(e).__name__,
                        'retry_delay': delay
                    }
                )
                time.sleep(delay)
                delay *= 2
                continue
    
    if last_exception:
        raise last_exception


def authenticate(service_account_file: str):
    """
    Authenticate using a service account JSON file with connection pooling.
    
    Args:
        service_account_file: Path to the service account JSON credentials file
        
    Returns:
        Authorized Google Sheets service object
        
    Raises:
        PermanentError: If service account file doesn't exist or is invalid
    """
    import os
    
    with _auth_lock:
        if service_account_file in _service_cache:
            return _service_cache[service_account_file]
        
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
            _service_cache[service_account_file] = service
            return service
        except Exception as e:
            raise PermanentError(f"Invalid service account file: {e}", original_exception=e)


def list_tabs(spreadsheet_id: str, service=None, service_account_file: Optional[str] = None) -> List[str]:
    """
    List all available tabs in a spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the Google Spreadsheet
        service: Optional authenticated service object
        service_account_file: Optional path to service account JSON file
        
    Returns:
        List of tab names
        
    Raises:
        PermanentError: If spreadsheet not found or permission denied
    """
    if service is None:
        if service_account_file is None:
            raise ValueError("Either service or service_account_file must be provided")
        service = authenticate(service_account_file)
    
    def _list():
        sheet = service.spreadsheets()
        spreadsheet = sheet.get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        return [s['properties']['title'] for s in sheets]
    
    try:
        return _execute_with_retry(_list)
    except PermanentError:
        raise
    except HttpError as e:
        if e.resp.status == 404:
            raise PermanentError(
                f"Spreadsheet not found (ID: {spreadsheet_id}).\n"
                f"Please verify:\n"
                f"  1. The spreadsheet ID is correct\n"
                f"  2. The spreadsheet exists\n"
                f"  3. Your service account has access to this spreadsheet",
                original_exception=e
            )
        elif e.resp.status == 403:
            raise PermanentError(
                f"Access denied to spreadsheet (ID: {spreadsheet_id}).\n"
                f"Please share the spreadsheet with your service account email.",
                original_exception=e
            )
        raise


def read_urls(spreadsheet_id: str, tab_name: str, service=None, service_account_file: Optional[str] = None) -> List[Tuple[int, str, Optional[str], Optional[str], bool]]:
    """
    Read URLs from column A of a spreadsheet tab, starting from row 2 (skipping header).
    Also reads existing PSI URLs from columns F and G and checks for skip conditions.
    Reads all data (A:G) in a single API call.
    
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
        PermanentError: If tab doesn't exist or permission denied
    """
    if service is None:
        if service_account_file is None:
            raise ValueError("Either service or service_account_file must be provided")
        service = authenticate(service_account_file)
    
    sheet = service.spreadsheets()
    range_name = f"{tab_name}!A2:G"
    
    def _read():
        result = sheet.values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        
        spreadsheet_data = sheet.get(
            spreadsheetId=spreadsheet_id,
            ranges=[range_name],
            fields='sheets(data(rowData(values(effectiveFormat(backgroundColor),formattedValue))))'
        ).execute()
        
        return result, spreadsheet_data
    
    try:
        result, spreadsheet_data = _execute_with_retry(_read)
    except PermanentError:
        raise
    except HttpError as e:
        if e.resp.status == 404:
            available_tabs = list_tabs(spreadsheet_id, service=service)
            error_msg = f"Tab '{tab_name}' not found in spreadsheet.\n"
            if available_tabs:
                error_msg += f"Available tabs: {', '.join(available_tabs)}"
            else:
                error_msg += "No tabs found in spreadsheet."
            raise PermanentError(error_msg, original_exception=e)
        elif e.resp.status == 403:
            raise PermanentError(
                f"Access denied to spreadsheet (ID: {spreadsheet_id}).\n"
                f"Please share the spreadsheet with your service account email.",
                original_exception=e
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
    1. BOTH cells F AND G containing the word "passed" or having background color #b7e1cd
    2. Partial fills (only F or only G) do NOT cause skip - allow processing of empty column
    
    Skip logic:
    - Skip if F has "passed" text AND G has "passed" text
    - Skip if F has #b7e1cd color AND G has #b7e1cd color
    - Skip if F has "passed" or #b7e1cd AND G has "passed" or #b7e1cd (any combination)
    - Do NOT skip if only F is filled (process G)
    - Do NOT skip if only G is filled (process F)
    
    Args:
        row_data: Formatted row data from the spreadsheet
        row_idx: Index in the row_data list (0-based)
        row_values: Raw values from the row
        
    Returns:
        True if the row should be skipped (both F and G are complete), False otherwise
    """
    logger = get_logger()
    
    mobile_value = row_values[5] if len(row_values) > 5 else None
    desktop_value = row_values[6] if len(row_values) > 6 else None
    
    mobile_has_passed_text = mobile_value and 'passed' in str(mobile_value).lower()
    desktop_has_passed_text = desktop_value and 'passed' in str(desktop_value).lower()
    
    mobile_has_green_bg = False
    desktop_has_green_bg = False
    
    if row_idx < len(row_data):
        row_cells = row_data[row_idx].get('values', [])
        
        if len(row_cells) > 5:
            mobile_cell = row_cells[5]
            mobile_has_green_bg = _has_target_background_color(mobile_cell)
        
        if len(row_cells) > 6:
            desktop_cell = row_cells[6]
            desktop_has_green_bg = _has_target_background_color(desktop_cell)
    
    mobile_complete = mobile_has_passed_text or mobile_has_green_bg
    desktop_complete = desktop_has_passed_text or desktop_has_green_bg
    
    should_skip = mobile_complete and desktop_complete
    
    actual_row_number = row_idx + 2
    
    if should_skip:
        skip_reasons = []
        if mobile_has_passed_text:
            skip_reasons.append(f"F{actual_row_number} contains 'passed' text")
        if mobile_has_green_bg:
            skip_reasons.append(f"F{actual_row_number} has #b7e1cd background")
        if desktop_has_passed_text:
            skip_reasons.append(f"G{actual_row_number} contains 'passed' text")
        if desktop_has_green_bg:
            skip_reasons.append(f"G{actual_row_number} has #b7e1cd background")
        
        logger.debug(
            f"Skipping row {actual_row_number}: Both columns complete - {', '.join(skip_reasons)}",
            extra={
                'row': actual_row_number,
                'mobile_complete': mobile_complete,
                'desktop_complete': desktop_complete,
                'mobile_passed_text': mobile_has_passed_text,
                'mobile_green_bg': mobile_has_green_bg,
                'desktop_passed_text': desktop_has_passed_text,
                'desktop_green_bg': desktop_has_green_bg
            }
        )
    else:
        status_parts = []
        if mobile_complete:
            status_parts.append("F complete")
        else:
            status_parts.append("F incomplete")
        if desktop_complete:
            status_parts.append("G complete")
        else:
            status_parts.append("G incomplete")
        
        logger.debug(
            f"Processing row {actual_row_number}: {', '.join(status_parts)} - partial fill allows processing",
            extra={
                'row': actual_row_number,
                'mobile_complete': mobile_complete,
                'desktop_complete': desktop_complete,
                'mobile_passed_text': mobile_has_passed_text,
                'mobile_green_bg': mobile_has_green_bg,
                'desktop_passed_text': desktop_has_passed_text,
                'desktop_green_bg': desktop_has_green_bg
            }
        )
    
    return should_skip


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


def write_psi_url(spreadsheet_id: str, tab_name: str, row_index: int, column: str, url: str, service=None, service_account_file: Optional[str] = None, dry_run: bool = False) -> None:
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
        dry_run: If True, log the operation but don't execute it
        
    Raises:
        PermanentError: If there's a permission or resource error
    """
    if service is None:
        if service_account_file is None:
            raise ValueError("Either service or service_account_file must be provided")
        service = authenticate(service_account_file)
    
    rate_limiter = get_spreadsheet_rate_limiter()
    audit_trail = get_audit_trail()
    logger = get_logger()
    
    if dry_run:
        logger.info(f"[DRY RUN] Would write to {tab_name}!{column}{row_index}: {url}")
        return
    
    rate_limiter.acquire(spreadsheet_id)
    
    with _write_lock:
        sheet = service.spreadsheets()
        range_name = f"{tab_name}!{column}{row_index}"
        
        body = {
            'values': [[url]]
        }
        
        def _write():
            return sheet.values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
        
        _execute_with_retry(_write)
        
        audit_trail.log_modification(
            spreadsheet_id=spreadsheet_id,
            tab_name=tab_name,
            row_index=row_index,
            column=column,
            value=url
        )


def batch_write_psi_urls(spreadsheet_id: str, tab_name: str, updates: List[Tuple[int, str, str]], service=None, service_account_file: Optional[str] = None, dry_run: bool = False) -> None:
    """
    Batch write PSI URLs to multiple cells in the spreadsheet (thread-safe).
    Writes in chunks of 100 cells with retry and exponential backoff.
    
    Args:
        spreadsheet_id: The ID of the Google Spreadsheet
        tab_name: The name of the tab/sheet to write to
        updates: List of tuples containing (row_index, column, url)
        service: Optional authenticated service object. If not provided, service_account_file must be provided
        service_account_file: Optional path to service account JSON file. Used if service is not provided
        dry_run: If True, log the operation but don't execute it
        
    Raises:
        PermanentError: If there's a permission or resource error
    """
    if not updates:
        return
    
    if service is None:
        if service_account_file is None:
            raise ValueError("Either service or service_account_file must be provided")
        service = authenticate(service_account_file)
    
    rate_limiter = get_spreadsheet_rate_limiter()
    audit_trail = get_audit_trail()
    logger = get_logger()
    
    if dry_run:
        for row_index, column, url in updates:
            logger.info(f"[DRY RUN] Would write to {tab_name}!{column}{row_index}: {url}")
        return
    
    rate_limiter.acquire(spreadsheet_id)
    
    with _write_lock:
        sheet = service.spreadsheets()
        
        chunk_size = 100
        for i in range(0, len(updates), chunk_size):
            chunk = updates[i:i + chunk_size]
            
            data = []
            for row_index, column, url in chunk:
                range_name = f"{tab_name}!{column}{row_index}"
                data.append({
                    'range': range_name,
                    'values': [[url]]
                })
            
            body = {
                'valueInputOption': 'RAW',
                'data': data
            }
            
            def _batch_write():
                return sheet.values().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body=body
                ).execute()
            
            _execute_with_retry(_batch_write)
            
            audit_trail.log_batch_modification(
                spreadsheet_id=spreadsheet_id,
                tab_name=tab_name,
                updates=chunk
            )
