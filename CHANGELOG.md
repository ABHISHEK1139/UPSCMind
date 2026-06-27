# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed
- Added `bcrypt` and `pytest-asyncio` to `requirements.txt` for auto-install
- Added `pytest.ini` with `asyncio_mode = auto` for async test support
- Fixed async test decorators in `test_e2e_real.py`

## [1.0.0] - 2026-06-27

### Added
- **8-Stage Answer Generation Pipeline**: Intent → Retrieval → Blueprint → Planning → Drafting → Review → Verification → Confidence
- **LangGraph V3 Orchestrator** with reflection loop and revision blueprint
- **Semantic Retrieval** via Qdrant with runtime embedding through LLMGateway
- **Multi-Reviewer** with 10-dimension scoring (accuracy, structure, coverage, examples, etc.)
- **Evidence Verification** with hallucination detection
- **Student Management**: Registration, JWT auth, profiles, dashboards
- **Study Planner**: Phase-based daily plans with spaced repetition
- **Revision Engine**: SM-2 algorithm for optimal review scheduling
- **Mock Tests**: Auto-generation and evaluation
- **Interview Prep**: Mock interviews with personality/leadership questions
- **Current Affairs**: Daily digest, monthly compilation, topic-wise mapping
- **Analytics Dashboard**: Progress tracking, weak topic detection
- **Event Bus**: Redis Pub/Sub inter-module communication
- **Security**: JWT auth, input sanitization, rate limiting, XSS protection
- **10 Docker Containers**: Backend, Frontend, PostgreSQL, Redis, Qdrant, Neo4j, Traefik, MinIO, Celery Worker, Celery Beat
- **199 Tests** across 11 test suites

### Infrastructure
- Full async/await throughout the backend
- GPU support for embeddings (NVIDIA RTX 3050+)
- Docker Compose orchestration
- Traefik reverse proxy with dashboard
- Celery background workers

### Documentation
- Comprehensive README with architecture diagram
- API endpoint documentation
- Contributing guidelines
- 10 documentation files covering architecture, audits, implementation plans
