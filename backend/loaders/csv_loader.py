"""CSV loader — each row or group of rows becomes a passage."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from backend.loaders.base import BaseLoader, LoadedSection

logger = logging.getLogger(__name__)


class CSVLoader(BaseLoader):
    """Loads CSV files, treating each row as a passage with column headers as context."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".csv"]

    def load(self, file_path: Path) -> list[LoadedSection]:
        source_name = file_path.name
        sections: list[LoadedSection] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, start=2):  # row 1 is header
                    # Build a readable text representation
                    text_parts = []
                    for col, val in row.items():
                        if val and val.strip():
                            text_parts.append(f"{col}: {val.strip()}")

                    if text_parts:
                        sections.append(
                            LoadedSection(
                                text="\n".join(text_parts),
                                metadata={
                                    "source_name": source_name,
                                    "row_number": row_num,
                                    "location": f"Row {row_num}",
                                },
                            )
                        )
        except Exception as e:
            logger.error(f"Failed to load CSV {file_path}: {e}")
            raise

        logger.info(f"Loaded {len(sections)} rows from {source_name}")
        return sections
