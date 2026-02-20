@echo off
setlocal EnableExtensions EnableDelayedExpansion

where python >nul 2>nul || (
  echo [ERROR] Python 3.11+ is required and was not found in PATH.
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo [INFO] Creating virtual environment...
  python -m venv .venv || exit /b 1
)

set "PY=.venv\Scripts\python.exe"
%PY% -m pip install --upgrade pip >nul

set "UV_CMD="
where uv >nul 2>nul && set "UV_CMD=uv"

if not defined UV_CMD (
  echo [INFO] uv not found in PATH. Trying to install into venv...
  %PY% -m pip install uv >nul 2>nul
  if exist .venv\Scripts\uv.exe set "UV_CMD=.venv\Scripts\uv.exe"
)

if defined UV_CMD (
  echo [INFO] Using uv workflow...
  %UV_CMD% sync && %UV_CMD% run python -m danbot.main && exit /b 0
  echo [WARN] uv workflow failed, falling back to pip.
)

echo [INFO] Using pip fallback workflow...
%PY% -m pip install -e . || exit /b 1
%PY% -m danbot.main
