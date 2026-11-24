# Safe, repeatable database initialisation. Never drops or resets data.
#
#   scripts\dev\init-database.ps1                # use DATABASE_URL from backend/.env
#   scripts\dev\init-database.ps1 -LocalCluster  # first time only: create a project-local
#                                                # PostgreSQL (port 54330) and use it
param([switch]$LocalCluster)
. "$PSScriptRoot\common.ps1"

Write-Step "1. backend/.env"
$null = Invoke-BackendScript @("scripts/env_file.py", "ensure")

if ($LocalCluster) {
    Write-Step "2. Project-local PostgreSQL"
    $code = Invoke-BackendScript @("scripts/local_db.py", "start")
    if ($code -ne 0) { Write-Bad "Local PostgreSQL could not be started."; exit $code }
} else {
    $db = Get-DatabaseEndpoint
    if ($db -and $db.Port -eq 54330) {
        Write-Step "2. Project-local PostgreSQL"
        $code = Invoke-BackendScript @("scripts/local_db.py", "start")
        if ($code -ne 0) { exit $code }
    }
}

Write-Step "3. Migrations and verification"
$code = Invoke-BackendScript @("scripts/init_db.py")
if ($code -eq 2) {
    Write-Host @"

DATABASE_URL is not configured. Choose ONE:
  A) Your existing PostgreSQL: create a role and database (see
     docs\13-user-guides\WINDOWS_LOCAL_SETUP.md, step 4), add DATABASE_URL to
     backend\.env, then run this script again.
  B) A project-local database (no password needed from you):
     scripts\dev\init-database.ps1 -LocalCluster
"@
}
exit $code
