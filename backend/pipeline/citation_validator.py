"""
Citation Validator — the reflection/self-critique step.

Programmatically checks every [n] marker in the answer:
1. Confirms each n maps to a real passage (catches hallucinated numbers)
2. Flags factual sentences missing citation markers
3. On failure, triggers bounded retry (max 2) via the Synthesizer

This is not just nice-to-have — it's what makes citations verifiable
rather than decorative.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from backend.config import settings
from backend.models.passage import Passage, Citation

logger = logging.getLogger(__name__)

# Matches [1], [2], [1][3], etc.
CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")

# Rough heuristic: a "factual sentence" contains at least 5 words
# and doesn't start with common non-factual patterns
NON_FACTUAL_PREFIXES = (
    "abstain",
    "i cannot",
    "i don't",
    "the provided",
    "unfortunately",
    "note:",
    "however,",
    "in summary",
    "to summarize",
    "in conclusion",
    "overall,",
)


@dataclass
class ValidationResult:
    """Result of citation validation."""
    is_valid: bool
    issues: list[str]
    citations: list[Citation]
    orphan_markers: list[int]       # [n] that don't map to any passage
    uncited_sentences: list[str]    # Factual sentences without citations


class CitationValidator:
    """
    Validates citation integrity in generated answers.

    Two checks:
    1. Marker validity: every [n] maps to an actual passage
    2. Coverage: every factual sentence has at least one [n]
    """

    def validate(
        self,
        answer_text: str,
        passages: list[Passage],
    ) -> ValidationResult:
        """Validate all citations in an answer against the passage set."""
        max_passage = len(passages)

        # 1. Extract all citation markers
        all_markers = [int(m) for m in CITATION_MARKER_RE.findall(answer_text)]
        unique_markers = set(all_markers)

        # 2. Check for orphan markers (reference non-existent passages)
        orphan_markers = [m for m in unique_markers if m < 1 or m > max_passage]

        # 3. Check for uncited factual sentences
        sentences = self._split_sentences(answer_text)
        uncited_sentences = []
        for sentence in sentences:
            if self._is_factual(sentence) and not CITATION_MARKER_RE.search(sentence):
                uncited_sentences.append(sentence)

        # 4. Build citation objects for valid markers
        citations: list[Citation] = []
        for marker in sorted(unique_markers):
            if 1 <= marker <= max_passage:
                passage = passages[marker - 1]  # 1-indexed to 0-indexed
                citations.append(
                    Citation(
                        marker=marker,
                        source=passage.source_name,
                        location=passage.location,
                        snippet=passage.text[:200] + ("..." if len(passage.text) > 200 else ""),
                    )
                )

        # 5. Compile issues
        issues: list[str] = []
        if orphan_markers:
            issues.append(
                f"Invalid citation markers {orphan_markers} — "
                f"only passages [1] through [{max_passage}] exist."
            )
        if uncited_sentences:
            for i, sentence in enumerate(uncited_sentences[:3]):  # Cap at 3 examples
                issues.append(
                    f"Uncited factual sentence: \"{sentence[:80]}...\""
                )
            if len(uncited_sentences) > 3:
                issues.append(
                    f"...and {len(uncited_sentences) - 3} more uncited sentences."
                )

        is_valid = len(orphan_markers) == 0 and len(uncited_sentences) == 0

        logger.info(
            f"Citation validation: valid={is_valid}, "
            f"markers={len(unique_markers)}, orphans={len(orphan_markers)}, "
            f"uncited={len(uncited_sentences)}"
        )

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            citations=citations,
            orphan_markers=orphan_markers,
            uncited_sentences=uncited_sentences,
        )

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences for validation."""
        # Split on sentence-ending punctuation followed by space or newline
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

    def _is_factual(self, sentence: str) -> bool:
        """
        Heuristic: determine if a sentence is making a factual claim
        that should be cited (vs. meta-commentary, transitions, etc.).
        """
        lower = sentence.lower().strip()

        # Skip abstention and meta-commentary
        for prefix in NON_FACTUAL_PREFIXES:
            if lower.startswith(prefix):
                return False

        # Skip very short sentences (likely transitions)
        words = sentence.split()
        if len(words) < 5:
            return False

        # Skip questions
        if sentence.strip().endswith("?"):
            return False

        # Skip sentences that are just headings (all bold/caps)
        if sentence.strip().startswith("#") or sentence.strip().startswith("**"):
            return False

        return True
