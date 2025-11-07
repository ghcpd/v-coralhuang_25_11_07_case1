Write-Host "Creating virtual environment .venv and installing dependencies"
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

Write-Host "Running pytest and producing raw_results.json"
pytest -q --tb=short --json-report --json-report-file=raw_results.json

Write-Host "Summarizing to output.json"
$r = Get-Content raw_results.json | ConvertFrom-Json
$summary = @{ total = $r.summary.total; passed = $r.summary.passed; failed = $r.summary.failed }
$out = @{ summary = $summary; raw = $r }
$out | ConvertTo-Json -Depth 10 | Out-File output.json -Encoding utf8
Write-Host "Wrote output.json"

Write-Host "Done"