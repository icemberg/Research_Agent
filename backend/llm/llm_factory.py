"""
LLM Factory — resolves provider chain: Groq primary → Groq secondary → Gemini fallback.

FallbackLLMClient wraps multiple providers and cascades on failure.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from backend.config import settings
from backend.llm.base import BaseLLMClient, LLMProviderError

logger = logging.getLogger(__name__)


class FallbackLLMClient(BaseLLMClient):
    """
    Wraps a chain of LLM clients, trying each in order.

    On generate/stream failure (LLMProviderError), falls through to the next.
    This provides resilience: Groq rate limit → Groq secondary → Gemini.
    """

    def __init__(self, clients: list[BaseLLMClient]):
        if not clients:
            raise ValueError("At least one LLM client is required")
        self._clients = clients
        self._active_index = 0
        logger.info(
            f"FallbackLLMClient initialized with {len(clients)} providers: "
            f"{[c.model_name for c in clients]}"
        )

    @property
    def model_name(self) -> str:
        return self._clients[self._active_index].model_name

    async def generate(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        errors = []
        for i, client in enumerate(self._clients):
            try:
                result = await client.generate(messages, temperature, max_tokens)
                self._active_index = i
                if i > 0:
                    logger.info(f"Fallback to {client.model_name} succeeded")
                return result
            except (LLMProviderError, Exception) as e:
                logger.warning(f"Provider {client.model_name} failed: {e}")
                errors.append(f"{client.model_name}: {e}")

        raise LLMProviderError(
            f"All {len(self._clients)} providers failed: {'; '.join(errors)}"
        )

    async def generate_stream(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        errors = []
        for i, client in enumerate(self._clients):
            try:
                async for token in client.generate_stream(messages, temperature, max_tokens):
                    self._active_index = i
                    yield token
                return  # Stream completed successfully
            except (LLMProviderError, Exception) as e:
                logger.warning(f"Stream provider {client.model_name} failed: {e}")
                errors.append(f"{client.model_name}: {e}")

        raise LLMProviderError(
            f"All stream providers failed: {'; '.join(errors)}"
        )


def get_llm_client() -> BaseLLMClient:
    """
    Build the LLM client chain based on available API keys.

    Priority: Groq Primary → Groq Secondary → Gemini
    """
    clients: list[BaseLLMClient] = []

    # Try Groq primary
    if settings.groq_api_key:
        try:
            from backend.llm.groq_client import GroqClient

            clients.append(GroqClient(model=settings.groq_model_primary))
            logger.info(f"Added Groq primary: {settings.groq_model_primary}")
        except Exception as e:
            logger.warning(f"Failed to init Groq primary: {e}")

        # Try Groq secondary
        try:
            from backend.llm.groq_client import GroqClient

            clients.append(GroqClient(model=settings.groq_model_secondary))
            logger.info(f"Added Groq secondary: {settings.groq_model_secondary}")
        except Exception as e:
            logger.warning(f"Failed to init Groq secondary: {e}")

    # Try Gemini fallback
    if settings.google_api_key:
        try:
            from backend.llm.gemini_client import GeminiClient

            clients.append(GeminiClient())
            logger.info(f"Added Gemini fallback: {settings.gemini_model}")
        except Exception as e:
            logger.warning(f"Failed to init Gemini: {e}")

    if not clients:
        raise LLMProviderError(
            "No LLM providers available. Set GROQ_API_KEY or GOOGLE_API_KEY."
        )

    if len(clients) == 1:
        return clients[0]

    return FallbackLLMClient(clients)
