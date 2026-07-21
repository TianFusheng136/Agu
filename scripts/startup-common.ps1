function Get-RadarStartupMode {
    param(
        [bool]$ApiReady,
        [bool]$WebReady
    )

    if ($ApiReady -and $WebReady) {
        return "reuse"
    }
    return "start"
}

function Get-RadarLogPaths {
    param(
        [string]$LogDirectory,
        [int]$ProcessId,
        [int]$ApiPort,
        [int]$WebPort
    )

    return [pscustomobject]@{
        backend_out = Join-Path $LogDirectory "backend.$ProcessId.$ApiPort.out.log"
        backend_err = Join-Path $LogDirectory "backend.$ProcessId.$ApiPort.err.log"
        frontend_out = Join-Path $LogDirectory "frontend.$ProcessId.$WebPort.out.log"
        frontend_err = Join-Path $LogDirectory "frontend.$ProcessId.$WebPort.err.log"
    }
}
