@echo off
setlocal

if "%APP_API_TOKEN%"=="" set APP_API_TOKEN=dev-token
set APP_HOST=127.0.0.1
set APP_PORT=8000

cd /d %~dp0..
if not exist .venv py -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt || exit /b 1

echo API: http://%APP_HOST%:%APP_PORT%
echo WS : ws://%APP_HOST%:%APP_PORT%/ws/events?token=%APP_API_TOKEN%
start "API" cmd /k "cd /d %~dp0.. && call .venv\Scripts\activate && set APP_ENV=dev && uvicorn api.main:app --reload --host %APP_HOST% --port %APP_PORT%"

where npm >nul 2>nul
if errorlevel 1 (
  echo [WARN] npm not found. Frontend dev server skipped.
) else (
  echo WEB: http://127.0.0.1:5173
  start "WEB" cmd /k "cd /d %~dp0..\web && set VITE_API_URL=http://%APP_HOST%:%APP_PORT% && set VITE_API_TOKEN=%APP_API_TOKEN% && npm install && npm run dev"
)
