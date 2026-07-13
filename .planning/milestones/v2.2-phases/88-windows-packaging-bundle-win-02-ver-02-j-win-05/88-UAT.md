---
status: resolved
phase: 88-windows-packaging-bundle-win-02-ver-02-j-win-05
source: [88-HUMAN-UAT.md, 88.1-HUMAN-UAT.md, 88.2-HUMAN-UAT.md, 88-03-CONSOLIDATED-VM-UAT.md]
session: 88-03 consolidated Win11 VM (Option C)
started: 2026-06-10
updated: 2026-06-13
note: |
  Scoped to the 5 outstanding rows from 88-HUMAN-UAT.md (the other 12 passed on the
  2026-06-06 VM run). Covers phase 88 (G1/G5), 88.1 (G2), 88.2 (G3) in one session.
---

## Current Test

[RESOLVED 2026-06-13 — Tests 6/7/8 (QtWebEngine OAuth logins) all PASS via Phase 88.3's B1 isolated-helper architecture. See `.planning/phases/88.3-bundle-qtwebengine-in-frozen-windows-build-so-oauth-logins-r/88.3-UAT.md` (G6-T6/T7/T8 pass).]

## Tests

### 1. Build + smoke guards (build.ps1)
expected: build.ps1 runs without -Skip flags; step 4c does not exit 11; step 4d prints "OAUTH HELPER GUARD OK" (not exit 12); installer produced at dist\installer\MusicStreamer-2.2.86-win64-setup.exe
result: pass
note: "Initially exit 11 (NoOp fallback) — root cause: [windows] winrt extra not installed in musicstreamer-build env (pywinrt 2.x→3.x split, env never re-synced to the 5 split dists). Resolved with `pip install -e \".[windows]\"`; rebuild gave MEDIAKEYS_BACKEND=WindowsMediaKeysBackend + SMTC SMOKE GUARD OK and OAUTH HELPER GUARD OK. The step-4c/4d guards correctly caught the missing dep pre-ship. FOLLOW-UP: capture [windows] as a build precondition (build.ps1 preflight or packaging README) so a fresh env can't silently ship NoOp. The MUSICSTREAMER_DIAG_RTHOOK 'RemoteException' lines are cosmetic stderr noise (PowerShell NativeCommandError on any native stderr), not failures."

### 2. Bundle plugin guard (UAT-15 / UAT-16)
expected: single PowerShell block — renaming gstlibav.dll then running check_bundle_plugins.py exits 10 with "PHASE-69 FAIL"; after restore, exits 0 with "PHASE-69 OK"
result: pass
note: "exit=10 with 'PHASE-69 FAIL: gstlibav.dll (provides avdec_aac, ships in conda-forge gst-libav)'; after restore exit=0 with 'PHASE-69 OK: all 2 required plugin DLL(s) present'. gstlibav.dll restored. Closes 88 G5/UAT-15 (the original $pluginsDir-empty blocker) + UAT-16."

### 3. Install + dist-info cleanup (UAT-17 / UAT-1b)
expected: after running the 2.2.86 installer over the prior install, _internal holds exactly ONE musicstreamer-*.dist-info named musicstreamer-2.2.86.dist-info (no stale 2.1.x); exactly one MusicStreamer*.lnk in Start Menu
result: pass
note: ".Count=1, .Name=musicstreamer-2.2.86.dist-info (no stale 2.1.68/2.1.84). Shortcut .Count=1. Confirms the [InstallDelete] G1 fix — version mislabel root cause eliminated."

### 4. SMTC overlay shows "MusicStreamer" (UAT-3)
expected: launched via Start-Menu shortcut, playing a station, the Win media flyout shows a media session labelled "MusicStreamer" (not "Unknown app", not absent)
result: pass
note: "Media flyout shows session labelled 'MusicStreamer'. G2 overlay-absent failure resolved — the winrt collect_all bundling + AUMID identity now surface the SMTC session correctly."

### 5. Hardware media keys (UAT-7)
expected: while playing, keyboard media play/pause toggles playback and media-stop stops it
result: pass
note: "Play/pause toggles and media-stop stops. With UAT-3, fully closes G2 (88.1) — SMTC overlay + media keys both functional on the frozen bundle."

### 6. GBS.FM in-app login + playback (UAT-10)
expected: AccountsDialog → GBS.FM login button opens the QtWebEngine login window; auth completes; GBS.FM audio plays. Cookie-import fallback does NOT trigger
result: pass
reported: "RESOLVED in Phase 88.3 (B1 isolated helper) — login window opens from the installed build, auth completes, no exit=2, cookie-import fallback did not trigger."
note: "PROGRESS vs G3 original: the helper now LAUNCHES (88.2 frozen --oauth-helper dispatch works), but the subprocess crashes exit=2. Root cause: oauth_helper.py:62-71 imports PySide6.QtWebEngineWidgets at module level and sys.exit(2) on ImportError. The frozen bundle ships NO QtWebEngine — MusicStreamer.spec has zero WebEngine refs, and only oauth_helper imports it (main app deliberately doesn't per the 'avoid 130MB QtWebEngine in main process' decision), so PyInstaller never collects the WebEngine runtime. The step-4d --self-test guard can't catch this: __main__.py:65 returns 0 BEFORE importing oauth_helper. Shared root cause → Tests 7 (Twitch) + 8 (Google) crash identically. This is a NEW gap distinct from G3's 'won't start' (which 88.2 did fix)."

### 7. Twitch login launches (UAT-10b)
expected: AccountsDialog → Connect Twitch opens the Twitch QtWebEngine login window from the frozen exe
result: pass
reported: "RESOLVED in Phase 88.3 — Twitch login window opens AND Twitch accepts the browser (required the PySide6 6.11.0 Chromium bump to clear Kasada's integrity check). No exit=2."
note: "CONFIRMED on VM — shares root cause with Test 6 (QtWebEngine not bundled; oauth_helper.py module-level QtWebEngineWidgets import → sys.exit(2)). Validates this is not GBS-specific. Verify after the QtWebEngine-bundling fix lands."

### 8. Google/YouTube login launches (UAT-10c)
expected: CookieImportDialog → Google/YouTube login button opens the Google QtWebEngine login window; on failure, a warning points to the File/Paste tabs (no silent dead-end)
result: pass
reported: "RESOLVED in Phase 88.3 — Google/YouTube login window opens from the installed build; no exit=2, no DLL-load failure."
note: "CONFIRMED on VM — shares root cause with Test 6 (QtWebEngine not bundled). NOTE: per CR-01, _on_google_process_error should surface a warning pointing to File/Paste tabs rather than a silent dead-end — worth confirming that error path fires gracefully once observed. Verify after the bundling fix."

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "GBS.FM (and Twitch/Google) in-app login runs in the frozen Windows bundle: the QtWebEngine login window opens and authentication completes"
  status: resolved
  resolution: "Closed by Phase 88.3 (B1 isolated oauth_helper.exe). WebEngine no longer lives in the conda main bundle; it ships in a separate pip-PySide6 helper exe that the main exe launches. Two follow-on defects surfaced at the 88.3-05 VM UAT and were fixed: (1) the helper build baked conda's Qt6Core.dll onto the build PATH → exit=2 (fixed: PATH sanitization + SHA256 ABI guard in build.ps1); (2) Twitch Kasada rejected the Qt 6.10 Chromium (fixed: helper bumped to PySide6 6.11.0). All three logins PASS from the installed build — see 88.3-UAT.md."
  reason: "User reported: 'Login helper crashed unexpectedly' exit=2. Helper now LAUNCHES (88.2 dispatch fix works) but crashes immediately."
  severity: blocker
  test: 6
  root_cause: "oauth_helper.py:62-71 imports PySide6.QtWebEngineWidgets at module level and calls sys.exit(2) on ImportError. The PyInstaller frozen bundle ships NO QtWebEngine: MusicStreamer.spec has zero WebEngine references (no QtWebEngineWidgets hiddenimport, no QtWebEngineProcess.exe / resources / locales collected). Only oauth_helper imports QtWebEngine — the main app deliberately doesn't (130MB-startup-avoidance decision) — and the import sits in a try/except, so PyInstaller's modulegraph never reliably collects the WebEngine runtime. The step-4d OAUTH HELPER GUARD (--self-test) cannot detect this because __main__.py:65 returns 0 before importing oauth_helper."
  artifacts:
    - path: "packaging/windows/MusicStreamer.spec"
      issue: "No QtWebEngine bundling — needs PySide6.QtWebEngineWidgets hiddenimport + QtWebEngine runtime (QtWebEngineProcess.exe, qtwebengine_resources*.pak, ICU data, locales, translations) collected. Pattern mirrors the winrt collect_all fix (88.1)."
    - path: "packaging/windows/build.ps1"
      issue: "Step-4d guard is too shallow (--self-test short-circuits). Consider a deeper guard that actually imports oauth_helper / QWebEngineView in the frozen exe so missing WebEngine fails the build, not the user."
  missing:
    - "Bundle QtWebEngine in MusicStreamer.spec (hiddenimport + collect WebEngine runtime/data)"
    - "Verify PySide6 QtWebEngine is installed in the musicstreamer-build env (env-provisioning fork — pending VM diagnostic)"
    - "Deepen the oauth-helper build guard to catch a missing WebEngine runtime"
  diagnostic_result: "CONFIRMED env fork — `python -c \"from PySide6.QtWebEngineWidgets import QWebEngineView\"` in musicstreamer-build raises ModuleNotFoundError. QtWebEngine is NOT installed in the build env. Strong lead: the env has PySide6-Essentials (no WebEngine) but not PySide6-Addons (which ships QtWebEngineWidgets) — OR conda pyside6 without qt6-webengine. Next: `pip list | Select-String 'PySide6|shiboken'` to confirm Essentials-vs-Addons. NOTE the Linux dev path uses apt python3-pyside6.qtwebenginewidgets (oauth_helper.py:67), so the Windows env was provisioned differently and never got the addon."
  fix_shape: "(1) Provision QtWebEngine in musicstreamer-build (likely `pip install PySide6-Addons` to match the installed PySide6 version, or conda qt6-webengine). (2) Likely STILL add explicit WebEngine bundling to MusicStreamer.spec — the import is try/except + subprocess-reached, so PyInstaller's PySide6 hook may not auto-collect the ~130MB runtime (QtWebEngineProcess.exe, qtwebengine_resources*.pak, ICU, locales). Mirror the 88.1 winrt collect_all pattern. (3) Deepen the step-4d build guard to actually import oauth_helper/QWebEngineView in the frozen exe (the --self-test short-circuit is why this shipped green). (4) Document [windows] winrt extra + QtWebEngine as build-env preconditions."

- truth: "Twitch login opens from the frozen exe"
  status: resolved
  resolution: "Closed by Phase 88.3. Twitch login window opens AND Twitch accepts the browser after the helper PySide6 6.11.0 (Chromium) bump cleared Kasada's integrity check. See 88.3-UAT.md test 3."
  reason: "User confirmed on VM — also fails to launch web login. Shares root cause with test 6 (QtWebEngine not bundled)."
  severity: blocker
  test: 7

- truth: "Google/YouTube login opens from the frozen exe"
  status: resolved
  resolution: "Closed by Phase 88.3. Google/YouTube login window opens from the installed build; no exit=2, no DLL-load failure. See 88.3-UAT.md test 4."
  reason: "User confirmed on VM — also fails to launch web login. Shares root cause with test 6. Verify graceful _on_google_process_error path after fix."
  severity: blocker
  test: 8
