#!/bin/bash

# run_test.sh - Reproducible test execution script

set -e

echo "======================================================================"
echo "Flask SearchableMixin Concurrency Bug Fix - Test Execution"
echo "======================================================================"

# Setup
echo "[1/4] Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

echo "[2/4] Installing dependencies..."
source .venv/bin/activate
pip install --quiet -r requirements.txt

# Run tests
echo "[3/4] Running test suite..."
python -m pytest test_concurrency.py -v --tb=short -json-report --json-report-file=raw_results.json > /tmp/pytest.log 2>&1 || true

# Capture results
echo "[4/4] Processing results..."
if [ -f raw_results.json ]; then
    python3 << 'EOF'
import json
import os

with open('raw_results.json') as f:
    data = json.load(f)

output = {
    "test_summary": {
        "total_tests": len(data.get('tests', [])),
        "passed": sum(1 for t in data.get('tests', []) if t.get('outcome') == 'passed'),
        "failed": sum(1 for t in data.get('tests', []) if t.get('outcome') == 'failed'),
        "duration_seconds": data.get('duration', 0)
    },
    "tests": [
        {
            "name": t.get('nodeid'),
            "outcome": t.get('outcome'),
            "duration": t.get('duration')
        }
        for t in data.get('tests', [])
    ]
}

with open('output.json', 'w') as f:
    json.dump(output, f, indent=2)

print("Test execution complete. Results saved to output.json")
EOF
fi

deactivate
echo "======================================================================"
echo "Test execution finished. Check output.json for results."
echo "======================================================================"
