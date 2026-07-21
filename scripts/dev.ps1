[CmdletBinding()]
param(
    [ValidateRange(1024, 65500)]
    [int]$PreferredApiPort = 8001,

    [ValidateRange(1024, 65500)]
    [int]$PreferredWebPort = 3000,

    [switch]$OpenBrowser,
    [switch]$DryRun,

    [ValidateRange(0, 86400)]
    [int]$RunSeconds = 0
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "startup-common.ps1")
$python = Join-Path $root ".venv\Scripts\python.exe"
$frontendModules = Join-Path $root "frontend\node_modules"
$runtime = Join-Path $root ".runtime"
$logs = Join-Path $runtime "logs"
$backend = $null
$frontend = $null
$backendOut = $null
$backendErr = $null
$frontendOut = $null
$frontendErr = $null

function Test-TcpPortFree {
    param([int]$Port)

    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        $Port
    )
    try {
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        $listener.Stop()
    }
}

function Find-FreePort {
    param(
        [int]$StartPort,
        [int[]]$ReservedPorts = @()
    )

    for ($port = $StartPort; $port -le [Math]::Min($StartPort + 100, 65500); $port++) {
        if ($ReservedPorts -contains $port) {
            continue
        }
        if (Test-TcpPortFree -Port $port) {
            return $port
        }
    }
    throw "No free TCP port found near $StartPort."
}

function Test-RadarApiReady {
    param([string]$ApiBaseUrl)

    try {
        $response = Invoke-RestMethod `
            -Uri "$ApiBaseUrl/health" `
            -TimeoutSec 2 `
            -ErrorAction Stop
        return (
            $response.status -eq "ok" -and
            $response.service -eq "ai-market-radar"
        )
    }
    catch {
        return $false
    }
}

function Test-RadarWebReady {
    param([string]$WebUrl)

    try {
        $response = Invoke-RestMethod `
            -Uri "$WebUrl/api/health" `
            -TimeoutSec 2 `
            -ErrorAction Stop
        return (
            $response.status -eq "ok" -and
            $response.service -eq "ai-market-radar-web"
        )
    }
    catch {
        return $false
    }
}

function Wait-HttpService {
    param(
        [string]$Uri,
        [System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $Process.Refresh()
        if ($Process.HasExited) {
            throw "Process $($Process.Id) exited before $Uri became ready."
        }
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "Timed out waiting for $Uri."
}

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)

    if ($null -eq $Process) {
        return
    }
    $Process.Refresh()
    if (-not $Process.HasExited) {
        & cmd.exe /d /c (
            "taskkill.exe /PID $($Process.Id) /T /F >nul 2>&1"
        ) | Out-Null
        $Process.Refresh()
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

function Start-LoggedCommand {
    param(
        [string]$Command,
        [string]$WorkingDirectory
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = "cmd.exe"
    $startInfo.Arguments = "/d /s /c `"$Command`""
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    return [System.Diagnostics.Process]::Start($startInfo)
}

function Open-DefaultBrowser {
    param([string]$Uri)

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Uri
    $startInfo.UseShellExecute = $true
    [System.Diagnostics.Process]::Start($startInfo) | Out-Null
}

function Stop-StaleProjectNextDev {
    param(
        [string]$ErrorLog,
        [string]$ProjectDirectory
    )

    if (-not (Test-Path -LiteralPath $ErrorLog)) {
        return $false
    }
    $errorText = Get-Content -LiteralPath $ErrorLog -Raw
    if ($errorText -notmatch "Another next dev server is already running") {
        return $false
    }
    $pidMatch = [regex]::Match($errorText, "PID:\s+(\d+)")
    $dirMatch = [regex]::Match($errorText, "Dir:\s+([^\r\n]+)")
    if (-not $pidMatch.Success -or -not $dirMatch.Success) {
        return $false
    }

    $reportedDirectory = $dirMatch.Groups[1].Value.Trim()
    $expectedDirectory = [System.IO.Path]::GetFullPath($ProjectDirectory).TrimEnd("\")
    $reportedDirectory = [System.IO.Path]::GetFullPath($reportedDirectory).TrimEnd("\")
    if ($reportedDirectory -ine $expectedDirectory) {
        return $false
    }

    $stalePid = [int]$pidMatch.Groups[1].Value
    try {
        $staleProcess = [System.Diagnostics.Process]::GetProcessById($stalePid)
    }
    catch {
        return $false
    }

    Write-Host "Stopping stale Next.js process $stalePid from this project." -ForegroundColor Yellow
    Stop-ProcessTree -Process $staleProcess
    Start-Sleep -Milliseconds 800
    return $true
}

$preferredApiBaseUrl = "http://127.0.0.1:$PreferredApiPort/api/v1"
$preferredWebUrl = "http://127.0.0.1:$PreferredWebPort"
$apiReady = Test-RadarApiReady -ApiBaseUrl $preferredApiBaseUrl
$webReady = Test-RadarWebReady -WebUrl $preferredWebUrl
$startupMode = Get-RadarStartupMode -ApiReady $apiReady -WebReady $webReady
$reuseExisting = $startupMode -eq "reuse"

if ($reuseExisting) {
    $apiPort = $PreferredApiPort
    $webPort = $PreferredWebPort
}
else {
    $apiPort = Find-FreePort -StartPort $PreferredApiPort
    $webPort = Find-FreePort -StartPort $PreferredWebPort -ReservedPorts @($apiPort)
}

$logPaths = Get-RadarLogPaths `
    -LogDirectory $logs `
    -ProcessId $PID `
    -ApiPort $apiPort `
    -WebPort $webPort
$backendOut = $logPaths.backend_out
$backendErr = $logPaths.backend_err
$frontendOut = $logPaths.frontend_out
$frontendErr = $logPaths.frontend_err

if ($DryRun) {
    [pscustomobject]@{
        api_port = $apiPort
        web_port = $webPort
        mode = $startupMode
        backend_out_log = $backendOut
        frontend_out_log = $frontendOut
    } | ConvertTo-Json -Compress
    exit 0
}

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $frontendModules)) {
    throw "Dependencies are missing. Run scripts\bootstrap.ps1 first."
}

if ($reuseExisting) {
    Write-Host "AI Market Radar is already running." -ForegroundColor Green
    Write-Host "Reusing FastAPI: $preferredApiBaseUrl" -ForegroundColor Cyan
    Write-Host "Reusing Next.js: $preferredWebUrl" -ForegroundColor Cyan
    if ($OpenBrowser) {
        Open-DefaultBrowser -Uri $preferredWebUrl
    }
    exit 0
}

New-Item -ItemType Directory -Force -Path $logs | Out-Null
Set-Content -LiteralPath $backendOut, $backendErr, $frontendOut, $frontendErr -Value ""

$apiBaseUrl = "http://127.0.0.1:$apiPort/api/v1"
$webUrl = "http://127.0.0.1:$webPort"
$env:NEXT_PUBLIC_API_URL = $apiBaseUrl

try {
    Write-Host "Starting FastAPI: $apiBaseUrl" -ForegroundColor Cyan
    $backendCommand = (
        "`"$python`" -m uvicorn app.main:app " +
        "--host 127.0.0.1 --port $apiPort " +
        "1>`"$backendOut`" 2>`"$backendErr`""
    )
    $backend = Start-LoggedCommand `
        -Command $backendCommand `
        -WorkingDirectory (Join-Path $root "backend")

    Wait-HttpService -Uri "$apiBaseUrl/health" -Process $backend

    Write-Host "Starting Next.js: $webUrl" -ForegroundColor Cyan
    $frontendCommand = (
        "npm.cmd run dev -- --hostname 127.0.0.1 --port $webPort " +
        "1>`"$frontendOut`" 2>`"$frontendErr`""
    )
    $frontendDirectory = Join-Path $root "frontend"
    $frontend = Start-LoggedCommand `
        -Command $frontendCommand `
        -WorkingDirectory $frontendDirectory

    try {
        Wait-HttpService -Uri $webUrl -Process $frontend
    }
    catch {
        $recovered = Stop-StaleProjectNextDev `
            -ErrorLog $frontendErr `
            -ProjectDirectory $frontendDirectory
        if (-not $recovered) {
            throw
        }
        Set-Content -LiteralPath $frontendOut, $frontendErr -Value ""
        $frontend = Start-LoggedCommand `
            -Command $frontendCommand `
            -WorkingDirectory $frontendDirectory
        Wait-HttpService -Uri $webUrl -Process $frontend
    }

    Write-Host ""
    Write-Host "AI Market Radar is ready: $webUrl" -ForegroundColor Green
    Write-Host "API docs: http://127.0.0.1:$apiPort/docs" -ForegroundColor DarkGray
    Write-Host "Selected ports automatically when defaults were occupied." -ForegroundColor DarkGray

    if ($OpenBrowser) {
        Open-DefaultBrowser -Uri $webUrl
    }

    if ($RunSeconds -gt 0) {
        Start-Sleep -Seconds $RunSeconds
        return
    }

    Write-Host "Keep this window open. Press Ctrl+C to stop." -ForegroundColor Green
    while ($true) {
        Start-Sleep -Seconds 1
        $backend.Refresh()
        $frontend.Refresh()
        if ($backend.HasExited -or $frontend.HasExited) {
            throw "A development service exited unexpectedly. See .runtime\logs."
        }
    }
}
catch {
    Write-Host ""
    Write-Host $_.Exception.Message -ForegroundColor Red
    foreach ($path in @($backendErr, $frontendErr)) {
        if ($path -and (Test-Path -LiteralPath $path)) {
            $content = Get-Content -LiteralPath $path -Tail 20
            if ($content) {
                Write-Host "--- $path ---" -ForegroundColor DarkGray
                $content | Write-Host
            }
        }
    }
    throw
}
finally {
    Stop-ProcessTree -Process $frontend
    Stop-ProcessTree -Process $backend
}
