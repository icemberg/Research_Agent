"""HTML loader using BeautifulSoup for clean text extraction."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.loaders.base import BaseLoader, LoadedSection

logger = logging.getLogger(__name__)


class HTMLLoader(BaseLoader):
    """Extracts text from HTML files, preserving heading structure."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".html", ".htm"]

    def load(self, file_path: Path) -> list[LoadedSection]:
        from bs4 import BeautifulSoup

        source_name = file_path.name

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            soup = BeautifulSoup(content, "lxml")
        except Exception as e:
            logger.error(f"Failed to load HTML {file_path}: {e}")
            raise

        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        sections: list[LoadedSection] = []
        heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
        current_heading = "Document"
        current_texts: list[str] = []

        for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td"]):
            tag_name = element.name
            text = element.get_text(strip=True)

            if not text:
                continue

            if tag_name in heading_tags:
                # Flush previous section
                if current_texts:
                    sections.append(
                        LoadedSection(
                            text="\n".join(current_texts),
                            metadata={
                                "source_name": source_name,
                                "section_heading": current_heading,
                                "location": f"Section: {current_heading}",
                            },
                        )
                    )
                    current_texts = []
                current_heading = text
            else:
                current_texts.append(text)

        # Flush remaining
        if current_texts:
            sections.append(
                LoadedSection(
                    text="\n".join(current_texts),
                    metadata={
                        "source_name": source_name,
                        "section_heading": current_heading,
                        "location": f"Section: {current_heading}",
                    },
                )
            )

        logger.info(f"Loaded {len(sections)} sections from {source_name}")
        return sections
