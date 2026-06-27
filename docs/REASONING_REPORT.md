# Hermes V2 — Reasoning & Recursive Loop Report
> How the system thinks, decides, and iterates to generate UPSC answers

---

## 🧠 The 8-Node Cognitive Pipeline

Every UPSC question passes through 8 cognitive nodes. Here's what each node considers and WHY:

---

### Node 1: Topic Detection
**What it does:** Classifies the question into domain, type, entities, and constitutional weight.

**What it considers:**
- **Domain:** Polity, Economy, History, Geography, Ethics, Science-Tech, Environment, IR, Society
- **Question type:** factual, analytical, evaluative, comparison, evolution, relationship, timeline, constitutional_amendment_chain, institutional_interaction
- **Entities:** Key people, articles, amendments, cases, institutions mentioned
- **Constitutional weight:** HIGH (involves Articles/Amendments/Cases), MEDIUM (tangential), LOW (none)

**WHY this matters:** The domain determines which knowledge base partitions to search. The question type determines the answer framework. Constitutional weight determines how heavily to cite legal provisions.

**Model used:** Cheap tier (GPT-OSS-120B) — this is a simple classification task.

---

### Node 2: Hybrid Retrieval
**What it does:** Finds relevant knowledge chunks from the knowledge base.

**What it considers:**
- **Dense vectors (Qdrant):** Semantic similarity — finds conceptually related content even if keywords don't match
- **Sparse vectors (BM25):** Keyword matching — finds exact term matches
- **RRF Fusion:** Combines both rankings using Reciprocal Rank Fusion (k=60)
- **Cross-Encoder Reranker:** Rescores top candidates for precision
- **Neo4j (conditional):** For relationship/timeline questions, traverses the knowledge graph
- **Knowledge freshness:** Deprioritizes outdated content, boosts newer material

**WHY this matters:** UPSC answers need both conceptual understanding (dense) and factual precision (sparse). The hybrid approach ensures neither is missed.

**Routing logic:**
```
if question_type in ["relationship", "timeline", "constitutional_amendment_chain", "institutional_interaction"]:
    → Use Neo4j graph traversal (targeted)
elif question_type in ["evolution", "comparison"]:
    → Use BOTH hybrid + graph (hybrid_and_graph)
else:
    → Use hybrid only (hybrid_only)
```

---

### Node 3: Framework Planning
**What it does:** Selects the answer framework and produces a reasoning plan.

**What it considers:**
- **Framework selection:** PESTLE, Timeline, Pro-Con, Institutional, Thematic, Cause-Effect, Comparative, Spatial
- **Examiner persona:** Who is evaluating this answer? What do they expect?
- **Common trap:** What mistake do most students make on this question?
- **Differentiator:** What non-obvious insight would elevate this answer?
- **Reasoning plan:** Step-by-step structure — intro strategy, body paragraphs, conclusion hook

**WHY this matters:** UPSC answers are evaluated on structure and framework adherence. A well-planned answer scores higher than a disorganized one, even with the same content.

**Model used:** Standard tier (Gemini 2.5 Flash) — needs moderate reasoning.

---

### Node 4: Answer Drafting
**What it does:** Generates the first full-length draft answer (800-1200 words).

**What it considers:**
- **The framework** from Node 3 (structure to follow)
- **The reasoning plan** from Node 3 (what to cover in each section)
- **Retrieved context** from Node 2 (evidence to cite)
- **Constitutional weight** (how heavily to reference Articles/Amendments/Cases)

**WHY this matters:** The draft is the first attempt. It doesn't need to be perfect — the review-revision loop will improve it.

**Model used:** Standard tier (Gemini 2.5 Flash) — main generation task.

---

### Node 5: Critique & Review
**What it does:** Critiques the draft and assigns a quality score (0.0-1.0).

**What it considers (6 dimensions):**
1. **Factual accuracy** — Are the facts correct?
2. **Structural coherence** — Does it follow the framework?
3. **Depth of analysis** — Multi-dimensional? Critical thinking?
4. **Constitutional grounding** — Articles/Amendments cited correctly?
5. **Examples & data** — Relevant case studies, committee recommendations?
6. **Conclusion quality** — Forward-looking? Balanced?

**Plus fact checking:**
- Extracts verifiable claims (Articles, Amendments, cases, dates)
- Verifies against Neo4j knowledge graph (DB lookup, not LLM)
- Falls back to LLM-based check if DB unavailable

**WHY this matters:** This is the quality gate. The critique score determines whether the answer is accepted or sent back for revision.

**Model used:** Reasoning tier (DeepSeek R1) — needs deep analysis.

---

### Node 6: Revision (Conditional)
**What it does:** Rewrites the answer based on critique feedback.

**When it activates:**
```
if critique_score < 0.9 OR fact_check_passed == False:
    if revision_iterations < 2:
        → REVISE (go to Node 6)
    else:
        → EXPORT anyway (max iterations reached)
```

**What it considers:**
- **The original draft** (what to improve)
- **The critique** (specific weaknesses to address)
- **The framework** (maintain structure while improving)

**WHY this matters:** Most answers need 1-2 revisions to reach quality threshold. The loop ensures continuous improvement.

**Model used:** Standard tier (Gemini 2.5 Flash) — regeneration with feedback.

---

### Node 7: Verification
**What it does:** Runs multi-layer verification before final output.

**Three layers:**
1. **Fact check** (reused from Node 5) — Was the fact check passed?
2. **Guardrails** — Content safety check (no bias, no hedging, no "As an AI...")
3. **Constitutional check** (if HIGH weight) — Verify all Articles/Amendments/cases exist in knowledge graph

**WHY this matters:** Final safety net. Even if the critique score is high, verification catches factual errors that the critique might have missed.

---

### Node 8: Export
**What it does:** Quality-gates the trajectory and writes training data.

**Quality gates (ALL must pass):**
1. Critique score ≥ 0.9
2. Fact check passed
3. Guardrails passed
4. Revisions ≤ 2
5. Answer length ≥ 200 words
6. Constitutional check passed (if HIGH weight)

**What it writes:**
- `trajectories.jsonl` — Full trajectory (all steps)
- `chatml_sft.jsonl` — ChatML format for SFT fine-tuning
- `dpo_pairs.jsonl` — Preference pairs (draft vs improved)
- `orpo_pairs.jsonl` — ORPO format pairs
- `reward_model.jsonl` — Reward model training data
- `rejected.jsonl` — Failed trajectories (for analysis)

---

## 🔄 The Recursive Loop Explained

```
                    ┌─────────────────────────────────────┐
                    │         LangGraph Orchestrator       │
                    └─────────────────────────────────────┘
                                      │
    ┌───────────┐    ┌───────────┐    │    ┌───────────┐    ┌───────────┐
    │  Topic     │───▶│ Retrieval │───▶│───▶│ Planning  │───▶│ Drafting  │
    │ Detection  │    │ (Hybrid)  │    │    │(Framework)│    │ (First)   │
    └───────────┘    └───────────┘    │    └───────────┘    └───────────┘
                                      │                           │
                                      │                           ▼
                                      │                    ┌───────────┐
                                      │                    │  Review   │
                                      │                    │(Critique) │
                                      │                    └─────┬─────┘
                                      │                          │
                                      │              ┌───────────┴───────────┐
                                      │              │                       │
                                      │              ▼                       ▼
                                      │       ┌───────────┐          ┌───────────┐
                                      │       │ Revision  │          │Verification│
                                      │       │ (Improve) │          │ (3 Layers) │
                                      │       └─────┬─────┘          └─────┬─────┘
                                      │             │                     │
                                      │             └──────────┬──────────┘
                                      │                        │
                                      │                        ▼
                                      │                 ┌───────────┐
                                      │                 │  Export   │
                                      │                 │(Quality   │
                                      │                 │  Gate)    │
                                      │                 └───────────┘
                                      │
                    ┌─────────────────────────────────────────────────┐
                    │  should_revise() decides:                       │
                    │                                                  │
                    │  if score >= 0.9 AND fact_check_passed:          │
                    │      → "verify" (skip revision)                  │
                    │  elif revision_iterations >= 2:                 │
                    │      → "verify" (max iterations reached)         │
                    │  else:                                           │
                    │      → "revise" (improve and re-review)          │
                    └─────────────────────────────────────────────────┘
```

### Loop Behavior

| Scenario | Iterations | What Happens |
|----------|-----------|--------------|
| Perfect draft | 0 | Score ≥ 0.9 + fact check pass → skip revision |
| Good draft, minor issues | 1 | Score < 0.9 → revise → re-review → pass |
| Poor draft | 2 | Score < 0.9 → revise → re-review → still < 0.9 → revise → re-review → export anyway |
| Fact check fail | 1-2 | Fact check fails → revise addressing issues → re-check |

**Maximum iterations: 2** (configurable via `ORCHESTRACTOR_MAX_REVISIONS`)

**Why max 2?** Beyond 2 revisions, the model tends to loop without improvement. Better to export with a lower score than to waste compute.

---

## 📊 Model Routing Strategy

| Task | Model | Cost Tier | Why |
|------|-------|-----------|-----|
| Topic detection | GPT-OSS-120B | Cheap ($0.05/1M) | Simple classification |
| Retrieval | None (vector search) | Free | No LLM needed |
| Planning | Gemini 2.5 Flash | Standard ($0.15/1M) | Moderate reasoning |
| Drafting | Gemini 2.5 Flash | Standard ($0.15/1M) | Main generation |
| Critique | DeepSeek R1 | Reasoning ($0.50/1M) | Deep analysis needed |
| Fact check | Neo4j DB lookup | Free | Deterministic verification |
| Revision | Gemini 2.5 Flash | Standard ($0.15/1M) | Regeneration with feedback |
| Verification | Neo4j + regex | Free | DB lookup + pattern matching |

**Estimated cost per answer:** $0.003-0.015 (depending on revisions)

---

## 🔒 Quality Gating

Only ~30-40% of generated answers pass all quality gates. This is intentional — we only train on perfect data.

| Gate | Threshold | Purpose |
|------|-----------|---------|
| Critique score | ≥ 0.9 | Expert-level quality |
| Fact check | PASSED | Zero hallucinations |
| Guardrails | PASSED | No bias/hedging |
| Revisions | ≤ 2 | Efficient generation |
| Answer length | ≥ 200 words | Substantive content |
| Constitutional | PASSED (if HIGH) | Legal citations verified |

---

## 📁 Training Data Output

Every answer generation run produces:

| File | Format | Records |
|------|--------|---------|
| `trajectories.jsonl` | Full trajectory | All runs |
| `chatml_sft.jsonl` | ChatML | Quality-gated only |
| `dpo_pairs.jsonl` | Preference pairs | When revision happened |
| `orpo_pairs.jsonl` | ORPO pairs | When revision happened |
| `reward_model.jsonl` | Score + rubric | Quality-gated only |
| `rejected.jsonl` | Full trajectory | Failed runs (for analysis) |

**Expected data volume:**
- 50-200 questions/day → 15-80 quality records/day
- 450-2,400 records/month
- 10,000+ records in 3-6 months (enough for fine-tuning)
