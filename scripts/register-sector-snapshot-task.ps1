[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$TaskName = "AI-Market-Radar-CollectSectorSnapshot",
    [ValidatePattern("^([01]?[0-9]|2[0-3]):[0-5][0-9]$")]
    [string]$At = "15:10",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$backend = Join-Path $root "backend"

if ($Remove) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        if ($PSCmdlet.ShouldProcess($TaskName, "Remove scheduled task")) {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
            Write-Host "Removed scheduled task: $TaskName"
        }
    }
    else {
        Write-Host "Scheduled task not found: $TaskName"
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment missing: $python. Run scripts\\bootstrap.ps1 first."
}

$runAt = [datetime]::Today.Add([timespan]::Parse($At))
$action = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "-X utf8 -m app.cli.collect_sector_snapshot" `
    -WorkingDirectory $backend
$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At $runAt
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 8)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

if ($PSCmdlet.ShouldProcess($TaskName, "Register weekday sector snapshot task at $At")) {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "Records one real public A-share sector rotation snapshot on weekdays." `
        -Force | Out-Null
    Write-Host "Registered $TaskName at $At every weekday."
}
