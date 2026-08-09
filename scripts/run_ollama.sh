#!/usr/bin/env bash
# Start Ollama if it isn't running, make sure the model is downloaded, run SnapTeX.
# Pass a model name to override MODEL_NAME from .env for this run.
set -e

cd "$(dirname "$0")/.."
source .env

MODEL="${1:-$MODEL_NAME}"

if ! ollama list >/dev/null 2>&1; then
    ollama serve &
    until ollama list >/dev/null 2>&1; do sleep 1; done
fi

ollama pull "$MODEL"
MODEL_NAME="$MODEL" uv run main.py
