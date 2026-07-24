"""
SQLite storage for documents and question history.

Zero-ops, sufficient for run logs and citation audit trail.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.config import settings
from backend.models.passage import AnswerResponse, DocumentInfo

logger = logging.getLogger(__name__)


class Database:
    """SQLite storage for document metadata and question/answer history."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.sqlite_db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        """Create tables if they don't exist."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    chunk_count INTEGER DEFAULT 0,
                    upload_time TEXT NOT NULL,
                    file_size_bytes INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'indexed'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    question_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    citations_json TEXT DEFAULT '[]',
                    abstained INTEGER DEFAULT 0,
                    confidence_note TEXT DEFAULT '',
                    latency_ms REAL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()
        logger.info(f"Database initialized: {self.db_path}")

    #  Documents 

    def save_document(self, doc: DocumentInfo) -> None:
        """Save or update document metadata."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents
                    (document_id, name, chunk_count, upload_time, file_size_bytes, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.document_id,
                    doc.name,
                    doc.chunk_count,
                    doc.upload_time,
                    doc.file_size_bytes,
                    doc.status,
                ),
            )
            conn.commit()

    def get_documents(self) -> list[DocumentInfo]:
        """List all ingested documents."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY upload_time DESC"
            ).fetchall()
            return [
                DocumentInfo(
                    document_id=row["document_id"],
                    name=row["name"],
                    chunk_count=row["chunk_count"],
                    upload_time=row["upload_time"],
                    file_size_bytes=row["file_size_bytes"],
                    status=row["status"],
                )
                for row in rows
            ]

    #  Questions 

    def save_question(self, response: AnswerResponse) -> None:
        """Save a question/answer pair."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO questions
                    (question_id, question, answer, citations_json,
                     abstained, confidence_note, latency_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response.question_id,
                    response.question,
                    response.answer_text,
                    json.dumps([c.model_dump() for c in response.citations]),
                    1 if response.abstained else 0,
                    response.confidence_note,
                    response.latency_ms,
                    response.created_at,
                ),
            )
            conn.commit()

    def get_question(self, question_id: str) -> AnswerResponse | None:
        """Fetch a past question by ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM questions WHERE question_id = ?", (question_id,)
            ).fetchone()

            if not row:
                return None

            from backend.models.passage import Citation

            citations = [Citation(**c) for c in json.loads(row["citations_json"])]
            return AnswerResponse(
                question_id=row["question_id"],
                question=row["question"],
                answer_text=row["answer"],
                citations=citations,
                abstained=bool(row["abstained"]),
                confidence_note=row["confidence_note"],
                latency_ms=row["latency_ms"],
                created_at=row["created_at"],
            )

    def get_questions(self, limit: int = 50) -> list[AnswerResponse]:
        """List recent questions."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM questions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()

            from backend.models.passage import Citation

            results = []
            for row in rows:
                citations = [Citation(**c) for c in json.loads(row["citations_json"])]
                results.append(
                    AnswerResponse(
                        question_id=row["question_id"],
                        question=row["question"],
                        answer_text=row["answer"],
                        citations=citations,
                        abstained=bool(row["abstained"]),
                        confidence_note=row["confidence_note"],
                        latency_ms=row["latency_ms"],
                        created_at=row["created_at"],
                    )
                )
            return results
