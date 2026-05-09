#Requires -Version 5.1
# Phase 44 MusicStreamer Windows build driver. Idempotent, snapshot-safe.
# Adapted from .planning/phases/43-gstreamer-windows-spike/build.ps1.
# Exit codes: 0=ok, 1=env missing, 2=pyinstaller failed, 3=smoke test failed,
#             4=PKG-03 guard fail, 5=version parse fail, 6=iscc fail, 7=spec entry guard fail,
#             8=pre-bundle clean fail, 9=post-bundle dist-info assertion fail

param(
    # Default: if inside a conda env, use its Library tree; else fall back to the MSVC installer path.
    [string]$GstRoot = $(if ($env:CONDA_PREFIX) { "$env:CONDA_PREFIX\Library" } else { "C:\spike-gst\runtime" }),
    [switch]$SkipSmoke      = $false,
    [switch]$SkipPipInstall = $(if ($env:CONDA_PREFIX) { $true } else { $false })
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Phase 65 WR-01: BUILD_FAIL paths use `Write-Host ... -ForegroundColor Red`
# (NOT `Write-Error`) followed by `exit N`. With $ErrorActionPreference =
# "Stop", `Write-Error` is escalated to a TERMINATING error -- the script
# unwinds through the surrounding try/finally as an unhandled exception and
# PowerShell emits its default exit code 1, never reaching the documented
# `exit N` line that follows. CI / wrapper scripts that branch on
# $LASTEXITCODE (e.g. exit 8 -> uv install fail, exit 9 -> dist-info drift)
# would all see 1 instead of the codes documented at the top of this
# script. Using Write-Host emits the diagnostic to the host stream without
# terminating, so the explicit `exit N` actually fires.
#
# Windows PowerShell 5.1 treats native-command stderr writes as terminating errors
# when $ErrorActionPreference = "Stop". PyInstaller, pip, and MusicStreamer.exe all log
# INFO/DEBUG to stderr. Invoke-Native wraps a native call with Continue semantics
# and propagates $LASTEXITCODE so explicit checks still fire on real failures.
#
# It ALSO stringifies any ErrorRecord output that the inner block emits — even with
# `*>&1` redirection, PS 5.1 keeps stderr as ErrorRecord objects, which the host
# formats as red "command : message / At ... char:NN" blocks when they reach the
# console. Forcing them to plain strings inside the pipeline gives clean white
# output that's still tee-able to a logfile.
function Invoke-Native {
    param([scriptblock]$Block)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Block | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) { "$($_.Exception.Message)" }
            else { $_ }
        }
    } finally { $ErrorActionPreference = $prev }
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
    Write-Host "BUILD_FAIL reason=gst_runtime_missing path='$GstRoot'" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path "$GstRoot\bin\gst-inspect-1.0.exe")) {
    Write-Host "BUILD_FAIL reason=gst_inspect_missing hint='reinstall with Complete feature set'" -ForegroundColor Red
    exit 1
}
# 1.28.x ships OpenSSL-backed TLS on Windows (gioopenssl.dll); 1.24/1.26 shipped GnuTLS (libgiognutls.dll).
$tlsDll = "$GstRoot\lib\gio\modules\gioopenssl.dll"
$legacyTlsDll = "$GstRoot\lib\gio\modules\libgiognutls.dll"
if (-not ((Test-Path $tlsDll) -or (Test-Path $legacyTlsDll))) {
    Write-Host "BUILD_FAIL reason=gio_tls_module_missing hint='reinstall with Complete feature set; expected gioopenssl.dll (1.28+) or libgiognutls.dll (1.26-)'" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path "$GstRoot\libexec\gstreamer-1.0\gst-plugin-scanner.exe")) {
    Write-Host "BUILD_FAIL reason=gst_plugin_scanner_missing path='$GstRoot\libexec\gstreamer-1.0\gst-plugin-scanner.exe'" -ForegroundColor Red
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
        Write-Host "BUILD_FAIL reason=pkg03_guard hint='bare subprocess.* call detected; route through musicstreamer/subprocess_utils.py'" -ForegroundColor Red
        exit 4
    }
    Write-Host "PKG-03 OK"

    # --- 3b. Spec entry-point guard (PKG-01) ----------------------------
    Write-Host "=== SPEC ENTRY GUARD: python tools/check_spec_entry.py ==="
    Invoke-Native { python ..\..\tools\check_spec_entry.py 2>&1 | Out-Host }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "BUILD_FAIL reason=spec_entry_guard hint='packaging/windows/MusicStreamer.spec is missing the canonical entry-point reference'" -ForegroundColor Red
        exit 7
    }

    # --- 3c. Pre-bundle dist-info clean (VER-02-J defense) -------------
    # PyInstaller's `copy_metadata("musicstreamer")` (MusicStreamer.spec
    # line 41) picks up EVERY musicstreamer-*.dist-info directory it
    # finds on sys.path. If the build env has both the current
    # 2.1.{phase}.dist-info AND a stale older dist-info (e.g. from a
    # previous v1.x or v2.0.x editable install that was never cleaned),
    # BOTH ship into dist/MusicStreamer/_internal/, and at runtime
    # importlib.metadata.version("musicstreamer") returns whichever
    # appears first on sys.path -- typically the older one (e.g. 1.1.0
    # observed on Kyle's Win11 VM during Phase 65 UAT, gap VER-02-J).
    #
    # Defense: uninstall + reinstall musicstreamer right before
    # pyinstaller runs, guaranteeing exactly one fresh dist-info
    # matching pyproject.toml [project].version exists when
    # copy_metadata scans. Cheap (~3-5s); makes the build resilient to
    # whatever historical state the build env happens to be in.
    #
    # DO NOT REMOVE without first updating both:
    #   - tests/test_packaging_spec.py (drift-guard test)
    #   - .planning/phases/65-.../65-04-PLAN.md (this plan's rationale)
    Write-Host "=== PRE-BUNDLE CLEAN: uv pip uninstall + reinstall musicstreamer ==="
    Invoke-Native { uv pip uninstall musicstreamer -y 2>&1 | Out-Host }
    # Note: uninstall exit code is intentionally NOT checked -- uv pip
    # uninstall returns non-zero if the package isn't installed, which
    # is fine on a fresh build env. We only care about the install
    # below succeeding.
    Invoke-Native { uv pip install -e ..\.. 2>&1 | Out-Host }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "BUILD_FAIL reason=pre_bundle_clean_failed hint='uv pip install -e ..\..\\ failed; check uv install + pyproject.toml validity'" -ForegroundColor Red
        exit 8
    }
    Write-Host "PRE-BUNDLE CLEAN OK -- fresh musicstreamer dist-info materialized in build env"

    # --- 4. PyInstaller -------------------------------------------------
    Write-Host "=== MUSICSTREAMER BUILD: pyinstaller ==="
    Invoke-Native { python -m PyInstaller MusicStreamer.spec --noconfirm --log-level INFO --distpath ..\..\dist --workpath build *>&1 | Tee-Object -FilePath "artifacts\build.log" }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "BUILD_FAIL reason=pyinstaller_nonzero exitcode=$LASTEXITCODE" -ForegroundColor Red
        exit 2
    }

    Write-Host "BUILD_OK step=pyinstaller exe='$here\..\..\dist\MusicStreamer\MusicStreamer.exe'"

    # --- 4a. Post-bundle dist-info assertion (VER-02-J defense) ---------
    # Belt-and-braces guard: even with step 3c's pre-bundle clean, a
    # build-env edge case could in theory leave a stale
    # musicstreamer-*.dist-info in site-packages (e.g. uv pip uninstall
    # missed an older virtualenv layer, or a parallel build dropped a
    # rogue dist-info into the search path). PyInstaller's copy_metadata
    # would then pick up BOTH and ship BOTH into the bundle, and at
    # runtime importlib.metadata would resolve to whichever appears first
    # on sys.path inside the bundle.
    #
    # This step inspects the produced bundle directly and fails the
    # build if either:
    #   (a) the bundle does not contain exactly ONE
    #       musicstreamer-*.dist-info directory, OR
    #   (b) that directory's METADATA `Version:` line does not equal
    #       pyproject.toml [project].version.
    #
    # On failure, the offending state is dumped to the build log so a
    # future maintainer can diagnose without re-running the build.
    #
    # DO NOT REMOVE without first updating both:
    #   - tests/test_packaging_spec.py (drift-guard test)
    #   - .planning/phases/65-.../65-04-PLAN.md (this plan's rationale)
    Write-Host "=== POST-BUNDLE ASSERTION: musicstreamer dist-info singleton + version match ==="

    # Read pyproject.toml [project].version (D-06) -- single source of
    # truth shared with step 6 / iscc.exe. Lifted from the original step
    # 6 location so step 4a can compare bundled METADATA Version: to it
    # without duplicating the regex.
    $pyproject = Get-Content "..\..\pyproject.toml" -Raw
    # Phase 65 WR-02: anchor the version match to the contiguous [project]
    # block (no `[` between the table header and the matched line) so a
    # future edit that introduces a sibling table with its own `version`
    # key (e.g. `[tool.foo] version = "x"`) cannot win the lazy `.*?`
    # match. `[^\[]*?` is non-greedy AND forbids opening another table,
    # confining the match to the [project] section.
    if ($pyproject -match '(?ms)^\[project\][^\[]*?^version\s*=\s*"([^"]+)"') {
        $appVersion = $matches[1]
    } else {
        Write-Host "BUILD_FAIL reason=version_not_found_in_pyproject hint='expected ^version = `"...`" inside the [project] table before any subsequent table header'" -ForegroundColor Red
        exit 5
    }
    Write-Host "AppVersion = $appVersion"

    # Bundle layout: PyInstaller --distpath ..\..\dist + spec name 'MusicStreamer'
    # produces dist/MusicStreamer/_internal/<dist-info>/.
    $bundleInternal = "..\..\dist\MusicStreamer\_internal"
    if (-not (Test-Path $bundleInternal)) {
        Write-Host "BUILD_FAIL reason=bundle_internal_not_found path='$bundleInternal' hint='pyinstaller produced an unexpected layout; check build.log'" -ForegroundColor Red
        exit 9
    }

    $msDistInfos = @(Get-ChildItem -Path $bundleInternal -Filter "musicstreamer-*.dist-info" -Directory -ErrorAction SilentlyContinue)
    if ($msDistInfos.Count -ne 1) {
        Write-Host "POST-BUNDLE ASSERTION FAIL: expected exactly one musicstreamer-*.dist-info, found $($msDistInfos.Count):" -ForegroundColor Red
        $msDistInfos | ForEach-Object { Write-Host "  - $($_.Name)" }
        Write-Host "BUILD_FAIL reason=post_bundle_distinfo_not_singleton found_count=$($msDistInfos.Count) hint='step 3c pre-bundle clean did not leave a single dist-info -- investigate build env site-packages'" -ForegroundColor Red
        exit 9
    }

    $bundledDistInfo = $msDistInfos[0]
    $bundledMetadata = Join-Path $bundledDistInfo.FullName "METADATA"
    if (-not (Test-Path $bundledMetadata)) {
        Write-Host "BUILD_FAIL reason=bundled_metadata_missing path='$bundledMetadata' hint='dist-info shipped without METADATA file -- corrupt install?'" -ForegroundColor Red
        exit 9
    }

    $bundledVersion = $null
    foreach ($line in (Get-Content $bundledMetadata)) {
        if ($line -match '^Version:\s*(.+?)\s*$') {
            $bundledVersion = $matches[1]
            break
        }
    }
    if (-not $bundledVersion) {
        Write-Host "BUILD_FAIL reason=bundled_metadata_no_version_line path='$bundledMetadata' hint='METADATA file present but has no Version: line'" -ForegroundColor Red
        exit 9
    }

    if ($bundledVersion -ne $appVersion) {
        Write-Host "POST-BUNDLE ASSERTION FAIL: dist-info version drift detected" -ForegroundColor Red
        Write-Host "  pyproject.toml [project].version : $appVersion"
        Write-Host "  bundled METADATA Version:        : $bundledVersion"
        Write-Host "  bundled dist-info dir name        : $($bundledDistInfo.Name)"
        Write-Host "BUILD_FAIL reason=post_bundle_version_mismatch bundled='$bundledVersion' expected='$appVersion' hint='step 3c pre-bundle clean did not refresh dist-info -- investigate uv pip uninstall behavior'" -ForegroundColor Red
        exit 9
    }

    Write-Host "POST-BUNDLE ASSERTION OK -- dist-info singleton: $($bundledDistInfo.Name) (version $bundledVersion matches pyproject)"

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

    # $appVersion was read from pyproject.toml at step 4a (single source
    # of truth shared with the post-bundle dist-info assertion).
    # /DAppVersion is the Inno Setup macro consumer (D-06).

    # Locate iscc.exe — default install path; allow override via env var.
    $isccPath = if ($env:INNO_SETUP_PATH) {
        $env:INNO_SETUP_PATH
    } else {
        "C:\Program Files (x86)\Inno Setup 6\iscc.exe"
    }
    if (-not (Test-Path $isccPath)) {
        Write-Host "BUILD_FAIL reason=iscc_not_found path='$isccPath' hint='install Inno Setup 6 from jrsoftware.org or set INNO_SETUP_PATH env var'" -ForegroundColor Red
        exit 6
    }

    Invoke-Native {
        & $isccPath "/DAppVersion=$appVersion" "MusicStreamer.iss" 2>&1 | Tee-Object -FilePath "artifacts\iscc.log"
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "BUILD_FAIL reason=iscc_nonzero exitcode=$LASTEXITCODE" -ForegroundColor Red
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
