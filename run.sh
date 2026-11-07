#!/usr/bin/env bash
# Runs Hominfer from this checkout in the foreground: http://127.0.0.1:8090
# (HOMINFER_HOST=0.0.0.0 to reach it from the LAN).
# Creates its venv on first run, then keeps it in sync with pyproject.toml.
# Ctrl+C stops the launcher AND the models it started.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
[ -x venv-hominfer/bin/python ] || uv venv -q --python 3.12 venv-hominfer
uv pip install -q --python venv-hominfer/bin/python -e ".[dev]"
exec venv-hominfer/bin/python -m hominfer
