# Stops ONLY the processes recorded by start.ps1 (PID + start time must both match),
# including their child processes. Never touches PostgreSQL or any other process.
# The project-local database keeps running; stop it with:  -Database
param([switch]$Database)
. "$PSScriptRoot\common.ps1"

$entries = Read-State
if ($entries.Count -eq 0) { Write-Host "Nothing recorded as started by start.ps1." }
foreach ($e in $entries) {
    $p = Get-OwnedProcess $e
    if ($p) {
        # /T: the whole tree (uv -> python, npm -> node). Only for a PID we verified as ours.
        & taskkill.exe /PID $p.Id /T /F | Out-Null
        Write-Ok "stopped $($e.name) (pid $($p.Id))"
    } else {
        Write-Warn "$($e.name) (pid $($e.pid)) was not running"
    }
}
if (Test-Path $StateFile) { Remove-Item $StateFile }

if ($Database) {
    $db = Get-DatabaseEndpoint
    if ($db -and $db.Port -eq 54330) { $null = Invoke-BackendScript @("scripts/local_db.py", "stop") }
    else { Write-Warn "Not using the project-local database; nothing to stop." }
}
