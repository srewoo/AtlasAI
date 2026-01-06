"""
Developer Tools Integration Service
Search Stack Overflow, npm, PyPI, and documentation
"""
import os
import logging
from typing import List, Dict, Any, Optional
import re

from ..base import (
    BaseIntegrationService,
    SearchResult,
    RateLimitConfig,
    CircuitBreakerConfig,
    ChunkConfig,
    create_service_app
)

logger = logging.getLogger(__name__)


class DevToolsService(BaseIntegrationService):
    """
    Developer Tools integration for searching code resources

    Features:
    - Stack Overflow: Questions and answers
    - npm: Package search and documentation
    - PyPI: Python package search
    - MDN: Web documentation
    - DevDocs: Multiple documentation sources
    """

    def __init__(
        self,
        stackoverflow_key: Optional[str] = None,
        redis_url: str = "redis://localhost:6379"
    ):
        super().__init__(
            service_name="devtools",
            version="1.0.0",
            rate_limit_config=RateLimitConfig(
                requests_per_window=300,  # Combined limit
                window_seconds=60,
                burst_size=30
            ),
            circuit_config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout=30
            ),
            chunk_config=ChunkConfig(
                max_chunk_size=1024,
                chunk_overlap=100
            ),
            redis_url=redis_url
        )
        self.stackoverflow_key = stackoverflow_key or os.getenv("STACKOVERFLOW_KEY")

    async def _init_client(self):
        """Initialize HTTP client"""
        try:
            import httpx
            self._api_client = httpx.AsyncClient(timeout=30.0)
            logger.info("DevTools client initialized")
        except ImportError:
            logger.error("httpx not installed. Run: pip install httpx")
            raise

    async def _health_check_impl(self) -> bool:
        """Check API connections"""
        if not self._api_client:
            return False
        try:
            # Test Stack Overflow API
            response = await self._api_client.get(
                "https://api.stackexchange.com/2.3/info",
                params={"site": "stackoverflow"}
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"DevTools health check failed: {e}")
            return False

    async def _search_impl(self, query: str, limit: int, **kwargs) -> List[Dict]:
        """Search across developer resources"""
        search_type = kwargs.get("search_type", "all")
        results = []

        if search_type in ["all", "stackoverflow"]:
            so_results = await self.search_stackoverflow(query, limit)
            results.extend(so_results)

        if search_type in ["all", "npm"]:
            npm_results = await self.search_npm(query, limit // 2)
            results.extend(npm_results)

        if search_type in ["all", "pypi"]:
            pypi_results = await self.search_pypi(query, limit // 2)
            results.extend(pypi_results)

        return results[:limit]

    async def search_stackoverflow(self, query: str, limit: int = 10) -> List[Dict]:
        """Search Stack Overflow questions"""
        if not self._api_client:
            return []

        try:
            params = {
                "order": "desc",
                "sort": "relevance",
                "intitle": query,
                "site": "stackoverflow",
                "pagesize": limit,
                "filter": "withbody"
            }

            if self.stackoverflow_key:
                params["key"] = self.stackoverflow_key

            response = await self._api_client.get(
                "https://api.stackexchange.com/2.3/search/advanced",
                params=params
            )

            if response.status_code != 200:
                logger.error(f"Stack Overflow error: {response.text}")
                return []

            data = response.json()
            items = data.get("items", [])

            results = []
            for item in items[:limit]:
                # Strip HTML from body
                body = item.get("body", "")
                body_text = re.sub(r'<[^>]+>', '', body)[:500]

                tags = item.get("tags", [])

                results.append({
                    "id": str(item.get("question_id", "")),
                    "title": item.get("title", ""),
                    "content": f"{item.get('title', '')}\n\n{body_text}",
                    "url": item.get("link", ""),
                    "source": "devtools",
                    "metadata": {
                        "type": "stackoverflow",
                        "score": item.get("score", 0),
                        "answer_count": item.get("answer_count", 0),
                        "is_answered": item.get("is_answered", False),
                        "tags": tags,
                        "view_count": item.get("view_count", 0),
                        "created": item.get("creation_date")
                    },
                    "score": item.get("score", 0)
                })

            return results

        except Exception as e:
            logger.error(f"Stack Overflow search error: {e}")
            return []

    async def search_npm(self, query: str, limit: int = 10) -> List[Dict]:
        """Search npm packages"""
        if not self._api_client:
            return []

        try:
            response = await self._api_client.get(
                "https://registry.npmjs.org/-/v1/search",
                params={
                    "text": query,
                    "size": limit
                }
            )

            if response.status_code != 200:
                logger.error(f"npm search error: {response.text}")
                return []

            data = response.json()
            packages = data.get("objects", [])

            results = []
            for pkg in packages[:limit]:
                package = pkg.get("package", {})
                name = package.get("name", "")

                results.append({
                    "id": name,
                    "title": f"npm: {name}",
                    "content": f"{name}\n\n{package.get('description', '')}\n\nKeywords: {', '.join(package.get('keywords', []))}",
                    "url": f"https://www.npmjs.com/package/{name}",
                    "source": "devtools",
                    "metadata": {
                        "type": "npm",
                        "version": package.get("version"),
                        "author": package.get("author", {}).get("name") if isinstance(package.get("author"), dict) else package.get("author"),
                        "keywords": package.get("keywords", []),
                        "score": pkg.get("score", {}).get("final", 0)
                    },
                    "score": pkg.get("score", {}).get("final", 0) * 100
                })

            return results

        except Exception as e:
            logger.error(f"npm search error: {e}")
            return []

    async def search_pypi(self, query: str, limit: int = 10) -> List[Dict]:
        """Search PyPI packages"""
        if not self._api_client:
            return []

        try:
            # PyPI uses a simple search endpoint
            response = await self._api_client.get(
                f"https://pypi.org/pypi/{query}/json"
            )

            results = []

            # If exact match found
            if response.status_code == 200:
                data = response.json()
                info = data.get("info", {})

                results.append({
                    "id": info.get("name", ""),
                    "title": f"PyPI: {info.get('name', '')}",
                    "content": f"{info.get('name', '')}\n\n{info.get('summary', '')}",
                    "url": info.get("project_url") or f"https://pypi.org/project/{info.get('name', '')}",
                    "source": "devtools",
                    "metadata": {
                        "type": "pypi",
                        "version": info.get("version"),
                        "author": info.get("author"),
                        "license": info.get("license"),
                        "requires_python": info.get("requires_python")
                    }
                })

            # Also search using simple API for related packages
            search_response = await self._api_client.get(
                "https://pypi.org/simple/",
                headers={"Accept": "application/vnd.pypi.simple.v1+json"}
            )

            if search_response.status_code == 200:
                simple_data = search_response.json()
                projects = simple_data.get("projects", [])

                # Filter by query
                matching = [
                    p for p in projects
                    if query.lower() in p.get("name", "").lower()
                ][:limit]

                for proj in matching:
                    name = proj.get("name", "")
                    if not any(r.get("id") == name for r in results):
                        results.append({
                            "id": name,
                            "title": f"PyPI: {name}",
                            "content": f"Python package: {name}",
                            "url": f"https://pypi.org/project/{name}/",
                            "source": "devtools",
                            "metadata": {
                                "type": "pypi"
                            }
                        })

            return results[:limit]

        except Exception as e:
            logger.error(f"PyPI search error: {e}")
            return []

    async def get_package_readme(self, package_name: str, registry: str = "npm") -> Optional[Dict]:
        """Get package README/documentation"""
        if not self._api_client:
            return None

        try:
            if registry == "npm":
                response = await self._api_client.get(
                    f"https://registry.npmjs.org/{package_name}"
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "id": package_name,
                        "title": f"npm: {package_name}",
                        "content": data.get("readme", "No README available"),
                        "url": f"https://www.npmjs.com/package/{package_name}",
                        "source": "devtools",
                        "metadata": {
                            "type": "npm_readme",
                            "version": data.get("dist-tags", {}).get("latest")
                        }
                    }

            elif registry == "pypi":
                response = await self._api_client.get(
                    f"https://pypi.org/pypi/{package_name}/json"
                )

                if response.status_code == 200:
                    data = response.json()
                    info = data.get("info", {})
                    return {
                        "id": package_name,
                        "title": f"PyPI: {package_name}",
                        "content": info.get("description", "No description available"),
                        "url": f"https://pypi.org/project/{package_name}/",
                        "source": "devtools",
                        "metadata": {
                            "type": "pypi_readme",
                            "version": info.get("version")
                        }
                    }

        except Exception as e:
            logger.error(f"Get README error: {e}")

        return None

    async def search_mdn(self, query: str, limit: int = 10) -> List[Dict]:
        """Search MDN Web Docs"""
        if not self._api_client:
            return []

        try:
            response = await self._api_client.get(
                "https://developer.mozilla.org/api/v1/search",
                params={
                    "q": query,
                    "locale": "en-US",
                    "size": limit
                }
            )

            if response.status_code != 200:
                logger.error(f"MDN search error: {response.text}")
                return []

            data = response.json()
            documents = data.get("documents", [])

            results = []
            for doc in documents[:limit]:
                results.append({
                    "id": doc.get("mdn_url", ""),
                    "title": doc.get("title", ""),
                    "content": doc.get("summary", ""),
                    "url": f"https://developer.mozilla.org{doc.get('mdn_url', '')}",
                    "source": "devtools",
                    "metadata": {
                        "type": "mdn",
                        "locale": doc.get("locale"),
                        "score": doc.get("score", 0)
                    },
                    "score": doc.get("score", 0)
                })

            return results

        except Exception as e:
            logger.error(f"MDN search error: {e}")
            return []

    async def get_stackoverflow_answers(self, question_id: str) -> List[Dict]:
        """Get answers for a Stack Overflow question"""
        if not self._api_client:
            return []

        try:
            params = {
                "order": "desc",
                "sort": "votes",
                "site": "stackoverflow",
                "filter": "withbody"
            }

            if self.stackoverflow_key:
                params["key"] = self.stackoverflow_key

            response = await self._api_client.get(
                f"https://api.stackexchange.com/2.3/questions/{question_id}/answers",
                params=params
            )

            if response.status_code != 200:
                return []

            data = response.json()
            answers = data.get("items", [])

            results = []
            for answer in answers:
                body = answer.get("body", "")
                body_text = re.sub(r'<[^>]+>', '', body)

                results.append({
                    "id": str(answer.get("answer_id", "")),
                    "title": f"Answer (Score: {answer.get('score', 0)})",
                    "content": body_text[:1000],
                    "url": f"https://stackoverflow.com/a/{answer.get('answer_id')}",
                    "source": "devtools",
                    "metadata": {
                        "type": "stackoverflow_answer",
                        "score": answer.get("score", 0),
                        "is_accepted": answer.get("is_accepted", False),
                        "question_id": question_id
                    }
                })

            return results

        except Exception as e:
            logger.error(f"Get answers error: {e}")
            return []

    async def close(self):
        """Close HTTP client"""
        if self._api_client:
            await self._api_client.aclose()
        await super().close()


# Create FastAPI app
def create_app() -> "FastAPI":
    service = DevToolsService()
    app = create_service_app(
        service,
        title="Developer Tools Integration Service",
        description="Search Stack Overflow, npm, PyPI, and MDN"
    )

    # Add custom endpoints
    @app.get("/stackoverflow")
    async def search_stackoverflow(query: str, limit: int = 10):
        return await service.search_stackoverflow(query, limit)

    @app.get("/stackoverflow/{question_id}/answers")
    async def get_answers(question_id: str):
        return await service.get_stackoverflow_answers(question_id)

    @app.get("/npm")
    async def search_npm(query: str, limit: int = 10):
        return await service.search_npm(query, limit)

    @app.get("/pypi")
    async def search_pypi(query: str, limit: int = 10):
        return await service.search_pypi(query, limit)

    @app.get("/mdn")
    async def search_mdn(query: str, limit: int = 10):
        return await service.search_mdn(query, limit)

    @app.get("/package/{registry}/{package_name}")
    async def get_package(registry: str, package_name: str):
        return await service.get_package_readme(package_name, registry)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8025)
