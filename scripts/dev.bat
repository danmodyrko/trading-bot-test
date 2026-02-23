@echo off
setlocal

set APP_ENV=dev
if "%APP_API_TOKEN%"=="" set APP_API_TOKEN=dev-token
set APP_HOST=127.0.0.1
set APP_PORT=8000

echo ========================================
echo Trading Bot - Development Launcher
echo Backend:  http://%APP_HOST%:%APP_PORT%
echo WebSocket: ws://%APP_HOST%:%APP_PORT%/ws/events
echo ========================================

cd /d %~dp0..

if not exist .venv (
  echo [INFO] Creating virtual environment...
  py -m venv .venv
)

call .venv\Scripts\activate
if errorlevel 1 (
  echo [ERROR] Could not activate virtual environment.
  exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install Python dependencies.
  exit /b 1
)

start "API" cmd /k "cd /d %~dp0.. && call .venv\Scripts\activate && set APP_ENV=dev && uvicorn api.main:app --reload --host %APP_HOST% --port %APP_PORT%"

where npm >nul 2>nul
if errorlevel 1 (
  echo [WARN] npm not found. Skipping Vite dev server.
  echo [WARN] Install Node.js LTS for frontend hot-reload.
) else (
  echo [INFO] Starting Vite dev server at http://127.0.0.1:5173
  start "WEB" cmd /k "cd /d %~dp0..\web && set VITE_API_URL=http://%APP_HOST%:%APP_PORT% && set VITE_API_TOKEN=%APP_API_TOKEN% && npm install && npm run dev"
)
