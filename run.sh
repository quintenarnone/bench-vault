#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m venv .venv 2>/dev/null || true
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m benchvault.app
