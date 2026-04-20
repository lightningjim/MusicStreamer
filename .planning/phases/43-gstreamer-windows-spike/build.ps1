#Requires -Version 5.1
# Phase 43 spike — build driver. Idempotent, snapshot-safe.
# Exit codes: 0=ok, 1=env missing, 2=pyinstaller failed, 3=smoke test failed

param(
    [string]$GstRoot   = "C:\spike-gst\runtime\1.0\msvc_x86_64",
    [switch]$SkipSmoke = $false
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# --- 0. Pre-flight checks -------------------------------------------------
Write-Host "=== SPIKE BUILD: pre-flight ==="
if (-not (Test-Path "$GstRoot\bin\libgstreamer-1.0-0.dll")) {
    Write-Error "SPIKE_FAIL reason=gst_runtime_missing path='$GstRoot'"
    exit 1
}
if (-not (Test-Path "$GstRoot\bin\gst-inspect-1.0.exe")) {
    Write-Error "SPIKE_FAIL reason=gst_inspect_missing hint='reinstall with Complete feature set'"
    exit 1
}
if (-not (Test-Path "$GstRoot\lib\gio\modules\libgiognutls.dll")) {
    Write-Error "SPIKE_FAIL reason=gio_tls_module_missing hint='reinstall with Complete feature set'"
    exit 1
}

& "$GstRoot\bin\gst-inspect-1.0.exe" --version | Select-String "version"

# --- 1. Export env for spec -----------------------------------------------
$env:GSTREAMER_ROOT = $GstRoot
$env:PATH           = "$GstRoot\bin;$env:PATH"   # bundler needs to load gst DLLs to introspect
$env:PYTHONPATH     = ""                          # avoid leaking site packages into build

# --- 2. Ensure clean build dir -------------------------------------------
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $here
try {
    Remove-Item -Recurse -Force "build", "dist" -ErrorAction SilentlyContinue

    # --- 3. Install/confirm build deps ----------------------------------
    Write-Host "=== SPIKE BUILD: python deps ==="
    python -m pip install --upgrade `
        "pyinstaller>=6.11" `
        "pyinstaller-hooks-contrib" `
        "pygobject>=3.50" `
        2>&1 | Out-Host

    # --- 4. PyInstaller -------------------------------------------------
    Write-Host "=== SPIKE BUILD: pyinstaller ==="
    python -m PyInstaller 43-spike.spec --noconfirm --log-level INFO *>&1 | Tee-Object -FilePath "artifacts\build.log"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "SPIKE_FAIL reason=pyinstaller_nonzero exitcode=$LASTEXITCODE"
        exit 2
    }

    Write-Host "SPIKE_OK step=build exe='$here\dist\spike\spike.exe'"

    # --- 5. Smoke test --------------------------------------------------
    if (-not $SkipSmoke) {
        Write-Host "=== SPIKE BUILD: smoke test ==="
        $testUrl = Get-Content "test_url.txt" -Raw -ErrorAction Stop
        $testUrl = $testUrl.Trim()
        if (-not $testUrl) {
            Write-Error "SPIKE_FAIL reason=test_url_empty hint='populate test_url.txt with AA HTTPS URL'"
            exit 3
        }

        & ".\dist\spike\spike.exe" $testUrl *>&1 | Tee-Object -FilePath "artifacts\smoke.log"
        if ($LASTEXITCODE -ne 0) {
            Write-Error "SPIKE_FAIL reason=smoke_nonzero exitcode=$LASTEXITCODE"
            exit 3
        }
        Write-Host "SPIKE_OK step=smoke"
    }
}
finally {
    Pop-Location
}

Write-Host "SPIKE_OK step=done"
exit 0
