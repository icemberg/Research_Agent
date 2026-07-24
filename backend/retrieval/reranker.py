"""
Cross-encoder re-ranker — re-scores candidate passages with a more
powerful model for higher precision at the cost of some latency.

Uses cross-encoder/ms-marco-MiniLM-L-6-v2 (small, fast, effective).
"""

from __future__ import annotations

import logging

from backend.config import settings
from backend.models.passage import Passage

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Re-ranks passages using a cross-encoder model."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.reranker_model
        self._model = None

    @property
    def model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info(f"Loading re-ranker model: {self.model_name}")
            self._model = CrossEncoder(self.model_name)
            logger.info("Re-ranker model loaded")
        return self._model

    def rerank(self, query: str, passages: list[Passage], top_k: int | None = None) -> list[Passage]:
        """
        Re-rank passages by cross-encoder relevance score.

        The cross-encoder sees (query, passage) pairs together,
        enabling much richer relevance judgments than bi-encoder dot products.
        """
        if not passages:
            return []

        top_k = top_k or settings.top_k

        # Build (query, passage) pairs
        pairs = [(query, p.text) for p in passages]

        # Score all pairs
        scores = self.model.predict(pairs)

        # Assign scores and sort
        scored_passages = []
        for passage, score in zip(passages, scores):
            p = passage.model_copy()
            p.score = float(score)
            scored_passages.append(p)

        scored_passages.sort(key=lambda p: p.score, reverse=True)

        results = scored_passages[:top_k]
        logger.info(
            f"Re-ranked {len(passages)} passages → top {len(results)} "
            f"(scores: {results[0].score:.3f} to {results[-1].score:.3f})"
        )
        return results
