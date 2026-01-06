"""
Notion Integration Service
Search pages, databases, and blocks
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


class NotionService(BaseIntegrationService):
    """
    Notion integration for searching pages and databases

    Features:
    - Search pages
    - Search databases
    - Query database entries
    - Get page content
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        redis_url: str = "redis://localhost:6379"
    ):
        super().__init__(
            service_name="notion",
            version="1.0.0",
            rate_limit_config=RateLimitConfig(
                requests_per_window=3,  # Notion is very strict
                window_seconds=1,
                burst_size=3
            ),
            circuit_config=CircuitBreakerConfig(
                failure_threshold=3,
                timeout=60
            ),
            chunk_config=ChunkConfig(
                max_chunk_size=512,
                chunk_overlap=50
            ),
            redis_url=redis_url
        )
        self.api_key = api_key or os.getenv("NOTION_API_KEY")
        self.base_url = "https://api.notion.com/v1"

    async def _init_client(self):
        """Initialize Notion client"""
        if not self.api_key:
            logger.warning("Notion API key not configured")
            return

        try:
            import httpx
            self._api_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            logger.info("Notion client initialized")
        except ImportError:
            logger.error("httpx not installed. Run: pip install httpx")
            raise

    async def _health_check_impl(self) -> bool:
        """Check Notion API connection"""
        if not self._api_client:
            return False
        try:
            response = await self._api_client.get("/users/me")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Notion health check failed: {e}")
            return False

    async def _search_impl(self, query: str, limit: int, **kwargs) -> List[Dict]:
        """Search Notion pages and databases"""
        if not self._api_client:
            return []

        try:
            response = await self._api_client.post(
                "/search",
                json={
                    "query": query,
                    "page_size": limit,
                    "sort": {
                        "direction": "descending",
                        "timestamp": "last_edited_time"
                    }
                }
            )

            if response.status_code != 200:
                logger.error(f"Notion search failed: {response.text}")
                return []

            data = response.json()
            results = data.get("results", [])

            return [self._format_result(item) for item in results[:limit]]

        except Exception as e:
            logger.error(f"Notion search error: {e}")
            return []

    def _format_result(self, item: Dict) -> Dict:
        """Format Notion result to standard format"""
        obj_type = item.get("object")
        item_id = item.get("id", "")

        if obj_type == "page":
            return self._format_page(item)
        elif obj_type == "database":
            return self._format_database(item)
        else:
            return {
                "id": item_id,
                "title": "Unknown",
                "content": "",
                "url": item.get("url", ""),
                "source": "notion",
                "metadata": {"type": obj_type}
            }

    def _format_page(self, page: Dict) -> Dict:
        """Format a Notion page"""
        page_id = page.get("id", "")
        properties = page.get("properties", {})

        # Extract title
        title = "Untitled"
        for prop_name, prop_value in properties.items():
            if prop_value.get("type") == "title":
                title_parts = prop_value.get("title", [])
                if title_parts:
                    title = "".join([t.get("plain_text", "") for t in title_parts])
                break

        # Build URL
        url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")

        return {
            "id": page_id,
            "title": title,
            "content": f"Page: {title}",  # Content fetched separately if needed
            "url": url,
            "source": "notion",
            "metadata": {
                "type": "page",
                "created_time": page.get("created_time"),
                "last_edited_time": page.get("last_edited_time"),
                "created_by": page.get("created_by", {}).get("id"),
                "icon": page.get("icon")
            }
        }

    def _format_database(self, database: Dict) -> Dict:
        """Format a Notion database"""
        db_id = database.get("id", "")
        title_parts = database.get("title", [])
        title = "".join([t.get("plain_text", "") for t in title_parts]) if title_parts else "Untitled Database"

        description_parts = database.get("description", [])
        description = "".join([d.get("plain_text", "") for d in description_parts]) if description_parts else ""

        url = database.get("url", f"https://notion.so/{db_id.replace('-', '')}")

        return {
            "id": db_id,
            "title": title,
            "content": description or f"Database: {title}",
            "url": url,
            "source": "notion",
            "metadata": {
                "type": "database",
                "created_time": database.get("created_time"),
                "last_edited_time": database.get("last_edited_time"),
                "properties": list(database.get("properties", {}).keys())
            }
        }

    async def get_page_content(self, page_id: str) -> Optional[Dict]:
        """Get full page content including blocks"""
        if not self._api_client:
            return None

        try:
            # Get page info
            page_response = await self._api_client.get(f"/pages/{page_id}")
            if page_response.status_code != 200:
                return None

            page = page_response.json()

            # Get page blocks (content)
            blocks_response = await self._api_client.get(
                f"/blocks/{page_id}/children",
                params={"page_size": 100}
            )

            content = ""
            if blocks_response.status_code == 200:
                blocks = blocks_response.json().get("results", [])
                content = self._extract_block_text(blocks)

            result = self._format_page(page)
            result["content"] = content

            return result

        except Exception as e:
            logger.error(f"Notion get page error: {e}")
            return None

    def _extract_block_text(self, blocks: List[Dict]) -> str:
        """Extract text from Notion blocks"""
        text_parts = []

        for block in blocks:
            block_type = block.get("type")
            block_data = block.get(block_type, {})

            # Extract rich text
            rich_text = block_data.get("rich_text", [])
            if rich_text:
                text = "".join([t.get("plain_text", "") for t in rich_text])
                text_parts.append(text)

            # Handle special block types
            if block_type == "heading_1":
                text_parts.append(f"\n# {text}\n")
            elif block_type == "heading_2":
                text_parts.append(f"\n## {text}\n")
            elif block_type == "heading_3":
                text_parts.append(f"\n### {text}\n")
            elif block_type == "bulleted_list_item":
                text_parts.append(f"• {text}")
            elif block_type == "numbered_list_item":
                text_parts.append(f"1. {text}")
            elif block_type == "to_do":
                checked = "✓" if block_data.get("checked") else "○"
                text_parts.append(f"{checked} {text}")
            elif block_type == "code":
                language = block_data.get("language", "")
                text_parts.append(f"\n```{language}\n{text}\n```\n")

        return "\n".join(text_parts)

    async def query_database(
        self,
        database_id: str,
        filter_obj: Optional[Dict] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Query a Notion database"""
        if not self._api_client:
            return []

        try:
            body = {"page_size": limit}
            if filter_obj:
                body["filter"] = filter_obj

            response = await self._api_client.post(
                f"/databases/{database_id}/query",
                json=body
            )

            if response.status_code != 200:
                logger.error(f"Database query failed: {response.text}")
                return []

            data = response.json()
            results = data.get("results", [])

            return [self._format_page(page) for page in results[:limit]]

        except Exception as e:
            logger.error(f"Notion database query error: {e}")
            return []

    async def close(self):
        """Close HTTP client"""
        if self._api_client:
            await self._api_client.aclose()
        await super().close()


# Create FastAPI app
def create_app() -> "FastAPI":
    service = NotionService()
    app = create_service_app(
        service,
        title="Notion Integration Service",
        description="Search Notion pages and databases"
    )

    # Add custom endpoints
    @app.get("/pages/{page_id}")
    async def get_page(page_id: str):
        return await service.get_page_content(page_id)

    @app.post("/databases/{database_id}/query")
    async def query_database(database_id: str, filter_obj: Optional[Dict] = None, limit: int = 10):
        return await service.query_database(database_id, filter_obj, limit)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8013)
