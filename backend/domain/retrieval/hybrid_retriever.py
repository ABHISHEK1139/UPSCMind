"""
Hermes V2 — Hybrid Retriever
═══════════════════════════════════════════════════════════════
Combines dense vector search (Qdrant + sentence-transformers)
with sparse BM25 lexical search, fused via Reciprocal Rank
Fusion (RRF).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

import torch
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Lazy / optional imports ────────────────────────────────────────────
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.exceptions import UnexpectedResponse
    from qdrant_client.http.models import Filter, SearchParams
except ImportError:
    QdrantClient = None
    UnexpectedResponse = Exception

# ── Constants ──────────────────────────────────────────────────────────
COLLECTION_NAME = "upsc_knowledge"
DENSE_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
RRF_K = 60


# ── Models ─────────────────────────────────────────────────────────────
class RetrievedChunk(BaseModel):
    """A single chunk returned by the retrieval pipeline."""

    text: str = Field(..., description="The chunk's textual content")
    source: str = Field(default="unknown", description="Provenance")
    score: float = Field(default=0.0, description="Fused relevance score")
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Hybrid Retriever ──────────────────────────────────────────────────
class HybridRetriever:
    """
    Dense (Qdrant) + Sparse (BM25) retrieval with RRF fusion.
    """

    def __init__(
        self,
        qdrant_client: Optional[QdrantClient] = None,
        dense_model_name: str = DENSE_MODEL_NAME,
        collection: str = COLLECTION_NAME,
    ) -> None:
        from core.db_qdrant import get_qdrant_client
        from core.config import get_settings

        self._client = qdrant_client or get_qdrant_client()
        self._collection = collection
        self._dense_model_name = dense_model_name
        self._dense_model: Any = None
        self._bm25: Any = None
        self._corpus: list[str] = []
        self._settings = get_settings()

        if SentenceTransformer is not None:
            try:
                # Auto-detect GPU, fallback to CPU
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                self._dense_model = SentenceTransformer(dense_model_name, device=device)
                logger.info("[HYBRID] Dense model loaded: %s (device: %s)", dense_model_name, device)
            except Exception as exc:
                logger.warning("[HYBRID] Failed to load dense model: %s", exc)

    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[dict] = None,
        current_date: Optional[str] = None,
        prefer_fresh: bool = True,
    ) -> list[RetrievedChunk]:
        """
        Run hybrid search: dense + sparse → RRF fusion.

        Parameters
        ----------
        query : str
            The search query.
        top_k : int, optional
            Number of results to return (default from settings).
        filters : dict, optional
            Qdrant payload filters.
        current_date : str, optional
            ISO date string (e.g., "2024-06-22"). If provided, chunks
            with valid_until < current_date are deprioritized.
        prefer_fresh : bool
            If True, boost newer chunks and deprioritize outdated ones.

        Returns
        -------
        list[RetrievedChunk]
            Fused and sorted results.
        """
        k = top_k or self._settings.RETRIEVAL_TOP_K
        
        # Add freshness filter if requested
        if prefer_fresh and current_date:
            filters = filters or {}
            # We handle freshness as a post-filter since Qdrant's
            # range filter on strings works for ISO dates
            filters["valid_until_gte"] = current_date

        # ── Dense retrieval (run in thread to not block event loop) ──
        dense_results = await asyncio.get_event_loop().run_in_executor(
            None, self._dense_search_sync, query, k * 2, filters
        )

        # ── Sparse retrieval ────────────────────────────────
        sparse_results = self._sparse_search(query, k=k * 2)

        # ── RRF Fusion ──────────────────────────────────────
        fused = self._reciprocal_rank_fusion(dense_results, sparse_results, k=k)
        logger.info(
            "[HYBRID] query='%s...' dense=%d sparse=%d fused=%d",
            query[:40], len(dense_results), len(sparse_results), len(fused),
        )
        return fused

    def _dense_search_sync(
        self, query: str, k: int, filters: Optional[dict] = None,
    ) -> list[RetrievedChunk]:
        """Dense vector search via Qdrant (sync, for run_in_executor)."""
        if self._dense_model is None or self._client is None:
            return []
        try:
            with torch.no_grad():
                query_vec = self._dense_model.encode(query, show_progress_bar=False).tolist()
            qdrant_filter = None
            if filters:
                from qdrant_client.http.models import Filter as QFilter, FieldCondition, MatchValue, Range
                conditions = []
                for key, value in filters.items():
                    if key == "valid_until_gte":
                        # Freshness filter: only return chunks valid after current_date
                        conditions.append(
                            FieldCondition(key="valid_until", range=Range(gte=value))
                        )
                    else:
                        conditions.append(
                            FieldCondition(key=key, match=MatchValue(value=value))
                        )
                qdrant_filter = QFilter(must=conditions) if conditions else None
            else:
                qdrant_filter = None

            # Fetch more than k to allow for freshness re-ranking
            fetch_limit = k * 2
            
            # Use query_points (Qdrant 1.18+) with fallback to search (older versions)
            try:
                from qdrant_client.models import models as qmodels
                result_points = self._client.query_points(
                    collection_name=self._collection,
                    query=query_vec,
                    query_filter=qdrant_filter,
                    limit=fetch_limit,
                    with_payload=True,
                    search_params=qmodels.SearchParams(hnsw_ef=128),
                )
                points = result_points.points
            except (AttributeError, TypeError):
                # Fallback for older Qdrant client versions
                points = self._client.search(
                    collection_name=self._collection,
                    query_vector=query_vec,
                    query_filter=qdrant_filter,
                    limit=fetch_limit,
                    with_payload=True,
                )
            
            chunks = [
                RetrievedChunk(
                    text=r.payload.get("text", ""),
                    source=str(r.payload.get("source", "qdrant")),
                    score=float(r.score),
                    metadata=dict(r.payload),
                )
                for r in points
            ]
            
            # Freshness re-ranking: boost newer chunks
            if prefer_fresh and current_date:
                chunks = self._apply_freshness_boost(chunks, current_date)
            
            return chunks[:k]
        except Exception as exc:
            logger.warning("[HYBRID] Dense search failed: %s", exc)
            return []

    def _sparse_search(self, query: str, k: int) -> list[RetrievedChunk]:
        """Sparse BM25 search over in-memory corpus."""
        if BM25Okapi is None or not self._corpus:
            return []
        try:
            tokenized = [doc.lower().split() for doc in self._corpus]
            bm25 = BM25Okapi(tokenized)
            scores = bm25.get_scores(query.lower().split())
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
            return [
                RetrievedChunk(
                    text=self._corpus[i],
                    source="bm25",
                    score=float(scores[i]),
                    metadata={"index": i},
                )
                for i in top_indices
            ]
        except Exception as exc:
            logger.warning("[HYBRID] Sparse search failed: %s", exc)
            return []

    @staticmethod
    def _apply_freshness_boost(
        chunks: list[RetrievedChunk],
        current_date: str,
        boost_factor: float = 0.1,
    ) -> list[RetrievedChunk]:
        """
        Boost scores of newer chunks and deprioritize outdated ones.
        
        Chunks with published_date closer to current_date get a small boost.
        Chunks with valid_until < current_date are penalized.
        """
        from datetime import datetime
        
        try:
            current = datetime.fromisoformat(current_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return chunks
        
        for chunk in chunks:
            metadata = chunk.metadata
            
            # Check if chunk is outdated
            valid_until = metadata.get("valid_until")
            if valid_until:
                try:
                    valid_date = datetime.fromisoformat(str(valid_until).replace("Z", "+00:00"))
                    if valid_date < current:
                        # Outdated chunk — significant penalty
                        chunk.score *= 0.3
                        continue
                except (ValueError, AttributeError):
                    pass
            
            # Boost newer content
            published = metadata.get("published_date") or metadata.get("year")
            if published:
                try:
                    if isinstance(published, int):
                        pub_date = datetime(published, 1, 1)
                    else:
                        pub_date = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
                    
                    # Calculate age in years
                    age_years = (current - pub_date).days / 365.25
                    
                    # Newer chunks get a small boost (max 10%)
                    if age_years < 1:
                        chunk.score *= (1.0 + boost_factor)
                    elif age_years < 3:
                        chunk.score *= (1.0 + boost_factor * 0.5)
                    elif age_years > 10:
                        # Very old chunks get a small penalty
                        chunk.score *= (1.0 - boost_factor * 0.3)
                except (ValueError, AttributeError):
                    pass
        
        # Re-sort after score adjustments
        chunks.sort(key=lambda c: c.score, reverse=True)
        return chunks

    @staticmethod
    def _reciprocal_rank_fusion(
        dense: list[RetrievedChunk],
        sparse: list[RetrievedChunk],
        k: int = 10,
    ) -> list[RetrievedChunk]:
        """Fuse dense and sparse results using RRF."""
        scores: dict[str, float] = {}
        chunks: dict[str, RetrievedChunk] = {}

        for rank, chunk in enumerate(dense):
            key = chunk.text[:200]
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
            chunks[key] = chunk

        for rank, chunk in enumerate(sparse):
            key = chunk.text[:200]
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
            if key not in chunks:
                chunks[key] = chunk

        sorted_keys = sorted(scores, key=scores.get, reverse=True)[:k]
        result = []
        for key in sorted_keys:
            chunk = chunks[key]
            chunk.score = scores[key]
            result.append(chunk)
        return result

    def index_corpus(self, documents: list[str]) -> None:
        """Load documents into the BM25 index."""
        self._corpus = documents
        logger.info("[HYBRID] Indexed %d documents for BM25.", len(documents))
