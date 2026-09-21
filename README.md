# AI Medical Insurance Coverage Checker

Upload a medical insurance policy PDF and ask plain-language questions about coverage, copays, deductibles, and benefits. The app extracts text (with OCR fallback), indexes passages for semantic search, and answers with page citations.

## Features

- PDF text extraction via PyMuPDF, with Tesseract OCR fallback for scanned pages
- RAG Q&A with accurate per-chunk page metadata and optional document scoping
- Pinecone vector search in production, or local FAISS / in-memory store for development and tests
- PostgreSQL (or SQLite) storage for documents and query history
- Streamlit UI with example questions and answer history
- Docker Compose stack ready for local runs and Render-style deploys

## Architecture

```
Streamlit (8502)  →  FastAPI (8001)  →  PostgreSQL
                          ↓
                   Pinecone or FAISS
                          ↓
                        OpenAI
```

## Quick start

### Prerequisites

- Docker and Docker Compose (recommended), or Python 3.11+
- OpenAI API key (for embeddings + answers in full mode)
- Optional: Pinecone API key (otherwise set `USE_LOCAL_VECTORSTORE=true`)

### 1. Configure environment

```bash
cp backend/env.example backend/.env
# Edit backend/.env and set:
#   TAMUS_AI_CHAT_API_KEY=...   (preferred — TAMU Chat API)
# or OPENAI_API_KEY=...
```

With a TAMU key the app defaults to:
- Chat: `protected.gemini-2.5-flash-lite`
- Embeddings: `protected.text-embedding-3-small`
- Endpoint: `https://chat-api.tamu.ai`

For local development without Pinecone, keep:

```env
USE_LOCAL_VECTORSTORE=true
```

### 2. Run with Docker

```bash
docker compose up --build
```

- Frontend: http://localhost:8502
- Backend API docs: http://localhost:8001/docs
- Health: http://localhost:8001/health

### 3. Run tests locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
QA_MODE=extractive USE_LOCAL_VECTORSTORE=true pytest -q
```

Tests use extractive answers and an in-memory/FAISS vector store — no API keys required.

## Usage

1. Open the Streamlit UI and upload a policy PDF
2. Click **Process PDF**
3. Ask questions such as:
   - Is MRI covered under this policy?
   - What's the copay for emergency room visits?
   - What's the annual deductible?
   - Are prescription drugs covered?

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + vector store / DB status |
| GET | `/documents` | Recent uploaded documents |
| POST | `/ingest` | Upload and index a PDF |
| POST | `/ask` | Ask a question (`question`, optional `k`, optional `document_id`) |

### Example

```bash
curl -X POST "http://localhost:8001/ingest" \
  -F "file=@policy.pdf"

curl -X POST "http://localhost:8001/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"Is MRI covered?","k":4,"document_id":"<id>"}'
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
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) and `render.yaml` for Render blueprint deployment. Set `OPENAI_API_KEY` and optionally `PINECONE_API_KEY` in the host environment.

## Security notes

- This is an MVP: no end-user auth
- Never commit `backend/.env`
- Answers are assistive only — verify against your official plan documents

## License

MIT — see [LICENSE](LICENSE).
