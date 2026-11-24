# Shared helpers for the AgriOS developer scripts (Windows PowerShell 5.1+).
# Dot-source from the other scripts:  . "$PSScriptRoot\common.ps1"

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..\..").Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$RunDir = Join-Path $Root "var\dev-run"          # git-ignored (var/)
$StateFile = Join-Path $RunDir "processes.json"
$ApiUrl = "http://127.0.0.1:8000"
$WebUrl = "http://localhost:5173"

function Write-Ok($msg)   { Write-Host "  [ok]   $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [warn] $msg" -ForegroundColor Yellow }
function Write-Bad($msg)  { Write-Host "  [fail] $msg" -ForegroundColor Red }
function Write-Step($msg) { Write-Host "`n$msg" -ForegroundColor Cyan }

function Test-Command($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

# Run a backend Python script with uv; returns the exit code.
function Invoke-BackendScript([string[]]$ScriptArgs) {
    Push-Location $Backend
    try {
        # Out-Host: show output without it becoming part of the function's return value.
        & uv run python @ScriptArgs | Out-Host
        return $LASTEXITCODE
    } finally { Pop-Location }
}

function Test-PortListening([int]$Port) {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return [bool]$conn
}

function Get-HttpStatus([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return [int]$r.StatusCode
    } catch {
        if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
        return 0
    }
}

# Reads DATABASE_URL's host:port from backend/.env without printing anything secret.
function Get-DatabaseEndpoint {
    $envFile = Join-Path $Backend ".env"
    if (-not (Test-Path $envFile)) { return $null }
    $line = Select-String -Path $envFile -Pattern '^\s*DATABASE_URL\s*=\s*(.+)$' | Select-Object -First 1
    if (-not $line) { return $null }
    $url = $line.Matches[0].Groups[1].Value
    if ($url -match '@([^:/]+):(\d+)/') { return @{ Host = $Matches[1]; Port = [int]$Matches[2] } }
    return $null
}

function Read-State {
    if (-not (Test-Path $StateFile)) { return @() }
    # Windows PowerShell 5.1 emits a JSON array as ONE pipeline object; ForEach-Object
    # unrolls it into individual entries (verified: without this, .api joined 3 URLs).
    $data = Get-Content $StateFile -Raw | ConvertFrom-Json
    return @($data | ForEach-Object { $_ })
}

# A recorded process is "ours" only if both PID and start time still match.
function Get-OwnedProcess($entry) {
    $p = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
    if ($p -and $p.StartTime.ToString("o") -eq $entry.started) { return $p }
    return $null
}
