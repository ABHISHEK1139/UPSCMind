# Hermes V2 — Comprehensive Deep Audit Report

**Date**: 2026-06-27  
**Auditor**: Senior Software Architect / Security Engineer / QA Engineer  
**Scope**: Entire codebase — backend, frontend, infrastructure, tests  
**Total Files Reviewed**: 80+  
**Test Suite**: 177 passing, 1 pre-existing failure  

---

## 1. Project Understanding

### What This Project Does
Hermes V2 is an AI-powered UPSC (Union Public Service Commission) Civil Services answer generation and learning platform. It generates structured, examiner-quality answers using an 8-stage LangGraph pipeline, and provides a full student learning management system with profiles, study planning, revision, notes, mock tests, and analytics.

### Target Users
- UPSC Civil Services aspirants (Prelims + Mains)
- Coaching institutes
- Self-study students

### Architecture
```
Frontend (React) → FastAPI Gateway → LangGraph V3 Pipeline → LLM (OWL Alpha)
                                    ↕
                         Student Services → PostgreSQL
                                    ↕
                         Event Bus → Redis → Celery Workers
                                    ↕
                         Qdrant (vectors) + Neo4j (graph)
```

### Workflow
1. User submits UPSC question
2. Intent classifier identifies domain, type, difficulty
3. Retrieval fetches evidence from Qdrant/Neo4j
4. UPSC blueprint creates structured answer plan
5. Planner selects framework and dimensions
6. Drafting generates full answer
7. Multi-reviewer scores on 10 dimensions
8. Evidence verification checks claims
9. Confidence estimator produces final score

### Missing Features
- **Data ingestion pipeline**: Qdrant collection `upsc_questions` doesn't exist — retrieval always falls back
- **CI/CD**: No GitHub Actions or similar
- **Monitoring/Alerting**: No Prometheus/Grafana
- **Backup/Recovery**: No automated DB backups
- **Multi-tenancy**: Single tenant only
- **Internationalization**: English only
- **Mobile App**: Web only
- **Offline Mode**: No PWA support

---

## 2. Folder Structure

### Backend (`backend/`)
| Folder | Purpose | Best Practice | Issues |
|--------|---------|---------------|--------|
| `api/` | REST routes | ✅ Good separation | Missing API versioning (`/api/v1/`) |
| `core/` | Infrastructure | ✅ Clean | Config has duplicates |
| `domain/` | Business logic | ✅ DDD approach | Some services lack interfaces |
| `workers/` | Celery tasks | ✅ Good | Missing error recovery |
| `scrapers/` | Data ingestion | ✅ Good | Not integrated with Docker |
| `tests/` | Test suite | ✅ Comprehensive | Missing load tests |
| `governance/` | Rate limiting | ✅ Good | In-memory only |

### Frontend (`frontend/`)
| Folder | Purpose | Issues |
|--------|---------|--------|
| `components/` | React components | ✅ Good |
| `hooks/` | Custom hooks | ✅ Good |
| `styles/` | CSS | ⚠️ No CSS modules/Tailwind |

### Unnecessary Files
- `backend/.cache/` — should be in `.gitignore`
- `backend/__pycache__/` — should be in `.gitignore`
- `backend/test_*.py` files at root — should be in `tests/`
- `backend/dspy_gepa_optimizer.py` — experimental, not used
- `backend/distilabel_pipeline.py` — experimental, not used

### Missing Files
- `docker-compose.prod.yml` — referenced but may not exist
- `.github/workflows/` — CI/CD
- `Makefile` — common commands
- `docs/` — architecture docs
- `migrations/` — Alembic migrations
- `.env.production` — production config template

---

## 3. Code Quality

### Good Practices
- ✅ Clean separation: `api/` → `domain/` → `core/`
- ✅ Async throughout
- ✅ Type hints used consistently
- ✅ Pydantic models for validation
- ✅ Dependency injection via FastAPI `Depends`
- ✅ Comprehensive test suite (177 tests)
- ✅ JWT authentication
- ✅ Input sanitization

### Code Smells

#### 3.1 Duplicate Code
**File**: `backend/core/config.py`
```python
# DUPLICATE — lines 76-82 AND 100-102
LANGFUSE_PUBLIC_KEY: str = ""
LANGFUSE_SECRET_KEY: str = ""
LANGFUSE_HOST: str = ""

# DUPLICATE — lines 84 AND 124
LLM_CACHE_TTL: int = 3600

# DUPLICATE — lines 89 AND 140 (DIFFERENT VALUES!)
GOVERNANCE_RATE_LIMIT_PER_MINUTE: int = 60  # line 89
GOVERNANCE_RATE_LIMIT_PER_MINUTE: int = 30  # line 140
```

#### 3.2 Long Functions
**File**: `backend/domain/answer_generation/nodes_v3.py`
- `node_multi_reviewer()` — 60+ lines
- `node_section_drafting()` — 50+ lines

#### 3.3 Magic Numbers
**File**: `backend/domain/answer_generation/nodes_v3.py`
```python
weights = {"accuracy": 0.2, "structure": 0.15, "coverage": 0.15, ...}
```
Should be constants at module level.

#### 3.4 Inconsistent Naming
- `node_upsc_blueprint` vs `node_multi_reviewer` — inconsistent prefix
- `REVISION_INTERVALS` (dict) vs `MASTERY_THRESHOLD` (int) — inconsistent constants

### SOLID Principles Violations

#### Single Responsibility
- ❌ `StudentService` handles auth, profile, preferences, progress, topic mastery — should be split
- ❌ `AnalyticsService` handles dashboard, reports, recommendations — should be split

#### Open/Closed
- ❌ Pipeline nodes are hardcoded — adding new nodes requires modifying orchestrator

#### Dependency Inversion
- ❌ Services directly instantiate `LLMGateway()` instead of receiving via DI

---

## 4. Bugs

### Critical (Production-Blocking)

#### BUG-1: Config Duplicate Settings Cause Undefined Behavior
**File**: `backend/core/config.py`, lines 89 vs 140
```python
GOVERNANCE_RATE_LIMIT_PER_MINUTE: int = 60  # line 89
GOVERNANCE_RATE_LIMIT_PER_MINUTE: int = 30  # line 140 — WINS!
```
**Impact**: Rate limit is 30, not 60 as intended. Pydantic uses the last definition.
**Fix**: Remove duplicate.

#### BUG-2: LLM Timeout Conflicting Units
**File**: `backend/core/config.py`, lines 86 vs 126
```python
LLM_TIMEOUT: int = 120        # seconds
LLM_TIMEOUT_MS: int = 60000   # milliseconds — which one is used?
```
**Impact**: `LLMGateway` uses `self.timeout = settings.LLM_TIMEOUT` (120s), but `LLM_TIMEOUT_MS` (60000ms) is never used. Confusing.
**Fix**: Remove `LLM_TIMEOUT_MS`, keep `LLM_TIMEOUT`.

#### BUG-3: WebSocket Route File Truncated
**File**: `backend/api/routes_websocket.py`
The file appears to be truncated at line 99. The `websocket_endpoint` function may be incomplete.
**Impact**: WebSocket streaming may not work correctly.
**Fix**: Verify and complete the file.

#### BUG-4: Knowledge Memory Zero Vector
**File**: `backend/domain/memory/knowledge.py`, line 47
```python
query_vector = [0.0] * self._embedding_dim  # Always returns irrelevant results!
```
**Impact**: Semantic search always returns empty/random results.
**Fix**: Implement actual embedding via LLMGateway.

### High (Functional Issues)

#### BUG-5: V1/V2 Orchestrator Still Present
**File**: `backend/domain/answer_generation/orchestrator.py`
The old orchestrator is still present and could be accidentally used.
**Impact**: Confusion, potential regression if someone imports the wrong one.
**Fix**: Move to `legacy/` or delete.

#### BUG-6: Dataset Collector DPO Pair Generation Fails
**File**: `backend/tests/test_training_data.py`, `test_dpo_pair_generation`
**Impact**: Training data pipeline broken.
**Fix**: Debug DPO pair generation logic.

#### BUG-7: WebSocket Connections Never Cleaned Up
**File**: `backend/api/routes_websocket.py`
```python
_active_connections: Dict[str, WebSocket] = {}
# Never removes disconnected clients!
```
**Impact**: Memory leak — disconnected clients stay in dict forever.
**Fix**: Remove on disconnect.

#### BUG-8: Feedback Store In-Memory
**File**: `backend/api/routes_feedback.py`
```python
_feedback_store: List[Dict[str, Any]] = []  # Lost on restart!
```
**Impact**: All feedback lost on server restart.
**Fix**: Use PostgreSQL.

### Medium (Quality Issues)

#### BUG-9: No Database Migrations
No Alembic migrations — tables are created via `Base.metadata.create_all()` which doesn't handle schema changes.
**Fix**: Add Alembic.

#### BUG-10: No API Versioning
All routes are at `/api/` without version prefix.
**Fix**: Add `/api/v1/` prefix.

#### BUG-11: Missing `__init__.py` in Some Packages
Some domain subpackages lack proper `__init__.py` exports.

#### BUG-12: Hardcoded URLs in Frontend
**File**: `frontend/src/hooks/useHermesAPI.js`
```javascript
const API_BASE = 'http://localhost:8000/api';  // Hardcoded!
```

#### BUG-13: No CSRF Protection
No CSRF tokens on POST/PUT endpoints.

#### BUG-14: No Request Size Limit
No limit on request body size — could be DoS vector.

---

## 5. Security Audit

### Critical

#### SEC-1: JWT Secret Not Configurable
**File**: `backend/api/security.py`
```python
SECRET_KEY = secrets.token_hex(32)  # Generated on every restart!
```
**Impact**: All tokens invalidated on server restart. Users logged out.
**Severity**: **Critical** for production.
**Fix**: Load from environment variable.

#### SEC-2: Hardcoded Database Credentials
**File**: `backend/core/config.py`
```python
DATABASE_URL: str = "postgresql+asyncpg://upsc_user:upsc_password@localhost:5432/upsc_db"
NEO4J_PASSWORD: str = "upsc_neo4j_password"
MINIO_SECRET_KEY: str = "hermes_secret_2026"
```
**Severity**: **Critical** — credentials in code.
**Fix**: Use environment variables with `Field(default_factory=...)`.

#### SEC-3: CORS Allows All Origins in Debug Mode
**File**: `backend/main.py`
```python
allow_origins=["http://localhost:3000", "http://localhost:5173"] if settings.APP_DEBUG else ["https://hermes.upsc.ai"]
```
**Severity**: **High** — if `APP_DEBUG=True` in production, CORS is wide open.
**Fix**: Separate debug/prod CORS config.

### High

#### SEC-4: No Account Lockout
No rate limit on login attempts — brute force possible.
**Fix**: Add account lockout after N failed attempts.

#### SEC-5: No Input Length Limit on Answer Submission
No max length on answer text in mock test evaluation.
**Fix**: Add `max_length` validation.

#### SEC-6: WebSocket Authentication Missing
WebSocket endpoint doesn't verify JWT token.
**Severity**: **High** — anyone can connect.
**Fix**: Add JWT verification to WebSocket handshake.

### Medium

#### SEC-7: No HTTPS Enforcement
No HSTS preloaded, no redirect from HTTP to HTTPS.

#### SEC-8: No Content Security Policy Nonce
CSP is static, not per-request nonce.

#### SEC-9: Password Reset Missing
No forgot password flow.

#### SEC-10: No Audit Logging
No log of who did what and when.

---

## 6. Performance Review

### Database Queries

#### PERF-1: N+1 Query in Student Profile
**File**: `backend/domain/students/service.py`
```python
result = await self.db.execute(
    select(Student)
    .options(selectinload(Student.preferences))
    .options(selectinload(Student.progress))  # Separate query!
    .where(Student.id == student_id)
)
```
**Fix**: Use `selectinload(Student.preferences).selectinload(Student.progress)` in one call.

#### PERF-2: No Database Indexing Strategy
Missing indexes on:
- `students.email` (unique, used for login)
- `student_topic_mastery.student_id` (frequent queries)
- `revision_records.next_revision_at` (used for due revisions)

#### PERF-3: No Query Result Caching
Dashboard data is recalculated on every request.
**Fix**: Add Redis cache with TTL.

### API Performance

#### PERF-4: No Response Compression
No gzip/brotli middleware.
**Fix**: Add `CompressionMiddleware`.

#### PERF-5: No Pagination
List endpoints (notes, mock tests, revisions) don't support pagination.
**Fix**: Add `limit`/`offset` parameters.

### Frontend Performance

#### PERF-6: No Code Splitting
All components loaded upfront.
**Fix**: Use `React.lazy()` for route-based splitting.

#### PERF-7: No Image Optimization
No lazy loading for images.

#### PERF-8: Large Bundle Size
All lucide-react icons imported.
**Fix**: Tree-shake imports.

---

## 7. Database Review

### Schema Issues

#### DB-1: No Timestamps on Most Tables
Only `students` and `student_progress` have `created_at`/`updated_at`.
Missing from: `study_plans`, `notes`, `mock_test_attempts`, `revision_records`.

#### DB-2: No Soft Delete
Records are hard-deleted. No audit trail.
**Fix**: Add `deleted_at` column.

#### DB-3: No JSON Validation
`tasks` column in `study_plans` is JSON — no schema validation at DB level.

#### DB-4: Missing Indexes
```sql
-- Needed:
CREATE INDEX idx_students_email ON students(email);
CREATE INDEX idx_topic_mastery_student ON student_topic_mastery(student_id);
CREATE INDEX idx_revision_due ON revision_records(next_revision_at);
CREATE INDEX idx_progress_student ON student_progress(student_id);
```

#### DB-5: No Connection Pool Tuning
Pool size is 10, but no max overflow configuration for production.

---

## 8. API Review

### REST Design Issues

#### API-1: Inconsistent URL Patterns
```
/api/student/register      # POST
/api/student/profile/{id}  # GET
/api/student/dashboard/{id} # GET
```
Should be:
```
/api/v1/students           # POST (register)
/api/v1/students/{id}      # GET (profile)
/api/v1/students/{id}/dashboard  # GET
```

#### API-2: No Pagination
`GET /api/student/notes/{id}` returns all notes — could be thousands.

#### API-3: No Consistent Error Format
Some endpoints return `{"error": ...}`, others return `{"detail": ...}`.

#### API-4: No Rate Limit Headers
No `X-RateLimit-*` headers in responses.

#### API-5: Missing Endpoints
- `POST /api/student/logout` — no logout endpoint
- `POST /api/student/password-reset` — no password reset
- `GET /api/student/sessions` — no session management
- `DELETE /api/student/notes/{id}` — no note deletion

---

## 9. Frontend Review

### UI Architecture

#### UI-1: No Global State Management
Uses local component state only. No Redux/Context for shared state like student profile.

#### UI-2: No Loading States
Some components don't show loading indicators during API calls.

#### UI-3: No Error Boundaries
No React error boundaries — one crash kills the whole app.

#### UI-4: No Accessibility
- No ARIA labels
- No keyboard navigation
- No screen reader support

#### UI-5: No Responsive Design
Dashboard uses fixed grid — doesn't adapt to mobile.

---

## 10. Backend Review

#### Architecture

#### ARCH-1: No Repository Pattern
Services directly use SQLAlchemy queries — no abstraction layer.

#### ARCH-2: No Service Layer Interface
Services don't implement interfaces — hard to mock/test.

#### ARCH-3: No Domain Events
Events are published but not consumed by other modules.

#### ARCH-4: No CQRS
Read and write use the same models — inefficient for complex queries.

---

## 11. DevOps

#### Docker

#### DOCKER-1: No Multi-Stage Build
Backend Dockerfile copies all files — large image.

#### DOCKER-2: No Health Checks in Docker Compose
Containers don't have health checks defined.

#### DOCKER-3: No Resource Limits
No CPU/memory limits on containers.

#### CI/CD

#### CICD-1: No CI/CD Pipeline
No automated testing on push/PR.

#### CICD-2: No Automated Deployment
Manual deployment only.

---

## 12. Testing

### Current State: 177 Tests, Good Coverage

#### TEST-1: No Load Tests
No Locust/k6 tests for performance under load.

#### TEST-2: No Chaos Engineering
No tests for failure scenarios (DB down, Redis down, etc.).

#### TEST-3: No Contract Tests
No Pact tests for API consumer contracts.

#### TEST-4: Missing Test Areas
- WebSocket tests
- Celery task tests
- Scraper tests
- Rate limiter tests under concurrent load

---

## 13. Dependencies

### Issues

#### DEP-1: `passlib` Still in Requirements
Even though we switched to direct `bcrypt`, `passlib` is still in `requirements.txt`.

#### DEP-2: No Pinning
Dependencies not pinned to exact versions.

#### DEP-3: Heavy Dependencies
- `dspy` — heavy, not used in V3 pipeline
- `langfuse` — heavy, optional

---

## 14. Documentation

### Current State
- ✅ README exists and is comprehensive
- ✅ API docs auto-generated by FastAPI
- ❌ No architecture decision records (ADRs)
- ❌ No runbook for operations
- ❌ No contribution guide
- ❌ No changelog

---

## 15. Production Readiness

### Score: 6.5/10

| Category | Score | Notes |
|----------|-------|-------|
| Scalability | 6/10 | No horizontal scaling strategy |
| Reliability | 6/10 | No circuit breakers, no retries |
| Observability | 5/10 | Langfuse optional, no structured logging |
| Maintainability | 7/10 | Clean code, good tests |
| Deployment | 6/10 | Docker but no CI/CD |
| Security | 6/10 | JWT secret hardcoded, no CSRF |
| Data Integrity | 6/10 | No migrations, no backups |

---

## 16. Best Practices Violations

| Principle | Violation | File |
|-----------|-----------|------|
| **DRY** | Duplicate config settings | `core/config.py` |
| **DRD** | Duplicate error handling in routes | Multiple route files |
| **KISS** | Over-engineered event bus for 2 subscribers | `core/event_manager.py` |
| **SOLID (S)** | StudentService does too much | `domain/students/service.py` |
| **SOLID (O)** | Pipeline nodes hardcoded | `orchestrator_v3.py` |
| **SOLID (D)** | Services directly instantiate LLMGateway | All services |
| **YAGNI** | DSPy signatures not used in V3 | `dspy_signatures.py` |

---

## 17. Improvement Roadmap

### High Priority (Fix Before Production)

| Issue | Difficulty | Impact | Effort |
|-------|------------|--------|--------|
| JWT secret from env | Low | Critical | 30 min |
| Remove duplicate config | Low | Critical | 15 min |
| WebSocket auth | Medium | High | 2 hours |
| Database credentials from env | Low | Critical | 30 min |
| Add DB indexes | Low | High | 1 hour |
| WebSocket cleanup | Low | Medium | 30 min |
| CORS debug protection | Low | High | 30 min |

### Medium Priority (Fix in Next Sprint)

| Issue | Difficulty | Impact | Effort |
|-------|------------|--------|--------|
| API versioning | Medium | Medium | 2 hours |
| Alembic migrations | Medium | High | 4 hours |
| Feedback persistence | Medium | Medium | 2 hours |
| Add CSP nonce | Low | Medium | 1 hour |
| Rate limit headers | Low | Low | 1 hour |
| Error response format | Low | Medium | 1 hour |

### Low Priority (Nice to Have)

| Issue | Difficulty | Impact | Effort |
|-------|------------|--------|--------|
| Code splitting | Low | Medium | 2 hours |
| Accessibility | High | High | 8 hours |
| Load tests | Medium | Medium | 4 hours |
| CI/CD pipeline | Medium | High | 8 hours |
| Mobile responsive | Medium | Medium | 8 hours |

---

## 18. Overall Rating

| Category | Score (1-10) | Notes |
|----------|-------------|-------|
| Architecture | 7/10 | Clean DDD, but missing patterns |
| Code Quality | 7/10 | Good, but some code smells |
| Security | 6/10 | JWT secret hardcoded, no CSRF |
| Performance | 6/10 | No caching, no pagination |
| Maintainability | 7/10 | Good tests, clean structure |
| Scalability | 5/10 | No horizontal scaling strategy |
| Readability | 8/10 | Well-commented, clear naming |
| Testing | 8/10 | 177 tests, good coverage |
| Documentation | 7/10 | Good README, missing ADRs |
| Production Readiness | 6.5/10 | Needs hardening |

### **Overall Score: 68/100**

---

## 19. Refactoring Suggestions

### Critical: Config Deduplication

**Problem**: `core/config.py` has duplicate settings causing undefined behavior.
```python
# BEFORE (BUGGY):
GOVERNANCE_RATE_LIMIT_PER_MINUTE: int = 60  # line 89
GOVERNANCE_RATE_LIMIT_PER_MINUTE: int = 30  # line 140 — WINS!
```

**Solution**:
```python
# AFTER (FIXED):
class Settings(BaseSettings):
    # ... all settings defined ONCE ...
    GOVERNANCE_RATE_LIMIT_PER_MINUTE: int = 60
    # ... no duplicates ...
```

### Critical: JWT Secret from Environment

**Problem**: Secret regenerated on every restart.
```python
# BEFORE:
SECRET_KEY = secrets.token_hex(32)
```

**Solution**:
```python
# AFTER:
import os
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_hex(32))
```

### High: WebSocket Authentication

**Problem**: No auth on WebSocket endpoint.

**Solution**:
```python
@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: str = Query(...)):
    # Verify JWT before accepting
    try:
        payload = verify_token(token)
    except HTTPException:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await websocket.accept()
    # ...
```

---

## 20. Final Verdict

### Would I Approve This Project for Production?

**Not yet.** The project has a solid foundation and good architecture, but several critical issues need to be addressed:

### Biggest Risks
1. **JWT secret regeneration** — all users logged out on every restart
2. **Hardcoded credentials** — database passwords in code
3. **No CI/CD** — manual deployment is error-prone
4. **No database migrations** — schema changes will break production

### What Should Be Fixed First
1. ✅ JWT secret from environment variable
2. ✅ Remove duplicate config settings
3. ✅ Database credentials from environment
4. ✅ WebSocket authentication
5. ✅ Add database indexes
6. ✅ WebSocket connection cleanup

### What Impressed Me
- ✅ Clean DDD architecture with clear separation
- ✅ Comprehensive test suite (177 tests)
- ✅ Full 8-stage pipeline with CoT tracing
- ✅ Student platform with 9 integrated services
- ✅ JWT authentication with input sanitization
- ✅ Docker compose with 10 containers
- ✅ Real LLM integration working end-to-end

### What I Would Completely Redesign
1. **Config system** — use `pydantic-settings` with env files, no duplicates
2. **Database layer** — add Alembic migrations, repository pattern
3. **API layer** — add versioning, pagination, consistent error format
4. **Frontend** — add state management, error boundaries, accessibility

### Recommendation
**Fix the 6 critical/high issues above, then this project is ready for beta launch.** The architecture is sound, the code quality is good, and the test coverage is excellent. The remaining issues are operational (CI/CD, monitoring) and can be addressed incrementally.
