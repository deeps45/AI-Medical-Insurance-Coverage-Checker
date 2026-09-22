#!/usr/bin/env bash
# End-to-end API pipeline against a running backend (default localhost:8001)
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8001}"
API_KEY="${APP_API_KEY:-}"
CURL_AUTH=()
if [[ -n "$API_KEY" ]]; then
  CURL_AUTH=(-H "X-API-Key: ${API_KEY}")
fi

echo "== health =="
curl -sS "${BASE_URL}/health" | python3 -m json.tool

PDF="${1:-}"
if [[ -z "$PDF" ]]; then
  echo "Usage: $0 /path/to/policy.pdf" >&2
  exit 1
fi

echo "== ingest =="
INGEST=$(curl -sS ${CURL_AUTH[@]+"${CURL_AUTH[@]}"} -F "file=@${PDF}" "${BASE_URL}/ingest")
echo "$INGEST" | python3 -m json.tool
DOC_ID=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['document_id'])" "$INGEST")

echo "== summary =="
curl -sS ${CURL_AUTH[@]+"${CURL_AUTH[@]}"} -H 'Content-Type: application/json' \
  -d "{\"document_id\":\"${DOC_ID}\",\"k\":8}" \
  "${BASE_URL}/summary" | python3 -m json.tool

echo "== ask =="
curl -sS ${CURL_AUTH[@]+"${CURL_AUTH[@]}"} -H 'Content-Type: application/json' \
  -d "{\"question\":\"Is MRI covered and what is the copay?\",\"document_id\":\"${DOC_ID}\",\"k\":4}" \
  "${BASE_URL}/ask" | python3 -m json.tool

echo "== ask/stream (first events) =="
set +o pipefail
curl -sS -N ${CURL_AUTH[@]+"${CURL_AUTH[@]}"} -H 'Content-Type: application/json' \
  -d "{\"question\":\"What is the annual deductible?\",\"document_id\":\"${DOC_ID}\",\"k\":3}" \
  "${BASE_URL}/ask/stream" | head -n 8
set -o pipefail

echo
echo "E2E_PIPELINE_OK doc_id=${DOC_ID}"
