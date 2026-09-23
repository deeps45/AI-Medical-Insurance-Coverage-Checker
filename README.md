# AI Medical Insurance Coverage Checker

Upload a medical insurance policy PDF and ask plain-language questions about coverage, copays, deductibles, and benefits. The app extracts text (with OCR fallback), indexes passages for semantic search, and answers with page citations.

**Repo:** https://github.com/deeps45/AI-Medical-Insurance-Coverage-Checker

## Features

- PDF text extraction via PyMuPDF, with Tesseract OCR fallback for scanned pages
- RAG Q&A with accurate per-chunk page metadata and optional document scoping
- TAMU Chat API (preferred) or OpenAI for chat + embeddings
- **Persistent per-document FAISS indexes** (survive restarts) or Pinecone in production
- **Delete / re-ingest** document APIs for clean policy management
- Optional **API key auth** (`ENABLE_AUTH` + `APP_API_KEY`) and per-client **rate limiting**
- **Streaming answers** (`/ask/stream`) and one-click **coverage summary**
- PostgreSQL (or SQLite) storage for documents and query history
- Streamlit UI with example questions, answer history, citations, and latency
- Docker Compose stack ready for local runs and Render-style deploys
- Pytest suite that runs offline without API keys (+ OCR when Tesseract is installed)

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Streamlit  │    │   FastAPI   │    │ PostgreSQL  │
│   Frontend  │◄──►│   Backend   │◄──►│  or SQLite  │
│   (8502)    │    │   (8001)    │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
     Pinecone or FAISS          TAMU Chat API
     (vector search)            or OpenAI
```

## Quick start

### Prerequisites

- Docker and Docker Compose (recommended), or Python 3.11+
- A TAMU Chat API key **or** an OpenAI API key
- Optional: Pinecone API key (otherwise set `USE_LOCAL_VECTORSTORE=true`)

### 1. Clone the repository

```bash
git clone https://github.com/deeps45/AI-Medical-Insurance-Coverage-Checker.git
cd AI-Medical-Insurance-Coverage-Checker
```

### 2. Set up environment variables

#### Option A: Setup script (recommended)

```bash
./setup.sh
# Then edit backend/.env with your API keys
nano backend/.env
```

#### Option B: Manual setup

```bash
cp backend/env.example backend/.env
```

Edit `backend/.env` and set at least one LLM key:

```env
# Preferred — TAMU Chat API (https://docs.tamus.ai)
TAMUS_AI_CHAT_API_KEY=your-tamu-key
TAMUS_AI_CHAT_API_ENDPOINT=https://chat-api.tamu.ai

# Fallback if TAMU key is unset
OPENAI_API_KEY=

# Optional managed vector DB; leave local mode on for local/dev
PINECONE_API_KEY=
PINECONE_INDEX_NAME=docsage-lite
USE_LOCAL_VECTORSTORE=true

CHAT_MODEL=protected.gemini-2.5-flash-lite
EMBEDDING_MODEL=protected.text-embedding-3-small
```

With a TAMU key the app defaults to:
- Chat: `protected.gemini-2.5-flash-lite`
- Embeddings: `protected.text-embedding-3-small`
- Endpoint: `https://chat-api.tamu.ai`

### 3. Start the application

```bash
docker compose up --build
```

- Frontend: http://localhost:8502
- Backend API docs: http://localhost:8001/docs
- Health: http://localhost:8001/health

### 4. Run tests locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
QA_MODE=extractive USE_LOCAL_VECTORSTORE=true pytest -q
```

Tests use extractive answers and an in-memory/FAISS vector store — no API keys required.

## Usage

### 1. Upload an insurance policy PDF

1. Open http://localhost:8502
2. Choose a PDF policy file
3. Click **Process PDF** to extract text and build the search index
4. Review processing stats: pages, chunks, and document ID

### 2. Ask questions

1. Once a document is loaded, type a coverage question (or click an example)
2. Get an AI answer grounded in retrieved policy text
3. See page citations / sources and response latency
4. Prior Q&A turns stay in session history

### 3. Example questions

- Is MRI covered under this policy?
- What's the copay for emergency room visits?
- What's the annual deductible?
- Are prescription drugs covered?
- What's the out-of-pocket maximum?
- Is physical therapy covered?

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + vector store / DB / LLM provider status |
| GET | `/documents` | Recent uploaded documents |
| POST | `/ingest` | Upload and index a PDF |
| PUT | `/documents/{id}/reingest` | Replace vectors for an existing document |
| DELETE | `/documents/{id}` | Delete document metadata + vectors |
| GET | `/queries` | Recent Q&A history (`document_id`, `limit`) |
| POST | `/ask/stream` | Same as `/ask` but SSE token stream |
| POST | `/summary` | One-click coverage snapshot for a document |

### Upload PDF

```bash
curl -X POST "http://localhost:8001/ingest" \
  -H "accept: application/json" \
  -F "file=@policy.pdf"
```

Response:

```json
{
  "document_id": "uuid-here",
  "pages": 15,
  "chunks": 45,
  "filename": "policy.pdf"
}
```

### Ask a question

```bash
curl -X POST "http://localhost:8001/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"Is MRI covered?","k":4,"document_id":"<id>"}'
```

Response:

```json
{
  "answer": "Yes, MRI is covered under this policy with a $50 copay... [p8]",
  "latency_ms": 1250.5,
  "sources": [
    {"page": 8, "source": "policy.pdf", "document_id": "uuid-here"},
    {"page": 9, "source": "policy.pdf", "document_id": "uuid-here"}
  ]
}
```

## Docker services

| Service | Role | Port |
|---------|------|------|
| `db` | PostgreSQL 16 | 5432 |
| `backend` | FastAPI + OCR + RAG | 8001 → 8000 |
| `frontend` | Streamlit UI | 8502 → 8501 |

## How it works

1. **PDF processing** — PyMuPDF extracts text; Tesseract OCR is used for scanned/empty pages. Text is split with a recursive character splitter (~1000 chars, 200 overlap) while preserving page numbers.
2. **Vector indexing** — Chunks are embedded (`text-embedding-3-small` via TAMU or OpenAI) and stored in Pinecone or local FAISS.
3. **Retrieval** — Top-k relevant chunks are fetched for the question, optionally filtered by `document_id`.
4. **Answer generation** — An LLM (default TAMU `gemini-2.5-flash-lite`) answers using only retrieved context and cites pages like `[p3]`.

## Database schema

### Documents

```sql
CREATE TABLE documents (
    id VARCHAR PRIMARY KEY,
    filename VARCHAR NOT NULL,
    page_count INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    status VARCHAR NOT NULL DEFAULT 'ready',
    uploaded_at TIMESTAMP NOT NULL
);
```

### Queries

```sql
CREATE TABLE queries (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR REFERENCES documents(id),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources_json TEXT,
    latency_ms FLOAT NOT NULL,
    created_at TIMESTAMP NOT NULL
);
```

## Configuration

| Variable | Purpose |
|----------|---------|
| `TAMUS_AI_CHAT_API_KEY` | Preferred LLM + embeddings via TAMU Chat API |
| `TAMUS_AI_CHAT_API_ENDPOINT` | Default `https://chat-api.tamu.ai` |
| `OPENAI_API_KEY` | Fallback if TAMU key is unset |
| `PINECONE_API_KEY` | Managed vector DB |
| `PINECONE_INDEX_NAME` | Pinecone index name |
| `USE_LOCAL_VECTORSTORE` | Prefer FAISS/memory over Pinecone |
| `FAISS_DIR` | On-disk FAISS root (default `./data/faiss`) |
| `ENABLE_AUTH` / `APP_API_KEY` | Optional API key gate (`X-API-Key` or Bearer) |
| `RATE_LIMIT_PER_MINUTE` | Per-client limit (default 60) |
| `QA_MODE=extractive` | Skip LLM chat (tests / offline demos) |
| `CHAT_MODEL` / `EMBEDDING_MODEL` | Model IDs (TAMU uses `protected.*` names) |
| `DATABASE_URL` | Postgres or SQLite connection string |

## Project layout

```
backend/          FastAPI app, services, DB models
frontend/         Streamlit UI
tests/            Pytest suite
db/               SQL notes
docker-compose.yml
render.yaml
DEPLOYMENT.md
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) and `render.yaml` for Render blueprint deployment.

Set `TAMUS_AI_CHAT_API_KEY` (or `OPENAI_API_KEY`) and optionally `PINECONE_API_KEY` / `DATABASE_URL` in the host environment.

## Troubleshooting

### Common issues

1. **Vector store / embeddings fail**
   - Confirm `TAMUS_AI_CHAT_API_KEY` or `OPENAI_API_KEY` is set in `backend/.env`
   - For local/dev without Pinecone, keep `USE_LOCAL_VECTORSTORE=true`
   - If using Pinecone, verify the index name exists and the API key is valid

2. **OCR fallback not working**
   - Verify Tesseract is installed in the backend image
   - Check `TESSERACT_CMD` (default `/usr/bin/tesseract`)

3. **Database connection issues**
   - Wait for Postgres healthcheck to pass before hitting the API
   - Confirm `DATABASE_URL` matches the Compose service (`db:5432`)

4. **Memory issues with large PDFs**
   - Increase Docker memory limits
   - Prefer text-based PDFs over huge scanned documents

### Logs

```bash
docker compose logs
docker compose logs backend
docker compose logs frontend
docker compose logs db
```

## Performance (approximate)

- Text extraction: ~1–2 seconds per page (PyMuPDF)
- OCR fallback: +2–3 seconds per empty/scanned page
- Question answering: ~1–4 seconds depending on model and retrieval
- Vector search: ~100–500ms locally; network-bound with remote APIs

## Security notes

- This is an MVP: no end-user authentication
- Never commit `backend/.env`
- Answers are assistive only — verify against your official plan documents
- API keys stay in environment variables / Docker secrets

## Production considerations

- Add authentication and user management
- Implement rate limiting
- Add monitoring and structured logging
- Use managed PostgreSQL (and Pinecone or equivalent) in production
- Consider document versioning plus backup/recovery

## License

MIT — see [LICENSE](LICENSE).

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

Please run `QA_MODE=extractive USE_LOCAL_VECTORSTORE=true pytest -q` before opening a PR.

## Support

- Open an issue on [GitHub](https://github.com/deeps45/AI-Medical-Insurance-Coverage-Checker/issues)
- Check the troubleshooting section above
- Review [DEPLOYMENT.md](DEPLOYMENT.md) for cloud setup

## Acknowledgments

- [LangChain](https://langchain.com/) for the RAG framework
- [TAMU Chat API](https://docs.tamus.ai/) / [OpenAI](https://openai.com/) for models and embeddings
- [Pinecone](https://pinecone.io/) and [FAISS](https://github.com/facebookresearch/faiss) for vector search
- [Streamlit](https://streamlit.io/) for the web interface
- [FastAPI](https://fastapi.tiangolo.com/) for the backend API
