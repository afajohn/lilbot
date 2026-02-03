#!/usr/bin/env python3
"""
Demo script showcasing the enhanced error handling features:
- RetryableError and PermanentError exception classes
- Exponential backoff retry decorator
- Circuit breaker pattern
- Structured error logging with traceback context
- Error metrics collection
"""

import sys
import os
import time
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from utils.exceptions import RetryableError, PermanentError
from utils.retry import retry_with_backoff
from utils.circuit_breaker import CircuitBreaker
from utils.error_metrics import ErrorMetrics, get_global_metrics
from utils.logger import setup_logger, log_error_with_context


def demo_exception_classes():
    """Demonstrate RetryableError and PermanentError"""
    print("\n" + "=" * 80)
    print("DEMO 1: Custom Exception Classes")
    print("=" * 80)
    
    try:
        raise RetryableError(
            "Network timeout - can retry",
            original_exception=TimeoutError("Connection timed out")
        )
    except RetryableError as e:
        print(f"Caught RetryableError: {e}")
        print(f"Original exception: {e.original_exception}")
    
    try:
        raise PermanentError(
            "Invalid API key - cannot retry",
            original_exception=ValueError("API key is malformed")
        )
    except PermanentError as e:
        print(f"Caught PermanentError: {e}")
        print(f"Original exception: {e.original_exception}")


def demo_retry_decorator():
    """Demonstrate exponential backoff retry decorator"""
    print("\n" + "=" * 80)
    print("DEMO 2: Exponential Backoff Retry Decorator")
    print("=" * 80)
    
    logger = setup_logger(name='demo', log_dir='logs')
    
    attempt_count = {'count': 0}
    
    @retry_with_backoff(
        max_retries=3,
        initial_delay=0.5,
        exponential_base=2.0,
        retryable_exceptions=(RetryableError, ConnectionError),
        permanent_exceptions=(PermanentError,),
        logger=logger
    )
    def flaky_function():
        attempt_count['count'] += 1
        print(f"  Attempt {attempt_count['count']}")
        
        if attempt_count['count'] < 3:
            raise RetryableError(f"Transient error on attempt {attempt_count['count']}")
        
        return "Success!"
    
    try:
        result = flaky_function()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Failed after retries: {e}")
    
    @retry_with_backoff(max_retries=2, logger=logger)
    def permanent_failure():
        raise PermanentError("This will not be retried")
    
    try:
        permanent_failure()
    except PermanentError as e:
        print(f"Permanent error (no retries): {e}")


def demo_circuit_breaker():
    """Demonstrate circuit breaker pattern"""
    print("\n" + "=" * 80)
    print("DEMO 3: Circuit Breaker Pattern")
    print("=" * 80)
    
    logger = setup_logger(name='demo', log_dir='logs')
    
    circuit_breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=5.0,
        expected_exception=Exception,
        name="DemoService",
        logger=logger
    )
    
    fail_count = {'count': 0}
    
    def unreliable_service():
        fail_count['count'] += 1
        if fail_count['count'] <= 5:
            raise Exception(f"Service failure #{fail_count['count']}")
        return "Service is back!"
    
    for i in range(8):
        try:
            result = circuit_breaker.call(unreliable_service)
            print(f"Call {i+1}: {result} (State: {circuit_breaker.state.value})")
        except Exception as e:
            print(f"Call {i+1}: Failed - {e} (State: {circuit_breaker.state.value})")
        
        if i == 4:
            print("  Waiting for recovery timeout...")
            time.sleep(5.5)


def demo_error_metrics():
    """Demonstrate error metrics collection"""
    print("\n" + "=" * 80)
    print("DEMO 4: Error Metrics Collection")
    print("=" * 80)
    
    metrics = ErrorMetrics()
    
    for i in range(10):
        metrics.increment_total_operations()
        
        if i % 3 == 0:
            metrics.record_error(
                error_type='NetworkError',
                function_name='api_call',
                error_message=f'Connection failed on attempt {i}',
                is_retryable=True,
                attempt=1
            )
            metrics.record_failure('api_call')
        elif i % 3 == 1:
            metrics.record_error(
                error_type='TimeoutError',
                function_name='api_call',
                error_message=f'Request timeout on attempt {i}',
                is_retryable=True,
                attempt=2
            )
            metrics.record_success('api_call', was_retried=True)
        else:
            metrics.record_success('api_call', was_retried=False)
    
    print("\nMetrics Summary:")
    metrics.print_summary()
    
    print("\nMetrics JSON:")
    print(metrics.to_json())


def demo_structured_logging():
    """Demonstrate structured error logging"""
    print("\n" + "=" * 80)
    print("DEMO 5: Structured Error Logging")
    print("=" * 80)
    
    logger = setup_logger(name='demo', log_dir='logs')
    
    try:
        raise ValueError("Invalid input parameter")
    except ValueError as e:
        log_error_with_context(
            logger,
            "Failed to process request",
            exception=e,
            context={
                'function': 'demo_function',
                'url': 'https://example.com',
                'attempt': 1,
                'timeout': 30
            },
            include_traceback=True
        )


def demo_integration():
    """Demonstrate all features working together"""
    print("\n" + "=" * 80)
    print("DEMO 6: Integrated Error Handling")
    print("=" * 80)
    
    logger = setup_logger(name='demo', log_dir='logs')
    metrics = get_global_metrics()
    
    circuit_breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=5.0,
        name="IntegratedService",
        logger=logger
    )
    
    @retry_with_backoff(
        max_retries=2,
        retryable_exceptions=(RetryableError,),
        logger=logger
    )
    def integrated_service(request_id: int):
        metrics.increment_total_operations()
        
        def execute():
            if random.random() < 0.3:
                raise RetryableError(f"Transient error for request {request_id}")
            return f"Processed request {request_id}"
        
        try:
            result = circuit_breaker.call(execute)
            metrics.record_success('integrated_service')
            return result
        except Exception as e:
            metrics.record_error(
                error_type=type(e).__name__,
                function_name='integrated_service',
                error_message=str(e),
                is_retryable=isinstance(e, RetryableError)
            )
            metrics.record_failure('integrated_service')
            raise
    
    for i in range(5):
        try:
            result = integrated_service(i)
            print(f"Request {i}: {result}")
        except Exception as e:
            print(f"Request {i}: Failed - {e}")
    
    print("\nFinal Metrics:")
    metrics.print_summary()


def main():
    print("\n" + "=" * 80)
    print("ERROR HANDLING FEATURES DEMONSTRATION")
    print("=" * 80)
    
    demo_exception_classes()
    demo_retry_decorator()
    demo_circuit_breaker()
    demo_error_metrics()
    demo_structured_logging()
    demo_integration()
    
    print("\n" + "=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    main()
