$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  Write-Error "Missing .venv. Create it with: D:\python\python3.11\python.exe -m venv .venv"
}

Push-Location $ProjectRoot
try {
  & $Python scripts\dev_check.py
  & $Python -m compileall api sts_engine scripts
  & $Python scripts\data_coverage_report.py --data data\public_full_data.json --fail-under 99
  & $Python scripts\ingest_graph.py --data data\public_full_data.json --dry-run
  & $Python scripts\check_graph_fixtures.py --data data\public_full_data.json
  & $Python scripts\check_decision_engine.py --data data\public_full_data.json
  & $Python scripts\check_live_bridge.py --data data\public_full_data.json --all-scenarios
  & $Python scripts\evaluate.py --data data\public_full_data.json --eval data\public_eval_cases.json
}
finally {
  Pop-Location
}
