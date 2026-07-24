"""
Loader factory — maps file extensions to the correct loader.
Open/Closed: adding a new format means adding a new loader class,
never editing existing logic here.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.loaders.base import BaseLoader
from backend.loaders.pdf_loader import PDFLoader
from backend.loaders.docx_loader import DocxLoader
from backend.loaders.text_loader import TextLoader
from backend.loaders.html_loader import HTMLLoader
from backend.loaders.csv_loader import CSVLoader

logger = logging.getLogger(__name__)


class LoaderFactory:
    """Registry of document loaders, keyed by file extension."""

    _loaders: list[BaseLoader] = [
        PDFLoader(),
        DocxLoader(),
        TextLoader(),
        HTMLLoader(),
        CSVLoader(),
    ]

    @classmethod
    def get_loader(cls, file_path: Path) -> BaseLoader:
        """Return the appropriate loader for a file, or raise ValueError."""
        ext = file_path.suffix.lower()
        for loader in cls._loaders:
            if ext in loader.supported_extensions:
                return loader

        supported = []
        for loader in cls._loaders:
            supported.extend(loader.supported_extensions)
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(set(supported)))}"
        )

    @classmethod
    def supported_extensions(cls) -> list[str]:
        """List all supported file extensions."""
        exts: list[str] = []
        for loader in cls._loaders:
            exts.extend(loader.supported_extensions)
        return sorted(set(exts))
