import time
import threading
import logging
import traceback
from enum import Enum
from typing import Callable, Optional
from functools import wraps


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker pattern implementation to prevent cascading failures.
    
    When failures exceed threshold, the circuit "opens" and requests fail fast
    without attempting the operation. After a timeout, it enters "half-open" state
    to test if the service has recovered.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 300.0,
        expected_exception: type = Exception,
        name: str = "CircuitBreaker",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery (half-open state)
            expected_exception: Exception type that counts as failure
            name: Name for logging purposes
            logger: Optional logger instance
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        self.logger = logger or logging.getLogger(__name__)
        
        self._failure_count = 0
        self._last_failure_time = None
        self._state = CircuitState.CLOSED
        self._lock = threading.Lock()
        self._success_count_in_half_open = 0
        self._half_open_success_threshold = 2
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        with self._lock:
            return self._state
    
    @property
    def failure_count(self) -> int:
        """Get current failure count"""
        with self._lock:
            return self._failure_count
    
    def call(self, func: Callable, *args, **kwargs):
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Function result if successful
            
        Raises:
            Exception: If circuit is open or function fails
        """
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._success_count_in_half_open = 0
                    self.logger.info(
                        f"Circuit breaker '{self.name}' entering HALF_OPEN state",
                        extra={
                            'circuit_breaker': self.name,
                            'state': 'half_open',
                            'failure_count': self._failure_count,
                            'elapsed_time': time.time() - self._last_failure_time
                        }
                    )
                else:
                    elapsed = time.time() - self._last_failure_time if self._last_failure_time else 0
                    remaining = self.recovery_timeout - elapsed
                    error_msg = (
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Service unavailable. Retry in {remaining:.1f}s"
                    )
                    self.logger.warning(
                        error_msg,
                        extra={
                            'circuit_breaker': self.name,
                            'state': 'open',
                            'failure_count': self._failure_count,
                            'remaining_timeout': remaining
                        }
                    )
                    raise Exception(error_msg)
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure(e)
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count_in_half_open += 1
                
                if self._success_count_in_half_open >= self._half_open_success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._last_failure_time = None
                    self.logger.info(
                        f"Circuit breaker '{self.name}' closed after successful recovery",
                        extra={
                            'circuit_breaker': self.name,
                            'state': 'closed',
                            'success_count': self._success_count_in_half_open
                        }
                    )
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0
    
    def _on_failure(self, exception: Exception):
        """Handle failed call"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self.logger.warning(
                    f"Circuit breaker '{self.name}' reopened after failure in HALF_OPEN state",
                    extra={
                        'circuit_breaker': self.name,
                        'state': 'open',
                        'failure_count': self._failure_count,
                        'exception_type': type(exception).__name__,
                        'exception_message': str(exception),
                        'traceback': traceback.format_exc()
                    }
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self.logger.error(
                    f"Circuit breaker '{self.name}' opened after {self._failure_count} failures. "
                    f"Recovery timeout: {self.recovery_timeout}s",
                    extra={
                        'circuit_breaker': self.name,
                        'state': 'open',
                        'failure_count': self._failure_count,
                        'failure_threshold': self.failure_threshold,
                        'recovery_timeout': self.recovery_timeout,
                        'exception_type': type(exception).__name__,
                        'exception_message': str(exception),
                        'traceback': traceback.format_exc()
                    }
                )
            else:
                self.logger.warning(
                    f"Circuit breaker '{self.name}' failure {self._failure_count}/{self.failure_threshold}",
                    extra={
                        'circuit_breaker': self.name,
                        'state': str(self._state.value),
                        'failure_count': self._failure_count,
                        'failure_threshold': self.failure_threshold,
                        'exception_type': type(exception).__name__,
                        'exception_message': str(exception)
                    }
                )
    
    def reset(self):
        """Manually reset circuit breaker to closed state"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._success_count_in_half_open = 0
            self.logger.info(
                f"Circuit breaker '{self.name}' manually reset",
                extra={
                    'circuit_breaker': self.name,
                    'state': 'closed'
                }
            )
    
    def __call__(self, func: Callable) -> Callable:
        """Allow circuit breaker to be used as a decorator"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
