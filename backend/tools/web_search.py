"""
Tavily Web Search Tool — typed, callable tool for live web data.

Normalizes search results into the same Passage schema used by the
document pipeline, so the Synthesizer needs no second code path.
"""

from __future__ import annotations

import hashlib
import logging

from backend.config import settings
from backend.models.passage import Passage, PassageSource

logger = logging.getLogger(__name__)


class TavilySearchTool:
    """Web search via Tavily API, returning results as Passage objects."""

    def __init__(self):
        self.api_key = settings.tavily_api_key
        self._client = None

    @property
    def client(self):
        """Lazy init of Tavily client."""
        if self._client is None:
            from tavily import TavilyClient

            if not self.api_key:
                raise ValueError("TAVILY_API_KEY not set")
            self._client = TavilyClient(api_key=self.api_key)
            logger.info("Tavily search client initialized")
        return self._client

    def search(self, query: str, max_results: int = 5) -> list[Passage]:
        """
        Search the web and return results as Passage objects.

        The normalization into Passage schema is the key design decision:
        downstream (assembler, synthesizer, validator) all work identically
        whether the evidence came from a document or the web.
        """
        try:
            response = self.client.search(
                query=query,
                max_results=max_results,
                search_depth="advanced",
                include_answer=False,
            )

            passages: list[Passage] = []
            for result in response.get("results", []):
                title = result.get("title", "Web Result")
                url = result.get("url", "")
                content = result.get("content", "")
                score = result.get("score", 0.0)

                if not content:
                    continue

                passage_id = hashlib.sha256(f"web::{url}::{content}".encode()).hexdigest()[:16]

                passages.append(
                    Passage(
                        id=passage_id,
                        text=content,
                        source_name=title,
                        location=url,
                        source_type=PassageSource.WEB_SEARCH,
                        score=score,
                        metadata={
                            "url": url,
                            "title": title,
                            "source_type": "web_search",
                        },
                        context_prefix=f"From web search result '{title}' ({url}). ",
                    )
                )

            logger.info(f"Web search for '{query[:50]}...': {len(passages)} results")
            return passages

        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []  # Graceful degradation — return empty, don't crash
