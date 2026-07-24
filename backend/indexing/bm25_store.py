"""
BM25 sparse keyword index — essential for exact-term matches
(dates, IDs, proper nouns) that dense embeddings miss.

Persisted to disk via pickle for fast reload.
"""

from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path

from backend.config import settings
from backend.models.passage import Passage

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric, remove short tokens."""
    tokens = re.findall(r"\b[a-z0-9]+(?:'[a-z]+)?\b", text.lower())
    return [t for t in tokens if len(t) > 1]


class BM25Store:
    """
    BM25 keyword index over passages.

    Stores passage metadata alongside the BM25 index so that
    results can be returned as full Passage objects with provenance.
    """

    def __init__(self, persist_dir: str | None = None):
        self.persist_dir = Path(persist_dir or settings.bm25_persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self._passages: list[Passage] = []
        self._tokenized_corpus: list[list[str]] = []
        self._bm25 = None
        self._dirty = False

        # Try to load from disk
        self._load()

    def add(self, passages: list[Passage]) -> None:
        """Add passages to the BM25 index."""
        if not passages:
            return

        # Dedup against existing
        existing_ids = {p.id for p in self._passages}
        new_passages = [p for p in passages if p.id not in existing_ids]

        if not new_passages:
            logger.debug("No new passages to add to BM25 index")
            return

        for p in new_passages:
            # Tokenize with context prefix for richer keyword matching
            text_to_index = f"{p.context_prefix}{p.text}" if p.context_prefix else p.text
            self._passages.append(p)
            self._tokenized_corpus.append(_tokenize(text_to_index))

        self._rebuild_index()
        self._save()
        logger.info(f"Added {len(new_passages)} passages to BM25 index (total: {len(self._passages)})")

    def query(self, text: str, top_k: int = 10) -> list[Passage]:
        """Query the BM25 index and return scored passages."""
        if self._bm25 is None or not self._passages:
            return []

        tokenized_query = _tokenize(text)
        if not tokenized_query:
            return []

        scores = self._bm25.get_scores(tokenized_query)

        # Get top-k indices sorted by score descending
        scored_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[:top_k]

        results: list[Passage] = []
        for idx in scored_indices:
            if scores[idx] > 0:
                passage = self._passages[idx].model_copy()
                passage.score = float(scores[idx])
                results.append(passage)

        return results

    def delete_document(self, source_name: str) -> int:
        """Delete all passages from a specific document."""
        original_count = len(self._passages)
        indices_to_keep = [
            i for i, p in enumerate(self._passages) if p.source_name != source_name
        ]

        self._passages = [self._passages[i] for i in indices_to_keep]
        self._tokenized_corpus = [self._tokenized_corpus[i] for i in indices_to_keep]

        deleted = original_count - len(self._passages)
        if deleted > 0:
            self._rebuild_index()
            self._save()
            logger.info(f"Deleted {deleted} passages for '{source_name}' from BM25 index")
        return deleted

    def count(self) -> int:
        """Total passages in the index."""
        return len(self._passages)

    def _rebuild_index(self) -> None:
        """Rebuild the BM25 index from the tokenized corpus."""
        from rank_bm25 import BM25Okapi

        if self._tokenized_corpus:
            self._bm25 = BM25Okapi(self._tokenized_corpus)
        else:
            self._bm25 = None

    def _save(self) -> None:
        """Persist index to disk."""
        data = {
            "passages": [p.model_dump() for p in self._passages],
            "tokenized_corpus": self._tokenized_corpus,
        }
        save_path = self.persist_dir / "bm25_index.pkl"
        with open(save_path, "wb") as f:
            pickle.dump(data, f)
        logger.debug(f"BM25 index saved to {save_path}")

    def _load(self) -> None:
        """Load index from disk if available."""
        load_path = self.persist_dir / "bm25_index.pkl"
        if load_path.exists():
            try:
                with open(load_path, "rb") as f:
                    data = pickle.load(f)
                self._passages = [Passage(**p) for p in data["passages"]]
                self._tokenized_corpus = data["tokenized_corpus"]
                self._rebuild_index()
                logger.info(f"BM25 index loaded: {len(self._passages)} passages")
            except Exception as e:
                logger.warning(f"Failed to load BM25 index: {e}. Starting fresh.")
                self._passages = []
                self._tokenized_corpus = []
                self._bm25 = None
