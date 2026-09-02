param(
  [string]$EnvPath = ".env",
  [string]$SalesRapidApiHost = "realtor-api-data.p.rapidapi.com"
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
$salesRapidApiKey = Read-SecretPlainText "Paste your Sales Data RapidAPI key"

if ([string]::IsNullOrWhiteSpace($salesRapidApiKey)) {
  throw "No Sales Data RapidAPI key entered. Nothing was changed."
}

$lines = @()
if (Test-Path -LiteralPath $resolvedEnvPath) {
  $lines = Get-Content -LiteralPath $resolvedEnvPath
}

$lines = Set-EnvLine -Lines $lines -Name "SALES_RAPIDAPI_HOST" -Value $SalesRapidApiHost
$lines = Set-EnvLine -Lines $lines -Name "SALES_RAPIDAPI_KEY" -Value $salesRapidApiKey

Set-Content -LiteralPath $resolvedEnvPath -Value $lines -Encoding UTF8
Write-Host "Updated $resolvedEnvPath with Sales Data RapidAPI settings."
Write-Host "Do not commit .env. This repo's .gitignore already excludes it."
