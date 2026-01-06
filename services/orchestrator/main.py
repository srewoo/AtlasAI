"""
Orchestrator Service
Coordinates parallel queries across all integration services
Handles streaming aggregation and result ranking
"""
import asyncio
import time
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceConfig:
    """Configuration for an integration service"""
    name: str
    url: str
    enabled: bool = True
    priority: int = 1  # Lower = higher priority
    timeout: float = 10.0
    keywords: List[str] = field(default_factory=list)


class OrchestratorQuery(BaseModel):
    """Query model for orchestrator"""
    query: str
    limit: int = 10
    services: Optional[List[str]] = None  # None = all enabled services
    parallel: bool = True
    include_metadata: bool = True


class SearchResult(BaseModel):
    """Standard search result"""
    id: str
    title: str
    content: str
    url: Optional[str] = None
    source: str
    score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class OrchestratorResponse(BaseModel):
    """Response from orchestrator"""
    results: List[SearchResult]
    sources_queried: List[str]
    sources_responded: List[str]
    total_time_ms: float
    per_service_time: Dict[str, float]


# Default service configurations
DEFAULT_SERVICES = [
    ServiceConfig(
        name="confluence",
        url="http://localhost:8015",
        keywords=["document", "wiki", "page", "documentation", "guide", "article"],
        priority=1
    ),
    ServiceConfig(
        name="jira",
        url="http://localhost:8016",
        keywords=["issue", "ticket", "bug", "task", "story", "epic", "sprint"],
        priority=1
    ),
    ServiceConfig(
        name="slack",
        url="http://localhost:8010",
        keywords=["message", "chat", "channel", "discussion", "conversation"],
        priority=2
    ),
    ServiceConfig(
        name="github",
        url="http://localhost:8011",
        keywords=["code", "repository", "commit", "pr", "pull request", "branch"],
        priority=2
    ),
    ServiceConfig(
        name="google",
        url="http://localhost:8012",
        keywords=["drive", "doc", "sheet", "email", "calendar", "meeting"],
        priority=2
    ),
    ServiceConfig(
        name="notion",
        url="http://localhost:8013",
        keywords=["page", "database", "note", "wiki"],
        priority=2
    ),
    ServiceConfig(
        name="linear",
        url="http://localhost:8017",
        keywords=["issue", "project", "cycle", "roadmap"],
        priority=3
    ),
    ServiceConfig(
        name="figma",
        url="http://localhost:8018",
        keywords=["design", "prototype", "component", "frame", "ui", "ux", "mockup"],
        priority=3
    ),
    ServiceConfig(
        name="microsoft365",
        url="http://localhost:8019",
        keywords=["teams", "sharepoint", "outlook", "onedrive", "office", "microsoft", "excel", "word", "powerpoint"],
        priority=2
    ),
    ServiceConfig(
        name="devtools",
        url="http://localhost:8025",
        keywords=["stackoverflow", "npm", "pypi", "package", "library", "mdn", "documentation", "how to", "error", "exception"],
        priority=3
    ),
    ServiceConfig(
        name="productivity",
        url="http://localhost:8026",
        keywords=["file", "local", "document", "notes", "bookmark", "clipboard", "recent"],
        priority=4
    ),
]


class Orchestrator:
    """
    Main orchestrator class that coordinates queries across services
    """

    def __init__(
        self,
        services: Optional[List[ServiceConfig]] = None,
        max_parallel: int = 10,
        default_timeout: float = 15.0
    ):
        self.services = {s.name: s for s in (services or DEFAULT_SERVICES)}
        self.max_parallel = max_parallel
        self.default_timeout = default_timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._service_status: Dict[str, ServiceStatus] = {}

    async def initialize(self):
        """Initialize the orchestrator"""
        self._client = httpx.AsyncClient(timeout=self.default_timeout)
        await self._check_services_health()
        logger.info(f"Orchestrator initialized with {len(self.services)} services")

    async def close(self):
        """Close the orchestrator"""
        if self._client:
            await self._client.aclose()

    async def _check_services_health(self):
        """Check health of all services"""
        tasks = []
        for name, config in self.services.items():
            if config.enabled:
                tasks.append(self._check_service_health(name, config))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_service_health(self, name: str, config: ServiceConfig):
        """Check health of a single service"""
        try:
            response = await self._client.get(f"{config.url}/health", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                self._service_status[name] = ServiceStatus(status)
            else:
                self._service_status[name] = ServiceStatus.UNHEALTHY
        except Exception as e:
            logger.debug(f"Service {name} health check failed: {e}")
            self._service_status[name] = ServiceStatus.UNKNOWN

    def _determine_services(self, query: str, requested_services: Optional[List[str]] = None) -> List[str]:
        """
        Determine which services to query based on the query content

        Args:
            query: Search query
            requested_services: Explicitly requested services (overrides auto-detection)

        Returns:
            List of service names to query
        """
        if requested_services:
            return [s for s in requested_services if s in self.services and self.services[s].enabled]

        query_lower = query.lower()
        matched_services = []
        fallback_services = []

        for name, config in self.services.items():
            if not config.enabled:
                continue

            # Check if query contains service-specific keywords
            if any(kw in query_lower for kw in config.keywords):
                matched_services.append((config.priority, name))
            else:
                fallback_services.append((config.priority, name))

        # Sort by priority and return
        if matched_services:
            matched_services.sort(key=lambda x: x[0])
            return [name for _, name in matched_services]

        # If no keywords matched, return high-priority services
        fallback_services.sort(key=lambda x: x[0])
        return [name for _, name in fallback_services[:5]]  # Top 5 services

    async def _query_service(
        self,
        name: str,
        config: ServiceConfig,
        query: str,
        limit: int
    ) -> tuple[str, List[Dict], float]:
        """
        Query a single service

        Returns:
            Tuple of (service_name, results, time_ms)
        """
        start_time = time.time()

        try:
            response = await self._client.post(
                f"{config.url}/search",
                json={"query": query, "limit": limit},
                timeout=config.timeout
            )

            elapsed = (time.time() - start_time) * 1000

            if response.status_code == 200:
                results = response.json()
                # Ensure each result has the source field
                for r in results:
                    if 'source' not in r:
                        r['source'] = name
                return (name, results, elapsed)
            else:
                logger.warning(f"Service {name} returned {response.status_code}")
                return (name, [], elapsed)

        except asyncio.TimeoutError:
            elapsed = (time.time() - start_time) * 1000
            logger.warning(f"Service {name} timed out after {elapsed:.0f}ms")
            return (name, [], elapsed)

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"Service {name} error: {e}")
            return (name, [], elapsed)

    async def search(self, request: OrchestratorQuery) -> OrchestratorResponse:
        """
        Execute search across multiple services

        Args:
            request: Search request

        Returns:
            Aggregated search response
        """
        start_time = time.time()

        # Determine which services to query
        services_to_query = self._determine_services(request.query, request.services)
        logger.info(f"Querying services: {services_to_query}")

        # Query services in parallel
        if request.parallel:
            tasks = []
            for name in services_to_query:
                config = self.services[name]
                tasks.append(self._query_service(name, config, request.query, request.limit))

            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            # Sequential queries
            results = []
            for name in services_to_query:
                config = self.services[name]
                result = await self._query_service(name, config, request.query, request.limit)
                results.append(result)

        # Aggregate results
        all_results = []
        sources_responded = []
        per_service_time = {}

        for result in results:
            if isinstance(result, Exception):
                continue

            name, items, elapsed = result
            per_service_time[name] = elapsed

            if items:
                sources_responded.append(name)
                all_results.extend(items)

        # Rank and deduplicate results
        ranked_results = self._rank_results(all_results, request.query)

        total_time = (time.time() - start_time) * 1000

        return OrchestratorResponse(
            results=[SearchResult(**r) for r in ranked_results[:request.limit]],
            sources_queried=services_to_query,
            sources_responded=sources_responded,
            total_time_ms=total_time,
            per_service_time=per_service_time
        )

    def _rank_results(self, results: List[Dict], query: str) -> List[Dict]:
        """
        Rank and deduplicate results

        Simple scoring based on:
        - Title match
        - Content match
        - Source priority
        """
        query_terms = set(query.lower().split())
        scored_results = []

        seen_ids = set()

        for result in results:
            # Deduplicate by ID
            result_id = f"{result.get('source')}:{result.get('id')}"
            if result_id in seen_ids:
                continue
            seen_ids.add(result_id)

            # Calculate score
            score = 0.0

            title = result.get('title', '').lower()
            content = result.get('content', '').lower()

            # Title matches are worth more
            for term in query_terms:
                if term in title:
                    score += 2.0
                if term in content:
                    score += 1.0

            # Source priority bonus
            source = result.get('source', '')
            if source in self.services:
                priority = self.services[source].priority
                score += (5 - priority)  # Higher priority = higher score

            result['score'] = score
            scored_results.append(result)

        # Sort by score descending
        scored_results.sort(key=lambda x: x.get('score', 0), reverse=True)

        return scored_results

    async def stream_search(self, request: OrchestratorQuery) -> AsyncGenerator[str, None]:
        """
        Stream search results as they arrive from services

        Yields:
            SSE formatted events
        """
        yield f"data: {json.dumps({'type': 'start', 'services': list(self._determine_services(request.query, request.services))})}\n\n"

        services_to_query = self._determine_services(request.query, request.services)

        # Create tasks for all services
        tasks = {}
        for name in services_to_query:
            config = self.services[name]
            task = asyncio.create_task(
                self._query_service(name, config, request.query, request.limit)
            )
            tasks[task] = name

        # Stream results as they complete
        all_results = []
        for task in asyncio.as_completed(tasks.keys()):
            try:
                name, results, elapsed = await task

                if results:
                    all_results.extend(results)

                    yield f"data: {json.dumps({'type': 'results', 'source': name, 'count': len(results), 'time_ms': elapsed, 'results': results[:3]})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'no_results', 'source': name, 'time_ms': elapsed})}\n\n"

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'source': tasks.get(task, 'unknown'), 'message': str(e)})}\n\n"

        # Send final ranked results
        ranked = self._rank_results(all_results, request.query)
        yield f"data: {json.dumps({'type': 'done', 'total_results': len(ranked), 'top_results': ranked[:request.limit]})}\n\n"

    def get_services_status(self) -> Dict[str, Any]:
        """Get status of all services"""
        return {
            name: {
                "enabled": config.enabled,
                "url": config.url,
                "status": self._service_status.get(name, ServiceStatus.UNKNOWN).value,
                "priority": config.priority
            }
            for name, config in self.services.items()
        }


# Create FastAPI app
app = FastAPI(
    title="Atlas AI Orchestrator",
    description="Coordinates queries across all integration services",
    version="1.0.0"
)

orchestrator = Orchestrator()


@app.on_event("startup")
async def startup():
    await orchestrator.initialize()


@app.on_event("shutdown")
async def shutdown():
    await orchestrator.close()


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "services": orchestrator.get_services_status()
    }


@app.post("/search", response_model=OrchestratorResponse)
async def search(request: OrchestratorQuery):
    """Search across all configured services"""
    return await orchestrator.search(request)


@app.post("/search/stream")
async def search_stream(request: OrchestratorQuery):
    """Stream search results as they arrive"""
    return StreamingResponse(
        orchestrator.stream_search(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/services")
async def list_services():
    """List all configured services and their status"""
    return orchestrator.get_services_status()


@app.post("/services/{service_name}/enable")
async def enable_service(service_name: str):
    """Enable a service"""
    if service_name in orchestrator.services:
        orchestrator.services[service_name].enabled = True
        return {"status": "enabled", "service": service_name}
    raise HTTPException(404, f"Service {service_name} not found")


@app.post("/services/{service_name}/disable")
async def disable_service(service_name: str):
    """Disable a service"""
    if service_name in orchestrator.services:
        orchestrator.services[service_name].enabled = False
        return {"status": "disabled", "service": service_name}
    raise HTTPException(404, f"Service {service_name} not found")


@app.post("/services/refresh")
async def refresh_services():
    """Refresh service health status"""
    await orchestrator._check_services_health()
    return orchestrator.get_services_status()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
