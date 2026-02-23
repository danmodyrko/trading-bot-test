@echo off
setlocal

set APP_ENV=dev
if "%APP_API_TOKEN%"=="" set APP_API_TOKEN=dev-token
set APP_HOST=127.0.0.1
set APP_PORT=8000

echo ========================================
echo Dev mode starting...
echo Backend:  http://%APP_HOST%:%APP_PORT%
echo Frontend: http://127.0.0.1:5173
echo ========================================

start "API" cmd /k "cd /d %~dp0.. && if not exist .venv py -m venv .venv && call .venv\Scripts\activate && pip install -r requirements.txt && uvicorn api.main:app --reload --host %APP_HOST% --port %APP_PORT%"
start "WEB" cmd /k "cd /d %~dp0..\web && npm install && set VITE_API_URL=http://%APP_HOST%:%APP_PORT% && set VITE_API_TOKEN=%APP_API_TOKEN% && npm run dev"
