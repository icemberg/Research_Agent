"""
Centralized configuration — all tunables loaded from environment / .env file.
Config is the single source of truth for every component (DRY).
"""

from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings driven by environment variables."""

    # ── LLM Providers ────────────────────────────────────────
    groq_api_key: str = Field(default="", description="Groq API key")
    groq_model_primary: str = Field(
        default="llama-3.3-70b-versatile",
        description="Primary Groq model (strong instruction-following)",
    )
    groq_model_secondary: str = Field(
        default="mixtral-8x7b-32768",
        description="Secondary Groq model (longer context window)",
    )

    google_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-2.0-flash", description="Gemini model name")

    # ── Web Search ───────────────────────────────────────────
    tavily_api_key: str = Field(default="", description="Tavily API key for web search")

    # ── Retrieval ────────────────────────────────────────────
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="SentenceTransformer embedding model",
    )
    reranker_model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        description="Cross-encoder reranker model",
    )
    chunk_size: int = Field(default=400, description="Target chunk size in tokens")
    chunk_overlap: int = Field(default=60, description="Overlap between chunks in tokens")
    top_k: int = Field(default=8, description="Final number of passages returned")
    top_k_candidates: int = Field(
        default=24, description="Candidates fetched before re-ranking"
    )
    enable_reranker: bool = Field(default=True, description="Enable cross-encoder re-ranking")

    # ── Citation Validation ──────────────────────────────────
    max_citation_retries: int = Field(
        default=2, description="Max retries for citation validation"
    )

    # ── Storage ──────────────────────────────────────────────
    chroma_persist_dir: str = Field(default="./data/chroma")
    bm25_persist_dir: str = Field(default="./data/bm25")
    sqlite_db_path: str = Field(default="./data/research_agent.db")

    # ── Server ───────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def ensure_data_dirs(self) -> None:
        """Create data directories if they don't exist."""
        for path_str in [self.chroma_persist_dir, self.bm25_persist_dir]:
            Path(path_str).mkdir(parents=True, exist_ok=True)
        # Ensure SQLite directory exists
        Path(self.sqlite_db_path).parent.mkdir(parents=True, exist_ok=True)


# Singleton — import this everywhere
settings = Settings()
