import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import threading
from tools.utils.logger import get_logger


class AuditTrail:
    
    def __init__(self, audit_log_path: str = 'audit_trail.jsonl'):
        self.audit_log_path = audit_log_path
        self.lock = threading.Lock()
        self.logger = get_logger()
        
        log_dir = os.path.dirname(audit_log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
    
    def log_modification(
        self,
        spreadsheet_id: str,
        tab_name: str,
        row_index: int,
        column: str,
        value: str,
        user: Optional[str] = None,
        operation: str = 'update',
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        entry = {
            'timestamp': timestamp,
            'operation': operation,
            'spreadsheet_id': spreadsheet_id,
            'tab_name': tab_name,
            'row': row_index,
            'column': column,
            'value': value,
            'user': user or 'system',
        }
        
        if metadata:
            entry['metadata'] = metadata
        
        with self.lock:
            try:
                with open(self.audit_log_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry) + '\n')
            except Exception as e:
                self.logger.error(f"Failed to write audit trail: {e}")
    
    def log_batch_modification(
        self,
        spreadsheet_id: str,
        tab_name: str,
        updates: list,
        user: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        for row_index, column, value in updates:
            self.log_modification(
                spreadsheet_id=spreadsheet_id,
                tab_name=tab_name,
                row_index=row_index,
                column=column,
                value=value,
                user=user,
                operation='batch_update',
                metadata=metadata
            )


_audit_trail_instance = None
_audit_trail_lock = threading.Lock()


def get_audit_trail() -> AuditTrail:
    global _audit_trail_instance
    with _audit_trail_lock:
        if _audit_trail_instance is None:
            _audit_trail_instance = AuditTrail()
        return _audit_trail_instance
