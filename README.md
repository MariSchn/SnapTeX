# SnapTeX

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

Screenshot to LaTeX converter powered by vision LLMs. Press a hotkey, and SnapTeX converts the image in your clipboard to a LaTeX string and copies it back, ready to paste.


## Features

- **Hotkey-triggered** — capture a screenshot, press a key, get LaTeX
- **Clipboard integration** — reads images and writes LaTeX, no file juggling
- **Any OpenAI-compatible API** — works with [Ollama](https://ollama.com), [OpenAI](https://platform.openai.com), [OpenRouter](https://openrouter.ai), and more
- **Configurable shortcuts** — register one or multiple hotkeys
- **Lightweight** — runs quietly in the background with no GUI

## How It Works

1. Take a screenshot of an equation (e.g. with Snipping Tool or `Win+Shift+S`).
2. Press **Ctrl+Alt+L** (configurable).
3. SnapTeX sends the clipboard image to a vision model and copies the resulting LaTeX to your clipboard.

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
| `MODEL_NAME` | Vision model to use                 | [`qwen3-vl:2b-instruct`](https://ollama.com/library/qwen3-vl:2b-instruct) |
| `SHORTCUTS`  | Comma-separated hotkeys to register | `ctrl+alt+l`                     |

### Example: Using Ollama (local)

```env
API_URL="http://127.0.0.1:11434/v1"
API_KEY="ollama"
MODEL_NAME="qwen3-vl:2b-instruct"
SHORTCUTS="ctrl+alt+l"
```

### Example: Using OpenAI API

```env
API_URL="https://api.openai.com/v1"
API_KEY="sk-..."
MODEL_NAME="gpt-5"
SHORTCUTS="ctrl+alt+l"
```

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).
