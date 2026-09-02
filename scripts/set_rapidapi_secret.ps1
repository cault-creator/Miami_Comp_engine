param(
  [string]$EnvPath = ".env",
  [string]$HostName = "realty-us.p.rapidapi.com"
)

$ErrorActionPreference = "Stop"

$resolvedEnvPath = Join-Path (Get-Location) $EnvPath
$secureKey = Read-Host "Paste your NEW rotated RapidAPI key" -AsSecureString

$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
  $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ([string]::IsNullOrWhiteSpace($plainKey)) {
  throw "No key entered. Nothing was changed."
}

$lines = @()
if (Test-Path -LiteralPath $resolvedEnvPath) {
  $lines = Get-Content -LiteralPath $resolvedEnvPath
}

$updates = @{
  "RAPIDAPI_HOST" = $HostName
  "RAPIDAPI_KEY" = $plainKey.Trim()
}

foreach ($name in $updates.Keys) {
  $value = $updates[$name]
  $pattern = "^\s*$([Regex]::Escape($name))\s*="
  $found = $false
  $lines = $lines | ForEach-Object {
    if ($_ -match $pattern) {
      $found = $true
      "$name=$value"
    } else {
      $_
    }
  }
  if (-not $found) {
    $lines += "$name=$value"
  }
}

Set-Content -LiteralPath $resolvedEnvPath -Value $lines -Encoding UTF8
Write-Host "Updated $resolvedEnvPath with RAPIDAPI_HOST and RAPIDAPI_KEY."
Write-Host "Do not commit .env. This repo's .gitignore already excludes it."
