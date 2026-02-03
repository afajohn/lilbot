import time
import threading
from typing import Dict
from collections import defaultdict


class SpreadsheetRateLimiter:
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.window_size = 60.0
        self.spreadsheet_requests: Dict[str, list] = defaultdict(list)
        self.lock = threading.Lock()
    
    def acquire(self, spreadsheet_id: str) -> None:
        with self.lock:
            now = time.time()
            cutoff = now - self.window_size
            
            self.spreadsheet_requests[spreadsheet_id] = [
                timestamp for timestamp in self.spreadsheet_requests[spreadsheet_id]
                if timestamp > cutoff
            ]
            
            if len(self.spreadsheet_requests[spreadsheet_id]) >= self.requests_per_minute:
                oldest_request = self.spreadsheet_requests[spreadsheet_id][0]
                wait_time = self.window_size - (now - oldest_request)
                if wait_time > 0:
                    time.sleep(wait_time)
                    now = time.time()
            
            self.spreadsheet_requests[spreadsheet_id].append(now)
    
    def get_usage(self, spreadsheet_id: str) -> Dict[str, any]:
        with self.lock:
            now = time.time()
            cutoff = now - self.window_size
            
            self.spreadsheet_requests[spreadsheet_id] = [
                timestamp for timestamp in self.spreadsheet_requests[spreadsheet_id]
                if timestamp > cutoff
            ]
            
            current_requests = len(self.spreadsheet_requests[spreadsheet_id])
            return {
                'current_requests': current_requests,
                'max_requests': self.requests_per_minute,
                'remaining': max(0, self.requests_per_minute - current_requests),
                'window_size': self.window_size
            }


_rate_limiter_instance = None
_rate_limiter_lock = threading.Lock()


def get_spreadsheet_rate_limiter() -> SpreadsheetRateLimiter:
    global _rate_limiter_instance
    with _rate_limiter_lock:
        if _rate_limiter_instance is None:
            _rate_limiter_instance = SpreadsheetRateLimiter()
        return _rate_limiter_instance
