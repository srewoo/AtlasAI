"""
Microsoft 365 Integration Service
Search Teams, SharePoint, Outlook, and OneDrive
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

GRAPH_API_URL = "https://graph.microsoft.com/v1.0"


class Microsoft365Service(BaseIntegrationService):
    """
    Microsoft 365 integration using Microsoft Graph API

    Features:
    - Teams: Search messages and channels
    - SharePoint: Search documents and sites
    - Outlook: Search emails and calendar
    - OneDrive: Search files
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant_id: Optional[str] = None,
        redis_url: str = "redis://localhost:6379"
    ):
        super().__init__(
            service_name="microsoft365",
            version="1.0.0",
            rate_limit_config=RateLimitConfig(
                requests_per_window=10000,  # Graph API is generous
                window_seconds=600,
                burst_size=100
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
        self.client_id = client_id or os.getenv("MS_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("MS_CLIENT_SECRET")
        self.tenant_id = tenant_id or os.getenv("MS_TENANT_ID")
        self._access_token = None
        self._token_expires = None

    async def _init_client(self):
        """Initialize Microsoft Graph client"""
        if not all([self.client_id, self.client_secret, self.tenant_id]):
            logger.warning("Microsoft 365 credentials not configured")
            return

        try:
            import httpx
            self._api_client = httpx.AsyncClient(timeout=30.0)
            await self._refresh_token()
            logger.info("Microsoft 365 client initialized")
        except ImportError:
            logger.error("httpx not installed. Run: pip install httpx")
            raise

    async def _refresh_token(self):
        """Get or refresh access token"""
        if self._access_token and self._token_expires and datetime.now() < self._token_expires:
            return

        try:
            token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

            response = await self._api_client.post(
                token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials"
                }
            )

            if response.status_code == 200:
                data = response.json()
                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                self._token_expires = datetime.now() + timedelta(seconds=expires_in - 60)
                logger.info("Microsoft 365 token refreshed")
            else:
                logger.error(f"Failed to get token: {response.text}")

        except Exception as e:
            logger.error(f"Token refresh error: {e}")

    async def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make authenticated request to Graph API"""
        await self._refresh_token()

        if not self._access_token:
            return None

        try:
            response = await self._api_client.get(
                f"{GRAPH_API_URL}{endpoint}",
                params=params,
                headers={"Authorization": f"Bearer {self._access_token}"}
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Graph API request error: {e}")
            return None

    async def _health_check_impl(self) -> bool:
        """Check Microsoft Graph API connection"""
        if not self._api_client:
            return False
        try:
            await self._refresh_token()
            return self._access_token is not None
        except Exception as e:
            logger.error(f"Microsoft 365 health check failed: {e}")
            return False

    async def _search_impl(self, query: str, limit: int, **kwargs) -> List[Dict]:
        """Search across Microsoft 365 services"""
        search_type = kwargs.get("search_type", "all")
        results = []

        if search_type in ["all", "messages", "teams"]:
            teams_results = await self.search_teams_messages(query, limit)
            results.extend(teams_results)

        if search_type in ["all", "files", "sharepoint", "onedrive"]:
            file_results = await self.search_files(query, limit)
            results.extend(file_results)

        if search_type in ["all", "emails", "outlook"]:
            email_results = await self.search_emails(query, limit)
            results.extend(email_results)

        return results[:limit]

    async def search_teams_messages(self, query: str, limit: int = 10) -> List[Dict]:
        """Search Teams messages"""
        if not self._api_client:
            return []

        try:
            # Use Search API for Teams messages
            await self._refresh_token()

            response = await self._api_client.post(
                f"{GRAPH_API_URL}/search/query",
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "requests": [{
                        "entityTypes": ["chatMessage"],
                        "query": {"queryString": query},
                        "from": 0,
                        "size": limit
                    }]
                }
            )

            if response.status_code != 200:
                logger.error(f"Teams search error: {response.text}")
                return []

            data = response.json()
            hits = data.get("value", [{}])[0].get("hitsContainers", [{}])[0].get("hits", [])

            results = []
            for hit in hits[:limit]:
                resource = hit.get("resource", {})
                results.append({
                    "id": resource.get("id", ""),
                    "title": f"Teams Message",
                    "content": resource.get("summary", "") or resource.get("body", {}).get("content", "")[:500],
                    "url": resource.get("webUrl", ""),
                    "source": "microsoft365",
                    "metadata": {
                        "type": "teams_message",
                        "from": resource.get("from", {}).get("user", {}).get("displayName"),
                        "created": resource.get("createdDateTime"),
                        "channel": resource.get("channelIdentity", {}).get("channelId")
                    }
                })

            return results

        except Exception as e:
            logger.error(f"Teams search error: {e}")
            return []

    async def search_files(self, query: str, limit: int = 10) -> List[Dict]:
        """Search SharePoint and OneDrive files"""
        if not self._api_client:
            return []

        try:
            await self._refresh_token()

            response = await self._api_client.post(
                f"{GRAPH_API_URL}/search/query",
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "requests": [{
                        "entityTypes": ["driveItem"],
                        "query": {"queryString": query},
                        "from": 0,
                        "size": limit
                    }]
                }
            )

            if response.status_code != 200:
                logger.error(f"File search error: {response.text}")
                return []

            data = response.json()
            hits = data.get("value", [{}])[0].get("hitsContainers", [{}])[0].get("hits", [])

            results = []
            for hit in hits[:limit]:
                resource = hit.get("resource", {})
                results.append({
                    "id": resource.get("id", ""),
                    "title": resource.get("name", "Untitled"),
                    "content": hit.get("summary", "") or f"File: {resource.get('name', '')}",
                    "url": resource.get("webUrl", ""),
                    "source": "microsoft365",
                    "metadata": {
                        "type": "file",
                        "file_type": resource.get("file", {}).get("mimeType"),
                        "size": resource.get("size"),
                        "created": resource.get("createdDateTime"),
                        "modified": resource.get("lastModifiedDateTime"),
                        "created_by": resource.get("createdBy", {}).get("user", {}).get("displayName")
                    }
                })

            return results

        except Exception as e:
            logger.error(f"File search error: {e}")
            return []

    async def search_emails(self, query: str, limit: int = 10) -> List[Dict]:
        """Search Outlook emails"""
        if not self._api_client:
            return []

        try:
            await self._refresh_token()

            response = await self._api_client.post(
                f"{GRAPH_API_URL}/search/query",
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "requests": [{
                        "entityTypes": ["message"],
                        "query": {"queryString": query},
                        "from": 0,
                        "size": limit
                    }]
                }
            )

            if response.status_code != 200:
                logger.error(f"Email search error: {response.text}")
                return []

            data = response.json()
            hits = data.get("value", [{}])[0].get("hitsContainers", [{}])[0].get("hits", [])

            results = []
            for hit in hits[:limit]:
                resource = hit.get("resource", {})
                results.append({
                    "id": resource.get("id", ""),
                    "title": resource.get("subject", "No Subject"),
                    "content": hit.get("summary", "") or resource.get("bodyPreview", "")[:500],
                    "url": resource.get("webLink", ""),
                    "source": "microsoft365",
                    "metadata": {
                        "type": "email",
                        "from": resource.get("from", {}).get("emailAddress", {}).get("address"),
                        "to": [r.get("emailAddress", {}).get("address") for r in resource.get("toRecipients", [])],
                        "received": resource.get("receivedDateTime"),
                        "has_attachments": resource.get("hasAttachments", False)
                    }
                })

            return results

        except Exception as e:
            logger.error(f"Email search error: {e}")
            return []

    async def get_calendar_events(self, query: str = "", limit: int = 10) -> List[Dict]:
        """Get upcoming calendar events"""
        if not self._api_client:
            return []

        try:
            now = datetime.utcnow()
            end = now + timedelta(days=7)

            data = await self._make_request(
                "/me/calendar/events",
                params={
                    "$filter": f"start/dateTime ge '{now.isoformat()}Z' and start/dateTime le '{end.isoformat()}Z'",
                    "$top": limit,
                    "$orderby": "start/dateTime",
                    "$select": "subject,start,end,location,organizer,webLink,bodyPreview"
                }
            )

            if not data:
                return []

            events = data.get("value", [])
            results = []

            for event in events:
                # Filter by query if provided
                if query and query.lower() not in event.get("subject", "").lower():
                    continue

                results.append({
                    "id": event.get("id", ""),
                    "title": event.get("subject", "No Title"),
                    "content": event.get("bodyPreview", ""),
                    "url": event.get("webLink", ""),
                    "source": "microsoft365",
                    "metadata": {
                        "type": "calendar_event",
                        "start": event.get("start", {}).get("dateTime"),
                        "end": event.get("end", {}).get("dateTime"),
                        "location": event.get("location", {}).get("displayName"),
                        "organizer": event.get("organizer", {}).get("emailAddress", {}).get("name")
                    }
                })

            return results[:limit]

        except Exception as e:
            logger.error(f"Calendar error: {e}")
            return []

    async def get_teams_channels(self) -> List[Dict]:
        """Get list of Teams channels"""
        if not self._api_client:
            return []

        try:
            # Get joined teams
            teams_data = await self._make_request("/me/joinedTeams")
            if not teams_data:
                return []

            results = []
            for team in teams_data.get("value", []):
                team_id = team.get("id")
                team_name = team.get("displayName")

                # Get channels for each team
                channels_data = await self._make_request(f"/teams/{team_id}/channels")
                if channels_data:
                    for channel in channels_data.get("value", []):
                        results.append({
                            "id": channel.get("id"),
                            "title": f"{team_name} / {channel.get('displayName')}",
                            "content": channel.get("description", ""),
                            "url": channel.get("webUrl", ""),
                            "source": "microsoft365",
                            "metadata": {
                                "type": "teams_channel",
                                "team_id": team_id,
                                "team_name": team_name
                            }
                        })

            return results

        except Exception as e:
            logger.error(f"Teams channels error: {e}")
            return []

    async def close(self):
        """Close HTTP client"""
        if self._api_client:
            await self._api_client.aclose()
        await super().close()


# Create FastAPI app
def create_app() -> "FastAPI":
    service = Microsoft365Service()
    app = create_service_app(
        service,
        title="Microsoft 365 Integration Service",
        description="Search Teams, SharePoint, Outlook, and OneDrive"
    )

    # Add custom endpoints
    @app.get("/teams/messages")
    async def search_teams(query: str, limit: int = 10):
        return await service.search_teams_messages(query, limit)

    @app.get("/teams/channels")
    async def get_channels():
        return await service.get_teams_channels()

    @app.get("/files")
    async def search_files(query: str, limit: int = 10):
        return await service.search_files(query, limit)

    @app.get("/emails")
    async def search_emails(query: str, limit: int = 10):
        return await service.search_emails(query, limit)

    @app.get("/calendar")
    async def get_calendar(query: str = "", limit: int = 10):
        return await service.get_calendar_events(query, limit)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8019)
