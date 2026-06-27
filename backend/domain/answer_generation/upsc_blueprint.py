"""
UPSC Blueprint Planner
═══════════════════════════════════════════════════════════════
Generates a structured, domain-specific blueprint for UPSC answers.

This is the single most important component for answer quality.
Instead of asking the LLM to "write an answer", we first create
a detailed blueprint, then ask the LLM to follow it strictly.

Example blueprint for "Harappan Architecture":
{
  "marks": 15,
  "target_words": 250,
  "time_minutes": 15,
  "sections": [
    {"name": "Introduction", "words": 40, "content": "Brief context of Harappan civilization (2600-1900 BCE), Indus Valley, urban planning pioneer"},
    {"name": "Urban Planning", "words": 50, "content": "Grid pattern, Citadel vs Lower Town, Mohenjo-daro layout, burnt bricks"},
    {"name": "Public Buildings", "words": 40, "content": "Great Bath (ritual bathing), Granaries (food storage), Assembly halls"},
    {"name": "Water & Drainage", "words": 40, "content": "Covered drains, soak pits, wells, Great Bath water management"},
    {"name": "Residential Architecture", "words": 30, "content": "Standardized bricks (1:2:4 ratio), multi-story houses, courtyards"},
    {"name": "Examples", "words": 30, "content": "Mohenjo-daro, Harappa, Dholavira, Lothal dockyard"},
    {"name": "Conclusion", "words": 20, "content": "Legacy: most advanced urban planning of ancient world, influence on later Indian architecture"}
  ],
  "examples": ["Mohenjo-daro", "Harappa", "Dholavira", "Lothal", "Kalibangan", "Banawali"],
  "visual": "City layout diagram showing Citadel, Lower Town, drainage system",
  "must_include": ["Grid pattern", "Great Bath", "Standardized bricks (1:2:4)", "Covered drainage", "Citadel vs Lower Town"],
  "examiner_expects": ["Specific site names", "Architectural terminology", "Comparative analysis", "Diagram/flowchart"],
  "common_mistakes": ["Vague descriptions without site names", "Missing drainage system", "No examples", "Too much history, not enough architecture"],
  "framework": "Thematic",
  "diagram_type": "city_layout"
}
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Domain-specific rubrics ──────────────────────────────────────────

DOMAIN_RUBRICS = {
    "History": {
        "sections": ["Introduction", "Main Body (thematic)", "Examples/Evidence", "Conclusion"],
        "key_criteria": ["Chronology", "Specific examples", "Cause-Effect", "Maps/Diagrams"],
        "common_mistakes": ["Vague dates", "No site names", "Missing causation"],
    },
    "Polity": {
        "sections": ["Introduction (constitutional provision)", "Provisions", "Significance", "Challenges", "Judgments", "Conclusion"],
        "key_criteria": ["Article numbers", "Case law", "Committee recommendations", "Comparative analysis"],
        "common_mistakes": ["Missing article numbers", "No case law", "Vague recommendations"],
    },
    "Economy": {
        "sections": ["Introduction (concept/scheme)", "Features", "Significance", "Challenges", "Way Forward", "Conclusion"],
        "key_criteria": ["Data/statistics", "Scheme details", "Fiscal impact", "International comparison"],
        "common_mistakes": ["No data", "Missing challenges", "No way forward"],
    },
    "Geography": {
        "sections": ["Introduction (location/extent)", "Physical Features", "Climate", "Human Geography", "Conclusion"],
        "key_criteria": ["Maps", "Lat/Long", "Climatic data", "Distribution patterns"],
        "common_mistakes": ["No map references", "Missing data", "Vague descriptions"],
    },
    "Environment": {
        "sections": ["Introduction (concept/issue)", "Causes", "Impacts", "Measures", "International Agreements", "Conclusion"],
        "key_criteria": ["Species names", "Data", "Policy references", "International conventions"],
        "common_mistakes": ["No specific species", "Missing data", "No policy framework"],
    },
    "Science-Tech": {
        "sections": ["Introduction (concept)", "Working Principle", "Applications", "Advantages/Limitations", "Indian Context", "Conclusion"],
        "key_criteria": ["Technical accuracy", "Indian examples", "Current developments"],
        "common_mistakes": ["Too technical without context", "No Indian examples"],
    },
    "IR": {
        "sections": ["Introduction (context)", "Background", "Current Developments", "India's Position", "Challenges", "Conclusion"],
        "key_criteria": ["Treaties", "Organizations", "Recent events", "India's interests"],
        "common_mistakes": ["No recent developments", "Missing India's perspective"],
    },
    "Ethics": {
        "sections": ["Introduction (ethical dilemma)", "Stakeholders", "Ethical Dimensions", "Options", "Best Option", "Conclusion"],
        "key_criteria": ["Moral thinkers", "Case studies", "Stakeholder analysis", "Ethical framework"],
        "common_mistakes": ["No stakeholder analysis", "Missing ethical framework", "No thinkers"],
    },
    "Society": {
        "sections": ["Introduction (issue)", "Causes", "Consequences", "Government Measures", "Way Forward", "Conclusion"],
        "key_criteria": ["Data (Census/NSSO)", "Scheme names", "Committee reports", "Social impact"],
        "common_mistakes": ["No data", "Missing scheme names", "Vague measures"],
    },
}


def generate_blueprint_prompt(
    question: str,
    domain: str,
    marks: int,
    question_type: str,
    entities: List[str],
    sub_topics: List[str],
) -> str:
    """Generate a domain-specific blueprint prompt."""
    rubric = DOMAIN_RUBRICS.get(domain, DOMAIN_RUBRICS["History"])

    return f"""You are a senior UPSC examiner and answer strategist. Create a detailed blueprint for this {marks}-mark {domain} question.

QUESTION: {question}

DOMAIN: {domain}
TYPE: {question_type}
KEY ENTITIES: {', '.join(entities) if entities else 'Identify from question'}
SUB-TOPICS: {', '.join(sub_topics) if sub_topics else 'Identify from question'}

DOMAIN-SPECIFIC RUBRIC:
- Sections: {' → '.join(rubric['sections'])}
- Key Criteria: {', '.join(rubric['key_criteria'])}
- Common Mistakes: {', '.join(rubric['common_mistakes'])}

Return JSON with:
  marks — {marks}
  target_words — {220 if marks == 15 else 150} (strict word limit for {marks}-mark question)
  time_minutes — {15 if marks == 15 else 10}
  sections — list of {{name, words, content}} (allocate words across sections)
  examples — list of 4-6 specific examples/data points expected
  visual — describe diagram/chart/table needed (or "none")
  must_include — list of 5-7 specific points examiner expects
  examiner_expects — list of 3-4 things examiner looks for
  common_mistakes — list of 3-4 mistakes to avoid
  framework — Thematic / Timeline / Pro-Con / Institutional / Cause-Effect
  diagram_type — city_layout / flowchart / table / timeline / map / process / none

RULES:
1. Allocate target_words across sections (must sum to target_words)
2. Examples must be SPECIFIC (site names, article numbers, scheme names, data)
3. must_include should be examiner's expected keywords
4. visual should describe exactly what diagram to draw
5. common_mistakes should be specific to this question

Return ONLY valid JSON."""


def create_fallback_blueprint(
    question: str,
    domain: str,
    marks: int,
) -> Dict[str, Any]:
    """Create a basic blueprint when LLM fails."""
    rubric = DOMAIN_RUBRICS.get(domain, DOMAIN_RUBRICS["History"])
    target_words = 220 if marks == 15 else 150

    return {
        "marks": marks,
        "target_words": target_words,
        "time_minutes": 15 if marks == 15 else 10,
        "sections": [
            {"name": "Introduction", "words": 40, "content": "Brief context and thesis"},
            {"name": "Main Body", "words": target_words - 70, "content": "Thematic coverage of key aspects"},
            {"name": "Examples/Evidence", "words": 30, "content": "Specific examples and data"},
            {"name": "Conclusion", "words": 30, "content": "Forward-looking summary"},
        ],
        "examples": [],
        "visual": "none",
        "must_include": rubric["key_criteria"][:3],
        "examiner_expects": rubric["key_criteria"],
        "common_mistakes": rubric["common_mistakes"],
        "framework": "Thematic",
        "diagram_type": "none",
    }


# ═══════════════════════════════════════════════════════════════════
# NODE: UPSC Blueprint Planner
# ═══════════════════════════════════════════════════════════════════

async def node_upsc_blueprint(state: dict) -> dict:
    """
    Generate a UPSC-specific answer blueprint.
    
    This is the MOST IMPORTANT node for answer quality.
    It tells the drafting agent EXACTLY what to write.
    """
    t0 = time.monotonic()
    question = state.get("question", "")
    domain = state.get("domain", "General Studies")
    marks = state.get("marks", 15)
    question_type = state.get("question_type", "analytical")
    entities = state.get("detected_entities", [])
    sub_topics = state.get("sub_topics", [])
    evidence = state.get("evidence_chunks", [])

    system_prompt = generate_blueprint_prompt(
        question=question,
        domain=domain,
        marks=marks,
        question_type=question_type,
        entities=entities,
        sub_topics=sub_topics,
    )

    # Include evidence context if available
    evidence_text = ""
    if evidence:
        evidence_text = "\n\nRETRIEVED EVIDENCE:\n"
        for i, chunk in enumerate(evidence[:5]):
            text = chunk.get("text", "")[:200] if isinstance(chunk, dict) else str(chunk)[:200]
            evidence_text += f"[Chunk {i+1}] {text}\n"

    try:
        from core.llm_gateway import LLMGateway
        gateway = LLMGateway()
        response = await gateway.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{evidence_text}\n\nGenerate the blueprint now."}
            ],
            temperature=0.2,
            max_tokens=1024,
            use_cache=False,
        )
        content = response.content.strip()
        result = _safe_json_parse_limited(content)
        latency = (time.monotonic() - t0) * 1000

        if not result or "sections" not in result:
            logger.warning("[UPSC BLUEPRINT] LLM returned invalid blueprint, using fallback")
            result = create_fallback_blueprint(question, domain, marks)

        return {
            "blueprint": result,
            "blueprint_latency_ms": latency,
            "cot_trace": _append_cot(state, "upsc_blueprint",
                f"Blueprint: {marks} marks, {result.get('target_words')} words, "
                f"{len(result.get('sections', []))} sections, "
                f"diagram={result.get('diagram_type', 'none')}",
                {"marks": marks, "target_words": result.get("target_words")},
                latency_ms=latency),
        }
    except Exception as exc:
        logger.error("[UPSC BLUEPRINT] Failed: %s", exc)
        result = create_fallback_blueprint(question, domain, marks)
        return {
            "blueprint": result,
            "blueprint_latency_ms": (time.monotonic() - t0) * 1000,
            "cot_trace": _append_cot(state, "upsc_blueprint",
                f"FALLBACK: {marks} marks", {"marks": marks}),
        }


def _safe_json_parse_limited(content: str) -> dict:
    """Parse JSON from LLM response."""
    if not content:
        return {}
    try:
        return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        pass
    # Try extracting from markdown
    import re
    block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', content, re.DOTALL)
    if block_match:
        try:
            return json.loads(block_match.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass
    # Try finding first { to last }
    start = content.find('{')
    end = content.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(content[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


def _append_cot(state: dict, node_name: str, thought: str, output: dict, latency_ms: float = 0) -> list:
    """Append a CoT step to the state's trace."""
    trace = list(state.get("cot_trace", []))
    trace.append({
        "step_number": len(trace) + 1,
        "node": node_name,
        "thought": thought,
        "output": output,
        "latency_ms": latency_ms,
    })
    return trace
