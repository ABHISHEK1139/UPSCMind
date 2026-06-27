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

```
hermes-v2/
├── backend/               # Python FastAPI backend
│   ├── api/               # REST API routes, middleware, security
│   ├── core/              # Config, database, LLM gateway, event bus
│   ├── domain/            # Business logic (14 domain modules)
│   │   ├── answer_generation/  # 8-stage LangGraph pipeline
│   │   ├── students/           # Profiles, auth, progress
│   │   ├── retrieval/          # Semantic search (Qdrant)
│   │   ├── study_planner/      # Daily study plans
│   │   ├── revision/           # Spaced repetition
│   │   └── ...                 # 8 more modules
│   ├── governance/        # Rate limiting, audit logging
│   ├── models/            # SQLAlchemy ORM models
│   ├── plugins/           # Evaluators, retrievers, scrapers
│   ├── prompts/           # YAML prompt templates
│   ├── scrapers/          # UPSC data scrapers
│   ├── tests/             # 17 test files (199 tests)
│   ├── workers/           # Background task workers
│   ├── main.py            # FastAPI entry point
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/              # React + Vite frontend
├── docs/                  # Documentation
├── scripts/               # Utility & setup scripts
├── dataset/               # UPSC question datasets (2011-2025)
├── databases/             # DB initialization scripts
├── training_data/         # Generated training data output
├── docker-compose.yml     # 10-container orchestration
└── .env.example           # Environment template
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.12 |
| **Framework** | FastAPI 0.138, LangGraph 1.2.6 |
| **LLM** | OWL Alpha via OpenRouter |
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
