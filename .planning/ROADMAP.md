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

### 🚧 v2.0 OS-Agnostic Revamp (In Progress)

**Milestone Goal:** Port MusicStreamer from GTK4/Libadwaita to Qt/PySide6, retire the GTK codebase, and ship a Windows-compatible distributable with feature-parity to v1.5 plus manual settings export/import and cross-platform media keys.

- [x] **Phase 35: Backend Isolation** - Refactor player.py to QObject + Qt signals; platformdirs data paths; Linux data migration; port yt-dlp/streamlink to library APIs; spike to drop mpv fallback (completed 2026-04-11)
- [ ] **Phase 36: Qt Scaffold + GTK Cutover** - Bare QMainWindow launches; GTK deleted; pytest-qt configured
- [ ] **Phase 37: Station List + Now Playing** - Core loop: grouped station list, now-playing panel, ICY titles, toasts
- [ ] **Phase 38: Filter Strip + Favorites** - Search/chip filters, favorites toggle view
- [ ] **Phase 39: Core Dialogs** - EditStation, DiscoveryDialog, ImportDialog, stream picker
- [ ] **Phase 40: Auth Dialogs + Accent** - AccountsDialog OAuth, YouTube cookies, accent color, hamburger menu
- [ ] **Phase 41: Platform Media Keys** - media_keys/ factory: MPRIS2 (Linux) + SMTC (Windows)
- [ ] **Phase 42: Settings Export/Import** - ZIP export/import with merge dialog
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
**Plans**: TBD
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
**Plans**: TBD
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
**Plans**: TBD
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
**Plans**: TBD
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
**Plans**: TBD
**UI hint**: yes

### Phase 41: Platform Media Keys
**Goal**: OS media keys (play/pause, stop, next/previous) control the player on both Linux and Windows; now-playing metadata is visible to the OS media session
**Depends on**: Phase 40
**Requirements**: MEDIA-01, MEDIA-02, MEDIA-03, MEDIA-04, MEDIA-05
**Success Criteria** (what must be TRUE):
  1. On Linux, pressing the keyboard media-play key pauses/resumes the stream; MPRIS2 service is visible to `playerctl`
  2. On Windows, the system media session overlay shows the station name and current ICY track title
  3. Media key events (play/pause, stop) control the Player on both platforms via the same `media_keys/` factory interface
  4. `dbus-python` is not imported anywhere in the codebase
**Plans**: TBD

### Phase 42: Settings Export/Import
**Goal**: User can export all stations, streams, favorites, and config to a portable ZIP file and import it on another machine with merge control
**Depends on**: Phase 41
**Requirements**: SYNC-01, SYNC-02, SYNC-03, SYNC-04, SYNC-05
**Success Criteria** (what must be TRUE):
  1. Export produces a `.zip` containing `settings.json` and a `logos/` folder; cookies and tokens are absent from the archive
  2. Import ZIP on a second machine adds new stations, replaces matches by stream URL, and respects the "replace all vs merge" toggle
  3. Import shows a summary dialog (N added, M replaced, K skipped, L errors) before committing any changes
  4. Export and Import actions are accessible from the hamburger menu
**Plans**: TBD
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
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1–34 | v1.0–v1.5 | all | Complete | 2026-04-10 |
| 35. Backend Isolation | v2.0 | 5/5 | Complete   | 2026-04-11 |
| 36. Qt Scaffold + GTK Cutover | v2.0 | 0/TBD | Not started | - |
| 37. Station List + Now Playing | v2.0 | 0/TBD | Not started | - |
| 38. Filter Strip + Favorites | v2.0 | 0/TBD | Not started | - |
| 39. Core Dialogs | v2.0 | 0/TBD | Not started | - |
| 40. Auth Dialogs + Accent | v2.0 | 0/TBD | Not started | - |
| 41. Platform Media Keys | v2.0 | 0/TBD | Not started | - |
| 42. Settings Export/Import | v2.0 | 0/TBD | Not started | - |
| 43. GStreamer Windows Spike | v2.0 | 0/TBD | Not started | - |
| 44. Windows Packaging + Installer | v2.0 | 0/TBD | Not started | - |

---
*Last updated: 2026-04-10 — v2.0 OS-Agnostic Revamp roadmap created (phases 35–44)*
