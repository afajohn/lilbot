class RetryableError(Exception):
    """
    Exception that indicates the operation can be retried.
    Used for transient failures like network errors, rate limiting, or temporary service unavailability.
    """
    def __init__(self, message: str, original_exception: Exception = None):
        super().__init__(message)
        self.original_exception = original_exception


class PermanentError(Exception):
    """
    Exception that indicates the operation should not be retried.
    Used for errors like invalid input, authentication failures, or business logic errors.
    """
    def __init__(self, message: str, original_exception: Exception = None):
        super().__init__(message)
        self.original_exception = original_exception
