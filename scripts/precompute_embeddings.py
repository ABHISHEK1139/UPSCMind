"""
Pre-compute embeddings for all 150 UPSC questions and store in Qdrant.
This eliminates the need for runtime embedding — the retrieval node
can just search Qdrant directly using pre-computed vectors.

Run this ONCE before the test. Takes ~10 min on GPU, ~3 hours on CPU.
"""
import asyncio
import json
import logging
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Load the 150 questions from test file ─────────────────────────
def load_questions():
    """Parse QUESTIONS list from test_upsc_human.py without importing it."""
    test_file = Path(__file__).parent / "test_upsc_human.py"
    content = test_file.read_text()
    # Extract the QUESTIONS list using exec in a safe namespace
    ns = {}
    # Find the QUESTIONS = [ ... ] block
    start = content.index("QUESTIONS = [")
    # Find the matching closing bracket
    bracket_count = 0
    end = start
    for i, c in enumerate(content[start:], start):
        if c == "[":
            bracket_count += 1
        elif c == "]":
            bracket_count -= 1
            if bracket_count == 0:
                end = i + 1
                break
    exec(content[start:end], ns)
    return ns["QUESTIONS"]


async def precompute():
    """Embed all questions and store in Qdrant."""
    from sentence_transformers import SentenceTransformer
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct, VectorParams, Distance

    questions = load_questions()
    logger.info("Loaded %d questions", len(questions))

    # ── Step 1: Load embedding model ───────────────────────────────
    logger.info("Loading embedding model...")
    t0 = time.monotonic()
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    logger.info("Model loaded in %.1fs", time.monotonic() - t0)

    # ── Step 2: Connect to Qdrant ──────────────────────────────────
    client = QdrantClient(host="qdrant", port=6333)

    # Create a dedicated collection for question embeddings
    collection_name = "upsc_questions"
    collections = [c.name for c in client.get_collections().collections]
    if collection_name not in collections:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        logger.info("Created collection: %s", collection_name)
    else:
        logger.info("Collection %s already exists", collection_name)

    # ── Step 3: Embed all questions (batch for GPU efficiency) ─────
    logger.info("Embedding %d questions...", len(questions))
    t0 = time.monotonic()
    texts = [q["q"] for q in questions]
    # Batch encode — much faster than one-by-one on GPU
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=True)
    embed_time = time.monotonic() - t0
    logger.info("Embedded %d questions in %.1fs (%.1f q/s)", len(questions), embed_time, len(questions) / embed_time)

    # ── Step 4: Upload to Qdrant ───────────────────────────────────
    logger.info("Uploading to Qdrant...")
    points = []
    for i, (item, vec) in enumerate(zip(questions, embeddings)):
        points.append(PointStruct(
            id=i + 1,
            vector=vec.tolist(),
            payload={
                "question": item["q"],
                "domain": item["domain"],
                "paper": item["paper"],
                "year": item["year"],
                "type": item["type"],
            },
        ))

    # Upload in batches of 100
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        client.upsert(collection_name=collection_name, points=batch)
        logger.info("Uploaded %d/%d", min(i + batch_size, len(points)), len(points))

    # ── Step 5: Verify ─────────────────────────────────────────────
    info = client.get_collection(collection_name)
    logger.info("Done! Collection '%s' has %d vectors", collection_name, info.points_count)

    # ── Step 6: Save mapping for test ──────────────────────────────
    mapping = []
    for i, item in enumerate(questions):
        mapping.append({
            "id": i + 1,
            "question": item["q"],
            "domain": item["domain"],
            "paper": item["paper"],
            "year": item["year"],
            "type": item["type"],
        })
    mapping_file = Path(__file__).parent / "dataset" / "question_embeddings_mapping.jsonl"
    mapping_file.parent.mkdir(parents=True, exist_ok=True)
    with open(mapping_file, "w") as f:
        for m in mapping:
            f.write(json.dumps(m) + "\n")
    logger.info("Saved mapping to %s", mapping_file)


if __name__ == "__main__":
    asyncio.run(precompute())
