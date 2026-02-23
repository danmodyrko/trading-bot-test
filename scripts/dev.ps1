$root = Split-Path $PSScriptRoot -Parent
if (-not $env:APP_API_TOKEN) { $env:APP_API_TOKEN = "dev-token" }
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; if (-not (Test-Path .venv)) { py -m venv .venv }; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; uvicorn api.main:app --reload --host 127.0.0.1 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\web'; npm install; $env:VITE_API_URL='http://127.0.0.1:8000'; $env:VITE_API_TOKEN='$env:APP_API_TOKEN'; npm run dev"
