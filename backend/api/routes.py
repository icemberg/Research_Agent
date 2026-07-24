"""
FastAPI route handlers — thin layer delegating to the Orchestrator.

All routes share the same Orchestrator instance (initialized in main.py lifespan).
"""

from __future__ import annotations

import json
import logging
import tempfile
import shutil
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from backend.models.requests import AskRequest, IngestResponse
from backend.models.passage import AnswerResponse, DocumentInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Research Agent"])


@router.post("/ingest", response_model=list[IngestResponse])
async def ingest_documents(
    request: Request,
    files: list[UploadFile] = File(..., description="Documents to ingest"),
):
    """Upload and ingest one or more documents into the corpus."""
    orchestrator = request.app.state.orchestrator
    db = request.app.state.database

    results = []

    for upload_file in files:
        # Save uploaded file to temp location
        suffix = Path(upload_file.filename or "document").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await upload_file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            result = orchestrator.ingest_file(tmp_path, source_name=upload_file.filename)
            result["name"] = upload_file.filename or result["name"]

            # Save to database
            db.save_document(DocumentInfo(
                document_id=result["document_id"],
                name=result["name"],
                chunk_count=result["chunk_count"],
                file_size_bytes=len(content),
                status=result["status"],
            ))

            results.append(IngestResponse(**result))

        except ValueError as e:
            results.append(IngestResponse(
                document_id="",
                name=upload_file.filename or "unknown",
                chunk_count=0,
                status=f"error: {e}",
            ))
        except Exception as e:
            logger.error(f"Ingestion error for {upload_file.filename}: {e}")
            results.append(IngestResponse(
                document_id="",
                name=upload_file.filename or "unknown",
                chunk_count=0,
                status=f"error: {e}",
            ))
        finally:
            # Clean up temp file
            tmp_path.unlink(missing_ok=True)

    return results


@router.get("/documents")
async def list_documents(request: Request):
    """List all ingested documents with metadata."""
    db = request.app.state.database
    docs = db.get_documents()
    if not docs:
        # Fallback: get from orchestrator
        orchestrator = request.app.state.orchestrator
        doc_list = orchestrator.get_document_list()
        return doc_list
    return [doc.model_dump() for doc in docs]


@router.post("/ask", response_model=AnswerResponse)
async def ask_question(request: Request, body: AskRequest):
    """Ask a question and get a cited answer (synchronous)."""
    orchestrator = request.app.state.orchestrator
    db = request.app.state.database

    response = await orchestrator.ask(
        question=body.question,
        document_ids=body.document_ids,
        allow_web_search=body.allow_web_search,
    )

    # Save to history
    db.save_question(response)

    return response


@router.post("/ask/stream")
async def ask_question_stream(request: Request, body: AskRequest):
    """
    Ask a question with streaming response (SSE).

    Events:
    - status: Progress updates
    - token: Individual answer tokens
    - citations: Final citation list
    - done: Complete response
    - error: Error message
    """
    orchestrator = request.app.state.orchestrator
    db = request.app.state.database

    async def event_generator():
        try:
            async for event in orchestrator.ask_stream(
                question=body.question,
                document_ids=body.document_ids,
                allow_web_search=body.allow_web_search,
            ):
                event_type = event["type"]
                event_data = event["data"]

                if isinstance(event_data, (dict, list)):
                    data_str = json.dumps(event_data)
                else:
                    data_str = str(event_data)

                yield {
                    "event": event_type,
                    "data": data_str,
                }

                # Save completed responses to history
                if event_type == "done" and isinstance(event_data, dict):
                    try:
                        from backend.models.passage import Citation
                        citations = [
                            Citation(**c) for c in event_data.get("citations", [])
                        ]
                        answer_response = AnswerResponse(
                            answer_text=event_data.get("answer_text", ""),
                            citations=citations,
                            abstained=event_data.get("abstained", False),
                            latency_ms=event_data.get("latency_ms", 0),
                            question_id=event_data.get("question_id", ""),
                            question=body.question,
                        )
                        db.save_question(answer_response)
                    except Exception as e:
                        logger.error(f"Failed to save streamed response: {e}")

        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.get("/questions/{question_id}")
async def get_question(request: Request, question_id: str):
    """Fetch a past question + answer by ID."""
    db = request.app.state.database
    response = db.get_question(question_id)

    if not response:
        raise HTTPException(status_code=404, detail=f"Question {question_id} not found")

    return response.model_dump()


@router.get("/questions")
async def list_questions(request: Request, limit: int = 50):
    """List recent questions and answers."""
    db = request.app.state.database
    questions = db.get_questions(limit=limit)
    return [q.model_dump() for q in questions]
