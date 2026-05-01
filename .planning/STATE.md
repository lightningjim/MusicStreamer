---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Fixes and Tweaks
status: executing
stopped_at: Phase 64 context gathered
last_updated: "2026-05-01T16:17:21.985Z"
last_activity: 2026-05-01 -- Phase 64 planning complete
progress:
  total_phases: 19
  completed_phases: 6
  total_plans: 19
  completed_plans: 16
  percent: 84
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-27)

**Core value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.
**Current focus:** Phase 55 — Edit Station Preserves Section State

## Current Position

Phase: 61
Plan: Not started
Status: Ready to execute
Last activity: 2026-05-01 -- Phase 64 planning complete

## Performance Metrics

**Velocity:**

- Total plans completed: 94 (v1.0–v1.5 combined)
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
- [Phase 50-01]: StationListPanel.refresh_recent() public method placed parallel to refresh_model in the '# Public refresh API' block; delegates only to _populate_recent — does NOT call model.refresh or _sync_tree_expansion (preserves provider tree expand/collapse state, SC #3)
- [Phase 50-01]: _on_station_activated calls station_panel.refresh_recent() via direct method call (D-04 — no Signal/connect, no QTimer.singleShot, no Qt.QueuedConnection); ordering update_last_played → refresh_recent is load-bearing per Pitfall #1 (DB write must precede UI re-query)
- [Phase ?]: Phase 51-01: Extended url_helpers.py rather than creating aa_siblings.py — all dependencies (NETWORKS, _is_aa_url, _aa_slug_from_url, _aa_channel_key_from_url) already in module
- [Phase ?]: Phase 51-01: find_aa_siblings returns tuple[network_slug, station_id, station_name] over dict — cheaper unpacking by Plan 03 renderer; HTML escaping is renderer's responsibility
- [Phase 51]: Phase 51-03: Qt.RichText QLabel with html.escape mitigation introduced as project-first T-39-01 deviation, locally bounded to one QLabel
- [Phase ?]: Phase 54-01: regression-lock shipped (Path A) — zero production code change per D-09; D-11 cache key invariant preserved

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
- v2.1 roadmap created 2026-04-27: Phases 49–60 (12 phases), 14 requirements mapped. BUG-07 (Phase 49) is first. Backlog stubs 999.2/4/5/6/10/11/12 renumbered as core phases 50–58.
- Phase 49 (BUG-07 — YouTube Linux Playback Regression) resolved without code change 2026-04-27 — playback resumed after user reinstalled both `yt-dlp` and the GStreamer plugins at the OS level. Suspected fix is one of those two but not bisected (both reinstalled together). Root cause not formally documented. Pattern matches v2.0 Phase 999.8 (REFUTED, resolved via separate commit). If regression returns, reopen as Phase 49.1 and bisect (revert yt-dlp first, then GStreamer plugins).
- Phase 50 (BUG-01 — Recently Played Live Update) complete 2026-04-28 — `StationListPanel.refresh_recent()` wired into `MainWindow._on_station_activated` after `update_last_played`. SC #1/#2/#3 confirmed via live UAT.
- Phase 61 added: Linux App Display Name in WM Dialogs (BUG-08) — surfaced during Phase 50 UAT 2026-04-28, parallel to WIN-02
- Phase 62 added: Audio Buffer Underrun Resilience (BUG-09) — surfaced 2026-04-28; intermittent dropout reports without clear repro, instrumentation phase
- Phase 63 added: Auto-Bump pyproject Version on Phase Completion (VER-01) — adopt `milestone.minor.phase` versioning (`2.1.50` for Phase 50 of v2.1); pyproject.toml version field auto-rewritten by phase.complete hook 2026-04-28
- Versioning convention 2026-04-28: project version is `{milestone_major}.{milestone_minor}.{phase_number}`. pyproject.toml manually bumped to 2.1.50 at Phase 50 close (commit 87f6dab or similar). Phase 51+ bumps will be automated by VER-01 / Phase 63.
- Phase 51 (BUG-02 — AudioAddict Cross-Network Siblings) complete 2026-04-28 — `find_aa_siblings` helper + sibling label in EditStationDialog with hyperlink-style links + `navigate_to_sibling = Signal(int)` + Save/Discard/Cancel dirty confirm. On-demand detection, no DB schema change. SC #4 (no failover regression) verified via grep gates + e2e `fake_player.play_calls == []` assertion.
- Phase 64 added: AudioAddict Siblings on Now Playing (BUG-02 follow-up) — surface AA siblings in the Now Playing panel as one-click jumps that switch active playback (unlike Phase 51's edit-dialog flow which only navigates the editor). Reuses `find_aa_siblings` helper from Phase 51. 2026-04-28
- Phase 65 added: Show current version in app (location TBD — hamburger menu vs. right end of bar containing hamburger) 2026-04-28
- Phase 66 added: Color Themes — preset and custom color schemes, with Vaporwave (pastel) and Overrun (neon+black) as the driving presets 2026-04-29
- Phase 67 added: Show similar stations below now playing for switching - From same Provider and Same Tag, random 5 from each with refresh, hideable and not shown by default 2026-05-01

### Pending Todos

- .planning/notes/2026-03-21-sdr-live-radio-support.md
- .planning/notes/2026-04-03-station-art-fetching-beyond-youtube.md

### Blockers/Concerns

- ~~Phase 49: YouTube Linux playback regression~~ — **resolved 2026-04-27** without code change (env-level fix). If regression returns, open Phase 49.1 to bisect.
- Phase 56: DI.fm HTTPS-fallback policy not yet decided (HTTP-for-DI.fm-only vs. universal)
- Phase 60: GBS.FM sub-capability scope to be refined at /gsd-discuss-phase time

## Deferred Items

Items previously deferred at v2.0 close, now folded into v2.1 initial scope (2026-04-27):

| Category | Item | v2.1 disposition |
|----------|------|------------------|
| seed | 006-visual-color-picker | in scope — Phase 59 |
| seed | 008-gbs-fm-integration | in scope — Phase 60 |
| uat (out-of-scope) | 999.3-03-HUMAN-UAT.md | still deferred — not a v2.1 gate |
| Phase 50 P01 | 25min | 3 tasks | 4 files |
| Phase 51 P03 | 8min | 2 tasks | 2 files |
| Phase 54 P01 | 4 min | 3 tasks | 1 files |

## Session Continuity

Last session: 2026-05-01T15:38:48.779Z
Stopped at: Phase 64 context gathered
Resume file: .planning/phases/64-audioaddict-siblings-on-now-playing/64-CONTEXT.md
