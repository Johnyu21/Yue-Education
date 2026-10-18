@echo off
chcp 65001 >nul
setlocal
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title Yue Education - start
cd /d "%~dp0"
if not exist "%~dp0tools\project_entry.cmd" (
  echo 缺少 tools\project_entry.cmd，请重新拉取完整仓库。
  if not "%YUE_NO_PAUSE%"=="1" pause
  exit /b 1
)
echo 正在启动粤教项目，请稍候...
call "%~dp0tools\project_entry.cmd" start %*
set "YUE_EXIT=%ERRORLEVEL%"
if not "%YUE_NO_PAUSE%"=="1" pause
exit /b %YUE_EXIT%
