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

    # Eagerly load the embedding model now so the (slow) download/init
    # happens during startup instead of blocking the first HTTP request.
    # Without this, the embedder's lazy `@property` defers loading until
    # first use, causing 502s while the model downloads on first request.
    logger.info("Eagerly loading embedding model before accepting requests...")
    app.state.orchestrator.embedder.load()
    logger.info("Embedding model ready.")

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


from fastapi.responses import RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
import os

frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

if os.path.exists(frontend_dist):
    # Mount the /assets directory for JS/CSS files
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Serve the root index.html
    @app.get("/")
    async def root():
        return FileResponse(os.path.join(frontend_dist, "index.html"))

    # Catch-all for other frontend files and SPA routing
    @app.get("/{file_name:path}")
    async def serve_frontend(file_name: str):
        # Do not intercept API requests or docs
        if file_name.startswith("api/") or file_name in ["docs", "openapi.json", "health"]:
            raise HTTPException(status_code=404)
        
        # Try to serve exact file (e.g. favicon.png)
        file_path = os.path.join(frontend_dist, file_name)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Fallback to SPA index.html
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    @app.get("/")
    async def root():
        """Redirect root to API documentation."""
        return RedirectResponse(url="/docs")

    @app.get("/favicon.ico")
    async def favicon():
        """Serve favicon or suppress 404 error."""
        if os.path.exists("frontend/public/favicon.png"):
            return FileResponse("frontend/public/favicon.png")
        return Response(content=b"", media_type="image/x-icon", status_code=204)

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
