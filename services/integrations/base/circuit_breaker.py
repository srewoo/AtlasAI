"""
Circuit Breaker Pattern Implementation
Prevents cascading failures by stopping requests to failing services
"""
import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation, requests flow through
    OPEN = "open"          # Failing, requests are blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5       # Failures before opening
    success_threshold: int = 3       # Successes before closing
    timeout: float = 30.0            # Seconds before trying again
    excluded_exceptions: tuple = ()  # Exceptions that don't count as failures


class CircuitBreaker:
    """
    Circuit Breaker implementation

    States:
    - CLOSED: Normal operation
    - OPEN: Service is failing, reject requests immediately
    - HALF_OPEN: Testing recovery, allow limited requests

    Usage:
        breaker = CircuitBreaker()

        async with breaker:
            result = await external_service_call()
    """

    def __init__(self, name: str = "default", config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        return self._state

    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN

    async def __aenter__(self):
        """Enter context manager - check if request is allowed"""
        await self._before_request()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - record success or failure"""
        if exc_type is None:
            await self._on_success()
        elif not isinstance(exc_val, self.config.excluded_exceptions):
            await self._on_failure(exc_val)
        return False  # Don't suppress exceptions

    async def _before_request(self):
        """Called before each request"""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if timeout has elapsed
                if self._last_failure_time:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.config.timeout:
                        logger.info(f"Circuit {self.name}: Transitioning to HALF_OPEN")
                        self._state = CircuitState.HALF_OPEN
                        self._success_count = 0
                    else:
                        raise CircuitOpenError(
                            f"Circuit {self.name} is OPEN. "
                            f"Retry in {self.config.timeout - elapsed:.1f}s"
                        )

    async def _on_success(self):
        """Record a successful request"""
        async with self._lock:
            self._failure_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    logger.info(f"Circuit {self.name}: Closing (service recovered)")
                    self._state = CircuitState.CLOSED
                    self._success_count = 0

    async def _on_failure(self, error: Exception):
        """Record a failed request"""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            logger.warning(f"Circuit {self.name}: Failure #{self._failure_count}: {error}")

            if self._state == CircuitState.HALF_OPEN:
                # Immediately open on failure in half-open state
                logger.warning(f"Circuit {self.name}: Opening (failed in HALF_OPEN)")
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.config.failure_threshold:
                logger.warning(f"Circuit {self.name}: Opening (threshold reached)")
                self._state = CircuitState.OPEN

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function through the circuit breaker

        Args:
            func: Async function to call
            *args, **kwargs: Arguments to pass to function

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open
        """
        async with self:
            return await func(*args, **kwargs)

    def get_status(self) -> dict:
        """Get circuit breaker status"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time
        }


class CircuitOpenError(Exception):
    """Raised when trying to use an open circuit"""
    pass


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers
    """

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker"""
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    def get_all_status(self) -> dict:
        """Get status of all circuit breakers"""
        return {
            name: breaker.get_status()
            for name, breaker in self._breakers.items()
        }


# Global registry
circuit_registry = CircuitBreakerRegistry()


def with_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None):
    """
    Decorator to wrap a function with circuit breaker

    Usage:
        @with_circuit_breaker("github-api")
        async def fetch_from_github():
            ...
    """
    def decorator(func):
        breaker = CircuitBreaker(name, config)

        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)

        wrapper.circuit_breaker = breaker
        return wrapper

    return decorator
