# PowerShell test execution script for SearchableMixin concurrency and safety tests

$ErrorActionPreference = "Stop"

Write-Host "=== Setting up test environment ===" -ForegroundColor Cyan

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -r requirements.txt

# Run tests with pytest and capture output
Write-Host ""
Write-Host "=== Running tests ===" -ForegroundColor Cyan
pytest test_concurrency.py -v --tb=short --json-report --json-report-file=raw_results.json 2>&1 | Tee-Object -FilePath test_output.txt

# Generate summary output.json
Write-Host ""
Write-Host "=== Generating summary ===" -ForegroundColor Cyan
python -c @"
import json
import sys
import os
from datetime import datetime

# Try to read pytest JSON report if available
raw_results = {}
if os.path.exists('raw_results.json'):
    try:
        with open('raw_results.json', 'r') as f:
            raw_results = json.load(f)
    except:
        pass

# Parse test output
test_output = ''
if os.path.exists('test_output.txt'):
    with open('test_output.txt', 'r') as f:
        test_output = f.read()

# Count test results from output
passed = test_output.count(' PASSED')
failed = test_output.count(' FAILED')
error = test_output.count(' ERROR')

# Extract timing if available
timing_info = {}
if 'duration' in raw_results.get('summary', {}):
    timing_info = {'total_duration_seconds': raw_results['summary'].get('duration', 0)}

# Create output summary
output = {
    'timestamp': datetime.now().isoformat(),
    'test_summary': {
        'total_tests': passed + failed + error,
        'passed': passed,
        'failed': failed,
        'errors': error,
        'success_rate': f'{(passed / (passed + failed + error) * 100):.1f}%' if (passed + failed + error) > 0 else '0%'
    },
    'timing': timing_info,
    'raw_output': test_output[-5000:] if len(test_output) > 5000 else test_output,
    'raw_results_available': os.path.exists('raw_results.json')
}

with open('output.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f'Tests completed: {passed} passed, {failed} failed, {error} errors')
print('Summary written to output.json')
"@

Write-Host ""
Write-Host "=== Test execution complete ===" -ForegroundColor Green
Write-Host "Results saved to:"
Write-Host "  - output.json (summary)"
Write-Host "  - raw_results.json (detailed pytest results)"
Write-Host "  - test_output.txt (console output)"

