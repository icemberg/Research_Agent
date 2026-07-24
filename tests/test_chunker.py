"""Tests for the semantic chunker — boundary correctness, overlap, metadata."""

# pyrefly: ignore [missing-import]
import pytest
from backend.chunking.semantic_chunker import SemanticChunker, _generate_passage_id, _build_context_prefix
from backend.loaders.base import LoadedSection


class TestChunker:
    """Unit tests for SemanticChunker."""

    def setup_method(self):
        self.chunker = SemanticChunker(chunk_size=50, chunk_overlap=10)

    def test_small_section_stays_whole(self):
        """A section smaller than chunk_size should not be split."""
        section = LoadedSection(
            text="This is a short paragraph about AI.",
            metadata={"source_name": "test.md", "location": "Section: Intro"},
        )
        passages = self.chunker.chunk_sections([section], "test.md")
        assert len(passages) == 1
        assert passages[0].text == "This is a short paragraph about AI."

    def test_large_section_gets_split(self):
        """A section larger than chunk_size should be split into multiple chunks."""
        # Create a text that's clearly over 50 tokens (~200 chars)
        long_text = ". ".join([f"Sentence number {i} contains some information about topic {i}" for i in range(20)])
        section = LoadedSection(
            text=long_text,
            metadata={"source_name": "test.md", "location": "Section: Long"},
        )
        passages = self.chunker.chunk_sections([section], "test.md")
        assert len(passages) > 1

    def test_metadata_preserved(self):
        """Metadata from sections should survive into passages."""
        section = LoadedSection(
            text="Test content.",
            metadata={"source_name": "report.pdf", "page_number": 5, "location": "Page 5"},
        )
        passages = self.chunker.chunk_sections([section], "report.pdf")
        assert passages[0].source_name == "report.pdf"
        assert passages[0].location == "Page 5"

    def test_dedup_prevents_duplicates(self):
        """Same text from same source should not create duplicate passages."""
        section = LoadedSection(
            text="Duplicate content.",
            metadata={"source_name": "test.md", "location": "Section: A"},
        )
        # Two identical sections
        passages = self.chunker.chunk_sections([section, section], "test.md")
        assert len(passages) == 1

    def test_context_prefix_generated(self):
        """Each passage should have a contextual prefix."""
        section = LoadedSection(
            text="Some content about climate change.",
            metadata={
                "source_name": "climate.pdf",
                "section_heading": "Global Warming",
                "location": "Section: Global Warming",
            },
        )
        passages = self.chunker.chunk_sections([section], "climate.pdf")
        assert passages[0].context_prefix != ""
        assert "climate.pdf" in passages[0].context_prefix

    def test_empty_section_produces_no_passages(self):
        """Empty sections should be skipped."""
        section = LoadedSection(text="   ", metadata={"source_name": "test.md"})
        passages = self.chunker.chunk_sections([section], "test.md")
        assert len(passages) == 0


class TestHelpers:
    def test_passage_id_deterministic(self):
        """Same source + text should always produce the same ID."""
        id1 = _generate_passage_id("doc.pdf", "Hello world")
        id2 = _generate_passage_id("doc.pdf", "Hello world")
        assert id1 == id2

    def test_passage_id_different_for_different_content(self):
        id1 = _generate_passage_id("doc.pdf", "Hello world")
        id2 = _generate_passage_id("doc.pdf", "Different content")
        assert id1 != id2

    def test_context_prefix_format(self):
        prefix = _build_context_prefix("report.pdf", {"page_number": 3})
        assert "report.pdf" in prefix
        assert "Page 3" in prefix
