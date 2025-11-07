#!/usr/bin/env bash
set -euo pipefail

# Create venv
python -m venv .venv
. .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run pytest and capture raw results
pytest -q --tb=short --json-report --json-report-file=raw_results.json

# Summarize results to output.json
python - <<'PY'
import json
with open('raw_results.json') as f:
    r = json.load(f)
summary = {
    'total': r.get('summary', {}).get('total', 0),
    'passed': r.get('summary', {}).get('passed', 0),
    'failed': r.get('summary', {}).get('failed', 0),
}
with open('output.json','w') as o:
    json.dump({'summary': summary, 'raw': r}, o, indent=2)
print('Wrote output.json')
PY
