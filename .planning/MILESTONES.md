# Milestones

## v2.0 OS-Agnostic Revamp (Shipped: 2026-04-26)

**Phases completed:** 29 phases, 81 plans, 73 tasks

**Key accomplishments:**

- One-liner:
- One-liner:
- One-liner:
- KEEP_MPV.
- `musicstreamer/__main__.py`
- Completed:
- 1. [Rule 3 — Blocking issue] icons.qrc produced nested resource path `:/icons/icons/<name>.svg`
- 1. [Rule 3 — Blocking issue] Patched `PySide6.QtGui.QGuiApplication.styleHints` directly instead of the `musicstreamer.__main__` attribute path
- 1. [Rule 3 - Blocking] Test assertion `findChild(QFrame)` returned first QLabel
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- 1. [Rule 3 - Blocking] pytest-qt not installed in uv venv
- One-liner:
- 1. [Rule 1 - Bug] Actual yt_import/aa_import signatures differ from plan interfaces
- NowPlayingPanel additions:
- Task 1 — build_accent_qss + palette helpers
- One-liner:
- One-liner:
- One-liner:
- `musicstreamer/ui_qt/discovery_dialog.py`:
- Shared resolver (`musicstreamer/ui_qt/_art_paths.py`)
- +5 tests
- `musicstreamer/media_keys/` package scaffolded: abstract `MediaKeysBackend(QObject)` with D-02 signal+method surface, `NoOpMediaKeysBackend` fallback, `create()` platform factory, and Windows `smtc.py` stub — 9/9 pytest-qt tests passing
- `LinuxMprisBackend` implemented via PySide6.QtDBus with Root + Player MPRIS2 adaptors, cover-art PNG cache, and 11/12 pytest-qt tests passing — `playerctl` can target the service by name on any machine with a D-Bus session bus
- MainWindow wired to MediaKeysBackend via factory: title_changed bridges to publish_metadata, 4 state transitions call set_playback_state, closeEvent calls shutdown — 8/8 spy-backend tests passing
- Cleared MPRIS metadata on all five stop transitions and wired logging.basicConfig so media_keys warnings reach stderr
- 1. [Rule 1 - Bug] Fixed logo filename mismatch in test helper
- 1. [Rule 1 - Bug] Fixed replace warning visibility test — isVisible() vs isHidden()
- Renamed `_ImportCommitWorker.finished` → `commit_done` (and `error` → `commit_error`) so PySide6's C++ `QThread::finished` stops misrouting error-path thread exits through the success slot; added a real-filesystem chmod 0o444 regression test the previous monkeypatch test was blind to.
- Everything verbatim
- Completed:
- Completed:
- Renamed _art_cache.py cache subdir to media-art/ with module-sentinel migration helper, enabling shared cover-art path for MPRIS2 and SMTC backends
- [windows] optional-dep group declared in pyproject.toml, smtc.py deferred-import skeleton replacing NotImplementedError stub, and 4 Wave-0 unit tests confirming Linux importability and NoOp factory fallback
- WindowsMediaKeysBackend wired to SMTC via MediaPlayer conduit: button routing (play/pause/stop), state mapping (playing/paused/stopped->MediaPlaybackStatus), Pitfall #1 + #4 + T-43.1-04 mitigations, 14 unit tests green on Linux with mocked winrt
- 7 RED test scaffolds + 2 build-time guard tools land Wave 0 contracts (SERVER_NAME, NodeRuntime shape, "Node.js: Missing" QAction text, .spec hiddenimports list) so Plans 02–05 have a single feedback loop.
- QLocalServer-based single-instance helper with FlashWindowEx focus fallback, Node.js host-runtime detection with CPython #109590 Windows safety, and version 2.0.0 source-of-truth landed.
- 1. [Rule 1 - Bug] `runtime_check.show_missing_node_dialog` AttributeError under Plan 01 test fake
- Windows packaging pipeline lands: PyInstaller .spec + GStreamer runtime hook + PowerShell build driver (with Python-tool PKG-03 guard) + Inno Setup per-user installer + EULA + README + multi-resolution .ico, all wired to the AUMID `org.lightningjim.MusicStreamer` and the pinned AppId GUID `914e9cb6-f320-478a-a2c4-e104cd450c88`.
- QA-05 widget-lifetime audit clean (23 subclasses + 9 dialog launch sites + 13 signal connections + zero UAT-log regressions); 44-UAT.md template ready for Win11 VM execution with 16 pending checklist rows including the new UAT-21-1.5 AppId 3-brace acceptance check.
- Cache key parity.
- New `_theme.py` design-token module with ERROR_COLOR_HEX/QCOLOR + STATION_ICON_SIZE; 9 hex sites and all 3 icon-size sites migrated; `edit_station_dialog.py:131` deliberately deferred to Plan 46-02 Task 2 for Wave 1 parallel-execution disjointness
- Three-arg _LogoFetchWorker signal distinguishes AudioAddict-URL-but-no-key from generic unsupported URLs, a parented 3s auto-clear timer scrubs stale status, and a stack-balanced wait cursor covers the fetch window.
- Pure failover ordering module (`stream_ordering.py`) with `codec_rank` + `order_streams`, plus `StationStream.bitrate_kbps: int = 0` field — zero coupling to DB, Qt, or GStreamer, 18 tests green.
- Extended `station_streams` with `bitrate_kbps INTEGER NOT NULL DEFAULT 0` (CREATE TABLE + idempotent ALTER TABLE), widened `Repo.insert_stream` / `Repo.update_stream` / `Repo.list_streams` to carry it, and swapped `player.py::play`'s position-only sort for `order_streams(station.streams)` — failover now prioritizes (codec rank desc, bitrate desc).
- Wired `bitrate_kbps` end-to-end through the three user-facing surfaces: AudioAddict import (DI.fm tier -> 320/128/64 map), RadioBrowser discovery-save (post-insert update_stream fix-up), Edit Station dialog (5th column with QIntValidator delegate), and settings export/import roundtrip (8-column INSERT in both _insert_station and _replace_station with forward-compat defensive coerce).
- 1. [Rule 3 — Blocking] Updated 9 pre-existing `_resolve_pls` mock side_effects
- None.
- New Player.buffer_percent Signal(int) sourced from GStreamer message::buffering with defensive parse, sentinel de-dup, and per-stream reset — backend half of Phase 47.1 ready for UI wiring in plan 02.
- Live GStreamer buffer-fill percent surfaced in NowPlayingPanel as a mini QProgressBar + {N}% QLabel row inside a hidden-by-default QFormLayout wrapper, toggled via a new checkable hamburger-menu QAction with SQLite persistence, and wired end-to-end to Player.buffer_percent via a bound-method connect (no lambda).
- Write side
- Adds a right-aligned "+" QToolButton header row emitting `new_station_requested`, plus a `select_station(station_id)` helper that maps source-model indexes through `StationFilterProxyModel` before calling `setCurrentIndex`.
- Twitch OAuth token capture rebuilt on 127.0.0.1 loopback listener + self-contained HTML bounce page, replacing the broken urlChanged fragment capture with CSRF-validated POST /capture and structured JSON-line stderr diagnostics.
- One-liner:
- Date:
- Shared cookie_utils.py helper (is_cookie_file_corrupted + temp_cookies_copy @contextmanager) and 9 RED tests that drive FIX-02 restoration and corruption auto-recovery in Plans 02/03.
- Ported the v1.5 FIX-02 temp-copy protection to `yt_import.scan_playlist` (the playlist-scan read site), added corruption auto-recovery with toast-callback plumbing through `_YtScanWorker`, and turned 5 RED cookie tests green.
- Player._youtube_resolve_worker now routes cookies through cookie_utils.temp_cookies_copy with corruption auto-clear + cookies_cleared Signal wired to MainWindow.show_toast — yt-dlp's save_cookies() side effect can no longer overwrite canonical cookies.txt on the player path.
- Closed out Phase 999.7 with full-suite pytest green (764 passed, 10 pre-existing baseline failures unchanged), human UAT sign-off on byte-equality of canonical cookies.txt across real YouTube playback, and a PROJECT.md Key Decisions entry anchoring the FIX-02 restoration for future phases.
- Outcome:
- Real root cause: yt-dlp's library API does not auto-discover JS runtimes the way the CLI does.

---

## v1.5 Further Polish (Shipped: 2026-04-10)

**Phases completed:** 14 phases (21–34), 21 plans | **Stats:** 265/265 tests passing, ~9,900 LOC Python total | **Timeline:** 2026-04-06 → 2026-04-10 (5 days)

**Delivered:** Closed out v1.x with bug fixes discovered through daily use plus opportunistic feature polish — YouTube cookie import, multi-stream station model with failover and quality selection, Twitch streaming via streamlink + OAuth, hamburger-menu consolidation, elapsed-time counter, 15s YouTube failover gate with connecting-toast UX, and panel-layout sizing regression fix.

**Key accomplishments:**

- **FIX-01 (Phase 21):** YouTube thumbnail sizing regression fixed by switching from `Gtk.Picture` + `ContentFit.CONTAIN` to pre-scaled `GdkPixbuf` + `Gtk.Image` with 320×180 slot; root-caused to `Gtk.Picture.measure()` reporting source natural size regardless of `set_size_request`/`vexpand`. Live-UAT verified after the initial audit missed the regression.
- **Phase 22 (COOKIE-01..06):** YouTube cookie import via file picker, paste, or Google login (WebKit2 embedded browser); stored at `~/.local/share/musicstreamer/cookies.txt` with 0o600 permissions; yt-dlp always gets `--no-cookies-from-browser` and both yt-dlp/mpv use `--cookies=<path>` when present.
- **Phase 23 (FIX-02/03):** Cookie invocations use temp copies to preserve the imported original; mpv fast-exit (~2s) with cookies triggers one retry without cookies to survive corrupted cookie files.
- **Phases 24–26 (FIX-04/05/06):** Tag chips and filter chips wrap via `Gtk.FlowBox`; the broken standalone filter-bar Edit button was replaced with a now-playing edit icon gated on play/pause state.
- **Phase 27 (STR-01..14):** Multi-stream station model — `station_streams` table with quality/label/position, `stations.url` migrated and dropped, `ManageStreamsDialog` for CRUD/reorder, quality presets (hi/med/low/custom), Radio-Browser/YT/AudioAddict import integrated.
- **Phase 28 (D-01..08):** Stream failover engine with server round-robin, quality fallback queue, toast notifications, and stream-picker UI; 13 failover tests.
- **Phase 29 (MENU-01..05):** Hamburger menu consolidation — Discover, Import, Accent Color, and YouTube Cookies moved from the header bar into a two-section Gio menu driven by `SimpleAction`s.
- **Phase 30 (TIMER-01..06):** Elapsed-time counter in now-playing panel with pause/resume, station-change reset, failover-safe continuity, and adaptive `M:SS` / `H:MM:SS` formatting.
- **Phases 31–32 (TWITCH/TAUTH):** Twitch streaming via `streamlink --stream-url` feeding GStreamer playbin3; offline detection with toast (no failover); OAuth token auth via renamed `AccountsDialog` with WebKit2 subprocess that captures the Twitch auth-token cookie and writes it to `TWITCH_TOKEN_PATH` with 0o600 perms.
- **Phase 33 (FIX-07):** YouTube streams get a 15-second minimum wait window before `_try_next_stream` can fire; `_yt_attempt_start_ts` + `_yt_poll_timer_id` track the gate; cookie-retry re-seeds the timestamp; "Connecting…" `Adw.Toast` fires on all `play()` / `play_stream()` paths; `_cancel_failover_timer` clears the attempt timestamp. 264 tests pass after the phase.
- **Phase 34 (cleanup):** Fixed deferred `test_streamlink_called_with_correct_args` by monkeypatching `musicstreamer.player.TWITCH_TOKEN_PATH` to force the no-token branch; annotated the stale cookies-test deferred item in Phase 33 as already resolved in commit `b3e066b` during 33-02. Production code untouched. 265/265 tests pass.

**Tech debt carried forward:** panel-sizing has no automated regression test (GTK needs live display); `accounts_dialog.py` uses deprecated `tempfile.mktemp`; `~/.local/share/musicstreamer/mpv.log` has no rotation.

**Process lesson:** Retroactive verification based on static code inspection missed the FIX-01 runtime GTK-measure behavior. Future phases touching GTK widget sizing require live-display UAT as an explicit gate.

---

## v1.4 Media & Art Polish (Shipped: 2026-04-05)

**Phases completed:** 5 phases (16–20), 8 plans | **Stats:** 153 tests | 69 files changed, 8,484 insertions | 2 days

**Delivered:** Tuned GStreamer buffer to eliminate ShoutCast drop-outs, added AudioAddict logo fetch at import + editor, YouTube 16:9 thumbnail display, custom accent color picker, play/pause button, and MPRIS2 OS media key integration.

**Key accomplishments:**

- GStreamer playbin3 `buffer-duration` (10s) and `buffer-size` (10 MB) set via TDD — eliminates ShoutCast/HTTP audible drop-outs; constants live in `constants.py` per project pattern
- `ThreadPoolExecutor` workers with thread-local `db_connect()` download AA channel logos at bulk import time; two-phase progress in `ImportDialog`; silent failure on fetch error
- AA URL detection for all 6 network domains in station editor with daemon-thread logo fetch and API key popover; `_aa_channel_key_from_url` uses `urllib.parse` (not regex) to correctly strip network slug prefix
- YouTube thumbnails displayed as full 16:9 using `ContentFit.CONTAIN` in now-playing logo slot; cover slot stays on fallback to avoid duplication
- `AccentDialog` with 8 GNOME-preset swatches and hex entry — immediate CSS provider reload at `PRIORITY_USER`, inline error state on invalid hex, persisted via SQLite settings
- `Player.pause()` (GStreamer NULL state) + play/pause button between star and stop; station stays selected on pause; MPRIS2 D-Bus service wired via `dbus-python` — OS media keys fully functional

---

## v1.3 Discovery & Favorites (Shipped: 2026-04-03)

**Phases completed:** 4 phases (12–15), 8 plans | **Stats:** 127 tests | 3,150 source + 1,468 test Python LOC | 59 commits | 8 days

**Delivered:** Added favorites (star ICY tracks, Favorites list), Radio-Browser.info discovery dialog, YouTube playlist importer, and AudioAddict bulk importer with tabbed ImportDialog.

**Key accomplishments:**

- `Favorite` dataclass, SQLite table with UNIQUE(station_name, track_title) dedup, repo CRUD — `INSERT OR IGNORE` for silent dedup; `cover_art.last_itunes_result` caches genre for favorites without a second API call
- Star button in now-playing panel (gated on non-junk ICY title), `Adw.ToggleGroup` Stations/Favorites view switcher, favorites list with trash removal and empty state
- `radio_browser.py` API client (`search_stations`, `fetch_tags`, `fetch_countries`) using urllib + daemon threads; `repo.station_exists_by_url` and `repo.insert_station` for discovery save
- `DiscoveryDialog` modal: live search, tag/country dropdowns, per-row play buttons with prior-station resume, save to library — `url_resolved` preferred over `url` (avoids PLS/M3U)
- `yt_import.py` backend with `scan_playlist`/`import_stations`; `ImportDialog` two-stage scan→checklist flow with spinner, progress count, and per-item selection; thread-local SQLite for import worker
- `aa_import.py` backend: `fetch_channels`/`import_stations` across all AudioAddict networks, PLS→direct URL resolution at fetch time, quality tier selection; `ImportDialog` refactored to `Gtk.Notebook` tabs (YouTube + AudioAddict)

---

## v1.2 Station UX & Polish (Shipped: 2026-03-27)

**Phases completed:** 5 phases, 12 plans, 13 tasks

**Key accomplishments:**

- SQLite data layer for recently-played tracking (millisecond-precision timestamps) and key/value settings storage, with idempotent migrations and 10 new passing tests
- Adw.ExpanderRow provider groups replacing flat StationRow list, with dual render modes (grouped/flat) driven by filter state
- Recently Played section above provider groups using in-place ListBox insert to preserve ExpanderRow collapse state, wired to play hook and hidden during active filters
- `matches_filter_multi` added to filter_utils.py — set-based multi-select filter with OR-within-dimension, AND-between-dimension logic and case-insensitive tag matching
- Gtk.DropDown provider/tag filters replaced with scrollable Gtk.ToggleButton chip strips supporting OR-within-dimension, AND-between-dimensions multi-select
- Replaced freeform provider and tags text entries in EditStationDialog with Adw.ComboRow picker and scrollable ToggleButton chip panel, both supporting inline creation of new values
- YouTube URL focus-out now fetches stream title via yt-dlp and auto-populates empty name field, running in parallel with the existing thumbnail fetch using independent flags
- Player.set_volume clamps float to [0.0, 1.0], writes GStreamer pipeline volume property, stores for mpv subprocess launch — 4 TDD tests pass, 85-test suite green
- Provider name shown inline as "Name · Provider" in now-playing label; Gtk.Scale volume slider wired to GStreamer and persisted via settings — 85 tests green
- Rounded panel gradient, station art 5px border-radius (GTK4: set_overflow(HIDDEN) required on Gtk.Stack — CSS overflow alone insufficient), improved spacing throughout

---

## v1.1 Polish & Station Management (Shipped: 2026-03-21)

**Phases completed:** 2 phases, 4 plans | **Stats:** 58 tests | 1,782 Python LOC | 27 commits | 1 day

**Delivered:** Fixed GTK markup escaping for ICY titles, surfaced station logos in the list, added delete station, per-station ICY disable, and YouTube thumbnail auto-fetch.

**Key accomplishments:**

- GTK markup escaping: `&`, `<`, `>` in ICY titles and station names display as literal characters
- Station logo pre-loaded into cover art slot as default; junk ICY title no longer clears it
- Station list always shows 48px prefix widget — logo when available, generic icon otherwise
- `Station.icy_disabled` field, SQLite migration, repo CRUD, and MainWindow playback guard for per-station ICY suppression
- Delete Station in edit dialog with playing guard (blocks deletion while streaming) and confirmation dialog
- YouTube URL auto-fetch: entering a YT URL triggers yt-dlp thumbnail fetch with spinner feedback

---

## v1.0 MVP (Shipped: 2026-03-20)

**Phases completed:** 4 phases, 8 plans, 0 tasks

**Delivered:** Transformed a monolithic GTK4/Python radio player into a modular, feature-rich app with live search/filter, ICY metadata display, and iTunes cover art.

**Stats:** 4 phases | 8 plans | 43 tests | 1,409 Python LOC | 74 files changed | 35 days

**Key accomplishments:**

- Refactored ~512-line `main.py` monolith into clean `musicstreamer/` package (constants, models, repo, assets, player, UI)
- TDD filter engine with real-time AND-composed search + provider/tag dropdowns and empty-state handling
- GStreamer ICY TAG bus wired to now-playing panel — live track titles with latin-1 mojibake correction
- Three-column now-playing panel: station logo (left), track info + Stop (center), cover art (right)
- iTunes Search API cover art with junk title detection, session dedup, and smooth in-flight transitions
- 43 automated tests across 4 modules; zero regressions across all phases

---
