# Quick Start Guide - Atlas AI

## What You Have

A complete AI-powered chatbot system with:

✅ **Backend API** (FastAPI) - Port 8001
✅ **Agentic RAG Engine** - Intelligent query routing
✅ **Multi-LLM Support** - OpenAI, Anthropic, Gemini, Ollama
✅ **Vector Database** - ChromaDB for fast retrieval
✅ **Chrome Extension** - Professional UI with Swiss design
✅ **Confluence Integration** - Search documentation
✅ **Jira Integration** - Query issues and tickets
✅ **Web Search** - DuckDuckGo integration

---

## 🚀 Quick Setup (5 Minutes)

### Option A: Docker (Recommended)

```bash
# 1. Start the backend with Docker
docker-compose up -d

# 2. Verify it's running
curl http://localhost:8001/api/

# 3. Load extension in Chrome (see Step 3 below)
```

### Option B: Manual Setup

#### Step 1: Start MongoDB

```bash
# Using Docker
docker run -d -p 27017:27017 --name atlas-mongodb mongo:7.0

# Or install locally (macOS)
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

#### Step 2: Start Backend

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Copy environment template
cp env.template .env

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

#### Step 3: Load Extension in Chrome

1. Open Chrome
2. Go to `chrome://extensions/`
3. Enable "Developer mode" (top right toggle)
4. Click "Load unpacked"
5. Select the `extension/` folder
6. Extension will appear in your toolbar!

#### Step 4: Configure Settings

1. Click the Atlas AI icon in Chrome toolbar
2. You'll be automatically redirected to Settings (first time)
3. Fill in required fields:
   - **LLM Provider**: OpenAI, Anthropic, or Gemini
   - **Model Name**: e.g., `gpt-4o`, `claude-sonnet-4-5-20250929`, `gemini-2.0-flash`
   - **API Key**: Your provider's API key
4. (Optional) Add Confluence/Jira credentials
5. Click "Test Connection"
6. Click "Save Settings"

---

## 📁 Project Structure

```
Atlas AI/
├── backend/
│   ├── server.py              # FastAPI server
│   ├── rag_engine.py          # Agentic RAG system
│   ├── llm_router.py          # Multi-LLM support
│   ├── vector_store.py        # ChromaDB wrapper
│   ├── confluence_client.py   # Confluence API
│   ├── jira_client.py         # Jira API
│   ├── web_search.py          # Web search
│   ├── requirements.txt       # Python deps
│   ├── Dockerfile             # Container config
│   └── env.template           # Environment template
│
├── extension/
│   ├── manifest.json          # Extension manifest
│   ├── config.js              # Configuration (update API_URL here!)
│   ├── popup.html/js          # Chat interface
│   ├── settings.html/js       # Settings page
│   ├── background.js          # Service worker
│   ├── styles.css             # Styling
│   └── icons/                 # Extension icons
│
├── frontend/                   # (Optional React admin dashboard)
├── docker-compose.yml          # Docker orchestration
└── docs/                       # Documentation
```

---

## 🔧 Configuration

### Backend Configuration (`backend/.env`)

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=atlas_ai_db
CORS_ORIGINS=*
LOG_LEVEL=INFO
```

### Extension Configuration (`extension/config.js`)

```javascript
const CONFIG = {
  API_URL: 'http://localhost:8001',  // Change for production
  DEFAULT_USER_ID: 'default',
  DEBUG_MODE: false
};
```

---

## 💬 Example Queries

```
"What's the deployment process?"
→ Searches Confluence for documentation

"Show me open bugs in PROJ"
→ Queries Jira for issues

"How to implement OAuth2?"
→ Searches web for tutorials

"What's in ticket AUTH-123?"
→ Gets Jira ticket details
```

---

## 🐛 Troubleshooting

### Backend won't start?
```bash
# Check MongoDB is running
docker ps | grep mongo

# Check port isn't in use
lsof -i :8001

# Check logs
docker-compose logs backend
```

### Extension not working?
1. Open Chrome DevTools (F12) on the popup
2. Check Console for errors
3. Verify backend is accessible: `curl http://localhost:8001/api/`

### "Settings not configured" error?
1. Click extension icon
2. Click "Open Settings"
3. Fill in at least: Provider, Model, API Key
4. Save Settings

---

## 📊 Architecture

```
User Query
    ↓
Chrome Extension (popup.js)
    ↓
Backend API (server.py)
    ↓
Query Analyzer (rag_engine.py)
    ↓
    ├─→ Confluence API ──┐
    ├─→ Jira API ────────┼─→ Vector Store (ChromaDB)
    └─→ Web Search ──────┘
    ↓
LLM Router (OpenAI/Anthropic/Gemini)
    ↓
Response with Source Citations
```

---

## 🔒 Security Notes

- API keys stored in Chrome's encrypted storage
- Backend should use HTTPS in production
- CORS configured for extension origins only
- No telemetry or tracking

---

## 📦 Production Deployment

See `extension/CHROME_STORE_SUBMISSION.md` for:
- Chrome Web Store submission guide
- Production backend deployment options
- Required assets and documentation

---

## 🆘 Support

- **Extension README**: `extension/README.md`
- **Full Documentation**: `PROJECT_DOCUMENTATION.md`
- **Implementation Status**: `IMPLEMENTATION_CHECKLIST.md`
- **Chrome Store Guide**: `extension/CHROME_STORE_SUBMISSION.md`

---

**Ready to start?** Run `docker-compose up -d` and load the extension! 🚀
