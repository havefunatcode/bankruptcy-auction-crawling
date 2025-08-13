"""
Error handling and retry mechanisms for the crawler
"""
import asyncio
import time
from typing import Any, Callable, Optional, Dict, List
from functools import wraps
from utils.logger import setup_logger
from config import MAX_RETRIES, RETRY_DELAY


class ErrorHandler:
    """Centralized error handling and retry logic"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.error_counts = {}
        self.last_errors = {}
        
    def retry_async(self, 
                   max_retries: int = MAX_RETRIES,
                   delay: float = RETRY_DELAY,
                   backoff_multiplier: float = 1.5,
                   exceptions: tuple = (Exception,)):
        """Decorator for async functions with retry logic"""
        
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                last_exception = None
                current_delay = delay
                
                for attempt in range(max_retries + 1):
                    try:
                        result = await func(*args, **kwargs)
                        
                        # Reset error count on success
                        func_name = func.__name__
                        if func_name in self.error_counts:
                            self.error_counts[func_name] = 0
                            
                        return result
                        
                    except exceptions as e:
                        last_exception = e
                        func_name = func.__name__
                        
                        # Track error
                        self.error_counts[func_name] = self.error_counts.get(func_name, 0) + 1
                        self.last_errors[func_name] = str(e)
                        
                        if attempt < max_retries:
                            self.logger.warning(
                                f"Attempt {attempt + 1} failed for {func_name}: {e}. "
                                f"Retrying in {current_delay:.1f}s..."
                            )
                            await asyncio.sleep(current_delay)
                            current_delay *= backoff_multiplier
                        else:
                            self.logger.error(
                                f"All {max_retries + 1} attempts failed for {func_name}. "
                                f"Last error: {e}"
                            )
                            
                raise last_exception
                
            return wrapper
        return decorator
        
    def retry_sync(self,
                  max_retries: int = MAX_RETRIES,
                  delay: float = RETRY_DELAY,
                  backoff_multiplier: float = 1.5,
                  exceptions: tuple = (Exception,)):
        """Decorator for sync functions with retry logic"""
        
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                current_delay = delay
                
                for attempt in range(max_retries + 1):
                    try:
                        result = func(*args, **kwargs)
                        
                        # Reset error count on success
                        func_name = func.__name__
                        if func_name in self.error_counts:
                            self.error_counts[func_name] = 0
                            
                        return result
                        
                    except exceptions as e:
                        last_exception = e
                        func_name = func.__name__
                        
                        # Track error
                        self.error_counts[func_name] = self.error_counts.get(func_name, 0) + 1
                        self.last_errors[func_name] = str(e)
                        
                        if attempt < max_retries:
                            self.logger.warning(
                                f"Attempt {attempt + 1} failed for {func_name}: {e}. "
                                f"Retrying in {current_delay:.1f}s..."
                            )
                            time.sleep(current_delay)
                            current_delay *= backoff_multiplier
                        else:
                            self.logger.error(
                                f"All {max_retries + 1} attempts failed for {func_name}. "
                                f"Last error: {e}"
                            )
                            
                raise last_exception
                
            return wrapper
        return decorator
        
    def circuit_breaker(self,
                       failure_threshold: int = 5,
                       timeout: float = 60.0,
                       expected_exception: type = Exception):
        """Circuit breaker pattern decorator"""
        
        def decorator(func: Callable):
            func._circuit_breaker_state = 'closed'  # closed, open, half-open
            func._failure_count = 0
            func._last_failure_time = None
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                current_time = time.time()
                
                # Check circuit state
                if func._circuit_breaker_state == 'open':
                    if current_time - func._last_failure_time < timeout:
                        raise CircuitBreakerOpenError(
                            f"Circuit breaker is open for {func.__name__}"
                        )
                    else:
                        func._circuit_breaker_state = 'half-open'
                        self.logger.info(f"Circuit breaker half-open for {func.__name__}")
                        
                try:
                    result = await func(*args, **kwargs)
                    
                    # Success - reset circuit breaker
                    if func._circuit_breaker_state == 'half-open':
                        func._circuit_breaker_state = 'closed'
                        func._failure_count = 0
                        self.logger.info(f"Circuit breaker closed for {func.__name__}")
                        
                    return result
                    
                except expected_exception as e:
                    func._failure_count += 1
                    func._last_failure_time = current_time
                    
                    if func._failure_count >= failure_threshold:
                        func._circuit_breaker_state = 'open'
                        self.logger.error(
                            f"Circuit breaker opened for {func.__name__} "
                            f"after {func._failure_count} failures"
                        )
                        
                    raise e
                    
            return wrapper
        return decorator
        
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring"""
        return {
            'error_counts': self.error_counts.copy(),
            'last_errors': self.last_errors.copy(),
            'total_functions_with_errors': len(self.error_counts),
            'total_errors': sum(self.error_counts.values())
        }
        
    def reset_error_counts(self, function_name: Optional[str] = None):
        """Reset error counts for monitoring"""
        if function_name:
            self.error_counts.pop(function_name, None)
            self.last_errors.pop(function_name, None)
        else:
            self.error_counts.clear()
            self.last_errors.clear()
            
    async def safe_execute(self,
                          func: Callable,
                          *args,
                          default_return: Any = None,
                          log_errors: bool = True,
                          **kwargs) -> Any:
        """Execute function safely with error handling"""
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            if log_errors:
                self.logger.error(f"Error in {func.__name__}: {e}")
            return default_return


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class RateLimiter:
    """Rate limiting utility"""
    
    def __init__(self, calls_per_second: float = 1.0):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_called = 0.0
        self.logger = setup_logger(__name__)
        
    async def acquire(self):
        """Acquire permission to make a call"""
        current_time = time.time()
        elapsed = current_time - self.last_called
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            self.logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            await asyncio.sleep(sleep_time)
            
        self.last_called = time.time()
        
    def __call__(self, func: Callable):
        """Decorator for rate limiting"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await self.acquire()
            return await func(*args, **kwargs)
        return wrapper


# Global error handler instance
error_handler = ErrorHandler()

# Convenience decorators
retry_async = error_handler.retry_async
retry_sync = error_handler.retry_sync
circuit_breaker = error_handler.circuit_breaker