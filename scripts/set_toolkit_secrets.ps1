param(
  [string]$EnvPath = ".env",
  [string]$EngineBase = "https://judicious-cassowary-306.convex.site",
  [string]$RapidApiHost = "realty-us.p.rapidapi.com"
)

$ErrorActionPreference = "Stop"

function Read-SecretPlainText {
  param([string]$Prompt)

  $secure = Read-Host $Prompt -AsSecureString
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim()
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  }
}

function Set-EnvLine {
  param(
    [string[]]$Lines,
    [string]$Name,
    [string]$Value
  )

  $pattern = "^\s*$([Regex]::Escape($Name))\s*="
  $found = $false
  $next = $Lines | ForEach-Object {
    if ($_ -match $pattern) {
      $found = $true
      "$Name=$Value"
    } else {
      $_
    }
  }
  if (-not $found) {
    $next += "$Name=$Value"
  }
  return $next
}

$resolvedEnvPath = Join-Path (Get-Location) $EnvPath
$engineKey = Read-SecretPlainText "Paste your Engine API key"
$rapidApiKey = Read-SecretPlainText "Paste your NEW rotated RapidAPI key"

if ([string]::IsNullOrWhiteSpace($engineKey)) {
  throw "No Engine API key entered. Nothing was changed."
}
if ([string]::IsNullOrWhiteSpace($rapidApiKey)) {
  throw "No RapidAPI key entered. Nothing was changed."
}

$lines = @()
if (Test-Path -LiteralPath $resolvedEnvPath) {
  $lines = Get-Content -LiteralPath $resolvedEnvPath
}

$lines = Set-EnvLine -Lines $lines -Name "ENGINE_BASE" -Value $EngineBase
$lines = Set-EnvLine -Lines $lines -Name "ENGINE_API_KEY" -Value $engineKey
$lines = Set-EnvLine -Lines $lines -Name "RAPIDAPI_HOST" -Value $RapidApiHost
$lines = Set-EnvLine -Lines $lines -Name "RAPIDAPI_KEY" -Value $rapidApiKey

Set-Content -LiteralPath $resolvedEnvPath -Value $lines -Encoding UTF8
Write-Host "Updated $resolvedEnvPath with Engine and RapidAPI settings."
Write-Host "Do not commit .env. This repo's .gitignore already excludes it."
