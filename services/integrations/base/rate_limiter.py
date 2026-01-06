"""
Rate Limiter - Token Bucket + Sliding Window implementation
Handles API rate limits gracefully with backoff strategies
"""
import asyncio
import time
from typing import Optional
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    requests_per_window: int = 100
    window_seconds: int = 60
    burst_size: int = 10  # Allow small bursts
    retry_after_header: str = "Retry-After"


class TokenBucket:
    """Token Bucket algorithm for rate limiting"""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens from the bucket

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False otherwise
        """
        async with self._lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def wait_for_token(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """
        Wait until tokens are available

        Args:
            tokens: Number of tokens needed
            timeout: Maximum time to wait

        Returns:
            True if tokens acquired within timeout
        """
        start = time.monotonic()

        while time.monotonic() - start < timeout:
            if await self.acquire(tokens):
                return True

            # Calculate wait time for next token
            wait_time = (tokens - self.tokens) / self.refill_rate
            wait_time = min(wait_time, timeout - (time.monotonic() - start))

            if wait_time > 0:
                await asyncio.sleep(min(wait_time, 1.0))

        return False

    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.monotonic()
        elapsed = now - self.last_refill
        refill_amount = elapsed * self.refill_rate

        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self.last_refill = now


class SlidingWindowCounter:
    """Sliding window rate limiter for precise rate limiting"""

    def __init__(self, window_seconds: int, max_requests: int):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.requests: deque = deque()
        self._lock = asyncio.Lock()

    async def is_allowed(self) -> bool:
        """Check if request is allowed within rate limit"""
        async with self._lock:
            now = time.time()
            window_start = now - self.window_seconds

            # Remove old requests outside window
            while self.requests and self.requests[0] < window_start:
                self.requests.popleft()

            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True

            return False

    async def wait_until_allowed(self, timeout: float = 30.0) -> bool:
        """Wait until a request slot is available"""
        start = time.time()

        while time.time() - start < timeout:
            if await self.is_allowed():
                return True

            # Calculate time until oldest request expires
            async with self._lock:
                if self.requests:
                    oldest = self.requests[0]
                    wait_time = oldest + self.window_seconds - time.time()
                    if wait_time > 0:
                        await asyncio.sleep(min(wait_time + 0.1, 1.0))
                else:
                    await asyncio.sleep(0.1)

        return False

    def get_remaining(self) -> int:
        """Get remaining requests in current window"""
        now = time.time()
        window_start = now - self.window_seconds

        # Count requests in current window
        count = sum(1 for r in self.requests if r >= window_start)
        return max(0, self.max_requests - count)


class RateLimiter:
    """
    Combined rate limiter using both Token Bucket and Sliding Window
    Provides smooth rate limiting with burst support
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config

        # Token bucket for burst handling
        self.token_bucket = TokenBucket(
            capacity=config.burst_size,
            refill_rate=config.requests_per_window / config.window_seconds
        )

        # Sliding window for precise limiting
        self.sliding_window = SlidingWindowCounter(
            window_seconds=config.window_seconds,
            max_requests=config.requests_per_window
        )

        # Track retry-after from API responses
        self.retry_after: Optional[float] = None
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """
        Try to acquire permission for a request

        Returns:
            True if request is allowed
        """
        # Check if we're in a forced wait period
        if self.retry_after and time.time() < self.retry_after:
            return False

        # Check both limiters
        if await self.token_bucket.acquire():
            if await self.sliding_window.is_allowed():
                return True

        return False

    async def wait_for_slot(self, timeout: float = 60.0) -> bool:
        """
        Wait for an available request slot

        Args:
            timeout: Maximum time to wait

        Returns:
            True if slot acquired within timeout
        """
        start = time.time()

        # First check retry-after
        if self.retry_after:
            wait_time = self.retry_after - time.time()
            if wait_time > 0:
                if wait_time > timeout:
                    return False
                logger.info(f"Waiting {wait_time:.1f}s due to Retry-After header")
                await asyncio.sleep(wait_time)
                self.retry_after = None

        remaining = timeout - (time.time() - start)
        if remaining <= 0:
            return False

        # Wait for token bucket
        if not await self.token_bucket.wait_for_token(timeout=remaining):
            return False

        remaining = timeout - (time.time() - start)
        if remaining <= 0:
            return False

        # Wait for sliding window
        return await self.sliding_window.wait_until_allowed(timeout=remaining)

    def set_retry_after(self, seconds: float):
        """Set a forced wait period (from API response)"""
        self.retry_after = time.time() + seconds
        logger.warning(f"Rate limit hit, retry after {seconds}s")

    def get_remaining_requests(self) -> int:
        """Get estimated remaining requests"""
        return self.sliding_window.get_remaining()


class AdaptiveRateLimiter(RateLimiter):
    """
    Adaptive rate limiter that adjusts based on API responses
    Learns from rate limit headers and errors
    """

    def __init__(self, config: RateLimitConfig):
        super().__init__(config)
        self.success_count = 0
        self.error_count = 0
        self.last_adjustment = time.time()
        self.adjustment_interval = 60  # seconds

    async def record_success(self):
        """Record a successful request"""
        self.success_count += 1
        await self._maybe_adjust()

    async def record_rate_limit_error(self, retry_after: Optional[float] = None):
        """Record a rate limit error"""
        self.error_count += 1

        if retry_after:
            self.set_retry_after(retry_after)
        else:
            # Exponential backoff based on error count
            backoff = min(60, 2 ** self.error_count)
            self.set_retry_after(backoff)

        await self._maybe_adjust()

    async def _maybe_adjust(self):
        """Adjust rate limits based on observed behavior"""
        now = time.time()

        if now - self.last_adjustment < self.adjustment_interval:
            return

        self.last_adjustment = now

        # If we're seeing too many errors, reduce rate
        if self.error_count > 0 and self.success_count > 0:
            error_rate = self.error_count / (self.success_count + self.error_count)

            if error_rate > 0.1:  # More than 10% errors
                # Reduce rate by 20%
                new_rate = int(self.config.requests_per_window * 0.8)
                logger.warning(f"High error rate ({error_rate:.1%}), reducing limit to {new_rate}")
                self.sliding_window.max_requests = new_rate

        # Reset counters
        self.success_count = 0
        self.error_count = 0
