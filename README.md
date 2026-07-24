# Research Agent with Citations

A production-grade RAG system that answers questions with **per-claim citations**, grounded strictly in a defined evidence set. Every factual claim is traceable to a specific source passage — an answer without a citation is treated as an answer that doesn't exist.

## Features

- **Hybrid Retrieval**: Dense embeddings (ChromaDB) + BM25 keyword search, merged via Reciprocal Rank Fusion
- **Contextual Chunking**: Anthropic-style context prefixes on every chunk for dramatically better retrieval
- **Cross-Encoder Re-ranking**: MS-MARCO re-ranker for precision on top-k results
- **Citation Validation**: Programmatic checks with bounded retry — every `[n]` marker is verified
- **Multi-Provider LLM**: Groq primary → Groq secondary → Gemini fallback chain
- **Web Search Fallback**: Tavily integration when corpus is insufficient
- **Abstention**: Explicit "I don't know" when evidence is lacking
- **Streaming**: SSE-based real-time token streaming
- **Full UI**: React frontend with clickable citations, drag-drop upload, and history

## Architecture

```
Question → Router → Hybrid Retriever (Dense + BM25 + RRF)
  → Cross-Encoder Re-ranker → Context Assembler
  → Synthesizer (LLM) → Citation Validator (retry loop)
  → Response Formatter → Cited Answer
```

## Quick Start

### 1. Clone & Install

```bash
cd Research_Agent

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 2. Configure API Keys

```bash
# Copy the example env file
copy .env.example .env

# Edit .env with your API keys:
# GROQ_API_KEY=your_key
# GOOGLE_API_KEY=your_key
# TAVILY_API_KEY=your_key
```

### 3. Ingest Documents

```bash
# Ingest a single file
python -m backend.cli ingest sample_docs/ai_transformers_overview.md

# Ingest a whole directory
python -m backend.cli ingest sample_docs/
```

### 4. Ask Questions (CLI)

```bash
# Ask from corpus
python -m backend.cli ask "What is the attention mechanism in transformers?"

# Ask with web search enabled
python -m backend.cli ask "What is the current price of Bitcoin?" --web
```

### 5. Start the API Server

```bash
uvicorn backend.main:app --reload --port 8000
```

API docs at: http://localhost:8000/docs

### 6. Start the Frontend (optional)

```bash
cd frontend
npm install
npm run dev
```

Frontend at: http://localhost:5173

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/ingest` | POST | Upload and index documents |
| `/api/v1/documents` | GET | List ingested documents |
| `/api/v1/ask` | POST | Ask a question (sync) |
| `/api/v1/ask/stream` | POST | Ask with streaming (SSE) |
| `/api/v1/questions` | GET | List past Q&A |
| `/api/v1/questions/{id}` | GET | Get a specific past Q&A |
| `/health` | GET | Health check |

## CLI Commands

```bash
research-agent ingest <path>     # Ingest file or directory
research-agent ask <question>    # Ask a question
research-agent documents         # List ingested docs
research-agent history           # View Q&A history
```

## Tech Stack

| Component | Technology |
|---|---|
| LLM (Primary) | Groq (llama-3.3-70b-versatile + mixtral-8x7b-32768) |
| LLM (Fallback) | Google Gemini (gemini-2.0-flash) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Store | ChromaDB (embedded, persistent) |
| Keyword Index | BM25 (rank_bm25) |
| Re-ranker | Cross-Encoder (ms-marco-MiniLM-L-6-v2) |
| Web Search | Tavily API |
| API Framework | FastAPI + SSE |
| Frontend | React + Vite |
| Storage | SQLite |
| CLI | Typer + Rich |

## Tradeoffs & Known Limitations

- **Hybrid > pure-dense**: BM25 catches exact-match terms (dates, IDs, names) that embeddings miss
- **Capped retries (max 2)**: Unbounded self-correction trades cost/latency for marginal gains
- **Single-node scope**: ChromaDB is in-process; scale needs hosted vector DB + job queue
- **OCR-quality PDFs**: Scanned documents degrade chunk quality
- **Context budget**: Very long documents may exceed the assembler's token budget

## License

MIT
