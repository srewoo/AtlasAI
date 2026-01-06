"""
Figma Integration Service
Search files, projects, components, and design assets
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

FIGMA_API_URL = "https://api.figma.com/v1"


class FigmaService(BaseIntegrationService):
    """
    Figma integration for searching design files and components

    Features:
    - Search files and projects
    - Get file structure and frames
    - Search components and styles
    - Get comments and annotations
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        team_id: Optional[str] = None,
        redis_url: str = "redis://localhost:6379"
    ):
        super().__init__(
            service_name="figma",
            version="1.0.0",
            rate_limit_config=RateLimitConfig(
                requests_per_window=100,  # Figma has strict limits
                window_seconds=60,
                burst_size=10
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
        self.access_token = access_token or os.getenv("FIGMA_TOKEN")
        self.team_id = team_id or os.getenv("FIGMA_TEAM_ID")

    async def _init_client(self):
        """Initialize Figma API client"""
        if not self.access_token:
            logger.warning("Figma access token not configured")
            return

        try:
            import httpx
            self._api_client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "X-Figma-Token": self.access_token,
                    "Content-Type": "application/json"
                }
            )
            logger.info("Figma client initialized")
        except ImportError:
            logger.error("httpx not installed. Run: pip install httpx")
            raise

    async def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make authenticated request to Figma API"""
        if not self._api_client:
            return None

        try:
            response = await self._api_client.get(
                f"{FIGMA_API_URL}{endpoint}",
                params=params
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("Figma rate limit hit")
                return None
            else:
                logger.error(f"Figma API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Figma API request error: {e}")
            return None

    async def _health_check_impl(self) -> bool:
        """Check Figma API connection"""
        if not self._api_client:
            return False
        try:
            response = await self._api_client.get(f"{FIGMA_API_URL}/me")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Figma health check failed: {e}")
            return False

    async def _search_impl(self, query: str, limit: int, **kwargs) -> List[Dict]:
        """Search across Figma resources"""
        search_type = kwargs.get("search_type", "all")
        results = []

        if search_type in ["all", "files"]:
            file_results = await self.search_files(query, limit)
            results.extend(file_results)

        if search_type in ["all", "components"]:
            component_results = await self.search_components(query, limit)
            results.extend(component_results)

        return results[:limit]

    async def search_files(self, query: str, limit: int = 10) -> List[Dict]:
        """Search team files by name"""
        if not self._api_client or not self.team_id:
            return []

        try:
            # Get team projects
            projects_data = await self._make_request(f"/teams/{self.team_id}/projects")
            if not projects_data:
                return []

            projects = projects_data.get("projects", [])
            results = []
            query_lower = query.lower()

            for project in projects:
                project_id = project.get("id")
                project_name = project.get("name", "")

                # Get files in project
                files_data = await self._make_request(f"/projects/{project_id}/files")
                if not files_data:
                    continue

                files = files_data.get("files", [])

                for file in files:
                    file_name = file.get("name", "")

                    # Match query against file name
                    if query_lower in file_name.lower() or query_lower in project_name.lower():
                        file_key = file.get("key", "")
                        results.append({
                            "id": file_key,
                            "title": file_name,
                            "content": f"Figma file: {file_name}\nProject: {project_name}",
                            "url": f"https://www.figma.com/file/{file_key}",
                            "source": "figma",
                            "metadata": {
                                "type": "file",
                                "project_id": project_id,
                                "project_name": project_name,
                                "thumbnail_url": file.get("thumbnail_url"),
                                "last_modified": file.get("last_modified")
                            }
                        })

                        if len(results) >= limit:
                            break

                if len(results) >= limit:
                    break

            return results[:limit]

        except Exception as e:
            logger.error(f"Figma file search error: {e}")
            return []

    async def search_components(self, query: str, limit: int = 10) -> List[Dict]:
        """Search team components"""
        if not self._api_client or not self.team_id:
            return []

        try:
            # Get team components
            data = await self._make_request(f"/teams/{self.team_id}/components")
            if not data:
                return []

            components = data.get("meta", {}).get("components", [])
            results = []
            query_lower = query.lower()

            for component in components:
                name = component.get("name", "")
                description = component.get("description", "")

                if query_lower in name.lower() or query_lower in description.lower():
                    file_key = component.get("file_key", "")
                    node_id = component.get("node_id", "")

                    results.append({
                        "id": f"{file_key}:{node_id}",
                        "title": f"Component: {name}",
                        "content": f"{name}\n\n{description}" if description else name,
                        "url": f"https://www.figma.com/file/{file_key}?node-id={node_id}",
                        "source": "figma",
                        "metadata": {
                            "type": "component",
                            "file_key": file_key,
                            "node_id": node_id,
                            "thumbnail_url": component.get("thumbnail_url"),
                            "created_at": component.get("created_at"),
                            "updated_at": component.get("updated_at")
                        }
                    })

                    if len(results) >= limit:
                        break

            return results

        except Exception as e:
            logger.error(f"Figma component search error: {e}")
            return []

    async def search_styles(self, query: str, limit: int = 10) -> List[Dict]:
        """Search team styles (colors, text, effects)"""
        if not self._api_client or not self.team_id:
            return []

        try:
            data = await self._make_request(f"/teams/{self.team_id}/styles")
            if not data:
                return []

            styles = data.get("meta", {}).get("styles", [])
            results = []
            query_lower = query.lower()

            for style in styles:
                name = style.get("name", "")
                description = style.get("description", "")
                style_type = style.get("style_type", "")

                if query_lower in name.lower() or query_lower in description.lower():
                    file_key = style.get("file_key", "")
                    node_id = style.get("node_id", "")

                    results.append({
                        "id": f"{file_key}:{node_id}",
                        "title": f"Style: {name}",
                        "content": f"{style_type.title()} style: {name}\n{description}",
                        "url": f"https://www.figma.com/file/{file_key}?node-id={node_id}",
                        "source": "figma",
                        "metadata": {
                            "type": "style",
                            "style_type": style_type,
                            "file_key": file_key,
                            "node_id": node_id,
                            "thumbnail_url": style.get("thumbnail_url")
                        }
                    })

                    if len(results) >= limit:
                        break

            return results

        except Exception as e:
            logger.error(f"Figma style search error: {e}")
            return []

    async def get_file_details(self, file_key: str) -> Optional[Dict]:
        """Get detailed file information including frames"""
        if not self._api_client:
            return None

        try:
            data = await self._make_request(f"/files/{file_key}")
            if not data:
                return None

            document = data.get("document", {})

            # Extract frames from pages
            frames = []
            for page in document.get("children", []):
                page_name = page.get("name", "")
                for child in page.get("children", []):
                    if child.get("type") == "FRAME":
                        frames.append({
                            "id": child.get("id"),
                            "name": child.get("name"),
                            "page": page_name,
                            "type": child.get("type")
                        })

            return {
                "id": file_key,
                "title": data.get("name", ""),
                "content": f"Figma file with {len(frames)} frames",
                "url": f"https://www.figma.com/file/{file_key}",
                "source": "figma",
                "metadata": {
                    "type": "file_detail",
                    "version": data.get("version"),
                    "last_modified": data.get("lastModified"),
                    "thumbnail_url": data.get("thumbnailUrl"),
                    "frames": frames[:20]  # Limit frames
                }
            }

        except Exception as e:
            logger.error(f"Get file details error: {e}")
            return None

    async def get_file_comments(self, file_key: str, limit: int = 20) -> List[Dict]:
        """Get comments on a file"""
        if not self._api_client:
            return []

        try:
            data = await self._make_request(f"/files/{file_key}/comments")
            if not data:
                return []

            comments = data.get("comments", [])
            results = []

            for comment in comments[:limit]:
                user = comment.get("user", {})

                results.append({
                    "id": comment.get("id", ""),
                    "title": f"Comment by {user.get('handle', 'Unknown')}",
                    "content": comment.get("message", ""),
                    "url": f"https://www.figma.com/file/{file_key}?comment={comment.get('id')}",
                    "source": "figma",
                    "metadata": {
                        "type": "comment",
                        "file_key": file_key,
                        "author": user.get("handle"),
                        "created_at": comment.get("created_at"),
                        "resolved_at": comment.get("resolved_at"),
                        "client_meta": comment.get("client_meta")
                    }
                })

            return results

        except Exception as e:
            logger.error(f"Get comments error: {e}")
            return []

    async def get_team_projects(self) -> List[Dict]:
        """Get all projects in the team"""
        if not self._api_client or not self.team_id:
            return []

        try:
            data = await self._make_request(f"/teams/{self.team_id}/projects")
            if not data:
                return []

            projects = data.get("projects", [])
            results = []

            for project in projects:
                results.append({
                    "id": str(project.get("id", "")),
                    "title": project.get("name", ""),
                    "content": f"Figma project: {project.get('name', '')}",
                    "url": "",  # Projects don't have direct URLs
                    "source": "figma",
                    "metadata": {
                        "type": "project"
                    }
                })

            return results

        except Exception as e:
            logger.error(f"Get projects error: {e}")
            return []

    async def close(self):
        """Close HTTP client"""
        if self._api_client:
            await self._api_client.aclose()
        await super().close()


# Create FastAPI app
def create_app() -> "FastAPI":
    service = FigmaService()
    app = create_service_app(
        service,
        title="Figma Integration Service",
        description="Search Figma files, components, and styles"
    )

    # Add custom endpoints
    @app.get("/files")
    async def search_files(query: str, limit: int = 10):
        return await service.search_files(query, limit)

    @app.get("/files/{file_key}")
    async def get_file(file_key: str):
        return await service.get_file_details(file_key)

    @app.get("/files/{file_key}/comments")
    async def get_comments(file_key: str, limit: int = 20):
        return await service.get_file_comments(file_key, limit)

    @app.get("/components")
    async def search_components(query: str, limit: int = 10):
        return await service.search_components(query, limit)

    @app.get("/styles")
    async def search_styles(query: str, limit: int = 10):
        return await service.search_styles(query, limit)

    @app.get("/projects")
    async def get_projects():
        return await service.get_team_projects()

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8018)
