#!/bin/bash

# Atlas AI - Local Development Startup Script

echo "🚀 Starting Atlas AI Backend Locally"
echo "====================================="
echo ""

# Navigate to backend directory
cd "$(dirname "$0")/backend"

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << 'EOF'
MONGO_URL=mongodb+srv://atlasai_user:IuWbj46v8o0RREc0@atlasai.4rg7ntu.mongodb.net/?appName=AtlasAI
DB_NAME=atlas_ai_db
CORS_ORIGINS=*
LOG_LEVEL=INFO
EOF
    echo "✅ .env file created"
fi

# Check Python version
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
echo "📍 Using Python $PYTHON_VERSION"
echo ""

# Remove old venv if it exists (to ensure clean install)
if [ -d "venv" ]; then
    echo "🗑️  Removing old virtual environment..."
    rm -rf venv
fi

# Create fresh virtual environment
echo "📦 Creating Python virtual environment..."
$PYTHON_CMD -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --quiet --upgrade pip

# Install dependencies
echo "📥 Installing dependencies (this will take 2-3 minutes)..."
echo "   - FastAPI & Uvicorn..."
pip install --quiet fastapi uvicorn[standard] python-multipart python-dotenv

echo "   - Database drivers..."
pip install --quiet motor pymongo

echo "   - LLM APIs..."
pip install --quiet openai anthropic google-generativeai

echo "   - Semantic search (this is the big one)..."
pip install --quiet chromadb sentence-transformers

echo "   - Atlassian & Web scraping..."
pip install --quiet atlassian-python-api beautifulsoup4 requests aiohttp

echo "   - Data processing..."
pip install --quiet pydantic python-dateutil

echo ""
echo "✅ All dependencies installed!"
echo ""

# Start the server
echo "🚀 Starting FastAPI server..."
echo "================================================"
echo "📍 Backend: http://localhost:8001"
echo "📊 API docs: http://localhost:8001/docs"
echo "📝 OpenAPI: http://localhost:8001/openapi.json"
echo "================================================"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run without reload for stability
uvicorn server:app --host 0.0.0.0 --port 8001
