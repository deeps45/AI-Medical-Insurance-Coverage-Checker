#!/usr/bin/env bash
# Back-compat: local stack launcher.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "$ROOT/compose-up.sh" "$@"
