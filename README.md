# SnapTeX

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

Screenshot to LaTeX converter powered by Vision-Language Models. Press a hotkey, and SnapTeX converts the image in your clipboard to a LaTeX string and copies it back, ready to paste.


## Features

- **Hotkey-triggered** — capture a screenshot, press a key, get LaTeX
- **Clipboard integration** — reads images and writes LaTeX, no file juggling
- **Any OpenAI-compatible API** — works with [Ollama](https://ollama.com), [OpenAI](https://platform.openai.com), [OpenRouter](https://openrouter.ai), and more
- **Configurable shortcuts** — register one or multiple hotkeys
- **Lightweight** — runs quietly in the background with no GUI

## How It Works

1. Take a screenshot of an equation (e.g. with Snipping Tool or `Win+Shift+S`).
2. Press **Ctrl+Alt+L** (configurable).
3. SnapTeX sends the clipboard image to a VLM and copies the resulting LaTeX to your clipboard.

## Setup

### Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Ollama](https://ollama.com/download) or any other OpenAI-compatible API

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/MariSchn/SnapTeX
   cd SnapTeX
   ```

2. Copy the example environment file and configure it:

   ```bash
   cp .env.example .env
   ```

3. Edit `.env` with your settings (see [Configuration](#configuration) for details).

## Usage

### Quick Start (with Ollama)

The `scripts/` directory provides convenience scripts that start Ollama, pull the model, and launch SnapTeX in one step:

```bash
.\scripts\run_ollama.bat  # Windows
./scripts/run_ollama.sh   # Linux / macOS
```

Pass a model name as the first argument to override `MODEL_NAME` from `.env` for that run:

```bash
./scripts/run_ollama.sh qwen3-vl:8b-instruct
```

### Manual Start

1. Start your preferred OpenAI-compatible API server (skip if using a cloud API).
2. Launch SnapTeX:

   ```bash
   uv run main.py
   ```

3. Press your configured hotkey with an image in the clipboard.

## Configuration

All configuration is done through the `.env` file:

| Variable     | Description                         | Default                          |
| ------------ | ----------------------------------- | -------------------------------- |
| `API_URL`    | OpenAI-compatible API endpoint      | `http://localhost:11434/v1`      |
| `API_KEY`    | API key for the endpoint            | `ollama`                         |
| `MODEL_NAME` | VLM model to use                    | [`glm-ocr:q8_0`](https://ollama.com/library/glm-ocr) |
| `SHORTCUTS`  | Comma-separated hotkeys to register | `ctrl+alt+l`                     |
| `MAX_TOKENS` | Upper bound on the reply            | `256`                            |

### Example: Using Ollama (local)

```env
API_URL="http://127.0.0.1:11434/v1"
API_KEY="ollama"
MODEL_NAME="glm-ocr:q8_0"
SHORTCUTS="ctrl+alt+l"
```

### Example: Using OpenAI API

```env
API_URL="https://api.openai.com/v1"
API_KEY="sk-..."
MODEL_NAME="gpt-5"
SHORTCUTS="ctrl+alt+l"
```

## Choosing a model

The default is `glm-ocr:q8_0`, which converts a typical equation in **0.17s**
and holds **1.2 GB** of memory. If you want a general-purpose VLM rather than
an OCR model, `qwen3-vl:2b-instruct` is the most accurate thing tested, at
about four times the latency.

Everything below was measured with the benchmark in [`bench/`](bench) — 40
equations across three difficulty tiers, rendered by real LaTeX at five
different resolutions and colour schemes, scored by normalised token edit
distance against the source. See [`bench/README.md`](bench/README.md) for what
the score actually means and how to add your own model.

**Hardware:** Apple M5 Max, 128 GB unified memory, macOS 26.5. Ollama 0.32.6,
mlx-vlm 0.6.10. Latency is end-to-end, one request at a time, measured client
side with a cold image cache. RAM is what `ollama ps` reports resident at
`num_ctx=8192`.

### Models

| Model | Engine | RAM | p50 | p95 | Score | Exact |
| --- | --- | --- | --- | --- | --- | --- |
| [`GLM-OCR-4bit`](https://hf.co/mlx-community/GLM-OCR-4bit) | MLX | 1.5 GB | **0.09s** | 0.16s | 0.983 | 92% |
| [`glm-ocr:q8_0`](https://ollama.com/library/glm-ocr) | Ollama | 1.5 GB | **0.17s** | 0.30s | 0.976 | 88% |
| [`ministral-3:3b`](https://ollama.com/library/ministral-3) | Ollama | 2.9 GB | 0.38s | 0.62s | 0.944 | 68% |
| [`qwen3.5:2b`](https://ollama.com/library/qwen3.5) | Ollama | 2.4 GB | 0.47s | 0.75s | 0.937 | 70% |
| [`gemma4:e2b-it-qat`](https://ollama.com/library/gemma4) | Ollama | 3.7 GB | 0.51s | 0.69s | 0.961 | 68% |
| [`gemma4:e4b-it-qat`](https://ollama.com/library/gemma4) | Ollama | 5.5 GB | 0.66s | 1.05s | 0.984 | 85% |
| [`qwen3-vl:2b-instruct`](https://ollama.com/library/qwen3-vl) | Ollama | 2.1 GB | 0.68s | 0.87s | **0.989** | 90% |
| [`qwen3-vl:4b-instruct`](https://ollama.com/library/qwen3-vl) | Ollama | 3.7 GB | 1.07s | 1.47s | 0.978 | 85% |
| [`qwen3-vl:8b-instruct`](https://ollama.com/library/qwen3-vl) | Ollama | 6.0 GB | 1.58s | 2.07s | 0.987 | 88% |
| [`qwen3.5:9b`](https://ollama.com/library/qwen3.5) | Ollama | 5.6 GB | 0.92s | 1.58s | 0.929 | 55% |
| [`deepseek-ocr:3b`](https://ollama.com/library/deepseek-ocr) | Ollama | 7.2 GB | 0.59s | 1.66s | 0.793 | 48% |

Scaling a family up doesn't help: Qwen3-VL 2B beats both its 4B and 8B siblings
while being 2.3x faster than the 8B, and the same holds for Qwen3.5 and
Ministral. Whatever these models are missing on hard equations, it isn't
parameters.

`deepseek-ocr:3b` is included for completeness — it's built for whole-page
documents and answers a crop of a single equation with a full `\documentclass`
preamble, prose, or occasionally a description of what it sees.

### What actually moved the needle

| Change | Effect |
| --- | --- |
| Stop sequences | **1.9s → 0.17s** on glm-ocr |
| `num_ctx=2048` instead of the default | **18 GB → 1.7 GB** resident, no latency change |
| MLX instead of Ollama, same model | **0.17s → 0.09s** |
| Quantization (Q4_K_M vs Q8_0 vs BF16) | ~15% latency, ≤0.4 points of accuracy |
| Prompt wording | nothing (0.976–0.989, all within noise of each other) |
| `OLLAMA_FLASH_ATTENTION`, `OLLAMA_KV_CACHE_TYPE=q8_0` | nothing measurable at this context size |
| Client-side image downscaling | nothing on Ollama — see below |

Two of these are worth explaining.

**Stop sequences.** Page-OCR models transcribe the equation correctly on the
first line and then keep re-emitting it in fenced blocks until they hit the
token cap. `glm-ocr` scored 0.23 before this and 0.98 after, and got 11x
faster. `MAX_TOKENS` alone doesn't fix it — it just caps the waste.

**Context length.** Ollama allocates the model's full advertised context unless
you tell it not to. For Qwen3-VL that's 262144 tokens, or **24 GB of KV cache
for a 3.3 GB model**. A screenshot needs under 2048. The launcher scripts set
`OLLAMA_CONTEXT_LENGTH=2048`; if you run Ollama as a background service, set it
there instead.

### Ollama vs MLX

MLX is roughly twice as fast on the same weights, and the reason is image
handling rather than raw compute. Ollama resizes every image to a fixed grid —
a 300x60 screenshot and a 1024x400 one both cost ~1080 visual tokens, and
downscaling before sending changes nothing. mlx-vlm honours the model's real
dynamic-resolution config, so that same screenshot costs 95–170 tokens.

There is no way to control this from Ollama: no request parameter, no
environment variable, and although the GGUF carries the right `shortest_edge` /
`longest_edge` metadata, Ollama doesn't apply it. The equivalent request for
Gemma 4 is [ollama/ollama#15626](https://github.com/ollama/ollama/issues/15626),
still open.

The practical consequence is that on Ollama, **image cost is a property of the
model you pick**, and it varies by more than 10x:

| Model | Visual tokens | Prefill |
| --- | --- | --- |
| `gemma4:e2b-it-qat` | 87 | 0.12s |
| `qwen3.5:2b` | 122 | 0.07s |
| `glm-ocr:q8_0` | 149 | 0.04s |
| `ministral-3:3b` | 698 | 0.11s |
| `qwen3-vl:2b-instruct` | 1091 | 0.44s |

Note this is prefill only — `gemma4:e4b` spends 12x fewer tokens on the image
than `qwen3-vl:2b` and still ends up at the same total latency, because it
gives the time back on decode.

If you want the MLX numbers, serve the model yourself and point `API_URL` at
it — SnapTeX only needs an OpenAI-compatible endpoint:

```bash
pip install mlx-vlm
python -m mlx_vlm.server --model mlx-community/GLM-OCR-4bit --port 8081
```

```env
API_URL="http://127.0.0.1:8081/v1"
MODEL_NAME="mlx-community/GLM-OCR-4bit"
```

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).
