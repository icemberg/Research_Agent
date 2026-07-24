"""Abstract base for LLM clients — Dependency Inversion principle."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator


class BaseLLMClient(ABC):
    """
    Abstract LLM client interface.

    Any LLM provider (Groq, Gemini, OpenAI, local) implements this.
    The orchestration layer depends only on this abstraction.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the model being used."""
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """
        Generate a completion from messages.

        Args:
            messages: List of {"role": "system"|"user"|"assistant", "content": str}
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens in response

        Returns:
            Generated text content.
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """
        Stream a completion token-by-token.

        Yields:
            Individual token strings as they arrive.
        """
        ...


class LLMProviderError(Exception):
    """Raised when an LLM provider fails — triggers fallback."""
    pass
