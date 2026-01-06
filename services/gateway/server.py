"""
Atlas AI Gateway Service
Main API gateway that coordinates with orchestrator for distributed context gathering
"""
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import json

# Import components
from llm_router import LLMRouter
from vector_store import VectorStore
from web_search import WebSearchClient
from rag_engine import AgenticRAG
from orchestrator_client import get_orchestrator_client

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'atlas_ai')]

# Create the main app
app = FastAPI(
    title="Atlas AI Gateway",
    description="API Gateway for Atlas AI Chrome Extension",
    version="2.0.0"
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Vector Store (global)
vector_store = VectorStore()


# Pydantic Models
class ChatMessage(BaseModel):
    message: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class SettingsModel(BaseModel):
    llm_provider: str
    llm_model: str
    llm_api_key: str
    # Atlassian credentials
    atlassian_domain: Optional[str] = None
    atlassian_email: Optional[str] = None
    atlassian_api_token: Optional[str] = None
    # Legacy credentials (backward compatibility)
    confluence_url: Optional[str] = None
    confluence_username: Optional[str] = None
    confluence_token: Optional[str] = None
    jira_url: Optional[str] = None
    jira_username: Optional[str] = None
    jira_token: Optional[str] = None
    # Integration toggles
    slack_bot_token: Optional[str] = None
    github_token: Optional[str] = None
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    notion_api_key: Optional[str] = None
    linear_api_key: Optional[str] = None
    ms_client_id: Optional[str] = None
    ms_client_secret: Optional[str] = None
    ms_tenant_id: Optional[str] = None
    figma_token: Optional[str] = None
    figma_team_id: Optional[str] = None
    enable_devtools: bool = True
    stackoverflow_key: Optional[str] = None
    enable_productivity: bool = True
    enable_local_files: bool = True
    enable_bookmarks: bool = True
    enable_clipboard: bool = False
    # General settings
    enable_web_search: bool = True
    use_streaming: bool = True


class ChatHistory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_message: str
    bot_response: str
    sources: List[str]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    settings: dict
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def get_enabled_services(settings: SettingsModel) -> List[str]:
    """Determine which services are enabled based on user settings"""
    services = []

    # Check Atlassian services
    has_atlassian = (
        (settings.atlassian_domain and settings.atlassian_email and settings.atlassian_api_token) or
        (settings.confluence_url and settings.confluence_username and settings.confluence_token)
    )
    if has_atlassian:
        services.extend(['confluence', 'jira'])

    # Check other integrations
    if settings.slack_bot_token:
        services.append('slack')
    if settings.github_token:
        services.append('github')
    if settings.google_client_id and settings.google_client_secret:
        services.append('google')
    if settings.notion_api_key:
        services.append('notion')
    if settings.linear_api_key:
        services.append('linear')
    if settings.ms_client_id and settings.ms_client_secret and settings.ms_tenant_id:
        services.append('microsoft365')
    if settings.figma_token:
        services.append('figma')
    if settings.enable_devtools:
        services.append('devtools')
    if settings.enable_productivity:
        services.append('productivity')

    return services


async def create_rag_engine(settings: SettingsModel) -> AgenticRAG:
    """Create RAG engine from user settings"""
    # Initialize LLM Router
    llm_router = LLMRouter(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key
    )

    # Initialize Web Search client
    web_search_client = None
    if settings.enable_web_search:
        web_search_client = WebSearchClient()
        logger.info("Web search client initialized")

    # Get enabled services
    enabled_services = get_enabled_services(settings)
    logger.info(f"Enabled services: {enabled_services}")

    # Create RAG engine with orchestrator
    rag_engine = AgenticRAG(
        vector_store=vector_store,
        llm_router=llm_router,
        orchestrator_client=get_orchestrator_client(),
        web_search_client=web_search_client,
        enabled_services=enabled_services
    )

    return rag_engine


# API Routes
@api_router.get("/")
async def root():
    return {"message": "Atlas AI Gateway is running", "version": "2.0.0"}


@api_router.get("/health")
async def health():
    """Health check endpoint"""
    orchestrator_healthy = await get_orchestrator_client().health_check()
    return {
        "status": "healthy",
        "orchestrator": "connected" if orchestrator_healthy else "disconnected",
        "database": "connected"
    }


@api_router.post("/settings")
async def save_settings(settings: SettingsModel, user_id: str = "default"):
    """Save user settings"""
    try:
        settings_doc = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "settings": settings.model_dump(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        await db.user_settings.update_one(
            {"user_id": user_id},
            {"$set": settings_doc},
            upsert=True
        )

        return {"status": "success", "message": "Settings saved successfully"}
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/settings/{user_id}")
async def get_settings(user_id: str = "default"):
    """Get user settings"""
    try:
        settings_doc = await db.user_settings.find_one({"user_id": user_id}, {"_id": 0})
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
        settings_doc = await db.user_settings.find_one({"user_id": user_id}, {"_id": 0})
        if not settings_doc or not settings_doc.get("settings"):
            raise HTTPException(status_code=400, detail="User settings not configured.")

        settings = SettingsModel(**settings_doc["settings"])
        rag_engine = await create_rag_engine(settings)

        # Fetch chat history
        chat_history = await db.chat_history.find(
            {"session_id": chat_request.session_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(5).to_list(5)
        chat_history.reverse()

        # Process query
        sources = await rag_engine.determine_source(chat_request.message)
        context = await rag_engine.gather_context(chat_request.message, sources)
        response_text = await rag_engine.generate_response(
            chat_request.message, context, chat_history
        )

        # Save history
        history = {
            "id": str(uuid.uuid4()),
            "session_id": chat_request.session_id,
            "user_message": chat_request.message,
            "bot_response": response_text,
            "sources": sources,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.chat_history.insert_one(history)

        return {
            "response": response_text,
            "sources": sources,
            "context": context[:3]
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/chat/stream")
async def chat_stream(chat_request: ChatMessage, user_id: str = "default"):
    """Process chat message with SSE streaming"""
    settings_doc = await db.user_settings.find_one({"user_id": user_id}, {"_id": 0})
    if not settings_doc or not settings_doc.get("settings"):
        raise HTTPException(status_code=400, detail="User settings not configured.")

    settings = SettingsModel(**settings_doc["settings"])

    async def event_stream():
        try:
            rag_engine = await create_rag_engine(settings)
            yield f"data: {json.dumps({'type': 'start'})}\n\n"

            # Fetch chat history
            chat_history = await db.chat_history.find(
                {"session_id": chat_request.session_id},
                {"_id": 0}
            ).sort("timestamp", -1).limit(5).to_list(5)
            chat_history.reverse()

            # Determine sources
            sources = await rag_engine.determine_source(chat_request.message)
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

            # Gather context
            context = await rag_engine.gather_context(chat_request.message, sources)

            # Extract used sources
            used_sources = list(set(doc.get('source', 'unknown') for doc in context if doc.get('source')))
            context_summary = [
                {
                    'title': doc.get('title', 'Untitled')[:100],
                    'source': doc.get('source', 'unknown'),
                    'url': doc.get('url', '')
                }
                for doc in context[:5]
            ]

            yield f"data: {json.dumps({'type': 'context', 'count': len(context), 'used_sources': used_sources, 'documents': context_summary})}\n\n"

            # Stream response
            full_response = ""
            async for chunk in rag_engine.stream_response(chat_request.message, context, chat_history):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

            # Save history
            history = {
                "id": str(uuid.uuid4()),
                "session_id": chat_request.session_id,
                "user_message": chat_request.message,
                "bot_response": full_response,
                "sources": sources,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await db.chat_history.insert_one(history)

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
        history = await db.chat_history.find(
            {"session_id": session_id},
            {"_id": 0}
        ).sort("timestamp", 1).to_list(100)

        for item in history:
            if isinstance(item.get('timestamp'), str):
                item['timestamp'] = datetime.fromisoformat(item['timestamp'])

        return {"history": history}
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/chat/history/{session_id}")
async def clear_chat_history(session_id: str):
    """Clear chat history for a session"""
    try:
        result = await db.chat_history.delete_many({"session_id": session_id})
        return {"status": "success", "deleted_count": result.deleted_count}
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/services")
async def list_services():
    """List all available integration services and their status"""
    try:
        return await get_orchestrator_client().get_services_status()
    except Exception as e:
        logger.error(f"Error getting services: {e}")
        return {}


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
        await llm_router.chat("Say 'Connection successful'")
        results["llm"] = {"status": "success", "message": "LLM connection successful"}
    except Exception as e:
        results["llm"] = {"status": "error", "message": str(e)}

    # Test Orchestrator
    try:
        orchestrator = get_orchestrator_client()
        if await orchestrator.health_check():
            results["orchestrator"] = {"status": "success", "message": "Orchestrator connected"}
        else:
            results["orchestrator"] = {"status": "error", "message": "Orchestrator not reachable"}
    except Exception as e:
        results["orchestrator"] = {"status": "error", "message": str(e)}

    return results


@api_router.get("/debug/settings/{user_id}")
async def debug_settings(user_id: str = "default"):
    """Debug endpoint to check stored settings"""
    try:
        settings_doc = await db.user_settings.find_one({"user_id": user_id}, {"_id": 0})
        if settings_doc and settings_doc.get("settings"):
            s = settings_doc["settings"]
            return {
                "has_llm": bool(s.get("llm_api_key")),
                "llm_provider": s.get("llm_provider"),
                "llm_model": s.get("llm_model"),
                "has_atlassian": bool(s.get("atlassian_domain")),
                "enabled_services": get_enabled_services(SettingsModel(**s)),
                "enable_web_search": s.get("enable_web_search"),
                "use_streaming": s.get("use_streaming")
            }
        return {"error": "No settings found for user"}
    except Exception as e:
        return {"error": str(e)}


# Include the router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    client.close()
    await get_orchestrator_client().close()
