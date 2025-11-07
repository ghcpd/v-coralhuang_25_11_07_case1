#!/usr/bin/env bash
set -e

python -m venv venv
# Activate for posix-like systems
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
fi

pip install --upgrade pip
pip install -r requirements.txt

# Run pytest with JSON report plugin
pytest -q --json-report --json-report-file=raw_results.json

# Create summarized output
python summarize.py

echo "Tests completed. Raw results in raw_results.json, summary in output.json"
