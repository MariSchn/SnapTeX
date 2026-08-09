@echo off
:: Same as run_ollama.bat, but with the settings the benchmark in bench/ picked:
:: glm-ocr:q8_0, and a context small enough that the model sits in ~1.2 GB
:: instead of the 18 GB Ollama allocates when you don't tell it otherwise.
::
:: OLLAMA_CONTEXT_LENGTH only applies to a server this script starts itself, so
:: if Ollama is already running you get the model but not the memory saving.
cd /d "%~dp0.."

for /f "usebackq tokens=1,* delims==" %%A in (".env") do set "%%A=%%~B"

set "MODEL_NAME=glm-ocr:q8_0"
if not "%~1"=="" set "MODEL_NAME=%~1"
set "OLLAMA_CONTEXT_LENGTH=2048"

ollama list >nul 2>&1 && goto :running
start "" ollama serve
:wait
timeout /t 1 /nobreak >nul
ollama list >nul 2>&1 || goto :wait
goto :ready

:running
echo Ollama is already running, so it keeps whatever context length it
echo started with. Restart it with OLLAMA_CONTEXT_LENGTH=2048 to get the
echo smaller footprint.

:ready
ollama pull %MODEL_NAME%
uv run main.py
