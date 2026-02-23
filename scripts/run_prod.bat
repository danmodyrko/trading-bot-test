@echo off
setlocal

set APP_ENV=prod
if "%APP_API_TOKEN%"=="" set APP_API_TOKEN=prod-token-change-me
set APP_HOST=127.0.0.1
set APP_PORT=8000

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm is not available in PATH.
  echo [ERROR] Install Node.js LTS: https://nodejs.org/
  echo [ERROR] If Node.js is already installed, reopen terminal and run again.
  exit /b 1
)

echo ========================================
echo Production mode starting...
echo UI + API: http://%APP_HOST%:%APP_PORT%
echo ========================================

cd /d %~dp0..\web
call npm ci
if errorlevel 1 exit /b 1
call npm run build
if errorlevel 1 exit /b 1

cd /d %~dp0..
if not exist .venv py -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
python run.py
