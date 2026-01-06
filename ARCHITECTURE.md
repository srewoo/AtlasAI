# Atlas AI - Microservices Architecture

## Overview

Modern microservices architecture with independent services for each integration, designed for scalability, fault tolerance, and optimal performance.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Chrome Extension (Frontend)                          │
│                              SSE Streaming                                   │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API Gateway (Port 8001)                           │
│                    FastAPI + Rate Limiting + Auth + CORS                     │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
            ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
            │ Orchestrator│  │  RAG Core   │  │    Auth     │
            │   Service   │  │   Service   │  │   Service   │
            └──────┬──────┘  └──────┬──────┘  └─────────────┘
                   │                │
                   │         ┌──────┴──────┐
                   │         ▼             ▼
                   │   ┌──────────┐  ┌──────────┐
                   │   │  Vector  │  │   LLM    │
                   │   │  Store   │  │  Router  │
                   │   │ (Chroma) │  │(Parallel)│
                   │   └──────────┘  └──────────┘
                   │
    ┌──────────────┼──────────────────────────────────────────┐
    │              │        Redis Message Queue               │
    │              │        (Pub/Sub + Caching)               │
    └──────────────┼──────────────────────────────────────────┘
                   │
    ┌──────────────┴──────────────────────────────────────────┐
    │                  Integration Services                    │
    │  ┌─────────┬─────────┬─────────┬─────────┬─────────┐   │
    │  │  Slack  │ GitHub  │ Google  │ Notion  │  Email  │   │
    │  │  :8010  │  :8011  │  :8012  │  :8013  │  :8014  │   │
    │  ├─────────┼─────────┼─────────┼─────────┼─────────┤   │
    │  │Confluenc│  Jira   │ Linear  │  Figma  │  Teams  │   │
    │  │  :8015  │  :8016  │  :8017  │  :8018  │  :8019  │   │
    │  ├─────────┼─────────┼─────────┼─────────┼─────────┤   │
    │  │Zendesk  │ Asana   │ Trello  │ PagerDty│ Calendar│   │
    │  │  :8020  │  :8021  │  :8022  │  :8023  │  :8024  │   │
    │  └─────────┴─────────┴─────────┴─────────┴─────────┘   │
    └─────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Rate Limiting Strategy
- **Token Bucket Algorithm** per service
- **Sliding Window** for API quotas
- **Backoff & Retry** with exponential delays
- **Circuit Breaker** pattern for failing services

### 2. LLM Token Management
- **Chunked Processing**: Split large documents into optimal chunks (512-1024 tokens)
- **Parallel Embedding**: Generate embeddings in parallel batches
- **Context Window Management**: Intelligent truncation to stay within limits
- **Token Counting**: Pre-calculate tokens before API calls

### 3. Caching Layers
- **L1 Cache**: In-memory (per service) - 5 min TTL
- **L2 Cache**: Redis (shared) - 1 hour TTL
- **L3 Cache**: Vector Store (persistent)

### 4. Parallel Processing
- **Concurrent Service Queries**: Query all relevant services simultaneously
- **Streaming Aggregation**: Stream results as they arrive
- **Priority Queuing**: High-priority queries bypass queue

## Service Communication

```
┌─────────────┐     HTTP/REST      ┌─────────────┐
│   Gateway   │ ◄────────────────► │  Services   │
└─────────────┘                    └─────────────┘
       │                                  │
       │        Redis Pub/Sub             │
       └──────────────────────────────────┘
```

## Directory Structure

```
services/
├── gateway/                 # API Gateway (main entry point)
│   ├── main.py
│   ├── routes/
│   ├── middleware/
│   └── Dockerfile
├── orchestrator/           # Query orchestration
│   ├── main.py
│   ├── parallel_executor.py
│   └── Dockerfile
├── rag-core/               # RAG engine + Vector store
│   ├── main.py
│   ├── vector_store.py
│   ├── llm_router.py
│   └── Dockerfile
├── integrations/           # Integration services
│   ├── base/               # Base service template
│   │   ├── base_service.py
│   │   ├── rate_limiter.py
│   │   ├── cache.py
│   │   └── circuit_breaker.py
│   ├── slack/
│   ├── github/
│   ├── google/
│   ├── notion/
│   ├── confluence/
│   ├── jira/
│   ├── linear/
│   ├── figma/
│   ├── teams/
│   ├── zendesk/
│   ├── asana/
│   ├── trello/
│   ├── pagerduty/
│   └── calendar/
├── shared/                 # Shared utilities
│   ├── models/
│   ├── utils/
│   └── config/
├── docker-compose.yml
├── docker-compose.dev.yml
└── .env.example
```

## Environment Variables

```env
# Gateway
GATEWAY_PORT=8001
CORS_ORIGINS=*

# Redis
REDIS_URL=redis://localhost:6379

# MongoDB
MONGO_URL=mongodb://localhost:27017
DB_NAME=atlas_ai

# LLM Providers
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=

# Integration APIs
SLACK_BOT_TOKEN=
SLACK_APP_TOKEN=
GITHUB_TOKEN=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
NOTION_API_KEY=
CONFLUENCE_URL=
CONFLUENCE_USERNAME=
CONFLUENCE_TOKEN=
JIRA_URL=
JIRA_USERNAME=
JIRA_TOKEN=
LINEAR_API_KEY=
FIGMA_TOKEN=
MS_CLIENT_ID=
MS_CLIENT_SECRET=
ZENDESK_SUBDOMAIN=
ZENDESK_EMAIL=
ZENDESK_TOKEN=
ASANA_TOKEN=
TRELLO_API_KEY=
TRELLO_TOKEN=
PAGERDUTY_TOKEN=
```

## Scaling Strategy

### Horizontal Scaling
- Each service can be scaled independently
- Load balancer distributes requests
- Redis handles session affinity

### Vertical Scaling
- Increase resources for heavy services (LLM, Vector Store)
- GPU support for local embeddings

## Health & Monitoring

Each service exposes:
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed status with dependencies
- `GET /metrics` - Prometheus metrics

## Development

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up gateway orchestrator slack-service

# Development mode (hot reload)
docker-compose -f docker-compose.dev.yml up
```

## Production Deployment

```bash
# Build all images
docker-compose build

# Deploy with scaling
docker-compose up -d --scale slack-service=3 --scale github-service=2
```
