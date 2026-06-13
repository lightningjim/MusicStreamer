#Requires -Version 5.1
# Phase 44 MusicStreamer Windows build driver. Idempotent, snapshot-safe.
# Adapted from .planning/phases/43-gstreamer-windows-spike/build.ps1.
# Exit codes: 0=ok, 1=env missing, 2=pyinstaller failed, 3=smoke test failed,
#             4=PKG-03 guard fail, 5=version parse fail, 6=iscc fail, 7=spec entry guard fail,
#             8=pre-bundle clean fail, 9=post-bundle dist-info assertion fail,
#             10=post-bundle plugin-presence guard fail (Phase 69)
#             11=smtc backend not loaded in frozen bundle (Phase 88.1 / WIN-02)
#             12=oauth helper entrypoint unreachable in frozen bundle (Phase 88.2 / D-05)
#             14=oauth_helper.exe WebEngine missing from isolated helper bundle (Phase 88.3 / B1 / G6)

param(
    # Default: if inside a conda env, use its Library tree; else fall back to the MSVC installer path.
    [string]$GstRoot = $(if ($env:CONDA_PREFIX) { "$env:CONDA_PREFIX\Library" } else { "C:\spike-gst\runtime" }),
    [switch]$SkipSmoke      = $false,
    # 88.1 WR-02: bypass the step-4c SMTC smoke guard (exit 11), mirroring -SkipSmoke.
    # The guard is active by default; this switch only exists for build iteration on a
    # VM where the SMTC check is being debugged independently of the bundle contents.
    [switch]$SkipSmtcGuard  = $false,
    # 88.2 D-05 / WR-02: bypass the step-4d oauth-helper guard (exit 12), mirroring -SkipSmtcGuard.
    # The guard is active by default; this switch exists for build iteration on a
    # VM where the oauth-helper dispatch is being debugged independently of the bundle.
    [switch]$SkipOauthGuard = $false,
    [switch]$SkipPipInstall = $(if ($env:CONDA_PREFIX) { $true } else { $false }),
    # 88.3-04 B1: path to a conda-free Python 3.12 exe used to create the isolated
    # oauth_helper venv. The helper build MUST NOT run under the conda env (B1 isolation).
    # Options:
    #   ""                              -- use `py -3.12` (python.org Windows launcher)
    #   "C:\path\to\python.exe"         -- python.org Python 3.12 direct path
    #   "<conda>\envs\helper-iso\python.exe" -- clean conda-forge env (no Qt/GStreamer)
    # See packaging/windows/README.md B1 section for setup instructions.
    [string]$HelperPythonExe = ""
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
# It ALSO stringifies any ErrorRecord output that the inner block emits  --  even with
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
    # This step invokes the Python tool  --  NOT a duplicated PowerShell Select-String regex
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
    # NOTE (Plan 65-05): commands use `python -m pip` rather than `uv pip`
    # because the validated Win11 build env is conda-forge spike (per
    # .claude/skills/spike-findings-musicstreamer/), which does NOT
    # provision the uv CLI. `python -m pip` works in any conda env AND
    # any uv-managed venv on Linux dev. Drift-guard test in
    # tests/test_packaging_spec.py asserts the `python -m pip` literal.
    Write-Host "=== PRE-BUNDLE CLEAN: python -m pip uninstall + reinstall musicstreamer ==="
    Invoke-Native { python -m pip uninstall musicstreamer -y 2>&1 | Out-Host }
    # Note: uninstall exit code is intentionally NOT checked -- python -m pip
    # uninstall returns non-zero if the package isn't installed, which
    # is fine on a fresh build env. We only care about the install
    # below succeeding.
    Invoke-Native { python -m pip install -e ..\.. 2>&1 | Out-Host }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "BUILD_FAIL reason=pre_bundle_clean_failed hint='python -m pip install -e ..\..\\ failed; check pip install + pyproject.toml validity'" -ForegroundColor Red
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

    # Phase 65 WR-04: the bare `musicstreamer-*.dist-info` wildcard
    # over-matches sibling distributions like `musicstreamer-extras-*.dist-info`
    # or `musicstreamer-cli-*.dist-info` (PEP 503 normalizes underscores
    # to dashes, so `musicstreamer_extras` would normalize to
    # `musicstreamer-extras` for its dist-info dir name). To future-proof
    # against a hypothetical sibling tripping a false-positive `exit 9`
    # ("not_singleton"), enumerate broadly first (so we can dump
    # discovered siblings into the failure log for diagnostics) but then
    # restrict to entries matching `musicstreamer-<X.Y.Z>.dist-info`
    # exactly  --  the only shape PyInstaller produces for OUR package.
    $msDistInfosBroad = @(Get-ChildItem -Path $bundleInternal -Filter "musicstreamer-*.dist-info" -Directory -ErrorAction SilentlyContinue)
    $msDistInfos = @($msDistInfosBroad | Where-Object { $_.Name -match '^musicstreamer-\d+\.\d+\.\d+\.dist-info$' })
    if ($msDistInfos.Count -ne 1) {
        Write-Host "POST-BUNDLE ASSERTION FAIL: expected exactly one musicstreamer-<X.Y.Z>.dist-info, found $($msDistInfos.Count) matching:" -ForegroundColor Red
        $msDistInfos | ForEach-Object { Write-Host "  match  - $($_.Name)" }
        if ($msDistInfosBroad.Count -ne $msDistInfos.Count) {
            Write-Host "  (broad enumeration also saw $($msDistInfosBroad.Count) musicstreamer-*.dist-info entries; non-matching siblings excluded:)"
            $msDistInfosBroad | Where-Object { $_.Name -notmatch '^musicstreamer-\d+\.\d+\.\d+\.dist-info$' } | ForEach-Object { Write-Host "  reject - $($_.Name)" }
        }
        Write-Host "BUILD_FAIL reason=post_bundle_distinfo_not_singleton found_count=$($msDistInfos.Count) broad_count=$($msDistInfosBroad.Count) hint='step 3c pre-bundle clean did not leave a single musicstreamer-X.Y.Z.dist-info -- investigate build env site-packages'" -ForegroundColor Red
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

    # --- 4b. Post-bundle plugin-presence guard (Phase 69 / G-01 / WIN-05) ---
    # Validates that AAC-required GStreamer plugin DLLs landed in the bundle.
    # Without this, a future docs-drift regression (e.g. a maintainer drops
    # gst-libav from the conda recipe in packaging/windows/README.md) would
    # silently produce a bundle that fails AAC playback at runtime with only
    # the generic "Playback error" toast as a signal -- the empirical Phase 56
    # F2 finding (56-05-UAT-LOG.md).
    #
    # Required plugin list is single-sourced from tools/check_bundle_plugins.py
    # REQUIRED_PLUGIN_DLLS dict (also imported by
    # tests/test_packaging_spec.py P-01 drift-guard pytest).
    #
    # DO NOT REMOVE without first updating both:
    #   - tests/test_packaging_spec.py (P-01 drift-guard test)
    #   - .planning/phases/69-debug-why-aac-streams-aren-t-playing-in-windows-possibly-mis/69-01-PLAN.md (this plan's rationale)
    Write-Host "=== POST-BUNDLE PLUGIN GUARD: python tools/check_bundle_plugins.py (Phase 69 / WIN-05) ==="
    Invoke-Native { python ..\..\tools\check_bundle_plugins.py --bundle ..\..\dist\MusicStreamer\_internal 2>&1 | Out-Host }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "BUILD_FAIL reason=plugin_missing hint='see tools/check_bundle_plugins.py output above; add the named conda-forge package to packaging/windows/README.md conda recipe'" -ForegroundColor Red
        exit 10
    }
    Write-Host "POST-BUNDLE PLUGIN GUARD OK"

    # --- 4c. SMTC smoke guard (Phase 88.1 / D-05 / WIN-02) -----------------
    # Assert that WindowsMediaKeysBackend (not NoOpMediaKeysBackend) constructs
    # in the frozen exe. A winrt bundling failure degrades silently to NoOp
    # (D-03 logging makes this diagnosable), so this build-time check makes
    # the failure LOUD at build time. Only runs on Windows  --  skip this guard
    # on Linux (the exe is not runnable on Linux; this block is always reached
    # on the Windows build VM in the 88-03 session).
    #
    # Phase 65 WR-01: use Write-Host (NOT Write-Error) + exit 11.
    # $ErrorActionPreference = "Stop" escalates Write-Error to a terminating
    # error  --  the documented `exit 11` line never fires; script returns 1.
    if (-not $SkipSmtcGuard) {
        Write-Host "=== SMTC SMOKE GUARD: assert WindowsMediaKeysBackend in frozen bundle (Phase 88.1 / D-05 / WIN-02) ==="
        Invoke-Native {
            & "..\..\dist\MusicStreamer\MusicStreamer.exe" --check-mediakeys 2>&1 | Out-Host
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "BUILD_FAIL reason=smtc_backend_not_loaded hint='MusicStreamer.exe --check-mediakeys returned non-zero; winrt import failed in frozen bundle; check build.log for ImportError from media_keys factory'" -ForegroundColor Red
            exit 11
        }
        Write-Host "SMTC SMOKE GUARD OK"
    } else {
        Write-Host "SMTC SMOKE GUARD skipped (-SkipSmtcGuard)"
    }

    # --- 4d. OAUTH HELPER GUARD -----------------------------------------
    # Phase 88.2 D-05: assert the frozen exe can dispatch --oauth-helper so
    # GBS.FM / Twitch / Google in-app login is reachable at runtime. Mirrors
    # the step-4c SMTC guard pattern. Exit 12 = oauth helper entrypoint
    # unreachable in frozen bundle (see exit-codes header above).
    #
    # Phase 65 WR-01: use Write-Host (NOT Write-Error) + exit 12.
    # $ErrorActionPreference = "Stop" escalates Write-Error to a terminating
    # error  --  the documented `exit 12` line never fires; script returns 1.
    if (-not $SkipOauthGuard) {
        Write-Host "=== OAUTH HELPER GUARD: assert frozen exe can dispatch --oauth-helper (Phase 88.2 / D-05) ==="
        Invoke-Native {
            & "..\..\dist\MusicStreamer\MusicStreamer.exe" --oauth-helper --self-test 2>&1 | Out-Host
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "BUILD_FAIL reason=oauth_helper_entrypoint_unreachable hint='MusicStreamer.exe --oauth-helper --self-test returned non-zero; __main__.py dispatch did not reach _run_oauth_helper'" -ForegroundColor Red
            exit 12
        }
        Write-Host "OAUTH HELPER GUARD OK"
    } else {
        Write-Host "OAUTH HELPER GUARD skipped (-SkipOauthGuard)"
    }

    # --- 4e. HELPER BUILD (Phase 88.3-04 / B1 / G6) -------------------------
    # Build the SECOND PyInstaller artifact: oauth_helper.exe from an ISOLATED
    # pip venv (no conda Qt, no GStreamer). The helper carries QtWebEngine for
    # all in-app OAuth logins (GBS.FM / Twitch / Google). The conda main bundle
    # has NO WebEngine (B1 invariant; conda-forge ships no PySide6 WebEngine
    # bindings). See packaging/windows/README.md B1 section + spike 001.
    #
    # ISOLATION IS LOAD-BEARING: the helper venv uses a conda-free Python 3.12
    # so pip installs an ABI-self-consistent Qt (pip Qt6Core + pip Qt6WebEngineCore
    # from the same build). Mixing conda Qt with pip WebEngine caused the G6
    # DLL-load failure (Phase 88.3 root cause). Use -HelperPythonExe to specify
    # the venv provider.
    #
    # Phase 65 WR-01: Write-Host (NOT Write-Error) + exit 14.
    Write-Host "=== HELPER BUILD: isolated pip venv + oauth_helper_standalone.spec (Phase 88.3-04 / B1) ==="

    $HelperVenv = Join-Path $here ".venv-oauth-helper"

    if ($HelperPythonExe -ne "") {
        if (-not (Test-Path $HelperPythonExe)) {
            Write-Host "BUILD_FAIL reason=helper_python_not_found path='$HelperPythonExe' hint='check -HelperPythonExe path'" -ForegroundColor Red
            exit 14
        }
        if (-not (Test-Path $HelperVenv)) {
            Write-Host "Creating isolated helper venv from -HelperPythonExe: $HelperPythonExe ..." -ForegroundColor Cyan
            $helperPyVer = & $HelperPythonExe -c "import sys;print('%d.%d'%sys.version_info[:2])"
            Write-Host "  (helper provider python is $helperPyVer)" -ForegroundColor Cyan
            Invoke-Native { & $HelperPythonExe -m venv $HelperVenv *>&1 | Out-Host }
        }
    } else {
        if (-not (Test-Path $HelperVenv)) {
            Write-Host "Creating isolated helper venv (py -3.12) ..." -ForegroundColor Cyan
            Invoke-Native { py -3.12 -m venv $HelperVenv *>&1 | Out-Host }
        }
    }

    if (-not (Test-Path $HelperVenv)) {
        Write-Host "BUILD_FAIL reason=helper_venv_creation_failed hint='No conda-free Python 3.12 found. Options: (1) winget install -e --id Python.Python.3.12 then re-run; (2) conda create -y -n helper-iso -c conda-forge python=3.12 pip then pass -HelperPythonExe to this script'" -ForegroundColor Red
        exit 14
    }

    $HelperVenvPy = Join-Path $HelperVenv "Scripts\python.exe"

    # --- B1 build-time PATH isolation (Phase 88.3 G6 root-cause fix) ----------
    # CRITICAL: step 0 prepends conda's Library\bin to $env:PATH so the MAIN
    # conda bundle's bundler can introspect GStreamer DLLs. But the isolated
    # helper is pip-only PySide6 and must NOT see conda Qt. PyInstaller resolves
    # each collected DLL's transitive imports (Qt6Core.dll, Qt6Gui.dll, ...) via
    # the BUILD-TIME PATH -- so with conda's Library\bin on PATH it bakes conda's
    # Qt6Core.dll into the helper bundle next to pip's WebEngine .pyd -> ABI
    # mismatch -> "the specified procedure could not be found" at runtime, in
    # EVERY environment (the Phase 88.3 G6 signature; reproduced at 88.3-05 UAT).
    # The spike (001) avoided this by building with conda fully deactivated.
    # Reproduce that clean-PATH condition: strip conda/miniforge/$GstRoot from
    # PATH for the helper pip-install + PyInstaller, then restore for the Inno
    # step. The helper python/pip/PyInstaller are all invoked via the explicit
    # $HelperVenvPy path, so none of them depend on PATH -- only DLL dependency
    # resolution does, which is exactly what we are steering back to the pip venv.
    $SavedPath = $env:PATH
    $env:PATH = ($env:PATH -split ';' | Where-Object {
        $_ -and
        $_ -notmatch '(?i)conda|miniforge|miniconda' -and
        $_ -notmatch '(?i)\\Library\\bin' -and
        $_ -notlike "$GstRoot*"
    }) -join ';'
    Write-Host "HELPER BUILD: PATH sanitized (conda/GStreamer stripped for ABI-clean helper) -> $env:PATH" -ForegroundColor DarkGray

    Write-Host "pip install -r oauth-helper-requirements.txt into isolated helper venv ..." -ForegroundColor Cyan
    Invoke-Native { & $HelperVenvPy -m pip install --upgrade pip *>&1 | Tee-Object -FilePath "artifacts\helper-pip.log" }
    Invoke-Native { & $HelperVenvPy -m pip install -r oauth-helper-requirements.txt *>&1 | Tee-Object -Append -FilePath "artifacts\helper-pip.log" }
    if ($LASTEXITCODE -ne 0) {
        $env:PATH = $SavedPath
        Write-Host "BUILD_FAIL reason=helper_pip_install_failed hint='pip install -r oauth-helper-requirements.txt failed in isolated venv; check artifacts\helper-pip.log'" -ForegroundColor Red
        exit 14
    }

    Write-Host "pyinstaller oauth_helper_standalone.spec (isolated helper venv, clean PATH) ..." -ForegroundColor Cyan
    # --clean discards any cached analysis from a prior conda-contaminated build,
    # so the sanitized-PATH dependency resolution is authoritative (no stale
    # conda Qt6Core lingering in the build-helper workpath).
    Invoke-Native { & $HelperVenvPy -m PyInstaller oauth_helper_standalone.spec --clean --noconfirm --distpath ..\..\dist --workpath build-helper *>&1 | Tee-Object -FilePath "artifacts\helper-build.log" }
    if ($LASTEXITCODE -ne 0) {
        $env:PATH = $SavedPath
        Write-Host "BUILD_FAIL reason=helper_pyinstaller_failed exitcode=$LASTEXITCODE hint='check artifacts\helper-build.log'" -ForegroundColor Red
        exit 14
    }
    $env:PATH = $SavedPath   # restore conda/GStreamer PATH for the Inno step

    if (-not (Test-Path "..\..\dist\oauth_helper\oauth_helper.exe")) {
        Write-Host "BUILD_FAIL reason=helper_exe_not_found hint='pyinstaller produced no dist\oauth_helper\oauth_helper.exe; check artifacts\helper-build.log'" -ForegroundColor Red
        exit 14
    }

    # Assert WebEngine binaries present in the helper bundle (T-88.3-04-01).
    # PyInstaller 6.x onedir nests under _internal; fall back to flat layout.
    $helperBundle = "..\..\dist\oauth_helper"
    $helperProc = Join-Path $helperBundle "_internal\PySide6\QtWebEngineProcess.exe"
    $helperCore = Join-Path $helperBundle "_internal\PySide6\Qt6WebEngineCore.dll"
    if (-not (Test-Path $helperProc)) { $helperProc = Join-Path $helperBundle "PySide6\QtWebEngineProcess.exe" }
    if (-not (Test-Path $helperCore)) { $helperCore = Join-Path $helperBundle "PySide6\Qt6WebEngineCore.dll" }
    if (-not (Test-Path $helperProc)) {
        Write-Host "BUILD_FAIL reason=helper_webengine_missing file=QtWebEngineProcess.exe hint='WebEngine hook did not fire -- check PySide6-Addons is in the isolated venv (not conda PySide6); see artifacts\helper-build.log'" -ForegroundColor Red
        exit 14
    }
    if (-not (Test-Path $helperCore)) {
        Write-Host "BUILD_FAIL reason=helper_webengine_missing file=Qt6WebEngineCore.dll hint='WebEngine DLL not bundled -- check PySide6-Addons is in the isolated venv; see artifacts\helper-build.log'" -ForegroundColor Red
        exit 14
    }

    # --- ABI-coherence guard (Phase 88.3 G6 root-cause regression catch) -------
    # The presence checks above only prove the WebEngine DLLs EXIST -- not that
    # they are the pip venv's own (ABI-self-consistent) Qt. The G6 failure was a
    # WRONG-version Qt6Core.dll baked in from conda's Library\bin on the build
    # PATH, which passes every presence check but fails at runtime with "the
    # specified procedure could not be found". Assert the bundled Qt6Core.dll is
    # byte-identical to the isolated venv's pip Qt6Core.dll -- if a future change
    # re-contaminates the build PATH, this fails here instead of at a VM UAT.
    $bundledQt6Core = Join-Path $helperBundle "_internal\PySide6\Qt6Core.dll"
    if (-not (Test-Path $bundledQt6Core)) { $bundledQt6Core = Join-Path $helperBundle "PySide6\Qt6Core.dll" }
    $venvQt6Core = Join-Path $HelperVenv "Lib\site-packages\PySide6\Qt6Core.dll"
    # An unresolvable path is a HARD FAILURE, not a skip: the G6 regression this
    # guard exists to catch (a wrong-ABI Qt6Core.dll) could coincide with a
    # PyInstaller layout change that makes a copy unlocatable, so a silent skip
    # would ship the very broken bundle the guard is meant to block. If we cannot
    # prove ABI coherence, fail the build (Phase 88.3 WR-01).
    if (-not ((Test-Path $bundledQt6Core) -and (Test-Path $venvQt6Core))) {
        Write-Host "BUILD_FAIL reason=helper_qt6core_abi_guard_indeterminate bundled='$bundledQt6Core' venv='$venvQt6Core' hint='could not locate both Qt6Core.dll copies; the _internal\PySide6 layout or venv site-packages path may have changed -- cannot prove ABI coherence, refusing to ship an unverifiable bundle.'" -ForegroundColor Red
        exit 14
    }
    $bundledHash = (Get-FileHash -Algorithm SHA256 $bundledQt6Core).Hash
    $venvHash    = (Get-FileHash -Algorithm SHA256 $venvQt6Core).Hash
    if ($bundledHash -ne $venvHash) {
        Write-Host "BUILD_FAIL reason=helper_qt6core_abi_mismatch bundled='$bundledQt6Core' venv='$venvQt6Core' hint='bundled Qt6Core.dll is NOT the isolated pip venv Qt -- conda/foreign Qt leaked onto the build PATH (Phase 88.3 G6). The helper PyInstaller step must run with conda stripped from PATH; see the B1 build-time PATH isolation block above.'" -ForegroundColor Red
        exit 14
    }
    Write-Host "HELPER ABI GUARD OK -- bundled Qt6Core.dll matches isolated pip venv (SHA256 $($venvHash.Substring(0,12))...)"

    Write-Host "HELPER BUILD OK -- QtWebEngineProcess.exe + Qt6WebEngineCore.dll present in dist\oauth_helper"

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

    # Locate iscc.exe  --  default install path; allow override via env var.
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
