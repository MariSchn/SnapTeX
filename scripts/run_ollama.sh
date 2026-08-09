#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load .env file
set -a
source "$SCRIPT_DIR/../.env"
set +a

# Optional CLI override for the model
if [ $# -gt 0 ]; then
    export MODEL_NAME="$1"
fi

API_VERSION_URL="${API_URL%/v1}/api/version"

# Ollama otherwise allocates the model's full advertised context - 262144 for
# qwen3-vl, which is 24 GB of KV cache for a 3.3 GB model. A screenshot needs
# well under 2048. Only takes effect for a server this script starts itself;
# if you run ollama as a background service, set it there instead.
export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-2048}"

# Start ollama if not already running
if curl -s "$API_VERSION_URL" >/dev/null 2>&1; then
    echo "[SnapTeX] Using the ollama server that is already running."
    echo "[SnapTeX] For the smallest memory footprint, make sure it was started"
    echo "[SnapTeX] with OLLAMA_CONTEXT_LENGTH=$OLLAMA_CONTEXT_LENGTH."
else
    ollama serve &
fi

# Wait for ollama to be ready
until curl -s "$API_VERSION_URL" >/dev/null 2>&1; do
    sleep 2
done

# Pull the model if needed, then run
ollama pull "$MODEL_NAME"
uv run main.py
