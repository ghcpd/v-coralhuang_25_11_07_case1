#!/bin/bash
set -euo pipefail

WORKDIR=$(cd "$(dirname "$0")" && pwd)
cd "$WORKDIR"

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

pytest -q --tb=short || true

# Minimal raw results capture
pytest -q --maxfail=1 > raw_results.txt || true

python - <<'PY'
import json
out = {
  "project": "flask_searchablemixin_buggy_version",
  "tests_raw": open('raw_results.txt','r',encoding='utf-8').read()
}
open('output.json','w',encoding='utf-8').write(json.dumps(out, indent=2))
print('Wrote output.json')
PY
