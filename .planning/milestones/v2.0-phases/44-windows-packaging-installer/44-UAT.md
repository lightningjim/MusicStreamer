---
phase: 44
plan: 05
status: signed-off
created: 2026-04-25
updated: 2026-04-25
---

# Phase 44 — Windows UAT (Packaging + Installer)

> Runs on the Win11 VM used during Phases 43 + 43.1. Sign off every row before marking Phase 44 complete.
>
> Workflow: build the installer with `packaging\windows\build.ps1` on the VM, then walk through D-20 (playback) and D-21 (installer/round-trip) item-by-item. Replace each `☐` with ✅ (pass) or ❌ (fail with notes), then mark `status: signed-off` in the frontmatter and commit.

## Environment Snapshot

Captured on Win11 VM:

```
Windows: (from `winver`)
Python: (from `python --version`; expected 3.12.x conda-forge)
Conda env: musicstreamer-build (or spike — whichever holds the build deps per Phase 43)
Inno Setup: (from `iscc.exe /?` first line; expected 6.3.x)
Node.js: (from `node --version`; required for UAT-20-4 only; removable for UAT-20-5)
pip list | findstr "PySide6 winrt yt-dlp streamlink pyinstaller":
  (paste)
```

## Build Artifacts

| Artifact | Path | Size | Verified |
|----------|------|------|----------|
| PyInstaller bundle | `dist\MusicStreamer\` | (~110 MB; DLL count ~126; plugins ~184) | ☐ |
| Inno Setup installer | `dist\installer\MusicStreamer-2.0.0-win64-setup.exe` | (single EXE) | ☐ |
| `build.log` tail | `artifacts\build.log` | — | ☐ `BUILD_OK installer='...'` + `BUILD_DIAG bundle_size_mb=... dll_count=... installer_size_mb=...` present |
| `iscc.log` | `artifacts\iscc.log` | — | ☐ `Successful compile` line |

## D-20 Playback Checklist

| # | Behavior | Requirement | Method | Pass/Fail | Notes |
|---|----------|-------------|--------|-----------|-------|
| UAT-20-1 | SomaFM HTTPS (Drone Zone) plays; ICY title updates within ~30s | PKG-01 | Select SomaFM → Drone Zone; wait 30s for ICY tag | ☐ | |
| UAT-20-2 | HLS stream plays end-to-end | PKG-01 | Select any HLS station in library | ☐ | |
| UAT-20-3 | DI.fm over HTTP plays (HTTPS expected to fail per D-15) | PKG-01 / D-15 | Select DI.fm channel with HTTP URL | ☐ | HTTPS waiver per D-15 acceptable; HTTP must pass. |
| UAT-20-4 | YouTube live with Node.js on PATH (LoFi Girl-style) plays via yt-dlp EJS solver | RUNTIME-01 / PKG-01 | Confirm `node --version` succeeds; play YT live URL | ☐ | |
| UAT-20-5 | YouTube live WITHOUT Node.js: all three warning surfaces appear — (a) startup QMessageBox dialog, (b) hamburger menu shows "⚠ Node.js: Missing (click to install)", (c) toast on YT play attempt "Install Node.js for YouTube playback". Non-YT streams still work. | RUNTIME-01 / D-13 | In a fresh cmd, `set PATH=...` to remove Node, relaunch app, attempt YT play; restore PATH after | ☐ | All three surfaces required. |
| UAT-20-6 | Twitch live plays via streamlink (requires valid OAuth token from Phase 32) | PKG-01 | Select Twitch station with token in user profile | ☐ | |
| UAT-20-7 | Multi-stream failover: primary URL fail → next stream in `order_streams()` order picks up | PKG-01 | Edit a station's primary URL to invalid, play it | ☐ | |
| UAT-20-8 | SMTC: hardware media keys (play/pause/stop) work; overlay shows station name + ICY title + cover art (station logo) | PKG-01 / MEDIA-03 | Press hardware media keys during playback; open volume flyout to view SMTC overlay | ☐ | Regression check vs. Phase 43.1 UAT. |

## D-21 Installer / Round-Trip Checklist

| # | Behavior | Requirement | Method | Pass/Fail | Notes |
|---|----------|-------------|--------|-----------|-------|
| UAT-21-1 | Fresh Win11 VM snapshot → `MusicStreamer-2.0.0-win64-setup.exe` runs → Start Menu shortcut exists at `%APPDATA%\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk` → launch via shortcut succeeds | PKG-02 | Revert VM snapshot, run installer, verify shortcut, launch via Start Menu | ☐ | |
| UAT-21-1.5 | iscc compiles `MusicStreamer.iss` with the `AppId={{914e9cb6-f320-478a-a2c4-e104cd450c88}` 3-brace literal (info-level pattern_compliance check per checker issue 7) | PKG-02 / RESEARCH §Pitfall 4 | On the build host (or VM) run `iscc MusicStreamer.iss` and observe acceptance. **Pass:** iscc compiles cleanly with the 3-brace form. **Fail:** iscc emits a syntax error citing `AppId` or unbalanced braces — switch the literal to the 4-brace form `AppId={{{{914e9cb6-f320-478a-a2c4-e104cd450c88}}` per RESEARCH §Pitfall 4, recompile, and document in Notes. Record `iscc /?` first line (version) and the literal that compiled. | ☐ | iscc version: ____ ; accepted literal: ____ . Note: `BUILD_OK installer=...` from build.ps1 already implies iscc accepted whatever form is present, but this row explicitly records the brace-count decision so future maintainers know which form is canonical for this Inno Setup version. |
| UAT-21-2 | Settings → Apps → Uninstall MusicStreamer; install dir `%LOCALAPPDATA%\MusicStreamer` removed; user data `%APPDATA%\musicstreamer\musicstreamer.sqlite3` and assets PRESERVED (D-03 invariant) | D-03 / PKG-02 | Run uninstaller, then `dir %LOCALAPPDATA%\MusicStreamer` (expect missing) and `dir %APPDATA%\musicstreamer` (expect SQLite + assets) | ☐ | |
| UAT-21-3 | Re-install over nothing succeeds | PKG-02 | Re-run installer after uninstall | ☐ | |
| UAT-21-4 | Settings export Linux→Windows round-trip preserves stations/streams/favorites/tags/logos | QA-03 / SC-6 | On Linux dev box, hamburger menu → Export Settings → save ZIP; copy ZIP to Win11 VM; on Windows installed app, hamburger menu → Import Settings → select ZIP → confirm summary dialog → import; verify all data visible AND playable | ☐ | |
| UAT-21-5 | Settings export Windows→Linux round-trip preserves stations/streams/favorites/tags/logos | QA-03 / SC-6 | Reverse — export from Windows installed app, copy ZIP back to Linux, import; verify same | ☐ | |
| UAT-21-6 | Single-instance: with app running, double-click Start Menu shortcut a second time → existing window raises and gets focus (no second window, no error dialog) | PKG-04 / D-09 | Launch app, then double-click Start Menu shortcut again | ☐ | |
| UAT-21-7 | AUMID/SMTC: overlay shows "MusicStreamer" (NOT "Unknown app"). Required: launched via Start Menu shortcut. Bare `python -m musicstreamer` from cmd will still show "Unknown app" — expected per Phase 43.1. | D-04 / PKG-02 | Launch via Start Menu shortcut, start playback, open SMTC overlay (volume flyout) | ☐ | |

## Build Instructions (run before checklist)

1. RDP/SSH into Win11 VM. Activate the conda env that holds the Phase 43 build deps:
   ```
   conda activate musicstreamer-build
   cd \path\to\MusicStreamer\packaging\windows
   ```
2. Run the build:
   ```
   .\build.ps1
   ```
   
   Expected output:
   - `PKG-03 OK: zero bare subprocess.* calls in musicstreamer/`
   - PyInstaller produces `..\..\dist\MusicStreamer\` (~110 MB, ~126 DLLs, ~184 plugins)
   - Inno Setup produces `..\..\dist\installer\MusicStreamer-2.0.0-win64-setup.exe`
   - `BUILD_OK installer='..\..\dist\installer\MusicStreamer-2.0.0-win64-setup.exe'`
   - `BUILD_DIAG bundle_size_mb=... dll_count=... installer_size_mb=...`
3. If build fails: paste exit code + log excerpt into the Build Artifacts section above. Common failures:
   - `BUILD_FAIL reason=iscc_not_found` → install Inno Setup 6 from https://jrsoftware.org/isdl.php OR set `$env:INNO_SETUP_PATH = "C:\Path\To\iscc.exe"`
   - `BUILD_FAIL reason=version_not_found_in_pyproject` → confirm pyproject.toml line 7 reads `version = "2.0.0"` (Plan 02 should have set this)
   - PyInstaller `ModuleNotFoundError: ... yt_dlp.extractor.foo` → add the specific extractor to `.spec` `hiddenimports` + rerun

## Sign-Off

- [X] All D-20 items pass (DI.fm HTTPS waiver per D-15 acceptable)
- [X] All D-21 items pass (including UAT-21-1.5 AppId brace-form acceptance)
- [X] No new tracebacks in `%LOCALAPPDATA%\musicstreamer\musicstreamer\diagnostics.log` from this UAT session (the app writes user data under `platformdirs.user_data_dir` = `%LOCALAPPDATA%\musicstreamer\musicstreamer\` on Windows, NOT under `%APPDATA%\musicstreamer\logs\`; that subfolder does not exist. `diagnostics.log` was added Phase 44 for YT/Twitch worker exception logging — only file to check.)
- [X] QA-05 audit doc reviewed (`44-QA05-AUDIT.md`)

After all rows checked, set `status: signed-off` in the frontmatter and commit.

**Signed off by:** Kyle Creasey
**Date:** 2026-04-25

    