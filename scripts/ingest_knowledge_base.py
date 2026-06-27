"""
Hermes V2 — Knowledge Base Ingestion Script
═══════════════════════════════════════════════════════════════
One-time (or periodic) script to ingest UPSC knowledge into Qdrant + Neo4j.

Sources:
  1. Previous year questions (dataset/mains_gs_all.jsonl)
  2. Previous year questions (dataset/prelims_gs_all.jsonl)
  3. CSAT dataset (dataset/csat_dataset_all.jsonl)

Usage:
    python -m ingest_knowledge_base
    python -m ingest_knowledge_base --source mains --batch-size 64
    python -m ingest_knowledge_base --rebuild  # Drop and recreate collection
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync context."""
    return asyncio.run(coro)

# ── Embedding ────────────────────────────────────────────────────────

class Embedder:
    """Wrapper for sentence-transformers embedding model."""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self._model = None
        self._model_name = model_name
    
    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("[EMBED] Loading model: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            logger.info("[EMBED] Model loaded. Embedding dim: %s", self._model.get_sentence_embedding_dimension())
    
    def encode(self, texts: list[str]) -> list[list[float]]:
        self._load()
        return self._model.encode(texts, show_progress_bar=True).tolist()
    
    @property
    def dim(self) -> int:
        self._load()
        return self._model.get_sentence_embedding_dimension()


# ── Chunking ─────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping word chunks."""
    words = text.split()
    if len(words) <= chunk_size:
        return [text]
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks


# ── Qdrant Ingestion ─────────────────────────────────────────────────

def ingest_to_qdrant(
    chunks: list[dict],
    collection: str = "upsc_knowledge",
    batch_size: int = 64,
) -> int:
    """Ingest chunks into Qdrant. Returns count of indexed chunks."""
    from qdrant_client.http.models import PointStruct, Distance, VectorParams
    from core.db_qdrant import get_qdrant_client
    from core.config import get_settings
    
    client = get_qdrant_client()
    settings = get_settings()
    embedder = Embedder()
    
    # Ensure collection exists
    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=embedder.dim, distance=Distance.COSINE),
        )
        logger.info("[QDRANT] Created collection: %s", collection)
    
    total = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["text"] for c in batch]
        vectors = embedder.encode(texts)
        
        points = []
        for chunk, vector in zip(batch, vectors):
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text": chunk["text"],
                    "source": chunk.get("source", "unknown"),
                    "domain": chunk.get("domain", "general"),
                    "year": chunk.get("year"),
                    "paper": chunk.get("paper"),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                },
            ))
        
        client.upsert(collection_name=collection, points=points, wait=True)
        total += len(points)
        logger.info("[QDRANT] Ingested %d/%d chunks", total, len(chunks))
    
    return total


# ── Neo4j Ingestion ─────────────────────────────────────────────────

def ingest_to_neo4j(entities: list[dict]) -> int:
    """Ingest entities and relationships into Neo4j."""
    from core.db_neo4j import execute_cypher
    
    count = 0
    for entity in entities:
        try:
            if entity["type"] == "article":
                _run_async(execute_cypher(
                    "MERGE (a:Article {number: $num}) SET a.description = $desc, a.part = $part",
                    {"num": entity["value"], "desc": entity.get("description", ""), "part": entity.get("part", "")},
                ))
            elif entity["type"] == "amendment":
                _run_async(execute_cypher(
                    "MERGE (a:Amendment {number: $num}) SET a.year = $year, a.description = $desc",
                    {"num": entity["value"], "year": entity.get("year", 0), "desc": entity.get("description", "")},
                ))
            elif entity["type"] == "case":
                _run_async(execute_cypher(
                    "MERGE (c:Case {name: $name}) SET c.year = $year, c.significance = $sig",
                    {"name": entity["value"], "year": entity.get("year", 0), "sig": entity.get("significance", "")},
                ))
            elif entity["type"] == "relationship":
                _run_async(execute_cypher(
                    "MATCH (a {name: $from}), (b {name: $to}) MERGE (a)-[r:RELATED_TO]->(b) SET r.description = $desc",
                    {"from": entity["from"], "to": entity["to"], "desc": entity.get("description", "")},
                ))
            count += 1
        except Exception as exc:
            logger.warning("[NEO4J] Failed to ingest entity %s: %s", entity, exc)
    
    return count


# ── Data Loaders ────────────────────────────────────────────────────

def load_mains_dataset(path: str = "dataset/mains_gs_all.jsonl") -> list[dict]:
    """Load UPSC Mains GS questions into chunks."""
    chunks = []
    p = Path(path)
    if not p.exists():
        logger.warning("[LOAD] File not found: %s", path)
        return chunks
    
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                question = record.get("question", "")
                answer = record.get("answer", record.get("model_answer", ""))
                year = record.get("year")
                paper = record.get("paper", "GS")
                subject = record.get("subject", record.get("domain", "general"))
                
                # Chunk the question + answer
                full_text = f"Question: {question}\n\nAnswer: {answer}"
                for idx, chunk in enumerate(chunk_text(full_text)):
                    chunks.append({
                        "text": chunk,
                        "source": f"mains_{year}_{paper}" if year else "mains",
                        "domain": subject,
                        "year": year,
                        "paper": paper,
                        "chunk_index": idx,
                    })
            except json.JSONDecodeError:
                continue
    
    logger.info("[LOAD] Loaded %d chunks from %s", len(chunks), path)
    return chunks


def load_prelims_dataset(path: str = "dataset/prelims_gs_all.jsonl") -> list[dict]:
    """Load UPSC Prelims questions into chunks."""
    chunks = []
    p = Path(path)
    if not p.exists():
        return chunks
    
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                question = record.get("question", "")
                options = record.get("options", [])
                answer = record.get("answer", "")
                explanation = record.get("explanation", "")
                year = record.get("year")
                
                # Handle options as list of dicts or strings
                if options and isinstance(options[0], dict):
                    options_str = " | ".join(o.get("text", o.get("option", str(o))) for o in options)
                else:
                    options_str = " | ".join(str(o) for o in options)
                full_text = f"Question: {question}\n\nOptions: {options_str}\nAnswer: {answer}\nExplanation: {explanation}"
                for idx, chunk in enumerate(chunk_text(full_text)):
                    chunks.append({
                        "text": chunk,
                        "source": f"prelims_{year}" if year else "prelims",
                        "domain": record.get("subject", "general"),
                        "year": year,
                        "paper": "Prelims",
                        "chunk_index": idx,
                    })
            except json.JSONDecodeError:
                continue
    
    logger.info("[LOAD] Loaded %d chunks from %s", len(chunks), path)
    return chunks


def load_constitutional_entities() -> list[dict]:
    """Load key constitutional entities into Neo4j."""
    entities = []
    
    # Key Articles
    articles = [
        {"number": "1", "description": "Name and territory of the Union", "part": "I"},
        {"number": "14", "description": "Equality before law", "part": "III"},
        {"number": "19", "description": "Protection of certain rights regarding freedom of speech", "part": "III"},
        {"number": "21", "description": "Protection of life and personal liberty", "part": "III"},
        {"number": "21A", "description": "Right to education", "part": "III"},
        {"number": "32", "description": "Remedies for enforcement of rights", "part": "III"},
        {"number": "44", "description": "Uniform civil code", "part": "IV"},
        {"number": "51A", "description": "Fundamental duties", "part": "IVA"},
        {"number": "226", "description": "Power of High Courts to issue certain writs", "part": "V"},
        {"number": "368", "description": "Power of Parliament to amend the Constitution", "part": "XX"},
    ]
    for a in articles:
        entities.append({"type": "article", "value": a["number"], "description": a["description"], "part": a["part"]})
    
    # Key Amendments
    amendments = [
        {"number": "42nd", "year": 1976, "description": "Mini Constitution — added Socialist, Secular, Integrity to Preamble"},
        {"number": "44th", "year": 1978, "description": "Right to Property removed from Fundamental Rights"},
        {"number": "73rd", "year": 1992, "description": "Panchayati Raj institutions"},
        {"number": "86th", "year": 2002, "description": "Right to Education (Article 21A)"},
        {"number": "101st", "year": 2016, "description": "Goods and Services Tax (GST)"},
        {"number": "103rd", "year": 2019, "description": "10% EWS reservation"},
    ]
    for a in amendments:
        entities.append({"type": "amendment", "value": a["number"], "year": a["year"], "description": a["description"]})
    
    # Key Cases
    cases = [
        {"name": "Kesavananda Bharati v. Kerala", "year": 1973, "significance": "Basic Structure Doctrine established"},
        {"name": "Maneka Gandhi v. Union of India", "year": 1978, "significance": "Expanded Article 21 — due process"},
        {"name": "Minerva Mills v. Union of India", "year": 1980, "significance": "Limited Parliament's amending power"},
        {"name": "Indira Gandhi v. Raj Narain", "year": 1975, "significance": "Free and fair elections part of basic structure"},
        {"name": "S.R. Bommai v. Union of India", "year": 1994, "significance": "Secularism is part of basic structure"},
        {"name": "Vishaka v. State of Rajasthan", "year": 1997, "significance": "Sexual harassment guidelines"},
        {"name": "Navtej Singh Johar v. Union of India", "year": 2018, "significance": "Decriminalized homosexuality — Section 377"},
        {"name": "Joseph Shine v. Union of India", "year": 2018, "significance": "Struck down adultery law — Section 497"},
    ]
    for c in cases:
        entities.append({"type": "case", "value": c["name"], "year": c["year"], "significance": c["significance"]})
    
    logger.info("[LOAD] Prepared %d constitutional entities for Neo4j", len(entities))
    return entities


# ── Main Pipeline ───────────────────────────────────────────────────

def run_ingestion(
    source: str = "all",
    rebuild: bool = False,
    batch_size: int = 64,
) -> Dict[str, Any]:
    """Run the full ingestion pipeline."""
    results = {"started_at": datetime.now(timezone.utc).isoformat()}
    
    # 0. Rebuild: drop and recreate Qdrant collection if requested
    if rebuild:
        logger.info("[INGEST] Rebuild mode: dropping existing Qdrant collection...")
        try:
            from core.db_qdrant import get_qdrant_client
            from core.config import get_settings
            client = get_qdrant_client()
            settings = get_settings()
            client.delete_collection(collection_name=settings.QDRANT_COLLECTION)
            logger.info("[INGEST] Dropped collection '%s'.", settings.QDRANT_COLLECTION)
        except Exception as exc:
            logger.warning("[INGEST] Could not drop collection (may not exist): %s", exc)
    
    # 1. Load data
    all_chunks = []
    if source in ("all", "mains"):
        all_chunks.extend(load_mains_dataset())
    if source in ("all", "prelims"):
        all_chunks.extend(load_prelims_dataset())
    
    results["total_chunks"] = len(all_chunks)
    
    if not all_chunks:
        logger.warning("[INGEST] No data found. Check dataset paths.")
        return results
    
    # 2. Ingest to Qdrant
    qdrant_count = ingest_to_qdrant(all_chunks, batch_size=batch_size)
    results["qdrant_chunks"] = qdrant_count
    
    # 3. Ingest constitutional entities to Neo4j
    entities = load_constitutional_entities()
    neo4j_count = ingest_to_neo4j(entities)
    results["neo4j_entities"] = neo4j_count
    
    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("[INGEST] Complete: %s", results)
    return results


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest UPSC knowledge base")
    parser.add_argument("--source", default="all", choices=["all", "mains", "prelims"])
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    
    results = run_ingestion(source=args.source, rebuild=args.rebuild, batch_size=args.batch_size)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
