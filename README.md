# Hermes V2 — AI UPSC Mentor Platform

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.138-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.6-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![Tests](https://img.shields.io/badge/tests-199%20passed-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-10%20containers-blue.svg)](https://www.docker.com/)

AI-powered answer generation and learning platform for UPSC Civil Services Examination. Generates structured, examiner-quality answers using LangGraph + OWL Alpha model, with full student profile management, study planning, revision, and analytics.

## ✨ Features

### Core Answer Generation
- **8-Stage Pipeline**: Intent → Retrieval → Blueprint → Planning → Drafting → Review → Verification → Confidence
- **Domain Classification**: Polity, Economy, History, Geography, Ethics, Science-Tech, Environment, IR, Society
- **UPSC Blueprint**: Structured answer plans with sections, examples, must-include items
- **Multi-Reviewer**: 10-dimension scoring (accuracy, structure, coverage, examples, etc.)
- **Evidence Verification**: Claim checking against retrieved evidence
- **Hallucination Detection**: Identifies unsupported claims
- **Chain-of-Thought Trace**: Full reasoning trace for every answer

### Student Platform
- **Student Profiles**: Registration, authentication (JWT), profile management
- **Topic Mastery**: State machine (NOT_STARTED → LEARNING → PRACTICED → MASTERED → REVISION_DUE)
- **Study Planner**: Phase-based daily plans (foundation/consolidation/revision)
- **Revision Engine**: Spaced repetition with SM-2 algorithm
- **Notes Generator**: Auto-generates notes, flashcards, mindmaps
- **Mock Tests**: Generate and evaluate practice tests
- **Interview Prep**: Mock interview with personality/leadership questions
- **Current Affairs**: Daily digest, monthly compilation, topic-wise mapping
- **Analytics Dashboard**: Progress tracking, weak topic detection, monthly reports

### Infrastructure
- **10 Docker Containers**: Backend, Frontend, PostgreSQL, Redis, Qdrant, Neo4j, Traefik, MinIO, Celery Worker, Celery Beat
- **GPU Support**: NVIDIA RTX 3050+ for embeddings
- **Async Throughout**: Full async/await for high performance
- **Security**: JWT auth, input sanitization, rate limiting, security headers
- **Event Bus**: Redis Pub/Sub for inter-module communication

## 🚀 Quick Start

### Option 1: One-Click Setup (Recommended)

**Windows (PowerShell):**
```powershell
git clone https://github.com/yourusername/hermes-v2.git
cd hermes-v2
.\start.ps1
```

**Linux / macOS (Bash):**
```bash
git clone https://github.com/yourusername/hermes-v2.git
cd hermes-v2
chmod +x scripts/*.sh
./scripts/setup.sh
```

This automatically:
- ✅ Checks Docker is installed and running
- ✅ Creates `.env` from `.env.example`
- ✅ Creates all required directories
- ✅ Pulls and builds all 10 containers
- ✅ Waits for health checks
- ✅ Runs all 199 tests

### Option 2: Manual Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/hermes-v2.git
cd hermes-v2

# Set up environment
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# Start all services (10 Docker containers)
docker compose up -d

# Run tests
docker exec hermes_backend python3 -m pytest tests/ -v
```

### Useful Commands

| Command | Description |
|---------|-------------|
| `.\start.ps1` (Win) / `./scripts/setup.sh` (Linux) | Start everything |
| `.\stop.ps1` (Win) / `./scripts/stop.sh` (Linux) | Stop all services |
| `.\health.ps1` (Win) / `./scripts/health.sh` (Linux) | Check health |
| `docker exec hermes_backend python3 -m pytest tests/ -v` | Run tests |
| `docker logs hermes_backend` | View backend logs |
| `docker compose down -v` | Remove all data |

### Access Points

| Service | URL |
|---------|-----|
| API | http://localhost:8000/api |
| API Docs | http://localhost:8000/api/docs |
| Traefik Dashboard | http://localhost:8080 |
| MinIO Console | http://localhost:9001 |
| Frontend | http://localhost:5173 |

> **First time?** The initial build takes 5-10 minutes. Subsequent starts are under 30 seconds.
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/answer` | POST | Generate UPSC answer (8-stage pipeline) |
| `/api/student/register` | POST | Register new student |
| `/api/student/login` | POST | Login (returns JWT) |
| `/api/student/profile/{id}` | GET | Get profile |
| `/api/student/dashboard/{id}` | GET | Dashboard data |
| `/api/student/study-plan/{id}` | GET | Daily study plan |
| `/api/student/revision-due/{id}` | GET | Topics due for revision |
| `/api/student/mock-tests/generate` | GET | Generate mock test |
| `/api/student/notes/generate` | POST | Generate notes/flashcards |
| `/api/student/interview/mock` | GET | Mock interview |
| `/api/student/current-affairs/daily` | GET | Daily current affairs |
| `/api/health` | GET | Health check |

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           HERMES V2 — AI UPSC MENTOR                    │
│                     Complete Answer Generation Platform                 │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────────┐
│   FRONTEND  │────▶│   TRAEFIK   │────▶│         BACKEND (FastAPI)       │
│  React+Vite │     │  :80 / :8080│     │            :8000                │
│  :5173      │     │  API Gateway│     │                                 │
└─────────────┘     └─────────────┘     └──────────┬──────────────────────┘
                                                   │
                    ┌──────────────────────────────┼──────────────────────────────┐
                    │                              │                              │
                    ▼                              ▼                              ▼
          ┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
          │  LLM GATEWAY    │          │   EVENT BUS     │          │  TASK WORKERS   │
          │  (LiteLLM)      │          │   (Redis)       │          │  (Celery)       │
          │  OWL Alpha      │          │   Pub/Sub       │          │  Worker + Beat  │
          └─────────────────┘          └─────────────────┘          └─────────────────┘
                    │                              │                              │
                    └──────────────────────────────┼──────────────────────────────┘
                                                   │
          ┌────────────────────────────────────────┼────────────────────────────────────────┐
          │                                        │                                        │
          ▼                                        ▼                                        ▼
┌─────────────────┐                    ┌─────────────────┐                    ┌─────────────────┐
│   PostgreSQL    │                    │    Qdrant       │                    │    Neo4j        │
│   (State)       │                    │    (Vectors)    │                    │    (Graph)      │
│   :5432         │                    │    :6333        │                    │    :7687        │
│                 │                    │                 │                    │                 │
│  • Students     │                    │  • Embeddings   │                    │  • Knowledge    │
│  • Progress     │                    │  • Semantic     │                    │  • Relations    │
│  • Study Plans  │                    │    Search       │                    │  • Citations    │
│  • Revisions    │                    │                 │                    │                 │
│  • Mock Tests   │                    │                 │                    │                 │
└─────────────────┘                    └─────────────────┘                    └─────────────────┘
          │                                        │                                        │
          └────────────────────────────────────────┼────────────────────────────────────────┘
                                                   │
                                                   ▼
                                        ┌─────────────────┐
                                        │    MinIO        │
                                        │    (Storage)    │
                                        │    :9000        │
                                        │                 │
                                        │  • Datasets     │
                                        │  • Documents    │
                                        │  • Exports      │
                                        └─────────────────┘
```

### Answer Generation Pipeline (8 Stages)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        ANSWER GENERATION PIPELINE                                    │
│                                                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐          │
│  │ 1. INTENT│──▶│2.RETRIEVE│──▶│3.BLUEPRINT│──▶│4. PLAN   │──▶│5. DRAFT  │          │
│  │          │   │          │   │          │   │          │   │          │          │
│  │ • Domain │   │ • Qdrant │   │ • Sections│  │ • Framework│ │ • Section │          │
│  │ • Type   │   │ • BM25   │   │ • Examples│  │ • Persona │   │   Writing │          │
│  │ • Entities│  │ • Neo4j  │   │ • Word    │   │ • Trap    │   │ • Evidence│          │
│  │ • Weight │   │ • Hybrid │   │   Alloc   │   │ • Differ. │   │   Integr. │          │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └────┬─────┘          │
│                                                                     │                │
│                                                                     ▼                │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────────────┐        │
│  │6. REVIEW │──▶│7. REVISE │──▶│8. VERIFY │──▶│   CONFIDENCE ESTIMATOR   │        │
│  │          │   │          │   │          │   │                          │        │
│  │ • 10-dim │   │ • MISSING │   │ • Claims │   │  • Overall Score (0-1)   │        │
│  │   Scores │   │ • WEAK   │   │ • Evidence│  │  • Verification Pass     │        │
│  │ • Weight │   │ • IMPROVE │   │ • Halluc.│   │  • Blueprint Match       │        │
│  │   Average│   │ • Priority│   │ • Guard  │   │  • Final Confidence      │        │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────────────────┘        │
│                                                                     │                │
│  ┌──────────────────────────────────────────────────────────────────┘                │
│  │                                                                                   │
│  │  ┌─────────────────────────────────────────────────────────────────┐              │
│  │  │                    REFLECTION LOOP                              │              │
│  │  │  Score < 0.75? → Revise → Re-draft → Re-review → Re-verify    │              │
│  │  │  Score >= 0.75? → Finalize → Output                            │              │
│  │  │  Max 1 revision (configurable)                                 │              │
│  │  └─────────────────────────────────────────────────────────────────┘              │
│  └───────────────────────────────────────────────────────────────────────────────────│
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
                    ┌─────────────────────────────────────────────────────┐
                    │                  DATA FLOW                          │
                    └─────────────────────────────────────────────────────┘

    User Question
         │
         ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ Intent  │───▶│Retrieval│───▶│ Blueprint│───▶│ Planner │
    │Classifier│   │(Qdrant+ │    │(UPSC    │    │(Strategy│
    │         │    │ BM25+   │    │ Structure│   │ + Dimensions)
    │         │    │ Neo4j)  │    │ Plan)   │    │         │
    └─────────┘    └─────────┘    └─────────┘    └─────────┘
                                                       │
                                                       ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │Confidence│◀──│ Verify  │◀──│ Review  │◀──│ Draft   │
    │Estimator│    │(Claims+ │    │(10-dim  │    │(Section │
    │         │    │ Evidence)│    │ Scores) │    │ Writing)│
    └────┬────┘    └─────────┘    └─────────┘    └─────────┘
         │
         ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    FINAL OUTPUT                             │
    │  • Answer Text (800-1200 words)                             │
    │  • Domain, Question Type, Framework                         │
    │  • Confidence Score (0.0 - 1.0)                             │
    │  • 10-dimension Review Scores                               │
    │  • Chain-of-Thought Trace                                   │
    │  • Revision History (if revised)                            │
    └─────────────────────────────────────────────────────────────┘
```

### Container Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          DOCKER COMPOSE — 10 CONTAINERS                              │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐    │
│  │                           frontend_net                                       │    │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐                                  │    │
│  │  │ Frontend │   │ Traefik  │   │ Backend  │                                  │    │
│  │  │ :5173    │   │ :80      │   │ :8000    │                                  │    │
│  │  │ React    │   │ :8080    │   │ FastAPI  │                                  │    │
│  │  │ Vite     │   │ Dashboard│   │          │                                  │    │
│  │  └──────────┘   └──────────┘   └──────────┘                                  │    │
│  └──────────────────────────────────────────────────────────────────────────────┘    │
│                                         │                                            │
│  ┌──────────────────────────────────────────────────────────────────────────────┐    │
│  │                           backend_net                                       │    │
│  │                                                                              │    │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │    │
│  │  │PostgreSQL│   │  Redis   │   │  Qdrant  │   │  Neo4j   │   │  MinIO   │  │    │
│  │  │  :5432   │   │  :6379   │   │  :6333   │   │  :7687   │   │  :9000   │  │    │
│  │  │          │   │          │   │          │   │          │   │  :9001   │  │    │
│  │  │ 10 tables│   │ Cache    │   │ Vectors  │   │ Graph    │   │ Objects  │  │    │
│  │  │ Students │   │ Events   │   │ Semantic │   │ Knowledge│   │ Datasets │  │    │
│  │  │ Progress │   │ Pub/Sub  │   │ Search   │   │ Relations│   │ Docs     │  │    │
│  │  │ Plans    │   │ Queue    │   │          │   │          │   │          │  │    │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘  │    │
│  │                                                                              │    │
│  │  ┌──────────┐   ┌──────────┐                                                 │    │
│  │  │  Celery  │   │  Celery  │                                                 │    │
│  │  │  Worker  │   │   Beat   │                                                 │    │
│  │  │          │   │Scheduler │                                                 │    │
│  │  └──────────┘   └──────────┘                                                 │    │
│  └──────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Database Schema (PostgreSQL — 10 Tables)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATABASE SCHEMA                               │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │   students   │  │   progress   │  │ study_plans  │               │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤               │
│  │ id (PK)      │  │ id (PK)      │  │ id (PK)      │               │
│  │ email (UQ)   │  │ student_id(FK)│ │ student_id(FK)│              │
│  │ password_hash│  │ topic_id (FK)│  │ date         │               │
│  │ name         │  │ mastery_level│  │ phase        │               │
│  │ phone        │  │ score        │  │ tasks (JSON) │               │
│  │ exam_year    │  │ last_practiced│ │ completed    │               │
│  │ optional_sub │  │ streak_days  │  │ created_at   │               │
│  │ created_at   │  │ updated_at   │  │ updated_at   │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  revisions   │  │  mock_tests  │  │    notes     │               │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤               │
│  │ id (PK)      │  │ id (PK)      │  │ id (PK)      │               │
│  │ student_id(FK)│ │ student_id(FK)│ │ student_id(FK)│              │
│  │ topic_id (FK)│  │ subject      │  │ topic_id (FK)│               │
│  │ due_date     │  │ questions    │  │ note_type    │               │
│  │ completed    │  │ score        │  │ content      │               │
│  │ interval_days│  │ total_marks  │  │ flashcards   │               │
│  │ ease_factor  │  │ time_taken   │  │ mindmap      │               │
│  │ repetitions  │  │ created_at   │  │ created_at   │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │   feedback   │  │  datasets    │  │    topics    │               │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤               │
│  │ id (PK)      │  │ id (PK)      │  │ id (PK)      │               │
│  │ student_id(FK)│ │ question     │  │ name         │               │
│  │ question     │  │ answer       │  │ domain       │               │
│  │ rating       │  │ source       │  │ sub_topics   │               │
│  │ comment      │  │ year         │  │ keywords     │               │
│  │ created_at   │  │ metadata     │  │ difficulty   │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

### Project Structure

```
hermes-v2/
├── backend/                          # Python FastAPI Backend
│   ├── api/                          # REST API Layer
│   │   ├── routes_answer.py          # POST /api/answer — Generate answer
│   │   ├── routes_student.py         # Student CRUD + auth
│   │   ├── routes_evaluation.py      # Evaluation endpoints
│   │   ├── routes_feedback.py        # Feedback collection
│   │   ├── routes_health.py          # Health check
│   │   ├── routes_websocket.py       # Real-time updates
│   │   ├── middleware.py             # Rate limiting, logging
│   │   ├── security.py               # JWT auth, input sanitization
│   │   └── telegram_bot.py           # Telegram integration
│   │
│   ├── core/                         # Core Infrastructure
│   │   ├── config.py                 # Settings (Pydantic)
│   │   ├── database.py               # Async SQLAlchemy session
│   │   ├── llm_gateway.py            # LiteLLM unified LLM gateway
│   │   ├── model_router.py           # Model failover chain
│   │   ├── event_bus.py              # Redis Pub/Sub
│   │   ├── event_consumers.py        # Event handlers
│   │   ├── db_postgres.py            # PostgreSQL connection
│   │   ├── db_qdrant.py              # Qdrant connection
│   │   ├── db_neo4j.py               # Neo4j connection
│   │   ├── db_redis.py               # Redis connection
│   │   └── telemetry.py              # OpenTelemetry tracing
│   │
│   ├── domain/                       # Business Logic (14 modules)
│   │   ├── answer_generation/        # 8-stage LangGraph pipeline
│   │   │   ├── nodes_v3.py           # 11 processing nodes
│   │   │   ├── orchestrator_v3.py    # Graph compiler + edges
│   │   │   ├── upsc_blueprint.py     # UPSC structure planner
│   │   │   └── schemas.py            # State schemas
│   │   ├── students/                 # Student management
│   │   │   ├── service.py            # CRUD + auth logic
│   │   │   ├── models.py             # SQLAlchemy models
│   │   │   └── intelligence.py       # Learning profile builder
│   │   ├── retrieval/                # Semantic search
│   │   │   ├── semantic_retriever.py # Qdrant + embedding
│   │   │   ├── hybrid_retriever.py   # Qdrant + BM25
│   │   │   └── router.py             # Strategy selector
│   │   ├── study_planner/            # Daily study plans
│   │   │   └── service.py            # Phase-based planning
│   │   ├── revision/                 # Spaced repetition
│   │   │   └── service.py            # SM-2 algorithm
│   │   ├── evaluation/               # Quality metrics
│   │   │   ├── continuous.py         # Post-ingestion checks
│   │   │   └── deepeval_metrics.py   # Deep evaluation
│   │   ├── verification/             # Fact checking
│   │   │   └── verifier_agent.py     # Claim verification
│   │   ├── dataset/                  # Training data collection
│   │   │   ├── collector.py          # Trajectory collection
│   │   │   ├── exporter.py           # JSONL/ChatML export
│   │   │   └── schemas.py            # Data schemas
│   │   ├── analytics/                # Progress analytics
│   │   │   └── service.py            # Reports + dashboards
│   │   ├── current_affairs/          # Daily news
│   │   │   ├── service.py            # Digest generation
│   │   │   └── scraper.py            # Web scraping
│   │   ├── interview/                # Mock interviews
│   │   │   └── service.py            # Question selection
│   │   ├── learning/                 # Learning service
│   │   │   └── service.py            # Progress tracking
│   │   ├── memory/                   # Memory layer
│   │   │   └── recall_engine.py      # Fact recall
│   │   ├── mock_tests/               # Practice tests
│   │   │   └── service.py            # Test generation
│   │   └── notes/                    # Note generation
│   │       └── service.py            # Notes + flashcards
│   │
│   ├── models/                       # Shared ORM models
│   ├── plugins/                      # Extensible plugins
│   │   ├── base.py                   # Plugin interface
│   │   ├── evaluators/               # Custom evaluators
│   │   ├── retrievers/               # Custom retrievers
│   │   └── scrapers/                 # Custom scrapers
│   │
│   ├── governance/                   # Rate limiting + audit
│   │   ├── rate_limiter.py           # Token bucket
│   │   └── audit_logger.py           # Audit trail
│   │
│   ├── prompts/                      # LLM prompt templates
│   │   ├── registry.py               # Prompt registry
│   │   ├── polity_v1.yaml            # Polity prompts
│   │   ├── economy_v1.yaml           # Economy prompts
│   │   └── ...                       # 5 more domain prompts
│   │
│   ├── scrapers/                     # UPSC data scrapers
│   │   ├── base.py                   # Abstract scraper
│   │   ├── pib.py                    # Press Information Bureau
│   │   └── ...                       # More sources
│   │
│   ├── workers/                      # Background tasks
│   │   └── celery_app.py             # Celery configuration
│   │
│   ├── research/                     # Research modules
│   │   ├── distillation/             # Knowledge distillation
│   │   ├── evaluation/               # Evaluation research
│   │   ├── fine_tuning/              # Fine-tuning scripts
│   │   ├── planning/                 # Planning research
│   │   ├── reasoning/                # Reasoning research
│   │   └── reward_models/            # Reward model research
│   │
│   ├── profiles/                     # Config profiles
│   │   ├── dev.yaml                  # Development
│   │   ├── prod.yaml                 # Production
│   │   └── test.yaml                 # Testing
│   │
│   ├── tests/                        # 17 test files (199 tests)
│   ├── main.py                       # FastAPI entry point
│   ├── Dockerfile                    # Multi-stage build
│   ├── requirements.txt              # 55 dependencies
│   ├── requirements-gpu.txt          # GPU packages
│   └── pytest.ini                    # Test configuration
│
├── frontend/                         # React + Vite Frontend
│   ├── src/                          # Source code
│   ├── package.json
│   └── vite.config.js
│
├── docs/                             # Documentation (10 files)
├── scripts/                          # Setup scripts
│   ├── setup.sh                      # Linux/Mac setup
│   ├── stop.sh                       # Linux/Mac stop
│   ├── health.sh                     # Linux/Mac health check
│   ├── batch_generate.py             # Batch answer generation
│   ├── create_tables.py              # DB table creation
│   ├── ingest_knowledge_base.py     # Knowledge ingestion
│   └── ...
│
├── dataset/                          # UPSC question datasets
│   ├── mains_gs_all.jsonl            # 15 years of questions
│   ├── prelims_gs_all.jsonl
│   └── metadata/
│
├── databases/                        # DB initialization scripts
│   ├── postgres/
│   ├── neo4j/
│   ├── qdrant/
│   ├── redis/
│   └── minio/
│
├── training_data/                    # Generated training data
├── docker-compose.yml                # 10-container orchestration
├── docker-compose.prod.yml           # Production config
├── start.ps1                         # Windows one-click start
├── stop.ps1                          # Windows stop
├── health.ps1                        # Windows health check
├── .env.example                      # Environment template
├── README.md                         # This file
├── CHANGELOG.md                      # Release history
├── CONTRIBUTING.md                   # Contribution guidelines
└── LICENSE                           # MIT License
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.12 |
| **Framework** | FastAPI 0.138, LangGraph 1.2.6 |
| **LLM** | OWL Alpha via OpenRouter (LiteLLM) |
| **Databases** | PostgreSQL 16, Qdrant 1.18, Neo4j 6.2, Redis 6.4 |
| **Frontend** | React, Vite |
| **Infrastructure** | Docker, Traefik, Celery, MinIO |
| **Testing** | pytest, pytest-asyncio (199 tests) |

## 🧪 Testing

```bash
# Run all tests (199 tests, 11 suites)
docker exec hermes_backend python3 -m pytest tests/ -v

# Run specific test suite
docker exec hermes_backend python3 -m pytest tests/test_training_data.py -v

# Run with coverage
docker exec hermes_backend python3 -m pytest tests/ --cov=backend --cov-report=html
```

| Test Suite | Tests | Coverage |
|------------|-------|----------|
| test_answer_quality.py | 7 | Answer generation quality |
| test_audit.py | 25 | Bug fix verification |
| test_comprehensive_audit.py | 33 | Full system audit |
| test_deep_audit.py | 31 | Deep integration tests |
| test_real_fixes.py | 21 | Verified bug fixes |
| test_retrieval.py | 4 | Semantic retrieval |
| test_security.py | 14 | Security & auth |
| test_services.py | 16 | Service layer |
| test_student_system.py | 24 | Student management |
| test_training_data.py | 6 | Training data pipeline |

## License

MIT
