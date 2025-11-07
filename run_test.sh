#!/usr/bin/env bash
set -euo pipefail

# Simple test runner script (POSIX). On Windows, you can run the commands manually
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Run pytest and create a JSON report
pytest -q --json-report --json-report-file=raw_results.json

# Summarize results into output.json
python - <<'PY'
import json, sys
with open('raw_results.json') as f:
    r=json.load(f)
summary={
  'passed': r.get('summary',{}).get('passed',0),
  'failed': r.get('summary',{}).get('failed',0),
  'skipped': r.get('summary',{}).get('skipped',0),
  'duration': r.get('duration',0)
}
with open('output.json','w') as f:
    json.dump({'summary': summary, 'raw': r}, f, indent=2)
PY

echo "Tests executed. See raw_results.json and output.json"
