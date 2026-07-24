"""Tests for the query router."""

# pyrefly: ignore [missing-import]
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.pipeline.router import QueryRouter, RouteDecision
from backend.llm.base import BaseLLMClient, LLMProviderError


class MockLLM(BaseLLMClient):
    """Mock LLM for testing."""

    def __init__(self, response: str = "CORPUS"):
        self._response = response

    @property
    def model_name(self) -> str:
        return "mock-model"

    async def generate(self, messages, temperature=0.1, max_tokens=4096):
        return self._response

    async def generate_stream(self, messages, temperature=0.1, max_tokens=4096):
        yield self._response


class TestQueryRouter:
    """Unit tests for QueryRouter."""

    @pytest.mark.asyncio
    async def test_no_docs_no_search_abstains(self):
        """No documents and no web search → ABSTAIN."""
        router = QueryRouter(MockLLM())
        decision = await router.route(
            question="What is AI?",
            document_summaries=[],
            allow_web_search=False,
            has_documents=False,
        )
        assert decision == RouteDecision.ABSTAIN

    @pytest.mark.asyncio
    async def test_no_docs_with_search_goes_web(self):
        """No documents but web search allowed → WEB_SEARCH."""
        router = QueryRouter(MockLLM())
        decision = await router.route(
            question="What is AI?",
            document_summaries=[],
            allow_web_search=True,
            has_documents=False,
        )
        assert decision == RouteDecision.WEB_SEARCH

    @pytest.mark.asyncio
    async def test_corpus_decision(self):
        """LLM returns CORPUS → CORPUS."""
        router = QueryRouter(MockLLM(response="CORPUS"))
        decision = await router.route(
            question="What is AI?",
            document_summaries=["AI overview document"],
            allow_web_search=True,
            has_documents=True,
        )
        assert decision == RouteDecision.CORPUS

    @pytest.mark.asyncio
    async def test_llm_failure_defaults_to_corpus(self):
        """If the LLM fails, router should default to CORPUS (graceful degradation)."""

        class FailingLLM(MockLLM):
            async def generate(self, *args, **kwargs):
                raise LLMProviderError("API down")

        router = QueryRouter(FailingLLM())
        decision = await router.route(
            question="What is AI?",
            document_summaries=["AI document"],
            allow_web_search=True,
            has_documents=True,
        )
        assert decision == RouteDecision.CORPUS  # Graceful degradation
