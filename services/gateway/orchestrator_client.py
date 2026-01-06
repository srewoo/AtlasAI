"""
Orchestrator Client
Communicates with the orchestrator service for distributed context gathering
"""
import os
import logging
import httpx
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

ORCHESTRATOR_URL = os.environ.get('ORCHESTRATOR_URL', 'http://localhost:8002')


class OrchestratorClient:
    """
    Client for the orchestrator service
    Replaces direct Confluence/Jira clients with microservice calls
    """

    def __init__(self, orchestrator_url: Optional[str] = None):
        self.orchestrator_url = orchestrator_url or ORCHESTRATOR_URL
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async client"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(
        self,
        query: str,
        services: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search across multiple services via orchestrator

        Args:
            query: Search query
            services: List of service names to query (None = auto-detect)
            limit: Maximum results per service

        Returns:
            List of search results from all services
        """
        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.orchestrator_url}/search",
                json={
                    "query": query,
                    "limit": limit,
                    "services": services,
                    "parallel": True,
                    "include_metadata": True
                }
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                logger.info(f"Orchestrator returned {len(results)} results from {data.get('sources_responded', [])}")
                return results
            else:
                logger.error(f"Orchestrator error: {response.status_code} - {response.text}")
                return []

        except httpx.ConnectError:
            logger.warning(f"Could not connect to orchestrator at {self.orchestrator_url}")
            return []
        except Exception as e:
            logger.error(f"Orchestrator search error: {e}")
            return []

    async def search_service(
        self,
        service: str,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search a specific service

        Args:
            service: Service name (confluence, jira, slack, etc.)
            query: Search query
            limit: Maximum results

        Returns:
            List of search results
        """
        return await self.search(query, services=[service], limit=limit)

    async def get_services_status(self) -> Dict[str, Any]:
        """Get status of all services"""
        client = await self._get_client()

        try:
            response = await client.get(f"{self.orchestrator_url}/services")
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            logger.error(f"Failed to get services status: {e}")
            return {}

    async def health_check(self) -> bool:
        """Check if orchestrator is healthy"""
        client = await self._get_client()

        try:
            response = await client.get(f"{self.orchestrator_url}/health")
            return response.status_code == 200
        except Exception:
            return False


# Singleton instance
_orchestrator_client: Optional[OrchestratorClient] = None


def get_orchestrator_client() -> OrchestratorClient:
    """Get or create orchestrator client singleton"""
    global _orchestrator_client
    if _orchestrator_client is None:
        _orchestrator_client = OrchestratorClient()
    return _orchestrator_client
