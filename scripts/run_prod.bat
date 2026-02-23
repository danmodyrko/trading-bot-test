@echo off
setlocal

set APP_ENV=prod
if "%APP_API_TOKEN%"=="" set APP_API_TOKEN=prod-token-change-me
set APP_HOST=127.0.0.1
set APP_PORT=8000

echo ========================================
echo Production mode starting...
echo UI + API: http://%APP_HOST%:%APP_PORT%
echo ========================================

cd /d %~dp0..\web
call npm ci
call npm run build

cd /d %~dp0..
if not exist .venv py -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
python run.py
