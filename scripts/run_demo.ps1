param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8000,
  [string]$DataPath = "data\public_full_data.json",
  [double]$Delay = 1.5,
  [int]$Loops = 1
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  Write-Error "Missing .venv. Create it first, then install requirements."
}

function Test-ApiHealth {
  param([string]$Url)
  try {
    $response = Invoke-WebRequest -UseBasicParsing "$Url/health" -TimeoutSec 2
    return $response.StatusCode -eq 200
  }
  catch {
    return $false
  }
}

Push-Location $ProjectRoot
try {
  $env:STS_KB_PATH = $DataPath
  $baseUrl = "http://${BindHost}:${Port}"
  $startedHere = $false
  $apiProcess = $null

  if (-not (Test-ApiHealth $baseUrl)) {
    Write-Host "[demo] Starting API at $baseUrl"
    $apiProcess = Start-Process `
      -FilePath $Python `
      -ArgumentList "-m uvicorn api.main:app --host $BindHost --port $Port" `
      -WorkingDirectory $ProjectRoot `
      -WindowStyle Hidden `
      -PassThru
    $startedHere = $true

    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
      if (Test-ApiHealth $baseUrl) {
        break
      }
      Start-Sleep -Milliseconds 300
    }
  }

  if (-not (Test-ApiHealth $baseUrl)) {
    Write-Error "API did not become healthy at $baseUrl"
  }

  Write-Host "[demo] Overlay: $baseUrl"
  Write-Host "[demo] Verifying live bridge event path"
  & $Python scripts\check_live_bridge.py --data $DataPath --all-scenarios --port 0

  Write-Host "[demo] Playing bridge scenarios into the overlay"
  & $Python scripts\bridge_demo_player.py --base-url $baseUrl --delay $Delay --loops $Loops

  Write-Host "[demo] Done. Keep $baseUrl open to inspect the overlay."
}
finally {
  if ($startedHere -and $apiProcess -and -not $apiProcess.HasExited) {
    Stop-Process -Id $apiProcess.Id -Force
  }
  Pop-Location
}
