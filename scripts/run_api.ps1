$ErrorActionPreference = "Stop"

param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8000,
  [string]$DataPath = "data\public_full_data.json"
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  Write-Error "Missing .venv. Run: D:\python\python3.11\python.exe -m venv .venv"
}

Push-Location $ProjectRoot
try {
  $env:STS_KB_PATH = $DataPath
  & $Python -m uvicorn api.main:app --host $HostName --port $Port --reload
}
finally {
  Pop-Location
}
