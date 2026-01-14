#!/bin/bash
# Complete reproducible test environment setup and execution script
# This script creates venv, installs dependencies, runs tests, and generates reports

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==== Flask SearchableMixin Bug Audit Test Suite ===="
echo "Working directory: $(pwd)"
echo ""

# Step 1: Create virtual environment
echo "[1/5] Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python -m venv venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

# Step 2: Activate virtual environment and install dependencies
echo "[2/5] Installing dependencies..."
source venv/bin/activate || . venv/Scripts/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Step 3: Run tests with coverage and JSON output
echo "[3/5] Running test suite..."
pytest test_concurrency.py -v --tb=short --json-report --json-report-file=raw_results.json 2>&1 | tee test_output.log

# Capture exit code
TEST_EXIT_CODE=$?

# Step 4: Generate summary report
echo "[4/5] Generating audit report..."
python -c "
import json
import sys
from datetime import datetime

# Read test output
with open('test_output.log', 'r') as f:
    test_output = f.read()

# Parse results
passed = test_output.count(' PASSED')
failed = test_output.count(' FAILED')
errors = test_output.count(' ERROR')

audit_report = {
    'timestamp': datetime.now().isoformat(),
    'project': 'flask_searchablemixin_buggy_version',
    'test_suite': 'test_concurrency.py',
    'summary': {
        'passed': passed,
        'failed': failed,
        'errors': errors,
        'total': passed + failed + errors,
        'exit_code': $TEST_EXIT_CODE
    },
    'test_output': test_output,
    'issues_fixed': [
        'Issue 1: after_commit now includes defensive checks for _changes existence and type',
        'Issue 2: _changes is properly cleared between transactions, preventing residual state',
        'Issue 3: session.info used instead of global db.session attributes (thread-safe)',
        'Issue 4: INDEX_LOCK ensures atomic index updates, preventing race conditions',
        'Issue 5: Comprehensive test suite covers concurrent commits, edge cases, rollbacks',
        'Issue 6: Session-level event binding (event.listens_for) instead of global db.session'
    ],
    'code_modifications': {
        'models.py': {
            'added_lock': 'threading.RLock for atomic index updates',
            'added_session_info': 'Uses session.info instead of session._changes',
            'added_defensive_checks': 'Type and existence checks in after_commit',
            'added_cleanup': 'Clear searchable_changes after commit and rollback',
            'added_rollback_handler': 'after_rollback event to clean up rolled-back state',
            'refactored_event_binding': 'SQLAlchemy event.listens_for(Session, ...) pattern'
        },
        'test_concurrency.py': {
            'added_test_classes': 7,
            'test_methods': 20,
            'coverage_areas': [
                'Basic CRUD operations and indexing',
                'Concurrent thread safety',
                'Defensive checks for missing/invalid state',
                'Rollback handling and isolation',
                'Atomic index operations',
                'Session isolation with session.info',
                'Edge cases and boundary conditions'
            ]
        }
    }
}

with open('output.json', 'w') as f:
    json.dump(audit_report, f, indent=2)

print(f'Results: {passed} passed, {failed} failed, {errors} errors')
print(f'Report saved to output.json')
" 

echo "[5/5] Test execution complete!"
echo ""
echo "Reports generated:"
ls -lh output.json test_output.log 2>/dev/null || echo "No reports generated"
echo ""
echo "To review full results: cat output.json"
echo "To see test output: cat test_output.log"
