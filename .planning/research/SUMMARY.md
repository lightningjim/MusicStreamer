# Project Research Summary

**Project:** MusicStreamer v2.0 — OS-Agnostic Qt/PySide6 Port
**Domain:** Cross-platform desktop audio stream player (Linux + Windows)
**Researched:** 2026-04-10
**Confidence:** MEDIUM-HIGH

---

## Executive Summary

MusicStreamer v2.0 is a UI-layer replacement: GTK4/Libadwaita exits, PySide6 enters, the Python + GStreamer + SQLite backend survives unchanged. Nine of ten backend modules are clean for direct reuse. The two that are not — player.py (GLib timer/idle calls) and mpris.py (dbus-python) — are the critical path. Getting player.py's threading model right before any UI work starts is the single most important sequencing decision, because every downstream phase depends on a Player that correctly delivers ICY titles, EOS events, and failover signals to Qt.

The recommended approach is a hard cutover: (1) refactor player.py to a QObject with Qt signals and QTimer instances, removing all GLib.* calls; (2) scaffold a bare QMainWindow and delete musicstreamer/ui/ immediately; (3) implement each dialog sequentially. The GStreamer Qt event loop is resolved by running a GLib.MainLoop daemon thread alongside Qt's main loop and emitting Qt signals from GStreamer bus callbacks. Bus messages cross the thread boundary via Qt's queued connection, no GLib idle calls needed in player.py. MPRIS2 moves to PySide6.QtDBus; Windows gets SMTC via winrt.

The highest single risk is GStreamer on Windows. Bundling GStreamer DLLs and plugins into a PyInstaller distributable is documented but untested for this project. All four researchers independently flagged this as the primary unknown. A Windows packaging spike must prove out the full chain on a clean Windows VM before the Windows port is declared done.

---

## Key Findings

### Recommended Stack

The v1.5 backend stack (Python, GStreamer playbin3, yt-dlp, streamlink, mpv, SQLite, urllib) requires zero changes. New additions: PySide6 >=6.8 (UI framework, LGPL, no commercial license needed for personal use), platformdirs (cross-platform data paths), winrt-runtime + winrt-Windows.Media.Playback (SMTC, Windows-only), and PySide6-WebEngine (Twitch OAuth, subprocess-isolated). Packages leaving: PyGObject GTK/Adw, dbus-python, WebKit2Gtk.

**Core technologies:**
- PySide6 6.8+: Qt UI framework, LGPL, pip-installable, works on both platforms
- PySide6.QtDBus: MPRIS2 on Linux, replaces dbus-python, already in the PySide6 package
- winrt-runtime + winrt-Windows.Media.Playback: SMTC on Windows, Windows 10+ only, guarded by sys.platform == 'win32'
- platformdirs: cross-platform data dir, replaces hardcoded XDG path in constants.py
- PyInstaller 6.x: packaging, only tool with a working GStreamer gi hook
- GLib.MainLoop daemon thread: GStreamer bus driver, runs alongside QEventLoop, communicates via Qt queued signals

### Expected Features

**Must have (v2.0 table stakes):**
- Qt/PySide6 UI at full v1.5 feature parity
- Platform-correct data paths via platformdirs
- Cross-platform media keys: SMTC (Windows) and MPRIS2/QtDBus (Linux) behind a media_keys/ factory
- Bundled SVG icon set compiled into .qrc
- Settings export/import: ZIP archive with export.json + logos, excludes cookies/tokens
- Windows installer via PyInstaller + NSIS
- Single-instance enforcement, high-DPI scaling, dark mode, toast via QSystemTrayIcon.showMessage

**Should have (v2.1):**
- Minimize-to-tray
- Windows accent color seed on first run

**Defer to v2.2+:**
- File association for .pls/.m3u, Windows Jump List, taskbar thumbnail toolbar

### Architecture Approach

Nine modules are clean for direct reuse; only player.py and mpris.py need refactoring. Player becomes a QObject with typed signals (title_changed, failover_event, offline_event) replacing current callback parameters; GLib.timeout_add/source_remove become QTimer instances. A GLib.MainLoop daemon thread drives the GStreamer bus; callbacks emit Qt signals via queued connection into the main thread. mpris.py is deleted and replaced by a media_keys/ package with a platform factory. Platform divergence is isolated to four seams: data paths, media keys, subprocess flags, and file permissions. The UI is a hard cutover to ui_qt/. Station list uses direct QListWidget fill, not QAbstractListModel.

**Major components:**
1. Player (QObject): GStreamer pipeline owner, emits Qt signals, QTimer for all timers, zero GLib calls
2. GLib daemon thread: runs GLib.MainLoop to drive GStreamer bus, signals only to main thread
3. media_keys/ package: factory returning MprisService (Linux, QtDBus) or SmtcService (Windows, winrt)
4. ui_qt/ package: full Qt UI, direct widget fill, custom ExpanderSection/ToastOverlay/FlowLayout widgets
5. platform_utils.py: app data dir, secure file write, CREATE_NO_WINDOW subprocess helper, extra tool dirs
6. settings_io.py (new): ZIP export/import with export.json + logo images

### Critical Pitfalls

1. GStreamer bus callbacks on wrong thread: bus.add_signal_watch() silently delivers nothing without a running GLib context. Use bus.enable_sync_message_emission() and emit a Qt signal from the sync handler. Never call QWidget methods inside that handler. Address in Phase A.

2. GStreamer plugin path missing in PyInstaller bundle (Windows): Pipelines fail immediately with no element "playbin3". Set GST_PLUGIN_PATH, GST_PLUGIN_SCANNER, GST_REGISTRY at startup when sys.frozen is detected. Add Tree() blocks for plugin DLLs in .spec. Test on clean VM.

3. souphttpsrc SSL on Windows: HTTPS streams fail (TLS/SSL support not available) when libgiognutls.dll is absent from the bundle. Explicitly collect from GStreamer MSVC runtime. Test an HTTPS stream as a packaging quality gate.

4. QObject C++ lifetime vs. Python GC: RuntimeError: Internal C++ object already deleted when Qt destroys a widget while Python holds a reference. Always parent widgets; dialogs use exec() or stored as self._dialog; GStreamer callbacks emit signals only.

5. Subprocess console window flash + pipe deadlock on Windows: CREATE_NO_WINDOW missing causes visible CMD flash. stdout=PIPE stderr=PIPE without timeout deadlocks when child fills pipe buffer. Centralize through a _popen() helper; use subprocess.run(capture_output=True, timeout=30) for yt-dlp.

---

## Reconciled Decisions

### 1. GStreamer Qt Event Loop: RESOLVED -- GLib daemon thread + Qt signals

Three researchers gave different recommendations. Canonical pattern: run a GLib.MainLoop on a daemon thread (ARCHITECTURE). In player.py, use bus.enable_sync_message_emission() + sync-message to emit Qt signals from callbacks (PITFALLS). Replace all GLib.idle_add/GLib.timeout_add in player.py with Qt signals and QTimer (all researchers agree).

STACK's QTimer-based timed_pop(0) polling is valid but polled at 50ms; the GLib daemon thread + sync emission is reactive and idiomatic for GStreamer + Qt coexistence. Do not use GLib.idle_add() in player.py -- it is a no-op on Windows.

### 2. MPRIS2 on Linux: RESOLVED -- PySide6.QtDBus

Drop dbus-python. Rewrite mpris.py using QDBusAbstractAdaptor and QDBusConnection.sessionBus(). Rationale: dbus-python requires DBusGMainLoop(set_as_default=True), which conflicts with the Qt-only loop goal. PySide6.QtDBus is already in the dependency set, no extra install. On Windows it is a no-op, guarded by sys.platform == 'linux'. More boilerplate than dbus-python but correct long-term architecture.

### 3. QtWebEngine vs system-browser OAuth: RESOLVED -- subprocess isolation

Keep the subprocess isolation pattern. Spawn a minimal oauth_helper.py that embeds QWebEngineView, connects to profile.cookieStore().cookieAdded, captures access_token, writes to a temp file, and exits. The main process reads the temp file.

Rationale: QtWebEngine adds ~130-150MB to the distributable and ~3s to main process startup. Subprocess isolation avoids both costs. System-browser + local redirect server (OAuth PKCE) is a zero-dependency alternative to flag for v2.1 if the subprocess approach proves fragile.

### 4. GStreamer Windows bundling: SPIKE REQUIRED

All four researchers flagged this as the primary unknown. The documented path (GStreamer MSVC runtime MSI + PyInstaller spec with Tree() plugin DLLs + GST_PLUGIN_PATH at startup + libgiognutls.dll for HTTPS) is correct in theory. A spike must validate the full chain on a clean Windows VM with Defender enabled before Phase H is planned.

---

## Implications for Roadmap

### Phase A: Backend isolation -- player.py refactor
**Rationale:** Everything downstream depends on Player working correctly. Prove the GStreamer Qt bridge before any UI exists.
**Delivers:** player.py without gi.repository.GLib; all 265 tests pass; Player is a QObject with typed signals and QTimer instances; GLib.MainLoop daemon thread wired in entry point.
**Pitfalls avoided:** Wrong-thread bus delivery (Pitfall 1), GLib.idle_add no-op on Windows (Pitfall 10)
**Research flag:** Standard patterns -- skip phase research.

### Phase B: Qt scaffold + GTK cutover
**Rationale:** Validate the entry point and delete GTK immediately to eliminate dead weight.
**Delivers:** Bare QMainWindow launches; musicstreamer/ui/ deleted; platformdirs path migration in constants.py; pytest-qt + offscreen configured.
**Pitfalls avoided:** Hardcoded data paths (Pitfall 6), parallel ui/ anti-pattern, Xvfb in tests (Pitfall 16)
**Research flag:** Boilerplate -- skip phase research. Gap to resolve: data path migration for existing Linux users on first run.

### Phase C: Station list + now-playing panel
**Rationale:** Core loop -- load stations, click to play, see title update. Validates Player signals wired to UI end-to-end.
**Delivers:** Grouped ExpanderSections, now-playing panel, volume slider, ICY title updates, recently played, ToastOverlay, bundled SVG icon set compiled into .qrc.
**Pitfalls avoided:** Libadwaita widget mapping (Pitfall 9), QObject lifetime (Pitfall 7)
**Research flag:** Custom Qt widget implementations follow published Qt examples -- skip phase research.

### Phase D: Filter strip + favorites view
**Rationale:** Stateless UI, no new backend or platform concerns. Group with Phase C or follow immediately.
**Delivers:** Search, provider/tag chip filters, empty state, Stations/Favorites segmented control, star button, favorites list.
**Pitfalls avoided:** GTK CSS to QSS translation (Pitfall 8) -- accent QSS written fresh for Qt selectors, not ported verbatim.

### Phase E: All dialogs
**Rationale:** Dialogs are independent of each other; implement as a group after main window is stable.
**Delivers:** EditStation, ManageStreams, Discovery, Import (YouTube + AudioAddict tabs), AccentDialog, AccountsDialog (oauth_helper.py subprocess for Twitch OAuth), StreamsDialog.
**Pitfalls avoided:** QObject lifetime in dialogs (Pitfall 7), WebEngine subprocess isolation (Pitfall 11), scope creep (Pitfall 15)
**Research flag:** AccountsDialog -- QWebEngineCookieStore.cookieAdded async delivery in a subprocess context needs one-off validation before implementation.

### Phase F: Platform integration (media keys + Windows subprocess compat)
**Rationale:** Platform-conditional code cleanly separated from UI. Implement after UI is stable.
**Delivers:** media_keys/ factory (MprisService/SmtcService), platform_utils.py complete, _popen() helper with CREATE_NO_WINDOW, pipe deadlock fixes, os.chmod no-op documented, single-instance enforcement.
**Pitfalls avoided:** Console window flash (Pitfall 4), pipe deadlock (Pitfall 5), chmod no-op (Pitfall 12)
**Research flag:** SMTC winrt async pattern for button_pressed events needs validation on a real Windows machine before Phase F is planned.

### Phase G: Settings export/import
**Rationale:** Standalone feature with no UI or platform dependencies; can be reprioritized earlier without risk.
**Delivers:** ZIP archive export (JSON + logos, excludes cookies/tokens), import with merge/conflict dialog, hamburger menu entry.
**Research flag:** Standard stdlib (zipfile, json) -- skip phase research.

### Phase H: Windows packaging spike + installer
**Rationale:** Highest-risk phase; validates GStreamer bundling on a clean Windows VM. Run as a spike first.
**Delivers:** PyInstaller spec with GStreamer plugin DLLs collected, frozen startup sets GST_PLUGIN_PATH/GST_REGISTRY, HTTPS stream plays on clean VM with Defender enabled, NSIS installer EXE.
**Pitfalls avoided:** Plugin path missing (Pitfall 2), souphttpsrc SSL (Pitfall 3), AV false positives (Pitfall 14) via --onedir + --no-upx
**Research flag:** NEEDS PHASE RESEARCH. Run spike first: install GStreamer MSVC MSI, build minimal PyInstaller spec, play HTTP + HTTPS streams on clean VM. Do not plan the full packaging phase until the spike passes.

### Phase Ordering Rationale

- Phases A-B are infrastructure prerequisites. No UI code before Player is clean and scaffold is green.
- Phase C proves the Player-UI signal path end-to-end. If ICY titles don't update, stop and fix before proceeding.
- Phases D-E follow naturally.
- Phase F after UI because media-keys shim needs confirmed signals to push into MPRIS2/SMTC.
- Phase G is isolated and can be moved earlier without risk.
- Phase H is last; packaging requires a stable, feature-complete codebase.

### Research Flags

Needs deeper research during planning:
- Phase H (Windows packaging): GStreamer DLL bundling is the project's primary unvalidated risk. Budget 1-2 days of exploration before planning the full phase.
- Phase F (SMTC): winrt async pattern for SMTC verified against docs only. Needs real Windows validation before planning.
- Phase E (OAuth): QWebEngineCookieStore.cookieAdded in a subprocess context needs a quick proof-of-concept.

Standard patterns -- skip research-phase:
- Phase A: Qt signals + QTimer replacing GLib calls is canonical.
- Phase B: PySide6 QMainWindow scaffold is boilerplate.
- Phase C: ExpanderSection, FlowLayout, ToastOverlay follow published Qt examples.
- Phase G: zipfile + json export/import is stdlib.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | PySide6 LGPL, PyInstaller GStreamer hook, platformdirs verified against official docs. winrt SMTC MEDIUM for Python-specific async behavior. |
| Features | HIGH | Port of known-working v1.5 features; new additions well-scoped with clear precedent. |
| Architecture | HIGH | Direct source audit of v1.5 codebase; module contamination factual. Qt threading model canonical per PySide6 docs. GLib daemon thread pattern MEDIUM -- documented but untested in this codebase. |
| Pitfalls | HIGH (Linux) / MEDIUM (Windows) | Bus threading, subprocess flags, pipe deadlock, AV false positives well-sourced. GStreamer Windows bundling requires project-specific validation. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- GStreamer Windows bundling (Phase H): Exact DLLs, PyInstaller spec structure, registry.bin behavior -- all require hands-on validation. First Windows task.
- SMTC winrt async pattern (Phase F): Python async handling for button_pressed on SystemMediaTransportControls may require asyncio bridge or Windows-specific event integration.
- QDBusAbstractAdaptor MPRIS2 boilerplate (Phase F): Exact Q_CLASSINFO declarations for org.mpris.MediaPlayer2.Player need a reference implementation before committing to QtDBus.
- Data path migration on upgrade (Phase B): First Linux launch after the port must migrate the old path if it differs from platformdirs. Needs an explicit plan.

---

## Sources

### Primary (HIGH confidence)
- PyPI PySide6 6.11.0 -- version, Python requirements
- Qt licensing docs -- LGPL personal-app analysis
- PySide6 QtDBus docs -- server-mode capability
- GStreamer bus documentation -- timed_pop, enable_sync_message_emission, add_signal_watch
- PyInstaller 6.x hooks-config docs -- GStreamer include_plugins/exclude_plugins
- Qt WebEngine platform notes -- Windows qt.conf requirement
- platformdirs GitHub/PyPI -- cross-platform path behavior
- Microsoft SMTC docs -- SystemMediaTransportControls API
- Direct source audit of musicstreamer/ package -- module contamination analysis
- PySide6 QueuedConnection docs -- cross-thread signal safety

### Secondary (MEDIUM confidence)
- GStreamer Discourse: Qt GStreamer event loop woes
- Qt Forum: GLib event loop integration
- pythonguis.com: Packaging PySide6 with PyInstaller
- GStreamer Discourse / PyInstaller/Kivy issue -- plugin DLL bundling on Windows
- winsdk / pywinrt GitHub -- Python SMTC bindings
- Qt Dark Mode on Windows 11 blog (Qt 6.5)
- pytest-qt troubleshooting docs -- offscreen platform configuration

### Tertiary (LOW confidence / needs project-specific validation)
- GStreamer souphttpsrc SSL issue #451 -- libgiognutls.dll requirement on Windows (documented, not yet verified for this project)
- PyInstaller AV false positive guide -- --onedir + --no-upx (community consensus, untested here)
- STACK.md bundle size estimate (~130MB QtWebEngineCore) -- from 2023 PyInstaller discussion, directionally accurate

---

*Research completed: 2026-04-10*
*Ready for roadmap: yes*
