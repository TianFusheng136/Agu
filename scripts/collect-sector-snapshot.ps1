[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8001/api/v1"
)

$ErrorActionPreference = "Stop"
$uri = "$($ApiBaseUrl.TrimEnd('/'))/market/rotation-snapshot"

try {
    $result = Invoke-RestMethod -Uri $uri -Method Post -TimeoutSec 45
}
catch {
    Write-Error "Unable to collect sector rotation snapshot: $($_.Exception.Message)"
    exit 1
}

if ($result.state -ne "recorded" -or $result.sectors_recorded -lt 1) {
    Write-Error "Collection did not return valid sector samples."
    exit 1
}

Write-Host "Sector rotation snapshot recorded: $($result.as_of), $($result.sectors_recorded) sectors." -ForegroundColor Green
