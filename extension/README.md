# Atlas AI - Chrome Extension

An AI-powered chatbot Chrome extension with access to Confluence, Jira, and web knowledge using an Agentic RAG system.

## Features

- **Multi-LLM Support**: Works with OpenAI, Anthropic Claude, Google Gemini, and local Ollama models
- **Confluence Integration**: Search and retrieve documentation from your Confluence workspace
- **Jira Integration**: Access and query Jira issues
- **Web Search**: Search the internet for current information
- **Agentic RAG**: Intelligent query routing to the most relevant sources
- **Fast & Efficient**: ChromaDB vector storage for quick retrieval
- **Professional UI**: Clean, modern interface following Swiss design principles

## Installation

### 1. Backend Setup

The backend server should already be running. If not:

```bash
cd /app/backend
pip install -r requirements.txt
# Backend runs on port 8001
```

### 2. Configure Backend URL

Before loading the extension, you **MUST** update the API URL in two files:

1. Open `/app/extension/popup.js` and change:
   ```javascript
   const API_URL = 'YOUR_BACKEND_URL_HERE';
   ```
   to your actual backend URL, e.g.:
   ```javascript
   const API_URL = 'http://your-backend-domain.com';
   ```

2. Open `/app/extension/settings.js` and make the same change.

### 3. Add Extension Icons

Add icon files in `/app/extension/icons/`:
- `icon16.png` (16x16px)
- `icon48.png` (48x48px)
- `icon128.png` (128x128px)

You can use any icon or generate one online.

### 4. Load Extension in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `/app/extension` directory
5. The extension should now appear in your extensions list

## Configuration

### First Time Setup

1. Click the extension icon in Chrome toolbar
2. Click "Open Settings"
3. Configure your settings:

#### Required Settings

**LLM Configuration:**
- **Provider**: Choose from OpenAI, Anthropic, Gemini, or Ollama
- **Model**: Enter the model name (e.g., `gpt-5.2`, `claude-sonnet-4-5-20250929`, `gemini-3-flash-preview`)
- **API Key**: Your API key for the chosen provider

#### Optional Integrations

**Confluence:**
- URL: Your Confluence instance URL (e.g., `https://yourcompany.atlassian.net`)
- Username: Your email address
- API Token: Generate from [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)

**Jira:**
- URL: Your Jira instance URL
- Username: Your email address
- API Token: Same as Confluence token if using Atlassian Cloud

**Web Search:**
- Enable/disable web search capability

4. Click "Test Connection" to verify your settings
5. Click "Save Settings"

## Usage

1. Click the extension icon to open the chat popup
2. Type your question in the input field
3. Press Enter or click "Send"
4. The assistant will:
   - Analyze your query
   - Determine relevant sources (Confluence, Jira, web)
   - Fetch information using RAG
   - Generate a comprehensive response
   - Show sources used

### Example Queries

- "What's the latest deployment process documentation?" (Confluence)
- "Show me open bugs assigned to John" (Jira)
- "How to implement OAuth2 in FastAPI?" (Web)
- "What's in the PROJ-123 ticket?" (Jira)

## Architecture

### Backend Components

- **FastAPI Server**: REST API endpoints
- **ChromaDB**: Vector database for RAG
- **Sentence Transformers**: Embeddings generation (all-MiniLM-L6-v2)
- **LLM Router**: Multi-provider LLM support with native APIs
- **Agentic RAG**: Intelligent query routing and context gathering

### Frontend (Extension)

- **Manifest V3**: Latest Chrome extension standard
- **Vanilla JS**: No framework dependencies
- **Chrome Storage**: Local settings persistence
- **Professional UI**: Swiss design with Manrope & Chivo fonts

## API Endpoints

- `POST /api/chat` - Send chat message
- `GET /api/chat/history/{session_id}` - Get chat history
- `DELETE /api/chat/history/{session_id}` - Clear chat history
- `POST /api/settings` - Save user settings
- `GET /api/settings/{user_id}` - Get user settings
- `POST /api/test-connection` - Test API connections

## Cost Optimization

- **Free Vector DB**: ChromaDB runs locally
- **Free Embeddings**: Using open-source sentence-transformers
- **Free Web Search**: DuckDuckGo HTML search (no API key)
- **Efficient Caching**: Vector store caches previous queries
- **You provide API key**: Use your own LLM provider

## Troubleshooting

### Extension doesn't load
- Check that you updated the API_URL in popup.js and settings.js
- Verify icon files exist
- Check Chrome DevTools console for errors

### "Settings not configured" error
- Open Settings and configure at minimum: LLM provider, model, and API key
- Click "Save Settings"

### Connection test fails
- Verify API keys are correct
- Check backend server is running
- Ensure URLs don't have trailing slashes
- For Confluence/Jira: verify you have API token (not password)

### No response from chatbot
- Check browser console for errors
- Verify backend URL is correct and accessible
- Test backend directly: `curl http://your-backend-url/api/`

## Development

### File Structure

```
/app/extension/
├── manifest.json       # Extension manifest
├── popup.html         # Main popup interface
├── popup.js           # Popup logic
├── settings.html      # Settings page
├── settings.js        # Settings logic
├── background.js      # Service worker
├── styles.css         # All styles
├── icons/            # Extension icons
└── README.md         # This file
```

### Backend Structure

```
/app/backend/
├── server.py          # FastAPI server
├── rag_engine.py      # Agentic RAG system
├── llm_router.py      # Multi-LLM support
├── vector_store.py    # ChromaDB wrapper
├── confluence_client.py
├── jira_client.py
├── web_search.py
└── requirements.txt
```

## Privacy & Security

- All settings stored locally in Chrome storage
- API keys never sent to third parties (except respective LLM providers)
- Backend can be self-hosted for complete control
- No telemetry or tracking

## License

Open source project for Atlas AI.
