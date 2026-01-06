"""
GitHub Integration Service
Search code, issues, PRs, wikis, and discussions
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


class GitHubService(BaseIntegrationService):
    """
    GitHub integration for searching code and issues

    Features:
    - Search code across repositories
    - Search issues and PRs
    - Search repositories
    - Get file contents
    - Search commits
    """

    def __init__(
        self,
        token: Optional[str] = None,
        redis_url: str = "redis://localhost:6379"
    ):
        super().__init__(
            service_name="github",
            version="1.0.0",
            rate_limit_config=RateLimitConfig(
                requests_per_window=5000,  # GitHub API limit
                window_seconds=3600,
                burst_size=30
            ),
            circuit_config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout=60
            ),
            chunk_config=ChunkConfig(
                max_chunk_size=1024,
                chunk_overlap=100
            ),
            redis_url=redis_url
        )
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"

    async def _init_client(self):
        """Initialize GitHub client"""
        try:
            import httpx
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Atlas-AI-Integration"
            }
            if self.token:
                headers["Authorization"] = f"token {self.token}"

            self._api_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0
            )
            logger.info("GitHub client initialized")
        except ImportError:
            logger.error("httpx not installed. Run: pip install httpx")
            raise

    async def _health_check_impl(self) -> bool:
        """Check GitHub API connection"""
        if not self._api_client:
            return False
        try:
            response = await self._api_client.get("/rate_limit")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"GitHub health check failed: {e}")
            return False

    async def _search_impl(self, query: str, limit: int, **kwargs) -> List[Dict]:
        """Search GitHub - defaults to combined search"""
        search_type = kwargs.get("search_type", "all")

        results = []

        if search_type in ["all", "code"]:
            code_results = await self.search_code(query, limit)
            results.extend(code_results)

        if search_type in ["all", "issues"]:
            issue_results = await self.search_issues(query, limit)
            results.extend(issue_results)

        if search_type in ["all", "repos"]:
            repo_results = await self.search_repos(query, limit // 2)
            results.extend(repo_results)

        return results[:limit]

    async def search_code(self, query: str, limit: int = 10) -> List[Dict]:
        """Search code across GitHub"""
        if not self._api_client:
            return []

        try:
            response = await self._api_client.get(
                "/search/code",
                params={"q": query, "per_page": limit}
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])

                results = []
                for item in items[:limit]:
                    repo = item.get("repository", {})
                    results.append({
                        "id": item.get("sha", ""),
                        "title": f"{repo.get('full_name')}/{item.get('path')}",
                        "content": f"File: {item.get('name')}\nPath: {item.get('path')}\nRepository: {repo.get('full_name')}",
                        "url": item.get("html_url"),
                        "source": "github",
                        "metadata": {
                            "type": "code",
                            "repo": repo.get("full_name"),
                            "path": item.get("path"),
                            "filename": item.get("name")
                        }
                    })

                return results

        except Exception as e:
            logger.error(f"GitHub code search error: {e}")

        return []

    async def search_issues(self, query: str, limit: int = 10) -> List[Dict]:
        """Search issues and PRs"""
        if not self._api_client:
            return []

        try:
            response = await self._api_client.get(
                "/search/issues",
                params={"q": query, "per_page": limit, "sort": "updated"}
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])

                results = []
                for item in items[:limit]:
                    # Extract repo from URL
                    repo_url = item.get("repository_url", "")
                    repo_name = "/".join(repo_url.split("/")[-2:]) if repo_url else ""

                    issue_type = "PR" if "pull_request" in item else "Issue"

                    results.append({
                        "id": str(item.get("id", "")),
                        "title": f"[{issue_type}] {item.get('title')}",
                        "content": f"{item.get('title')}\n\n{item.get('body', '')[:500]}",
                        "url": item.get("html_url"),
                        "source": "github",
                        "metadata": {
                            "type": issue_type.lower(),
                            "repo": repo_name,
                            "number": item.get("number"),
                            "state": item.get("state"),
                            "author": item.get("user", {}).get("login"),
                            "labels": [l.get("name") for l in item.get("labels", [])],
                            "created_at": item.get("created_at"),
                            "updated_at": item.get("updated_at")
                        }
                    })

                return results

        except Exception as e:
            logger.error(f"GitHub issues search error: {e}")

        return []

    async def search_repos(self, query: str, limit: int = 10) -> List[Dict]:
        """Search repositories"""
        if not self._api_client:
            return []

        try:
            response = await self._api_client.get(
                "/search/repositories",
                params={"q": query, "per_page": limit, "sort": "stars"}
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])

                results = []
                for item in items[:limit]:
                    results.append({
                        "id": str(item.get("id", "")),
                        "title": item.get("full_name"),
                        "content": item.get("description", "") or "No description",
                        "url": item.get("html_url"),
                        "source": "github",
                        "metadata": {
                            "type": "repository",
                            "stars": item.get("stargazers_count", 0),
                            "forks": item.get("forks_count", 0),
                            "language": item.get("language"),
                            "topics": item.get("topics", []),
                            "updated_at": item.get("updated_at")
                        }
                    })

                return results

        except Exception as e:
            logger.error(f"GitHub repos search error: {e}")

        return []

    async def get_file_content(self, owner: str, repo: str, path: str) -> Optional[Dict]:
        """Get file content from a repository"""
        if not self._api_client:
            return None

        try:
            response = await self._api_client.get(
                f"/repos/{owner}/{repo}/contents/{path}"
            )

            if response.status_code == 200:
                data = response.json()
                import base64

                content = ""
                if data.get("encoding") == "base64":
                    content = base64.b64decode(data.get("content", "")).decode("utf-8")
                else:
                    content = data.get("content", "")

                return {
                    "id": data.get("sha"),
                    "title": data.get("name"),
                    "content": content,
                    "url": data.get("html_url"),
                    "source": "github",
                    "metadata": {
                        "type": "file_content",
                        "path": path,
                        "size": data.get("size")
                    }
                }

        except Exception as e:
            logger.error(f"GitHub file content error: {e}")

        return None

    async def search_commits(self, query: str, limit: int = 10) -> List[Dict]:
        """Search commits"""
        if not self._api_client:
            return []

        try:
            response = await self._api_client.get(
                "/search/commits",
                params={"q": query, "per_page": limit},
                headers={"Accept": "application/vnd.github.cloak-preview+json"}
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])

                results = []
                for item in items[:limit]:
                    commit = item.get("commit", {})
                    repo = item.get("repository", {})

                    results.append({
                        "id": item.get("sha", ""),
                        "title": commit.get("message", "").split("\n")[0][:100],
                        "content": commit.get("message", ""),
                        "url": item.get("html_url"),
                        "source": "github",
                        "metadata": {
                            "type": "commit",
                            "repo": repo.get("full_name"),
                            "author": commit.get("author", {}).get("name"),
                            "date": commit.get("author", {}).get("date")
                        }
                    })

                return results

        except Exception as e:
            logger.error(f"GitHub commits search error: {e}")

        return []

    async def close(self):
        """Close HTTP client"""
        if self._api_client:
            await self._api_client.aclose()
        await super().close()


# Create FastAPI app
def create_app() -> "FastAPI":
    service = GitHubService()
    app = create_service_app(
        service,
        title="GitHub Integration Service",
        description="Search GitHub code, issues, PRs, and repositories"
    )

    # Add custom endpoints
    @app.get("/code")
    async def search_code(query: str, limit: int = 10):
        return await service.search_code(query, limit)

    @app.get("/issues")
    async def search_issues(query: str, limit: int = 10):
        return await service.search_issues(query, limit)

    @app.get("/repos")
    async def search_repos(query: str, limit: int = 10):
        return await service.search_repos(query, limit)

    @app.get("/commits")
    async def search_commits(query: str, limit: int = 10):
        return await service.search_commits(query, limit)

    @app.get("/file/{owner}/{repo}/{path:path}")
    async def get_file(owner: str, repo: str, path: str):
        return await service.get_file_content(owner, repo, path)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)
