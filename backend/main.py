"""
FastAPI application entry point.

- CORS middleware for React dev server
- Lifespan event to initialize components on startup
- Health check endpoint
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api.routes import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan — initialize heavy components once on startup.

    This avoids cold-start latency on the first request.
    """
    logger.info("Starting Research Agent API...")

    # Initialize core components
    from backend.pipeline.orchestrator import Orchestrator
    from backend.storage.database import Database

    settings.ensure_data_dirs()

    app.state.orchestrator = Orchestrator()
    app.state.database = Database()

    logger.info(
        f"Research Agent API ready. "
        f"Vector store: {app.state.orchestrator.vector_store.count()} passages"
    )

    yield

    logger.info("Shutting down Research Agent API...")


app = FastAPI(
    title="Research Agent with Citations",
    description=(
        "A RAG-based research agent that answers questions with per-claim citations, "
        "grounded strictly in a defined evidence set."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow React dev server and common origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alt dev server
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.get("/health")
async def health_check():
    """Liveness/readiness check."""
    orchestrator = app.state.orchestrator
    return {
        "status": "healthy",
        "vector_store_passages": orchestrator.vector_store.count(),
        "bm25_passages": orchestrator.bm25_store.count(),
        "llm_model": orchestrator.llm.model_name,
    }
