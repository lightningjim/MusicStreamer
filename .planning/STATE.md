---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: OS-Agnostic Revamp
status: executing
stopped_at: Phase 49 deferred to backlog 999.12; v2.0 remaining = Phase 44 (Windows packaging)
last_updated: "2026-04-25T00:30:00.000Z"
last_activity: 2026-04-24
progress:
  total_phases: 28
  completed_phases: 22
  total_plans: 76
  completed_plans: 76
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-10)

**Core value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.
**Current focus:** Phase 44 — Windows Packaging + Installer (final v2.0 phase)

## Current Position

Phase: 999.9 (youtube-playback-broken-no-video-formats-found-regression) — COMPLETE
Plan: 1 of 1 (resolved by ea6aa87; first-pass 0fcff6d superseded — see 999.9-01-SUMMARY.md)
Status: Complete
Last activity: 2026-04-24

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 91 (v1.0–v1.5 combined)
- Average duration: ~14 min/plan
- Total execution time: ~12 hours

**Recent Trend:**

- Last milestone (v1.5): 21 plans across 14 phases
- Trend: Stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Key v2.0 decisions already settled:

- GStreamer event loop: GLib.MainLoop daemon thread + bus.enable_sync_message_emission() + Qt queued signals (not QTimer polling)
- MPRIS2: PySide6.QtDBus replaces dbus-python entirely
- OAuth: subprocess-isolated QWebEngineView (oauth_helper.py) — avoids 130MB QtWebEngine in main process startup
- Data paths: platformdirs.user_data_dir("musicstreamer") — XDG on Linux, %APPDATA% on Windows
- GTK cutover: hard cutover in Phase 36; no parallel dual-UI period
- [Phase 35]: KEEP_MPV: cookie-protected YouTube path fails through yt-dlp library API; mpv subprocess fallback retained for _play_youtube() in Plan 35-04
- [Phase 35]: Plan 35-02: PEP 562 __getattr__ shim in constants.py preserves backward compat for DATA_DIR/DB_PATH/etc. — re-evaluates paths.* on every access so paths._root_override monkeypatching works
- [Phase 35]: Spike branch KEEP_MPV: cookie-protected YouTube live fails on yt_dlp library + cookiefile, mpv subprocess retained
- [Phase 36]: icons.qrc uses file alias attributes so resources resolve at :/icons/<name>.svg (pyside6-rcc otherwise nests prefix + file path)
- [Phase 36]: Move function-local urllib.parse import to module level in url_helpers.py (only non-verbatim extraction change)
- [Phase 36]: Delete test_fetch_aa_logo tests in Plan 36-02 alongside test_fetch_yt_thumbnail — both rely on GLib patches that die with ui/ deletion in 36-03; Phase 39 rebuilds with Qt signals
- [Phase 36]: Atomic GTK cutover: deleted musicstreamer/ui/, mpris.py, test_mpris.py, and stale build/ artifact in a single commit. No ripple fixes required thanks to 36-02 url_helpers extraction.
- [Phase 41]: NotImplementedError over abc.ABCMeta for QObject subclasses (PySide6 metaclass constraint)
- [Phase 41-platform-media-keys]: publish_metadata(None) placed before set_playback_state('stopped') so MPRIS clients see cleared metadata before stopped state
- [Phase 41-platform-media-keys]: logging.basicConfig in main() only — not duplicated in _run_smoke or _run_gui
- [Phase 47-01]: Unknown bitrates (bitrate_kbps <= 0) partition LAST, sorted by position asc — order_streams uses two sorted() calls + comprehension partition for purity, never list.sort() in-place (D-07, D-09, P-3)
- [Phase 47-01]: codec_rank normalizes via (codec or "").strip().upper() for None-safety + whitespace tolerance (PB-10)
- [Phase 47-01]: StationStream.bitrate_kbps: int = 0 placed AFTER codec field to preserve positional construction compat with existing call sites (D-01)
- [Phase 47-02]: station_streams.bitrate_kbps migrated via BOTH CREATE TABLE body AND idempotent ALTER TABLE block wrapped in try/except sqlite3.OperationalError — no user_version bump (D-02)
- [Phase 47-02]: Repo.insert_stream / Repo.update_stream take bitrate_kbps: int = 0 kwarg (default preserves all existing positional callers including insert_station, settings_export, aa_import, edit_station_dialog, discovery_dialog)
- [Phase 47-02]: player.py::play line 166 one-line swap sorted(station.streams, key=position) → order_streams(station.streams); variable name streams_by_position retained for minimum-diff (semantically stale but working)
- [Phase 47-03]: discovery_dialog._on_save_row uses G-2 Option 1 post-insert fix-up (capture insert_station station_id, then list_streams + update_stream(bitrate_kbps=...)) — mirrors aa_import.import_stations_multi:188-196 rather than widening the insert_station public signature
- [Phase 47-03]: _BitrateDelegate(QStyledItemDelegate) with QIntValidator(0, 9999) placed at module scope (not nested in EditStationDialog) to mirror station_star_delegate.py convention; registered via setItemDelegateForColumn(_COL_BITRATE, _BitrateDelegate(self))
- [Phase 47-03]: int(stream.get("bitrate_kbps", 0) or 0) in BOTH settings_export._insert_station AND _replace_station — single idiom neutralizes missing key (pre-47 ZIP forward-compat, P-2), None, empty string, and malformed-value threats
- [Phase 43-01]: Wave 1 build artifacts (.spec, runtime_hook, smoke_test, build.ps1, .gitignore, README) copied verbatim from 43-RESEARCH.md skeletons — no improvisation per plan directive; user can run iteration 1 on Win11 VM
- [Phase 43 D-03 amended]: Bumped from 1.24.12 to **1.28.2** upstream (current latest 2026-04-08); 1.28.x ships single .exe installer + flat layout + OpenSSL TLS (`gioopenssl.dll`) replacing GnuTLS
- [Phase 43 D-03 amended (b)]: Relaxed from official MSVC installer to **conda-forge** as primary GStreamer/PyGObject source. Rationale: PyGObject has no PyPI wheels; source build on Windows needs ~1 GB of VS Build Tools + meson/ninja/pkg-config. conda-forge packages are same gvsbuild output as the MSI, byte-for-byte equivalent.
- [Phase 43 findings]: Custom runtime_hook.py is REQUIRED — stock pyi_rth_gstreamer.py doesn't set GIO_EXTRA_MODULES, GI_TYPELIB_PATH, or GST_PLUGIN_SCANNER. Without them: HTTPS fails (`TLS/SSL support not available`), typelibs flaky, scanner in-process.
- [Phase 43 findings]: Stock `hook-gi.repository.Gio.py` warns "Could not determine Gio modules path!" on conda-forge and ships broken bundle. Explicit `Tree(GST_ROOT/lib/gio/modules, prefix='gio/modules')` in .spec compensates.
- [Phase 43 findings]: Bundle self-contained at 110.7 MB — 126 top-level DLLs + 184 plugins (hooks-contrib 2026.2 places in `_internal/gst_plugins/`, not older `gstreamer-1.0/`) + 57 typelibs. Validated with deactivated-conda re-run.
- [Phase 43 gotcha]: DI.fm premium URLs reject HTTPS server-side (TLS handshake succeeds, stream returns error -5). GStreamer not at fault. Phase 44 policy decision: HTTP for DI.fm specifically, or accept server-side HTTPS unavailability.
- [Phase 43.1 bus-watch]: `bus.add_signal_watch()` MUST run on the thread iterating its own thread-default `MainContext` (the `GstBusLoopThread` bridge). Inline-on-main attaches the GSource to the default MainContext which no one iterates on Windows → bus handlers silently drop. Helper: `GstBusLoopThread.run_sync(callable)` marshals the attach.
- [Phase 43.1 AUMID]: `SetCurrentProcessExplicitAppUserModelID` must run BEFORE `QApplication()` (AUMID binds at first window creation) and must use explicit `LPCWSTR` argtypes (default ctypes marshaling can pass `str` as narrow pointer). Shell still shows "Unknown app" until a registered Start Menu shortcut carries the matching AUMID — deferred to Phase 44 installer.
- [Phase 43.1 SMTC thumbnail]: `asyncio.run(await writer.store_async())` avoids the STA-reentry raise on Qt's main thread (Pitfall #3); `writer.detach_stream()` before `RandomAccessStreamReference.create_from_stream` is also required, otherwise the reference reader sees an unreadable stream owned by the DataWriter.
- [Phase 43.1 cross-OS regression]: `QTimer.singleShot(0, callable)` from a non-`QThread` (GStreamer bus-loop thread) silently drops — the bridge thread has no Qt event loop. Any cross-thread work from a bus handler MUST go through a queued `Signal`, same pattern already used for `title_changed`. Latent everywhere; surfaced as a 10 s Shoutcast-death regression once bus handlers reliably dispatched on the bridge thread. Documented in `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md`.
- Wave 0 stubs use fixture mirroring (not pytest.fail placeholders) to encode exact contracts for Plans 01/02/03
- fresh_station fixture added alongside existing station fixture; existing tests untouched
- 999.1-02: header row placed at top-level layout (not inside stations_page) so '+' button is visible in Favorites mode too
- 999.1-02: select_station walks source model inline and maps via proxy.mapFromSource (StationTreeModel API kept minimal)
- [Phase 999.1-03]: Shared slot _on_new_station_clicked handles BOTH hamburger menu action and StationListPanel.new_station_requested signal — single code path for menu and panel '+' button (D-02). Lambda-capture of new_id matches _on_edit_requested precedent (no functools import added to main_window.py).
- 999.7-01: Shared cookie_utils helper module at package root with @contextlib.contextmanager + mkstemp for per-call tempfile copies; 2/9 tests green immediately, 7 RED for Plans 02/03
- Phase 999.7-02: Wired cookie_utils.temp_cookies_copy into yt_import.scan_playlist + forwarded toast_callback through _YtScanWorker
- [Phase 999.7-03]: Player.cookies_cleared declared at class scope next to playback_error; _youtube_resolve_worker wraps yt_dlp.YoutubeDL inside cookie_utils.temp_cookies_copy with corruption auto-clear before the ctxmgr (outside the yt-dlp block). Direct connect to MainWindow.show_toast — no intermediate slot.
- [Phase 999.7-03]: FakePlayer test doubles in 3 MainWindow test modules extended with cookies_cleared Signal(str) — fixture parity over shared base class (minimal-diff).
- Phase 999.7: FIX-02 (yt-dlp temp-copy protection) restored on the library-API path via shared cookie_utils.py (mkstemp+copy2+unlink). Both read sites (player + yt_import) route cookies through a per-call temp file; yt-dlp's save_cookies() on __exit__ can no longer clobber canonical cookies.txt. Corruption auto-clear + toast wired on both sites. Byte-equality UAT approved on live YouTube playback (sha256 stable).
- [Phase 999.9]: yt-dlp 2026.03.17 silently dropped extractor_args["youtubepot-jsruntime"]; pinned player_client=web in musicstreamer/player.py::_youtube_resolve_worker. Bundled yt_dlp_ejs handles JS challenges without --remote-components (probe row 7 confirmed). Phase 999.7 cookie invariant preserved.

### Roadmap Evolution

- Phase 45 added: Unify station-icon loader (note: original add-phase op reported 46; retired placeholder freed slot 45 at commit time) — completed 2026-04-14
- Phase 46 added: UI polish — theme tokens + logo status cleanup (from 40.1 + 45 UI-REVIEW findings) — 2026-04-14
- Phase 47 added: Stats for nerds + AutoEQ import — harvests SEED-005 (buffer indicator) + SEED-007 (AutoEQ profile import) — 2026-04-14
- Phase 41 narrowed: scope restricted to Linux Media Keys (MPRIS2 via QtDBus); MEDIA-03 + Windows slice of MEDIA-04/05 split out — 2026-04-14
- Phase 43.1 inserted: Windows Media Keys (SMTC), depends on Phase 41 (factory) + Phase 43 (runtime); requires live Windows VM validation — 2026-04-14
- Phase 44 success criteria amended: added Phase 42 Linux↔Windows settings-export round-trip UAT — 2026-04-14
- Phase 48 added: Fix AudioAddict listen key not persisting to DB (surfaced by Phase 42 UAT test 7; skipped as out-of-scope) — 2026-04-17
- Phase 49 added: Add ability to add PLS to Streams section of station and auto resolve the # of streams in as new entries — 2026-04-24
- Phase 49 → Backlog 999.12 (deferred to next milestone so v2.0 can ship after Phase 44) — 2026-04-25

### Pending Todos

- .planning/notes/2026-03-21-sdr-live-radio-support.md
- .planning/notes/2026-03-21-sync-config-between-computers.md
- .planning/notes/2026-03-20-icy-override-per-station.md

### Blockers/Concerns

- ~~Phase 43 (GStreamer Windows Spike) must complete before Phase 44 can be planned~~ — **resolved 2026-04-20**: Phase 43 passed iteration 1, findings doc + skill persisted, Phase 44 unblocked
- ~~Phase 41 (SMTC on Windows): winrt async pattern for button_pressed needs real Windows validation~~ — **resolved 2026-04-23**: Phase 43.1 UAT signed off on Win11 VM, all 10 items pass, MEDIA-03/04/05 complete
- Phase 40 (OAuth): QWebEngineCookieStore.cookieAdded in subprocess context needs proof-of-concept before planning
- **Phase 44 scope:** DI.fm premium rejects HTTPS server-side; Phase 44 must decide HTTP-fallback policy for DI.fm specifically vs. universal HTTPS
- **Phase 44 scope (new):** register Start Menu shortcut carrying `System.AppUserModel.ID=org.lightningjim.MusicStreamer` so the SMTC overlay shows "MusicStreamer" instead of "Unknown app" (AUMID is correctly bound to the process; this is the shell display-name path)
- **Phase 44 backlog:** audio pause/restart glitch + ignored volume setting on Windows (GStreamer, not SMTC); fix `test_thumbnail_from_in_memory_stream` (`MagicMock` not awaitable — needs `AsyncMock` for `store_async`)

## Session Continuity

Last session: 2026-04-24T23:42:24.660Z
Stopped at: Phase 999.9 Plan 01 Tasks 1-2 complete; Task 3 UAT pending
Resume file: None

**Ship step pending (manual):** squash-merge `phase-43.1-uat-diag` → `main`, then advance to Phase 44 planning.

**Completed Phase:** 999.8 (twitch-stations-play-silent — REFUTED, resolved by 9df84de) — 2026-04-24

**Planned Phase:** 999.9 (youtube-playback-broken-no-video-formats-found-regression) — 1 plans — 2026-04-24T23:35:12.701Z
