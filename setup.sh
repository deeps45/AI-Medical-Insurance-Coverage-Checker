#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/backend/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT/backend/env.example" "$ENV_FILE"
  echo "Created backend/.env from env.example — add your API keys."
else
  echo "backend/.env already exists."
fi

echo "Next: edit backend/.env, then run: docker compose up --build"
