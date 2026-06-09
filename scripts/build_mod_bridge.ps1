param(
  [string]$ModsDir = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$JavaHome = Join-Path $ProjectRoot ".tools\jdk17"
$Gradle = Join-Path $ProjectRoot ".tools\gradle\bin\gradle.bat"
$ModBridge = Join-Path $ProjectRoot "mod-bridge"
$LocalModsDirConfig = Join-Path $ModBridge "local.modsdir.txt"

function Resolve-ModsDir {
  param([string]$ExplicitModsDir)

  if ($ExplicitModsDir -ne "") {
    return $ExplicitModsDir
  }
  if ($env:STS_AGENT_MODS_DIR -and $env:STS_AGENT_MODS_DIR.Trim() -ne "") {
    return $env:STS_AGENT_MODS_DIR.Trim()
  }
  if (Test-Path $LocalModsDirConfig) {
    $Configured = (Get-Content -Raw -LiteralPath $LocalModsDirConfig).Trim()
    if ($Configured -ne "") {
      return $Configured
    }
  }

  $Candidates = @(
    "E:\SteamLibrary\steamapps\common\SlayTheSpire\mods",
    "D:\SteamLibrary\steamapps\common\SlayTheSpire\mods",
    "$env:ProgramFiles(x86)\Steam\steamapps\common\SlayTheSpire\mods",
    "$env:ProgramFiles\Steam\steamapps\common\SlayTheSpire\mods"
  )
  foreach ($Candidate in $Candidates) {
    if ($Candidate -and (Test-Path $Candidate)) {
      return $Candidate
    }
  }
  return ""
}

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

$ResolvedModsDir = Resolve-ModsDir -ExplicitModsDir $ModsDir
if ($ResolvedModsDir -ne "") {
  $OutputJar = Join-Path $ModBridge "build\libs\sts-agent-bridge-0.1.0.jar"
  if (-not (Test-Path $OutputJar)) {
    Write-Error "Built Mod jar not found: $OutputJar"
  }
  if (-not (Test-Path $ResolvedModsDir)) {
    New-Item -ItemType Directory -Path $ResolvedModsDir | Out-Null
  }
  Copy-Item -LiteralPath $OutputJar -Destination (Join-Path $ResolvedModsDir "sts-agent-bridge-0.1.0.jar") -Force
  Write-Host "Copied Mod jar to $ResolvedModsDir"
}
else {
  Write-Host "No Slay the Spire mods directory configured; jar left in mod-bridge\build\libs."
}
