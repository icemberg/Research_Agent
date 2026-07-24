"""DOCX loader using python-docx for paragraph-level extraction."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.loaders.base import BaseLoader, LoadedSection

logger = logging.getLogger(__name__)


class DocxLoader(BaseLoader):
    """Extracts text from DOCX files with paragraph and heading structure."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".docx"]

    def load(self, file_path: Path) -> list[LoadedSection]:
        from docx import Document

        sections: list[LoadedSection] = []
        source_name = file_path.name

        try:
            doc = Document(file_path)
            current_heading = "Document Start"
            current_paragraphs: list[str] = []
            para_index = 0

            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue

                # Detect heading styles
                if para.style and para.style.name.startswith("Heading"):
                    # Flush accumulated paragraphs under previous heading
                    if current_paragraphs:
                        sections.append(
                            LoadedSection(
                                text="\n".join(current_paragraphs),
                                metadata={
                                    "source_name": source_name,
                                    "section_heading": current_heading,
                                    "location": f"Section: {current_heading}",
                                    "paragraph_index": para_index,
                                },
                            )
                        )
                        current_paragraphs = []
                        para_index += 1
                    current_heading = text
                else:
                    current_paragraphs.append(text)

            # Flush remaining
            if current_paragraphs:
                sections.append(
                    LoadedSection(
                        text="\n".join(current_paragraphs),
                        metadata={
                            "source_name": source_name,
                            "section_heading": current_heading,
                            "location": f"Section: {current_heading}",
                            "paragraph_index": para_index,
                        },
                    )
                )

        except Exception as e:
            logger.error(f"Failed to load DOCX {file_path}: {e}")
            raise

        logger.info(f"Loaded {len(sections)} sections from {source_name}")
        return sections
