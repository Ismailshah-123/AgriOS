# Crop Doctor finalisation for the model selected in ml/reports/SELECTION.md (runbook steps 4-8):
#   final evaluation ONCE (test + external) -> ONNX package -> OOD evaluation -> serving parity
#   test -> register + activate in the dev DB.
# Safety: refuses to start below 8 GB available RAM (owner's rule) or if the AgriOS app stack /
# another ML job is running; every heavy step runs under a RAM watchdog (kills the tree < 1.5 GB).
# Never re-runs a finished step: the final evaluation is skipped if its metrics already exist
# (the test set is opened once), and package.py refuses an existing version.
#   cd ml; .\scripts\finalize_crop_doctor.ps1
param(
    [string]$Exp = "E2_mobilenet_v3_large_tomato_v1",
    [string]$Version = "1.0.0",
    [string]$Packages = "D:\AgriOS-data\packages",
    [double]$StartMinGB = 8.0,
    [double]$FloorGB = 1.5
)
$ErrorActionPreference = "Stop"
$ml = Split-Path $PSScriptRoot -Parent
$root = Split-Path $ml -Parent
Set-Location $ml
$py = Join-Path $ml ".venv\Scripts\python.exe"
$run = "runs\$Exp\seed42"
$final = "reports\$Exp\final"
$pkg = Join-Path $Packages "crop_doctor_tomato\$Version"
# Absolute: the parity/register steps run from backend\ (Push-Location), where a relative path breaks.
$log = Join-Path $ml "runs\finalize_${Exp}_$(Get-Date -Format yyyyMMdd_HHmmss).log"
function Log($m) { $l = "$(Get-Date -Format s) $m"; Write-Host $l; Add-Content $log $l }
function AvailGB { [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 2) }

if (-not (Test-Path "reports\SELECTION.md")) { throw "reports\SELECTION.md missing: select on validation first" }
if (-not (Select-String -Path "reports\SELECTION.md" -Pattern $Exp -Quiet)) { throw "$Exp is not the selected model" }
$busy = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "agrios_ml\.(train|evaluate|ood|package)" }
if ($busy) { throw "another ML job is running (pid $($busy.ProcessId -join ','))" }
if (Test-Path (Join-Path $root "var\dev-run\processes.json")) {
    $st = Get-Content (Join-Path $root "var\dev-run\processes.json") -Raw | ConvertFrom-Json
    if ($st | Where-Object { Get-Process -Id $_.pid -ErrorAction SilentlyContinue }) { throw "stop the app first: scripts\dev\stop.ps1" }
}

function Step($name, [string[]]$argv, [int]$timeoutMin = 90) {
    $a = AvailGB
    if ($a -lt $StartMinGB) { throw "$name refused: available RAM $a GB < $StartMinGB GB. Close browsers/apps and re-run." }
    Log "START $name (available $a GB): $($argv -join ' ')"
    $p = Start-Process -FilePath $py -ArgumentList $argv -WorkingDirectory $ml -PassThru -NoNewWindow `
        -RedirectStandardOutput "$log.$name.out" -RedirectStandardError "$log.$name.err"
    # Cache the handle now: without it, Start-Process -PassThru reports a null ExitCode after exit
    # (the 2026-11-24 final_eval run succeeded but was logged as "FAIL exit " for this reason).
    $null = $p.Handle
    $deadline = (Get-Date).AddMinutes($timeoutMin)
    while (-not $p.HasExited) {
        Start-Sleep -Seconds 3
        $a = AvailGB
        if ($a -lt $FloorGB -or (Get-Date) -gt $deadline) {
            Log "KILL $name (available $a GB)"; & taskkill /PID $p.Id /T /F | Out-Null; throw "$name stopped by watchdog"
        }
    }
    if ($p.ExitCode -ne 0) { Log "FAIL $name exit $($p.ExitCode) (see $log.$name.err)"; throw "$name failed" }
    Log "DONE $name"
}

if (Test-Path "$final\metrics.json") { Log "final evaluation already exists: $final (not re-run; test opened once)" }
else { Step "final_eval" @("-m", "agrios_ml.evaluate", $run, "--report-dir", $final, "--final") }
if (Test-Path "$pkg\package.json") { Log "package exists: $pkg" }
else { Step "package" @("-m", "agrios_ml.package", $run, "--metrics", "$final\metrics.json", "--version", $Version, "--out", $Packages) }
if (Test-Path "reports\$Exp\ood\ood_metrics.json") { Log "OOD metrics exist" }
else {
    Step "ood" @("-m", "agrios_ml.ood", $run, "--package", $pkg, "--manifest", "..\datasets\reports\dataset_manifest.csv",
        "--raw-root", "..\datasets\raw\agri_foundation_v1", "--cache", "D:\AgriOS-data\interim\ood_cache", "--out", "reports\$Exp\ood", "--workers", "2")
}

Log "parity test (backend, CPU)"
Push-Location (Join-Path $root "backend")
try {
    $env:AGRIOS_TEST_MODEL_PACKAGE = $pkg
    & uv run pytest tests/unit/test_onnx_predictor.py -q
    if ($LASTEXITCODE -ne 0) { throw "ONNX/torch parity test failed: not registering" }
    Log "parity OK; registering"
    & uv run python scripts/register_model.py $pkg --activate --notes "tomato_v1 $Exp, final eval $(Get-Date -Format yyyy-MM-dd), SELECTION.md"
    if ($LASTEXITCODE -ne 0) { throw "registration failed" }
} finally {
    Remove-Item Env:AGRIOS_TEST_MODEL_PACKAGE -ErrorAction SilentlyContinue
    Pop-Location
}
Log "ALL DONE. Start the app (scripts\dev\start.ps1) and create a Crop Doctor case with a real tomato leaf photo."
