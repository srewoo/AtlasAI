"""
Base Integration Service
Template for all integration services with built-in:
- Rate limiting
- Caching
- Circuit breaker
- Retry logic
- Health checks
- Metrics
"""
import asyncio
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .rate_limiter import RateLimiter, RateLimitConfig, AdaptiveRateLimiter
from .cache import MultiLayerCache, cached
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitOpenError
from .chunker import DocumentChunker, ChunkConfig

logger = logging.getLogger(__name__)

T = TypeVar('T')


class SearchQuery(BaseModel):
    """Standard search query model"""
    query: str
    limit: int = 10
    filters: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    """Standard search result model"""
    id: str
    title: str
    content: str
    url: Optional[str] = None
    source: str
    metadata: Optional[Dict[str, Any]] = None
    score: Optional[float] = None


class ServiceHealth(BaseModel):
    """Service health status"""
    status: str  # healthy, degraded, unhealthy
    service: str
    version: str
    uptime: float
    checks: Dict[str, bool]
    metrics: Optional[Dict[str, Any]] = None


@dataclass
class ServiceMetrics:
    """Metrics tracking for service"""
    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    requests_cached: int = 0
    avg_response_time: float = 0.0
    last_request_time: Optional[float] = None
    start_time: float = field(default_factory=time.time)

    def record_request(self, success: bool, duration: float, from_cache: bool = False):
        """Record a request metric"""
        self.requests_total += 1
        if success:
            self.requests_success += 1
        else:
            self.requests_failed += 1
        if from_cache:
            self.requests_cached += 1

        # Update average response time
        self.avg_response_time = (
            (self.avg_response_time * (self.requests_total - 1) + duration)
            / self.requests_total
        )
        self.last_request_time = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "requests_total": self.requests_total,
            "requests_success": self.requests_success,
            "requests_failed": self.requests_failed,
            "requests_cached": self.requests_cached,
            "success_rate": self.requests_success / self.requests_total if self.requests_total > 0 else 0,
            "cache_hit_rate": self.requests_cached / self.requests_total if self.requests_total > 0 else 0,
            "avg_response_time_ms": self.avg_response_time * 1000,
            "uptime_seconds": time.time() - self.start_time
        }


class BaseIntegrationService(ABC):
    """
    Abstract base class for all integration services

    Provides:
    - Rate limiting with adaptive backoff
    - Multi-layer caching
    - Circuit breaker pattern
    - Retry logic with exponential backoff
    - Document chunking
    - Health checks
    - Metrics collection
    """

    def __init__(
        self,
        service_name: str,
        version: str = "1.0.0",
        rate_limit_config: Optional[RateLimitConfig] = None,
        circuit_config: Optional[CircuitBreakerConfig] = None,
        chunk_config: Optional[ChunkConfig] = None,
        redis_url: str = "redis://localhost:6379",
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self.service_name = service_name
        self.version = version
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Initialize components
        self.rate_limiter = AdaptiveRateLimiter(
            rate_limit_config or RateLimitConfig()
        )
        self.circuit_breaker = CircuitBreaker(
            name=service_name,
            config=circuit_config or CircuitBreakerConfig()
        )
        self.cache = MultiLayerCache(
            redis_url=redis_url,
            cache_prefix=service_name
        )
        self.chunker = DocumentChunker(chunk_config or ChunkConfig())
        self.metrics = ServiceMetrics()

        self._initialized = False
        self._api_client = None

    async def initialize(self):
        """Initialize service connections"""
        if self._initialized:
            return

        await self.cache.connect()
        await self._init_client()
        self._initialized = True
        logger.info(f"{self.service_name} initialized")

    @abstractmethod
    async def _init_client(self):
        """Initialize the API client - implement in subclass"""
        pass

    @abstractmethod
    async def _search_impl(self, query: str, limit: int, **kwargs) -> List[Dict]:
        """
        Implement the actual search logic in subclass

        Args:
            query: Search query
            limit: Max results
            **kwargs: Additional parameters

        Returns:
            List of search results
        """
        pass

    @abstractmethod
    async def _health_check_impl(self) -> bool:
        """
        Implement health check logic in subclass

        Returns:
            True if service is healthy
        """
        pass

    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """
        Main search method with all protections

        Args:
            query: Search query object

        Returns:
            List of search results
        """
        start_time = time.time()
        from_cache = False

        try:
            # Check cache first
            cache_key = f"search:{query.query}:{query.limit}"
            cached_result = await self.cache.get(cache_key)
            if cached_result:
                from_cache = True
                self.metrics.record_request(True, time.time() - start_time, from_cache=True)
                return [SearchResult(**r) for r in cached_result]

            # Wait for rate limit slot
            if not await self.rate_limiter.wait_for_slot(timeout=30):
                raise HTTPException(429, "Rate limit exceeded")

            # Execute with circuit breaker and retries
            results = await self._execute_with_protection(
                self._search_impl,
                query.query,
                query.limit,
                **(query.filters or {})
            )

            # Cache results
            if results:
                await self.cache.set(cache_key, [r.dict() if hasattr(r, 'dict') else r for r in results])

            # Record success
            await self.rate_limiter.record_success()
            self.metrics.record_request(True, time.time() - start_time)

            return [SearchResult(**r) if isinstance(r, dict) else r for r in results]

        except CircuitOpenError as e:
            logger.warning(f"{self.service_name} circuit open: {e}")
            self.metrics.record_request(False, time.time() - start_time)
            raise HTTPException(503, f"Service temporarily unavailable: {e}")

        except Exception as e:
            logger.error(f"{self.service_name} search error: {e}")
            self.metrics.record_request(False, time.time() - start_time)
            raise HTTPException(500, f"Search failed: {e}")

    async def _execute_with_protection(self, func, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker and retries

        Args:
            func: Async function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                async with self.circuit_breaker:
                    return await func(*args, **kwargs)

            except CircuitOpenError:
                raise  # Don't retry if circuit is open

            except Exception as e:
                last_error = e
                logger.warning(
                    f"{self.service_name} attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )

                # Check if it's a rate limit error
                if "429" in str(e) or "rate limit" in str(e).lower():
                    await self.rate_limiter.record_rate_limit_error()

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    await asyncio.sleep(delay)

        raise last_error

    async def health_check(self) -> ServiceHealth:
        """
        Check service health

        Returns:
            Health status object
        """
        checks = {
            "initialized": self._initialized,
            "circuit_closed": self.circuit_breaker.is_closed,
            "rate_limit_ok": self.rate_limiter.get_remaining_requests() > 0
        }

        # Run implementation-specific health check
        try:
            checks["api_connection"] = await self._health_check_impl()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            checks["api_connection"] = False

        # Determine overall status
        if all(checks.values()):
            status = "healthy"
        elif checks.get("api_connection") and checks.get("initialized"):
            status = "degraded"
        else:
            status = "unhealthy"

        return ServiceHealth(
            status=status,
            service=self.service_name,
            version=self.version,
            uptime=time.time() - self.metrics.start_time,
            checks=checks,
            metrics=self.metrics.to_dict()
        )

    async def close(self):
        """Close service connections"""
        await self.cache.close()
        logger.info(f"{self.service_name} closed")


def create_service_app(
    service: BaseIntegrationService,
    title: str = None,
    description: str = None
) -> FastAPI:
    """
    Create a FastAPI app for an integration service

    Args:
        service: The integration service instance
        title: API title
        description: API description

    Returns:
        FastAPI application
    """
    app = FastAPI(
        title=title or f"{service.service_name} API",
        description=description or f"Integration service for {service.service_name}",
        version=service.version
    )

    @app.on_event("startup")
    async def startup():
        await service.initialize()

    @app.on_event("shutdown")
    async def shutdown():
        await service.close()

    @app.get("/health")
    async def health():
        return await service.health_check()

    @app.get("/health/detailed")
    async def health_detailed():
        health = await service.health_check()
        return {
            **health.dict(),
            "cache_stats": service.cache.stats(),
            "circuit_breaker": service.circuit_breaker.get_status()
        }

    @app.post("/search", response_model=List[SearchResult])
    async def search(query: SearchQuery):
        return await service.search(query)

    @app.get("/metrics")
    async def metrics():
        return service.metrics.to_dict()

    return app
