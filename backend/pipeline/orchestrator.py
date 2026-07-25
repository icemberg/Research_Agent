"""
Orchestrator — the main agent loop tying all components together.

This is the Orchestrator–Worker pattern: a lightweight loop that
delegates to specialized workers (retriever, synthesizer, validator).

Pipeline:
  Question → Router → Retriever → Re-ranker → Assembler → Synthesizer
  → Validator (retry loop) → Formatter → Response
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import AsyncIterator

from backend.config import settings
from backend.models.passage import Passage, Citation, AnswerResponse, PassageSource
from backend.llm.base import BaseLLMClient
from backend.llm.llm_factory import get_llm_client
from backend.indexing.embedder import Embedder
from backend.indexing.vector_store import ChromaVectorStore
from backend.indexing.bm25_store import BM25Store
from backend.retrieval.hybrid_retriever import HybridRetriever
from backend.retrieval.reranker import CrossEncoderReranker
from backend.pipeline.router import QueryRouter, RouteDecision
from backend.pipeline.context_assembler import ContextAssembler
from backend.pipeline.synthesizer import Synthesizer
from backend.pipeline.citation_validator import CitationValidator
from backend.tools.web_search import TavilySearchTool
from backend.chunking.semantic_chunker import SemanticChunker
from backend.loaders.loader_factory import LoaderFactory

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main agent orchestrator — coordinates the full RAG pipeline.

    All components are injected or lazily constructed, enabling
    testing with mocks and swapping implementations (DI principle).
    """

    def __init__(
        self,
        llm_client: BaseLLMClient | None = None,
        embedder: Embedder | None = None,
        vector_store: ChromaVectorStore | None = None,
        bm25_store: BM25Store | None = None,
    ):
        # Ensure data directories exist
        settings.ensure_data_dirs()

        # Core components (lazy or injected)
        self.llm = llm_client or get_llm_client()
        self.embedder = embedder or Embedder()
        self.vector_store = vector_store or ChromaVectorStore()
        self.bm25_store = bm25_store or BM25Store()

        # Pipeline components
        self.retriever = HybridRetriever(self.embedder, self.vector_store, self.bm25_store)
        self.reranker = CrossEncoderReranker() if settings.enable_reranker else None
        self.router = QueryRouter(self.llm)
        self.assembler = ContextAssembler()
        self.synthesizer = Synthesizer(self.llm, self.assembler)
        self.validator = CitationValidator()
        self.chunker = SemanticChunker()

        # Optional tools
        self.web_search = TavilySearchTool() if settings.tavily_api_key else None

        logger.info(
            f"Orchestrator initialized: LLM={self.llm.model_name}, "
            f"reranker={'enabled' if self.reranker else 'disabled'}, "
            f"web_search={'enabled' if self.web_search else 'disabled'}"
        )

    #  Ingestion 

    def ingest_file(self, file_path: Path, source_name: str | None = None) -> dict:
        """
        Ingest a single file: load → chunk → embed → index.

        Returns: {document_id, name, chunk_count, status}
        """
        logger.info(f"Ingesting: {file_path}")
        start = time.time()
        
        name_to_use = source_name or file_path.name

        # 1. Load
        loader = LoaderFactory.get_loader(file_path)
        sections = loader.load(file_path)
        logger.info(f"Loaded {len(sections)} sections from {name_to_use}")

        # 2. Chunk (with contextual prefixes)
        passages = self.chunker.chunk_sections(sections, name_to_use)
        logger.info(f"Chunked into {len(passages)} passages")

        if not passages:
            return {
                "document_id": "",
                "name": name_to_use,
                "chunk_count": 0,
                "status": "empty",
            }

        # 3. Embed (with contextual prefixes for richer vectors)
        texts = [p.text for p in passages]
        prefixes = [p.context_prefix for p in passages]
        embeddings = self.embedder.embed_passages_with_context(texts, prefixes)

        # 4. Index in both stores
        self.vector_store.add(passages, embeddings)
        self.bm25_store.add(passages)

        elapsed = time.time() - start
        doc_id = passages[0].id[:8]  # Use first chunk ID prefix as doc ID

        logger.info(
            f"Ingestion complete: {name_to_use} → {len(passages)} passages in {elapsed:.1f}s"
        )

        return {
            "document_id": doc_id,
            "name": name_to_use,
            "chunk_count": len(passages),
            "status": "indexed",
        }

    def ingest_directory(self, dir_path: Path) -> list[dict]:
        """Ingest all supported files in a directory."""
        results = []
        supported = set(LoaderFactory.supported_extensions())

        for file_path in sorted(dir_path.iterdir()):
            if file_path.is_file() and file_path.suffix.lower() in supported:
                try:
                    result = self.ingest_file(file_path)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to ingest {file_path}: {e}")
                    results.append({
                        "document_id": "",
                        "name": file_path.name,
                        "chunk_count": 0,
                        "status": f"error: {e}",
                    })

        return results

    #  Question Answering

    async def ask(
        self,
        question: str,
        document_ids: list[str] | None = None,
        allow_web_search: bool = False,
    ) -> AnswerResponse:
        """
        Full agent loop: route → retrieve → rerank → synthesize → validate → format.

        This is the main entry point for answering questions.
        """
        start = time.time()
        question_id = str(uuid.uuid4())[:8]

        logger.info(f"[{question_id}] Question: {question}")

        #  Step 1: Route 
        has_documents = self.vector_store.count() > 0
        doc_summaries = self._get_document_summaries()

        decision = await self.router.route(
            question=question,
            document_summaries=doc_summaries,
            allow_web_search=allow_web_search,
            has_documents=has_documents,
        )
        logger.info(f"[{question_id}] Router decision: {decision.value}")

        #  Step 2: Handle abstention 
        if decision == RouteDecision.ABSTAIN:
            return AnswerResponse(
                answer_text=(
                    "ABSTAIN: I cannot answer this question. The available document corpus "
                    "does not appear to contain relevant information, and web search is "
                    "either disabled or would not help with this type of question."
                ),
                citations=[],
                abstained=True,
                confidence_note="No relevant sources found",
                latency_ms=(time.time() - start) * 1000,
                question_id=question_id,
                question=question,
            )

        #  Step 3: Retrieve passages 
        passages: list[Passage] = []

        if decision == RouteDecision.WEB_SEARCH and self.web_search:
            logger.info(f"[{question_id}] Invoking web search")
            passages = self.web_search.search(question)
            if not passages:
                logger.warning(f"[{question_id}] Web search returned no results")
        elif decision == RouteDecision.CORPUS or (decision == RouteDecision.WEB_SEARCH and not self.web_search):
            passages = self.retriever.retrieve(
                query=question,
                top_k=settings.top_k_candidates if self.reranker else settings.top_k,
                filter_doc_ids=document_ids,
            )

        if not passages:
            # Try web search as a last resort if allowed
            if allow_web_search and self.web_search and decision != RouteDecision.WEB_SEARCH:
                logger.info(f"[{question_id}] Corpus retrieval empty, falling back to web search")
                passages = self.web_search.search(question)

            if not passages:
                return AnswerResponse(
                    answer_text=(
                        "ABSTAIN: The provided sources do not contain sufficient information "
                        "to answer this question. No relevant passages were found in the "
                        "document corpus."
                    ),
                    citations=[],
                    abstained=True,
                    confidence_note="No passages retrieved",
                    latency_ms=(time.time() - start) * 1000,
                    question_id=question_id,
                    question=question,
                )

        logger.info(f"[{question_id}] Retrieved {len(passages)} passages")

        #  Step 4: Re-rank (optional) ─
        if self.reranker and len(passages) > settings.top_k:
            passages = self.reranker.rerank(question, passages, top_k=settings.top_k)
            logger.info(f"[{question_id}] Re-ranked to top {len(passages)} passages")

        #  Step 5: Synthesize with citations 
        answer_text, messages = await self.synthesizer.synthesize(question, passages)
        logger.info(f"[{question_id}] Synthesis complete ({len(answer_text)} chars)")

        #  Step 6: Validate citations (with retry)
        final_answer = answer_text
        validation = self.validator.validate(final_answer, passages)

        retry_count = 0
        while not validation.is_valid and retry_count < settings.max_citation_retries:
            retry_count += 1
            logger.warning(
                f"[{question_id}] Citation validation failed (attempt {retry_count}): "
                f"{validation.issues}"
            )

            issues_text = "\n".join(f"- {issue}" for issue in validation.issues)
            final_answer = await self.synthesizer.retry_with_correction(
                original_messages=messages,
                original_answer=final_answer,
                issues=issues_text,
                max_passage=len(passages),
            )
            validation = self.validator.validate(final_answer, passages)

        if not validation.is_valid:
            logger.warning(
                f"[{question_id}] Citations still invalid after {retry_count} retries. "
                f"Proceeding with best-effort answer."
            )

        # Check for explicit abstention in the answer
        is_abstained = "ABSTAIN:" in final_answer.upper()

        latency = (time.time() - start) * 1000

        response = AnswerResponse(
            answer_text=final_answer,
            citations=validation.citations,
            abstained=is_abstained,
            confidence_note=(
                f"Validated: {validation.is_valid}, "
                f"Sources: {len(validation.citations)}, "
                f"Model: {self.llm.model_name}"
            ),
            latency_ms=latency,
            question_id=question_id,
            question=question,
        )

        logger.info(
            f"[{question_id}] Response ready: "
            f"abstained={is_abstained}, citations={len(validation.citations)}, "
            f"latency={latency:.0f}ms"
        )

        return response

    async def ask_stream(
        self,
        question: str,
        document_ids: list[str] | None = None,
        allow_web_search: bool = False,
    ) -> AsyncIterator[dict]:
        """
        Streaming version of ask — yields events for SSE.

        Events:
        - {"type": "status", "data": "..."} — progress updates
        - {"type": "token", "data": "..."} — answer tokens
        - {"type": "citations", "data": [...]} — final citations after validation
        - {"type": "done", "data": {...}} — final complete response
        - {"type": "error", "data": "..."} — error message
        """
        start = time.time()
        question_id = str(uuid.uuid4())[:8]

        try:
            yield {"type": "status", "data": "Analyzing question..."}

            # Route
            has_documents = self.vector_store.count() > 0
            doc_summaries = self._get_document_summaries()
            decision = await self.router.route(
                question=question,
                document_summaries=doc_summaries,
                allow_web_search=allow_web_search,
                has_documents=has_documents,
            )

            yield {"type": "status", "data": f"Route: {decision.value}"}

            if decision == RouteDecision.ABSTAIN:
                yield {
                    "type": "done",
                    "data": {
                        "answer_text": "ABSTAIN: The available sources cannot answer this question.",
                        "citations": [],
                        "abstained": True,
                        "latency_ms": (time.time() - start) * 1000,
                        "question_id": question_id,
                    },
                }
                return

            # Retrieve
            yield {"type": "status", "data": "Retrieving relevant passages..."}
            passages: list[Passage] = []

            if decision == RouteDecision.WEB_SEARCH and self.web_search:
                passages = self.web_search.search(question)
            else:
                passages = self.retriever.retrieve(
                    query=question,
                    top_k=settings.top_k_candidates if self.reranker else settings.top_k,
                    filter_doc_ids=document_ids,
                )

            if not passages and allow_web_search and self.web_search:
                passages = self.web_search.search(question)

            if not passages:
                yield {
                    "type": "done",
                    "data": {
                        "answer_text": "ABSTAIN: No relevant passages found.",
                        "citations": [],
                        "abstained": True,
                        "latency_ms": (time.time() - start) * 1000,
                        "question_id": question_id,
                    },
                }
                return

            # Re-rank
            if self.reranker and len(passages) > settings.top_k:
                yield {"type": "status", "data": "Re-ranking passages..."}
                passages = self.reranker.rerank(question, passages, top_k=settings.top_k)

            yield {"type": "status", "data": f"Synthesizing answer from {len(passages)} passages..."}

            # Stream synthesis
            full_answer = ""
            async for token in self.synthesizer.synthesize_stream(question, passages):
                full_answer += token
                yield {"type": "token", "data": token}

            # Validate
            yield {"type": "status", "data": "Validating citations..."}
            validation = self.validator.validate(full_answer, passages)

            if not validation.is_valid:
                # One retry for streaming
                issues_text = "\n".join(f"- {issue}" for issue in validation.issues)
                messages = self.assembler.assemble(question, passages)
                full_answer = await self.synthesizer.retry_with_correction(
                    original_messages=messages,
                    original_answer=full_answer,
                    issues=issues_text,
                    max_passage=len(passages),
                )
                validation = self.validator.validate(full_answer, passages)

            # Final response
            latency = (time.time() - start) * 1000
            is_abstained = "ABSTAIN:" in full_answer.upper()

            yield {
                "type": "citations",
                "data": [c.model_dump() for c in validation.citations],
            }

            yield {
                "type": "done",
                "data": {
                    "answer_text": full_answer,
                    "citations": [c.model_dump() for c in validation.citations],
                    "abstained": is_abstained,
                    "latency_ms": latency,
                    "question_id": question_id,
                    "question": question,
                },
            }

        except Exception as e:
            logger.error(f"[{question_id}] Stream error: {e}", exc_info=True)
            yield {"type": "error", "data": str(e)}


    def _get_document_summaries(self) -> list[str]:
        """Get a brief summary of ingested document names for the router."""
        # Query all unique source names from the vector store
        try:
            # Get all metadata from ChromaDB to find unique source names
            results = self.vector_store.collection.get(
                include=["metadatas"]
            )
            if results and results["metadatas"]:
                sources = set()
                for meta in results["metadatas"]:
                    name = meta.get("source_name", "")
                    if name:
                        sources.add(name)
                return list(sources)
        except Exception:
            pass
        return []

    def get_document_list(self) -> list[dict]:
        """List all ingested documents with metadata."""
        try:
            results = self.vector_store.collection.get(
                include=["metadatas"],
            )
            if not results or not results["metadatas"]:
                return []

            # Group by source_name
            docs: dict[str, int] = {}
            for meta in results["metadatas"]:
                name = meta.get("source_name", "unknown")
                docs[name] = docs.get(name, 0) + 1

            return [
                {"name": name, "chunk_count": count}
                for name, count in sorted(docs.items())
            ]
        except Exception:
            return []
