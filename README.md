# Hermes V2 — AI UPSC Mentor Platform

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.138-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.6-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![Tests](https://img.shields.io/badge/tests-199%20passed-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-10%20containers-blue.svg)](https://www.docker.com/)

**Free, open-source AI mentor for UPSC Civil Services preparation.**

Generate examiner-quality answers, get instant feedback, follow personalized study plans, and track your progress — all on your own laptop.

---

## 🎯 What It Does

### For Students

| Problem | How Hermes Solves It |
|---------|---------------------|
| Coaching costs ₹5L+ | **Free** — runs on any laptop with Docker |
| No quality feedback | **10-dimension scoring** — instant, objective evaluation |
| Scattered study material | **One platform** — answers, notes, tests, current affairs |
| No personalization | **Adaptive study plans** based on your weak topics |
| Forgetting what you studied | **Spaced repetition** — revises at optimal intervals |
| No progress tracking | **Analytics dashboard** — mastery, streaks, weak areas |

### Answer Generation in 8 Stages

```
Question → Intent → Retrieval → Blueprint → Planning → Drafting → Review → Verify → Output
```

1. **Intent** — Classifies domain, question type, difficulty
2. **Retrieval** — Searches knowledge base (Qdrant + BM25 + Neo4j)
3. **Blueprint** — Creates UPSC structure (sections, word allocation, examples)
4. **Planning** — Strategy, framework, examiner persona
5. **Drafting** — Writes 800-1200 word answer
6. **Review** — Scores on 10 dimensions (accuracy, structure, coverage...)
7. **Verify** — Checks claims against evidence, detects hallucinations
8. **Output** — Final answer with confidence score + revision if needed

### Student Features

- **📝 Answer Generation** — UPSC-grade answers with citations
- **📊 10-Dimension Scoring** — accuracy, structure, coverage, examples, etc.
- **📅 Study Planner** — Daily plans based on your exam date
- **🔄 Spaced Repetition** — SM-2 algorithm for optimal revision timing
- **📚 Notes Generator** — Notes, flashcards, mindmaps from answers
- **📝 Mock Tests** — Practice tests with evaluation
- **🎤 Interview Prep** — Mock interviews with personality questions
- **📰 Current Affairs** — Daily digest mapped to UPSC syllabus
- **📈 Analytics** — Progress tracking, weak topic detection, streaks

---

## 🚀 Quick Start

### One-Click Setup (Recommended)

**Windows:**
```powershell
git clone https://github.com/yourusername/hermes-v2.git
cd hermes-v2
.\start.ps1
```

**Linux / macOS:**
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

### Manual Setup

```bash
git clone https://github.com/yourusername/hermes-v2.git
cd hermes-v2
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
docker compose up -d
docker exec hermes_backend python3 -m pytest tests/ -v
```

### Access Points

| Service | URL |
|---------|-----|
| API | http://localhost:8000/api |
| API Docs | http://localhost:8000/api/docs |
| Traefik Dashboard | http://localhost:8080 |
| MinIO Console | http://localhost:9001 |
| Frontend | http://localhost:5173 |

---

## 📡 API Usage

### Generate an Answer

```bash
curl -X POST http://localhost:8000/api/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "Discuss the impact of GST on Indian economy"}'
```

**Response:**
```json
{
  "session_id": "uuid",
  "question": "Discuss the impact of GST on Indian economy",
  "answer": "The Goods and Services Tax (GST), introduced via the 101st Constitutional Amendment...",
  "domain": "Economy",
  "question_type": "analytical",
  "framework": "Thematic",
  "confidence": 0.85,
  "critique_score": 0.82,
  "fact_check_passed": true,
  "review_scores": {
    "accuracy": 0.9,
    "structure": 0.85,
    "coverage": 0.8,
    "examples": 0.75
  },
  "revision_iterations": 1,
  "total_latency_ms": 12500,
  "cot_trace": [...]
}
```

### Register a Student

```bash
curl -X POST http://localhost:8000/api/student/register \
  -H "Content-Type: application/json" \
  -d '{"email": "student@example.com", "password": "secure123", "name": "Rahul", "exam_year": 2027}'
```

### Get Study Plan

```bash
curl http://localhost:8000/api/student/{id}/study-plan/{id}
```

---

## 🧪 Testing

```bash
# Run all 199 tests
docker exec hermes_backend python3 -m pytest tests/ -v

# Run specific suite
docker exec hermes_backend python3 -m pytest tests/test_training_data.py -v

# Run with coverage
docker exec hermes_backend python3 -m pytest tests/ --cov=backend --cov-report=html
```

| Test Suite | Tests | What It Tests |
|------------|-------|---------------|
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

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.12 |
| **Framework** | FastAPI 0.138, LangGraph 1.2.6 |
| **LLM** | OWL Alpha via OpenRouter (LiteLLM) |
| **Databases** | PostgreSQL 16, Qdrant 1.18, Neo4j 6.2, Redis 6.4 |
| **Frontend** | React, Vite |
| **Infrastructure** | Docker, Traefik, Celery, MinIO |
| **Testing** | pytest, pytest-asyncio (199 tests) |

---

## 📁 Project Structure

```
hermes-v2/
├── backend/          # Python FastAPI backend (14 domain modules)
├── frontend/         # React + Vite frontend
├── docs/             # Documentation
├── scripts/          # Setup scripts (start, stop, health)
├── dataset/          # UPSC question datasets (2011-2025)
├── databases/        # DB initialization scripts
├── training_data/    # Generated training data
├── docker-compose.yml
├── start.ps1         # Windows one-click start
├── stop.ps1          # Windows stop
├── health.ps1        # Windows health check
├── requirements.txt  # 55 Python dependencies
├── requirements-gpu.txt  # GPU packages (torch, unsloth, etc.)
├── .env.example
├── README.md         # This file — project overview
├── CHANGELOG.md
├── CONTRIBUTING.md
└── LICENSE           # MIT
```

> **Full technical architecture with diagrams:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Fork, clone, create branch
git checkout -b feature/amazing-feature

# Make changes, run tests
docker exec hermes_backend python3 -m pytest tests/ -q

# Push and open PR
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

---

## 📊 Project Stats

| Metric | Count |
|--------|-------|
| Domain modules | 14 |
| Docker containers | 10 |
| Test files | 17 |
| Tests | 199 |
| API endpoints | 20+ |
| Python dependencies | 55 |
| Database tables | 10 |
| LLM pipeline stages | 8 |
| Review dimensions | 10 |

---

*Built with ❤️ for UPSC aspirants everywhere.*
