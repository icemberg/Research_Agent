"""
Groq LLM client — wraps the Groq SDK with retry logic.

Supports both primary (llama-3.3-70b-versatile) and secondary (mixtral-8x7b-32768) models.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from backend.config import settings
from backend.llm.base import BaseLLMClient, LLMProviderError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]  # Exponential backoff seconds


class GroqClient(BaseLLMClient):
    """Groq API client with automatic retry and exponential backoff."""

    def __init__(self, model: str | None = None):
        # pyrefly: ignore [missing-import]
        from groq import Groq, AsyncGroq

        self._model = model or settings.groq_model_primary
        api_key = settings.groq_api_key
        if not api_key:
            raise LLMProviderError("GROQ_API_KEY not set")

        self._sync_client = Groq(api_key=api_key)
        self._async_client = AsyncGroq(api_key=api_key)
        logger.info(f"Groq client initialized with model: {self._model}")

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._async_client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content
                if content:
                    return content
                raise LLMProviderError("Empty response from Groq")

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF[attempt]
                    logger.warning(
                        f"Groq attempt {attempt + 1} failed: {e}. Retrying in {wait}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Groq failed after {MAX_RETRIES} attempts: {e}")

        raise LLMProviderError(f"Groq exhausted retries: {last_error}")

    async def generate_stream(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        try:
            stream = await self._async_client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Groq stream failed: {e}")
            raise LLMProviderError(f"Groq stream error: {e}")
