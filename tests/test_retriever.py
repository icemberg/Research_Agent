"""Tests for the hybrid retriever — ensures RRF fusion works correctly."""

# pyrefly: ignore [missing-import]
import pytest
from backend.retrieval.hybrid_retriever import reciprocal_rank_fusion
from backend.models.passage import Passage


class TestReciprocalRankFusion:
    """Unit tests for the RRF merge algorithm."""

    def _make_passage(self, pid: str, score: float = 0.0) -> Passage:
        return Passage(
            id=pid, text=f"Content of {pid}",
            source_name="test.md", location="Test",
            score=score,
        )

    def test_single_list_preserves_order(self):
        """RRF with one list should preserve the original ranking."""
        passages = [
            self._make_passage("a", 0.9),
            self._make_passage("b", 0.8),
            self._make_passage("c", 0.7),
        ]
        result = reciprocal_rank_fusion([passages])
        assert result[0].id == "a"
        assert result[1].id == "b"
        assert result[2].id == "c"

    def test_two_lists_boost_shared_results(self):
        """Passages appearing in both lists should rank higher."""
        list1 = [
            self._make_passage("a", 0.9),
            self._make_passage("b", 0.8),
            self._make_passage("c", 0.7),
        ]
        list2 = [
            self._make_passage("c", 0.95),  # "c" appears in both
            self._make_passage("d", 0.85),
            self._make_passage("a", 0.75),  # "a" appears in both
        ]
        result = reciprocal_rank_fusion([list1, list2])
        # "a" and "c" should rank highest (appear in both lists)
        top_ids = {r.id for r in result[:2]}
        assert "a" in top_ids or "c" in top_ids

    def test_empty_lists_handled(self):
        """Empty input lists should not crash."""
        result = reciprocal_rank_fusion([[], []])
        assert result == []

    def test_rrf_scores_are_positive(self):
        """All RRF scores should be positive."""
        passages = [self._make_passage("a"), self._make_passage("b")]
        result = reciprocal_rank_fusion([passages])
        for p in result:
            assert p.score > 0
