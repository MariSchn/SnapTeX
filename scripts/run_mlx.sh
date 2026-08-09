#!/usr/bin/env bash
# The fastest configuration in bench/: GLM-OCR on MLX, ~0.09s per conversion.
# Apple Silicon only, and needs mlx-vlm (pip install mlx-vlm).
#
# Weights download on first run. The server is stopped again when you quit.
set -e

cd "$(dirname "$0")/.."

MODEL="${1:-mlx-community/GLM-OCR-4bit}"
PORT=8081

if ! curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null; then
    python -m mlx_vlm.server --model "$MODEL" --port "$PORT" &
    trap 'kill %1' EXIT
    until curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null; do sleep 1; done
fi

API_URL="http://127.0.0.1:$PORT/v1" MODEL_NAME="$MODEL" uv run main.py
