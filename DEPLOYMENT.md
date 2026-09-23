# Deployment Guide (free hosting)

Goal: **$0 infrastructure**. The only ongoing cost should be your **LLM/embedding API**
(TAMU Chat or OpenAI).

## Cost cheat sheet

| Path | Hosting $ | Durable indexes? | Notes |
|------|-----------|------------------|-------|
| **Local Docker Compose** | $0 | Yes (local volumes) | Best free everyday use |
| **Render Free blueprint** (`render.yaml`) | $0 | No (ephemeral disk) | Public URL; sleeps when idle; free Postgres ~30 days |
| Render Starter + disk | ~$13+/mo | Yes | Only if you later want always-on |

LLM usage is billed by your API provider in all cases.

## 1. Local (recommended free path)

```bash
cp backend/env.example backend/.env
# set TAMUS_AI_CHAT_API_KEY=... (or OPENAI_API_KEY)
./compose-up.sh
```

- UI: http://localhost:8502  
- API: http://localhost:8001/docs  
- Postgres on host port **5433**; FAISS in the `faiss_data` volume  

Optional hardening still free locally:

```env
ENABLE_AUTH=true
APP_API_KEY=change-me
```

## 2. Public free URL on Render

1. Push `main`: https://github.com/deeps45/AI-Medical-Insurance-Coverage-Checker  
2. [Render](https://dashboard.render.com) → **New + → Blueprint** → this repo  
3. Confirm plans are **Free** (web + Postgres) — `render.yaml` already sets `plan: free`  
4. Set **only** secrets (no paid add-ons):
   - `TAMUS_AI_CHAT_API_KEY` **or** `OPENAI_API_KEY`
5. Deploy — do **not** attach a paid disk

### Free-tier behavior (important)

- **Cold starts:** after ~15 minutes idle the web service sleeps; first request is slow.  
- **No persistent disk:** FAISS indexes are wiped when the instance sleeps/redeploys → **re-upload the PDF** after wake.  
- **Free Postgres:** expires about **30 days** after creation unless you upgrade; upgrade within the grace window or data is deleted.  
- **Memory:** free instances are small (512MB). Prefer text PDFs over huge scans; if the service OOMs, use local Compose instead.

The API returns a clear error when a document row exists but the vector index is gone (re-upload).

After deploy:

```bash
curl https://YOUR-SERVICE.onrender.com/health
```

Open the same host in a browser for the UI. `APP_API_KEY` is auto-generated; the combined image uses it for API calls.

## Single-container image

Root `Dockerfile` + `docker-entrypoint.sh`:

1. FastAPI on `127.0.0.1:8000`  
2. Streamlit on `127.0.0.1:8501`  
3. nginx on `$PORT` (UI + `/health`, `/ask`, …)

## Smoke checks

```bash
curl -sf http://127.0.0.1:8001/health
QA_MODE=extractive USE_LOCAL_VECTORSTORE=true pytest -q
python scripts/eval_sample_policies.py --base-url http://127.0.0.1:8001
```

## Ops notes

- `POST /admin/cleanup` respects `DOCUMENT_TTL_HOURS` (free blueprint uses `48`).  
- Uploads enforce `%PDF` magic + `MAX_UPLOAD_MB` (free blueprint uses `10`).  
- Rotate keys pasted into chat.  
- Answers are assistive only — not official benefits advice.
