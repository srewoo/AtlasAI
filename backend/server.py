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

# Import RAG components
from llm_router import LLMRouter
from vector_store import VectorStore
from confluence_client import ConfluenceClient
from jira_client import JiraClient
from web_search import WebSearchClient
from rag_engine import AgenticRAG

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

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

    # Initialize Web Search client
    web_search_client = None
    if settings.enable_web_search:
        web_search_client = WebSearchClient()
        logger.info("Web search client initialized")

    # Create RAG engine
    rag_engine = AgenticRAG(
        vector_store=vector_store,
        llm_router=llm_router,
        confluence_client=confluence_client,
        jira_client=jira_client,
        web_search_client=web_search_client
    )

    return rag_engine

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Chatbot API is running"}

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
        
        # Update or insert settings
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
        # Get user settings
        settings_doc = await db.user_settings.find_one({"user_id": user_id}, {"_id": 0})
        if not settings_doc or not settings_doc.get("settings"):
            raise HTTPException(status_code=400, detail="User settings not configured. Please configure settings first.")

        settings = SettingsModel(**settings_doc["settings"])

        # Create RAG engine
        rag_engine = await create_rag_engine(settings)

        # Fetch last 5 messages from chat history for context
        chat_history = await db.chat_history.find(
            {"session_id": chat_request.session_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(5).to_list(5)

        # Reverse to get chronological order
        chat_history.reverse()

        # Determine sources
        sources = await rag_engine.determine_source(chat_request.message)

        # Gather context
        context = await rag_engine.gather_context(chat_request.message, sources)

        # Generate response with chat history
        response_text = await rag_engine.generate_response(
            chat_request.message,
            context,
            chat_history
        )

        # Save chat history
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

    # Get user settings
    settings_doc = await db.user_settings.find_one({"user_id": user_id}, {"_id": 0})
    if not settings_doc or not settings_doc.get("settings"):
        raise HTTPException(status_code=400, detail="User settings not configured.")

    settings = SettingsModel(**settings_doc["settings"])

    async def event_stream():
        """Generate SSE events"""
        try:
            # Create RAG engine
            rag_engine = await create_rag_engine(settings)

            # Send initial event
            yield f"data: {json.dumps({'type': 'start'})}\n\n"

            # Fetch last 5 messages from chat history for context
            chat_history = await db.chat_history.find(
                {"session_id": chat_request.session_id},
                {"_id": 0}
            ).sort("timestamp", -1).limit(5).to_list(5)

            # Reverse to get chronological order
            chat_history.reverse()

            # Determine sources
            sources = await rag_engine.determine_source(chat_request.message)
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
            history = {
                "id": str(uuid.uuid4()),
                "session_id": chat_request.session_id,
                "user_message": chat_request.message,
                "bot_response": full_response,
                "sources": sources,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await db.chat_history.insert_one(history)

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
        history = await db.chat_history.find(
            {"session_id": session_id},
            {"_id": 0}
        ).sort("timestamp", 1).to_list(100)
        
        # Convert ISO strings back to datetime
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

@api_router.get("/debug/settings/{user_id}")
async def debug_settings(user_id: str = "default"):
    """Debug endpoint to check what settings are stored"""
    try:
        settings_doc = await db.user_settings.find_one({"user_id": user_id}, {"_id": 0})
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
    
    return results

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
