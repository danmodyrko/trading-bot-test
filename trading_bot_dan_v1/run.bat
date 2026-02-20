@echo off
setlocal
where python >nul 2>nul || (echo Python 3.11+ required & exit /b 1)
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo Installing uv...
  python -m pip install --user uv
)
uv sync
uv run python -m danbot.main
