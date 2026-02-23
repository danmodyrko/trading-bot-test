# Run Guide (Windows-first)

## Dev prerequisites
- Python 3.11+
- Node 20+

## Backend
```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set APP_API_TOKEN=dev-token
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

## Frontend
```bat
cd web
npm install
set VITE_API_URL=http://127.0.0.1:8000
set VITE_API_TOKEN=dev-token
npm run dev
```

## One-command dev launch
- `scripts\dev.bat`
- `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1`

## Production-ish local run
- Start API without `--reload`.
- Build frontend: `cd web && npm run build`.
- Serve build with any static web server (or integrated reverse proxy).

## Security
- Change `APP_API_TOKEN` from default before non-local use.
- Restrict CORS origins in `api/main.py`.
