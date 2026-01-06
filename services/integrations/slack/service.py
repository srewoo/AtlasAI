"""
Slack Integration Service
Search messages, channels, and users
"""
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from ..base import (
    BaseIntegrationService,
    SearchResult,
    RateLimitConfig,
    CircuitBreakerConfig,
    ChunkConfig,
    create_service_app
)

logger = logging.getLogger(__name__)


class SlackService(BaseIntegrationService):
    """
    Slack integration for searching messages and channels

    Features:
    - Search messages across channels
    - Search files
    - List channels and users
    - Get conversation history
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        redis_url: str = "redis://localhost:6379"
    ):
        super().__init__(
            service_name="slack",
            version="1.0.0",
            rate_limit_config=RateLimitConfig(
                requests_per_window=50,  # Slack Tier 2
                window_seconds=60,
                burst_size=10
            ),
            circuit_config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout=30
            ),
            chunk_config=ChunkConfig(
                max_chunk_size=512,
                chunk_overlap=50
            ),
            redis_url=redis_url
        )
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN")

    async def _init_client(self):
        """Initialize Slack client"""
        if not self.bot_token:
            logger.warning("Slack bot token not configured")
            return

        try:
            from slack_sdk.web.async_client import AsyncWebClient
            self._api_client = AsyncWebClient(token=self.bot_token)
            logger.info("Slack client initialized")
        except ImportError:
            logger.error("slack_sdk not installed. Run: pip install slack_sdk")
            raise

    async def _health_check_impl(self) -> bool:
        """Check Slack API connection"""
        if not self._api_client:
            return False
        try:
            response = await self._api_client.auth_test()
            return response.get("ok", False)
        except Exception as e:
            logger.error(f"Slack health check failed: {e}")
            return False

    async def _search_impl(self, query: str, limit: int, **kwargs) -> List[Dict]:
        """Search Slack messages"""
        if not self._api_client:
            return []

        results = []

        try:
            # Search messages
            response = await self._api_client.search_messages(
                query=query,
                count=limit,
                sort="timestamp",
                sort_dir="desc"
            )

            if response.get("ok"):
                messages = response.get("messages", {}).get("matches", [])

                for msg in messages[:limit]:
                    channel_info = msg.get("channel", {})
                    user_info = msg.get("user") or msg.get("username", "Unknown")

                    # Get permalink
                    permalink = msg.get("permalink", "")

                    results.append({
                        "id": msg.get("ts", ""),
                        "title": f"Message in #{channel_info.get('name', 'unknown')}",
                        "content": msg.get("text", "")[:1000],
                        "url": permalink,
                        "source": "slack",
                        "metadata": {
                            "channel": channel_info.get("name"),
                            "channel_id": channel_info.get("id"),
                            "user": user_info,
                            "timestamp": msg.get("ts"),
                            "type": "message"
                        }
                    })

        except Exception as e:
            logger.error(f"Slack search error: {e}")

        return results

    async def search_channels(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for channels matching query"""
        if not self._api_client:
            return []

        try:
            response = await self._api_client.conversations_list(
                types="public_channel,private_channel",
                limit=100
            )

            if response.get("ok"):
                channels = response.get("channels", [])
                # Filter by query
                matching = [
                    c for c in channels
                    if query.lower() in c.get("name", "").lower()
                    or query.lower() in c.get("purpose", {}).get("value", "").lower()
                ]

                return [
                    {
                        "id": c.get("id"),
                        "title": f"#{c.get('name')}",
                        "content": c.get("purpose", {}).get("value", ""),
                        "url": f"slack://channel?team=&id={c.get('id')}",
                        "source": "slack",
                        "metadata": {
                            "type": "channel",
                            "member_count": c.get("num_members", 0),
                            "is_private": c.get("is_private", False)
                        }
                    }
                    for c in matching[:limit]
                ]

        except Exception as e:
            logger.error(f"Slack channel search error: {e}")

        return []

    async def get_channel_history(
        self,
        channel_id: str,
        limit: int = 20,
        oldest: Optional[str] = None
    ) -> List[Dict]:
        """Get recent messages from a channel"""
        if not self._api_client:
            return []

        try:
            params = {
                "channel": channel_id,
                "limit": limit
            }
            if oldest:
                params["oldest"] = oldest

            response = await self._api_client.conversations_history(**params)

            if response.get("ok"):
                messages = response.get("messages", [])
                return [
                    {
                        "id": msg.get("ts"),
                        "title": f"Message at {datetime.fromtimestamp(float(msg.get('ts', 0)))}",
                        "content": msg.get("text", ""),
                        "source": "slack",
                        "metadata": {
                            "user": msg.get("user"),
                            "type": msg.get("type"),
                            "timestamp": msg.get("ts")
                        }
                    }
                    for msg in messages
                ]

        except Exception as e:
            logger.error(f"Slack history error: {e}")

        return []

    async def search_files(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for files in Slack"""
        if not self._api_client:
            return []

        try:
            response = await self._api_client.files_list(
                count=limit
            )

            if response.get("ok"):
                files = response.get("files", [])
                # Filter by query
                matching = [
                    f for f in files
                    if query.lower() in f.get("name", "").lower()
                    or query.lower() in f.get("title", "").lower()
                ]

                return [
                    {
                        "id": f.get("id"),
                        "title": f.get("title") or f.get("name"),
                        "content": f.get("preview", "")[:500],
                        "url": f.get("permalink"),
                        "source": "slack",
                        "metadata": {
                            "type": "file",
                            "filetype": f.get("filetype"),
                            "size": f.get("size"),
                            "created": f.get("created")
                        }
                    }
                    for f in matching[:limit]
                ]

        except Exception as e:
            logger.error(f"Slack file search error: {e}")

        return []


# Create FastAPI app
def create_app() -> "FastAPI":
    service = SlackService()
    app = create_service_app(
        service,
        title="Slack Integration Service",
        description="Search Slack messages, channels, and files"
    )

    # Add custom endpoints
    @app.get("/channels")
    async def search_channels(query: str, limit: int = 10):
        return await service.search_channels(query, limit)

    @app.get("/channels/{channel_id}/history")
    async def get_channel_history(channel_id: str, limit: int = 20):
        return await service.get_channel_history(channel_id, limit)

    @app.get("/files")
    async def search_files(query: str, limit: int = 10):
        return await service.search_files(query, limit)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
