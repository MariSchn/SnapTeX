@echo off
setlocal enabledelayedexpansion


for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0..\.env") do set "%%A=%%~B"

:: Optional CLI override for the model
if not "%~1"=="" set "MODEL_NAME=%~1"

:: Start ollama if not already running
curl -s "!API_URL:/v1=!/api/version" >nul 2>&1 || start "" ollama serve

:: Wait for ollama to be ready
:wait
curl -s "!API_URL:/v1=!/api/version" >nul 2>&1 || (timeout /t 2 /nobreak >nul & goto :wait)

:: Pull the model if needed, then run
ollama pull !MODEL_NAME! && echo. && uv run main.py

endlocal
