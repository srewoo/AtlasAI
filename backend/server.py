from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import json

# Import RAG components
from llm_router import LLMRouter
from vector_store import VectorStore
from confluence_client import ConfluenceClient
from jira_client import JiraClient
from slack_client import SlackClient
from web_search import WebSearchClient
from rag_engine import AgenticRAG
from database import db, init_database, close_database

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Vector Store (global)
vector_store = VectorStore()


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_database()
    logger.info("Database initialized")
    yield
    # Shutdown
    await close_database()
    logger.info("Database connection closed")


# Create the main app with lifespan
app = FastAPI(lifespan=lifespan)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Pydantic Models
class ChatMessage(BaseModel):
    message: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class SettingsModel(BaseModel):
    llm_provider: str  # openai, gemini, anthropic, ollama
    llm_model: str
    llm_api_key: str
    # Atlassian credentials (new consolidated format)
    atlassian_domain: Optional[str] = None
    atlassian_email: Optional[str] = None
    atlassian_api_token: Optional[str] = None
    # Legacy individual credentials (for backward compatibility)
    confluence_url: Optional[str] = None
    confluence_username: Optional[str] = None
    confluence_token: Optional[str] = None
    jira_url: Optional[str] = None
    jira_username: Optional[str] = None
    jira_token: Optional[str] = None
    # Slack credentials
    slack_bot_token: Optional[str] = None  # xoxb-... token
    slack_user_token: Optional[str] = None  # xoxp-... token (for search)
    enable_web_search: bool = True
    use_streaming: bool = True


# Helper function to create RAG engine from settings
async def create_rag_engine(settings: SettingsModel) -> AgenticRAG:
    """Create RAG engine from user settings"""
    # Initialize LLM Router
    llm_router = LLMRouter(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key
    )

    # Determine Atlassian credentials (use new format if available, else legacy)
    atlassian_url = None
    atlassian_username = None
    atlassian_token = None

    if settings.atlassian_domain and settings.atlassian_email and settings.atlassian_api_token:
        # Use new consolidated Atlassian credentials
        domain = settings.atlassian_domain
        atlassian_url = domain if domain.startswith('http') else f'https://{domain}'
        atlassian_username = settings.atlassian_email
        atlassian_token = settings.atlassian_api_token
        logger.info(f"Using consolidated Atlassian credentials for domain: {settings.atlassian_domain}")

    # Initialize Confluence client
    confluence_client = None
    confluence_url = atlassian_url or settings.confluence_url
    confluence_username = atlassian_username or settings.confluence_username
    confluence_token = atlassian_token or settings.confluence_token

    if confluence_url and confluence_username and confluence_token:
        try:
            confluence_client = ConfluenceClient(
                url=confluence_url,
                username=confluence_username,
                api_token=confluence_token
            )
            logger.info(f"Confluence client initialized for: {confluence_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Confluence client: {e}")
    else:
        logger.warning("Confluence client not initialized - missing credentials")

    # Initialize Jira client
    jira_client = None
    jira_url = atlassian_url or settings.jira_url
    jira_username = atlassian_username or settings.jira_username
    jira_token = atlassian_token or settings.jira_token

    if jira_url and jira_username and jira_token:
        try:
            jira_client = JiraClient(
                url=jira_url,
                username=jira_username,
                api_token=jira_token
            )
            logger.info(f"Jira client initialized for: {jira_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Jira client: {e}")
    else:
        logger.warning("Jira client not initialized - missing credentials")

    # Initialize Slack client
    slack_client = None
    if settings.slack_bot_token:
        try:
            slack_client = SlackClient(
                bot_token=settings.slack_bot_token,
                user_token=settings.slack_user_token  # Optional, for search
            )
            logger.info("Slack client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Slack client: {e}")
    else:
        logger.warning("Slack client not initialized - missing bot token")

    # Initialize Web Search client (lowest priority)
    web_search_client = None
    if settings.enable_web_search:
        web_search_client = WebSearchClient()
        logger.info("Web search client initialized")

    # Create RAG engine with intelligent query agent
    rag_engine = AgenticRAG(
        vector_store=vector_store,
        llm_router=llm_router,
        confluence_client=confluence_client,
        jira_client=jira_client,
        slack_client=slack_client,
        web_search_client=web_search_client
    )

    return rag_engine


# API Routes
@api_router.get("/")
async def root():
    return {"message": "Chatbot API is running", "database": "SQLite (local)"}


@api_router.post("/settings")
async def save_settings(settings: SettingsModel, user_id: str = "default"):
    """Save user settings"""
    try:
        doc_id = str(uuid.uuid4())
        success = await db.save_user_settings(user_id, settings.model_dump(), doc_id)

        if success:
            return {"status": "success", "message": "Settings saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save settings")
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/settings/{user_id}")
async def get_settings(user_id: str = "default"):
    """Get user settings"""
    try:
        settings_doc = await db.get_user_settings(user_id)
        if settings_doc:
            return settings_doc
        return {"user_id": user_id, "settings": None}
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/chat")
async def chat(chat_request: ChatMessage, user_id: str = "default"):
    """Process chat message"""
    try:
        # Get user settings
        settings_doc = await db.get_user_settings(user_id)
        if not settings_doc or not settings_doc.get("settings"):
            raise HTTPException(status_code=400, detail="User settings not configured. Please configure settings first.")

        settings = SettingsModel(**settings_doc["settings"])

        # Create RAG engine
        rag_engine = await create_rag_engine(settings)

        # Fetch last 5 messages from chat history for context
        chat_history = await db.get_recent_chat_history(chat_request.session_id, limit=5)

        # Determine sources using intelligent agent
        sources, analysis = await rag_engine.determine_source(chat_request.message)

        # Check if required source is available
        is_available, unavailable_message = rag_engine.check_required_source_available(analysis)
        if not is_available:
            return {
                "response": unavailable_message,
                "sources": [],
                "context": [],
                "requires_setup": True
            }

        # Gather context
        context = await rag_engine.gather_context(chat_request.message, sources)

        # Generate response with chat history
        response_text = await rag_engine.generate_response(
            chat_request.message,
            context,
            chat_history
        )

        # Save chat history
        await db.add_chat_message(
            session_id=chat_request.session_id,
            user_message=chat_request.message,
            bot_response=response_text,
            sources=sources,
            doc_id=str(uuid.uuid4())
        )

        return {
            "response": response_text,
            "sources": sources,
            "context": context[:3]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/chat/stream")
async def chat_stream(chat_request: ChatMessage, user_id: str = "default"):
    """Process chat message with SSE streaming"""
    try:
        # Get user settings
        settings_doc = await db.get_user_settings(user_id)
        if not settings_doc or not settings_doc.get("settings"):
            raise HTTPException(status_code=400, detail="User settings not configured. Please configure your API keys in Settings.")

        settings = SettingsModel(**settings_doc["settings"])

        # Validate LLM settings
        if not settings.llm_api_key:
            raise HTTPException(status_code=400, detail="LLM API key not configured. Please add your API key in Settings.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading settings for streaming: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load settings: {str(e)}")

    async def event_stream():
        """Generate SSE events"""
        try:
            # Create RAG engine
            rag_engine = await create_rag_engine(settings)

            # Send initial event
            yield f"data: {json.dumps({'type': 'start'})}\n\n"

            # Fetch last 5 messages from chat history for context
            chat_history = await db.get_recent_chat_history(chat_request.session_id, limit=5)

            # Determine sources using intelligent agent
            sources, analysis = await rag_engine.determine_source(chat_request.message)

            # Check if required source is available
            is_available, unavailable_message = rag_engine.check_required_source_available(analysis)
            if not is_available:
                yield f"data: {json.dumps({'type': 'error', 'message': unavailable_message, 'requires_setup': True})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

            # Gather context
            context = await rag_engine.gather_context(chat_request.message, sources)

            # Extract actual sources that returned results
            used_sources = list(set(doc.get('source', 'unknown') for doc in context if doc.get('source')))

            # Build context summary for frontend (title, source, url)
            context_summary = [
                {
                    'title': doc.get('title', 'Untitled')[:100],
                    'source': doc.get('source', 'unknown'),
                    'url': doc.get('url', '')
                }
                for doc in context[:5]  # Top 5 documents
            ]

            yield f"data: {json.dumps({'type': 'context', 'count': len(context), 'used_sources': used_sources, 'documents': context_summary})}\n\n"

            # Stream response with chat history
            full_response = ""
            async for chunk in rag_engine.stream_response(chat_request.message, context, chat_history):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

            # Save to history
            await db.add_chat_message(
                session_id=chat_request.session_id,
                user_message=chat_request.message,
                bot_response=full_response,
                sources=sources,
                doc_id=str(uuid.uuid4())
            )

            # Send complete event with used sources and document references
            yield f"data: {json.dumps({'type': 'done', 'sources': sources, 'used_sources': used_sources, 'documents': context_summary})}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@api_router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """Get chat history for a session"""
    try:
        history = await db.get_chat_history(session_id, limit=100)
        return {"history": history}
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/chat/history/{session_id}")
async def clear_chat_history(session_id: str):
    """Clear chat history for a session"""
    try:
        deleted_count = await db.clear_chat_history(session_id)
        return {"status": "success", "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/debug/settings/{user_id}")
async def debug_settings(user_id: str = "default"):
    """Debug endpoint to check what settings are stored"""
    try:
        settings_doc = await db.get_user_settings(user_id)
        if settings_doc and settings_doc.get("settings"):
            s = settings_doc["settings"]
            return {
                "has_llm": bool(s.get("llm_api_key")),
                "llm_provider": s.get("llm_provider"),
                "llm_model": s.get("llm_model"),
                "has_atlassian_domain": bool(s.get("atlassian_domain")),
                "atlassian_domain": s.get("atlassian_domain"),
                "has_atlassian_email": bool(s.get("atlassian_email")),
                "has_atlassian_token": bool(s.get("atlassian_api_token")),
                "has_confluence_url": bool(s.get("confluence_url")),
                "has_jira_url": bool(s.get("jira_url")),
                "has_slack_bot_token": bool(s.get("slack_bot_token")),
                "has_slack_user_token": bool(s.get("slack_user_token")),
                "enable_web_search": s.get("enable_web_search"),
                "use_streaming": s.get("use_streaming")
            }
        return {"error": "No settings found for user"}
    except Exception as e:
        return {"error": str(e)}


@api_router.post("/test-connection")
async def test_connection(settings: SettingsModel):
    """Test API connections"""
    results = {}

    # Test LLM
    try:
        llm_router = LLMRouter(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key
        )
        response = await llm_router.chat("Say 'Connection successful'")
        results["llm"] = {"status": "success", "message": "LLM connection successful"}
    except Exception as e:
        results["llm"] = {"status": "error", "message": str(e)}

    # Test Confluence
    if settings.confluence_url and settings.confluence_username and settings.confluence_token:
        try:
            confluence = ConfluenceClient(
                url=settings.confluence_url,
                username=settings.confluence_username,
                api_token=settings.confluence_token
            )
            confluence.search_content("test", limit=1)
            results["confluence"] = {"status": "success", "message": "Confluence connection successful"}
        except Exception as e:
            results["confluence"] = {"status": "error", "message": str(e)}

    # Test Jira
    if settings.jira_url and settings.jira_username and settings.jira_token:
        try:
            jira = JiraClient(
                url=settings.jira_url,
                username=settings.jira_username,
                api_token=settings.jira_token
            )
            jira.search_issues("test", limit=1)
            results["jira"] = {"status": "success", "message": "Jira connection successful"}
        except Exception as e:
            results["jira"] = {"status": "error", "message": str(e)}

    # Test Slack
    if settings.slack_bot_token:
        try:
            slack = SlackClient(
                bot_token=settings.slack_bot_token,
                user_token=settings.slack_user_token
            )
            test_result = await slack.test_connection()
            if test_result.get("status") == "success":
                results["slack"] = {
                    "status": "success",
                    "message": f"Slack connection successful - Team: {test_result.get('team')}"
                }
            else:
                results["slack"] = {"status": "error", "message": test_result.get("error")}
        except Exception as e:
            results["slack"] = {"status": "error", "message": str(e)}

    return results


# Individual integration test endpoints
class LLMTestConfig(BaseModel):
    llm_provider: str
    llm_model: str
    llm_api_key: str


class AtlassianTestConfig(BaseModel):
    confluence_url: str
    confluence_username: str
    confluence_token: str
    jira_url: str
    jira_username: str
    jira_token: str


class SlackTestConfig(BaseModel):
    slack_bot_token: str


class GitHubTestConfig(BaseModel):
    github_token: str


class GoogleTestConfig(BaseModel):
    google_client_id: str
    google_client_secret: str


class NotionTestConfig(BaseModel):
    notion_api_key: str


class LinearTestConfig(BaseModel):
    linear_api_key: str


class Microsoft365TestConfig(BaseModel):
    ms_client_id: str
    ms_client_secret: str
    ms_tenant_id: str


class FigmaTestConfig(BaseModel):
    figma_token: str


@api_router.post("/test-integration/llm")
async def test_llm_integration(config: LLMTestConfig):
    """Test LLM provider connection"""
    try:
        llm_router = LLMRouter(
            provider=config.llm_provider,
            model=config.llm_model,
            api_key=config.llm_api_key
        )
        response = await llm_router.chat("Say 'OK'")
        return {"status": "success", "message": f"LLM connected ({config.llm_provider})"}
    except Exception as e:
        logger.error(f"LLM test failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/test-integration/atlassian")
async def test_atlassian_integration(config: AtlassianTestConfig):
    """Test Atlassian (Confluence + Jira) connection"""
    results = {}

    # Test Confluence
    try:
        confluence = ConfluenceClient(
            url=config.confluence_url,
            username=config.confluence_username,
            api_token=config.confluence_token
        )
        confluence.search_content("test", limit=1)
        results["confluence"] = "OK"
    except Exception as e:
        results["confluence"] = f"Error: {str(e)}"

    # Test Jira
    try:
        jira = JiraClient(
            url=config.jira_url,
            username=config.jira_username,
            api_token=config.jira_token
        )
        jira.search_issues("test", limit=1)
        results["jira"] = "OK"
    except Exception as e:
        results["jira"] = f"Error: {str(e)}"

    # Check if both succeeded
    if results.get("confluence") == "OK" and results.get("jira") == "OK":
        return {"status": "success", "message": "Confluence & Jira connected"}
    elif results.get("confluence") == "OK":
        return {"status": "success", "message": "Confluence connected (Jira failed)"}
    elif results.get("jira") == "OK":
        return {"status": "success", "message": "Jira connected (Confluence failed)"}
    else:
        raise HTTPException(status_code=400, detail=f"Confluence: {results.get('confluence')}, Jira: {results.get('jira')}")


@api_router.post("/test-integration/slack")
async def test_slack_integration(config: SlackTestConfig):
    """Test Slack connection"""
    try:
        slack = SlackClient(bot_token=config.slack_bot_token)
        result = await slack.test_connection()

        if result.get("status") == "success":
            return {"status": "success", "message": f"Slack connected - Team: {result.get('team', 'Unknown')}"}
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Connection failed"))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Slack test failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/test-integration/github")
async def test_github_integration(config: GitHubTestConfig):
    """Test GitHub connection"""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"token {config.github_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )

            if response.status_code == 200:
                user_data = response.json()
                return {"status": "success", "message": f"GitHub connected - User: {user_data.get('login', 'Unknown')}"}
            elif response.status_code == 401:
                raise HTTPException(status_code=400, detail="Invalid GitHub token")
            else:
                raise HTTPException(status_code=400, detail=f"GitHub API error: {response.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub test failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/test-integration/google")
async def test_google_integration(config: GoogleTestConfig):
    """Test Google OAuth credentials (validation only)"""
    # Google OAuth requires full OAuth flow, so we just validate the format
    if not config.google_client_id.endswith('.apps.googleusercontent.com'):
        raise HTTPException(status_code=400, detail="Invalid Client ID format (should end with .apps.googleusercontent.com)")

    if len(config.google_client_secret) < 10:
        raise HTTPException(status_code=400, detail="Client Secret appears too short")

    return {"status": "success", "message": "Google credentials format valid (OAuth flow required for full test)"}


@api_router.post("/test-integration/notion")
async def test_notion_integration(config: NotionTestConfig):
    """Test Notion API connection"""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.notion.com/v1/users/me",
                headers={
                    "Authorization": f"Bearer {config.notion_api_key}",
                    "Notion-Version": "2022-06-28"
                }
            )

            if response.status_code == 200:
                user_data = response.json()
                name = user_data.get("name", user_data.get("bot", {}).get("owner", {}).get("user", {}).get("name", "Unknown"))
                return {"status": "success", "message": f"Notion connected - {name}"}
            elif response.status_code == 401:
                raise HTTPException(status_code=400, detail="Invalid Notion API key")
            else:
                raise HTTPException(status_code=400, detail=f"Notion API error: {response.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Notion test failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/test-integration/linear")
async def test_linear_integration(config: LinearTestConfig):
    """Test Linear API connection"""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.linear.app/graphql",
                headers={
                    "Authorization": config.linear_api_key,
                    "Content-Type": "application/json"
                },
                json={"query": "{ viewer { id name email } }"}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("data", {}).get("viewer"):
                    viewer = data["data"]["viewer"]
                    return {"status": "success", "message": f"Linear connected - {viewer.get('name', 'Unknown')}"}
                else:
                    errors = data.get("errors", [])
                    error_msg = errors[0].get("message") if errors else "Unknown error"
                    raise HTTPException(status_code=400, detail=f"Linear error: {error_msg}")
            elif response.status_code == 401:
                raise HTTPException(status_code=400, detail="Invalid Linear API key")
            else:
                raise HTTPException(status_code=400, detail=f"Linear API error: {response.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Linear test failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/test-integration/microsoft365")
async def test_microsoft365_integration(config: Microsoft365TestConfig):
    """Test Microsoft 365 (Azure AD) credentials"""
    import httpx

    try:
        # Get OAuth token using client credentials flow
        async with httpx.AsyncClient() as client:
            token_url = f"https://login.microsoftonline.com/{config.ms_tenant_id}/oauth2/v2.0/token"
            response = await client.post(
                token_url,
                data={
                    "client_id": config.ms_client_id,
                    "client_secret": config.ms_client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials"
                }
            )

            if response.status_code == 200:
                token_data = response.json()
                if token_data.get("access_token"):
                    return {"status": "success", "message": "Microsoft 365 credentials valid"}
                else:
                    raise HTTPException(status_code=400, detail="No access token received")
            elif response.status_code == 400:
                error_data = response.json()
                error_desc = error_data.get("error_description", "Invalid credentials")
                raise HTTPException(status_code=400, detail=f"Azure AD error: {error_desc.split('.')[0]}")
            else:
                raise HTTPException(status_code=400, detail=f"Azure AD error: {response.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Microsoft 365 test failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/test-integration/figma")
async def test_figma_integration(config: FigmaTestConfig):
    """Test Figma API connection"""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.figma.com/v1/me",
                headers={
                    "X-Figma-Token": config.figma_token
                }
            )

            if response.status_code == 200:
                user_data = response.json()
                return {"status": "success", "message": f"Figma connected - {user_data.get('handle', user_data.get('email', 'Unknown'))}"}
            elif response.status_code == 403:
                raise HTTPException(status_code=400, detail="Invalid Figma token")
            else:
                raise HTTPException(status_code=400, detail=f"Figma API error: {response.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Figma test failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
