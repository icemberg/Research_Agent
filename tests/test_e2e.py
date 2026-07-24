"""End-to-end tests for the Research Agent pipeline."""

# pyrefly: ignore [missing-import]
import pytest
from backend.pipeline.orchestrator import Orchestrator
from backend.models.passage import AnswerResponse
from pathlib import Path


@pytest.fixture
def orchestrator():
    """Provides an orchestrator instance for E2E tests."""
    return Orchestrator()


@pytest.mark.asyncio
async def test_e2e_abstain_on_unrelated_question(orchestrator):
    """The agent should abstain when asked a question it cannot answer from the corpus."""
    # Note: we assume the corpus doesn't contain info about the GDP of Mars
    response = await orchestrator.ask(
        question="What is the GDP of Mars?",
        allow_web_search=False
    )
    assert response.abstained
    assert "ABSTAIN" in response.answer_text


@pytest.mark.asyncio
async def test_e2e_answer_with_citations(orchestrator):
    """The agent should answer a question correctly if the document is ingested."""
    # First, ingest a test document
    test_doc = Path("sample_docs/ai_transformers_overview.md")
    if test_doc.exists():
        orchestrator.ingest_file(test_doc)

        # Then, ask a question
        response = await orchestrator.ask(
            question="What is the attention mechanism in transformers?",
            allow_web_search=False
        )
        
        # Verify response
        assert not response.abstained
        assert len(response.citations) > 0
        assert "self-attention" in response.answer_text.lower()
        
        # Verify citation markers match actual citations
        import re
        markers_in_text = set(int(m) for m in re.findall(r"\[(\d+)\]", response.answer_text))
        citation_markers = set(c.marker for c in response.citations)
        assert markers_in_text.issubset(citation_markers)
