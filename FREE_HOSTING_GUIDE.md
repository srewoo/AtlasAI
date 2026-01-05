# Atlas AI - Free Hosting Guide

## 🎯 Recommended: Fly.io (Best Free Option)

### Why Fly.io?
- ✅ 3GB RAM free (enough for sentence-transformers)
- ✅ Persistent storage (1GB free for ChromaDB)
- ✅ No spin-down issues
- ✅ Fast response times
- ✅ Easy deployment

### Setup Steps

#### 1. Install Fly CLI

```bash
# macOS/Linux
curl -L https://fly.io/install.sh | sh

# Windows (PowerShell)
iwr https://fly.io/install.ps1 -useb | iex
```

#### 2. Sign Up & Login

```bash
fly auth signup  # Create account
fly auth login   # Or login if you have account
```

#### 3. Prepare Backend

Create `fly.toml` in the backend directory:

```toml
# fly.toml
app = "atlas-ai-backend"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  PORT = "8001"
  DB_NAME = "atlas_ai_db"
  CORS_ORIGINS = "*"

[http_service]
  internal_port = 8001
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 1024
```

#### 4. Deploy

```bash
cd backend

# Create Fly app
fly launch --no-deploy

# Create persistent volume for ChromaDB
fly volumes create chroma_data --size 1 --region ord

# Add MongoDB (Free 256MB from Fly)
fly postgres create --name atlas-ai-db --vm-size shared-cpu-1x --volume-size 1

# Get MongoDB connection string
fly postgres attach atlas-ai-db

# Deploy
fly deploy

# Get your backend URL
fly status
# URL will be: https://atlas-ai-backend.fly.dev
```

#### 5. Update Extension Config

```javascript
// extension/config.js
const CONFIG = {
  API_URL: 'https://atlas-ai-backend.fly.dev',
  // ...
};
```

---

## 🔄 Alternative: Render.com + Keep-Alive

### Setup

#### 1. Create `render.yaml`

```yaml
services:
  - type: web
    name: atlas-ai-backend
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn server:app --host 0.0.0.0 --port 8000"
    envVars:
      - key: MONGO_URL
        value: mongodb+srv://your-mongodb-atlas-connection
      - key: DB_NAME
        value: atlas_ai_db
      - key: CORS_ORIGINS
        value: "*"
    disk:
      name: chroma-data
      mountPath: /app/chroma_db
      sizeGB: 1

databases:
  - name: atlas-mongodb
    databaseName: atlas_ai_db
    user: atlas_user
```

#### 2. Deploy to Render

1. Go to https://render.com
2. Connect your GitHub repo
3. Create new "Web Service"
4. Select the backend directory
5. Deploy!

#### 3. Keep-Alive Solution

**Problem:** Free tier spins down after 15 min inactivity.

**Solution:** Use a free cron service to ping your backend.

##### Option A: UptimeRobot (Recommended)

1. Sign up at https://uptimerobot.com (free)
2. Add new monitor:
   - Type: HTTP(s)
   - URL: `https://your-app.onrender.com/api/`
   - Monitoring interval: 5 minutes
3. Done! Your backend will never sleep.

##### Option B: Cron-job.org

1. Sign up at https://cron-job.org
2. Create new cron job:
   - URL: `https://your-app.onrender.com/api/`
   - Interval: Every 14 minutes
3. Enable and save.

---

## 📊 Free Tier Comparison

| Provider | RAM | Storage | Sleep? | Bandwidth | Cold Start |
|----------|-----|---------|--------|-----------|------------|
| **Fly.io** | 3GB (shared) | 1GB | ❌ No | 160GB | None |
| **Render.com** | 512MB | 1GB | ⚠️ Yes (15min) | 100GB | 30-60s |
| **Railway** | ❌ No free tier | - | - | - | - |
| **Replit** | 0.5GB | 1GB | ⚠️ Yes | Limited | 5-10s |
| **Google Cloud Run** | 1GB | ❌ No persistent | ⚠️ Yes | 2M reqs | 2-5s |

---

## 💾 Free MongoDB Options

### Option 1: MongoDB Atlas (Recommended)

**Free Tier:**
- 512MB storage
- Shared cluster
- No credit card required

**Setup:**
```bash
# 1. Sign up at https://www.mongodb.com/cloud/atlas
# 2. Create free cluster (M0)
# 3. Create database user
# 4. Get connection string
# 5. Update .env:

MONGO_URL=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
```

### Option 2: Fly.io Postgres

Fly offers free Postgres, but you'd need to adapt the code (currently uses MongoDB).

---

## 🔧 Optimizations for Free Hosting

### 1. Reduce Memory Usage

**Optimize sentence-transformers model:**

```python
# vector_store.py
# Use smaller model on free tier
self.embedding_model = SentenceTransformer(
    'all-MiniLM-L6-v2',
    device='cpu'  # Force CPU to save GPU resources
)
```

### 2. Lazy Load ChromaDB

```python
# Initialize only when needed
def __init__(self):
    self._collection = None

@property
def collection(self):
    if self._collection is None:
        self._collection = self.client.get_or_create_collection(...)
    return self._collection
```

### 3. Add Health Check Endpoint

Already exists at `/api/` but optimize it:

```python
@api_router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
```

---

## 📦 Complete Free Stack

### Backend: Fly.io
- **Cost:** $0/month
- **Setup time:** 15 minutes
- **Performance:** Good

### Database: MongoDB Atlas
- **Cost:** $0/month (512MB)
- **Setup time:** 5 minutes
- **Reliability:** Excellent

### Extension: Chrome Web Store
- **Cost:** $5 one-time
- **Distribution:** Free forever
- **Users:** Unlimited

### **Total Monthly Cost: $0** 🎉

---

## ⚠️ Free Tier Limitations

### What Works Well:
- ✅ Small to medium usage (< 100 queries/day)
- ✅ Personal use or small team
- ✅ Development/testing
- ✅ MVP/proof of concept

### What Might Not Work:
- ❌ High traffic (1000+ queries/day)
- ❌ Large vector database (> 1GB)
- ❌ Enterprise SLA requirements
- ❌ Multiple concurrent users

### When to Upgrade:
- Backend response time > 3 seconds
- Storage exceeding free limits
- Need guaranteed uptime
- More than 10 active users

---

## 🚀 Deployment Script

Save as `deploy-free.sh`:

```bash
#!/bin/bash

echo "🚀 Atlas AI - Free Deployment"

# Check if Fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo "Installing Fly CLI..."
    curl -L https://fly.io/install.sh | sh
fi

# Login to Fly
fly auth login

# Navigate to backend
cd backend

# Deploy
fly launch --name atlas-ai-backend --region ord --yes

# Create volume
fly volumes create chroma_data --size 1

# Deploy
fly deploy

# Get URL
echo "✅ Backend deployed!"
echo "Your API URL: https://atlas-ai-backend.fly.dev"
echo ""
echo "📝 Next steps:"
echo "1. Update extension/config.js with your API URL"
echo "2. Set up MongoDB Atlas (free): https://www.mongodb.com/cloud/atlas"
echo "3. Add MongoDB URL to Fly secrets: fly secrets set MONGO_URL=..."
echo "4. Load extension in Chrome"
```

Make executable:
```bash
chmod +x deploy-free.sh
./deploy-free.sh
```

---

## 🎓 Summary

**Recommendation for FREE hosting:**

1. **Backend:** Fly.io (best free tier, no sleep)
2. **Database:** MongoDB Atlas (512MB free)
3. **Extension:** Chrome Web Store ($5 one-time)

**Total cost: $5 one-time + $0/month ongoing** ✅

**Good for:**
- Personal projects
- Small teams (< 20 users)
- MVPs and demos
- Development/testing

**Upgrade when:**
- Need better performance
- Higher traffic
- Require SLAs
- Storage > 1GB

Would you like help setting up any of these free options?

