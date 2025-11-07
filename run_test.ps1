# PowerShell script to set up environment and run tests
$ErrorActionPreference = 'Stop'
python -m venv venv
# Activate venv
& .\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Run pytest with JSON report plugin
pytest -q --json-report --json-report-file=raw_results.json

# Summarize results
python summarize.py
Write-Host "Tests completed. Raw results in raw_results.json, summary in output.json"
