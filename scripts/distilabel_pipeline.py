"""
Hermes V2 — Distilabel Synthetic Data Pipeline
═══════════════════════════════════════════════════════════════
Uses Distilabel (by Argilla) to generate synthetic UPSC Q&A pairs
at scale. This complements the real-user trajectory collection with
massive amounts of diverse training data.

Usage:
    python -m distilabel_pipeline --num-samples 1000 --output dataset/synthetic/
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ── UPSC Question Templates ─────────────────────────────────────────

UPSC_DOMAINS = [
    "Polity", "Economy", "History", "Geography", "Ethics",
    "Science-Tech", "Environment", "International Relations", "Society",
]

QUESTION_TEMPLATES = {
    "Polity": [
        "Discuss the significance of {concept} in the Indian Constitution.",
        "Critically examine the role of {institution} in Indian democracy.",
        "Analyze the evolution of {concept} through constitutional amendments.",
        "Compare the provisions of {concept} in India with {country}.",
    ],
    "Economy": [
        "Discuss the impact of {policy} on India's economic growth.",
        "Analyze the challenges of {sector} in the Indian economy.",
        "Evaluate the effectiveness of {scheme} in addressing {issue}.",
    ],
    "History": [
        "Trace the evolution of {event} and its impact on modern India.",
        "Discuss the role of {person} in {movement}.",
        "Analyze the causes and consequences of {event}.",
    ],
    "Geography": [
        "Discuss the geographical factors influencing {phenomenon} in India.",
        "Analyze the impact of {factor} on {region}'s development.",
    ],
    "Ethics": [
        "Discuss the ethical dimensions of {issue} in public administration.",
        "Analyze the role of {value} in governance with suitable examples.",
    ],
    "Science-Tech": [
        "Discuss the potential of {technology} in transforming {sector} in India.",
        "Analyze the ethical and social implications of {technology}.",
    ],
    "Environment": [
        "Discuss the impact of {factor} on India's biodiversity.",
        "Analyze the effectiveness of {policy} in addressing {issue}.",
    ],
    "International Relations": [
        "Discuss the significance of {event} for India's foreign policy.",
        "Analyze India's role in {organization/forum}.",
    ],
    "Society": [
        "Discuss the challenges of {issue} in Indian society.",
        "Analyze the impact of {factor} on {group} in India.",
    ],
}

CONCEPTS = {
    "Polity": ["federalism", "judicial review", "fundamental rights", "directive principles", "parliamentary democracy", "separation of powers", "basic structure"],
    "Economy": ["GST", "fiscal deficit", "monetary policy", "financial inclusion", "MSMEs", "agricultural reforms", "digital economy"],
    "History": ["Quit India Movement", "Non-Cooperation Movement", "Partition", "Green Revolution", "Emergency", "liberalization"],
    "Geography": ["monsoon", "Himalayan rivers", "coastal erosion", "urbanization", "desification", "cyclones"],
    "Ethics": ["integrity", "empathy", "accountability", "transparency", "compassion", "impartiality"],
    "Science-Tech": ["AI", "quantum computing", "space technology", "biotechnology", "cybersecurity", "5G"],
    "Environment": ["climate change", "biodiversity loss", "water scarcity", "air pollution", "deforestation", "renewable energy"],
    "International Relations": ["UNSC reform", "Indo-Pacific", "BRICS", "G20", "neighborhood first", "Act East Policy"],
    "Society": ["caste discrimination", "gender inequality", "urbanization", "education gap", "healthcare access", "digital divide"],
}


def generate_synthetic_questions(num_samples: int = 1000) -> List[Dict[str, str]]:
    """Generate synthetic UPSC-style questions."""
    import random

    questions = []
    for _ in range(num_samples):
        domain = random.choice(UPSC_DOMAINS)
        templates = QUESTION_TEMPLATES.get(domain, QUESTION_TEMPLATES["Polity"])
        template = random.choice(templates)
        concepts = CONCEPTS.get(domain, ["governance"])
        concept = random.choice(concepts)

        question = template.replace("{concept}", concept)
        question = question.replace("{institution}", random.choice(["Parliament", "Supreme Court", "Election Commission", "CAG", "NITI Aayog"]))
        question = question.replace("{policy}", random.choice(["Make in India", "Digital India", "Skill India", "Startup India"]))
        question = question.replace("{scheme}", random.choice(["PM-KISAN", "Ayushman Bharat", "MGNREGA", "Jan Dhan"]))
        question = question.replace("{sector}", random.choice(["agriculture", "manufacturing", "services", "defense"]))
        question = question.replace("{issue}", random.choice(["poverty", "unemployment", "inequality", "corruption"]))
        question = question.replace("{country}", random.choice(["USA", "UK", "Canada", "Australia", "South Africa"]))
        question = question.replace("{event}", random.choice(concepts))
        question = question.replace("{person}", random.choice(["Gandhi", "Nehru", "Ambedkar", "Patel", "Bose"]))
        question = question.replace("{movement}", random.choice(["freedom struggle", "social reform", "peasant movement"]))
        question = question.replace("{phenomenon}", random.choice(["floods", "droughts", "earthquakes", "landslides"]))
        question = question.replace("{factor}", random.choice(["climate change", "population growth", "industrialization"]))
        question = question.replace("{region}", random.choice(["Northeast", "Western Ghats", "Thar Desert", "Coastal India"]))
        question = question.replace("{value}", random.choice(["integrity", "empathy", "objectivity", "dedication"]))
        question = question.replace("{technology}", random.choice(["AI", "blockchain", "IoT", "robotics"]))
        question = question.replace("{organization/forum}", random.choice(["UN", "WTO", "IMF", "World Bank"]))
        question = question.replace("{group}", random.choice(["women", "SC/ST", "OBC", "minorities", "disabled"]))

        questions.append({
            "question": question,
            "domain": domain,
            "synthetic": True,
        })

    return questions


def create_distilabel_pipeline(
    num_samples: int = 1000,
    output_dir: str | Path = "dataset/synthetic",
    model: str = "openrouter/owl-alpha",
) -> Dict[str, Any]:
    """
    Create and run a Distilabel pipeline for synthetic UPSC data generation.

    Falls back to a simple implementation if Distilabel is not installed.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        # Try to use Distilabel
        from distilabel.pipeline import Pipeline
        from distilabel.steps import LoadDataFromDicts
        from distilabel.steps.tasks import TextGeneration
        from distilabel.llms import OpenAILLM

        questions = generate_synthetic_questions(num_samples)

        llm = OpenAILLM(
            model=model,
            api_key="",
            api_base="https://openrouter.ai/api/v1",
        )

        with Pipeline("upsc-synthetic-generation") as pipeline:
            load_data = LoadDataFromDicts(data=questions)

            generate_answer = TextGeneration(
                llm=llm,
                system_prompt=(
                    "You are a UPSC Civil Services expert. Generate a comprehensive, "
                    "well-structured answer (800-1200 words) with proper citations "
                    "(Articles, Amendments, cases). Use the <think></think> format "
                    "for your reasoning."
                ),
                input_batch_size=5,
                output_mappings={"generation": "synthetic_answer"},
            )

            load_data >> generate_answer

        distiset = pipeline.run()

        # Save
        output_file = output_path / "synthetic_upsc_data.jsonl"
        with open(output_file, "w", encoding="utf-8") as f:
            for batch in distiset["default"]["train"]:
                for item in batch:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")

        logger.info("[DISTILABEL] Generated %d synthetic samples.", num_samples)
        return {"status": "success", "samples": num_samples, "output": str(output_file)}

    except ImportError:
        # Fallback: generate questions without Distilabel
        logger.info("[DISTILABEL] Not installed. Using fallback generation.")
        return _fallback_generation(num_samples, output_path)


def _fallback_generation(num_samples: int, output_path: Path) -> Dict[str, Any]:
    """Generate synthetic data without Distilabel (using LLM gateway directly)."""
    questions = generate_synthetic_questions(num_samples)
    output_file = output_path / "synthetic_upsc_questions.jsonl"

    with open(output_file, "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    logger.info("[FALLBACK] Generated %d synthetic questions (no answers yet).", num_samples)
    return {
        "status": "partial",
        "samples": num_samples,
        "output": str(output_file),
        "note": "Install distilabel for full pipeline: pip install distilabel",
    }


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic UPSC data")
    parser.add_argument("--num-samples", type=int, default=1000)
    parser.add_argument("--output", default="dataset/synthetic")
    parser.add_argument("--model", default="openrouter/owl-alpha")
    args = parser.parse_args()

    results = create_distilabel_pipeline(
        num_samples=args.num_samples,
        output_dir=args.output,
        model=args.model,
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
