from typing import List, Tuple, Optional, Dict, Any
from tools.utils.logger import get_logger
from tools.utils.exceptions import PermanentError


class SpreadsheetSchemaValidator:
    
    EXPECTED_COLUMNS = {
        'A': 'URL',
        'F': 'Mobile PSI',
        'G': 'Desktop PSI'
    }
    
    MIN_COLUMNS = 7
    
    def __init__(self):
        self.logger = get_logger()
    
    def validate_schema(self, spreadsheet_id: str, tab_name: str, service) -> Tuple[bool, List[str]]:
        errors = []
        
        try:
            sheet = service.spreadsheets()
            
            spreadsheet_metadata = sheet.get(
                spreadsheetId=spreadsheet_id,
                ranges=[f"{tab_name}!A1:G1"],
                fields='sheets(properties(title,gridProperties),data(rowData(values(formattedValue))))'
            ).execute()
            
            if not spreadsheet_metadata.get('sheets'):
                errors.append(f"Tab '{tab_name}' not found in spreadsheet")
                return False, errors
            
            sheet_data = spreadsheet_metadata['sheets'][0]
            grid_properties = sheet_data.get('properties', {}).get('gridProperties', {})
            column_count = grid_properties.get('columnCount', 0)
            
            if column_count < self.MIN_COLUMNS:
                errors.append(
                    f"Insufficient columns: found {column_count}, expected at least {self.MIN_COLUMNS} "
                    f"(A through G)"
                )
            
            header_data = sheet_data.get('data', [])
            if header_data and header_data[0].get('rowData'):
                header_row = header_data[0]['rowData'][0].get('values', [])
                
                if not header_row or len(header_row) == 0:
                    self.logger.warning("No header row found in spreadsheet (row 1 is empty)")
                else:
                    column_names = {}
                    for idx, cell in enumerate(header_row):
                        value = cell.get('formattedValue', '').strip()
                        if value:
                            column_letter = chr(65 + idx)
                            column_names[column_letter] = value
                    
                    for col, expected_name in self.EXPECTED_COLUMNS.items():
                        if col in column_names:
                            actual_name = column_names[col]
                            self.logger.info(f"Column {col} header: '{actual_name}'")
                        else:
                            self.logger.warning(
                                f"Column {col} is empty (expected '{expected_name}')"
                            )
            else:
                self.logger.warning("Could not read header row for validation")
            
            range_result = sheet.values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{tab_name}!A:A"
            ).execute()
            
            values = range_result.get('values', [])
            
            if len(values) <= 1:
                errors.append("No data rows found in column A (only header or empty)")
            
        except Exception as e:
            errors.append(f"Schema validation error: {e}")
            self.logger.error(f"Schema validation failed: {e}", exc_info=True)
        
        is_valid = len(errors) == 0
        
        if is_valid:
            self.logger.info(f"Schema validation passed for tab '{tab_name}'")
        else:
            self.logger.warning(f"Schema validation issues found for tab '{tab_name}':")
            for error in errors:
                self.logger.warning(f"  - {error}")
        
        return is_valid, errors
    
    def validate_required_columns_exist(self, tab_name: str, service, spreadsheet_id: str) -> Tuple[bool, List[str]]:
        errors = []
        
        try:
            result = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                ranges=[f"{tab_name}!A1:G1"]
            ).execute()
            
            sheets = result.get('sheets', [])
            if not sheets:
                errors.append(f"Tab '{tab_name}' not found")
                return False, errors
            
        except Exception as e:
            errors.append(f"Could not validate columns: {e}")
            return False, errors
        
        return len(errors) == 0, errors
