"""PDF loader using pdfplumber for page-accurate text extraction."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.loaders.base import BaseLoader, LoadedSection

logger = logging.getLogger(__name__)


class PDFLoader(BaseLoader):
    """Extracts text from PDFs with page-level metadata preservation."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    def load(self, file_path: Path) -> list[LoadedSection]:
        import pdfplumber

        sections: list[LoadedSection] = []
        source_name = file_path.name

        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()
                    if text and text.strip():
                        sections.append(
                            LoadedSection(
                                text=text.strip(),
                                metadata={
                                    "source_name": source_name,
                                    "page_number": page_num,
                                    "location": f"Page {page_num}",
                                    "total_pages": len(pdf.pages),
                                },
                            )
                        )
        except Exception as e:
            logger.error(f"Failed to load PDF {file_path}: {e}")
            raise

        logger.info(f"Loaded {len(sections)} pages from {source_name}")
        return sections
