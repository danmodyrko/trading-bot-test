# Verification

## Commands

1. Syntax check backend modules:
```bash
python -m py_compile engine/*.py api/*.py scripts/smoke_test.py
```
Expected: no output, zero exit code.

2. Install dependencies:
```bash
python -m pip install -r requirements.txt
```
Expected: all packages installed. In restricted environments this can fail due to network/proxy rules.

3. Backend run:
```bash
set APP_API_TOKEN=dev-token
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```
Expected: API starts, REST and WS available.

4. Smoke test:
```bash
python scripts/smoke_test.py
```
Expected: prints `status`, `settings mode`, and first WS frames including snapshot/event/status/ping.

5. Frontend run:
```bash
cd web
npm install
npm run dev
```
Expected: dashboard loads at Vite URL and displays live feed/events.
