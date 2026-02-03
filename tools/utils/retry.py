import time
import logging
import traceback
from functools import wraps
from typing import Callable, Tuple, Type, Optional
from .exceptions import RetryableError, PermanentError


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (RetryableError,),
    permanent_exceptions: Tuple[Type[Exception], ...] = (PermanentError,),
    logger: Optional[logging.Logger] = None
) -> Callable:
    """
    Decorator that implements exponential backoff retry logic with structured error logging.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds between retries
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delay (reduces thundering herd)
        retryable_exceptions: Tuple of exception types that should trigger retry
        permanent_exceptions: Tuple of exception types that should NOT be retried
        logger: Optional logger instance for structured logging
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)
            
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except permanent_exceptions as e:
                    logger.error(
                        f"Permanent error in {func.__name__}: {str(e)}",
                        extra={
                            'function': func.__name__,
                            'attempt': attempt + 1,
                            'error_type': 'permanent',
                            'exception_type': type(e).__name__,
                            'traceback': traceback.format_exc()
                        }
                    )
                    raise
                    
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        actual_delay = min(delay, max_delay)
                        
                        if jitter:
                            import random
                            actual_delay = actual_delay * (0.5 + random.random())
                        
                        logger.warning(
                            f"Retryable error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}): {str(e)}. "
                            f"Retrying in {actual_delay:.2f}s",
                            extra={
                                'function': func.__name__,
                                'attempt': attempt + 1,
                                'max_attempts': max_retries + 1,
                                'error_type': 'retryable',
                                'exception_type': type(e).__name__,
                                'retry_delay': actual_delay,
                                'traceback': traceback.format_exc()
                            }
                        )
                        
                        time.sleep(actual_delay)
                        delay *= exponential_base
                    else:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}: {str(e)}",
                            extra={
                                'function': func.__name__,
                                'attempt': attempt + 1,
                                'error_type': 'retryable_exhausted',
                                'exception_type': type(e).__name__,
                                'traceback': traceback.format_exc()
                            }
                        )
                        raise
                        
                except Exception as e:
                    logger.error(
                        f"Unexpected error in {func.__name__}: {str(e)}",
                        extra={
                            'function': func.__name__,
                            'attempt': attempt + 1,
                            'error_type': 'unexpected',
                            'exception_type': type(e).__name__,
                            'traceback': traceback.format_exc()
                        }
                    )
                    raise
            
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator
