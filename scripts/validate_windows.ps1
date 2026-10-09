<#
.SYNOPSIS
  VISTA Windows validation for Python 3.11 or 3.12. Everything runs locally; after the pip install step
  no internet, API key or extra model download is needed.
.DESCRIPTION
  Creates .venv311 / .venv312, installs requirements-dev.txt with the candidate constraints
  (constraints\windows-cp311.txt | cp312), then runs: environment report, pip check, onnxruntime import check,
  ruff, pytest (mock), pytest -m requires_model (real engine), benchmark, server probes.
  Logs go to results\validation-py<ver>-<timestamp>\ . Nothing is deleted. No commit/push.
.EXAMPLE
  .\scripts\validate_windows.ps1 -PythonVersion 3.11 -Label "X270 on AC power"
#>
[CmdletBinding()]
param(
  [ValidateSet('3.11', '3.12')][string]$PythonVersion = '3.11',
  [int]$Runs = 5,
  [int]$Warmup = 2,
  [string]$Label = '',
  [switch]$SkipBenchmark,
  [switch]$SkipProbes,
  [switch]$NoConstraints
)

# Native tools write progress to stderr; with 'Stop' Windows PowerShell 5.1 would treat that as an error.
$ErrorActionPreference = 'Continue'
Set-Location (Split-Path -Parent $PSScriptRoot)

$tag = $PythonVersion.Replace('.', '')
$venv = ".venv$tag"
$py = Join-Path $venv 'Scripts\python.exe'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = "results\validation-py$tag-$stamp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$results = New-Object System.Collections.ArrayList

function Invoke-Step {
  param([string]$Name, [scriptblock]$Command, [bool]$Required = $true)
  $log = Join-Path $logDir (($Name -replace '[^A-Za-z0-9]+', '_') + '.log')
  Write-Host ""
  Write-Host "==> $Name" -ForegroundColor Cyan
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $global:LASTEXITCODE = 0
  & $Command 2>&1 | Tee-Object -FilePath $log | Out-Host
  $code = $LASTEXITCODE
  $sw.Stop()
  $status = if ($code -eq 0) { 'PASS' } else { 'FAIL' }
  [void]$results.Add([pscustomobject]@{ Step = $Name; Status = $status; ExitCode = $code; Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1); Required = $Required })
  return ($code -eq 0)
}

# 0. Python launcher check -------------------------------------------------------------------------
Write-Host "Looking for Python $PythonVersion via the 'py' launcher..."
& py "-$PythonVersion" --version
if ($LASTEXITCODE -ne 0) {
  Write-Host "Python $PythonVersion not found. Installed versions:" -ForegroundColor Yellow
  & py -0p
  Write-Host "Install it from python.org (64-bit) and re-run. Python 3.13+ is NOT supported by rapidocr-onnxruntime 1.4.4." -ForegroundColor Yellow
  exit 2
}

# 1. Machine facts (for interpreting the benchmark) ---------------------------------------------------
Invoke-Step 'machine info' {
  Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | Format-List
  Get-CimInstance Win32_ComputerSystem | Select-Object @{n = 'TotalRAM_MB'; e = { [math]::Round($_.TotalPhysicalMemory / 1MB) } } | Format-List
  Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, @{n = 'FreeRAM_MB'; e = { [math]::Round($_.FreePhysicalMemory / 1KB) } } | Format-List
  powercfg /getactivescheme
  Get-CimInstance Win32_Battery | Select-Object BatteryStatus, EstimatedChargeRemaining | Format-List
  $global:LASTEXITCODE = 0
} $false | Out-Null

# 2. Virtual environment + install ------------------------------------------------------------------
if (-not (Test-Path $py)) {
  if (-not (Invoke-Step "create $venv" { & py "-$PythonVersion" -m venv $venv })) { exit 3 }
}
Invoke-Step 'upgrade pip' { & $py -m pip install --upgrade pip } | Out-Null
$constraint = "constraints\windows-cp$tag.txt"
$ok = if ($NoConstraints) {
  Invoke-Step 'install deps (unconstrained)' { & $py -m pip install -r requirements-dev.txt }
} else {
  Invoke-Step "install deps (constraints $constraint)" { & $py -m pip install -r requirements-dev.txt -c $constraint }
}
if (-not $ok) { Write-Host 'Dependency installation failed; see the log above.' -ForegroundColor Red }

# 3. Checks -----------------------------------------------------------------------------------------------
Invoke-Step 'python and package versions' {
  & $py -c "import sys, platform; print(sys.version); print(platform.platform(), platform.machine())"
  & $py -m pip list
} $false | Out-Null
Invoke-Step 'pip check' { & $py -m pip check }
$importOk = Invoke-Step 'onnxruntime import' {
  & $py -c "import onnxruntime as o; print(o.__version__, o.get_available_providers())"
}
if (-not $importOk) {
  Write-Host "onnxruntime failed to import. A missing 'Microsoft Visual C++ Redistributable' (x64, 2015-2022) is a" -ForegroundColor Yellow
  Write-Host "commonly reported cause of DLL load errors. This was NOT verified from package metadata; check the log." -ForegroundColor Yellow
}
Invoke-Step 'ruff' { & $py -m ruff check . }
Invoke-Step 'pytest (mock engine)' { & $py -m pytest -q -p no:cacheprovider }
if ($importOk) {
  Invoke-Step 'pytest real engine (network blocked)' { & $py -m pytest -q -p no:cacheprovider -m requires_model -s }
  if (-not $SkipBenchmark) {
    Invoke-Step 'benchmark' { & $py -m scripts.benchmark_ocr --runs $Runs --warmup $Warmup --label $Label } $false | Out-Null
  }
  if (-not $SkipProbes) {
    Invoke-Step 'server probes' { & $py -m scripts.probe_server } $false | Out-Null
  }
}

# 4. Summary ---------------------------------------------------------------------------------------------------
Write-Host ""
Write-Host "================ SUMMARY (Python $PythonVersion) ================" -ForegroundColor Cyan
$results | Format-Table Step, Status, ExitCode, Seconds, Required -AutoSize | Out-Host
$results | Format-Table Step, Status, ExitCode, Seconds, Required -AutoSize | Out-String -Width 200 | Set-Content -Path (Join-Path $logDir 'summary.txt')
Write-Host "Logs: $logDir   JSON reports: results\benchmark-*.json, results\probe-*.json"
Write-Host "This run only counts as Windows evidence for the machine it ran on."
$failedRequired = @($results | Where-Object { $_.Status -eq 'FAIL' -and $_.Required }).Count
if ($failedRequired -gt 0) { exit 1 } else { exit 0 }
