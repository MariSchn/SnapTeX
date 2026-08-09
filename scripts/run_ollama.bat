@echo off
setlocal enabledelayedexpansion


for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0..\.env") do set "%%A=%%~B"

:: Optional CLI override for the model
if not "%~1"=="" set "MODEL_NAME=%~1"

:: Ollama otherwise allocates the model's full advertised context - 262144 for
:: qwen3-vl, which is 24 GB of KV cache for a 3.3 GB model. A screenshot needs
:: well under 2048. Only takes effect for a server this script starts itself.
if not defined OLLAMA_CONTEXT_LENGTH set "OLLAMA_CONTEXT_LENGTH=2048"

:: Start ollama if not already running
curl -s "!API_URL:/v1=!/api/version" >nul 2>&1 || start "" ollama serve

:: Wait for ollama to be ready
:wait
curl -s "!API_URL:/v1=!/api/version" >nul 2>&1 || (timeout /t 2 /nobreak >nul & goto :wait)

:: Pull the model if needed, then run
ollama pull !MODEL_NAME! && echo. && uv run main.py

endlocal
