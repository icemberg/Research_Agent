"""
Synthesizer — calls the LLM to generate a cited answer from passages.

This component is intentionally thin: it delegates prompt construction
to ContextAssembler and validation to CitationValidator.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from backend.llm.base import BaseLLMClient
from backend.pipeline.context_assembler import ContextAssembler
from backend.models.passage import Passage

logger = logging.getLogger(__name__)


class Synthesizer:
    """Generates cited answers from retrieved passages via LLM."""

    def __init__(self, llm_client: BaseLLMClient, context_assembler: ContextAssembler):
        self.llm = llm_client
        self.assembler = context_assembler

    async def synthesize(
        self,
        question: str,
        passages: list[Passage],
        temperature: float = 0.1,
    ) -> tuple[str, list[dict]]:
        """
        Generate a cited answer.

        Returns:
            (answer_text, messages) — messages are kept for potential retry.
        """
        messages = self.assembler.assemble(question, passages)

        logger.info(
            f"Synthesizing answer for '{question[:50]}...' "
            f"with {len(passages)} passages via {self.llm.model_name}"
        )

        answer = await self.llm.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=4096,
        )

        logger.debug(f"Raw answer ({len(answer)} chars): {answer[:100]}...")
        return answer, messages

    async def synthesize_stream(
        self,
        question: str,
        passages: list[Passage],
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        """Stream the synthesis token by token."""
        messages = self.assembler.assemble(question, passages)

        async for token in self.llm.generate_stream(
            messages=messages,
            temperature=temperature,
            max_tokens=4096,
        ):
            yield token

    async def retry_with_correction(
        self,
        original_messages: list[dict],
        original_answer: str,
        issues: str,
        max_passage: int,
    ) -> str:
        """Retry synthesis with citation correction instructions."""
        messages = self.assembler.assemble_correction(
            original_messages, original_answer, issues, max_passage
        )

        logger.info("Retrying synthesis with citation corrections")
        answer = await self.llm.generate(
            messages=messages,
            temperature=0.05,  # Lower temp for corrections
            max_tokens=4096,
        )

        return answer
