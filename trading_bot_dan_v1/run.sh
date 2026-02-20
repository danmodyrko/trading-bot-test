#!/usr/bin/env bash
set -euo pipefail
python3 --version
if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip install --user uv
fi
uv sync
uv run python -m danbot.main
