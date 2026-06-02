param(
  [string]$ModsDir = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$JavaHome = Join-Path $ProjectRoot ".tools\jdk17"
$Gradle = Join-Path $ProjectRoot ".tools\gradle\bin\gradle.bat"
$ModBridge = Join-Path $ProjectRoot "mod-bridge"

if (-not (Test-Path $JavaHome)) {
  Write-Error "Missing portable JDK at $JavaHome. Install or unpack JDK 17 before building the Mod bridge."
}

if (-not (Test-Path $Gradle)) {
  Write-Error "Missing portable Gradle at $Gradle. Install or unpack Gradle before building the Mod bridge."
}

$RequiredJars = @(
  "desktop-1.0.jar",
  "BaseMod.jar",
  "ModTheSpire.jar"
)

foreach ($Jar in $RequiredJars) {
  $Path = Join-Path $ModBridge "libs\$Jar"
  if (-not (Test-Path $Path)) {
    Write-Error "Missing dependency jar: $Path"
  }
}

Push-Location $ModBridge
try {
  $env:JAVA_HOME = $JavaHome
  & $Gradle jar --no-daemon
}
finally {
  Pop-Location
}

if ($ModsDir -ne "") {
  $OutputJar = Join-Path $ModBridge "build\libs\sts-agent-bridge-0.1.0.jar"
  if (-not (Test-Path $OutputJar)) {
    Write-Error "Built Mod jar not found: $OutputJar"
  }
  if (-not (Test-Path $ModsDir)) {
    New-Item -ItemType Directory -Path $ModsDir | Out-Null
  }
  Copy-Item -LiteralPath $OutputJar -Destination (Join-Path $ModsDir "sts-agent-bridge-0.1.0.jar") -Force
  Write-Host "Copied Mod jar to $ModsDir"
}
