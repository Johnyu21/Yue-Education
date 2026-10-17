@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Create the virtual environment and install requirements-m5.txt first.
  exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn app.m5_main:app --host 127.0.0.1 --port 8000
