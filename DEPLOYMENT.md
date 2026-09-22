# Deployment Guide (Render)

Deploy the Coverage Checker to Render using the included `render.yaml` blueprint.

## Prerequisites

1. GitHub repo: https://github.com/deeps45/AI-Medical-Insurance-Coverage-Checker
2. Render account: https://render.com
3. At least one LLM key:
   - **Preferred:** `TAMUS_AI_CHAT_API_KEY` from TAMU Chat API
   - Or `OPENAI_API_KEY`
4. Optional: `PINECONE_API_KEY` (otherwise keep `USE_LOCAL_VECTORSTORE=true`)

## Blueprint deploy

1. Push `main` to GitHub
2. In Render: **New + → Blueprint**
3. Connect this repository
4. Set environment variables (do not commit secrets):
   - `TAMUS_AI_CHAT_API_KEY` (or `OPENAI_API_KEY`)
   - Optional: `PINECONE_API_KEY`, `APP_API_KEY`, `ENABLE_AUTH=true`
5. Create resources and wait for the first deploy

The blueprint provisions a web service + Postgres. Local FAISS is used when Pinecone is unset; attach a persistent disk if you need FAISS to survive redeploys on Render.

## Manual web service

- Environment: Docker
- Dockerfile: root `Dockerfile` (or `backend/` + `frontend/` as separate services)
- Health check: `/` for the Streamlit image, or `/health` for the API

## Local Docker Compose (recommended for demos)

```bash
./setup.sh
# edit backend/.env
docker compose up --build
```

- UI: http://localhost:8502
- API: http://localhost:8001/docs
- Postgres host port: **5433** (avoids clashes with other local Postgres)

## Smoke checks after deploy

```bash
curl https://YOUR-SERVICE/health
BASE_URL=https://YOUR-API ./scripts/e2e_pipeline.sh /path/to/policy.pdf
```

## Notes

- This agent cannot complete a Render deploy without your Render login.
- Rotate any API keys that were pasted into chat history.
- Enable `ENABLE_AUTH=true` + `APP_API_KEY` before exposing the API publicly.
