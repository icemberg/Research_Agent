"""Abstract retriever interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.models.passage import Passage


class BaseRetriever(ABC):
    """Interface for passage retrieval — swappable implementations."""

    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        filter_doc_ids: list[str] | None = None,
    ) -> list[Passage]:
        """Retrieve the top-k most relevant passages for a query."""
        ...
