"""
Abstract base class for all document loaders.
SRP: a loader converts a file into structured text segments — nothing more.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LoadedSection:
    """A logical section extracted from a document."""
    text: str
    metadata: dict = field(default_factory=dict)
    # metadata keys: page_number, section_heading, paragraph_index, source_name


class BaseLoader(ABC):
    """Interface for document loaders. Swappable per Liskov (any loader works)."""

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """File extensions this loader handles (e.g., ['.pdf'])."""
        ...

    @abstractmethod
    def load(self, file_path: Path) -> list[LoadedSection]:
        """
        Parse a file and return a list of logical sections.
        Each section preserves structural metadata (page, heading, etc.).
        """
        ...

    def can_load(self, file_path: Path) -> bool:
        """Check if this loader supports the given file."""
        return file_path.suffix.lower() in self.supported_extensions
