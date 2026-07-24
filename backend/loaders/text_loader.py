"""Plain text and Markdown loader with heading detection."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from backend.loaders.base import BaseLoader, LoadedSection

logger = logging.getLogger(__name__)

# Matches Markdown headings: # Heading, ## Subheading, etc.
MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class TextLoader(BaseLoader):
    """Loads .txt and .md files, splitting on headings for structure."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".txt", ".md"]

    def load(self, file_path: Path) -> list[LoadedSection]:
        source_name = file_path.name
        is_markdown = file_path.suffix.lower() == ".md"

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            raise

        if is_markdown:
            sections = self._split_by_headings(content, source_name)
        else:
            sections = self._split_by_paragraphs(content, source_name)

        logger.info(f"Loaded {len(sections)} sections from {source_name}")
        return sections

    def _split_by_headings(self, content: str, source_name: str) -> list[LoadedSection]:
        """Split Markdown content on heading boundaries."""
        sections: list[LoadedSection] = []
        # Find all heading positions
        headings = list(MD_HEADING_RE.finditer(content))

        if not headings:
            # No headings — treat as single section
            if content.strip():
                sections.append(
                    LoadedSection(
                        text=content.strip(),
                        metadata={
                            "source_name": source_name,
                            "section_heading": "Document",
                            "location": "Full document",
                        },
                    )
                )
            return sections

        # Text before first heading
        pre_heading_text = content[: headings[0].start()].strip()
        if pre_heading_text:
            sections.append(
                LoadedSection(
                    text=pre_heading_text,
                    metadata={
                        "source_name": source_name,
                        "section_heading": "Introduction",
                        "location": "Section: Introduction",
                    },
                )
            )

        # Each heading + its content
        for i, match in enumerate(headings):
            heading_text = match.group(2).strip()
            start = match.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
            body = content[start:end].strip()

            if body:
                sections.append(
                    LoadedSection(
                        text=body,
                        metadata={
                            "source_name": source_name,
                            "section_heading": heading_text,
                            "location": f"Section: {heading_text}",
                            "heading_level": len(match.group(1)),
                        },
                    )
                )

        return sections

    def _split_by_paragraphs(self, content: str, source_name: str) -> list[LoadedSection]:
        """Split plain text on double-newline paragraph boundaries."""
        paragraphs = re.split(r"\n\s*\n", content)
        sections: list[LoadedSection] = []

        for i, para in enumerate(paragraphs):
            text = para.strip()
            if text and len(text) > 20:  # Skip trivially short fragments
                sections.append(
                    LoadedSection(
                        text=text,
                        metadata={
                            "source_name": source_name,
                            "paragraph_index": i + 1,
                            "location": f"Paragraph {i + 1}",
                        },
                    )
                )

        return sections
