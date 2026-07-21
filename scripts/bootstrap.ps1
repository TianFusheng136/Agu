[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "[1/3] Creating Python virtual environment..." -ForegroundColor Cyan
    python -m venv $venv
}

Write-Host "[2/3] Installing backend dependencies..." -ForegroundColor Cyan
& $python -m pip install --upgrade pip
& $python -m pip install --no-cache-dir -e "$root\backend[dev]"

Write-Host "[3/3] Installing locked frontend dependencies..." -ForegroundColor Cyan
Push-Location (Join-Path $root "frontend")
try {
    npm.cmd ci
}
finally {
    Pop-Location
}

Write-Host "Bootstrap complete." -ForegroundColor Green
