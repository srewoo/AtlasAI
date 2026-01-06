# Atlas AI - Backend Deployment Guide

This guide covers deployment strategies for the Atlas AI backend services.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Chrome Extension                              │
│                    (Deployed to Chrome Web Store)                    │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API Gateway (8001)                           │
│              services/gateway - Main entry point                     │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
┌──────────────────────────┐        ┌──────────────────────────────────┐
│    Orchestrator (8002)   │        │         Infrastructure           │
│   Coordinates services   │        │  MongoDB (27017) + Redis (6379)  │
└──────────────────────────┘        └──────────────────────────────────┘
                    │
    ┌───────┬───────┼───────┬───────┬───────┐
    ▼       ▼       ▼       ▼       ▼       ▼
┌───────┐┌───────┐┌───────┐┌───────┐┌───────┐┌───────┐
│Confl. ││ Jira  ││ Slack ││GitHub ││Google ││ ...   │
│ 8015  ││ 8016  ││ 8010  ││ 8011  ││ 8012  ││       │
└───────┘└───────┘└───────┘└───────┘└───────┘└───────┘
```

## Service Ports Reference

| Service | Port | Description |
|---------|------|-------------|
| Gateway | 8001 | Main API entry point |
| Orchestrator | 8002 | Service coordinator |
| Slack | 8010 | Slack integration |
| GitHub | 8011 | GitHub integration |
| Google | 8012 | Google Workspace |
| Notion | 8013 | Notion integration |
| Confluence | 8015 | Confluence integration |
| Jira | 8016 | Jira integration |
| Linear | 8017 | Linear integration |
| Figma | 8018 | Figma integration |
| Microsoft 365 | 8019 | Teams, SharePoint, Outlook |
| DevTools | 8025 | Stack Overflow, npm, PyPI |
| Productivity | 8026 | Local files, bookmarks |
| MongoDB | 27017 | Database |
| Redis | 6379 | Cache & rate limiting |

---

## Deployment Options

### Option 1: Docker Compose (Recommended for Development/Small Scale)

**Prerequisites:**
- Docker & Docker Compose installed
- 4GB+ RAM available

**Steps:**

```bash
# 1. Navigate to services directory
cd services

# 2. Copy and configure environment
cp .env.example .env
# Edit .env with your API keys and credentials

# 3. Start all services
docker-compose up -d

# 4. Verify services are running
docker-compose ps

# 5. Check logs
docker-compose logs -f gateway
```

**Useful Commands:**
```bash
# Stop all services
docker-compose down

# Restart specific service
docker-compose restart gateway

# View logs for specific service
docker-compose logs -f confluence

# Rebuild after code changes
docker-compose up -d --build

# Scale specific service (if needed)
docker-compose up -d --scale slack=2
```

---

### Option 2: Kubernetes (Production/Enterprise)

**Prerequisites:**
- Kubernetes cluster (EKS, GKE, AKS, or self-hosted)
- kubectl configured
- Helm (optional but recommended)

**Directory Structure:**
```
k8s/
├── namespace.yaml
├── configmap.yaml
├── secrets.yaml
├── gateway/
│   ├── deployment.yaml
│   └── service.yaml
├── orchestrator/
│   ├── deployment.yaml
│   └── service.yaml
├── integrations/
│   ├── confluence-deployment.yaml
│   ├── jira-deployment.yaml
│   └── ...
└── ingress.yaml
```

**Example Gateway Deployment (k8s/gateway/deployment.yaml):**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: atlas-gateway
  namespace: atlas-ai
spec:
  replicas: 2
  selector:
    matchLabels:
      app: atlas-gateway
  template:
    metadata:
      labels:
        app: atlas-gateway
    spec:
      containers:
      - name: gateway
        image: your-registry/atlas-gateway:latest
        ports:
        - containerPort: 8001
        env:
        - name: MONGO_URL
          valueFrom:
            secretKeyRef:
              name: atlas-secrets
              key: mongo-url
        - name: ORCHESTRATOR_URL
          value: "http://orchestrator-service:8002"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
```

**Deployment Steps:**
```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Create secrets
kubectl create secret generic atlas-secrets \
  --from-literal=mongo-url='mongodb://...' \
  --from-literal=redis-url='redis://...' \
  -n atlas-ai

# 3. Deploy infrastructure
kubectl apply -f k8s/mongodb/
kubectl apply -f k8s/redis/

# 4. Deploy services
kubectl apply -f k8s/orchestrator/
kubectl apply -f k8s/gateway/
kubectl apply -f k8s/integrations/

# 5. Configure ingress
kubectl apply -f k8s/ingress.yaml
```

---

### Option 3: Cloud Platform Services

#### AWS Deployment

**Architecture:**
- **ECS/Fargate** or **EKS** for containers
- **DocumentDB** for MongoDB
- **ElastiCache** for Redis
- **ALB** for load balancing
- **ECR** for container registry

```bash
# Build and push images to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com

docker build -t atlas-gateway services/gateway/
docker tag atlas-gateway:latest <account>.dkr.ecr.us-east-1.amazonaws.com/atlas-gateway:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/atlas-gateway:latest
```

#### Google Cloud Deployment

**Architecture:**
- **Cloud Run** or **GKE** for containers
- **MongoDB Atlas** or **Firestore** for database
- **Memorystore** for Redis
- **Cloud Load Balancing**

```bash
# Deploy to Cloud Run
gcloud run deploy atlas-gateway \
  --image gcr.io/PROJECT_ID/atlas-gateway \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars MONGO_URL=...,ORCHESTRATOR_URL=...
```

#### Azure Deployment

**Architecture:**
- **Azure Container Apps** or **AKS**
- **Cosmos DB** (MongoDB API)
- **Azure Cache for Redis**
- **Azure Front Door**

---

### Option 4: Single Server (Budget/Simple)

For small deployments on a single VPS (DigitalOcean, Linode, etc.):

```bash
# 1. SSH into server
ssh user@your-server

# 2. Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 3. Clone repository
git clone https://github.com/your-org/atlas-ai.git
cd atlas-ai/services

# 4. Configure environment
cp .env.example .env
nano .env  # Add your credentials

# 5. Start with Docker Compose
docker-compose up -d

# 6. Setup nginx reverse proxy (optional but recommended)
sudo apt install nginx
sudo nano /etc/nginx/sites-available/atlas-ai
```

**Nginx Configuration:**
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;

        # SSE support
        proxy_buffering off;
        proxy_read_timeout 86400;
    }
}
```

---

## Environment Configuration

### Required Environment Variables

```bash
# Infrastructure
MONGO_URL=mongodb://localhost:27017
DB_NAME=atlas_ai
REDIS_URL=redis://localhost:6379

# Service URLs (for Docker network)
ORCHESTRATOR_URL=http://orchestrator:8002

# CORS (update for production)
CORS_ORIGINS=chrome-extension://*,https://yourdomain.com
```

### Integration Credentials

Each integration requires specific credentials. Only configure the ones you need:

```bash
# Atlassian (Confluence + Jira)
CONFLUENCE_URL=https://your-company.atlassian.net
CONFLUENCE_USERNAME=your-email@company.com
CONFLUENCE_TOKEN=your-api-token
JIRA_URL=https://your-company.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_TOKEN=your-api-token

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# GitHub
GITHUB_TOKEN=ghp_...

# Google Workspace
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Notion
NOTION_API_KEY=secret_...

# Linear
LINEAR_API_KEY=lin_api_...

# Microsoft 365
MS_CLIENT_ID=...
MS_CLIENT_SECRET=...
MS_TENANT_ID=...

# Figma
FIGMA_TOKEN=figd_...
FIGMA_TEAM_ID=...

# Stack Overflow (optional, for higher rate limits)
STACKOVERFLOW_KEY=...
```

---

## Minimal Deployment (Gateway Only)

If you only need Confluence + Jira + Web search (no microservices):

```bash
# Use the legacy backend folder
cd backend

# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp env.template .env
# Edit .env with your credentials

# Run
uvicorn server:app --host 0.0.0.0 --port 8001
```

This runs without the orchestrator and microservices - the gateway handles everything directly.

---

## Selective Service Deployment

You don't need to deploy all services. Deploy only what you need:

```yaml
# docker-compose.override.yml - Only Atlassian + Gateway
version: '3.8'
services:
  # Disable unused services
  slack:
    profiles: ["disabled"]
  github:
    profiles: ["disabled"]
  google:
    profiles: ["disabled"]
  notion:
    profiles: ["disabled"]
  linear:
    profiles: ["disabled"]
  figma:
    profiles: ["disabled"]
  microsoft365:
    profiles: ["disabled"]
  devtools:
    profiles: ["disabled"]
  productivity:
    profiles: ["disabled"]
```

Then run:
```bash
docker-compose up -d gateway orchestrator confluence jira redis mongodb
```

---

## Health Checks & Monitoring

### Health Endpoints

```bash
# Gateway health
curl http://localhost:8001/api/health

# Orchestrator health (shows all services)
curl http://localhost:8002/health

# Individual service health
curl http://localhost:8015/health  # Confluence
curl http://localhost:8016/health  # Jira
```

### Recommended Monitoring Stack

```yaml
# Add to docker-compose.yml
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
```

---

## SSL/TLS Configuration

### Using Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d api.yourdomain.com

# Auto-renewal is configured automatically
```

### Using Cloudflare (Alternative)

1. Point DNS to your server via Cloudflare
2. Enable "Full (strict)" SSL mode
3. Cloudflare handles SSL termination

---

## Backup Strategy

### MongoDB Backup

```bash
# Manual backup
docker-compose exec mongodb mongodump --out /backup/$(date +%Y%m%d)

# Automated daily backup (add to crontab)
0 2 * * * cd /path/to/services && docker-compose exec -T mongodb mongodump --archive > /backups/atlas-$(date +\%Y\%m\%d).archive
```

### Redis Backup

Redis persistence is configured in docker-compose.yml with volume `redis_data`.

---

## Scaling Considerations

### Horizontal Scaling

| Service | Scalable? | Notes |
|---------|-----------|-------|
| Gateway | Yes | Stateless, scale behind load balancer |
| Orchestrator | Yes | Stateless |
| Integration Services | Yes | Each is stateless |
| MongoDB | Yes | Use replica set or MongoDB Atlas |
| Redis | Yes | Use Redis Cluster or ElastiCache |

### Resource Requirements

| Deployment Size | RAM | CPU | Storage |
|----------------|-----|-----|---------|
| Minimal (Gateway only) | 2GB | 1 vCPU | 10GB |
| Small (5 services) | 4GB | 2 vCPU | 20GB |
| Medium (all services) | 8GB | 4 vCPU | 50GB |
| Production | 16GB+ | 8+ vCPU | 100GB+ |

---

## Troubleshooting

### Common Issues

**1. Services can't connect to each other**
```bash
# Check Docker network
docker network ls
docker network inspect atlas_ai_network
```

**2. MongoDB connection fails**
```bash
# Check MongoDB is running
docker-compose logs mongodb

# Test connection
docker-compose exec mongodb mongosh
```

**3. Gateway can't reach orchestrator**
```bash
# Check orchestrator logs
docker-compose logs orchestrator

# Test from gateway container
docker-compose exec gateway curl http://orchestrator:8002/health
```

**4. Extension can't connect to backend**
- Verify CORS_ORIGINS includes your extension ID
- Check if firewall allows port 8001
- Verify SSL if using HTTPS

---

## Production Checklist

- [ ] All environment variables configured
- [ ] MongoDB has authentication enabled
- [ ] Redis has password set
- [ ] CORS origins restricted to extension ID
- [ ] SSL/TLS configured
- [ ] Health checks passing
- [ ] Monitoring/alerting setup
- [ ] Backup strategy in place
- [ ] Rate limiting configured
- [ ] Logs being collected
- [ ] Resource limits set for containers

---

## Support

For issues or questions:
- GitHub Issues: [Create an issue](https://github.com/your-org/atlas-ai/issues)
- Documentation: See `/docs` folder
