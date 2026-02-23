@echo off
setlocal

set APP_ENV=prod
if "%APP_API_TOKEN%"=="" set APP_API_TOKEN=prod-token-change-me
set APP_HOST=127.0.0.1
set APP_PORT=8000

echo ========================================
echo Trading Bot - Production Launcher
echo Host: http://%APP_HOST%:%APP_PORT%
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

echo [INFO] Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install Python dependencies.
  exit /b 1
)

if not exist web\dist (
  where npm >nul 2>nul
  if errorlevel 1 (
    echo Node.js/npm not installed.
    echo Backend started without UI.
    echo Install Node.js LTS to enable dashboard.
  ) else (
    echo [INFO] Building frontend because web\dist is missing...
    pushd web
    if exist package-lock.json (
      echo [INFO] Installing frontend dependencies with npm ci...
      call npm ci
      if errorlevel 1 (
        echo [WARN] npm ci failed. Falling back to npm install...
        call npm install
      )
    ) else (
      echo [INFO] package-lock.json missing. Installing frontend dependencies with npm install...
      call npm install
    )
    if errorlevel 1 (
      echo [WARN] npm install failed. Starting backend without UI build.
    ) else (
      call npm run build
      if errorlevel 1 echo [WARN] npm run build failed. Starting backend without fresh UI build.
    )
    popd
  )
) else (
  echo [INFO] Frontend build already present at web\dist.
)

start "" "http://127.0.0.1:8000"
echo [INFO] Starting backend server...
uvicorn api.main:app --host %APP_HOST% --port %APP_PORT%
