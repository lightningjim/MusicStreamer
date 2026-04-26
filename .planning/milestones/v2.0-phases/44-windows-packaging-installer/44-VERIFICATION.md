---
phase: 44-windows-packaging-installer
verified: 2026-04-25T17:30:00Z
status: passed
score: 13/13 static must-haves verified; 6/6 ROADMAP success criteria via UAT (signed off 2026-04-25)
overrides_applied: 0
re_verification: null  # initial verification
human_verification:
  - test: "UAT-21-1: Run installer on clean Win11 VM"
    expected: "MusicStreamer-2.0.0-win64-setup.exe installs to %LOCALAPPDATA%\\MusicStreamer; Start Menu shortcut at %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\MusicStreamer.lnk; launch via shortcut succeeds"
    why_human: "Requires Win11 VM with conda-forge env + Inno Setup 6.3+; cannot be exercised from Linux dev box"
  - test: "UAT-21-1.5: iscc compile of MusicStreamer.iss with 3-brace AppId form"
    expected: "iscc accepts AppId={{914e9cb6-...} or fall back to 4-brace form per Pitfall 4; record iscc version + accepted literal"
    why_human: "Requires Inno Setup compiler on Windows host"
  - test: "UAT-21-2: Uninstall preserves user data (D-03 invariant)"
    expected: "%LOCALAPPDATA%\\MusicStreamer removed; %APPDATA%\\musicstreamer\\musicstreamer.sqlite3 + assets PRESERVED"
    why_human: "Requires installed/uninstalled state on Win11"
  - test: "UAT-21-3: Re-install over nothing succeeds"
    expected: "Installer runs cleanly post-uninstall"
    why_human: "Win11 VM only"
  - test: "UAT-21-4: Settings export round-trip Linux→Windows (SC-6)"
    expected: "ZIP exported on Linux, copied to Win11, imported via hamburger menu; stations/streams/favorites/tags/logos all visible AND playable"
    why_human: "Cross-platform file transfer + live import flow"
  - test: "UAT-21-5: Settings export round-trip Windows→Linux (SC-6)"
    expected: "Reverse direction preserves all data"
    why_human: "Cross-platform"
  - test: "UAT-21-6: Single-instance activate-existing-window behavior"
    expected: "Second double-click of Start Menu shortcut raises + focuses existing window; no second window; no error"
    why_human: "QLocalServer named-pipe semantics + Windows focus-steal behavior need live shell environment"
  - test: "UAT-21-7: AUMID/SMTC display name is 'MusicStreamer' (not 'Unknown app')"
    expected: "When launched via Start Menu shortcut, SMTC overlay shows 'MusicStreamer'. Bare python -m musicstreamer still shows 'Unknown app' (expected per 43.1)"
    why_human: "Windows shell binds AUMID via the registered shortcut; only verifiable on Windows with a real shortcut"
  - test: "UAT-20-1: SomaFM Drone Zone HTTPS plays + ICY title within 30s"
    expected: "Audible playback; ICY title visible in now-playing panel"
    why_human: "Live audio + ICY metadata over network"
  - test: "UAT-20-2: HLS stream plays end-to-end"
    expected: "Audible HLS playback"
    why_human: "Live network audio"
  - test: "UAT-20-3: DI.fm over HTTP plays (HTTPS waiver per D-15)"
    expected: "HTTP URL plays; HTTPS limitation documented in README"
    why_human: "Server-side; live audio"
  - test: "UAT-20-4: YouTube live with Node.js on PATH plays via yt-dlp + EJS"
    expected: "Live YouTube stream resolves and plays"
    why_human: "Requires Node.js + live yt-dlp resolution"
  - test: "UAT-20-5: Three Node.js missing surfaces appear (startup dialog + hamburger indicator + YT-fail toast)"
    expected: "All three RUNTIME-01 UI surfaces visible; non-YT streams still play"
    why_human: "Requires PATH manipulation on Windows + visual UI inspection"
  - test: "UAT-20-6: Twitch live plays via streamlink with valid OAuth token"
    expected: "Live Twitch playback"
    why_human: "Live stream + OAuth token"
  - test: "UAT-20-7: Multi-stream failover picks next stream on primary URL fail"
    expected: "Failover walks order_streams() order"
    why_human: "Live failure injection + observation"
  - test: "UAT-20-8: SMTC media keys + overlay (station + ICY + cover art)"
    expected: "Hardware media keys play/pause/stop; overlay shows full metadata"
    why_human: "Windows SMTC integration; live media-key hardware"
---

# Phase 44: Windows Packaging + Installer Verification Report

**Phase Goal:** Produce a Windows installer EXE that installs MusicStreamer with all dependencies; single-instance enforcement works; no console windows appear; Node.js is documented as a host prerequisite (not bundled).

**Verified:** 2026-04-25T17:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria + plan-level must_haves)

| #   | Truth                                                                                                                                                                                       | Status                                  | Evidence                                                                                                                                                                |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | SC-1: NSIS/Inno Setup installer EXE installs the app to `%LOCALAPPDATA%\MusicStreamer` with a Start Menu shortcut                                                                            | ⚠️ STATIC OK / LIVE PENDING             | `.iss` + `.spec` + `build.ps1` + `.ico` all present; `DefaultDirName={localappdata}\MusicStreamer`, Start Menu shortcut with AUMID confirmed in .iss. Live build/install requires Win11 VM (UAT-21-1) |
| 2   | SC-2: Launching a second instance activates the running window instead of opening a duplicate                                                                                                 | ⚠️ STATIC OK / LIVE PENDING             | `single_instance.py` 162 lines; `acquire_or_forward()` + `raise_and_focus()` + FlashWindowEx fallback present; tests pass (3/3); wired into `_run_gui` after QApplication. Live double-click test pending (UAT-21-6) |
| 3   | SC-3: Installer documents Node.js prerequisite (RUNTIME-01) and fails gracefully if Node.js missing                                                                                            | ✓ VERIFIED                              | `runtime_check.py` 96 lines; `check_node()` + `show_missing_node_dialog()`; MainWindow hamburger indicator + YT-fail toast both wired; `packaging/windows/README.md` documents the prerequisite; integration tests pass (3/3 toast/indicator + 1/1 dialog) |
| 4   | SC-4: PKG-03 is a no-op at ship time; no bare subprocess.{Popen,run,call} outside `subprocess_utils.py`                                                                                       | ✓ VERIFIED                              | `python tools/check_subprocess_guard.py` exits 0; `tests/test_pkg03_compliance.py` passes; `build.ps1` invokes the same Python tool (single source of truth per checker issue 6) |
| 5   | SC-5: Windows smoke test passes (ShoutCast HTTPS, HLS, YouTube via yt-dlp+EJS, Twitch via streamlink, failover, media keys, installer round-trip)                                              | ❓ HUMAN NEEDED                          | All 8 D-20 items in 44-UAT.md `☐` (unchecked); requires Win11 VM execution                                                                                              |
| 6   | SC-6: Phase 42 settings export round-trip Linux↔Windows preserves stations/streams/favorites/tags/logos                                                                                        | ❓ HUMAN NEEDED                          | UAT-21-4 + UAT-21-5 in 44-UAT.md `☐` (unchecked); requires Win11 VM + cross-platform file copy                                                                          |
| 7   | PLAN: Single-instance via QLocalServer/QLocalSocket with named-pipe (Win) / unix-socket (Linux) semantics                                                                                     | ✓ VERIFIED                              | `single_instance.py:25` imports QLocalServer/QLocalSocket; `SERVER_NAME = "org.lightningjim.MusicStreamer.single-instance"` matches D-08; `removeServer()` + `setSocketOptions(UserAccessOption)` present |
| 8   | PLAN: Node.js detection returns a NodeRuntime dataclass with available + path; win32 prefers `node.exe` (CPython #109590)                                                                     | ✓ VERIFIED                              | `runtime_check.py:34-37` `@dataclass(frozen=True) class NodeRuntime`; `_which_node()` lines 51-61 prefers `shutil.which("node.exe")` on win32                          |
| 9   | PLAN: pyproject.toml version is 2.0.0 + `__version__.py` mirrors                                                                                                                              | ✓ VERIFIED                              | `pyproject.toml:7` = `version = "2.0.0"`; `musicstreamer/__version__.py` = `__version__ = "2.0.0"`                                                                     |
| 10  | PLAN: GUI entry order is _set_windows_aumid → Gst.init → migration → QApplication → single_instance → check_node → MainWindow → activate_requested wiring → window.show → app.exec            | ✓ VERIFIED                              | `__main__.py:130-175` exact order; line 153 (`acquire_or_forward`) < line 161 (`check_node`) < line 170 (`MainWindow(player, repo, node_runtime=node_runtime)`) < line 171 (`activate_requested.connect`) |
| 11  | PLAN: MainWindow accepts `node_runtime` kwarg; hamburger menu shows "⚠ Node.js: Missing (click to install)" when absent; YT-fail toast says "Install Node.js for YouTube playback"            | ✓ VERIFIED                              | `main_window.py:108` `node_runtime=None`; `:115` stores; `:184-189` conditional QAction; `:354-358` early-return branch in `_on_playback_error`; `:363` `_on_node_install_clicked` handler |
| 12  | PLAN: AUMID literal in `__main__.py` and `MusicStreamer.iss` exactly match (case-sensitive — Pitfall 1)                                                                                       | ✓ VERIFIED                              | Both contain `org.lightningjim.MusicStreamer` exactly (`grep -c` returns 1+ in each); .iss line 65 sets `AppUserModelID: "org.lightningjim.MusicStreamer"` on the Start Menu shortcut |
| 13  | PLAN: Inno Setup AppId pinned with double-open-brace literal (Pitfall 4)                                                                                                                       | ⚠️ STATIC OK / iscc COMPILE PENDING     | `MusicStreamer.iss:11` = `AppId={{914e9cb6-f320-478a-a2c4-e104cd450c88}` (3-brace form). UAT-21-1.5 records whether iscc accepts this form or requires 4-brace fallback |
| 14  | PLAN: PyInstaller .spec entry point is `../../musicstreamer/__main__.py`; required hidden imports present (PySide6.QtNetwork, QtSvg, winrt.windows.media etc.)                                | ✓ VERIFIED                              | `MusicStreamer.spec:79` Analysis entry; lines 86-100 hiddenimports list; `python tools/check_spec_entry.py` exits 0; `tests/test_spec_hidden_imports.py` passes              |
| 15  | PLAN: QA-05 widget-lifetime audit complete with subclass inventory + dialog launch sites + callback flow + UAT-log regression check                                                            | ✓ VERIFIED (with caveat)                | `44-QA05-AUDIT.md` 162 lines, 4 sections, 23 subclass rows, 9 dialog launch sites, 13 callback rows, NONE UAT regressions. **Caveat:** audit scope is `musicstreamer/ui_qt/` only — does NOT explicitly cover `single_instance.py` (which post-mid-phase-fix uses bound-method `_on_socket_ready` via `self.sender()` — substantively QA-05 compliant) |
| 16  | PLAN: 44-UAT.md template ready for Win11 VM execution with D-20 + D-21 checklists                                                                                                              | ✓ VERIFIED (template); ❓ EXECUTION PENDING | `44-UAT.md` 96 lines, 21 unchecked checkboxes (8 D-20 + 8 D-21 + 4 sign-off + 1 build artifacts row); `status: in-progress` in frontmatter; UAT-21-1.5 added per checker issue 7 |
| 17  | PLAN: All 5 plans merged with SUMMARY.md per plan                                                                                                                                              | ✓ VERIFIED                              | 5 SUMMARY.md files present; commits 257fd9d, 2e51ae1, a5c22d2, f557c94, 78e8ece, f1b03cd, 890b93c, ad5f8d6, 8a7bf12, e4587a6 all in `git log` |

**Score:** 13/13 static must-haves verified; 6 ROADMAP SCs static parts complete, 4 SCs (SC-1, SC-2, SC-5, SC-6) require live Win11 VM verification.

### Required Artifacts

| Artifact                                                  | Expected                                                       | Status     | Details                                                                                                                                                       |
| --------------------------------------------------------- | -------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `musicstreamer/single_instance.py`                        | SingleInstanceServer + SERVER_NAME + acquire_or_forward + raise_and_focus | ✓ VERIFIED | 162 lines; all symbols exported; QA-05 compliant (bound method dispatch via sender()); post-mid-phase-fix `socket.setParent(self)` pattern present (line 53)         |
| `musicstreamer/runtime_check.py`                          | NodeRuntime dataclass + check_node + show_missing_node_dialog + NODEJS_INSTALL_URL | ✓ VERIFIED | 96 lines; CPython #109590 mitigation present (line 51-61); module-level enum capture (lines 29-31) makes show_missing_node_dialog robust to test fakes        |
| `musicstreamer/__version__.py`                            | `__version__ = "2.0.0"` literal                                | ✓ VERIFIED | Present + correct                                                                                                                                             |
| `pyproject.toml`                                          | `version = "2.0.0"`                                            | ✓ VERIFIED | Line 7                                                                                                                                                        |
| `musicstreamer/__main__.py`                               | _run_gui wires single_instance + runtime_check + node_runtime kwarg + activate_requested.connect | ✓ VERIFIED | Lines 149-175; smoke path (`_run_smoke`) untouched                                                                                                            |
| `musicstreamer/ui_qt/main_window.py`                      | node_runtime kwarg + hamburger indicator + YT-fail toast + _on_node_install_clicked | ✓ VERIFIED | Lines 108, 115, 184-189, 354-358, 363                                                                                                                         |
| `packaging/windows/MusicStreamer.spec`                    | Analysis entry + hiddenimports + console=False + upx=False + icon | ✓ VERIFIED | 165 lines; all required strings present; `tests/test_spec_hidden_imports.py` passes                                                                           |
| `packaging/windows/runtime_hook.py`                       | GIO_EXTRA_MODULES + GI_TYPELIB_PATH + GST_PLUGIN_SCANNER       | ✓ VERIFIED | 55 lines; verbatim from Phase 43 spike + cosmetic diag prefix rename                                                                                          |
| `packaging/windows/build.ps1`                             | PyInstaller + PKG-03 guard via Python tool + iscc + diagnostics | ✓ VERIFIED | 173 lines; line 93 invokes `python ..\..\tools\check_subprocess_guard.py` (single source of truth per checker issue 6); no Select-String regex duplication    |
| `packaging/windows/MusicStreamer.iss`                     | AppId pinned + PrivilegesRequired=lowest + AppUserModelID match + no UninstallDelete | ✓ VERIFIED | 80 lines; all invariants present; AUMID exact match with `__main__.py`                                                                                        |
| `packaging/windows/EULA.txt`                              | LGPL/yt-dlp/streamlink/Qt/Node.js attributions                 | ✓ VERIFIED | Present                                                                                                                                                       |
| `packaging/windows/README.md`                             | Build runbook + DI.fm + AUMID + Node.js + SmartScreen notes    | ✓ VERIFIED | Present                                                                                                                                                       |
| `packaging/windows/icons/MusicStreamer.ico`               | 6-resolution multi-size .ico                                   | ✓ VERIFIED | `file` reports MS Windows icon resource; `identify` confirms 16/32/48/64/128/256                                                                              |
| `tools/check_subprocess_guard.py` + `tools/check_spec_entry.py` | Build-time guards exit 0 on clean tree, exit 4/7 on violations | ✓ VERIFIED | Both exit 0 on current tree; `subprocess_utils.py` exclusion present                                                                                          |
| `.planning/phases/44-windows-packaging-installer/44-QA05-AUDIT.md` | Subclass inventory + dialog launch sites + callback flow + UAT-log regression | ✓ VERIFIED (with caveat) | 162 lines; clean. **Caveat:** scope = `musicstreamer/ui_qt/`; does not explicitly enumerate `single_instance.py` callbacks (substantively compliant — bound-method dispatch via sender()) |
| `.planning/phases/44-windows-packaging-installer/44-UAT.md` | D-20 + D-21 checklists + Environment Snapshot + Sign-Off       | ✓ VERIFIED (template); ❓ EXECUTION PENDING | 96 lines; 21 ☐ unchecked; status: in-progress (Win11 VM session pending)                                                                                       |

### Key Link Verification

| From                                            | To                                                              | Via                                                                | Status   | Details                                                                                                                                                       |
| ----------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `__main__._run_gui`                             | `single_instance.acquire_or_forward`                            | lazy import + call after QApplication                              | ✓ WIRED  | Line 152-153                                                                                                                                                  |
| `__main__._run_gui`                             | `runtime_check.check_node`                                      | lazy import + call before MainWindow                               | ✓ WIRED  | Line 160-161                                                                                                                                                  |
| `__main__._run_gui`                             | `single_instance.raise_and_focus`                               | server.activate_requested.connect with parameter-only lambda capturing window | ✓ WIRED  | Line 171-173                                                                                                                                                  |
| `MainWindow`                                    | `node_runtime` kwarg → conditional hamburger QAction            | if `node_runtime is not None and not node_runtime.available`       | ✓ WIRED  | main_window.py:184-189                                                                                                                                        |
| `MainWindow._on_playback_error`                 | `show_toast("Install Node.js for YouTube playback")`            | early-return branch when "YouTube resolve failed" + node missing   | ✓ WIRED  | main_window.py:354-358; regression guard in `test_player_emits_expected_yt_failure_prefix` confirms `player.py:557` matches the substring                     |
| `MusicStreamer.iss` Start Menu shortcut         | `__main__._set_windows_aumid` AUMID literal                     | both equal `org.lightningjim.MusicStreamer` (Pitfall 1)            | ✓ WIRED  | grep match in both files                                                                                                                                      |
| `MusicStreamer.spec` Analysis entry             | `musicstreamer/__main__.py`                                     | `"../../musicstreamer/__main__.py"` literal                        | ✓ WIRED  | spec line 79; `tools/check_spec_entry.py` exits 0                                                                                                             |
| `build.ps1`                                     | `tools/check_subprocess_guard.py`                               | PowerShell invokes Python tool (single source of truth, issue 6)  | ✓ WIRED  | build.ps1:93                                                                                                                                                  |
| `build.ps1`                                     | `iscc.exe`                                                      | reads version from pyproject.toml regex; passes /DAppVersion       | ✓ WIRED  | build.ps1:131-153; INNO_SETUP_PATH env var override supported                                                                                                 |

### Data-Flow Trace (Level 4)

| Artifact                          | Data Variable | Source                                                                                                                | Produces Real Data | Status     |
| --------------------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------ | ---------- |
| `runtime_check.NodeRuntime`       | `path`        | `_which_node()` → `shutil.which("node.exe")` / `shutil.which("node")` (live OS PATH lookup)                            | yes (live PATH)    | ✓ FLOWING  |
| `MainWindow._node_runtime`        | NodeRuntime   | `_run_gui` constructs via `runtime_check.check_node()` and passes through kwarg                                        | yes                | ✓ FLOWING  |
| `single_instance.SERVER_NAME`     | str constant  | module constant (D-08)                                                                                                | yes (deterministic) | ✓ FLOWING |
| `MusicStreamer.iss` AppVersion    | str           | `build.ps1` regex extracts from pyproject.toml `[project].version`, passes as `/DAppVersion=2.0.0`                     | yes                | ✓ FLOWING  |
| `MusicStreamer.spec` GST_ROOT     | Path          | `os.environ.get("GSTREAMER_ROOT", default)`; `build.ps1` sets it from `$CONDA_PREFIX\Library`                          | yes (build env)    | ✓ FLOWING (build-time only) |

No HOLLOW_PROP or DISCONNECTED artifacts. The Node.js detection chain (PATH → check_node → NodeRuntime → MainWindow kwarg → hamburger QAction / toast) is fully wired and exercised by integration tests.

### Behavioral Spot-Checks

| Behavior                                                                  | Command                                                                                                       | Result                                              | Status |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- | ------ |
| PKG-03 guard tool exits 0 on clean tree                                   | `python tools/check_subprocess_guard.py`                                                                      | `PKG-03 OK: zero bare subprocess.* calls`; exit=0   | ✓ PASS |
| Spec-entry guard tool exits 0                                             | `python tools/check_spec_entry.py`                                                                            | `PKG-01 OK: spec references "../../musicstreamer/__main__.py"`; exit=0 | ✓ PASS |
| All Phase 44 unit tests pass                                              | `pytest tests/test_single_instance.py tests/test_runtime_check.py tests/ui_qt/test_main_window_node_indicator.py tests/ui_qt/test_missing_node_dialog.py tests/test_pkg03_compliance.py tests/test_spec_hidden_imports.py` | 10 passed                                           | ✓ PASS |
| MainWindow integration tests pass (40 tests)                              | `pytest tests/test_main_window_integration.py`                                                                | 40 passed                                           | ✓ PASS |
| Module imports resolve                                                    | `python -c "from musicstreamer.single_instance import acquire_or_forward; from musicstreamer.runtime_check import check_node, NodeRuntime; from musicstreamer.__version__ import __version__; assert __version__ == '2.0.0'"` | clean import; version 2.0.0                         | ✓ PASS |
| Icon file is valid Windows .ico with all 6 resolutions                    | `file ... && identify ...`                                                                                    | MS Windows icon resource; 16/32/48/64/128/256 all present | ✓ PASS |
| AUMID literal match between __main__.py and MusicStreamer.iss             | `grep -c "org.lightningjim.MusicStreamer"`                                                                    | 1 match in each                                     | ✓ PASS |
| Live build.ps1 → installer EXE produces dist/installer/MusicStreamer-2.0.0-win64-setup.exe | `.\build.ps1` on Win11 VM                                                                                | UAT-21 sequence required                            | ? SKIP (Linux executor; Win11 VM only) |

### Requirements Coverage

| Requirement | Source Plan         | Description                                                                                                                                                                         | Status                          | Evidence                                                                                                                                                       |
| ----------- | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PKG-01      | 44-04               | PyInstaller spec bundles GStreamer Windows runtime DLLs + plugins with HTTPS streams verified working (souphttpsrc SSL CA bundle + libgiognutls.dll/gioopenssl.dll included)         | ⚠️ STATIC OK / LIVE PENDING     | .spec + runtime_hook present; tests/test_spec_hidden_imports.py PASS; verified on Phase 43 spike VM (HTTPS SomaFM); Phase 44 fresh-VM verification = UAT-20-1   |
| PKG-02      | 44-04               | NSIS/Inno Setup installer produces a Windows distributable installing to %LOCALAPPDATA%\MusicStreamer with Start Menu shortcut                                                       | ⚠️ STATIC OK / LIVE PENDING     | .iss present with all invariants; live install = UAT-21-1                                                                                                      |
| PKG-03      | 44-01, 44-04        | All subprocess launches go through `_popen()` helper with CREATE_NO_WINDOW; no console window flashes. As of Plan 35-06 there are zero subprocess calls in `musicstreamer/`         | ✓ SATISFIED                     | `tools/check_subprocess_guard.py` exits 0; `tests/test_pkg03_compliance.py` PASS; `build.ps1` invokes the Python tool                                          |
| PKG-04      | 44-01, 44-02, 44-03 | Single-instance enforcement on both platforms (secondary launches forward activation to running instance)                                                                              | ⚠️ STATIC OK / LIVE PENDING     | `single_instance.py` complete; tests pass; wired into `_run_gui`. Live double-launch = UAT-21-6                                                                |
| PKG-05      | RETIRED             | Original: bundle mpv.exe on Windows                                                                                                                                                  | ✓ RETIRED                       | Plan 35-06 retired; not applicable                                                                                                                              |
| QA-03       | 44-01, 44-05        | Windows smoke test runs on clean Windows VM or manual UAT (station playback, YouTube, Twitch, failover, media keys, installer round-trip)                                            | ❓ NEEDS HUMAN                  | 44-UAT.md template ready with 16 rows; all `☐`; awaits Win11 VM execution                                                                                       |
| QA-05       | 44-05               | Widget lifetime audit performed on all dialog and GStreamer callback flows                                                                                                          | ✓ SATISFIED (with caveat)        | `44-QA05-AUDIT.md` clean. **Caveat:** audit scope = `musicstreamer/ui_qt/`; does not explicitly enumerate `single_instance.py` (substantively compliant — bound-method dispatch via `sender()` after mid-phase fix `a598aca`) |
| RUNTIME-01  | (already complete)  | Node.js host runtime requirement (yt-dlp EJS solver). Already marked complete in REQUIREMENTS.md                                                                                     | ✓ SATISFIED                     | `runtime_check.py` + UI surfaces fulfill the documented-prerequisite intent; tests pass                                                                         |

**Coverage:** All 6 phase requirements (PKG-01, PKG-02, PKG-03, PKG-04, QA-03, QA-05) accounted for. PKG-05 retired (no-op). PKG-03 + QA-05 + RUNTIME-01 fully SATISFIED. PKG-01 + PKG-02 + PKG-04 + QA-03 require Win11 VM live verification (UAT pending).

**No orphaned requirements.** REQUIREMENTS.md maps PKG-01..04, QA-03, QA-05 to Phase 44; all are claimed by the plan frontmatter and verified above.

### Anti-Patterns Found

| File                                          | Line  | Pattern                                                                                  | Severity | Impact                                                                                                                              |
| --------------------------------------------- | ----- | ---------------------------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `.planning/phases/44-windows-packaging-installer/44-UAT.md` | 1-96  | 21 `☐` unchecked checkboxes                                                              | ℹ️ Info  | Expected — UAT execution is the human checkpoint; status: in-progress; will flip to `signed-off` after Win11 VM session            |
| `44-QA05-AUDIT.md`                            | 5     | Scope statement is `musicstreamer/ui_qt/`, does not explicitly include `single_instance.py` | ⚠️ Warning | Mid-phase fix `a598aca` re-architected `_on_new_connection` to use bound-method `_on_socket_ready` dispatching via `self.sender()` — this IS QA-05 compliant by substance, but the audit doc does not enumerate `single_instance.py` callbacks. Recommend a one-line addendum to the audit confirming the post-fix code is reviewed |
| `44-REVIEW.md`                                | 1     | status: `issues_found` (advisory: 0 critical, 2 warnings, 6 info)                        | ℹ️ Info  | Code review is advisory-only and does not block phase completion                                                                    |

No 🛑 Blocker anti-patterns. No empty implementations or hardcoded stubs in production code. The deferred-items.md file documents 3 pre-existing test failures verified reproducible on the Wave 0 base commit (out of Phase 44 scope).

### Human Verification Required

Phase 44 produces a Windows-only deliverable (installer EXE + runtime behaviors). Per CONTEXT.md D-15 the phase scope is "strictly Windows packaging; Linux UAT is out of scope". Per the auto-mode prompt, Plan 05 explicitly defers the human checkpoint (Task 3) — the 44-UAT.md template is populated and awaits operator execution.

**16 UAT items remain unchecked on Win11 VM:**

#### D-20 Playback Checklist (8 items)

1. **UAT-20-1 — SomaFM Drone Zone HTTPS playback + ICY title within 30s**
   - Test: Select SomaFM Drone Zone in installed app; observe ICY title appears
   - Expected: Audible HTTPS playback, ICY metadata visible
   - Why human: Live network audio + ICY metadata observation

2. **UAT-20-2 — HLS stream end-to-end playback**
   - Test: Select an HLS station from library
   - Expected: Audible playback
   - Why human: Live network audio

3. **UAT-20-3 — DI.fm over HTTP plays (HTTPS waiver per D-15)**
   - Test: Select a DI.fm station with HTTP URL
   - Expected: HTTP plays; HTTPS limitation documented and accepted
   - Why human: Live audio; D-15 server-side limitation

4. **UAT-20-4 — YouTube live with Node.js on PATH plays via yt-dlp + EJS**
   - Test: Confirm `node --version` succeeds, then play a LoFi-Girl-style YT live URL
   - Expected: Live YT stream plays via yt-dlp resolution
   - Why human: Requires Node.js + live yt-dlp resolution

5. **UAT-20-5 — YouTube live WITHOUT Node.js: 3 warning surfaces**
   - Test: Remove Node from PATH; relaunch app
   - Expected: (a) startup QMessageBox dialog, (b) hamburger menu shows "⚠ Node.js: Missing (click to install)", (c) toast on YT play attempt "Install Node.js for YouTube playback"; non-YT streams still work
   - Why human: PATH manipulation + visual UI inspection

6. **UAT-20-6 — Twitch live via streamlink with valid OAuth token**
   - Test: Play Twitch station with token in user profile
   - Expected: Live Twitch playback
   - Why human: Live OAuth + streaming

7. **UAT-20-7 — Multi-stream failover**
   - Test: Edit a station's primary URL to invalid; play it
   - Expected: Next stream in `order_streams()` order picks up
   - Why human: Live failure injection + observation

8. **UAT-20-8 — SMTC media keys + overlay**
   - Test: Press hardware media keys; open SMTC overlay
   - Expected: play/pause/stop work; overlay shows station + ICY + cover art
   - Why human: Windows SMTC integration; live media-key hardware

#### D-21 Installer / Round-Trip Checklist (8 items)

9. **UAT-21-1 — Fresh Win11 install via setup.exe + Start Menu shortcut launch**
10. **UAT-21-1.5 — iscc accepts 3-brace AppId form (Pitfall 4 documentation)**
11. **UAT-21-2 — Uninstall preserves user data (D-03 invariant)**
12. **UAT-21-3 — Re-install over nothing**
13. **UAT-21-4 — Settings export Linux→Windows round-trip (SC-6)**
14. **UAT-21-5 — Settings export Windows→Linux round-trip (SC-6)**
15. **UAT-21-6 — Single-instance: second shortcut click raises existing window (PKG-04)**
16. **UAT-21-7 — AUMID/SMTC display name "MusicStreamer" via Start Menu launch**

All 16 items have detailed Method + Pass/Fail + Notes columns in `44-UAT.md`. Operator runs `packaging\windows\build.ps1` on the Win11 VM, walks through the rows, replaces each `☐` with ✅ or ❌, sets `status: signed-off` in the frontmatter, and commits. After sign-off, the milestone closes.

### Gaps Summary

**No actionable gaps.** All static deliverables (code modules, packaging artifacts, build tooling, QA-05 audit, UAT template) are present, tested green on Linux (10 unit tests + 40 integration tests pass; 785 total in full suite, 3 pre-existing failures documented in `deferred-items.md`), and ready to ship.

**One minor recommendation (advisory, non-blocking):** The QA-05 audit doc (44-QA05-AUDIT.md) was written BEFORE the mid-phase fix `a598aca` re-architected `single_instance.py::_on_new_connection` to use bound-method dispatch via `self.sender()`. The post-fix code is QA-05 compliant by substance (bound method, parented socket, no captured lambda capturing self), but the audit document's scope statement explicitly says `musicstreamer/ui_qt/` and does not enumerate `single_instance.py` callbacks. A one-line addendum to the audit confirming review of the post-fix code would tighten the documentation. This is advisory only — does not block phase completion.

**Phase 44 is static-complete.** Ship-readiness is gated on Win11 VM UAT execution (the explicit `checkpoint:human-verify` deferred under `--auto` mode in Plan 05).

---

_Verified: 2026-04-25T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
