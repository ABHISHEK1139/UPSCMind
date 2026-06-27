# Hermes V2 — Architecture Guide

> **This document explains how Hermes V2 works technically.**
> For what the project does and why, see [README.md](../README.md).

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Container Architecture](#container-architecture)
3. [Answer Generation Pipeline](#answer-generation-pipeline)
4. [Data Flow](#data-flow)
5. [Database Schema](#database-schema)
6. [Event System](#event-system)
7. [LLM Gateway](#llm-gateway)
8. [Project Structure](#project-structure)
9. [Tech Stack](#tech-stack)

---

## System Overview

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

---

## Container Architecture

### 10 Docker Containers

| Container | Image | Port | Purpose | Health Check |
|-----------|-------|------|---------|--------------|
| `hermes_traefik` | traefik:v2.10 | 80, 8080 | API gateway, load balancer, routing | Dashboard :8080 |
| `hermes_backend` | custom build | 8000 | FastAPI application server | `/api/health` |
| `hermes_frontend` | custom build | 5173 | React + Vite frontend | HTTP 200 |
| `hermes_postgres` | postgres:16-alpine | 5432 | Primary relational database | `pg_isready` |
| `hermes_redis` | redis:7-alpine | 6379 | Cache, event bus, Celery broker | `redis-cli ping` |
| `hermes_qdrant` | qdrant/qdrant | 6333 | Vector search, embeddings | `/health` |
| `hermes_neo4j` | neo4j:5 | 7474, 7687 | Knowledge graph | HTTP :7474 |
| `hermes_minio` | minio/minio | 9000, 9001 | Object storage (S3-compatible) | `/minio/health/live` |
| `hermes_celery_worker` | backend image | — | Background task processing | Python import |
| `hermes_celery_beat` | backend image | — | Scheduled task scheduler | Python import |

### Networks

```
frontend_net ─── Traefik (:80) ─── Backend (:8000) ─── Frontend (:5173)
backend_net  ─── Backend ─── PostgreSQL, Redis, Qdrant, Neo4j, MinIO, Celery
```

### Startup Order

```
1. PostgreSQL ─── (healthcheck: pg_isready)
2. Redis ──────── (healthcheck: redis-cli ping)
3. Qdrant ─────── (no healthcheck — started)
4. Neo4j ──────── (healthcheck: wget :7474)
5. MinIO ──────── (healthcheck: mc ready local)
6. Backend ────── (depends on: postgres, redis, neo4j healthy; qdrant started)
7. Frontend ───── (depends on: backend)
8. Traefik ────── (depends on: backend, frontend)
9. Celery Worker ─ (depends on: postgres, redis)
10. Celery Beat ── (depends on: redis)
```

---

## Answer Generation Pipeline

### 8-Stage LangGraph Pipeline

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
│  │  │                                                                 │              │
│  │  │   Score < 0.75? ──▶ Revise ──▶ Re-draft ──▶ Re-review ──▶ ...  │              │
│  │  │   Score >= 0.75? ──▶ Finalize ──▶ Output                        │              │
│  │  │   Max 1 revision (configurable)                                 │              │
│  │  │                                                                 │              │
│  │  └─────────────────────────────────────────────────────────────────┘              │
│  └───────────────────────────────────────────────────────────────────────────────────│
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Node Details

| # | Node | Input | Output | LLM Call |
|---|------|-------|--------|----------|
| 1 | **Intent Classifier** | Question text | Domain, type, entities, constitutional weight, difficulty, marks, confidence | ✅ |
| 2 | **Multi-Retrieval** | Question + domain | Evidence chunks from Qdrant + BM25 + Neo4j | ❌ |
| 3 | **UPSC Blueprint** | Question + domain + entities | Structured plan: sections, word allocation, examples, must-include | ✅ |
| 4 | **Enhanced Planner** | Question + blueprint | Framework, examiner persona, trap, differentiator, dimensions, reasoning plan | ✅ |
| 5 | **Section Drafting** | Plan + blueprint + evidence | Full answer text (800-1200 words) | ✅ |
| 6 | **Multi-Reviewer** | Question + answer + dimensions | 10-dimension scores (accuracy, structure, coverage, examples, etc.) | ✅ |
| 7 | **Revision Blueprint** | Reviewer feedback | Structured MISSING/WEAK/IMPROVE instructions | ❌ |
| 8 | **Evidence Verification** | Answer + evidence chunks | Verified claims, hallucination flags | ✅ |
| 9 | **Confidence Estimator** | All previous scores | Final confidence (0.0-1.0) | ❌ |

### State Reducer

All nodes share a single state dict. A custom merge reducer ensures partial updates don't lose keys:

```python
def _state_reducer(a, b):
    """Merge two state dicts, preserving all keys."""
    merged = dict(a)
    for k, v in b.items():
        if v is not None:
            merged[k] = v
    return merged
```

---

## Data Flow

```
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
    │                                                             │
    │  {                                                          │
    │    "answer": "The 800-1200 word answer text...",            │
    │    "domain": "Economy",                                     │
    │    "question_type": "analytical",                           │
    │    "framework": "Thematic",                                 │
    │    "confidence": 0.85,                                      │
    │    "critique_score": 0.82,                                  │
    │    "fact_check_passed": true,                               │
    │    "review_scores": {                                       │
    │      "accuracy": 0.9, "structure": 0.85, ...                │
    │    },                                                      │
    │    "cot_trace": [...],                                      │
    │    "revision_iterations": 1                                 │
    │  }                                                          │
    └─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### PostgreSQL — 10 Tables

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

### Relationships

```
students ──1:N── progress (per topic)
students ──1:N── study_plans (daily)
students ──1:N── revisions (spaced repetition)
students ──1:N── mock_tests
students ──1:N── notes
students ──1:N── feedback
topics ──1:N── progress
topics ──1:N── revisions
topics ──1:N── notes
```

### Qdrant Collections

| Collection | Purpose | Vectors |
|------------|---------|---------|
| `knowledge_base` | UPSC syllabus content | 384-dim embeddings |

### Neo4j Graph

| Node Type | Properties | Relationships |
|------------|------------|---------------|
| Topic | name, domain, difficulty | :HAS_SUBTOPIC, :RELATED_TO |
| Article | number, title, text | :CITED_IN, :AMENDED_BY |
| Case | name, year, summary | :RELATES_TO, :OVERRULES |
| Scheme | name, ministry, year | :COVERS, :BENEFITS |

---

## Event System

### Redis Pub/Sub Events

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EVENT BUS                                    │
│                                                                      │
│  Producer ──▶ Redis Channel ──▶ Consumer                             │
│                                                                      │
│  Events:                                                            │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ hermes.question_received    → Log question, trigger flow  │     │
│  │ hermes.topic_detected        → Update topic analytics      │     │
│  │ hermes.retrieval_completed   → Cache results               │     │
│  │ hermes.draft_completed       → Log draft metrics           │     │
│  │ hermes.review_completed      → Update quality scores       │     │
│  │ hermes.revision_completed    → Update revision schedule    │     │
│  │ hermes.verification_passed   → Mark answer as verified     │     │
│  │ hermes.answer_generated      → Update progress & mastery   │     │
│  │ hermes.feedback_received     → Store user feedback         │     │
│  │ hermes.dataset_saved         → Log training data           │     │
│  │ hermes.benchmark_started     → Start evaluation           │     │
│  │ hermes.benchmark_completed   → Store evaluation results    │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
│  Consumers:                                                         │
│  • EventConsumers (progress, mastery, analytics)                    │
│  • AuditLogger (governance)                                         │
│  • DatasetCollector (training data)                                 │
│  • ContinuousEvaluator (quality monitoring)                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## LLM Gateway

### Unified LLM Interface

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LLM GATEWAY                                  │
│                                                                      │
│  Code ──▶ LLMGateway.complete() ──▶ LiteLLM ──▶ OpenRouter         │
│                                          │                           │
│  Features:                               ▼                           │
│  • Response caching (Redis)         OWL Alpha Model                  │
│  • Langfuse tracing                          │                       │
│  • Failover chain                            ▼                       │
│  • Structured logging                  Response ──▶ Cache ──▶ Return │
│  • Token counting                                                   │
│  • Cost tracking                                                    │
│                                                                      │
│  Config:                                                             │
│  • Model: openrouter/owl-alpha                                      │
│  • Max retries: 3                                                    │
│  • Timeout: 120s per call                                            │
│  • Cache TTL: 1 hour (Redis)                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### Embedding Pipeline

```
Question Text ──▶ LLMGateway.embed() ──▶ LiteLLM ──▶ OpenRouter
                                              │
                                              ▼
                                    384-dim vector
                                              │
                                              ▼
                                    Qdrant search (cosine similarity)
                                              │
                                              ▼
                                    Top-K evidence chunks
```

---

## Project Structure

```
hermes-v2/
├── backend/                          # Python FastAPI Backend
│   ├── api/                          # REST API Layer
│   │   ├── routes_answer.py          # POST /api/answer
│   │   ├── routes_student.py         # Student CRUD + auth
│   │   ├── routes_evaluation.py      # Evaluation endpoints
│   │   ├── routes_feedback.py        # Feedback collection
│   │   ├── routes_health.py          # Health check
│   │   ├── routes_websocket.py       # Real-time updates
│   │   ├── middleware.py             # Rate limiting, logging
│   │   ├── security.py               # JWT auth, sanitization
│   │   └── telegram_bot.py           # Telegram integration
│   │
│   ├── core/                         # Core Infrastructure
│   │   ├── config.py                 # Settings (Pydantic)
│   │   ├── database.py               # Async SQLAlchemy session
│   │   ├── llm_gateway.py            # LiteLLM unified gateway
│   │   ├── model_router.py           # Model failover chain
│   │   ├── event_bus.py              # Redis Pub/Sub
│   │   ├── event_consumers.py        # Event handlers
│   │   ├── telemetry.py              # OpenTelemetry
│   │   └── db_*.py                   # DB connectors
│   │
│   ├── domain/                       # Business Logic (14 modules)
│   │   ├── answer_generation/        # 8-stage LangGraph pipeline
│   │   ├── students/                 # Student management
│   │   ├── retrieval/                # Semantic search
│   │   ├── study_planner/            # Daily study plans
│   │   ├── revision/                 # Spaced repetition
│   │   ├── evaluation/               # Quality metrics
│   │   ├── verification/             # Fact checking
│   │   ├── dataset/                  # Training data collection
│   │   ├── analytics/                # Progress analytics
│   │   ├── current_affairs/          # Daily news
│   │   ├── interview/                # Mock interviews
│   │   ├── learning/                 # Learning service
│   │   ├── memory/                   # Memory layer
│   │   ├── mock_tests/               # Practice tests
│   │   └── notes/                    # Note generation
│   │
│   ├── models/                       # Shared ORM models
│   ├── plugins/                      # Extensible plugins
│   ├── governance/                   # Rate limiting + audit
│   ├── prompts/                      # LLM prompt templates
│   ├── scrapers/                     # UPSC data scrapers
│   ├── workers/                      # Background tasks
│   ├── research/                     # Research modules
│   ├── profiles/                     # Config profiles
│   ├── tests/                        # 17 test files (199 tests)
│   ├── main.py                       # FastAPI entry point
│   ├── Dockerfile                    # Multi-stage build
│   ├── requirements.txt              # 55 dependencies
│   ├── requirements-gpu.txt          # GPU packages
│   └── pytest.ini                    # Test configuration
│
├── frontend/                         # React + Vite Frontend
├── docs/                             # Documentation (10 files)
├── scripts/                          # Setup scripts
├── dataset/                          # UPSC question datasets
├── databases/                        # DB initialization scripts
├── training_data/                    # Generated training data
├── docker-compose.yml                # 10-container orchestration
├── start.ps1                         # Windows one-click start
├── stop.ps1                          # Windows stop
├── health.ps1                        # Windows health check
├── .env.example                      # Environment template
├── README.md                         # Project overview
├── CHANGELOG.md                      # Release history
├── CONTRIBUTING.md                   # Contribution guidelines
└── LICENSE                           # MIT License
```

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Language** | Python | 3.12 |
| **Framework** | FastAPI | 0.138 |
| **Agent Framework** | LangGraph | 1.2.6 |
| **LLM** | OWL Alpha via OpenRouter | — |
| **LLM Router** | LiteLLM | 1.89 |
| **Relational DB** | PostgreSQL | 16 |
| **Vector DB** | Qdrant | 1.18 |
| **Graph DB** | Neo4j | 6.2 |
| **Cache/Events** | Redis | 7 |
| **Object Storage** | MinIO | latest |
| **Task Queue** | Celery | 5.6 |
| **Frontend** | React + Vite | — |
| **API Gateway** | Traefik | 2.10 |
| **Observability** | OpenTelemetry + Langfuse | — |
| **Testing** | pytest + pytest-asyncio | 9.1 + 1.4 |

---

## How to Read This Document

1. **Start with [README.md](../README.md)** — Understand what the project does
2. **Read [System Overview](#system-overview)** — High-level architecture
3. **Read [Answer Generation Pipeline](#answer-generation-pipeline)** — Core feature
4. **Read [Database Schema](#database-schema)** — Data model
5. **Read [Project Structure](#project-structure)** — File organization
6. **Explore `backend/`** — Read the source code

---

*Last updated: 2026-06-27*
