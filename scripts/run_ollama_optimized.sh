#!/usr/bin/env bash
# Same as run_ollama.sh, but with the settings the benchmark in bench/ picked:
# glm-ocr:q8_0, and a context small enough that the model sits in ~1.2 GB
# instead of the 18 GB Ollama allocates when you don't tell it otherwise.
#
# OLLAMA_CONTEXT_LENGTH only applies to a server this script starts itself, so
# if Ollama is already running you get the model but not the memory saving.
set -e

cd "$(dirname "$0")/.."
source .env

MODEL="${1:-glm-ocr:q8_0}"
export OLLAMA_CONTEXT_LENGTH=2048

if ollama list >/dev/null 2>&1; then
    echo "Ollama is already running, so it keeps whatever context length it"
    echo "started with. Restart it with OLLAMA_CONTEXT_LENGTH=2048 to get the"
    echo "smaller footprint."
else
    ollama serve &
    until ollama list >/dev/null 2>&1; do sleep 1; done
fi

ollama pull "$MODEL"
MODEL_NAME="$MODEL" uv run main.py
