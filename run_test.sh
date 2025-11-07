#!/bin/bash
set -e
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q | tee raw_results.txt
python - <<'PY'
import json, subprocess, sys
# Generate a basic summary
out = {'tests_output': open('raw_results.txt').read()}
with open('output.json','w') as f:
    json.dump(out,f,indent=2)
print('Wrote output.json')
PY
