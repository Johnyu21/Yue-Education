@echo off
chcp 65001 >nul
setlocal
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title Yue Education - Stop
cd /d "%~dp0"
if not exist "%~dp0backend\.venv\Scripts\python.exe" (
  echo 找不到项目 Python 环境：backend\.venv\Scripts\python.exe
  pause
  exit /b 1
)
echo 正在停止粤教服务正式项目，请稍候...
"%~dp0backend\.venv\Scripts\python.exe" "%~dp0tools\local_project_runner.py" stop %*
set "YUE_EXIT=%ERRORLEVEL%"
if not "%YUE_NO_PAUSE%"=="1" pause
exit /b %YUE_EXIT%
