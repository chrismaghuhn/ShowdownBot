$ErrorActionPreference = "Stop"
$PidFile = Join-Path $PSScriptRoot ".local_showdown_server.pid"
if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host "No .local_showdown_server.pid found -- nothing to stop"
    exit 0
}
$procId = Get-Content -LiteralPath $PidFile | Select-Object -First 1
try {
    Stop-Process -Id $procId -Force -ErrorAction Stop
    Write-Host "Stopped pokemon-showdown (pid $procId)"
}
catch {
    Write-Host "Process $procId already stopped or not found"
}
Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
