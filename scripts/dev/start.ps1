# Starts API (:8000), job worker and frontend (:5173) as background processes.
# Logs: var\dev-run\logs\*.log   Stop with: scripts\dev\stop.ps1
# Other ports if those are busy:  start.ps1 -ApiPort 8010 -WebPort 5180
param([int]$ApiPort = 8000, [int]$WebPort = 5173)
. "$PSScriptRoot\common.ps1"
$ApiUrl = "http://127.0.0.1:$ApiPort"
$WebUrl = "http://localhost:$WebPort"

Write-Step "Checking prerequisites"
foreach ($tool in @("uv", "npm")) {
    if (-not (Test-Command $tool)) { Write-Bad "$tool not found. Run scripts\dev\check-environment.ps1"; exit 1 }
}
foreach ($dir in @((Join-Path $Backend ".venv"), (Join-Path $Frontend "node_modules"))) {
    if (-not (Test-Path $dir)) { Write-Bad "$dir missing. Run scripts\dev\check-environment.ps1"; exit 1 }
}
$running = @(Read-State | Where-Object { Get-OwnedProcess $_ })
if ($running.Count -gt 0) { Write-Warn "AgriOS is already running (scripts\dev\status.ps1)."; exit 0 }
foreach ($port in @($ApiPort, $WebPort)) {
    if (Test-PortListening $port) {
        Write-Bad "Port $port is already in use by another process. Stop it first (this script will not kill it)."
        exit 1
    }
}

$db = Get-DatabaseEndpoint
if ($db -and $db.Port -eq 54330) {
    $null = Invoke-BackendScript @("scripts/local_db.py", "start")
}
Write-Step "Verifying database"
$code = Invoke-BackendScript @("scripts/init_db.py", "--check")
if ($code -ne 0) { Write-Bad "Database not ready. Run scripts\dev\init-database.ps1"; exit $code }

New-Item -ItemType Directory -Force (Join-Path $RunDir "logs") | Out-Null
$uv = (Get-Command uv).Source
$npm = (Get-Command npm.cmd).Source
$specs = @(
    @{ name = "api";      file = $uv;  args = "run uvicorn app.main:app --port $ApiPort"; cwd = $Backend },
    @{ name = "worker";   file = $uv;  args = "run python -m app.jobs.worker";       cwd = $Backend },
    @{ name = "frontend"; file = $npm; args = "run dev -- --port $WebPort --strictPort"; cwd = $Frontend }
)
# Children inherit these: the API must accept the web app's origin (refresh-cookie check)
# and the Vite proxy must target this API port. Restored afterwards.
$saved = @{ ALLOWED_ORIGINS = $env:ALLOWED_ORIGINS; VITE_API_PROXY_TARGET = $env:VITE_API_PROXY_TARGET }
$env:ALLOWED_ORIGINS = $WebUrl
$env:VITE_API_PROXY_TARGET = $ApiUrl
$state = @()
Write-Step "Starting processes"
foreach ($s in $specs) {
    $log = Join-Path $RunDir "logs\$($s.name).log"
    # cmd.exe does the log redirection. Start-Process's own -Redirect* switches enable
    # handle inheritance, so the servers would hold this script's output pipe open and any
    # caller capturing it (VS Code task, CI) would hang. Environment is still inherited.
    $cmdLine = "/d /c `"`"$($s.file)`" $($s.args) > `"$log`" 2>&1`""
    $p = Start-Process -FilePath "cmd.exe" -ArgumentList $cmdLine -WorkingDirectory $s.cwd `
        -WindowStyle Hidden -PassThru
    $state += [pscustomobject]@{ name = $s.name; pid = $p.Id; started = $p.StartTime.ToString("o"); api = $ApiUrl; web = $WebUrl }
    Write-Ok "$($s.name) (pid $($p.Id)) -> $log"
}
$env:ALLOWED_ORIGINS = $saved.ALLOWED_ORIGINS
$env:VITE_API_PROXY_TARGET = $saved.VITE_API_PROXY_TARGET
ConvertTo-Json @($state) | Set-Content -Encoding utf8 $StateFile

Write-Step "Waiting for services"
$deadline = (Get-Date).AddSeconds(90)
$apiOk = $false; $webOk = $false
while ((Get-Date) -lt $deadline -and -not ($apiOk -and $webOk)) {
    if (-not $apiOk) { $apiOk = (Get-HttpStatus "$ApiUrl/api/v1/ready") -eq 200 }
    if (-not $webOk) { $webOk = (Get-HttpStatus $WebUrl) -eq 200 }
    Start-Sleep -Milliseconds 700
}
if ($apiOk) { Write-Ok "API ready:  $ApiUrl/api/v1/docs" } else { Write-Bad "API not ready; see var\dev-run\logs\api.log" }
if ($webOk) { Write-Ok "Web app:    $WebUrl" } else { Write-Bad "Frontend not up; see var\dev-run\logs\frontend.log" }
if (-not ($apiOk -and $webOk)) { exit 1 }
Write-Host "`nAgriOS is running. Open $WebUrl  (stop: scripts\dev\stop.ps1)" -ForegroundColor Green
