# Shows database, migration, API and frontend status. Read-only.
. "$PSScriptRoot\common.ps1"
$recorded = @(Read-State)
if ($recorded.Count -gt 0 -and $recorded[0].api) { $ApiUrl = $recorded[0].api; $WebUrl = $recorded[0].web }

Write-Step "Database"
$db = Get-DatabaseEndpoint
if (-not $db) { Write-Bad "DATABASE_URL not set in backend/.env" }
else {
    Write-Ok "configured for $($db.Host):$($db.Port)"
    $code = Invoke-BackendScript @("scripts/init_db.py", "--check")
    if ($code -eq 0) { Write-Ok "connected; migrations at head" } else { Write-Bad "check failed (exit $code)" }
}

Write-Step "Services"
$health = Get-HttpStatus "$ApiUrl/api/v1/health"
$ready = Get-HttpStatus "$ApiUrl/api/v1/ready"
$web = Get-HttpStatus $WebUrl
if ($health -eq 200) { Write-Ok "API health  200" } else { Write-Bad "API health  $health" }
if ($ready -eq 200) { Write-Ok "API ready   200" } else { Write-Bad "API ready   $ready" }
if ($web -eq 200) { Write-Ok "Frontend    200 ($WebUrl)" } else { Write-Bad "Frontend    $web" }

Write-Step "Processes started by start.ps1"
$entries = Read-State
if ($entries.Count -eq 0) { Write-Host "  none recorded" }
foreach ($e in $entries) {
    if (Get-OwnedProcess $e) { Write-Ok "$($e.name) running (pid $($e.pid))" }
    else { Write-Warn "$($e.name) not running" }
}
