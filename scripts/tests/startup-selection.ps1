$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$devScript = Join-Path $root "scripts\dev.ps1"
$startupCommon = Join-Path $root "scripts\startup-common.ps1"
. $startupCommon
$devSource = Get-Content -LiteralPath $devScript -Raw
if ($devSource -notmatch '\[int\]\$PreferredApiPort\s*=\s*8001') {
    throw "Default API port must be 8001"
}
if ($devSource -notmatch '\$WebUrl/api/health') {
    throw "Existing web service detection must use the fast health endpoint"
}
$apiListener = [System.Net.Sockets.TcpListener]::new(
    [System.Net.IPAddress]::Loopback,
    54321
)
$webListener = [System.Net.Sockets.TcpListener]::new(
    [System.Net.IPAddress]::Loopback,
    54322
)

try {
    $apiListener.Start()
    $webListener.Start()
    $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $devScript `
        -PreferredApiPort 54321 `
        -PreferredWebPort 54322 `
        -DryRun
    if ($LASTEXITCODE -ne 0) {
        throw "dev.ps1 dry-run failed"
    }

    $selection = $output | Select-Object -Last 1 | ConvertFrom-Json
    if ($selection.api_port -eq 54321) {
        throw "Occupied API port was not replaced"
    }
    if ($selection.web_port -eq 54322) {
        throw "Occupied web port was not replaced"
    }
    if ($selection.api_port -eq $selection.web_port) {
        throw "API and web ports must be different"
    }
    if ($selection.mode -ne "start") {
        throw "Occupied non-HTTP ports must select a new startup mode"
    }
    if ($selection.backend_out_log -notmatch 'backend\.\d+\.\d+\.out\.log$') {
        throw "Backend log path must be unique to the process and selected port"
    }
    if ($selection.frontend_out_log -notmatch 'frontend\.\d+\.\d+\.out\.log$') {
        throw "Frontend log path must be unique to the process and selected port"
    }
    Write-Host "Startup port selection test passed."
}
finally {
    $apiListener.Stop()
    $webListener.Stop()
}

if ((Get-RadarStartupMode -ApiReady $true -WebReady $true) -ne "reuse") {
    throw "Healthy existing API and web services must be reused"
}
if ((Get-RadarStartupMode -ApiReady $true -WebReady $false) -ne "start") {
    throw "A partial service set must start a complete new pair"
}
$paths = Get-RadarLogPaths `
    -LogDirectory "C:\logs" `
    -ProcessId 321 `
    -ApiPort 8001 `
    -WebPort 3000
if ($paths.backend_out -ne "C:\logs\backend.321.8001.out.log") {
    throw "Backend log path must include process and port"
}
if ($paths.frontend_out -ne "C:\logs\frontend.321.3000.out.log") {
    throw "Frontend log path must include process and port"
}
Write-Host "Existing healthy service reuse test passed."
