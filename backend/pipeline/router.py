"""
Query Router — classifies incoming questions before synthesis runs.

Decides: "answer from corpus" vs. "invoke web search" vs. "abstain"
BEFORE synthesis, cutting cost and hallucination surface.
"""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path

from backend.llm.base import BaseLLMClient, LLMProviderError

logger = logging.getLogger(__name__)

ROUTER_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "router.txt"


class RouteDecision(str, Enum):
    CORPUS = "CORPUS"
    WEB_SEARCH = "WEB_SEARCH"
    ABSTAIN = "ABSTAIN"


class QueryRouter:
    """
    LLM-based query router with graceful fallback.

    On router failure, defaults to CORPUS (try to answer) rather than crashing.
    """

    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client
        self._prompt_template = ROUTER_PROMPT_PATH.read_text(encoding="utf-8")

    async def route(
        self,
        question: str,
        document_summaries: list[str],
        allow_web_search: bool = False,
        has_documents: bool = True,
    ) -> RouteDecision:
        """
        Classify the question into a routing decision.

        Logic:
        - If no documents and web search not allowed → ABSTAIN
        - If no documents but web search allowed → WEB_SEARCH
        - Otherwise, ask the LLM to classify
        """
        # Edge cases
        if not has_documents and not allow_web_search:
            logger.info("No documents and web search disabled → ABSTAIN")
            return RouteDecision.ABSTAIN

        if not has_documents and allow_web_search:
            logger.info("No documents, web search enabled → WEB_SEARCH")
            return RouteDecision.WEB_SEARCH

        # Build prompt
        doc_summary = "\n".join(f"- {s}" for s in document_summaries) if document_summaries else "No document summaries available"
        prompt = self._prompt_template.format(
            document_summary=doc_summary,
            question=question,
        )

        try:
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=20,
            )

            decision_text = response.strip().upper()

            # Parse the response
            if "ABSTAIN" in decision_text:
                decision = RouteDecision.ABSTAIN
            elif "WEB_SEARCH" in decision_text and allow_web_search:
                decision = RouteDecision.WEB_SEARCH
            elif "WEB_SEARCH" in decision_text and not allow_web_search:
                # Web search requested but not allowed → try corpus
                decision = RouteDecision.CORPUS
            else:
                decision = RouteDecision.CORPUS

            logger.info(f"Router decision for '{question[:50]}...': {decision.value}")
            return decision

        except (LLMProviderError, Exception) as e:
            # Graceful degradation: if router fails, try corpus
            logger.warning(f"Router failed ({e}), defaulting to CORPUS")
            return RouteDecision.CORPUS
