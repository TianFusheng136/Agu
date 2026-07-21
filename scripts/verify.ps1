[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw ".venv is missing. Run scripts\bootstrap.ps1 first."
}

Write-Host "[1/6] Startup port selection" -ForegroundColor Cyan
& powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File (Join-Path $root "scripts\tests\startup-selection.ps1")
if ($LASTEXITCODE -ne 0) { throw "Startup selection test failed" }

Write-Host "[2/6] Backend tests" -ForegroundColor Cyan
Push-Location (Join-Path $root "backend")
try {
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Pytest failed" }

    Write-Host "[3/6] Backend lint" -ForegroundColor Cyan
    & $python -m ruff check app tests
    if ($LASTEXITCODE -ne 0) { throw "Ruff failed" }
}
finally {
    Pop-Location
}

Push-Location (Join-Path $root "frontend")
try {
    Write-Host "[4/6] Frontend component tests" -ForegroundColor Cyan
    npm.cmd test
    if ($LASTEXITCODE -ne 0) { throw "Vitest failed" }

    Write-Host "[5/6] Frontend lint" -ForegroundColor Cyan
    npm.cmd run lint
    if ($LASTEXITCODE -ne 0) { throw "ESLint failed" }

    Write-Host "[6/6] Frontend production build" -ForegroundColor Cyan
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "Next.js build failed" }
}
finally {
    Pop-Location
}

Write-Host "All verification checks passed." -ForegroundColor Green
