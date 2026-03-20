#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load .env file
set -a
source "$SCRIPT_DIR/../.env"
set +a

API_VERSION_URL="${API_URL%/v1}/api/version"

# Start ollama if not already running
curl -s "$API_VERSION_URL" >/dev/null 2>&1 || ollama serve &

# Wait for ollama to be ready
until curl -s "$API_VERSION_URL" >/dev/null 2>&1; do
    sleep 2
done

# Pull the model if needed, then run
ollama pull "$MODEL_NAME"
uv run main.py
