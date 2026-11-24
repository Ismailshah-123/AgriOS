# Starts ONE training run and stops it if available RAM falls below a floor.
# Why: the RTX 3060 / 15.6 GB PC hung once when RAM ran out during training (2026-11-23).
# Stopping is safe: train.py writes last.pt atomically after every epoch, and re-running the
# same config resumes from it. The run dir is never deleted or overwritten by this script.
#
# Usage (from ml/):
#   .\scripts\train_supervised.ps1 -Config experiments\configs\E2_mobilenet_v3_large_tomato_v1.json
# Test the kill path without training (dummy process, floor set above available RAM):
#   .\scripts\train_supervised.ps1 -DummySeconds 60 -FloorGB 999 -StartMinGB 0
param(
    [string]$Config,
    [double]$StartMinGB = 8.0,   # owner's rule: never start below 8 GB available
    [double]$FloorGB = 1.5,      # stop training below this (E2 used 1.0; do not lower)
    [int]$PollSeconds = 5,
    [int]$DummySeconds = 0,      # >0: supervise a harmless sleep process instead of training
    [string]$LogDir = "runs",
    [int]$WatchPid = 0           # >0: do not start anything; watch this existing training process
)
$ErrorActionPreference = "Stop"
$ml = Split-Path $PSScriptRoot -Parent
Set-Location $ml

function Get-AvailGB { [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 2) }
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$name = if ($DummySeconds -gt 0) { "dummy" } else { [IO.Path]::GetFileNameWithoutExtension($Config) }
$log = Join-Path $LogDir "supervisor_${name}_$stamp.log"
function Log($msg) { $line = "$(Get-Date -Format s) $msg"; Add-Content -Path $log -Value $line; Write-Host $line }

$py = Join-Path $ml ".venv\Scripts\python.exe"
if ($WatchPid -gt 0) {  # detached second watchdog for an already-running job
    $p = Get-Process -Id $WatchPid
    $log = Join-Path $LogDir "supervisor_watch_${WatchPid}_$stamp.log"
    Log "watching pid $WatchPid, floor $FloorGB GB"
    $min = Get-AvailGB
    while (-not $p.HasExited) {
        Start-Sleep -Seconds $PollSeconds
        $a = Get-AvailGB
        if ($a -lt $min) { $min = $a }
        if ($a -lt $FloorGB) {
            Log "STOP: available RAM $a GB < floor $FloorGB GB; killing process tree $WatchPid"
            & taskkill.exe /PID $WatchPid /T /F | Out-Null
            Log "killed; min avail $min GB. Resume = re-run the same config."
            exit 4
        }
    }
    Log "pid $WatchPid ended; min avail $min GB"
    exit 0
}
if ($DummySeconds -le 0) {
    if (-not $Config -or -not (Test-Path $Config)) { throw "Config not found: $Config" }
    $other = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match "agrios_ml\.(train|evaluate|ood)" }
    if ($other) { Log "REFUSED: another ML job is running (pid $($other.ProcessId -join ','))"; exit 2 }
}
$avail = Get-AvailGB
if ($avail -lt $StartMinGB) { Log "REFUSED: $avail GB available < start minimum $StartMinGB GB"; exit 3 }

if ($DummySeconds -gt 0) {
    $args_ = "-c `"import time; time.sleep($DummySeconds)`""  # one quoted string: Start-Process does not quote array items
    $out = Join-Path $LogDir "supervisor_dummy_$stamp.out"
} else {
    $args_ = "-m agrios_ml.train `"$Config`""
    $out = Join-Path $LogDir "$name`_train_$stamp.log"
}
$p = Start-Process -FilePath $py -ArgumentList $args_ -WorkingDirectory $ml -PassThru -NoNewWindow `
    -RedirectStandardOutput $out -RedirectStandardError "$out.err"
$null = $p.Handle  # cache the handle, else ExitCode is empty after exit
Log "started pid $($p.Id) ($name), avail $avail GB, floor $FloorGB GB, output $out"
$min = $avail
while (-not $p.HasExited) {
    Start-Sleep -Seconds $PollSeconds
    $a = Get-AvailGB
    if ($a -lt $min) { $min = $a }
    if ($a -lt $FloorGB) {
        Log "STOP: available RAM $a GB < floor $FloorGB GB; killing process tree $($p.Id)"
        & taskkill.exe /PID $p.Id /T /F | Out-Null
        Start-Sleep -Seconds 2
        $left = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($p.Id)"
        Log "killed; exited=$($p.HasExited); children left=$(@($left).Count); min avail $min GB. Resume = re-run the same config."
        exit 4
    }
}
Log "finished with exit code $($p.ExitCode); min avail $min GB"
exit $p.ExitCode
