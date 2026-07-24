"""
Hybrid Retriever — Dense (ChromaDB) + Sparse (BM25) + Reciprocal Rank Fusion.

This is the architecture's key quality differentiator: dense embeddings capture
semantic similarity while BM25 catches exact-term matches (dates, IDs, names)
that embeddings alone miss — exactly what citations depend on.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from backend.config import settings
from backend.indexing.embedder import Embedder
from backend.indexing.vector_store import ChromaVectorStore
from backend.indexing.bm25_store import BM25Store
from backend.models.passage import Passage
from backend.retrieval.base import BaseRetriever

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    ranked_lists: list[list[Passage]],
    k: int = 60,
) -> list[Passage]:
    """
    Merge multiple ranked passage lists using Reciprocal Rank Fusion.

    RRF score = Σ 1/(k + rank) across all lists.
    k=60 is standard — reduces dominance of very top-ranked results.

    Only uses rank position, not raw scores — solves the
    BM25-vs-cosine score incompatibility problem elegantly.
    """
    rrf_scores: dict[str, float] = defaultdict(float)
    passage_map: dict[str, Passage] = {}

    for ranked_list in ranked_lists:
        for rank, passage in enumerate(ranked_list):
            rrf_scores[passage.id] += 1.0 / (k + rank + 1)
            # Keep the passage with the highest individual score
            if passage.id not in passage_map or passage.score > passage_map[passage.id].score:
                passage_map[passage.id] = passage

    # Sort by RRF score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda pid: rrf_scores[pid], reverse=True)

    results = []
    for pid in sorted_ids:
        passage = passage_map[pid].model_copy()
        passage.score = rrf_scores[pid]  # Replace with RRF score
        results.append(passage)

    return results


class HybridRetriever(BaseRetriever):
    """
    Combines dense vector search + BM25 keyword search via RRF.

    Pipeline:
    1. Query both stores for top_k_candidates each
    2. Merge via Reciprocal Rank Fusion
    3. Return top_k results with full provenance metadata
    """

    def __init__(
        self,
        embedder: Embedder,
        vector_store: ChromaVectorStore,
        bm25_store: BM25Store,
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.bm25_store = bm25_store

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        filter_doc_ids: list[str] | None = None,
    ) -> list[Passage]:
        """
        Hybrid retrieval: dense + sparse → RRF fusion → top-k.
        """
        top_k = top_k or settings.top_k
        candidates = settings.top_k_candidates

        # 1. Dense retrieval from ChromaDB
        query_embedding = self.embedder.embed_query(query)
        dense_results = self.vector_store.query(
            embedding=query_embedding,
            top_k=candidates,
            filter_doc_ids=filter_doc_ids,
        )
        logger.debug(f"Dense retrieval: {len(dense_results)} candidates")

        # 2. Sparse retrieval from BM25
        sparse_results = self.bm25_store.query(text=query, top_k=candidates)
        logger.debug(f"BM25 retrieval: {len(sparse_results)} candidates")

        # 3. Reciprocal Rank Fusion
        fused = reciprocal_rank_fusion([dense_results, sparse_results])

        # 4. Return top-k
        results = fused[:top_k]
        logger.info(
            f"Hybrid retrieval for '{query[:50]}...': "
            f"{len(dense_results)} dense + {len(sparse_results)} sparse "
            f"→ {len(fused)} fused → {len(results)} returned"
        )

        return results
