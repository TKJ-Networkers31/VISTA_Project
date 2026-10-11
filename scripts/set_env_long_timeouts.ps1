# Updates ONLY the keys listed below in .env and keeps every other line (including VISTA_NIM_API_KEY).
# Makes a backup (.env.bak) first. Removes duplicate lines of those keys (the loader keeps the FIRST duplicate).
# Run from anywhere:  .\scripts\set_env_long_timeouts.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path .env)) {
  Copy-Item .env.example .env
  Write-Host "Created .env from .env.example"
}
Copy-Item .env .env.bak -Force
$settings = [ordered]@{
  VISTA_POLICY_DEFAULT            = 'hybrid'
  VISTA_EXTERNAL_ENABLED          = 'true'
  VISTA_EXTERNAL_TIMEOUT_SECONDS  = '150'
  VISTA_EXTERNAL_RETRY_MAX        = '1'
  VISTA_TASK_TIMEOUT_SECONDS      = '320'
  VISTA_UNDERSTANDING_MAX_SIDE    = '768'
  VISTA_NIM_MAX_TOKENS            = '1024'
  VISTA_NIM_ENABLE_THINKING       = 'false'
}
$lines = @(Get-Content .env)
foreach ($k in $settings.Keys) {
  $lines = @($lines | Where-Object { $_ -notmatch ('^\s*' + $k + '\s*=') })
  $lines += ($k + '=' + $settings[$k])
}
Set-Content -Path .env -Value $lines -Encoding UTF8
Write-Host "Updated in .env:"
foreach ($k in $settings.Keys) { Write-Host ("  " + $k + "=" + $settings[$k]) }
if (Select-String -Path .env -Pattern '^VISTA_NIM_API_KEY=.+' -Quiet) {
  Write-Host "VISTA_NIM_API_KEY: present (not shown)."
} else {
  Write-Host "VISTA_NIM_API_KEY: MISSING or empty. Add a line  VISTA_NIM_API_KEY=<your key>  to .env." -ForegroundColor Yellow
}
Write-Host "Backup: .env.bak . Now restart the server (Ctrl+C, then python -m apps.api)."
