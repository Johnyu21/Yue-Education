@echo off
setlocal
set "YUE_RUN_PY="
if defined YUE_PYTHON (
  call :probe "%YUE_PYTHON%"
  if not defined YUE_RUN_PY (
    echo YUE_PYTHON 指向的 Python 不可用，需要 Python 3.12 或 3.13。
    exit /b 1
  )
  goto selected
)
if exist "%~dp0..\backend\.venv\Scripts\python.exe" call :probe "%~dp0..\backend\.venv\Scripts\python.exe"
if defined YUE_RUN_PY goto selected
py -3.12 -c "import sys; sys.exit(0 if sys.version_info[:2] in [(3,12),(3,13)] else 1)" >nul 2>nul
if not errorlevel 1 goto py12
py -3.13 -c "import sys; sys.exit(0 if sys.version_info[:2] in [(3,12),(3,13)] else 1)" >nul 2>nul
if not errorlevel 1 goto py13
for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined YUE_RUN_PY call :probe "%%P"
if defined YUE_RUN_PY goto selected
for /f "delims=" %%P in ('where python3.exe 2^>nul') do if not defined YUE_RUN_PY call :probe "%%P"
if defined YUE_RUN_PY goto selected
echo 未找到 Python 3.12 或 3.13。请先安装，并勾选 Add Python to PATH。
echo 安装后重新打开脚本；自定义安装位置可通过 YUE_PYTHON 指定 python.exe。
exit /b 1
:py12
py -3.12 "%~dp0setup_project.py" %*
exit /b %ERRORLEVEL%
:py13
py -3.13 "%~dp0setup_project.py" %*
exit /b %ERRORLEVEL%
:selected
"%YUE_RUN_PY%" "%~dp0setup_project.py" %*
exit /b %ERRORLEVEL%
:probe
"%~1" -c "import sys; sys.exit(0 if sys.version_info[:2] in [(3,12),(3,13)] else 1)" >nul 2>nul
if not errorlevel 1 set "YUE_RUN_PY=%~1"
exit /b 0
