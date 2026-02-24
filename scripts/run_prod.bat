@echo off
setlocal

set APP_ENV=prod
if "%APP_API_TOKEN%"=="" (
  set APP_API_TOKEN=change-me-token
  echo [WARN] APP_API_TOKEN was not set. Using temporary token: change-me-token
  echo [WARN] Set APP_API_TOKEN before running for secure usage.
)
set APP_HOST=127.0.0.1
set APP_PORT=8000

cd /d %~dp0..
if not exist .venv py -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt || exit /b 1

where npm >nul 2>nul
if errorlevel 1 (
  echo [WARN] npm not found. Skipping frontend build and starting backend only.
) else (
  pushd web
  call npm install
  if errorlevel 1 (
    echo [WARN] npm install failed. Continuing backend only.
  ) else (
    call npm run build
    if errorlevel 1 echo [WARN] npm run build failed. Continuing backend only.
  )
  popd
)

start "" "http://127.0.0.1:8000"
uvicorn api.main:app --host %APP_HOST% --port %APP_PORT%
