# UPSCMind — Quick Start Guide
═══════════════════════════════════════════════════════════════

## 3-Step Setup

### Step 1: Clone & Configure
```bash
git clone https://github.com/ABHISHEK1139/UPSCMind.git
cd UPSCMind
cp .env.example .env
# Edit .env → add your OPENROUTER_API_KEY
```

### Step 2: Start
```bash
./start.ps1
```

### Step 3: Open
```
API:      http://localhost:8000/api
Docs:     http://localhost:8000/api/docs
Traefik:  http://localhost:8080
MinIO:    http://localhost:9001
```

## That's It! 🎉

The system comes with:
- ✅ **21.5 MB training data** (trajectories, SFT, reward model)
- ✅ **8 MB UPSC question bank** (mains + prelims, 2011-2025)
- ✅ **Year-wise PYQ data** (2011-2025, arithmetic/comprehension/reasoning)
- ✅ **Pre-built Docker images** (just build and run)
- ✅ **GPU support** (auto-detects NVIDIA GPU)
- ✅ **Auto-restart** (crash recovery built-in)

## API Keys

| Key | Required | Get At |
|-----|----------|--------|
| `OPENROUTER_API_KEY` | ✅ Yes | https://openrouter.ai/settings/credits |
| `GEMINI_API_KEY` | ❌ Optional | https://aistudio.google.com/appkey |
| `LANGFUSE_*` | ❌ Optional | https://cloud.langfuse.com |

## Common Commands

```bash
./start.ps1          # Start
./start.ps1 stop     # Stop
./start.ps1 test     # Run tests
./start.ps1 logs     # View logs
./start.ps1 status   # Check health
./start.ps1 prod     # Production mode (GPU + auto-restart)
```

## Test Results

| Domain | Score | Time |
|--------|-------|------|
| Polity | 0.795 | 142s |
| Economy | 0.575 | 103s |
| History | 0.709 | 98s |
| Geography | 0.515 | 113s |
| Environment | 0.460 | 110s |
| IR | 0.618 | 128s |
| Science-Tech | 0.598 | 112s |
| Ethics | 0.552 | 103s |
| Society | 0.725 | 92s |
| Governance | 0.753 | 104s |

**Average: 0.630 | Total: 18.4 min**

## Architecture

```
Question → Intent → Retrieval → Blueprint → Planning → Drafting → Review → Verify → Confidence → Answer
```

8 nodes, 7 LLM calls, ~2-3 minutes per answer.

## Tech Stack

- **LLM**: OWL Alpha (OpenRouter)
- **Orchestration**: LangGraph 1.2.6
- **Vector DB**: Qdrant (GPU-accelerated)
- **Graph DB**: Neo4j
- **API**: FastAPI
- **Frontend**: React + Vite
- **Infra**: Docker Compose (10 services, GPU support)

## Need Help?

```bash
./start.ps1 status   # Check service health
./start.ps1 logs     # View logs
docker exec hermes_backend python3 /app/test_upsc.py  # Run tests
```
