"""
Context Assembler — builds the structured prompt with numbered passages.

This is the bridge between retrieval and synthesis: it formats passages
so that [1], [2] markers in the LLM output are unambiguous.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.models.passage import Passage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system.txt"
CITATION_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "citation_format.txt"


class ContextAssembler:
    """Assembles the final prompt with numbered passages and citation instructions."""

    def __init__(self, max_context_tokens: int = 6000):
        self.max_context_tokens = max_context_tokens
        self._system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        self._citation_prompt = CITATION_PROMPT_PATH.read_text(encoding="utf-8")

    def assemble(
        self,
        question: str,
        passages: list[Passage],
    ) -> list[dict]:
        """
        Build the message list for the LLM.

        Returns: [system_msg, user_msg] in OpenAI-style format.
        """
        # Build numbered passages block
        passages_block = self._format_passages(passages)

        system_content = f"{self._system_prompt}\n\n{self._citation_prompt}"

        user_content = (
            f"## Retrieved Passages\n\n"
            f"{passages_block}\n\n"
            f"## Question\n\n"
            f"{question}\n\n"
            f"Please provide a comprehensive answer using ONLY the passages above. "
            f"Cite every factual claim with [n] markers."
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        return messages

    def _format_passages(self, passages: list[Passage]) -> str:
        """Format passages as a numbered list with source attribution."""
        parts = []
        token_count = 0

        for i, passage in enumerate(passages, start=1):
            # Build passage header with source info
            source_info = f"[Source: {passage.source_name}"
            if passage.location:
                source_info += f", {passage.location}"
            source_info += "]"

            passage_text = f"**Passage [{i}]** {source_info}\n{passage.text}"

            # Rough token estimate
            estimated_tokens = len(passage_text) // 4
            if token_count + estimated_tokens > self.max_context_tokens:
                logger.warning(
                    f"Context budget exceeded at passage {i}/{len(passages)}. "
                    f"Truncating to {i - 1} passages."
                )
                break

            parts.append(passage_text)
            token_count += estimated_tokens

        return "\n\n---\n\n".join(parts)

    def assemble_correction(
        self,
        original_messages: list[dict],
        original_answer: str,
        issues: str,
        max_passage: int,
    ) -> list[dict]:
        """Build a correction prompt for the citation validator retry."""
        correction_template = (Path(__file__).parent.parent / "prompts" / "correction.txt").read_text(encoding="utf-8")
        correction_prompt = correction_template.format(
            issues=issues,
            max_passage=max_passage,
        )

        # Append the original answer and correction as a conversation
        messages = original_messages.copy()
        messages.append({"role": "assistant", "content": original_answer})
        messages.append({"role": "user", "content": correction_prompt})

        return messages
