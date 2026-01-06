"""
Slack Client - Search and retrieve messages from Slack workspaces
Uses Slack Web API for message search and retrieval.
"""

import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SlackClient:
    """Client for interacting with Slack API"""

    def __init__(self, bot_token: str, user_token: Optional[str] = None):
        """
        Initialize Slack client.

        Args:
            bot_token: Slack Bot User OAuth Token (xoxb-...)
            user_token: Slack User OAuth Token (xoxp-...) - needed for search
        """
        self.bot_token = bot_token
        self.user_token = user_token  # Search API requires user token
        self.base_url = "https://slack.com/api"

    async def search_messages(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search for messages in Slack.
        Note: Requires search:read scope and user token.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of message dictionaries
        """
        # Use user token for search (bot tokens can't search)
        token = self.user_token or self.bot_token

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/search.messages",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "query": query,
                        "count": limit,
                        "sort": "score",
                        "sort_dir": "desc"
                    }
                ) as response:
                    data = await response.json()

                    if not data.get("ok"):
                        error = data.get("error", "Unknown error")
                        logger.error(f"Slack search error: {error}")
                        return []

                    messages = data.get("messages", {}).get("matches", [])
                    return self._format_messages(messages)

        except Exception as e:
            logger.error(f"Slack search failed: {e}")
            return []

    async def get_channel_history(
        self,
        channel_id: str,
        limit: int = 20,
        oldest: Optional[float] = None
    ) -> List[Dict]:
        """
        Get message history from a channel.

        Args:
            channel_id: Slack channel ID
            limit: Maximum number of messages
            oldest: Unix timestamp for oldest message

        Returns:
            List of message dictionaries
        """
        try:
            params = {
                "channel": channel_id,
                "limit": limit
            }
            if oldest:
                params["oldest"] = oldest

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/conversations.history",
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                    params=params
                ) as response:
                    data = await response.json()

                    if not data.get("ok"):
                        error = data.get("error", "Unknown error")
                        logger.error(f"Slack history error: {error}")
                        return []

                    messages = data.get("messages", [])
                    return self._format_channel_messages(messages, channel_id)

        except Exception as e:
            logger.error(f"Slack get history failed: {e}")
            return []

    async def get_user_info(self, user_id: str) -> Optional[Dict]:
        """Get user information by ID"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/users.info",
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                    params={"user": user_id}
                ) as response:
                    data = await response.json()

                    if data.get("ok"):
                        user = data.get("user", {})
                        return {
                            "id": user.get("id"),
                            "name": user.get("name"),
                            "real_name": user.get("real_name"),
                            "email": user.get("profile", {}).get("email"),
                            "title": user.get("profile", {}).get("title"),
                            "avatar": user.get("profile", {}).get("image_72")
                        }
                    return None

        except Exception as e:
            logger.error(f"Slack get user failed: {e}")
            return None

    async def get_channel_info(self, channel_id: str) -> Optional[Dict]:
        """Get channel information by ID"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/conversations.info",
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                    params={"channel": channel_id}
                ) as response:
                    data = await response.json()

                    if data.get("ok"):
                        channel = data.get("channel", {})
                        return {
                            "id": channel.get("id"),
                            "name": channel.get("name"),
                            "is_private": channel.get("is_private", False),
                            "topic": channel.get("topic", {}).get("value"),
                            "purpose": channel.get("purpose", {}).get("value")
                        }
                    return None

        except Exception as e:
            logger.error(f"Slack get channel failed: {e}")
            return None

    def _format_messages(self, messages: List[Dict]) -> List[Dict]:
        """Format search results into standard document format"""
        formatted = []

        for msg in messages:
            channel = msg.get("channel", {})
            timestamp = float(msg.get("ts", 0))

            formatted.append({
                "source": "slack",
                "title": f"Message in #{channel.get('name', 'unknown')}",
                "content": msg.get("text", ""),
                "url": msg.get("permalink", ""),
                "timestamp": datetime.fromtimestamp(timestamp).isoformat() if timestamp else None,
                "metadata": {
                    "channel_id": channel.get("id"),
                    "channel_name": channel.get("name"),
                    "user": msg.get("user"),
                    "username": msg.get("username"),
                    "score": msg.get("score", 0)
                }
            })

        return formatted

    def _format_channel_messages(self, messages: List[Dict], channel_id: str) -> List[Dict]:
        """Format channel history into standard document format"""
        formatted = []

        for msg in messages:
            timestamp = float(msg.get("ts", 0))

            formatted.append({
                "source": "slack",
                "title": f"Message in channel",
                "content": msg.get("text", ""),
                "url": "",  # Permalink not available in history
                "timestamp": datetime.fromtimestamp(timestamp).isoformat() if timestamp else None,
                "metadata": {
                    "channel_id": channel_id,
                    "user": msg.get("user"),
                    "type": msg.get("type"),
                    "subtype": msg.get("subtype")
                }
            })

        return formatted

    async def test_connection(self) -> Dict:
        """Test the Slack connection"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/auth.test",
                    headers={"Authorization": f"Bearer {self.bot_token}"}
                ) as response:
                    data = await response.json()

                    if data.get("ok"):
                        return {
                            "status": "success",
                            "team": data.get("team"),
                            "user": data.get("user"),
                            "bot_id": data.get("bot_id")
                        }
                    else:
                        return {
                            "status": "error",
                            "error": data.get("error")
                        }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
