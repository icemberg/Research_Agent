"""Tests for the citation validator — the reflection/self-critique step."""

# pyrefly: ignore [missing-import]
import pytest
from backend.pipeline.citation_validator import CitationValidator
from backend.models.passage import Passage


class TestCitationValidator:
    """Unit tests for CitationValidator."""

    def setup_method(self):
        self.validator = CitationValidator()
        self.passages = [
            Passage(
                id="p1", text="AI was invented in the 1950s.",
                source_name="ai.md", location="Section: History",
            ),
            Passage(
                id="p2", text="Deep learning uses neural networks.",
                source_name="dl.md", location="Section: Basics",
            ),
            Passage(
                id="p3", text="Transformers use attention mechanisms.",
                source_name="transformers.md", location="Section: Architecture",
            ),
        ]

    def test_valid_citations_pass(self):
        """A well-cited answer should pass validation."""
        answer = (
            "AI was first developed in the 1950s [1]. "
            "Modern approaches use deep learning with neural networks [2]. "
            "The transformer architecture introduced attention mechanisms [3]."
        )
        result = self.validator.validate(answer, self.passages)
        assert result.is_valid
        assert len(result.orphan_markers) == 0
        assert len(result.uncited_sentences) == 0

    def test_orphan_marker_detected(self):
        """References to non-existent passages should be flagged."""
        answer = (
            "AI started in the 1950s [1]. "
            "Something interesting happened [5]."  # [5] doesn't exist
        )
        result = self.validator.validate(answer, self.passages)
        assert not result.is_valid
        assert 5 in result.orphan_markers

    def test_uncited_factual_sentence_detected(self):
        """Factual sentences without citations should be flagged."""
        answer = (
            "AI was first developed in the 1950s [1]. "
            "Machine learning has revolutionized many industries."  # No citation!
        )
        result = self.validator.validate(answer, self.passages)
        assert not result.is_valid
        assert len(result.uncited_sentences) > 0

    def test_abstention_not_flagged(self):
        """Abstention responses should not be flagged as uncited."""
        answer = "ABSTAIN: The provided sources do not contain information about quantum computing."
        result = self.validator.validate(answer, self.passages)
        # Abstentions are valid even without citations
        assert len(result.uncited_sentences) == 0

    def test_multiple_citations_per_sentence(self):
        """Multiple citations on one sentence should all be valid."""
        answer = "Neural networks are used in deep learning and AI [1][2][3]."
        result = self.validator.validate(answer, self.passages)
        assert result.is_valid
        assert len(result.citations) == 3

    def test_citation_objects_populated(self):
        """Citation objects should contain correct source info."""
        answer = "AI research began in the 1950s [1]."
        result = self.validator.validate(answer, self.passages)
        assert len(result.citations) == 1
        assert result.citations[0].marker == 1
        assert result.citations[0].source == "ai.md"
        assert result.citations[0].location == "Section: History"

    def test_empty_answer(self):
        """Empty answer should not crash."""
        result = self.validator.validate("", self.passages)
        assert result.is_valid  # No claims to check
