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
- [ ] **Phase 43: GStreamer Windows Spike** - Validate GStreamer DLL bundling on clean Windows VM
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
**Plans**: TBD

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
**Plans**: TBD

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
**Plans**: TBD

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
| 43. GStreamer Windows Spike | v2.0 | 0/TBD | Not started | - |
| 43.1. Windows Media Keys (SMTC) | v2.0 | 0/TBD | Not started | - |
| 44. Windows Packaging + Installer | v2.0 | 0/TBD | Not started | - |

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

### Phase 47: Stats for nerds + AutoEQ import + stream bitrate quality ordering — harvest SEED-005 (live GStreamer buffer-fill indicator in now-playing panel, wired to message::buffering) and SEED-007 (in-app parametric EQ with AutoEQ ParametricEQ.txt profile import via GStreamer equalizer-nbands element; unlocks headphone EQ on work PC where Equalizer APO is blocked)

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 46
**Plans:** 0 plans

**Scope additions (2026-04-15):**
- Add `bitrate_kbps: int = 0` field to `StationStream` model + DB migration
- Expose bitrate in the Edit Station dialog stream table (editable alongside codec/label)
- Failover queue ordering: sort by `(codec_rank desc, bitrate_kbps desc)` when bitrate is known; fall back to `position` order when bitrate=0 (backwards compat). Codec ranks: FLAC=3 > AAC=2 > MP3=1 > other=0. Same-codec tie-break: higher kbps first (320 > 128). Cross-codec at same kbps: AAC ranks above MP3 (efficiency advantage at equivalent perceptual quality).
- AA import (`aa_import.py`) populates bitrate_kbps from known DI.fm quality tiers (hi=320/AAC, med=128/AAC, low=64/AAC)
- RadioBrowser import populates bitrate_kbps from the `bitrate` field already returned by the API

Plans:
- [ ] TBD (run /gsd-plan-phase 47 to break down)

### Phase 48: Fix AudioAddict listen key not persisting to DB — settings.audioaddict_listen_key is not being stored when set via AccountsDialog/ImportDialog, causing it to be empty on read and blocking Phase 42 round-trip UAT test 7. Scope: diagnose where the key write is dropped, fix persistence, add regression test that sets-then-reads the key across an app restart. Out of scope: the read-only-DB silent-import issue (owned by Phase 42).

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 47
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 48 to break down)

---
*Last updated: 2026-04-16 — Phase 42 plans created (2 plans in 2 waves)*
