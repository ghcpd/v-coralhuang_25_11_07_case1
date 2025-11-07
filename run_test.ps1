# PowerShell version of the run_test helper
$ErrorActionPreference = 'Stop'

$venv = '.venv'
python -m venv $venv
.\$venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r .\requirements.txt

pytest -q --json-report --json-report-file=raw_results.json

python summarize_results.py
