"""
Linear Integration Service
Search issues, projects, and roadmaps
"""
import os
import logging
from typing import List, Dict, Any, Optional

from ..base import (
    BaseIntegrationService,
    SearchResult,
    RateLimitConfig,
    CircuitBreakerConfig,
    ChunkConfig,
    create_service_app
)

logger = logging.getLogger(__name__)


GRAPHQL_ENDPOINT = "https://api.linear.app/graphql"


class LinearService(BaseIntegrationService):
    """
    Linear integration for searching issues and projects

    Features:
    - Search issues
    - Search projects
    - Get issue details
    - Get project roadmap
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        redis_url: str = "redis://localhost:6379"
    ):
        super().__init__(
            service_name="linear",
            version="1.0.0",
            rate_limit_config=RateLimitConfig(
                requests_per_window=1500,
                window_seconds=3600,
                burst_size=50
            ),
            circuit_config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout=60
            ),
            chunk_config=ChunkConfig(
                max_chunk_size=512,
                chunk_overlap=50
            ),
            redis_url=redis_url
        )
        self.api_key = api_key or os.getenv("LINEAR_API_KEY")

    async def _init_client(self):
        """Initialize Linear client"""
        if not self.api_key:
            logger.warning("Linear API key not configured")
            return

        try:
            import httpx
            self._api_client = httpx.AsyncClient(
                headers={
                    "Authorization": self.api_key,
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            logger.info("Linear client initialized")
        except ImportError:
            logger.error("httpx not installed. Run: pip install httpx")
            raise

    async def _health_check_impl(self) -> bool:
        """Check Linear API connection"""
        if not self._api_client:
            return False
        try:
            query = """
                query {
                    viewer {
                        id
                    }
                }
            """
            response = await self._api_client.post(
                GRAPHQL_ENDPOINT,
                json={"query": query}
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Linear health check failed: {e}")
            return False

    async def _search_impl(self, query: str, limit: int, **kwargs) -> List[Dict]:
        """Search Linear issues"""
        if not self._api_client:
            return []

        graphql_query = """
            query SearchIssues($query: String!, $first: Int!) {
                issueSearch(query: $query, first: $first) {
                    nodes {
                        id
                        identifier
                        title
                        description
                        url
                        state {
                            name
                            color
                        }
                        priority
                        priorityLabel
                        assignee {
                            name
                            email
                        }
                        team {
                            name
                            key
                        }
                        project {
                            name
                        }
                        labels {
                            nodes {
                                name
                                color
                            }
                        }
                        createdAt
                        updatedAt
                    }
                }
            }
        """

        try:
            response = await self._api_client.post(
                GRAPHQL_ENDPOINT,
                json={
                    "query": graphql_query,
                    "variables": {"query": query, "first": limit}
                }
            )

            if response.status_code != 200:
                logger.error(f"Linear search failed: {response.text}")
                return []

            data = response.json()
            issues = data.get("data", {}).get("issueSearch", {}).get("nodes", [])

            results = []
            for issue in issues:
                state = issue.get("state", {})
                assignee = issue.get("assignee", {})
                team = issue.get("team", {})
                labels = [l.get("name") for l in issue.get("labels", {}).get("nodes", [])]

                results.append({
                    "id": issue.get("id"),
                    "title": f"[{issue.get('identifier')}] {issue.get('title')}",
                    "content": f"{issue.get('title')}\n\n{issue.get('description', '')[:500]}",
                    "url": issue.get("url"),
                    "source": "linear",
                    "metadata": {
                        "type": "issue",
                        "identifier": issue.get("identifier"),
                        "state": state.get("name"),
                        "priority": issue.get("priorityLabel"),
                        "assignee": assignee.get("name") if assignee else None,
                        "team": team.get("name") if team else None,
                        "project": issue.get("project", {}).get("name") if issue.get("project") else None,
                        "labels": labels,
                        "created_at": issue.get("createdAt"),
                        "updated_at": issue.get("updatedAt")
                    }
                })

            return results

        except Exception as e:
            logger.error(f"Linear search error: {e}")
            return []

    async def get_issue(self, issue_id: str) -> Optional[Dict]:
        """Get a specific issue by ID or identifier"""
        if not self._api_client:
            return None

        graphql_query = """
            query GetIssue($id: String!) {
                issue(id: $id) {
                    id
                    identifier
                    title
                    description
                    url
                    state {
                        name
                    }
                    priority
                    priorityLabel
                    assignee {
                        name
                    }
                    comments {
                        nodes {
                            body
                            user {
                                name
                            }
                            createdAt
                        }
                    }
                }
            }
        """

        try:
            response = await self._api_client.post(
                GRAPHQL_ENDPOINT,
                json={
                    "query": graphql_query,
                    "variables": {"id": issue_id}
                }
            )

            if response.status_code != 200:
                return None

            data = response.json()
            issue = data.get("data", {}).get("issue")

            if not issue:
                return None

            comments = issue.get("comments", {}).get("nodes", [])
            comment_text = "\n".join([
                f"- {c.get('user', {}).get('name', 'Unknown')}: {c.get('body', '')[:200]}"
                for c in comments[:5]
            ])

            return {
                "id": issue.get("id"),
                "title": f"[{issue.get('identifier')}] {issue.get('title')}",
                "content": f"{issue.get('description', '')}\n\nComments:\n{comment_text}",
                "url": issue.get("url"),
                "source": "linear",
                "metadata": {
                    "type": "issue",
                    "identifier": issue.get("identifier"),
                    "state": issue.get("state", {}).get("name"),
                    "priority": issue.get("priorityLabel"),
                    "assignee": issue.get("assignee", {}).get("name") if issue.get("assignee") else None
                }
            }

        except Exception as e:
            logger.error(f"Linear get issue error: {e}")
            return None

    async def get_projects(self, limit: int = 20) -> List[Dict]:
        """Get all projects"""
        if not self._api_client:
            return []

        graphql_query = """
            query GetProjects($first: Int!) {
                projects(first: $first) {
                    nodes {
                        id
                        name
                        description
                        url
                        state
                        progress
                        targetDate
                        teams {
                            nodes {
                                name
                            }
                        }
                    }
                }
            }
        """

        try:
            response = await self._api_client.post(
                GRAPHQL_ENDPOINT,
                json={
                    "query": graphql_query,
                    "variables": {"first": limit}
                }
            )

            if response.status_code != 200:
                return []

            data = response.json()
            projects = data.get("data", {}).get("projects", {}).get("nodes", [])

            return [
                {
                    "id": p.get("id"),
                    "title": p.get("name"),
                    "content": p.get("description", "") or f"Project: {p.get('name')}",
                    "url": p.get("url"),
                    "source": "linear",
                    "metadata": {
                        "type": "project",
                        "state": p.get("state"),
                        "progress": p.get("progress"),
                        "target_date": p.get("targetDate"),
                        "teams": [t.get("name") for t in p.get("teams", {}).get("nodes", [])]
                    }
                }
                for p in projects
            ]

        except Exception as e:
            logger.error(f"Linear get projects error: {e}")
            return []

    async def close(self):
        """Close HTTP client"""
        if self._api_client:
            await self._api_client.aclose()
        await super().close()


# Create FastAPI app
def create_app() -> "FastAPI":
    service = LinearService()
    app = create_service_app(
        service,
        title="Linear Integration Service",
        description="Search Linear issues and projects"
    )

    # Add custom endpoints
    @app.get("/issues/{issue_id}")
    async def get_issue(issue_id: str):
        return await service.get_issue(issue_id)

    @app.get("/projects")
    async def get_projects(limit: int = 20):
        return await service.get_projects(limit)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8017)
