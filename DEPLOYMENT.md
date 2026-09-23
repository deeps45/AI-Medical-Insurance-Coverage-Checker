# Deployment Guide

Deploy the Coverage Checker with Docker Compose (local/demo) or Render (public).

## What this agent can / cannot do

| Step | Status |
|------|--------|
| Repo deploy configs (`Dockerfile`, `render.yaml`, nginx entrypoint, FAISS disk) | Done in-repo |
| Click **Deploy** on Render / pay for a plan | **You** — needs your Render login |
| Set `TAMUS_AI_CHAT_API_KEY` (or OpenAI) in the host | **You** — secrets stay out of git |

## Local demo (recommended)

```bash
cp backend/env.example backend/.env
# edit keys in backend/.env
./compose-up.sh
# or: docker compose up --build
```

- UI: http://localhost:8502  
- API: http://localhost:8001/docs · health: http://localhost:8001/health  
- Postgres host port: **5433**

Production-ish local flags:

```env
ENABLE_AUTH=true
APP_API_KEY=change-me
RATE_LIMIT_PER_MINUTE=45
INGEST_RATE_LIMIT_PER_MINUTE=10
MAX_UPLOAD_MB=20
DOCUMENT_TTL_HOURS=168
```

## Render blueprint (public demo)

1. Push `main` to GitHub: https://github.com/deeps45/AI-Medical-Insurance-Coverage-Checker  
2. Render → **New + → Blueprint** → connect this repo (`render.yaml`)  
3. Set secrets in the dashboard (do not commit them):
   - `TAMUS_AI_CHAT_API_KEY` (preferred) **or** `OPENAI_API_KEY`
   - Confirm `APP_API_KEY` (auto-generated) and `ENABLE_AUTH=true`
4. Deploy. The blueprint creates:
   - Web service (nginx → Streamlit UI + FastAPI `/health`, `/ask`, …)
   - Postgres
   - 1GB disk at `/app/data/faiss` so indexes survive redeploys

After deploy:

```bash
curl https://YOUR-SERVICE.onrender.com/health
# UI opens at the same host; set APP_API_KEY in the Streamlit service env if split
```

Pass the API key from the Streamlit container via `APP_API_KEY` (already wired in compose / combined image).

## Single-container image

Root `Dockerfile` runs:

1. FastAPI on `127.0.0.1:8000`  
2. Streamlit on `127.0.0.1:8501`  
3. nginx on `$PORT` routing API paths + UI  

Entrypoint: `docker-entrypoint.sh`. Local multi-service stack still uses `docker-compose.yml`.

## Smoke checks

```bash
curl -sf http://127.0.0.1:8001/health
QA_MODE=extractive USE_LOCAL_VECTORSTORE=true pytest -q
python scripts/eval_sample_policies.py --base-url http://127.0.0.1:8001
```

## Ops notes

- `POST /admin/cleanup` removes documents older than `DOCUMENT_TTL_HOURS` (also runs on API startup).  
- Uploads reject non-PDF magic bytes and oversized files (`MAX_UPLOAD_MB`).  
- Rotate any keys that were pasted into chat.  
- Answers are assistive only — not official benefits advice.
