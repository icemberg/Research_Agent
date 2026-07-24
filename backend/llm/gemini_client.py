"""
Google Gemini LLM client — fallback provider using the new google-genai SDK.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from backend.config import settings
from backend.llm.base import BaseLLMClient, LLMProviderError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]


class GeminiClient(BaseLLMClient):
    """Google Gemini API client via the google-genai SDK."""

    def __init__(self, model: str | None = None):
        from google import genai

        self._model = model or settings.gemini_model
        api_key = settings.google_api_key
        if not api_key:
            raise LLMProviderError("GOOGLE_API_KEY not set")

        self._client = genai.Client(api_key=api_key)
        logger.info(f"Gemini client initialized with model: {self._model}")

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

        # Convert OpenAI-style messages to Gemini format
        contents = self._convert_messages(messages)

        for attempt in range(MAX_RETRIES):
            try:
                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=self._model,
                    contents=contents,
                    config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                    },
                )
                if response.text:
                    return response.text
                raise LLMProviderError("Empty response from Gemini")

            except LLMProviderError:
                raise
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF[attempt]
                    logger.warning(
                        f"Gemini attempt {attempt + 1} failed: {e}. Retrying in {wait}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Gemini failed after {MAX_RETRIES} attempts: {e}")

        raise LLMProviderError(f"Gemini exhausted retries: {last_error}")

    async def generate_stream(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        contents = self._convert_messages(messages)

        try:
            response = await asyncio.to_thread(
                self._client.models.generate_content_stream,
                model=self._model,
                contents=contents,
                config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            logger.error(f"Gemini stream failed: {e}")
            raise LLMProviderError(f"Gemini stream error: {e}")

    def _convert_messages(self, messages: list[dict]) -> list:
        """
        Convert OpenAI-style messages to Gemini format.

        Gemini expects: [{"role": "user"/"model", "parts": [{"text": "..."}]}]
        System messages are prepended to the first user message.
        """
        system_parts = []
        converted = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_parts.append(content)
            elif role == "user":
                # Prepend system message to first user message
                if system_parts:
                    content = "\n\n".join(system_parts) + "\n\n" + content
                    system_parts = []
                converted.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                converted.append({"role": "model", "parts": [{"text": content}]})

        return converted
