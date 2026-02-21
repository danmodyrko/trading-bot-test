@echo off
setlocal

where python >nul 2>nul || (echo Python 3.11+ required & exit /b 1)

if not exist .venv (
  python -m venv .venv || exit /b 1
)

call .venv\Scripts\activate.bat || exit /b 1
python -m pip install --upgrade pip || exit /b 1
pip install -r requirements.txt || exit /b 1
python -m danbot.main
