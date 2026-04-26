# Phase 44: Windows Packaging + Installer - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Wrap the Phase 43-validated GStreamer bundle in a **Windows installer EXE** that:
- Installs MusicStreamer to `%LOCALAPPDATA%\MusicStreamer` (per-user, `PrivilegesRequired=lowest`)
- Registers a Start Menu shortcut whose `System.AppUserModel.ID=org.lightningjim.MusicStreamer` matches the in-process AUMID set in `musicstreamer/__main__.py::_set_windows_aumid`
- Enforces single-instance with activate-existing-window behavior
- Documents Node.js as a host prerequisite (not bundled) and surfaces the requirement clearly at runtime
- Passes a clean-Win11-VM smoke test + a Linux↔Windows settings export round-trip (SC-6)

**In scope:** Inno Setup installer script, PyInstaller `.spec` + `runtime_hook.py` + `build.ps1` port from Phase 43 spike, Windows AUMID shortcut wiring, single-instance (`QLocalServer`), Node.js detection + UX, pyproject version bump to 2.0.0, QA-05 widget-lifetime audit, Windows UAT execution.

**Out of scope (this phase):** Linux packaging (AppImage/Flatpak — v2.1+), code signing (v2.1+), auto-updater (v2.1+), CI automation of the Windows build, aggressive GStreamer plugin pruning, per-URL HTTPS→HTTP fallback in `player.py`.

</domain>

<decisions>
## Implementation Decisions

### Installer Tool + Structure
- **D-01:** Installer tool: **Inno Setup**. Pascal-style `.iss` script, first-class per-user install mode, built-in `Tasks` / `Icons` section supports `AppUserModelID` shortcut property. One `.iss` file under `packaging/windows/`.
- **D-02:** Install location: **`%LOCALAPPDATA%\MusicStreamer`** (`PrivilegesRequired=lowest`, no admin elevation). `AppId={{GUID}}` pinned so upgrades detect prior install via registry.
- **D-03:** Upgrade behavior: **overwrite existing install**. Uninstaller runs silently as part of new install; user data in `%APPDATA%\musicstreamer` (via `platformdirs.user_data_dir`) is a separate dir and is never touched by the installer.
- **D-04:** Shortcuts: **Start Menu only**. Start Menu shortcut is **mandatory** — it carries the AUMID (`AppUserModelID=org.lightningjim.MusicStreamer`) so SMTC displays "MusicStreamer" instead of "Unknown app". No Desktop shortcut, no Pin-to-Taskbar (user can pin manually post-install if they want).
- **D-05:** License page: **include a short EULA/notice page**. Minimal text covering "personal use, no warranty, uses GStreamer LGPL components, yt-dlp/streamlink attribution". Text file lives at `packaging/windows/EULA.txt`, referenced via Inno Setup `LicenseFile=`.
- **D-06:** Version: **bump `pyproject.toml` to `2.0.0`** as part of this phase. Installer reads version from pyproject (or build.ps1 passes it in as `-DAppVersion`).
- **D-07:** Installer filename: `MusicStreamer-<version>-win64-setup.exe` (e.g., `MusicStreamer-2.0.0-win64-setup.exe`). Output to `dist/installer/` (gitignored).

### Single-Instance + Runtime Checks
- **D-08:** Single-instance mechanism: **`QLocalServer`/`QLocalSocket`** (Qt-native, cross-platform — applies to Linux too). First instance opens a named local server (server name: `org.lightningjim.MusicStreamer.single-instance`). Second instance connects, sends an `activate` message, exits silently.
- **D-09:** Second-launch behavior: **raise + focus existing window**. First instance receives the `activate` message → restores from minimize if needed → `raise_()` + `activateWindow()`. `FlashWindow` fallback if Windows focus-steal prevention blocks the raise.
- **D-10:** Single-instance guard lives in `__main__.py` immediately after `_set_windows_aumid()` and before `QApplication` widget construction (actual `QApplication` itself must exist first because `QLocalServer` needs the event loop, so: QApplication → check single-instance → MainWindow or forward+exit).

### Node.js Prerequisite UX (RUNTIME-01)
- **D-11:** Startup detection: at app launch, check for `node` on PATH (`shutil.which("node")`). Runs after single-instance check, before MainWindow is shown.
- **D-12:** Missing-Node behavior: **soft warning + continue**. Non-blocking `QMessageBox` at startup: title "Node.js not found", body "MusicStreamer needs Node.js for YouTube playback. Install from nodejs.org. All other stream types will work without it." Button: [Open nodejs.org] [OK]. App continues to MainWindow — ShoutCast/HLS/Twitch are unaffected.
- **D-13:** Warning surfaces in **three places** (all conditional on Node.js missing):
  1. **Startup dialog** — shown once per missing-state session (not persistent across restarts; if still missing next launch, show again).
  2. **Toast at YT play time** — when yt-dlp fails resolving a YouTube URL (any failure mode where `node` absence is the likely cause), show toast via `ToastOverlay`: "Install Node.js for YouTube playback" with a click-through to nodejs.org.
  3. **Persistent hamburger indicator** — while Node.js is missing, hamburger menu shows a dedicated "⚠ Node.js: Missing (click to install)" entry that opens `https://nodejs.org` in the default browser. Entry disappears once Node.js is detected (re-check at next launch; no live watcher needed).
- **D-14:** Detection cache: Node.js presence is checked once at startup and stored on a `SystemInfo` object (or equivalent singleton). No runtime polling; a user who installs Node.js mid-session must restart the app.

### DI.fm HTTPS Policy (Phase 43 Gotcha #6)
- **D-15:** **Accept as server-side issue.** SomaFM HTTPS proves the `souphttpsrc` + `gioopenssl.dll` TLS path works. DI.fm returns `streaming stopped, reason error (-5)` after a successful TLS handshake — their listen-key server rejects HTTPS post-connect. No code change in `player.py` or `aa_import.py`. Document the limitation in `packaging/windows/README.md` + note in `43-SPIKE-FINDINGS.md` "Known Gotchas" table (already present). If DI.fm ever fixes their server, MusicStreamer automatically works.

### GStreamer Bundle Scope
- **D-16:** **Broad-collect all 184 GStreamer plugins** (~110 MB bundle as measured in Phase 43). Phase 43 proved this configuration plays SomaFM HTTPS successfully. No aggressive pruning this phase — the risk of accidentally removing a plugin the full app needs (vs. the spike's minimal smoke test) outweighs the ~60 MB size savings. Revisit pruning only if bundle size becomes a user complaint or a CI/distribution blocker.
- **D-17:** `.spec`, `runtime_hook.py`, `build.ps1` — **copy verbatim** from `.planning/phases/43-gstreamer-windows-spike/` and from `.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/`. Required edits: replace `smoke_test.py` reference with the real MusicStreamer entry point (`musicstreamer/__main__.py`), update `$GstRoot` default if the build env diverges from the spike conda env.
- **D-18:** Build env: **conda-forge**, not the upstream MSVC installer. Non-negotiable — PyGObject has no Windows PyPI wheels. Miniforge + `conda create -n musicstreamer-build -c conda-forge python=3.12 pygobject pycairo pyinstaller pyinstaller-hooks-contrib gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly`. Locked versions: Python 3.12, PyInstaller ≥ 6.19, `pyinstaller-hooks-contrib` ≥ 2026.2.

### QA — Smoke Test + Compliance
- **D-19:** Smoke-test cadence: **once per Phase 44 ship**. Manual UAT on the clean Win11 VM when the installer is ready. Personal project, no CI automation — add automated CI as a v2.1+ backlog item if needed.
- **D-20:** Smoke-test playback/feature checklist:
  1. SomaFM HTTPS (`ice4.somafm.com/dronezone-256-mp3`) plays, ICY title updates
  2. HLS stream plays (pick one from the library)
  3. DI.fm over HTTP plays (known HTTPS limitation — D-15)
  4. YouTube live with Node.js on PATH (LoFi Girl-style stream) plays via yt-dlp + EJS solver
  5. YouTube live with Node.js removed from PATH: warning surfaces correctly (startup dialog + hamburger indicator + toast on play attempt); non-YT streams still work
  6. Twitch live stream plays via streamlink (requires valid OAuth token in user profile)
  7. Multi-stream failover: force primary to fail (e.g., edit URL to invalid) → next stream in `order_streams()` order picks up
  8. SMTC round-trip: Windows media keys (keyboard + overlay) play/pause/stop work; SMTC overlay shows station name + ICY title + cover art
- **D-21:** Smoke-test installer/round-trip checklist:
  1. Fresh Win11 VM snapshot → run installer → Start Menu shortcut exists → launch via shortcut succeeds
  2. Uninstall via Settings → Apps → removes installed files cleanly (user data in `%APPDATA%\musicstreamer` preserved)
  3. Re-install over nothing → works
  4. Settings export Linux→Windows: on Linux, export ZIP; move ZIP to Windows VM; import via hamburger menu; verify stations, streams, favorites, tags, logos all present and playable
  5. Settings export Windows→Linux: same flow in reverse
  6. Single-instance: double-click Start Menu shortcut while app running → existing window raises and gets focus (no second instance, no error)
  7. AUMID/SMTC shell binding: SMTC overlay shows **"MusicStreamer"** (not "Unknown app"). This requires launch via the Start Menu shortcut — bare `python -m musicstreamer` will still show "Unknown app" (no registered shortcut with matching AUMID, per Phase 43.1 findings).
- **D-22:** PKG-03 compliance: **retire as a no-op** at ship time. Add a simple ripgrep check to `build.ps1` (or a dedicated `check_subprocess.py`) that fails the build if `musicstreamer/` contains any `subprocess.Popen|subprocess.run|subprocess.call` outside `subprocess_utils.py` and tests. Keeps the `_popen()` helper in `subprocess_utils.py` available for future reintroductions. Roadmap SC-4 is satisfied by the grep pass.
- **D-23:** QA-05 widget-lifetime audit: **document-only audit + spot fixes**. Deliverable: `44-QA05-AUDIT.md` summarizing a grep sweep of QWidget subclasses + dialog open paths, confirming `parent=` is set, confirming no `RuntimeError: Internal C++ object already deleted` appears in existing UAT logs from Phases 37–43.1. Fix any specific findings inline; do not add stress tests.

### Claude's Discretion
- Exact GUID for Inno Setup `AppId` — generate once, lock into `.iss`.
- EULA wording — draft per intent in D-05; user reviews the final copy.
- Naming of the single-instance helper module (e.g., `musicstreamer/single_instance.py`).
- Whether the Node.js startup check + warning dialog live in `__main__.py` or in a dedicated `musicstreamer/runtime_check.py` module.
- Where to place the `packaging/` directory relative to repo root (`packaging/windows/` is the assumed convention).

### Folded Todos
None — no pending todos in `.planning/notes/` match Phase 44's scope (the three pending notes are SDR support, cross-machine config sync, and per-station ICY override).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 43 Spike (source artifacts — copy verbatim)
- `.planning/phases/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md` — Full findings, BOM (126 DLLs, 184 plugins, 57 typelibs), 9 gotchas table, Phase 44 handoff checklist
- `.planning/phases/43-gstreamer-windows-spike/43-spike.spec` — PyInstaller spec with `GST_ROOT` auto-detect, dual-path scanner resolution, `Tree()` blocks for gio/modules, typelibs, schemas
- `.planning/phases/43-gstreamer-windows-spike/runtime_hook.py` — Sets `GIO_EXTRA_MODULES`, `GI_TYPELIB_PATH`, `GST_PLUGIN_SCANNER` (stock rthook misses these)
- `.planning/phases/43-gstreamer-windows-spike/build.ps1` — Build driver with `CONDA_PREFIX` auto-detect + `Invoke-Native` PS 5.1 stderr helper
- `.planning/phases/43-gstreamer-windows-spike/smoke_test.py` — Self-contained HTTPS playback test pattern
- `.planning/phases/43-gstreamer-windows-spike/README.md` — VM setup + per-iteration runbook
- `.claude/skills/spike-findings-musicstreamer/references/windows-gstreamer-bundling.md` — Condensed recipe for Windows GStreamer bundling
- `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` — Cross-platform Qt/GLib bus handler threading rules (already applied; relevant if bus wiring changes)

### Phase 43.1 — AUMID + related Windows wiring
- `.planning/phases/43.1-windows-media-keys-smtc/43.1-CONTEXT.md` — SMTC backend decisions; notes AUMID must precede `QApplication()` and needs a registered Start Menu shortcut with matching `System.AppUserModel.ID` to display the app name
- `musicstreamer/__main__.py` — Current `_set_windows_aumid()` implementation + AUMID string `org.lightningjim.MusicStreamer`

### Phase 42 — Settings Export (SC-6 round-trip UAT)
- `musicstreamer/settings_export.py` — Pure logic under test (build/preview/commit)
- `musicstreamer/ui_qt/settings_import_dialog.py` — Import dialog + merge controls
- Phase 42 UAT notes (captured in STATE.md) — round-trip Linux↔Windows is the driving SC-6 requirement

### Project-level
- `.planning/REQUIREMENTS.md` — PKG-01, PKG-02, PKG-03, PKG-04, QA-03, QA-05 (pending); PKG-05 retired; RUNTIME-01 locked
- `.planning/ROADMAP.md` §"Phase 44: Windows Packaging + Installer" — Goal + 6 success criteria
- `.planning/STATE.md` — Blockers/Concerns list contains three Phase 44 scope items (DI.fm HTTPS, AUMID Start Menu wiring, audio pause/restart glitch backlog)

### Compliance / existing helpers
- `musicstreamer/subprocess_utils.py` — `_popen()` helper (PKG-03); keep in place, add grep guard (D-22)
- `pyproject.toml` — version bump target (D-06: 1.1.0 → 2.0.0)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`musicstreamer/__main__.py`** — `_set_windows_aumid()` already in place; single-instance guard slots in between AUMID call and MainWindow show
- **`musicstreamer/subprocess_utils.py::_popen`** — already sets `CREATE_NO_WINDOW`; just needs the ripgrep compliance check to enforce usage
- **`musicstreamer/paths.py`** — `platformdirs.user_data_dir("musicstreamer")` already resolves `%APPDATA%\musicstreamer` on Windows; settings migration between installed vs. dev layouts is a non-issue (same path)
- **`musicstreamer/ui_qt/toast_overlay.py`** — existing ToastOverlay handles the "Install Node.js" toast (D-13 part 2) with no new widget work
- **`musicstreamer/ui_qt/main_window.py::_build_hamburger_menu`** (approx.) — hamburger-menu assembly point for the persistent Node.js-missing indicator (D-13 part 3)
- **Phase 43 artifacts** (`.spec`, `runtime_hook.py`, `build.ps1`, `smoke_test.py`) — copy verbatim per D-17; only edits are entry-point reference + `$GstRoot` default

### Established Patterns
- **Platform-split code** via `sys.platform == "win32"` guards (used throughout `media_keys/`, `subprocess_utils.py`) — Node.js check + single-instance Windows-specific paths follow this idiom
- **Factory-with-no-op-fallback** (`media_keys/__init__.py::create`) — pattern for Node.js runtime check: return a `NodeRuntime` object whose `available` property drives UX decisions
- **Qt signals for cross-thread** (from spike-findings `qt-glib-bus-threading.md`) — single-instance `QLocalServer.newConnection` runs on the main thread already, so no threading concern there
- **`platformdirs.user_data_dir()`** for all data paths — installer must NOT touch `%APPDATA%\musicstreamer` on install or uninstall (user data stays)

### Integration Points
- **`__main__.py` GUI entry path**: `_set_windows_aumid()` → `QApplication` → **[NEW] single-instance check** → **[NEW] Node.js detection** → MainWindow → `app.exec()`
- **Hamburger menu** (`main_window.py`): add conditional "⚠ Node.js: Missing" QAction when `node_runtime.available is False`
- **Installer build pipeline**: `build.ps1` → PyInstaller (`dist/MusicStreamer/`) → Inno Setup (`iscc packaging/windows/MusicStreamer.iss`) → `dist/installer/MusicStreamer-2.0.0-win64-setup.exe`
- **Ship-time checks**: `build.ps1` runs (a) PyInstaller build, (b) subprocess grep guard (D-22), (c) Inno Setup compile, (d) output size + DLL count diagnostic

</code_context>

<specifics>
## Specific Ideas

- **AUMID string** remains `org.lightningjim.MusicStreamer` (already in `__main__.py`). Installer shortcut must set `AppUserModelID` to the exact same string — any mismatch breaks SMTC display.
- **Start Menu shortcut is mandatory** because it's the only way the AUMID binds to a registered shell shortcut. Bare `python -m musicstreamer` invocations continue to show "Unknown app" in SMTC — this is expected (Phase 43.1 finding).
- **Per-user install** (`PrivilegesRequired=lowest`) because (a) no admin friction for a personal app, (b) per-user install places the shortcut under `%APPDATA%\Microsoft\Windows\Start Menu\Programs\` which accepts AUMID without elevation.
- **Node.js UX is "three-pronged"** (D-13) — startup dialog + toast + hamburger indicator. User explicitly wanted all three; makes the prerequisite impossible to miss.
- **DI.fm HTTPS stays broken** (D-15) — user accepts this as server-side, documents it, no code workaround. HTTPS works for SomaFM/AudioAddict-non-DI.fm/general ShoutCast.
- **No code signing, no MSIX, no auto-update, no CI automation** — all deferred to v2.1+. Personal-scale distribution accepts Windows SmartScreen friction.
- **pyproject bump to 2.0.0** is part of this phase (D-06), not a separate ship step.

</specifics>

<deferred>
## Deferred Ideas

### Deferred to v2.1+ (confirmed)
- Code signing / OV certificate — personal-scale accepts SmartScreen friction
- MSIX packaging — NSIS/Inno Setup is sufficient
- Auto-update mechanism — explicit anti-feature for personal-scale app
- AppImage / Flatpak for Linux — future phase
- GitHub Actions Windows CI runner for smoke-test automation
- Aggressive GStreamer plugin pruning (revisit if bundle size becomes a complaint)
- `FlashWindow` fallback tuning for Windows focus-steal scenarios (add if single-instance UAT reveals issues)

### Out-of-phase (already captured in backlog / STATE.md)
- Audio pause/restart glitch on Windows (GStreamer, not SMTC) — STATE.md blocker list
- `test_thumbnail_from_in_memory_stream` `MagicMock` → `AsyncMock` fix — STATE.md blocker list
- Backlog bugs 999.x (unrelated)

### Reviewed Todos (not folded)
None — the three pending todos in `.planning/notes/` (SDR support, cross-machine config sync, per-station ICY override) are out of Phase 44 scope.

</deferred>

---

*Phase: 44-windows-packaging-installer*
*Context gathered: 2026-04-23*
