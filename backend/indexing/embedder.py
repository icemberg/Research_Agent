"""
Embedder — wraps SentenceTransformer for dense vector generation.

Embeds the contextual text (context_prefix + chunk text) so that
the vector captures document-level meaning, not just the isolated chunk.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from backend.config import settings

logger = logging.getLogger(__name__)


class Embedder:
    """FastEmbed wrapper with lazy model loading."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self._model = None

    @property
    def model(self):
        """Lazy-load the model on first use."""
        if self._model is None:
            # pyrefly: ignore [missing-import]
            from fastembed import TextEmbedding

            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = TextEmbedding(self.model_name)
            logger.info("Embedding model loaded.")
        return self._model

    def load(self) -> None:
        """
        Force the model to load/download immediately (eager loading).

        Intended to be called during application startup so that the
        (potentially slow) model download/initialization happens before
        the server begins accepting HTTP requests, rather than blocking
        the first incoming request.
        """
        _ = self.model

    @property
    def dimension(self) -> int:
        """Embedding vector dimension."""
        # all-MiniLM-L6-v2 uses 384 dimensions
        return 384

    def embed(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        """
        Embed a batch of texts into dense vectors.

        Args:
            texts: List of strings to embed.
            batch_size: Batch size for encoding efficiency.

        Returns:
            List of embedding vectors (as Python lists of floats).
        """
        if not texts:
            return []

        embeddings_gen = self.model.embed(
            texts,
            batch_size=batch_size,
        )
        return [e.tolist() for e in embeddings_gen]

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        return self.embed([query])[0]

    def embed_passages_with_context(
        self,
        texts: list[str],
        context_prefixes: list[str],
    ) -> list[list[float]]:
        """
        Embed passages with their contextual prefixes prepended.
        This is the key to contextual retrieval — the embedding captures
        document-level context, not just the isolated chunk text.
        """
        contextualized = [
            f"{prefix}{text}" if prefix else text
            for prefix, text in zip(context_prefixes, texts)
        ]
        return self.embed(contextualized)
