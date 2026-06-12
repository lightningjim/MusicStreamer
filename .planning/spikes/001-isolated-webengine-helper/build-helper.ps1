# Spike 001 build driver - isolated standalone oauth_helper.exe (B1).
# ASCII ONLY (PowerShell 5.1 parses .ps1 as cp1252; non-ASCII breaks strings).
#
# Run on the Win11 VM from this spike directory, in a PLAIN PowerShell
# (NOT the Miniforge prompt, and with NO conda env active for the BUILD):
#   powershell -ExecutionPolicy Bypass -File .\build-helper.ps1
#
# What it does:
#   1. Creates an isolated venv (.venv-helper) using the system Python 3.12.
#      Deliberately NOT conda - the whole point of B1 is pip-only Qt isolation.
#   2. pip install -r requirements.txt (PySide6-Essentials+Addons 6.10.1).
#   3. Builds Stage A (webengine_smoke) and Stage B (oauth_helper) bundles.
#   4. Asserts QtWebEngineProcess.exe + Qt6WebEngineCore.dll are in each bundle.
#   5. Runs the Stage A smoke in --probe mode and reports its exit code.
#
# Exit codes (so the spike result is machine-checkable):
#   0  all build + assertions + probe passed
#   20 venv / pip install failed
#   21 a pyinstaller build failed
#   22 QtWebEngineProcess.exe missing from a bundle (the G6 failure signature)
#   23 Qt6WebEngineCore.dll missing from a bundle
#   24 Stage A probe exe did not exit 0

$ErrorActionPreference = "Stop"

function Invoke-Native {
    # PyInstaller/pip log INFO to stderr; under -EA Stop the first line aborts.
    param([scriptblock]$Block)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Block } finally { $ErrorActionPreference = $prev }
}

function Fail($code, $msg) {
    Write-Host "SPIKE-FAIL [$code]: $msg" -ForegroundColor Red
    exit $code
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
Write-Host "=== Spike 001 build dir: $ScriptDir ===" -ForegroundColor Cyan

# --- Guard: warn if a conda env is active (contaminates the isolation test) ---
if ($env:CONDA_PREFIX) {
    Write-Host "WARNING: CONDA_PREFIX is set ($env:CONDA_PREFIX)." -ForegroundColor Yellow
    Write-Host "         The BUILD must use plain pip Python, not conda." -ForegroundColor Yellow
    Write-Host "         Run 'conda deactivate' until no (env) prefix shows, then re-run." -ForegroundColor Yellow
    Fail 20 "conda env active during build - deactivate first"
}

# --- 1. Isolated venv ---------------------------------------------------------
$Venv = Join-Path $ScriptDir ".venv-helper"
if (-not (Test-Path $Venv)) {
    Write-Host "Creating isolated venv (py -3.12) ..." -ForegroundColor Cyan
    Invoke-Native { py -3.12 -m venv $Venv }
    if (-not (Test-Path $Venv)) { Fail 20 "venv creation failed (is Python 3.12 installed? 'py -3.12 --version')" }
}
$VenvPy = Join-Path $Venv "Scripts\python.exe"

Write-Host "pip install -r requirements.txt ..." -ForegroundColor Cyan
Invoke-Native { & $VenvPy -m pip install --upgrade pip *>&1 | Tee-Object "pip.log" }
Invoke-Native { & $VenvPy -m pip install -r requirements.txt *>&1 | Tee-Object -Append "pip.log" }

# Verify the WebEngine import resolves IN the build env before bundling.
Write-Host "Verifying WebEngine import in the isolated env ..." -ForegroundColor Cyan
$probe = & $VenvPy -c "from PySide6.QtWebEngineWidgets import QWebEngineView; print('IMPORT_OK')" 2>&1
if ($probe -notmatch "IMPORT_OK") {
    Write-Host $probe -ForegroundColor Red
    Fail 20 "WebEngine import failed in the isolated env (pip-only stack should NOT have this problem - investigate)"
}
Write-Host "  WebEngine import OK in isolated env" -ForegroundColor Green

# --- 2. Build both bundles ----------------------------------------------------
function Build-Spec($spec) {
    Write-Host "pyinstaller $spec ..." -ForegroundColor Cyan
    Invoke-Native { & $VenvPy -m PyInstaller $spec --noconfirm *>&1 | Tee-Object -Append "build.log" }
}
Build-Spec "webengine_smoke.spec"
if (-not (Test-Path "dist\webengine_smoke\webengine_smoke.exe")) { Fail 21 "Stage A build produced no exe" }
Build-Spec "oauth_helper_standalone.spec"
if (-not (Test-Path "dist\oauth_helper\oauth_helper.exe")) { Fail 21 "Stage B build produced no exe" }

# --- 3. Bundle assertions (the G6 failure signature is a MISSING WebEngine) ---
function Assert-WebEngine($bundleDir) {
    $proc = Join-Path $bundleDir "_internal\PySide6\QtWebEngineProcess.exe"
    $core = Join-Path $bundleDir "_internal\PySide6\Qt6WebEngineCore.dll"
    # PyInstaller 6.x onedir nests under _internal; fall back to flat layout.
    if (-not (Test-Path $proc)) { $proc = Join-Path $bundleDir "PySide6\QtWebEngineProcess.exe" }
    if (-not (Test-Path $core)) { $core = Join-Path $bundleDir "PySide6\Qt6WebEngineCore.dll" }
    if (-not (Test-Path $proc)) { Fail 22 "QtWebEngineProcess.exe missing in $bundleDir" }
    if (-not (Test-Path $core)) { Fail 23 "Qt6WebEngineCore.dll missing in $bundleDir" }
    Write-Host "  OK: QtWebEngineProcess.exe + Qt6WebEngineCore.dll present in $bundleDir" -ForegroundColor Green
}
Assert-WebEngine "dist\webengine_smoke"
Assert-WebEngine "dist\oauth_helper"

# --- 4. Stage A probe (deterministic, no human needed) ------------------------
Write-Host "Running Stage A smoke --probe ..." -ForegroundColor Cyan
$smokeExe = "dist\webengine_smoke\webengine_smoke.exe"
Invoke-Native { & $smokeExe --probe --url "https://example.com" --timeout 25 *>&1 | Tee-Object "probe.log" }
$probeCode = $LASTEXITCODE
Write-Host "  Stage A probe exit code: $probeCode" -ForegroundColor Cyan
if ($probeCode -ne 0) { Fail 24 "Stage A probe did not exit 0 (see probe.log for JSON events)" }

Write-Host ""
Write-Host "=== SPIKE 001 BUILD + STAGE A: ALL GREEN ===" -ForegroundColor Green
Write-Host "Bundles:" -ForegroundColor Green
Write-Host "  dist\webengine_smoke\webengine_smoke.exe" -ForegroundColor Green
Write-Host "  dist\oauth_helper\oauth_helper.exe" -ForegroundColor Green
Write-Host ""
Write-Host "Next - run the MANUAL stages from VM-RUNBOOK (see README How to Run):" -ForegroundColor Yellow
Write-Host "  Stage B: .\dist\oauth_helper\oauth_helper.exe --mode gbs   (and twitch, google)" -ForegroundColor Yellow
Write-Host "  Stage C (isolation): activate conda, put Library\bin on PATH, re-run the probe:" -ForegroundColor Yellow
Write-Host "           .\dist\webengine_smoke\webengine_smoke.exe --probe --url https://example.com" -ForegroundColor Yellow
Write-Host "           It MUST still exit 0 with conda Qt on PATH." -ForegroundColor Yellow
exit 0
