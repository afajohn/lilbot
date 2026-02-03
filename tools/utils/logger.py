import logging
import os
import threading
import json
import traceback
from datetime import datetime
from typing import Optional, Dict, Any


_logger_lock = threading.Lock()


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that adds structured error context to log records.
    Handles 'extra' dict fields and formats them for better readability.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        base_message = super().format(record)
        
        if hasattr(record, 'extra_data'):
            extra_data = record.extra_data
            if extra_data:
                extra_str = json.dumps(extra_data, indent=2, default=str)
                base_message += f"\n  Context: {extra_str}"
        
        if hasattr(record, 'traceback') and record.traceback:
            base_message += f"\n  Traceback:\n{record.traceback}"
        
        return base_message


class ErrorContextFilter(logging.Filter):
    """
    Filter that extracts structured error context from 'extra' dict in log records.
    This allows structured logging while keeping the log messages clean.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        extra_fields = [
            'function', 'attempt', 'max_attempts', 'error_type', 'exception_type',
            'retry_delay', 'traceback', 'circuit_breaker', 'state', 'failure_count',
            'url', 'http_status', 'remaining_timeout', 'elapsed_time'
        ]
        
        extra_data = {}
        for field in extra_fields:
            if hasattr(record, field):
                extra_data[field] = getattr(record, field)
        
        if extra_data:
            record.extra_data = extra_data
        
        return True


def setup_logger(name: str = 'audit', log_dir: str = 'logs') -> logging.Logger:
    """
    Set up a thread-safe logger with both console and file handlers.
    Includes structured error logging with traceback context.
    
    Args:
        name: Logger name
        log_dir: Directory to store log files
        
    Returns:
        Configured logger instance
    """
    with _logger_lock:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        
        if logger.handlers:
            return logger
        
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(log_dir, f'audit_{timestamp}.log')
        
        file_formatter = StructuredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(ErrorContextFilter())
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        logger.info(f"Logging to file: {log_file}")
        
        return logger


def get_logger(name: str = 'audit') -> logging.Logger:
    """
    Get an existing logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_error_with_context(
    logger: logging.Logger,
    message: str,
    exception: Optional[Exception] = None,
    context: Optional[Dict[str, Any]] = None,
    include_traceback: bool = True
):
    """
    Log an error with structured context and optional traceback.
    
    Args:
        logger: Logger instance to use
        message: Error message
        exception: Optional exception object
        context: Optional dictionary of context information
        include_traceback: Whether to include traceback in log
    """
    extra = context or {}
    
    if exception:
        extra['exception_type'] = type(exception).__name__
        extra['exception_message'] = str(exception)
    
    if include_traceback:
        extra['traceback'] = traceback.format_exc()
    
    logger.error(message, extra=extra)


def log_warning_with_context(
    logger: logging.Logger,
    message: str,
    context: Optional[Dict[str, Any]] = None
):
    """
    Log a warning with structured context.
    
    Args:
        logger: Logger instance to use
        message: Warning message
        context: Optional dictionary of context information
    """
    extra = context or {}
    logger.warning(message, extra=extra)


def log_info_with_context(
    logger: logging.Logger,
    message: str,
    context: Optional[Dict[str, Any]] = None
):
    """
    Log an info message with structured context.
    
    Args:
        logger: Logger instance to use
        message: Info message
        context: Optional dictionary of context information
    """
    extra = context or {}
    logger.info(message, extra=extra)
