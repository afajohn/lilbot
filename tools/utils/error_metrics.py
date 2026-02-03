import threading
import time
from typing import Dict, Optional, List
from datetime import datetime
from collections import defaultdict
import json


class ErrorMetrics:
    """
    Collects and tracks error metrics for monitoring and analysis.
    Thread-safe implementation for concurrent usage.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._errors_by_type: Dict[str, int] = defaultdict(int)
        self._errors_by_function: Dict[str, int] = defaultdict(int)
        self._error_details: List[Dict] = []
        self._start_time = time.time()
        self._total_operations = 0
        self._successful_operations = 0
        self._retried_operations = 0
        self._failed_operations = 0
    
    def record_error(
        self,
        error_type: str,
        function_name: str,
        error_message: str,
        is_retryable: bool = False,
        attempt: int = 1,
        traceback: Optional[str] = None
    ):
        """
        Record an error occurrence.
        
        Args:
            error_type: Type/category of error (e.g., 'NetworkError', 'TimeoutError')
            function_name: Name of function where error occurred
            error_message: Error message
            is_retryable: Whether error is retryable
            attempt: Attempt number when error occurred
            traceback: Optional traceback string
        """
        with self._lock:
            self._errors_by_type[error_type] += 1
            self._errors_by_function[function_name] += 1
            
            self._error_details.append({
                'timestamp': datetime.now().isoformat(),
                'error_type': error_type,
                'function_name': function_name,
                'error_message': error_message,
                'is_retryable': is_retryable,
                'attempt': attempt,
                'traceback': traceback
            })
            
            if len(self._error_details) > 1000:
                self._error_details = self._error_details[-1000:]
    
    def record_success(self, function_name: str, was_retried: bool = False):
        """
        Record a successful operation.
        
        Args:
            function_name: Name of function that succeeded
            was_retried: Whether operation succeeded after retry
        """
        with self._lock:
            self._successful_operations += 1
            if was_retried:
                self._retried_operations += 1
    
    def record_failure(self, function_name: str):
        """
        Record a failed operation (after all retries exhausted).
        
        Args:
            function_name: Name of function that failed
        """
        with self._lock:
            self._failed_operations += 1
    
    def increment_total_operations(self):
        """Increment total operations counter"""
        with self._lock:
            self._total_operations += 1
    
    def get_summary(self) -> Dict:
        """
        Get summary of error metrics.
        
        Returns:
            Dictionary containing error statistics
        """
        with self._lock:
            elapsed_time = time.time() - self._start_time
            
            return {
                'elapsed_time_seconds': elapsed_time,
                'total_operations': self._total_operations,
                'successful_operations': self._successful_operations,
                'failed_operations': self._failed_operations,
                'retried_operations': self._retried_operations,
                'success_rate': (
                    self._successful_operations / self._total_operations * 100
                    if self._total_operations > 0 else 0.0
                ),
                'retry_rate': (
                    self._retried_operations / self._total_operations * 100
                    if self._total_operations > 0 else 0.0
                ),
                'errors_by_type': dict(self._errors_by_type),
                'errors_by_function': dict(self._errors_by_function),
                'total_errors': sum(self._errors_by_type.values()),
                'recent_errors': self._error_details[-10:] if self._error_details else []
            }
    
    def get_detailed_errors(self, limit: int = 100) -> List[Dict]:
        """
        Get detailed error information.
        
        Args:
            limit: Maximum number of errors to return
            
        Returns:
            List of error detail dictionaries
        """
        with self._lock:
            return self._error_details[-limit:] if self._error_details else []
    
    def reset(self):
        """Reset all metrics"""
        with self._lock:
            self._errors_by_type.clear()
            self._errors_by_function.clear()
            self._error_details.clear()
            self._start_time = time.time()
            self._total_operations = 0
            self._successful_operations = 0
            self._retried_operations = 0
            self._failed_operations = 0
    
    def to_json(self, indent: int = 2) -> str:
        """
        Export metrics as JSON string.
        
        Args:
            indent: JSON indentation level
            
        Returns:
            JSON string of metrics summary
        """
        return json.dumps(self.get_summary(), indent=indent)
    
    def print_summary(self):
        """Print formatted summary of metrics"""
        summary = self.get_summary()
        
        print("\n" + "=" * 80)
        print("ERROR METRICS SUMMARY")
        print("=" * 80)
        print(f"Elapsed Time: {summary['elapsed_time_seconds']:.2f}s")
        print(f"Total Operations: {summary['total_operations']}")
        print(f"Successful: {summary['successful_operations']} ({summary['success_rate']:.1f}%)")
        print(f"Failed: {summary['failed_operations']}")
        print(f"Retried: {summary['retried_operations']} ({summary['retry_rate']:.1f}%)")
        print(f"Total Errors: {summary['total_errors']}")
        print()
        
        if summary['errors_by_type']:
            print("Errors by Type:")
            for error_type, count in sorted(
                summary['errors_by_type'].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                print(f"  {error_type}: {count}")
            print()
        
        if summary['errors_by_function']:
            print("Errors by Function:")
            for func_name, count in sorted(
                summary['errors_by_function'].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                print(f"  {func_name}: {count}")
            print()
        
        if summary['recent_errors']:
            print("Recent Errors (last 10):")
            for error in summary['recent_errors']:
                print(f"  [{error['timestamp']}] {error['error_type']} in {error['function_name']}")
                print(f"    {error['error_message']}")
            print()
        
        print("=" * 80)


_global_metrics = None
_metrics_lock = threading.Lock()


def get_global_metrics() -> ErrorMetrics:
    """Get or create global error metrics instance"""
    global _global_metrics
    with _metrics_lock:
        if _global_metrics is None:
            _global_metrics = ErrorMetrics()
        return _global_metrics
