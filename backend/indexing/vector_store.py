"""
ChromaDB vector store wrapper.

Implements BaseVectorStore interface (Dependency Inversion) —
swap to FAISS/Pinecone/pgvector by implementing the same interface.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from backend.config import settings
from backend.models.passage import Passage

logger = logging.getLogger(__name__)


class BaseVectorStore(ABC):
    """Abstract vector store interface."""

    @abstractmethod
    def add(self, passages: list[Passage], embeddings: list[list[float]]) -> None:
        """Add passages with their embeddings to the store."""
        ...

    @abstractmethod
    def query(
        self, embedding: list[float], top_k: int = 10, filter_doc_ids: list[str] | None = None
    ) -> list[Passage]:
        """Query the store for the top-k most similar passages."""
        ...

    @abstractmethod
    def delete_document(self, source_name: str) -> int:
        """Delete all passages from a specific document. Returns count deleted."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Total number of passages in the store."""
        ...


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB-backed vector store with persistent storage."""

    def __init__(self, persist_dir: str | None = None, collection_name: str = "research_agent"):
        import chromadb

        self.persist_dir = persist_dir or settings.chroma_persist_dir
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB initialized: {self.persist_dir}, "
            f"collection={collection_name}, "
            f"passages={self.collection.count()}"
        )

    def add(self, passages: list[Passage], embeddings: list[list[float]]) -> None:
        """Add passages with pre-computed embeddings."""
        if not passages:
            return

        # ChromaDB upsert for idempotent re-ingestion
        self.collection.upsert(
            ids=[p.id for p in passages],
            embeddings=embeddings,
            documents=[p.text for p in passages],
            metadatas=[
                {
                    "source_name": p.source_name,
                    "location": p.location,
                    "source_type": p.source_type.value,
                    "context_prefix": p.context_prefix,
                    **{k: str(v) for k, v in p.metadata.items()},
                }
                for p in passages
            ],
        )
        logger.info(f"Upserted {len(passages)} passages into ChromaDB")

    def query(
        self,
        embedding: list[float],
        top_k: int = 10,
        filter_doc_ids: list[str] | None = None,
    ) -> list[Passage]:
        """Query for similar passages using cosine similarity."""
        where_filter = None
        if filter_doc_ids:
            where_filter = {"source_name": {"$in": filter_doc_ids}}

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, self.collection.count() or 1),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        passages: list[Passage] = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0.0
                # ChromaDB returns cosine distance; convert to similarity
                similarity = 1.0 - distance

                passages.append(
                    Passage(
                        id=doc_id,
                        text=results["documents"][0][i],
                        source_name=meta.get("source_name", ""),
                        location=meta.get("location", ""),
                        context_prefix=meta.get("context_prefix", ""),
                        score=similarity,
                        metadata=meta,
                    )
                )

        return passages

    def delete_document(self, source_name: str) -> int:
        """Delete all passages from a specific document."""
        # Get IDs matching the source
        results = self.collection.get(
            where={"source_name": source_name},
            include=[],
        )
        if results and results["ids"]:
            self.collection.delete(ids=results["ids"])
            count = len(results["ids"])
            logger.info(f"Deleted {count} passages for document '{source_name}'")
            return count
        return 0

    def count(self) -> int:
        """Total passage count."""
        return self.collection.count()
