#!/usr/bin/env bash
# Combined backend + Streamlit (+ optional nginx) for single-container hosts.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export PYTHONPATH="${ROOT}/backend:${PYTHONPATH:-}"
export FAISS_DIR="${FAISS_DIR:-${ROOT}/data/faiss}"
mkdir -p "$FAISS_DIR"

API_PORT="${API_PORT:-8000}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"
PUBLIC_PORT="${PORT:-8080}"
USE_NGINX="${USE_NGINX:-true}"

# Streamlit → local API (same container)
export BASE_URL="${BASE_URL:-http://127.0.0.1:${API_PORT}}"
export RENDER="${RENDER:-true}"

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait || true
}
trap cleanup EXIT INT TERM

echo "Starting API on 0.0.0.0:${API_PORT}…"
(
  cd "${ROOT}/backend"
  exec uvicorn app:app --host 127.0.0.1 --port "$API_PORT"
) &
PIDS+=($!)

echo "Starting Streamlit on 127.0.0.1:${STREAMLIT_PORT}…"
(
  exec streamlit run frontend/streamlit_app.py \
    --server.port="$STREAMLIT_PORT" \
    --server.address=127.0.0.1 \
    --browser.gatherUsageStats=false \
    --server.headless=true
) &
PIDS+=($!)

for _ in $(seq 1 90); do
  if curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if [[ "$USE_NGINX" == "true" ]] && command -v nginx >/dev/null 2>&1; then
  # Rewrite listen port to match $PORT (Render injects PORT)
  conf="/tmp/nginx-coverage.conf"
  sed "s/listen 8080;/listen ${PUBLIC_PORT};/" "${ROOT}/deploy/nginx.conf" > "$conf"
  echo "Starting nginx on 0.0.0.0:${PUBLIC_PORT}…"
  exec nginx -c "$conf" -g "daemon off;"
fi

# Fallback: Streamlit is the public process (API only on localhost)
echo "nginx unavailable — exposing Streamlit on ${PUBLIC_PORT}"
kill "${PIDS[1]}" 2>/dev/null || true
exec streamlit run frontend/streamlit_app.py \
  --server.port="$PUBLIC_PORT" \
  --server.address=0.0.0.0 \
  --browser.gatherUsageStats=false \
  --server.headless=true
