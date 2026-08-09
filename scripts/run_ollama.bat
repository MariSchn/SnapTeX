@echo off
:: Start Ollama if it isn't running, make sure the model is downloaded, run SnapTeX.
:: Pass a model name to override MODEL_NAME from .env for this run.
cd /d "%~dp0.."

for /f "usebackq tokens=1,* delims==" %%A in (".env") do set "%%A=%%~B"

if not "%~1"=="" set "MODEL_NAME=%~1"

ollama list >nul 2>&1 && goto :ready
start "" ollama serve
:wait
timeout /t 1 /nobreak >nul
ollama list >nul 2>&1 || goto :wait
:ready

ollama pull %MODEL_NAME%
uv run main.py
