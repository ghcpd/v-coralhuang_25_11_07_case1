#!/usr/bin/env bash
set -euo pipefail

# Cross-platform helpers
PYTHON=python
VENV_DIR=.venv

$PYTHON -m venv $VENV_DIR
source $VENV_DIR/bin/activate || { echo "Activate failed - you may be on Windows Powershell. Try run_test.ps1"; exit 1; }

pip install --upgrade pip
pip install -r requirements.txt

# Run pytest with JSON result plugin
pytest -q --json-report --json-report-file=raw_results.json

# Create simple summary output.json
python summarize_results.py
