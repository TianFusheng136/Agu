[CmdletBinding()]
param(
    [string]$Version = "v0.3.1"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Run scripts/bootstrap.ps1 first to create the project Python environment."
}

$archive = "https://github.com/TauricResearch/TradingAgents/archive/refs/tags/$Version.zip"
Write-Host "Installing TradingAgents $Version into the Agu virtual environment..."
& $python -m pip install $archive
if ($LASTEXITCODE -ne 0) {
    throw "TradingAgents installation failed. Check the network and try again."
}
Write-Host "TradingAgents installation completed. Restart Agu to enable the multi-agent page."
