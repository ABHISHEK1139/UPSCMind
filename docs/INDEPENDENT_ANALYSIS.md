# Hermes V2 — Independent Analysis & Honest Assessment
> My own thinking on what to build, what to skip, and what actually matters.
> Not a survey of tools. A plan for making this system work.

---

## 🔍 First: What Are We Actually Building?

Before choosing tools, let me state what I think the real goal is:

**Build a system that generates UPSC answers so good that the reasoning process itself becomes training data for a specialized model.**

That means the #1 priority is **answer quality**, not framework diversity. Every tool choice should answer: "Does this make the answer better?"

---

## 📊 Honest Assessment of Current State

### What's Actually Implemented vs. What's Placeholder

| Component | Real Implementation | Placeholder |
|-----------|---------------------|-------------|
| LangGraph orchestrator | ✅ Full 8-node graph with CoT capture | |
| DSPy signatures | ✅ 8 signatures with MoE models | |
| Hybrid retriever | ✅ Qdrant + BM25 + RRF fusion | |
| Neo4j graph retriever | ✅ 4 query types (relationships, timeline, amendments, institutional) | |
| Cross-encoder reranker | ✅ With graceful fallback | |
| Dataset collector | ✅ 6-point quality gating, 5 formats | |
| Scrapers | | ❌ All return empty lists |
| Embeddings | | ❌ Zero vectors (384-dim dummies) |
| Evaluation metrics | | ❌ Basic structural checks only |
| Fact checker | | ❌ JSON parse with fallback to "pass" |
| Verifier agent | | ❌ Same — graceful pass on error |
| Memory layers | ✅ All 5 layers implemented | |
| Celery workers | ✅ 4 task modules with beat schedule | |
| API routes | ✅ Answer, health, evaluation, feedback, websocket | |

**The skeleton is complete. The muscles are missing.**

The system has all the right architectural pieces, but the actual intelligence — the embeddings that find relevant context, the scrapers that ingest real data, the evaluation that catches real errors — is stubbed out.

---

## 🎯 My Priority List (What Actually Matters)

### Priority 0: Make It Actually Run

Before any new tool, the system needs to **produce one real end-to-end answer**. Today it cannot, because:

1. **Embeddings are zero vectors.** Qdrant returns random results. The retriever is a no-op.
2. **Scrapers return empty lists.** There's no real knowledge base.
3. **The knowledge base is empty.** Even if retrieval worked, there's nothing to retrieve.

**This is the single most important thing to fix.** No amount of GEPA optimization or Distilabel pipelines will help if the system can't retrieve relevant context.

**What to do:**
```python
# 1. Use a real embedding model
# Option A: sentence-transformers (local, free)
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
embeddings = model.encode(texts)

# Option B: OpenAI embeddings (API, cheap)
from core.llm_gateway import LLMGateway
gateway = LLMGateway()
embeddings = await gateway.embed(texts)

# 2. Ingest the existing UPSC dataset
# You already have: dataset/mains_gs_all.jsonl (thousands of PYQs)
# Embed these into Qdrant as your initial knowledge base

# 3. Use Crawl4AI for real scraping
# Start with PIB — it's the most structured source
```

**Estimated effort:** 2-3 days to get real embeddings + basic ingestion working.

---

### Priority 1: Real Evaluation (Not Placeholders)

The current evaluation is the weakest link. The "fact checker" returns `{"passed": True}` on every error. The "structural metric" just checks for the word "Introduction."

**Why this matters:** Your entire training data pipeline depends on quality gating. If the evaluation is broken, you're either:
- Accepting garbage data (training a bad model)
- Rejecting good data (wasting compute)

**What to do:**

```python
# Replace the placeholder fact checker with a real one
# Option A: Use DeepEval (recommended)
from deepeval.metrics import HallucinationMetric, FaithfulnessMetric

# Option B: Build a targeted UPSC fact checker
# UPSC facts are verifiable: Article numbers, Amendment numbers,
# case names, dates, committee names — all have ground truth

class UPSCFactChecker:
    """Checks UPSC-specific factual claims against a verified knowledge base."""
    
    def extract_claims(self, answer: str) -> list[dict]:
        """Extract verifiable claims from an answer."""
        claims = []
        # Article references
        for match in re.finditer(r'Article\s+(\d+[A-Z]?)', answer):
            claims.append({
                "type": "article",
                "value": match.group(1),
                "context": answer[max(0, match.start()-50):match.end()+50],
            })
        # Amendment references
        for match in re.finditer(r'(\d+(?:st|nd|rd|th)\s+Amendment)', answer):
            claims.append({
                "type": "amendment",
                "value": match.group(1),
            })
        # Case citations
        for match in re.finditer(r'([A-Z][a-z]+)\s+v\.?\s+([A-Z][a-z]+)', answer):
            claims.append({
                "type": "case",
                "value": f"{match.group(1)} v. {match.group(2)}",
            })
        return claims
    
    async def verify(self, claims: list[dict]) -> dict:
        """Verify claims against Neo4j knowledge graph."""
        results = []
        for claim in claims:
            if claim["type"] == "article":
                # Check if article exists in Neo4j
                result = await execute_cypher(
                    "MATCH (a:Article {number: $num}) RETURN a",
                    {"num": claim["value"]},
                )
                results.append({
                    "claim": claim,
                    "verified": len(result) > 0,
                })
        return results
```

**Key insight:** UPSC facts are **structured and verifiable**. You don't need a general-purpose hallucination detector. You need to check that Article 21 exists, that Kesavananda Bharati was in 1973, that the 42nd Amendment is real. This is a **database lookup**, not an LLM judgment.

**Estimated effort:** 1-2 days for a targeted UPSC fact checker.

---

### Priority 2: Model Router (The Missing Piece)

The reviewer is absolutely right. Currently, every node uses the same model (Gemini 2.5 Flash). This is wasteful:

| Task | Current Model | Better Choice | Why |
|------|--------------|---------------|-----|
| Topic detection | Gemini 2.5 Flash | Cheaper model (GPT-OSS-120B) | Simple classification |
| Planning | Gemini 2.5 Flash | Same | Needs reasoning |
| Drafting | Gemini 2.5 Flash | Same | Needs quality |
| Critique | Gemini 2.5 Flash | Reasoning model | Needs deep analysis |
| Fact checking | Gemini 2.5 Flash | Targeted DB lookup | Not an LLM task |
| Constitutional check | Gemini 2.5 Flash | Targeted DB lookup | Not an LLM task |

**What to implement:**

```python
class ModelRouter:
    """Routes tasks to appropriate models based on complexity and cost."""
    
    # Model tiers
    CHEAP = "openrouter/openai/gpt-oss-120b"      # $0.05/1M tokens
    STANDARD = "openrouter/google/gemini-2.5-flash" # $0.15/1M tokens
    REASONING = "openrouter/deepseek/deepseek-r1"   # $0.50/1M tokens
    
    TASK_MODELS = {
        "topic_detection": CHEAP,      # Simple classification
        "retrieval": None,              # No LLM — vector search
        "planning": STANDARD,           # Needs moderate reasoning
        "drafting": STANDARD,           # Main generation
        "critique": REASONING,          # Needs deep analysis
        "fact_check": None,             # DB lookup, not LLM
        "constitutional_check": None,   # DB lookup, not LLM
        "revision": STANDARD,           # Regenerate with feedback
    }
    
    def get_model(self, task: str) -> str | None:
        return self.TASK_MODELS.get(task, self.STANDARD)
```

**Impact:** 40-60% cost reduction on LLM calls without quality loss.

---

### Priority 3: Structured Training Data (Not Raw CoT)

The reviewer makes an excellent point. Raw Chain-of-Thought is noisy. Here's my take:

**Keep the CoT trace, but don't train on it directly.** Instead, extract structured signals:

```python
# What we currently save (raw CoT):
{
  "cot_trace": [
    {"step": 1, "node": "topic_detection", "thought": "I think this is Polity because..."},
    {"step": 2, "node": "retrieval", "thought": "Retrieved 10 chunks..."},
    # ... 5 more steps of free-form reasoning
  ]
}

# What we should ALSO save (structured decisions):
{
  "decisions": {
    "domain": {"value": "Polity", "confidence": 0.95, "alternatives": ["Economy"]},
    "framework": {"value": "Thematic", "reason": "analytical_multi_dimension"},
    "retrieval": {"strategy": "hybrid_and_graph", "chunks_used": 5, "sources": ["qdrant", "neo4j"]},
    "quality": {"initial_score": 0.72, "final_score": 0.95, "improvement": 0.23},
    "revision": {"iterations": 1, "main_issue": "missing_citation"},
  }
}
```

**Why both?** The raw CoT is useful for analysis and debugging. The structured decisions are what you actually train on. The structured data is:
- **Compact:** ~500 tokens vs ~3000 for raw CoT
- **Deterministic:** Same question → same structured output
- **Trainable:** Clear input/output pairs for each sub-task
- **Model-agnostic:** Works regardless of which LLM generated it

**Four datasets to build:**

| Dataset | Content | Size Target | Use |
|---------|---------|-------------|-----|
| SFT | Question → Final Answer | 10,000+ | Base fine-tuning |
| DPO | (Question, Bad Draft, Good Draft) | 5,000+ | Preference tuning |
| Planner | (Question, Domain) → Framework + Strategy | 3,000+ | Train planner model |
| Retriever | (Question, Retrieved, Selected) → Relevance | 5,000+ | Train reranker |

---

### Priority 4: Knowledge Freshness

The reviewer is right again. UPSC content has a temporal dimension:

- The 103rd Amendment (EWS reservation) didn't exist before 2019
- GDP figures change every year
- Supreme Court judgments override older ones
- Government schemes get renamed or replaced

**What to implement:**

```python
# Add temporal metadata to every knowledge chunk
{
    "text": "The fiscal deficit target is 4.5% of GDP...",
    "source": "Union Budget 2024-25",
    "published_date": "2024-02-01",
    "valid_until": "2025-03-31",  # Until next budget
    "supersedes": ["fiscal_deficit_2023"],
    "domain": "Economy",
    "type": "budget_figure",
}

# In the retriever, filter by date
def retrieve_with_freshness(query, domain, current_date):
    return hybrid_search(
        query,
        filters={
            "domain": domain,
            "valid_until": {"$gte": current_date},
        },
        sort_by="published_date",  # Prefer newer
    )
```

---

### Priority 5: Continuous Evaluation Pipeline

Instead of "run benchmark after development," make evaluation automatic:

```python
# After every scraper run:
async def post_scraper_evaluation(source: str, new_docs: int):
    """Automatically evaluate after data ingestion."""
    
    # 1. Sample 20 questions from the new data
    sample = sample_questions(source, n=20)
    
    # 2. Run through the pipeline
    results = [await generate_answer(q) for q in sample]
    
    # 3. Check for regressions
    avg_score = mean(r.critique_score for r in results)
    avg_latency = mean(r.latency_ms for r in results)
    
    # 4. Compare with baseline
    baseline = load_baseline(source)
    if avg_score < baseline.score - 0.05:
        alert(f"Quality regression in {source}: {avg_score:.2f} vs {baseline.score:.2f}")
    
    # 5. Update baseline
    save_baseline(source, avg_score, avg_latency)
```

---

## ❌ What I Would NOT Do (And Why)

### Don't Add Weaviate
Agree with the reviewer. Qdrant + BM25 + reranker already gives you hybrid search. Adding Weaviate means:
- Duplicate embeddings (2x storage)
- Sync complexity (which DB is the source of truth?)
- More containers to monitor

**Qdrant alone is sufficient.** If you need better hybrid search later, use Qdrant's built-in sparse vectors (available since Qdrant 1.7+).

### Don't Add Helicone
You have Langfuse. It already tracks costs, latency, and token usage. Helicone would be redundant unless you specifically need its proxy caching feature.

### Don't Add CopilotKit
Your React frontend works. CopilotKit is nice but adds a dependency that you don't need until you have users complaining about the UI.

### Don't Add n8n
Celery + Celery Beat already handles all your scheduled tasks. n8n is great for non-technical users building workflows, but you're a developer writing Python. Stick with Celery.

### Don't Make GraphRAG the Default
Agree with the reviewer. GraphRAG should be a specialized path for complex timeline/evolution questions, not the primary retrieval engine. Your current routing logic (hybrid for most questions, Neo4j for relationship/timeline questions) is the right approach.

### Don't Use Distilabel as Primary Data Source
Distilabel is great for generating synthetic data, but **synthetic UPSC data is risky**. UPSC answers need to be factually precise. A synthetic answer that sounds good but has a wrong Article number is worse than no data at all.

**Use Distilabel for:**
- Generating diverse question formulations
- Creating preference pairs (good vs bad answers)
- Augmenting rare topics

**Don't use Distilabel for:**
- Generating the core knowledge base
- Creating answers without human verification

---

## ✅ What I Would Do (My Actual Plan)

### Week 1: Make It Real
1. **Real embeddings** — Replace zero vectors with sentence-transformers or OpenAI embeddings
2. **Ingest existing data** — Load `mains_gs_all.jsonl` into Qdrant
3. **Basic PIB scraper** — Use Crawl4AI to scrape latest PIB releases
4. **End-to-end test** — Generate one real answer and verify quality

### Week 2: Make It Smart
5. **Model router** — Route tasks to appropriate models (cheap/standard/reasoning)
6. **Targeted fact checker** — UPSC-specific claim verification against Neo4j
7. **Structured training data** — Extract decisions, not just raw CoT
8. **Knowledge freshness** — Add temporal metadata to all chunks

### Week 3: Make It Measurable
9. **Real evaluation** — Replace placeholders with DeepEval + targeted checks
10. **Continuous evaluation** — Auto-benchmark after scraper runs
11. **Data versioning** — Track dataset versions with metadata
12. **Cost tracking** — Per-answer cost breakdown

### Week 4: Make It Better
13. **DSPy GEPA** — Optimize prompts using collected trajectories
14. **DPO pair generation** — Build preference dataset from revisions
15. **Planner supervision** — Train framework selection independently
16. **Retrieval supervision** — Train reranker on selected vs unused chunks

### Month 2-3: Make It Yours
17. **Fine-tune initial model** — SFT on 5,000+ high-quality trajectories
18. **DPO training** — Preference optimization on revision pairs
19. **Evaluate custom model** — Compare against Hermes V2 baseline
20. **Iterate** — Use custom model as Hermes backbone, collect more data

---

## 📊 Revised Tool Stack

| Layer | Tool | Why |
|-------|------|-----|
| Orchestration | LangGraph 1.x | Already using it, upgrade for persistence |
| Prompt optimization | DSPy 3.3 + GEPA | Auto-optimize from your data |
| Vector DB | Qdrant only | Sufficient, no Weaviate needed |
| Graph DB | Neo4j 5 | For relationships, timelines, amendments |
| Embeddings | sentence-transformers | Free, local, good quality |
| Scraping | Crawl4AI | Best for structured government data |
| Evaluation | DeepEval + custom UPSC checks | Standard + domain-specific |
| Synthetic data | Distilabel (carefully) | For augmentation only, not core data |
| Observability | Langfuse + OpenTelemetry | Already have both, sufficient |
| Model routing | Custom (see above) | Task-based routing, 40-60% cost savings |
| Fine-tuning | Unsloth + TRL | Best for Llama/Mistral fine-tuning |
| Data versioning | Custom metadata | Track dataset/model/prompt versions |
| Scheduling | Celery Beat | Already working, no n8n needed |

**Total new tools to install: 4** (sentence-transformers, Crawl4AI, DeepEval, Distilabel)

---

## 💡 The Biggest Insight

The reviewer said: *"Resist the temptation to build everything at once."*

I agree, but I'd go further: **The biggest risk isn't building too many things. It's building things that don't connect.**

Your system has 20+ files but can't produce one real answer because the embeddings are zero vectors and the scrapers return empty lists. The architecture is beautiful but the data pipeline is broken.

**Fix the data pipeline first.** Everything else — GEPA, Distilabel, fine-tuning — depends on having real, high-quality data flowing through the system.

The order is simple:
1. **Data in** (embeddings + scraping + ingestion)
2. **Answers out** (real retrieval + generation)
3. **Quality check** (real evaluation + fact checking)
4. **Data flywheel** (collect trajectories + quality gate)
5. **Optimize** (GEPA + fine-tuning)

Don't jump to step 5 before step 1 works.
