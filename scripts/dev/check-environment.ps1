# Checks tools, project dependencies and backend/.env (names only; never prints values).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\dev\check-environment.ps1
. "$PSScriptRoot\common.ps1"
$problems = 0

Write-Step "Tools"
foreach ($tool in @("uv", "node", "npm", "git")) {
    if (Test-Command $tool) {
        $v = (& $tool --version 2>$null | Select-Object -First 1)
        Write-Ok "$tool $v"
    } else { Write-Bad "$tool not found on PATH"; $problems++ }
}
$pgReady = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\pg_isready.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1
if ($pgReady) { Write-Ok "PostgreSQL tools: $($pgReady.DirectoryName)" }
else { Write-Warn "PostgreSQL binaries not found (needed for the local/test clusters; set PG_BIN)" }

Write-Step "Project dependencies"
if (Test-Path (Join-Path $Backend ".venv")) { Write-Ok "backend/.venv" }
else { Write-Bad "backend/.venv missing -> run: cd backend; uv sync"; $problems++ }
if (Test-Path (Join-Path $Frontend "node_modules")) { Write-Ok "frontend/node_modules" }
else { Write-Bad "frontend/node_modules missing -> run: cd frontend; npm ci"; $problems++ }

Write-Step "Backend configuration (backend/.env)"
if (Test-Command "uv") {
    $code = Invoke-BackendScript @("scripts/env_file.py", "check")
    if ($code -ne 0) { $problems++ }
}
$db = Get-DatabaseEndpoint
if ($db) {
    if ($db.Port -eq 54329) { Write-Bad "DATABASE_URL points at the TEST cluster (54329). Use a development database."; $problems++ }
    elseif ($pgReady) {
        & $pgReady.FullName -h $db.Host -p $db.Port -q
        if ($LASTEXITCODE -eq 0) { Write-Ok "PostgreSQL reachable at $($db.Host):$($db.Port)" }
        else { Write-Bad "PostgreSQL NOT reachable at $($db.Host):$($db.Port)"; $problems++ }
    }
}

Write-Step "Ports"
foreach ($port in @(8000, 5173)) {
    if (Test-PortListening $port) { Write-Warn "port $port is in use (start.ps1 needs it free)" }
    else { Write-Ok "port $port free" }
}

if ($problems -gt 0) { Write-Host "`n$problems problem(s) found." -ForegroundColor Red; exit 1 }
Write-Host "`nEnvironment OK." -ForegroundColor Green
