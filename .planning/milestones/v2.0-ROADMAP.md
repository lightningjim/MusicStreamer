# Roadmap: MusicStreamer

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2024-03-20)
- ✅ **v1.1 Polish & Station Management** — Phases 5–6 (shipped 2024-03-21)
- ✅ **v1.2 Station UX & Polish** — Phases 7–11 (shipped 2024-03-25)
- ✅ **v1.3 Discovery & Favorites** — Phases 12–15 (shipped 2024-04-03)
- ✅ **v1.4 Media & Art Polish** — Phases 16–20 (shipped 2024-04-05)
- ✅ **v1.5 Further Polish** — Phases 21–34 (shipped 2026-04-10)
- 🚧 **v2.0 OS-Agnostic Revamp** — Phases 35–44 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2024-03-20</summary>

- [x] Phase 1: Module Extraction (3/3 plans) — completed 2024-03-18
- [x] Phase 2: Search and Filter (2/2 plans) — completed 2024-03-19
- [x] Phase 3: ICY Metadata Display (2/2 plans) — completed 2024-03-20
- [x] Phase 4: Cover Art (1/1 plan) — completed 2024-03-20

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Polish & Station Management (Phases 5–6) — SHIPPED 2024-03-21</summary>

- [x] Phase 5: Display Polish (2/2 plans) — completed 2024-03-21
- [x] Phase 6: Station Management (2/2 plans) — completed 2024-03-21

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 Station UX & Polish (Phases 7–11) — SHIPPED 2024-03-25</summary>

- [x] Phase 7: Station List Restructuring (3/3 plans) — completed 2024-03-22
- [x] Phase 8: Filter Bar Multi-Select (2/2 plans) — completed 2024-03-22
- [x] Phase 9: Station Editor Improvements (2/2 plans) — completed 2024-03-23
- [x] Phase 10: Now Playing & Audio (2/2 plans) — completed 2024-03-24
- [x] Phase 11: UI Polish (1/1 plan) — completed 2024-03-25

Full details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

<details>
<summary>✅ v1.3 Discovery & Favorites (Phases 12–15) — SHIPPED 2024-04-03</summary>

- [x] Phase 12: Favorites (2/2 plans) — completed 2024-03-31
- [x] Phase 13: Radio-Browser Discovery (2/2 plans) — completed 2024-04-01
- [x] Phase 14: YouTube Playlist Import (2/2 plans) — completed 2024-04-02
- [x] Phase 15: AudioAddict Import (2/2 plans) — completed 2024-04-03

Full details: `.planning/milestones/v1.3-ROADMAP.md`

</details>

<details>
<summary>✅ v1.4 Media & Art Polish (Phases 16–20) — SHIPPED 2024-04-05</summary>

- [x] Phase 16: GStreamer Buffer Tuning (1/1 plan) — completed 2024-04-03
- [x] Phase 17: AudioAddict Station Art (2/2 plans) — completed 2024-04-03
- [x] Phase 18: YouTube Thumbnail 16:9 (1/1 plan) — completed 2024-04-05
- [x] Phase 19: Custom Accent Color (2/2 plans) — completed 2024-04-05
- [x] Phase 20: Playback Controls & Media Keys (2/2 plans) — completed 2024-04-05

Full details: `.planning/milestones/v1.4-ROADMAP.md`

</details>

<details>
<summary>✅ v1.5 Further Polish (Phases 21–34) — SHIPPED 2026-04-10</summary>

- [x] Phase 21: Panel Layout Fix (1/1 plan) — completed 2026-04-10
- [x] Phase 22: Import YT Cookies (3/3 plans) — completed 2026-04-07
- [x] Phase 23: Fix YT Playback (cookies) (1/1 plan) — completed 2026-04-07
- [x] Phase 24: Tag Chip FlowBox (1/1 plan) — completed 2026-04-08
- [x] Phase 25: Filter Chip Overflow (1/1 plan) — completed 2026-04-08
- [x] Phase 26: Edit Button Fix (1/1 plan) — completed 2026-04-08
- [x] Phase 27: Multi-Stream Model (3/3 plans) — completed 2026-04-08
- [x] Phase 28: Stream Failover (2/2 plans) — completed 2026-04-09
- [x] Phase 29: Hamburger Menu Consolidation (1/1 plan) — completed 2026-04-09
- [x] Phase 30: Elapsed Time Counter (1/1 plan) — completed 2026-04-09
- [x] Phase 31: Twitch via Streamlink (2/2 plans) — completed 2026-04-09
- [x] Phase 32: Twitch OAuth Token (2/2 plans) — completed 2026-04-10
- [x] Phase 33: YT 15s Wait + Toast (2/2 plans) — completed 2026-04-10
- [x] Phase 34: Deferred Items from Phase 33 (1/1 plan) — completed 2026-04-10

Full details: `.planning/milestones/v1.5-ROADMAP.md`

</details>

### v2.0 OS-Agnostic Revamp (In Progress)

**Milestone Goal:** Port MusicStreamer from GTK4/Libadwaita to Qt/PySide6, retire the GTK codebase, and ship a Windows-compatible distributable with feature-parity to v1.5 plus manual settings export/import and cross-platform media keys.

- [x] **Phase 35: Backend Isolation** - Refactor player.py to QObject + Qt signals; platformdirs data paths; Linux data migration; port yt-dlp/streamlink to library APIs; spike to drop mpv fallback (completed 2026-04-11)
- [x] **Phase 36: Qt Scaffold + GTK Cutover** - Bare QMainWindow launches; GTK deleted; pytest-qt configured (completed 2026-04-11)
- [x] **Phase 37: Station List + Now Playing** - Core loop: grouped station list, now-playing panel, ICY titles, toasts (completed 2026-04-12)
- [x] **Phase 38: Filter Strip + Favorites** - Search/chip filters, favorites toggle view (completed 2026-04-13)
- [x] **Phase 39: Core Dialogs** - EditStation, DiscoveryDialog, ImportDialog, stream picker (completed 2026-04-13)
- [x] **Phase 40: Auth Dialogs + Accent** - AccountsDialog OAuth, YouTube cookies, accent color, hamburger menu (completed 2026-04-13)
- [x] **Phase 41: Platform Media Keys** - media_keys/ factory: MPRIS2 (Linux) + SMTC (Windows) (completed 2026-04-16)
- [x] **Phase 42: Settings Export/Import** - ZIP export/import with merge dialog (completed 2026-04-16)
- [x] **Phase 43: GStreamer Windows Spike** - Validate GStreamer DLL bundling on clean Windows VM — completed 2026-04-20
- [ ] **Phase 44: Windows Packaging + Installer** - PyInstaller spec, NSIS installer, QA smoke test

## Phase Details

### Phase 35: Backend Isolation
**Goal**: Player is a QObject with typed Qt signals and zero GLib calls; data paths use platformdirs; existing Linux data migrates non-destructively on first launch; yt-dlp/streamlink called as libraries; mpv fallback eliminated if GStreamer can handle yt-dlp-resolved URLs
**Depends on**: Phase 34 (v1.5 complete)
**Requirements**: PORT-01, PORT-02, PORT-05, PORT-06, PORT-09, QA-02
**Success Criteria** (what must be TRUE):
  1. App launches on Linux and GStreamer plays a ShoutCast stream with ICY title updating in the terminal/log
  2. All 265 existing tests pass (ported to pytest-qt offscreen) with zero GTK imports
  3. Existing Linux user data at `~/.local/share/musicstreamer/` is present at the platformdirs location on first launch (migrated or already there)
  4. No `GLib.idle_add`, `GLib.timeout_add`, or `dbus-python` imports remain in `player.py`
  5. `yt_import.py` and `player._play_twitch()` use `yt-dlp` and `streamlink` Python APIs (no `subprocess.Popen` calls to those tools); a YouTube live stream plays end-to-end via the library path
  6. mpv fallback spike result documented — either mpv code paths removed (preferred) or mpv retained with spike failure notes
**Plans**: 5 plans
- [x] 35-01-mpv-spike-PLAN.md — Install Phase 35 deps + run mpv-drop spike, record DROP_MPV/KEEP_MPV decision
- [x] 35-02-platformdirs-paths-PLAN.md — paths.py + migration.py helpers, refactor constants.py + call sites (PORT-05, PORT-06)
- [x] 35-03-ytdlp-and-mpris-stub-PLAN.md — yt_import.py library-API port + mpris.py no-op stub (PORT-09 yt-dlp side, D-09..D-11)
- [x] 35-04-player-qobject-PLAN.md — Player → QObject + GstBusLoopThread + streamlink library + spike-branched YouTube (PORT-01, PORT-02, PORT-09 player side)
- [x] 35-05-headless-entry-and-tests-PLAN.md — headless __main__.py entry + big-bang pytest-qt test port (QA-02)
- [x] 35-06-drop-mpv-yt-dlp-ejs-PLAN.md — Supersedes KEEP_MPV: drop mpv entirely, resolve YouTube via yt-dlp library with EJS JS challenge solver. Adds RUNTIME-01 (Node.js runtime requirement). Retires PKG-05.

### Phase 36: Qt Scaffold + GTK Cutover
**Goal**: The app is a Qt application: bare QMainWindow launches, GTK codebase is deleted, icons are bundled, and the test harness uses offscreen Qt
**Depends on**: Phase 35
**Requirements**: PORT-03, PORT-04, PORT-07, PORT-08, QA-01, QA-04
**Success Criteria** (what must be TRUE):
  1. `python -m musicstreamer` opens a Qt window (not GTK) on Linux
  2. `musicstreamer/ui/` directory does not exist; `musicstreamer/ui_qt/` is the only UI package
  3. `pytest` runs with offscreen Qt platform and all phase-35 tests still pass
  4. Bundled SVG icons load from `.qrc` resource; no missing-icon errors on Linux or Windows
  5. Windows dark-mode regression does not occur (Qt Fusion style enforced on Windows)
**Plans**: 4 plans
- [x] 36-01-PLAN.md — Scaffold ui_qt package + bundled Adwaita icons + rewrite __main__.py (argparse GUI/--smoke split, Windows Fusion palette)
- [x] 36-02-PLAN.md — Extract pure URL helpers from ui/edit_dialog.py to url_helpers.py and rewire tests (safety valve before GTK delete)
- [x] 36-03-PLAN.md — Atomic GTK cutover: delete ui/, mpris.py, test_mpris.py, build/ artifact + grep sweep
- [x] 36-04-PLAN.md — Qt scaffold smoke tests (QA-01 MainWindow render + PORT-08 icon fallback + PORT-07 dark-palette code path)
**UI hint**: yes

### Phase 37: Station List + Now Playing
**Goal**: A user can open the app, see their stations grouped by provider, click one to play, and see ICY title, cover art, elapsed timer, and volume slider update in the now-playing panel
**Depends on**: Phase 36
**Requirements**: UI-01, UI-02, UI-12, UI-14
**Success Criteria** (what must be TRUE):
  1. Station list shows provider groups (collapsible), recently-played section, and per-row logos
  2. Clicking a station plays it; ICY track title updates live in the now-playing panel
  3. Cover art loads from iTunes; YouTube 16:9 thumbnails display without panel sizing regression
  4. Volume slider adjusts playback volume and persists across restarts
  5. Toast notifications appear for failover and connecting states
**Plans**: 4 plans
- [x] 37-01-PLAN.md — StationListPanel: StationTreeModel + provider-grouped QTreeView + Recently Played section + audio-x-generic-symbolic icon (UI-01)
- [x] 37-02-PLAN.md — NowPlayingPanel: 3-column layout + control row + cover art slot + volume persistence + 3 media-playback icons (UI-02, UI-14)
- [x] 37-03-PLAN.md — ToastOverlay: frameless fade-in/hold/fade-out widget with parent-resize re-anchor (UI-12)
- [x] 37-04-PLAN.md — MainWindow integration: QSplitter + Player wiring + signal routing + FakePlayer integration tests (UI-01, UI-02, UI-12, UI-14)
**UI hint**: yes

### Phase 38: Filter Strip + Favorites
**Goal**: A user can filter stations by search/provider/tag chips and toggle to their favorites list
**Depends on**: Phase 37
**Requirements**: UI-03, UI-04
**Success Criteria** (what must be TRUE):
  1. Typing in the search box filters the station list in real time
  2. Provider and tag chip rows wrap on narrow windows; multi-select composes with AND-between / OR-within logic
  3. Toggling the Stations/Favorites control switches to the favorites list inline; trash button removes entries
  4. Star button on now-playing panel saves an ICY track title to favorites
**Plans**: 2 plans
Plans:
- [x] 38-01-PLAN.md — DB migration + StationFilterProxyModel + FlowLayout + filter strip UI + icons
- [x] 38-02-PLAN.md — Segmented control + FavoritesView + station star delegate + track star button + wiring
**UI hint**: yes

### Phase 39: Core Dialogs
**Goal**: User can edit stations (multi-stream management, tags, ICY toggle), discover new stations via Radio-Browser, import from YouTube/AudioAddict playlists, and manually select a stream from now-playing
**Depends on**: Phase 38
**Requirements**: UI-05, UI-06, UI-07, UI-13
**Success Criteria** (what must be TRUE):
  1. EditStation dialog opens for a playing station; provider/tag pickers work; multi-stream CRUD and quality presets function; delete is blocked while playing
  2. DiscoveryDialog searches Radio-Browser.info, previews a station, and saves it to the library
  3. ImportDialog YouTube tab scans a playlist and imports selected live streams with progress feedback
  4. ImportDialog AudioAddict tab accepts an API key, selects quality, and imports all channels with logos
  5. Stream picker dropdown on the now-playing panel switches the active stream manually
**Plans**: 4 plans
Plans:
- [x] 39-01-PLAN.md — EditStationDialog: station CRUD + tag chips + multi-stream table + delete guard (UI-05)
- [x] 39-02-PLAN.md — DiscoveryDialog: Radio-Browser search + preview play + save-to-library (UI-06)
- [x] 39-03-PLAN.md — ImportDialog: YouTube scan/import + AudioAddict fetch/import with progress (UI-07)
- [x] 39-04-PLAN.md — Edit button + stream picker on NowPlayingPanel + MainWindow dialog wiring (UI-13)
**UI hint**: yes

### Phase 40: Auth Dialogs + Accent
**Goal**: User can authenticate Twitch via OAuth, manage YouTube cookies, pick an accent color, and access all actions from the hamburger menu
**Depends on**: Phase 39
**Requirements**: UI-08, UI-09, UI-10, UI-11
**Success Criteria** (what must be TRUE):
  1. AccountsDialog opens a subprocess QWebEngineView for Twitch OAuth; token is captured and written with restricted permissions
  2. YouTube cookie import works via file picker, paste, and Google login (subprocess OAuth helper); cookies stored at the platform-appropriate path with 0o600 permissions
  3. Accent color picker applies 8 presets or hex entry as live QSS; persists across restarts
  4. Hamburger menu exposes Discover, Import, Accent Color, YouTube Cookies, Accounts, and Export/Import Settings
**Plans**: 4 plans
Plans:
- [x] 40-01-PLAN.md — AccentColorDialog: build_accent_qss + palette helper + dialog with 8 presets + hex entry (UI-11)
- [x] 40-02-PLAN.md — oauth_helper.py subprocess + AccountsDialog with QProcess Twitch OAuth (UI-08)
- [x] 40-03-PLAN.md — CookieImportDialog: file/paste/Google login tabs with validation (UI-09)
- [x] 40-04-PLAN.md — Hamburger menu wiring + accent startup load + subprocess_utils (UI-10, UI-11 startup)
**UI hint**: yes

### Phase 40.1: Bug-fix sweep — YT import, Discovery icons, AA feedback, station logos, ICY disable (INSERTED, EXPANDED 2026-04-13)

**Goal:** Fix five v2.0 Qt-port regressions in one sweep:
1. YouTube playlist import drops all live streams (double-filter bug in `_YtScanWorker`)
2. Discovery preview buttons show text "Play"/"Stop" — switch to icon toggles
3. AudioAddict import shows "Imported 0 channels" with no dedup feedback
4. Station logos don't render anywhere (placeholder shows for all stations); EditStationDialog has no logo upload or auto-fetch on URL paste
5. "Disable ICY" toggle has no effect — iTunes cover art and ICY track titles still update

**Requirements**: TBD (regression fixes; no new requirement IDs)
**Depends on:** Phase 40
**Plans:** 4/6 plans executed

Plans:
- [ ] TBD (run /gsd-plan-phase 40.1 to break down)

Note: Original Phase 45 (station logos + ICY disable) was folded into 40.1 on 2026-04-13. See `40.1-CONTEXT.md` for full decisions.

### Phase 41: Linux Media Keys (MPRIS2)
**Goal**: OS media keys control the Player on Linux via MPRIS2; now-playing metadata (station + ICY title + cover art) visible to the OS media session; platform factory scaffolded so Phase 43.1 can drop in the Windows backend later
**Depends on**: Phase 40
**Requirements**: MEDIA-01 (factory), MEDIA-02 (QtDBus MPRIS2 impl), MEDIA-04 (Linux slice), MEDIA-05 (Linux slice)
**Success Criteria** (what must be TRUE):
  1. `musicstreamer/media_keys/` package with a `create(player, repo)` factory selecting backend by `sys.platform`; Linux backend implemented, Windows stub raises `NotImplementedError` pending Phase 43.1
  2. Pressing the keyboard media-play key pauses/resumes the stream; `playerctl status` and `playerctl metadata` show the running service
  3. Station name, ICY track title, and cover art pixmap are published to MPRIS2 and update on every `title_changed` signal
  4. `dbus-python` is not imported anywhere in the codebase
  5. MPRIS2 failure modes (no session bus, D-Bus unavailable) log a warning and return a no-op backend — app startup never blocks on this
**Scope split note**: MEDIA-03 (Windows SMTC) and the Windows slice of MEDIA-04/05 deferred to Phase 43.1 because the winrt `button_pressed` async pattern needs live Windows validation (see Phase 43 spike findings).
**Plans**: 3 plans
- [x] 41-01-PLAN.md — Scaffold media_keys package (base class, NoOp fallback, factory, Windows stub)
- [x] 41-02-PLAN.md — LinuxMprisBackend (QtDBus adaptors + cover-art PNG cache)
- [x] 41-03-PLAN.md — MainWindow wiring + UAT checkpoint (playerctl + keyboard media keys)

### Phase 42: Settings Export/Import
**Goal**: User can export all stations, streams, favorites, and config to a portable ZIP file and import it on another machine with merge control
**Depends on**: Phase 41
**Requirements**: SYNC-01, SYNC-02, SYNC-03, SYNC-04, SYNC-05
**Success Criteria** (what must be TRUE):
  1. Export produces a `.zip` containing `settings.json` and a `logos/` folder; cookies and tokens are absent from the archive
  2. Import ZIP on a second machine adds new stations, replaces matches by stream URL, and respects the "replace all vs merge" toggle
  3. Import shows a summary dialog (N added, M replaced, K skipped, L errors) before committing any changes
  4. Export and Import actions are accessible from the hamburger menu
**Plans**: 2 plans
Plans:
- [x] 42-01-PLAN.md — Pure export/import logic: build_zip, preview_import, commit_import + unit tests (SYNC-01, SYNC-02, SYNC-03, SYNC-04)
- [x] 42-02-PLAN.md — SettingsImportDialog + MainWindow menu wiring + QThread workers + UAT (SYNC-04, SYNC-05)
**UI hint**: yes

### Phase 43: GStreamer Windows Spike
**Goal**: GStreamer playback (HTTP + HTTPS streams) is verified working in a PyInstaller-bundled distributable on a clean Windows VM before packaging is planned
**Depends on**: Phase 42
**Requirements**: PKG-06
**Success Criteria** (what must be TRUE):
  1. A minimal PyInstaller `--onedir` build runs on a clean Windows VM without GStreamer installed system-wide
  2. An HTTPS ShoutCast stream plays successfully in the bundle (souphttpsrc SSL / libgiognutls.dll present)
  3. The spike documents exact GStreamer DLLs, plugin list, and `.spec` Tree() blocks needed for Phase 44
**Plans**: 3 plans
Plans:
- [x] 43-01-PLAN.md — Wave 1: Land four build artifacts (.spec, runtime_hook.py, smoke_test.py, build.ps1) + .gitignore + README runbook from RESEARCH skeletons (autonomous) — completed 2026-04-19
- [x] 43-02-PLAN.md — Wave 2: Paste-back iteration loop on user's Win11 VM; ≤5 iterations to green SPIKE_OK + has_default_database=True + audibility word — completed 2026-04-20 iteration 1, audible (SomaFM HTTPS; DI.fm premium rejects HTTPS server-side)
- [x] 43-03-PLAN.md — Wave 3: Harvest 43-SPIKE-FINDINGS.md from paste-back evidence + persist spike-findings-musicstreamer skill — completed 2026-04-20

### Phase 43.1: Windows Media Keys (SMTC)
**Goal**: Windows system media session (SMTC) controls the Player via the same `media_keys/` factory scaffolded in Phase 41; station + ICY + cover art visible in the Windows overlay; validated live on user's Windows VM
**Depends on**: Phase 41 (factory + Linux backend), Phase 43 (confirmed Windows runtime)
**Requirements**: MEDIA-03 (winrt SMTC impl), MEDIA-04 (Windows slice), MEDIA-05 (Windows slice)
**Success Criteria** (what must be TRUE):
  1. `WindowsMediaKeysBackend` implemented via `winrt-Windows.Media.Playback`; factory returns it when `sys.platform == "win32"`
  2. `winrt-Windows.Media.Playback` is declared under `[project.optional-dependencies].windows` in `pyproject.toml` so Linux installs don't pull it; imports guarded by `sys.platform`
  3. Pressing Windows media keys (keyboard or on-screen overlay) triggers play/pause/stop on the Player; validated manually on user's Windows VM
  4. SMTC overlay shows station name, ICY track title, and cover art pixmap; updates on every `title_changed`
  5. SMTC COM/winrt initialization failure logs a warning and falls back to no-op backend — app startup never blocks on this
**Scope split note**: Split out of original Phase 41 on 2026-04-14 because the winrt `button_pressed` async pattern needed live Windows validation, which requires Phase 43's confirmed Windows runtime.
**Plans**: 6 plans

Plans:
- [ ] 43.1-01-PLAN.md — Rename _art_cache subdir mpris-art/ → media-art/ with best-effort migration (D-04) + update Phase 41 MPRIS2 regression tests (Wave 1)
- [ ] 43.1-02-PLAN.md — pyproject [project.optional-dependencies].windows group + replace smtc.py NotImplementedError stub with ImportError fallback + Wave-0 test scaffolding (Wave 1)
- [ ] 43.1-03-PLAN.md — WindowsMediaKeysBackend class: __init__ (MediaPlayer + SMTC + Pitfall #1 command_manager=False + Pitfall #4 token storage) + _on_button_pressed + _apply_playback_state (Wave 2)
- [ ] 43.1-04-PLAN.md — publish_metadata + _build_thumbnail_ref helper using InMemoryRandomAccessStream (D-03 revised per Pitfall #2, file:// rejected) + DisplayUpdater.type=MUSIC (D-08) (Wave 3)
- [ ] 43.1-05-PLAN.md — shutdown() with idempotency sentinel + remove_button_pressed + close() + end-to-end D-07 factory-fallback regression (Wave 4)
- [ ] 43.1-06-PLAN.md — Windows UAT on Win11 VM: install winrt extras + 7-item UAT record + sign-off (non-autonomous, Wave 5)

### Phase 44: Windows Packaging + Installer
**Goal**: A Windows installer EXE is produced that installs MusicStreamer with all dependencies; single-instance enforcement works; no console windows appear; Node.js is documented as a host prerequisite (not bundled)
**Depends on**: Phase 43
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04, QA-03, QA-05 (PKG-05 retired by Plan 35-06)
**Success Criteria** (what must be TRUE):
  1. NSIS (or Inno Setup) installer EXE installs the app to `%LOCALAPPDATA%\MusicStreamer` with a Start Menu shortcut
  2. Launching a second instance activates the running window instead of opening a duplicate
  3. Installer documents the Node.js host prerequisite (required by yt-dlp's EJS JS challenge solver — see RUNTIME-01) and fails gracefully at first launch if Node.js is not on PATH
  4. PKG-03 is a no-op at ship time (Plan 35-06 eliminated all subprocess launches in `musicstreamer/`); if any reappear before Phase 44, they must go through a centralized `_popen()` helper with `CREATE_NO_WINDOW`
  5. Windows smoke test passes: station playback (ShoutCast + HLS), YouTube via yt-dlp library + EJS, Twitch via streamlink library, failover, media keys, and installer round-trip all verified on a clean VM
  6. Phase 42 settings export round-trip UAT: export on Linux → import on Windows (and reverse) preserves stations, streams, favorites, tag chips, and logo paths correctly via `platformdirs.user_data_dir()` resolution at each end
**Plans**: 5 plans

Plans:
- [ ] 44-01-PLAN.md — Wave 0 test scaffolds + tooling guards (PKG-03, PKG-04, QA-03)
- [ ] 44-02-PLAN.md — single_instance.py + runtime_check.py + __version__.py + pyproject 2.0.0 bump (PKG-04, RUNTIME-01)
- [ ] 44-03-PLAN.md — Wire single_instance + Node.js into __main__.py + MainWindow (PKG-04, RUNTIME-01)
- [ ] 44-04-PLAN.md — Windows packaging artifacts: .spec, runtime_hook, build.ps1, MusicStreamer.iss, EULA, README, .ico (PKG-01, PKG-02, PKG-03)
- [ ] 44-05-PLAN.md — QA-05 audit doc + 44-UAT.md + Win11 VM UAT execution (QA-03, QA-05, all PKG)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1–34 | v1.0–v1.5 | all | Complete | 2026-04-10 |
| 35. Backend Isolation | v2.0 | 5/5 | Complete   | 2026-04-11 |
| 36. Qt Scaffold + GTK Cutover | v2.0 | 4/4 | Complete   | 2026-04-11 |
| 37. Station List + Now Playing | v2.0 | 4/4 | Complete    | 2026-04-12 |
| 38. Filter Strip + Favorites | v2.0 | 2/2 | Complete    | 2026-04-13 |
| 39. Core Dialogs | v2.0 | 4/4 | Complete    | 2026-04-13 |
| 40. Auth Dialogs + Accent | v2.0 | 4/4 | Complete    | 2026-04-13 |
| 41. Linux Media Keys (MPRIS2) | v2.0 | 4/4 | Complete   | 2026-04-16 |
| 42. Settings Export/Import | v2.0 | 3/3 | Complete    | 2026-04-17 |
| 43. GStreamer Windows Spike | v2.0 | 0/3 | Planned | - |
| 43.1. Windows Media Keys (SMTC) | v2.0 | 0/6 | Planned | - |
| 44. Windows Packaging + Installer | v2.0 | 0/5 | Planned | - |

### Phase 45: Unify station-icon loader — dedup station_tree_model + favorites_view + station_list_panel paths into a shared _art_paths helper; fixes broken station-list logo rendering where raw relative station_art_path is passed to QPixmap() without abs_art_path resolution

**Goal:** Single shared `load_station_icon` helper in `musicstreamer/ui_qt/_art_paths.py` replaces three duplicate loaders, restoring real station logos in both the main station tree and the favorites list (currently both fall back to the generic music-note icon because they skip `abs_art_path()`).
**Requirements**: PHASE-45-UNIFY-LOADER, PHASE-45-FIX-LIST-LOGO, PHASE-45-FIX-FAVES-LOGO
**Depends on:** none (independent bugfix/refactor)
**Plans:** 1/1 plans complete

Plans:
- [x] 45-01-PLAN.md — Add shared `load_station_icon` to `_art_paths.py` (TDD), migrate three UI call sites, delete duplicates, manual UAT


### Phase 46: UI polish — theme tokens + logo status cleanup: centralize hardcoded error-red #c0392b into a theme constant (6+ sites, blocks dark mode); distinguish 'AA URL, use Choose File' from 'truly unsupported URL' in EditStationDialog fetch status; auto-clear _logo_status label after 3s or on next textChanged; export STATION_ICON_SIZE constant from _art_paths.py; add fetch-in-flight spinner and logo empty-state glyph (from 40.1 + 45 UI-REVIEW findings)

**Goal:** End the hardcoded-hex pattern blocking dark mode by centralizing `#c0392b` and `QSize(32, 32)` into a shared `_theme.py` module, AND close three EditStationDialog logo-status UX gaps (distinguish AA-no-key from unsupported URL, auto-clear label after 3s or on textChanged, apply Qt.WaitCursor during fetch).
**Requirements**: None (cleanup phase; phase_req_ids is null — must-haves come from CONTEXT.md §Phase Boundary)
**Depends on:** Phase 45
**Plans:** 2/2 plans complete

Plans:
- [x] 46-01-PLAN.md — Theme token module + migration sweep (create `_theme.py`, migrate 10 hex + 3 QSize sites, add tests/test_theme.py)
- [x] 46-02-PLAN.md — EditStationDialog logo-status UX (AA-URL classification, 3s auto-clear timer, Qt.WaitCursor override)

### Phase 47: Stream bitrate quality ordering — add `bitrate_kbps` to `StationStream`, populate on AA/RadioBrowser import, and reorder failover queue by (codec_rank, bitrate) for higher-quality-first playback

**Goal:** Add a numeric `bitrate_kbps` field to `StationStream`, populate it during AA (DI.fm tier map) and RadioBrowser (API field) imports, reorder the failover queue by (codec_rank desc, bitrate_kbps desc, position asc) with unknowns last, and expose the field as an editable 5th column in the Edit Station dialog. Preserve backwards compat via additive DB migration and defensive `.get("bitrate_kbps", 0)` on settings-import boundaries.
**Requirements**: TBD
**Depends on:** Phase 46
**Plans:** 7/7 plans complete

**Scope (from 2026-04-15 roadmap addition, split from original Phase 47 on 2026-04-17):**
- Add `bitrate_kbps: int = 0` field to `StationStream` model + DB migration
- Expose bitrate in the Edit Station dialog stream table (editable alongside codec/label)
- Failover queue ordering: sort by `(codec_rank desc, bitrate_kbps desc)` when bitrate is known; fall back to `position` order when bitrate=0 (backwards compat). Codec ranks: FLAC=3 > AAC=2 > MP3=1 > other=0. Same-codec tie-break: higher kbps first (320 > 128). Cross-codec at same kbps: AAC ranks above MP3 (efficiency advantage at equivalent perceptual quality).
- AA import (`aa_import.py`) populates bitrate_kbps from known DI.fm quality tiers (hi=320/AAC, med=128/AAC, low=64/AAC)
- RadioBrowser import populates bitrate_kbps from the `bitrate` field already returned by the API

Plans: 3/3 plans complete

- [x] 47-01-PLAN.md — Pure-logic foundation: `StationStream.bitrate_kbps` + `musicstreamer/stream_ordering.py` + 18 green tests (Wave 1) — completed 2026-04-18
- [x] 47-02-PLAN.md — Schema + repo CRUD + player failover hook: ALTER TABLE migration, widened `list_streams`/`insert_stream`/`update_stream`, single-line `player.play()` swap to `order_streams` (Wave 2, parallel with 47-03) — completed 2026-04-18
- [x] 47-03-PLAN.md — Import + UI + settings-export wiring: AA tier map, RadioBrowser post-insert fix-up in `_on_save_row`, Edit Station 5th column with `_BitrateDelegate` + `QIntValidator`, settings_export 8-column INSERT with forward-compat `.get()` (Wave 2, parallel with 47-02) — completed 2026-04-18

### Phase 47.1: Stats for nerds — live GStreamer buffer-fill indicator (SEED-005)

**Goal:** Wire a live buffer-fill percent indicator in the now-playing panel, driven by GStreamer's `message::buffering` bus signal. Diagnose drop-outs, give curious users stream-health visibility.
**Requirements**: TBD
**Depends on:** Phase 47 (no hard dep; independent — but sequenced after bitrate for focus)
**Plans:** 2/2 plans complete

**Scope (split from original Phase 47 on 2026-04-17; harvests SEED-005):**
- `player.py`: connect `bus.connect("message::buffering", self._on_gst_buffering)` alongside existing handlers; emit a Qt signal with the percent (0-100) for the UI layer.
- `now_playing_panel.py`: add a collapsible "stats for nerds" row with the buffer percent (progress bar or `{N}%` label). Hidden by default; toggle via settings or hamburger menu.
- Out of scope (deferred): other diagnostic stats (codec, sample rate, ICY bitrate, stream URL) — capture as follow-up if useful during implementation.

Plans:
- [x] 47.1-01-PLAN.md — Player bus subscription + buffer_percent Signal + de-dup sentinel + 4 pytest-qt tests (Wave 1)
- [x] 47.1-02-PLAN.md — NowPlayingPanel stats widget + hamburger QAction toggle + MainWindow wiring + 7 widget tests (Wave 2, depends_on 01)

### Phase 47.2: In-app parametric EQ with AutoEQ profile import (SEED-007) ✓ COMPLETE 2026-04-19

**Goal:** Insert a GStreamer parametric EQ element into the playback pipeline and provide a UI to import/activate AutoEQ `ParametricEQ.txt` profiles. Primary driver: unlocks headphone EQ on the user's work PC where Equalizer APO is blocked.
**Requirements**: TBD
**Depends on:** Phase 35 Plan 06 (Player QObject architecture) — already shipped. No hard dep on 47 or 47.1.
**Plans:** 4/4 plans complete
**UAT:** Passed 2026-04-19 — audible A/B, profile swap, preamp, trash flow all good. Windows parity deferred to Phase 43/44.
**Known issue (deferred):** Brief audio dropout on EQ on/off toggle — D-05 design said bypass via zeroed gains should be dropout-free, so this is a regression worth investigating in a follow-up phase.

**Scope (split from original Phase 47 on 2026-04-17; harvests SEED-007):**
- Pipeline integration: add `equalizer-nbands` (or a biquad chain for true parametric EQ) to `playbin3.audio-filter`; wire enable/disable toggle.
- AutoEQ `ParametricEQ.txt` parser: read the AutoEQ config format (filter type, frequency, Q, gain per band).
- UI: EQ dialog (or Settings section) with profile import, enable toggle, and per-band visualization.
- Profile storage: per-user (one active EQ) rather than per-station — confirmed during discuss.
- Out of scope (deferred): bundled AutoEQ profiles, per-station override, dynamic range compression, other DSP filters — capture as follow-up if requested.

Plans:
- [x] 47.2-01-PLAN.md — Parser + paths helper + EQ toggle SVG icon (Wave 1, no deps)
- [x] 47.2-02-PLAN.md — Player pipeline integration: equalizer-nbands in audio-filter + 3 new set_eq_* methods + startup restore (Wave 2, depends on 01)
- [x] 47.2-03-PLAN.md — EqualizerDialog + QPainter response curve + hamburger menu wiring (Wave 3, depends on 01, 02)
- [x] 47.2-04-PLAN.md — NP panel EQ toggle button + settings ZIP eq-profiles/ round-trip (Wave 3, depends on 01, 02)

### Phase 48: Fix AudioAddict listen key not persisting to DB ✓ COMPLETE 2026-04-19 — settings.audioaddict_listen_key is not being stored when set via AccountsDialog/ImportDialog, causing it to be empty on read and blocking Phase 42 round-trip UAT test 7. Scope: diagnose where the key write is dropped, fix persistence, add regression test that sets-then-reads the key across an app restart. Out of scope: the read-only-DB silent-import issue (owned by Phase 42).

**Goal:** Persist the AudioAddict listen key to SQLite on successful fetch so it survives app restarts and prefills `ImportDialog` on open. Expose view-status + clear controls in `AccountsDialog` (no edit there). Mask the key by default with a show toggle. Regression-test the full save → reopen → readback flow at widget level, and re-assert Phase 42's export-exclusion contract (`audioaddict_listen_key` stays out of the settings ZIP) with a non-empty stored value.
**Requirements**: None (bug-fix phase; coverage driven by CONTEXT D-01..D-13)
**Depends on:** Phase 47
**Plans:** 2 plans

Plans:
- [x] 48-01-PLAN.md — AccountsDialog repo threading + AA view/clear group + `_is_aa_key_saved` + combined `_update_status` + 8 retrofit tests + 3 new AA tests (Wave 1)
- [x] 48-02-PLAN.md — ImportDialog repo threading + prefill + mask + show toggle + success-gated `set_setting` + 6 new AA widget tests + extend `test_credentials_excluded` with non-empty stored value (Wave 2, depends_on 48-01 for shared main_window.py)

---

## Backlog

> Unsequenced ideas parked for later promotion via `/gsd-review-backlog`.

### Phase 999.1: Add "New Station" primary action (PLANNED)

**Goal:** Provide a direct UX path to create a station from scratch via a hamburger-menu entry and a "+" button on the StationListPanel header. Both entry points pre-create a placeholder station via `repo.create_station()` and open `EditStationDialog` in `is_new=True` mode; cancel/close deletes the placeholder; save refreshes the list and selects the new station (no auto-play). Closes the v1.x UX gap surfaced during Phase 46 UAT where the only paths to a new station were Discover (AudioAddict) or Import (YouTube/playlist).
**Requirements:** D-01..D-08 (backlog UX phase — no REQ-XX IDs; D-IDs from CONTEXT.md are the requirement anchors)
**Depends on:** none (independent UX addition)
**Plans:** 4/4 plans complete

Plans:
- [x] 999.1-00-PLAN.md — Wave 0: 15 failing test stubs across test_edit_station_dialog.py, test_station_list_panel.py, test_main_window_integration.py
- [x] 999.1-01-PLAN.md — EditStationDialog `is_new` mode: constructor flag, pre-added blank stream row (D-05), delete-on-reject/close (D-04), provider-blank (D-08), save-cleanup flag flip
- [x] 999.1-02-PLAN.md — StationListPanel: right-aligned "+" QToolButton + `new_station_requested` signal (D-02) + `select_station(id)` helper with proxy mapping (D-07b)
- [x] 999.1-03-PLAN.md — MainWindow wiring: "New Station" menu action first in Group 1 (D-01), `_on_new_station_clicked` shared slot (D-03), post-save refresh + select + no-auto-play (D-07a/c)

### Phase 999.2: Recently Played list does not update live (BACKLOG — BUG)

**Goal:** Fix the Recently Played section so it updates in real time when a station starts playing. Current behavior: the DB is updated correctly (confirmed — `stations.last_played_at` gets the new timestamp), but the UI list only refreshes when the app is restarted. Likely the Recently Played widget model isn't wired to a station-played signal. Investigate `station_list_panel.py` (Recently Played block) + `main_window.py` playback-start handler; emit/connect a refresh signal when a station transitions to playing.
**Requirements:** TBD
**Depends on:** none (standalone bug fix)
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.3: Twitch and Google login does not work, it immediately falls back to failure (BACKLOG — BUG)

**Goal:** Investigate and fix OAuth login flows for Twitch and Google (YouTube) — both currently fail immediately and fall back to the failure path with no successful token exchange. Likely causes to rule out: stale/expired OAuth client credentials, redirect-URI mismatch, browser launcher + loopback listener timing, or a regression in the auth-dialogs introduced during Phase 40. Check the auth dialog + token-exchange callpaths in both providers; reproduce with fresh credentials and capture the exact failure mode (network error vs. bad-response vs. user-cancel misread).
**Requirements:** TBD
**Depends on:** none (bug fix in existing auth flows)
**Plans:** 3/3 plans complete

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.4: Cross-network mirror-station sibling links (AA — BACKLOG — FEATURE)

**Goal:** Model AudioAddict stations that appear on multiple AA networks (e.g. "Ambient" on DI.FM AND ZenRadio) as a sibling group rather than unrelated duplicate stations. Keep the stations DISTINCT (not merged, no cross-network failover) because the schedules don't line up — what's playing on DI.FM's Ambient at any moment is NOT what's playing on ZenRadio's Ambient. The link is purely organizational: show "also available on ZenRadio" on the DI.FM station (and vice-versa), let the user jump between siblings, and optionally unify favorites + last-played across the group.

**Why not cross-network failover (Option 2):** Rejected because AA mirror schedules drift — failing from DI.FM hi → ZenRadio hi would cut mid-song to a completely different track, breaking user expectation. Failover only makes sense within a single network's stream list.

**Open design questions (for /gsd-discuss-phase):**
- Detection: automatic at AA-import time (match on `channel_key` or normalized `channel_name`) or manual "mark as sibling" UX?
- Favorites: unified across the sibling group, or per-station?
- Last-played / Recently Played: unified, or per-station?
- UI affordance: badge on station card? Context-menu "Switch to mirror"? Separate "Siblings" panel in Edit Station?
- Data model: new `mirror_group_id` column on `stations`, or a separate `station_siblings` join table?

**Requirements:** TBD (derive during discuss)
**Depends on:** none. Builds on existing AA-import infrastructure but does not require Phase 47.x failover work.
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.5: EQ on/off toggle causes brief audio dropout (BACKLOG — BUG)

**Goal:** Eliminate the brief audio dropout heard when clicking the NP-panel EQ toggle button. Per Phase 47.2 CONTEXT D-05, toggle is designed as bypass-via-zero-gains on the resident `equalizer-nbands` element — no pipeline state transition, no element rebuild, and therefore no dropout. Observed behavior contradicts that contract.

**Surfaced:** Phase 47.2 UAT on 2026-04-19.

**Investigation starting points:**
- `musicstreamer/player.py` `_apply_eq_state` bypass branch (added in Plan 47.2-02) — confirm it only mutates `band.set_property("gain", ...)` on the existing element; no `set_state`, no `audio-filter` reassignment, no rebuild.
- Check whether writing `gain=0.0` on every band at once triggers caps renegotiation inside `equalizer-nbands` / GStreamer. Try setting gains in a specific order, or wrapping in a single `GstStructure` update if one exists.
- Verify `set_eq_enabled` is called once per click (no double-fire from `toggled` + `clicked` signals on the checkable button).
- Consider hysteresis: cache the zeroed state and skip property writes when already zeroed.
- Related (may share root cause): confirm same-band-count profile swaps are dropout-free — if they aren't, same investigation likely covers both.

**Requirements:** TBD (derive during discuss)
**Depends on:** none (standalone bug fix on existing Phase 47.2 code)
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.6: Merge YouTube Cookies menu into Accounts menu (BACKLOG)

**Goal:** [Captured for future planning] — YouTube cookies are an account credential, so surfacing them as a separate top-level menu is inconsistent. Fold the YouTube Cookies menu entry into the Accounts menu alongside other account-based integrations.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.7: yt-dlp overwrites cookies.txt — regression of FIX-02 (PLANNED — BUG)

**Goal:** Restore the v1.5 Phase 23 (FIX-02) temp-copy protection that was lost when Plan 35-06 replaced the mpv subprocess with the `yt_dlp.YoutubeDL` library API. Wrap both yt-dlp read sites (`player._youtube_resolve_worker` + `yt_import.scan_playlist`) in a shared `musicstreamer/cookie_utils.temp_cookies_copy()` context manager so yt-dlp's `save_cookies()` side effect on `__exit__` never touches the canonical `cookies.txt`. Auto-recover already-corrupted files (yt-dlp marker detected) with a toast at the read site. Reproduced 2026-04-24 during Phase 999.3 UAT.
**Requirements:** FIX-02-a..e (restored), NEW-a..d (corruption auto-recovery)
**Depends on:** none (bug fix; code lives in existing phase-35 / phase-40 surface area)
**Plans:** 4 plans

Plans:
- [ ] 999.7-01-PLAN.md — Wave 1 TDD: create `cookie_utils.py` (corruption predicate + temp-copy @contextmanager) + 9 failing tests in `tests/test_cookies.py` + extended FakeYDLSaveCookies fixture
- [ ] 999.7-02-PLAN.md — Wave 2: `yt_import.scan_playlist` routes cookies through `temp_cookies_copy()` + toast_callback kwarg + `_YtScanWorker` forwards `self._toast`
- [ ] 999.7-03-PLAN.md — Wave 2 (parallel with 02): `Player._youtube_resolve_worker` routes cookies through `temp_cookies_copy()` + class-level `cookies_cleared = Signal(str)` + MainWindow wiring to `show_toast`
- [ ] 999.7-04-PLAN.md — Wave 3: full-suite regression guard + human UAT (byte-identity + tempfile-leak + corruption recovery) + PROJECT.md Key Decisions entry

### Phase 999.8: Twitch stations play silent — REFUTED, actual root cause was streamlink 8.x API regression (COMPLETE)

**Goal:** After Phase 999.3 fixed Twitch OAuth login, Twitch stations resolve and GStreamer "plays" (elapsed timer ticks) but produce no audio. Original hypothesis: Phase 47.2 equalizer plugged into `playbin3.audio-filter` silences Twitch's HLS audio format. **REFUTED 2026-04-24.**
**Outcome:** Actual root cause was `streamlink` 8.x dropping `Streamlink.set_plugin_option`. The Twitch resolution worker crashed with `AttributeError` before assigning a URI to playbin3 — symptom (timer ticks, no audio) was indistinguishable from EQ-induced silencing because the crash happened in a `daemon=True` thread without surfacing as `playback_error`. Fixed in `9df84de` (one-line API update: `session.set_plugin_option("twitch", "api-header", v)` → `session.set_option("twitch-api-header", v)`). EQ was never at fault. Planned GstBin wrapper + matrix harness dropped per single-user pragmatic policy. See `999.8-DIAGNOSTIC.md` and `999.8-SUMMARY.md` for full record.
**Requirements:** TBD
**Plans:** 0 plans (resolved by `9df84de`; planned work was against refuted hypothesis)

### Phase 999.9: YouTube playback broken — library API needed explicit js_runtimes (COMPLETE 2026-04-24)

**Goal:** Reproduced 2026-04-24 during Phase 999.7 UAT. YouTube live streams (e.g. LoFi Girl) yielded `ERROR: [youtube] <id>: No video formats found!` from `yt_dlp.YoutubeDL.extract_info()`, while the same URL played fine via `uv run yt-dlp` at the shell. Cookies, yt-dlp version, and Node availability all ruled out by Phase 999.7 + pre-flight checks.
**Outcome:** Real root cause was a CLI-vs-library divergence in yt-dlp 2026.03.17: the library API does NOT auto-discover JS runtimes the way the CLI does, so the YouTube n-challenge solver never ran. Fix shipped in `ea6aa87`: added `js_runtimes={"node": {"path": None}}` to the `_youtube_resolve_worker` opts dict; dropped the player_client pin from the first-pass fix (no longer needed once the runtime is wired). Dead `extractor_args["youtubepot-jsruntime"]` namespace also removed (was silently ignored by 2026.03.17). UAT approved: LoFi Girl plays end-to-end, cookies sha256 unchanged across UAT and reboot. Phase 999.7 invariant intact. See `999.9-01-SUMMARY.md` for the full diagnostic trail (the first-pass Branch A pin in `0fcff6d` was a misdiagnosis — historical record preserved).
**Requirements:** TBD
**Plans:** 1 plan (complete)

Plans:
- [x] 999.9-01-PLAN.md — Probe yt-dlp player_client matrix + apply fix + in-app UAT (D-01..D-07) — completed 2026-04-24

### Phase 999.10: Radio logo viewport on station section is rectangular — logos cut off (BACKLOG — BUG)

**Goal:** [Captured for future planning] — The logo display area in the station section renders more rectangular than square, so square station logos are cropped on the top/bottom (or left/right) edges. Fix the viewport aspect ratio (or the image fit policy) so logos display fully without cropping.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.11: Editing a station and saving recloses all open sections (BACKLOG — BUG)

**Goal:** [Captured for future planning] — When the user edits a station and saves changes, the UI collapses/closes everything that was previously expanded or open in the station view. Save should preserve the current expansion/open state instead of resetting it.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.12: Add ability to add PLS to Streams section of station and auto resolve the # of streams in as new entries (BACKLOG — FEATURE)

**Goal:** [Captured for future planning] — In the station editor, allow pasting/loading a PLS playlist URL into the Streams section; the app should auto-fetch the PLS, parse out each entry, and add them as individual stream rows (with bitrate/codec resolved where possible). Originally captured as Phase 49; deferred to next milestone so v2.0 can ship after Phase 44.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

---
*Last updated: 2026-04-25 — moved Phase 49 → backlog 999.12 (deferred to next milestone; v2.0 ships after Phase 44)*
