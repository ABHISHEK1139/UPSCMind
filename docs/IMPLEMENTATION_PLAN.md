# Hermes V2 — Detailed Implementation Plan
> Phase-by-phase plan to go from "skeleton" to "production-ready"

---

## Current State Assessment

### ✅ Fully Implemented (Real Code)
- LangGraph 8-node orchestrator with CoT capture
- DSPy signatures (8 signatures)
- Hybrid retriever (Qdrant + BM25 + RRF)
- Neo4j graph retriever (4 query types)
- Cross-encoder reranker
- Dataset collector (6-point gating, 5 formats)
- Dataset exporter + storage
- All 5 memory layers
- Celery workers + beat schedule (4 task modules)
- API routes (answer, health, evaluation, feedback, websocket)
- Model router (3-tier: cheap/standard/reasoning/none)
- UPSC fact checker (targeted DB lookup)
- Knowledge base ingestion script
- Governance (agent registry, rate limiter, audit logger)
- Profiles (dev, prod, benchmark, offline)
- Plugin architecture
- Tests (answer quality, retrieval, training data)

### ⚠️ Partially Implemented (Needs Completion)
- **Scrapers**: Base class + 6 scrapers exist but return empty lists
- **Evaluation**: 6 metric files exist but most are placeholders
- **Answer route**: Basic but needs proper state initialization + error handling
- **Frontend**: Exists but components are basic

### ❌ Missing (Not Yet Built)
- **Continuous evaluation pipeline** (auto-benchmark after scraper runs)
- **Structured training data extraction** (decisions separate from raw CoT)
- **Data versioning** (track dataset/model/prompt versions)
- **Knowledge freshness** (temporal metadata on chunks)
- **WebSocket integration** (real-time agent state streaming)
- **Proper error handling** in API routes
- **Health check endpoint** (currently just returns {"status": "ok"})

---

## Phase 1: Make It Actually Work (Days 1-3)

### 1.1 Fix the Answer Route
**File:** `api/routes_answer.py`

The current route doesn't initialize the full state, doesn't handle errors, and doesn't return training data metadata.

### 1.2 Add Health Check with DB Verification
**File:** `api/routes_health.py`

Should verify all databases are reachable.

### 1.3 Add WebSocket Event Streaming
**File:** `api/routes_websocket.py` + `api/routes_answer.py`

Stream agent state updates to frontend via WebSocket.

### 1.4 Add Proper Error Handling
**File:** `api/routes_answer.py`

Wrap the orchestrator in try/except with meaningful error responses.

### 1.5 Add Structured Training Data Extraction
**File:** `domain/dataset/collector.py`

Add method to extract structured decisions from raw CoT.

---

## Phase 2: Make It Measurable (Days 4-5)

### 2.1 Implement Continuous Evaluation
**New file:** `domain/evaluation/continuous.py`

Auto-benchmark after scraper runs.

### 2.2 Add Data Versioning
**File:** `domain/dataset/schemas.py` + `domain/dataset/exporter.py`

Track dataset/model/prompt versions in export metadata.

### 2.3 Add Knowledge Freshness
**File:** `domain/retrieval/hybrid_retrieval.py` + `ingest_knowledge_base.py`

Add temporal metadata and filtering.

### 2.4 Upgrade Evaluation Metrics
**Files:** `domain/evaluation/metrics.py`, `domain/evaluation/hallucination.py`

Replace placeholders with real DeepEval integration.

---

## Phase 3: Make It Robust (Days 6-7)

### 3.1 Add Crawl4AI Scrapers
**Files:** `scrapers/pib.py`, `scrapers/prs.py`

Replace placeholder scrapers with real Crawl4AI implementations.

### 3.2 Add Retry Logic + Circuit Breakers
**File:** `core/llm_gateway.py`

Add circuit breaker pattern for LLM calls.

### 3.3 Add Rate Limiting Middleware
**File:** `api/middleware.py`

Rate limit API endpoints using the governance rate limiter.

### 3.4 Add Request Logging
**File:** `api/middleware.py`

Log all requests with timing, cost, and outcome.

---

## Phase 4: Make It Production-Ready (Days 8-10)

### 4.1 Docker Health Checks
**File:** `docker-compose.yml`

Add proper health checks for all services.

### 4.2 Add Prometheus Metrics
**File:** `core/metrics.py`

Export Prometheus metrics for monitoring.

### 4.3 Add Grafana Dashboard
**New file:** `monitoring/grafana-dashboard.json`

Pre-configured dashboard for Hermes V2.

### 4.4 Add Alerting Rules
**New file:** `monitoring/alerts.yml`

Alert on quality regression, high latency, high cost.

---

## Implementation Order (Today)

1. Fix answer route (full state init, error handling, training metadata)
2. Upgrade health check (DB verification)
3. Add WebSocket streaming to answer route
4. Add structured training data extraction
5. Add continuous evaluation
6. Add data versioning
7. Add knowledge freshness filtering
8. Upgrade evaluation metrics with DeepEval
