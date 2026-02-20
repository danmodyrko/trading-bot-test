#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 is required" >&2
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "[INFO] Creating virtual environment..."
  python3 -m venv .venv
fi

PY=.venv/bin/python
$PY -m pip install --upgrade pip >/dev/null

if command -v uv >/dev/null 2>&1; then
  echo "[INFO] Using uv workflow..."
  uv sync && uv run python -m danbot.main && exit 0
fi

echo "[INFO] uv not found; using pip fallback workflow..."
$PY -m pip install -e .
$PY -m danbot.main
