#Requires -Version 5.1
# Phase 44 MusicStreamer Windows build driver. Idempotent, snapshot-safe.
# Adapted from .planning/phases/43-gstreamer-windows-spike/build.ps1.
# Exit codes: 0=ok, 1=env missing, 2=pyinstaller failed, 3=smoke test failed,
#             4=PKG-03 guard fail, 5=version parse fail, 6=iscc fail, 7=spec entry guard fail

param(
    # Default: if inside a conda env, use its Library tree; else fall back to the MSVC installer path.
    [string]$GstRoot = $(if ($env:CONDA_PREFIX) { "$env:CONDA_PREFIX\Library" } else { "C:\spike-gst\runtime" }),
    [switch]$SkipSmoke      = $false,
    [switch]$SkipPipInstall = $(if ($env:CONDA_PREFIX) { $true } else { $false })
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Windows PowerShell 5.1 treats native-command stderr writes as terminating errors
# when $ErrorActionPreference = "Stop". PyInstaller, pip, and MusicStreamer.exe all log
# INFO/DEBUG to stderr. Invoke-Native wraps a native call with Continue semantics
# and propagates $LASTEXITCODE so explicit checks still fire on real failures.
function Invoke-Native {
    param([scriptblock]$Block)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Block } finally { $ErrorActionPreference = $prev }
}

# artifacts/ must exist before Tee-Object writes build.log / smoke.log into it.
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "artifacts") | Out-Null

Write-Host "=== MUSICSTREAMER BUILD: environment ==="
Write-Host "GstRoot        = $GstRoot"
Write-Host "CONDA_PREFIX   = $($env:CONDA_PREFIX)"
Write-Host "SkipPipInstall = $SkipPipInstall"

# --- 0. Pre-flight checks -------------------------------------------------
Write-Host "=== MUSICSTREAMER BUILD: pre-flight ==="
if (-not (Test-Path "$GstRoot\bin\gstreamer-1.0-0.dll")) {
    Write-Error "BUILD_FAIL reason=gst_runtime_missing path='$GstRoot'"
    exit 1
}
if (-not (Test-Path "$GstRoot\bin\gst-inspect-1.0.exe")) {
    Write-Error "BUILD_FAIL reason=gst_inspect_missing hint='reinstall with Complete feature set'"
    exit 1
}
# 1.28.x ships OpenSSL-backed TLS on Windows (gioopenssl.dll); 1.24/1.26 shipped GnuTLS (libgiognutls.dll).
$tlsDll = "$GstRoot\lib\gio\modules\gioopenssl.dll"
$legacyTlsDll = "$GstRoot\lib\gio\modules\libgiognutls.dll"
if (-not ((Test-Path $tlsDll) -or (Test-Path $legacyTlsDll))) {
    Write-Error "BUILD_FAIL reason=gio_tls_module_missing hint='reinstall with Complete feature set; expected gioopenssl.dll (1.28+) or libgiognutls.dll (1.26-)'"
    exit 1
}
if (-not (Test-Path "$GstRoot\libexec\gstreamer-1.0\gst-plugin-scanner.exe")) {
    Write-Error "BUILD_FAIL reason=gst_plugin_scanner_missing path='$GstRoot\libexec\gstreamer-1.0\gst-plugin-scanner.exe'"
    exit 1
}

Invoke-Native { & "$GstRoot\bin\gst-inspect-1.0.exe" --version | Select-String "version" }

# --- 1. Export env for spec -----------------------------------------------
$env:GSTREAMER_ROOT = $GstRoot
$env:PATH           = "$GstRoot\bin;$env:PATH"   # bundler needs to load gst DLLs to introspect
$env:PYTHONPATH     = ""                          # avoid leaking site packages into build

# --- 2. Ensure clean build dir -------------------------------------------
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $here
try {
    Remove-Item -Recurse -Force "build", "dist", "..\..\dist" -ErrorAction SilentlyContinue

    # --- 3. Install/confirm build deps ----------------------------------
    if ($SkipPipInstall) {
        Write-Host "=== MUSICSTREAMER BUILD: python deps (skipped -- using conda env) ==="
        Invoke-Native { python -c "import gi, PyInstaller; print(f'PyInstaller={PyInstaller.__version__}  gi={gi.__version__}')" 2>&1 | Out-Host }
    } else {
        # NOTE: pip install PyGObject fails on Windows without MSVC C++ toolchain + PKG_CONFIG_PATH.
        # If you see "subprocess-exited-with-error" below, switch to conda-forge (see README).
        Write-Host "=== MUSICSTREAMER BUILD: python deps (pip) ==="
        Invoke-Native {
            python -m pip install --upgrade `
                "pyinstaller>=6.19" `
                "pyinstaller-hooks-contrib>=2026.2" `
                "pygobject>=3.50" `
                2>&1 | Out-Host
        }
    }

    # --- 3a. PKG-03 compliance guard (D-22) -----------------------------
    # SINGLE SOURCE OF TRUTH: tools/check_subprocess_guard.py (Plan 01).
    # This step invokes the Python tool — NOT a duplicated PowerShell Select-String regex
    # (per checker issue 6, eliminates drift between regex implementations).
    Write-Host "=== PKG-03 GUARD: subprocess.* usage scan (python tools/check_subprocess_guard.py) ==="
    Invoke-Native { python ..\..\tools\check_subprocess_guard.py 2>&1 | Out-Host }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "BUILD_FAIL reason=pkg03_guard hint='bare subprocess.* call detected; route through musicstreamer/subprocess_utils.py'"
        exit 4
    }
    Write-Host "PKG-03 OK"

    # --- 3b. Spec entry-point guard (PKG-01) ----------------------------
    Write-Host "=== SPEC ENTRY GUARD: python tools/check_spec_entry.py ==="
    Invoke-Native { python ..\..\tools\check_spec_entry.py 2>&1 | Out-Host }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "BUILD_FAIL reason=spec_entry_guard hint='packaging/windows/MusicStreamer.spec is missing the canonical entry-point reference'"
        exit 7
    }

    # --- 4. PyInstaller -------------------------------------------------
    Write-Host "=== MUSICSTREAMER BUILD: pyinstaller ==="
    Invoke-Native { python -m PyInstaller MusicStreamer.spec --noconfirm --log-level INFO --distpath ..\..\dist --workpath build *>&1 | Tee-Object -FilePath "artifacts\build.log" }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "BUILD_FAIL reason=pyinstaller_nonzero exitcode=$LASTEXITCODE"
        exit 2
    }

    Write-Host "BUILD_OK step=pyinstaller exe='$here\..\..\dist\MusicStreamer\MusicStreamer.exe'"

    # --- 5. Smoke test --------------------------------------------------
    if (-not $SkipSmoke) {
        Write-Host "=== MUSICSTREAMER BUILD: smoke test (--version) ==="
        # MusicStreamer is a GUI app; the smoke step is a launch-and-exit sanity check
        # only when a smoke harness exists. Default behavior is to skip in this phase
        # since UAT (Plan 05) handles full functional verification.
        Write-Host "BUILD_INFO smoke_skipped=ui_app reason='UAT covers functional verification'"
    }

    # --- 6. Inno Setup compile (D-01, D-07) -----------------------------
    Write-Host "=== INNO SETUP: compile installer ==="

    # Read version from pyproject.toml (D-06) — passed to iscc.exe as /DAppVersion
    $pyproject = Get-Content "..\..\pyproject.toml" -Raw
    if ($pyproject -match '(?ms)^\[project\].*?^version\s*=\s*"([^"]+)"') {
        $appVersion = $matches[1]
    } else {
        Write-Error "BUILD_FAIL reason=version_not_found_in_pyproject"
        exit 5
    }
    Write-Host "AppVersion = $appVersion"

    # Locate iscc.exe — default install path; allow override via env var.
    $isccPath = if ($env:INNO_SETUP_PATH) {
        $env:INNO_SETUP_PATH
    } else {
        "C:\Program Files (x86)\Inno Setup 6\iscc.exe"
    }
    if (-not (Test-Path $isccPath)) {
        Write-Error "BUILD_FAIL reason=iscc_not_found path='$isccPath' hint='install Inno Setup 6 from jrsoftware.org or set INNO_SETUP_PATH env var'"
        exit 6
    }

    Invoke-Native {
        & $isccPath "/DAppVersion=$appVersion" "MusicStreamer.iss" 2>&1 | Tee-Object -FilePath "artifacts\iscc.log"
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "BUILD_FAIL reason=iscc_nonzero exitcode=$LASTEXITCODE"
        exit 6
    }

    $installerPath = "..\..\dist\installer\MusicStreamer-$appVersion-win64-setup.exe"
    Write-Host "BUILD_OK installer='$installerPath'"

    # --- 7. Diagnostic (bundle size, DLL count) -------------------------
    $bundleSize = (Get-ChildItem "..\..\dist\MusicStreamer" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
    $dllCount = (Get-ChildItem "..\..\dist\MusicStreamer\_internal\*.dll").Count
    $installerSize = (Get-Item $installerPath).Length / 1MB
    Write-Host ("BUILD_DIAG bundle_size_mb={0:N1} dll_count={1} installer_size_mb={2:N1}" -f $bundleSize, $dllCount, $installerSize)
}
finally {
    Pop-Location
}

Write-Host "BUILD_OK step=done"
exit 0
