#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
.venv/Scripts/pip.exe install --upgrade pip
.venv/Scripts/pip.exe install -r requirements.txt
.venv/Scripts/pytest.exe -q --json-report --json-report-file=raw_results.json
python - <<'PY'
import json,sys
try:
    r = json.load(open('raw_results.json'))
except Exception as e:
    print('Failed to read raw_results.json:', e)
    sys.exit(2)
summary = {
    'passed': r.get('summary',{}).get('passed',0),
    'failed': r.get('summary',{}).get('failed',0),
    'errors': r.get('summary',{}).get('errors',0),
    'duration': r.get('duration',0.0)
}
json.dump({'raw': r, 'summary': summary}, open('output.json','w'), indent=2)
print('Wrote output.json')
PY
