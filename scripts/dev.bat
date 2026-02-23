@echo off
setlocal
if "%APP_API_TOKEN%"=="" set APP_API_TOKEN=dev-token
start "API" cmd /k "cd /d %~dp0.. && if not exist .venv py -m venv .venv && call .venv\Scripts\activate && pip install -r requirements.txt && uvicorn api.main:app --reload --host 127.0.0.1 --port 8000"
start "WEB" cmd /k "cd /d %~dp0..\web && npm install && set VITE_API_URL=http://127.0.0.1:8000 && set VITE_API_TOKEN=%APP_API_TOKEN% && npm run dev"
