"""
Shared configuration settings for all services
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class BaseServiceSettings(BaseSettings):
    """Base settings for all services"""

    # Service identification
    service_name: str = "base-service"
    service_port: int = 8000
    debug: bool = False

    # Redis configuration
    redis_url: str = "redis://localhost:6379"
    redis_cache_ttl: int = 3600  # 1 hour default

    # Rate limiting defaults
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # Circuit breaker defaults
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 30  # seconds

    # Retry configuration
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_exponential_base: float = 2.0

    # Chunking configuration
    chunk_size: int = 512  # tokens
    chunk_overlap: int = 50  # tokens
    max_chunks_per_doc: int = 20

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "allow"


class GatewaySettings(BaseServiceSettings):
    """API Gateway settings"""
    service_name: str = "gateway"
    service_port: int = 8001
    cors_origins: str = "*"
    mongo_url: str = "mongodb://localhost:27017"
    db_name: str = "atlas_ai"


class OrchestratorSettings(BaseServiceSettings):
    """Orchestrator service settings"""
    service_name: str = "orchestrator"
    service_port: int = 8002
    parallel_timeout: int = 30  # seconds
    max_parallel_requests: int = 10


class RAGCoreSettings(BaseServiceSettings):
    """RAG Core service settings"""
    service_name: str = "rag-core"
    service_port: int = 8003
    vector_store_path: str = "./chroma_db"
    embedding_model: str = "all-MiniLM-L6-v2"
    context_window: int = 4096
    max_context_docs: int = 5


class SlackSettings(BaseServiceSettings):
    """Slack integration settings"""
    service_name: str = "slack-service"
    service_port: int = 8010
    slack_bot_token: Optional[str] = None
    slack_app_token: Optional[str] = None
    rate_limit_requests: int = 50  # Slack tier 2
    rate_limit_window: int = 60


class GitHubSettings(BaseServiceSettings):
    """GitHub integration settings"""
    service_name: str = "github-service"
    service_port: int = 8011
    github_token: Optional[str] = None
    rate_limit_requests: int = 5000  # GitHub API limit
    rate_limit_window: int = 3600


class GoogleSettings(BaseServiceSettings):
    """Google Workspace integration settings"""
    service_name: str = "google-service"
    service_port: int = 8012
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    rate_limit_requests: int = 100
    rate_limit_window: int = 100


class NotionSettings(BaseServiceSettings):
    """Notion integration settings"""
    service_name: str = "notion-service"
    service_port: int = 8013
    notion_api_key: Optional[str] = None
    rate_limit_requests: int = 3  # Notion is strict
    rate_limit_window: int = 1


class LinearSettings(BaseServiceSettings):
    """Linear integration settings"""
    service_name: str = "linear-service"
    service_port: int = 8017
    linear_api_key: Optional[str] = None
    rate_limit_requests: int = 1500
    rate_limit_window: int = 3600


class FigmaSettings(BaseServiceSettings):
    """Figma integration settings"""
    service_name: str = "figma-service"
    service_port: int = 8018
    figma_token: Optional[str] = None
    rate_limit_requests: int = 120
    rate_limit_window: int = 60


class TeamsSettings(BaseServiceSettings):
    """Microsoft Teams integration settings"""
    service_name: str = "teams-service"
    service_port: int = 8019
    ms_client_id: Optional[str] = None
    ms_client_secret: Optional[str] = None
    ms_tenant_id: Optional[str] = None


class ZendeskSettings(BaseServiceSettings):
    """Zendesk integration settings"""
    service_name: str = "zendesk-service"
    service_port: int = 8020
    zendesk_subdomain: Optional[str] = None
    zendesk_email: Optional[str] = None
    zendesk_token: Optional[str] = None
    rate_limit_requests: int = 400
    rate_limit_window: int = 60


class AsanaSettings(BaseServiceSettings):
    """Asana integration settings"""
    service_name: str = "asana-service"
    service_port: int = 8021
    asana_token: Optional[str] = None
    rate_limit_requests: int = 150
    rate_limit_window: int = 60


class TrelloSettings(BaseServiceSettings):
    """Trello integration settings"""
    service_name: str = "trello-service"
    service_port: int = 8022
    trello_api_key: Optional[str] = None
    trello_token: Optional[str] = None
    rate_limit_requests: int = 100
    rate_limit_window: int = 10


class PagerDutySettings(BaseServiceSettings):
    """PagerDuty integration settings"""
    service_name: str = "pagerduty-service"
    service_port: int = 8023
    pagerduty_token: Optional[str] = None
    rate_limit_requests: int = 200
    rate_limit_window: int = 60


class CalendarSettings(BaseServiceSettings):
    """Calendar integration settings (Google + Outlook)"""
    service_name: str = "calendar-service"
    service_port: int = 8024


@lru_cache()
def get_settings(service_type: str = "base") -> BaseServiceSettings:
    """Get settings for a specific service type"""
    settings_map = {
        "base": BaseServiceSettings,
        "gateway": GatewaySettings,
        "orchestrator": OrchestratorSettings,
        "rag-core": RAGCoreSettings,
        "slack": SlackSettings,
        "github": GitHubSettings,
        "google": GoogleSettings,
        "notion": NotionSettings,
        "linear": LinearSettings,
        "figma": FigmaSettings,
        "teams": TeamsSettings,
        "zendesk": ZendeskSettings,
        "asana": AsanaSettings,
        "trello": TrelloSettings,
        "pagerduty": PagerDutySettings,
        "calendar": CalendarSettings,
    }
    return settings_map.get(service_type, BaseServiceSettings)()
