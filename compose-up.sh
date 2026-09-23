#!/usr/bin/env bash
# Local multi-container stack (Postgres + API + Streamlit).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
docker compose up --build "$@"
