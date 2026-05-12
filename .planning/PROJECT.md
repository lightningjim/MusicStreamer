# MusicStreamer

## What This Is

A personal GNOME desktop app for listening to curated internet radio and live streams. Supports ShoutCast-style streams (AudioAddict, Soma.FM, etc.) and YouTube live streams (e.g., Lofi Girl). Designed for a personal library of 50–200 stations organized by provider with multi-select filtering, recently played, live track title display, cover art from iTunes, volume control, favorites (star ICY tracks), in-app Radio-Browser.info discovery, and bulk import from YouTube playlists or AudioAddict networks.

## Core Value

Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## Current Milestone: v2.1 Fixes and Tweaks

**Goal:** Burn down v2.0 carry-forward bugs and small polish features, while leaving room to absorb new issues and improvements as they surface from daily use. Same shape as v1.1 / v1.5 — a rolling polish milestone where new phases get added via `/gsd-add-phase` as you find them.

**Target features:**

*Phase 44 carry-forward (Windows polish):*
- Audio pause/restart glitch + ignored volume setting on Windows (GStreamer)
- DI.fm HTTPS-fallback policy decision
- Start Menu shortcut with `AppUserModel.ID=org.lightningjim.MusicStreamer` so SMTC overlay shows "MusicStreamer" not "Unknown app"
- Fix `test_thumbnail_from_in_memory_stream` (`MagicMock` not awaitable — needs `AsyncMock` for `store_async`)

*Already parked for v2.1+:*
- SEED-006 — Visual color picker for accent dialog
- SEED-008 — GBS-FM integration

*Pending todos (pull in opportunistically):*
- Station art fetching beyond YouTube (`.planning/notes/2026-04-03-...`)
- SDR live radio support (`.planning/notes/2026-03-21-...`)

**Open-ended scope:** Additional phases will be added throughout v2.1 as Kyle plays with the app and reports issues/improvements. The initial scope above seeds the milestone; the closing scope is decided when Kyle calls `/gsd-complete-milestone`.

## Previous Milestone: v2.0 OS-Agnostic Revamp ✓ SHIPPED 2026-04-25

**Delivered:** 17 phases in core scope (35–48 with .x sub-phases) + 5 backlog regression fixes (999.1, 999.3, 999.7, 999.8, 999.9), 81 plans total. All 35 active requirements satisfied (PKG-05 retired). Cross-phase integration verified clean (182 wiring tests pass). Windows installer EXE shipped via PyInstaller + Inno Setup, signed off via Win11 VM UAT.

**Headline outcomes:**
- GTK4/Libadwaita fully retired — single PySide6 codebase across Linux + Windows
- Player.py rewritten as QObject with typed Qt signals; GLib calls eliminated
- Cross-platform media keys: MPRIS2 (Linux) via QtDBus + SMTC (Windows) via winrt
- Settings export/import ZIP with merge dialog (manual sync replaces v2.1+ cloud-sync goal)
- Windows installer at `%LOCALAPPDATA%\Programs\MusicStreamer` with single-instance + Node.js runtime check
- Stream quality ordering by codec rank + bitrate (Phase 47); buffer-fill indicator (47.1); AutoEQ parametric EQ (47.2)
- GStreamer 1.28+ on Windows pinned: requires `flags & ~0x1` to skip video pad on audio-only consumption + `gst-libav` for AAC/H.264 decoders + `chardet>=5,<6` for requests' char-detection (charset_normalizer mypyc shared module not bundle-collectible)

## Previous Milestone: v1.5 Further Polish ✓ SHIPPED 2026-04-10

**Delivered:** 14 phases (21–34), 21 plans, 53 requirements satisfied. Fixed all bugs surfaced during daily use plus opportunistic polish: multi-stream failover, Twitch via streamlink + OAuth, hamburger-menu consolidation, elapsed-time counter, YouTube cookie import, 15s YouTube failover gate, panel-layout sizing regression fix, and the Phase 33 deferred-test cleanup in Phase 34.

## Current State (Phase 69 complete — 2026-05-11)

- **Package:** `musicstreamer/` — constants, models, repo, assets, player, ui_qt/, radio_browser.py, yt_import.py, aa_import.py, accent_utils.py, cover_art.py, paths.py, url_helpers.py
- **LOC:** ~13,000 Python total (source + tests) | **Tests:** 399 passing, 1 pre-existing failure
- **Stack:** Python + PySide6 + GStreamer + SQLite + yt-dlp + streamlink + urllib (iTunes API, Radio-Browser API, AudioAddict API). GTK4/Libadwaita deleted in Phase 36. Node.js runtime for yt-dlp EJS solver. mpv removed in Phase 35.
- **Station list:** Provider-grouped tree + recently played section; collapsible filter strip with search box, provider/tag chip rows (FlowLayout wrapping, OR-within/AND-between), clear-all; segmented Stations/Favorites toggle; station star delegate on tree rows
- **Now-playing:** Three-column panel — logo (16:9 for YouTube via ContentFit.CONTAIN, square otherwise) | "Name · Provider" / track title / Edit+Star+Pause+Stop+StreamPicker | cover art; volume slider with GStreamer + persistence; star button for ICY track favorites; edit button opens EditStationDialog; stream picker QComboBox syncs with failover
- **Cover art:** iTunes Search API, junk detection, session dedup, placeholder fallback; genre cached in `last_itunes_result` for favorites
- **Station management:** EditStationDialog (Qt) — editable provider combo, FlowLayout tag chips, multi-stream QTableWidget (add/remove/reorder, quality presets), ICY disable toggle, delete with playing guard, YouTube/AA thumbnail auto-fetch
- **Favorites:** Star ICY track titles, store in SQLite with station/provider/genre context, toggle Favorites/Stations view inline, remove with trash button; star stations from tree rows
- **Discovery:** DiscoveryDialog (Qt) — search Radio-Browser.info by name, filter by tag/country, inline preview play via main Player, save to library with url_resolved preference
- **Import:** ImportDialog (Qt, tabbed) — YouTube playlist tab (scan→checklist, live-streams only, progress bar); AudioAddict tab (API key, quality selector, all networks, dedup by URL, PLS resolution, logo download, progress bar)
- **Playback:** GStreamer buffer tuned (10s/10MB); pause keeps station selected; MPRIS2 D-Bus service for OS media keys
- **Settings sync:** Manual export/import — ZIP with settings.json + logos/, merge-by-URL or replace-all, summary dialog with counts + expandable list, hamburger menu access
- **Personalization:** Custom accent color picker (8 presets + hex), CSS provider at PRIORITY_USER, persisted in SQLite
- **YouTube Cookies:** Import cookies via file picker, paste, or Google login (WebKit2 subprocess); stored at ~/.local/share/musicstreamer/cookies.txt with 0o600 permissions; yt-dlp always gets --no-cookies-from-browser; both yt-dlp and mpv use --cookies when file exists. **Phase 999.7:** yt-dlp library invocations route cookies through a per-call temp copy via `musicstreamer/cookie_utils.temp_cookies_copy()` so the canonical file is never rewritten; corrupted files (yt-dlp marker header) are auto-cleared with a toast at the read site.

## Requirements

### Validated

- ✓ Play ShoutCast/mp3/aac streams via GStreamer — existing pre-v1.0
- ✓ Play YouTube live streams via yt-dlp + GStreamer — existing pre-v1.0
- ✓ Add and edit stations (name, URL, provider, tags, art) — existing pre-v1.0
- ✓ Station art (1:1 logo image per station) — existing pre-v1.0
- ✓ SQLite persistence in ~/.local/share/musicstreamer/ — existing pre-v1.0
- ✓ Codebase modularised (constants, models, repo, assets, player, UI) — v1.0 Phase 1
- ✓ Live search filters station list by name in real time — v1.0 Phase 2
- ✓ Provider dropdown filters to selected provider — v1.0 Phase 2
- ✓ Tag dropdown filters to selected genre/tag — v1.0 Phase 2
- ✓ Search + dropdowns compose with AND logic — v1.0 Phase 2
- ✓ Clear all filters returns full list — v1.0 Phase 2
- ✓ ICY track title shown and auto-updates mid-stream — v1.0 Phase 3
- ✓ YouTube streams show station name when no ICY metadata — v1.0 Phase 3
- ✓ Station brand logo displayed top-left in now-playing — v1.0 Phase 3
- ✓ Cover art displayed top-right via iTunes Search API — v1.0 Phase 4
- ✓ Placeholder shown when no cover art available — v1.0 Phase 4
- ✓ ICY track titles with &, <, > display as literal characters — v1.1 Phase 5
- ✓ Cover art slot shows station logo when no ICY title available — v1.1 Phase 5
- ✓ Station list shows each station's logo inline per row — v1.1 Phase 5
- ✓ User can delete a station from the list — v1.1 Phase 6
- ✓ Station editor auto-populates image from YouTube thumbnail — v1.1 Phase 6
- ✓ User can disable ICY metadata per station — v1.1 Phase 6
- ✓ BROWSE-01: Stations grouped by provider in list, collapsed by default, expandable — v1.2 Phase 7
- ✓ BROWSE-04: "Recently Played" section at top showing last 3 played stations, most recent first — v1.2 Phase 7
- ✓ BROWSE-02: User can filter by multiple providers simultaneously — v1.2 Phase 8
- ✓ BROWSE-03: User can filter by multiple genres/tags simultaneously — v1.2 Phase 8
- ✓ MGMT-01: Station editor shows existing providers as selectable options — v1.2 Phase 9
- ✓ MGMT-02: Station editor shows existing genres/tags as selectable options (multi-select) — v1.2 Phase 9
- ✓ MGMT-03: User can add a new provider/genre inline from the station editor — v1.2 Phase 9
- ✓ MGMT-04: YouTube station URL auto-imports stream title — v1.2 Phase 9
- ✓ NP-01: Now Playing panel shows provider name alongside station name — v1.2 Phase 10
- ✓ AUDIO-01: Volume slider in main window controls playback volume — v1.2 Phase 10
- ✓ AUDIO-02: Volume setting persists between sessions — v1.2 Phase 10
- ✓ UI-01: Panels use rounded corners — v1.2 Phase 11
- ✓ UI-02: Colors softened with subtle gradients — v1.2 Phase 11
- ✓ UI-03: Station list rows have more vertical padding — v1.2 Phase 11
- ✓ UI-04: Now Playing panel has more internal whitespace — v1.2 Phase 11
- ✓ FAVES-01: User can star the currently playing ICY track title — v1.3 Phase 12
- ✓ FAVES-02: Favorites stored in DB with station name, provider, and track title — v1.3 Phase 12
- ✓ FAVES-03: Favorites view replaces station list inline (toggle between Stations / Favorites) — v1.3 Phase 12
- ✓ FAVES-04: User can remove a favorite from the Favorites view — v1.3 Phase 12
- ✓ DISC-01: User can search Radio-Browser.info stations by name/provider from in-app discovery dialog — v1.3 Phase 13
- ✓ DISC-02: User can filter Radio-Browser.info results by tag (genre) or country — v1.3 Phase 13
- ✓ DISC-03: User can play a Radio-Browser.info station as a preview without saving to library — v1.3 Phase 13
- ✓ DISC-04: User can save a Radio-Browser.info station to their library — v1.3 Phase 13
- ✓ IMPORT-01: User can paste a YouTube playlist URL and import live streams as stations with progress feedback — v1.3 Phase 14
- ✓ IMPORT-02: User can enter an AudioAddict API key to import all network channels, skipping duplicates — v1.3 Phase 15
- ✓ IMPORT-03: User can select stream quality (hi / med / low) before importing AudioAddict channels — v1.3 Phase 15
- ✓ STREAM-01: GStreamer buffer-duration (10s) and buffer-size (10 MB) tuned — ShoutCast/HTTP drop-outs eliminated — v1.4 Phase 16
- ✓ ART-01: AudioAddict channel logos fetched from AA API at bulk import time via ThreadPoolExecutor workers — v1.4 Phase 17
- ✓ ART-02: Station editor auto-fetches AA logo on URL paste (same UX as YouTube thumbnail) — v1.4 Phase 17
- ✓ ART-03: YouTube thumbnails displayed as full 16:9 via ContentFit.CONTAIN; non-YouTube art unaffected — v1.4 Phase 18
- ✓ ACCENT-01: Custom accent color with 8 presets + hex input, CSS at PRIORITY_USER, persisted in SQLite — v1.4 Phase 19
- ✓ CTRL-01: Play/pause button between star and stop; pause keeps station selected and now-playing visible — v1.4 Phase 20
- ✓ CTRL-02: MPRIS2 D-Bus service wired via dbus-python — OS media keys control pause/resume/stop — v1.4 Phase 20

- ✓ FIX-01: YouTube 16:9 thumbnail does not inflate now-playing panel when window is maximized/fullscreen — v1.5 Phase 21 (fixed via GdkPixbuf pre-scale + Gtk.Image, live UAT confirmed)
- ✓ FIX-02: yt-dlp/mpv cookie invocations use temporary copies so original cookies.txt is never overwritten — v1.5 Phase 23
- ✓ FIX-03: mpv fast-exit (~2s) with cookies triggers one retry without cookies — v1.5 Phase 23
- ✓ FIX-04: Tag chip FlowBox in edit dialog wraps instead of overflowing — v1.5 Phase 24
- ✓ FIX-05: Provider/tag filter chip containers wrap via FlowBox — v1.5 Phase 25
- ✓ FIX-06: Standalone Edit button replaced with now-playing edit icon gated on play/pause — v1.5 Phase 26
- ✓ FIX-07: YouTube streams get 15s minimum wait before failover + "Connecting…" toast on all play paths — v1.5 Phase 33
- ✓ COOKIE-01..06: YouTube cookie import via file/paste/Google login, 0o600 perms, hamburger menu entry — v1.5 Phase 22
- ✓ STR-01..14: Multi-stream per station model (station_streams table, quality presets, ManageStreamsDialog, Radio-Browser/YT/AudioAddict integration) — v1.5 Phase 27
- ✓ D-01..08 (Stream Failover): Toast + picker + round-robin queue, 13 failover tests — v1.5 Phase 28
- ✓ MENU-01..05: Hamburger menu consolidation (Discover, Import, Accent, YT Cookies) — v1.5 Phase 29
- ✓ TIMER-01..06: Elapsed time counter, pause/resume, failover-safe — v1.5 Phase 30
- ✓ TWITCH-01..08: Twitch streaming via streamlink, offline detection, failover integration — v1.5 Phase 31
- ✓ TAUTH-01..07: Twitch OAuth token auth via AccountsDialog + WebKit2 capture — v1.5 Phase 32
- ✓ PHASE-33-DEFERRED: Twitch test fixture fixed (monkeypatch TWITCH_TOKEN_PATH), stale cookies-test bullet annotated as already resolved — v1.5 Phase 34

### Active (v2.1)

Requirements for v2.1 live in `.planning/REQUIREMENTS.md` (generated by the roadmap cycle). Initial scope (now all shipped): the six v2.0 backlog bug stubs, the Phase 44 Windows polish carry-forward, and the two dormant seeds (visual color picker + GBS-FM). The milestone has since absorbed additional bugs/improvements as they surfaced from daily use. Rolling milestone — phases added throughout via `/gsd-add-phase`.

### Out of Scope

| Feature | Reason |
|---------|--------|
| Radio-Browser.info as primary browse mode | Anti-feature — undermines curated library model; discovery is modal/import flow only |
| Playback history distinct from favorites | Different use case; favorites are intentional stars, not automatic history |
| Auto-refresh saved Radio-Browser stations | Stations in library are managed manually; auto-refresh adds complexity for unclear benefit |
| Social sharing / export of favorites | Single-user desktop app |
| MusicBrainz cover art fallback | iTunes sufficient; revisit if gaps found |
| ~~Twitch stream support~~ | Implemented in Phase 31 via streamlink |
| Local music library / file playback | Streaming app only |
| Multi-user / authentication | Single-user desktop app |
| Podcast support | Different use case |
| Last.fm scrobbling | Future enhancement |
| Mobile app | Linux GNOME desktop only |

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Search + dropdowns for filtering | User explicitly chose this over sidebar/chips | ✓ Good — clean UX, easy to compose |
| ICY metadata via GStreamer TAG bus | Already flowing in pipeline | ✓ Good — zero extra dependencies |
| Cover art via iTunes Search API | Free, no key required | ✓ Good — works for most western music |
| `urllib` over `requests` for iTunes fetch | No extra dependency | ✓ Good — stdlib sufficient |
| GLib.idle_add for cross-thread UI updates | GStreamer bus on non-GTK thread | ✓ Good — established pattern, no races |
| GdkPixbuf pre-scale to 160×160 | Avoid GTK downscale artifacts | ✓ Good — consistent with logo slot |
| Gtk.Stack for logo/art slots | Smooth fallback swap without flicker | ✓ Good — reused across both slots |
| Session dedup via `_last_cover_icy` | Avoid redundant API calls on repeated TAG | ✓ Good — no external cache needed |
| set_text() not set_markup() for ICY labels | set_text() does not parse Pango markup | ✓ Good — no escaping needed for plain labels |
| markup_escape_text in Adw.ActionRow | ActionRow title/subtitle ARE parsed as Pango markup | ✓ Good — escaping required here |
| Adw.SwitchRow for ICY toggle | Native Adwaita toggle, integrates with form layout | ✓ Good — consistent with Adwaita HIG |
| daemon thread + GLib.idle_add for YT thumbnail | yt-dlp subprocess must not block GTK main loop | ✓ Good — established cross-thread pattern |
| Gtk.Stack (pic/spinner) in arts grid | Avoids re-parenting station_pic during fetch | ✓ Good — no flicker during thumbnail load |
| strftime ms precision for last_played_at | datetime('now') second-level granularity caused ordering failures | ✓ Good |
| Drop set_filter_func for grouped list | filter_func cannot inspect ExpanderRow children added via add_row() | ✓ Good |
| ExpanderRow activated signal for play | row-activated on outer ListBox does not fire for group children | ✓ Good |
| ListBox.insert(row,0) for RP refresh | Preserves ExpanderRow expand/collapse state vs. full reload | ✓ Good |
| Empty set = inactive filter dimension | Parallel to None/empty string convention in matches_filter | ✓ Good |
| _rebuilding flag for bulk chip mutations | Prevents spurious filter updates during rebuild/clear | ✓ Good |
| new_provider_entry takes precedence | Typed value always wins over combo selection | ✓ Good |
| Volume stored as float 0.0–1.0 | Convert to int only at mpv call site | ✓ Good |
| Provider as "Name · Provider" (U+00B7) | Clean inline label without extra UI elements | ✓ Good |
| Volume default 80 not 100 | Avoid blasting on first launch | ✓ Good |
| CSS on Gtk.Stack container for border-radius | Stack is the clip container — radius not visible on Gtk.Image | ✓ Good |
| INSERT OR IGNORE for favorites dedup | UNIQUE(station_name, track_title) constraint; silent no-op on repeat star | ✓ Good |
| last_itunes_result module-level dict | Caches full iTunes result so genre is available for favorites without a second API call | ✓ Good |
| Adw.ToggleGroup for Stations/Favorites switcher | Native Adwaita segmented control, HIG-compliant | ✓ Good |
| url_resolved preferred over url (Radio-Browser) | url is often a PLS/M3U playlist, url_resolved is the direct stream | ✓ Good |
| is_live is True strict identity check (yt-dlp) | Non-live entries return None not False in flat-playlist extract mode | ✓ Good |
| Thread-local db_connect() in import workers | SQLite connections cannot be shared across threads | ✓ Good |
| ch['key'] not ch['name'] for AudioAddict PLS slug | Channel names have spaces; keys are lowercase slugs used in URL paths | ✓ Good |
| ValueError('no_channels') for empty AudioAddict response | Catches expired API keys returning 200+empty instead of 401 | ✓ Good |
| Resolve PLS to direct URL in aa_import.fetch_channels | GStreamer cannot play PLS playlists; resolution must happen at import time | ✓ Good |
| Twitch via streamlink | `_play_twitch()` resolves HLS URL via `streamlink --stream-url`, feeds to GStreamer playbin3; offline detection with toast | ✓ Good — Phase 31 |
| Buffer constants in constants.py (not inlined) | Consistent with project pattern, allows future tuning | ✓ Good |
| ThreadPoolExecutor for AA logo downloads | Async/decoupled from insert loop — avoids import regression | ✓ Good |
| Thread-local db_connect() in logo workers | SQLite connections cannot be shared across threads | ✓ Good |
| _aa_channel_key_from_url strips network slug prefix | Stream URL paths are slug-prefixed; AA API images by bare channel name | ✓ Good |
| ContentFit.CONTAIN for YouTube 16:9 in 160×160 slot | No slot widening — CONTAIN letterboxes cleanly within existing dimensions | ✓ Good |
| Cover slot stays on fallback for YouTube stations | Avoids duplicate thumbnail in both logo and cover slots | ✓ Good |
| CssProvider at PRIORITY_USER for accent color | Overrides app-level theme tokens; PRIORITY_APPLICATION insufficient | ✓ Good |
| Player.pause() identical to stop() | "Keep station selected" logic lives in main_window, not player | ✓ Good |
| DBusGMainLoop(set_as_default=True) at module import | Must be called before dbus.service.Object class definition | ✓ Good |
| Edit icon in now-playing controls_box, not filter bar | Filter bar Edit button was broken by ExpanderRow grouping; per-row edit icons already exist; now-playing edit is more useful | ✓ Good |
| Dropped mpv subprocess fallback for YouTube (Plan 35-06) | yt-dlp library API with `extractor_args={'youtubepot-jsruntime': {'remote_components': ['ejs:github']}}` + Node.js runtime resolves cookie-protected and JS-challenged YouTube streams directly; mpv provided no independent resolution path since it shells out to the same yt-dlp extractor internally. Supersedes the original Phase 35 KEEP_MPV spike decision. | ✓ Good — v2.0 Plan 35-06 |
| Phase 999.7: FIX-02 restored on yt-dlp library API path | Plan 35-06 replaced the mpv subprocess with `yt_dlp.YoutubeDL` and dropped the v1.5 Phase 23 temp-copy wrapper. yt-dlp's `YoutubeDL.__exit__` calls `save_cookies()` whenever `cookiefile` is set, clobbering the canonical file with its own serialization. Restored via shared `musicstreamer/cookie_utils.py` (`is_cookie_file_corrupted` predicate + `temp_cookies_copy()` @contextmanager with `mkstemp` + `copy2` + unlink-in-finally). Both yt-dlp read sites (`player._youtube_resolve_worker` + `yt_import.scan_playlist`) route cookies through the ctxmgr. Corrupted files auto-clear with a toast. Cross-platform: uses `mkstemp` over `NamedTemporaryFile` for Windows compat (v2.0). | ✓ Good — v2.0 Phase 999.7 |

## Versioning

The `pyproject.toml` `version` field follows `{major}.{minor}.{phase}`, where `{major}.{minor}` is sourced from the `## Current Milestone: vX.Y` heading above and `{phase}` is the most recently completed phase number. The bump is automated by `tools/bump_version.py` via the `.claude/settings.json` PreToolUse hook on `gsd-sdk query commit "docs(phase-NN): complete phase execution"` — gated by the `workflow.auto_version_bump` flag in `.planning/config.json` (default: true).

**Worked example:** Closing Phase 50 of v2.1 yields `version = "2.1.50"`; closing Phase 63 yields `2.1.63`. The leading `2.1` comes from `## Current Milestone: v2.1` in this file.

## Constraints

- **Tech stack:** Python + GTK4/Libadwaita — no framework changes
- **Platform:** Linux GNOME desktop only
- **No network auth:** API keys only where required by service (AudioAddict)
- **Test runner:** pytest via `uv run --with pytest` (no system pip)

## Phase History

| Phase | Milestone | Status | Completed |
|-------|-----------|--------|-----------|
| 1: Module Extraction | v1.0 | ✓ Complete | 2026-03-18 |
| 2: Search and Filter | v1.0 | ✓ Complete | 2026-03-19 |
| 3: ICY Metadata Display | v1.0 | ✓ Complete | 2026-03-20 |
| 4: Cover Art | v1.0 | ✓ Complete | 2026-03-20 |
| 5: Display Polish | v1.1 | ✓ Complete | 2026-03-21 |
| 6: Station Management | v1.1 | ✓ Complete | 2026-03-21 |
| 7: Station List Restructuring | v1.2 | ✓ Complete | 2026-03-22 |
| 8: Filter Bar Multi-Select | v1.2 | ✓ Complete | 2026-03-22 |
| 9: Station Editor Improvements | v1.2 | ✓ Complete | 2026-03-23 |
| 10: Now Playing & Audio | v1.2 | ✓ Complete | 2026-03-24 |
| 11: UI Polish | v1.2 | ✓ Complete | 2026-03-25 |
| 12: Favorites | v1.3 | ✓ Complete | 2026-03-31 |
| 13: Radio-Browser Discovery | v1.3 | ✓ Complete | 2026-04-01 |
| 14: YouTube Playlist Import | v1.3 | ✓ Complete | 2026-04-02 |
| 15: AudioAddict Import | v1.3 | ✓ Complete | 2026-04-03 |
| 16: GStreamer Buffer Tuning | v1.4 | ✓ Complete | 2026-04-03 |
| 17: AudioAddict Station Art | v1.4 | ✓ Complete | 2026-04-03 |
| 18: YouTube Thumbnail 16:9 | v1.4 | ✓ Complete | 2026-04-05 |
| 19: Custom Accent Color | v1.4 | ✓ Complete | 2026-04-05 |
| 20: Playback Controls & Media Keys | v1.4 | ✓ Complete | 2026-04-05 |
| 21: Panel Layout Fix | v1.5 | ✓ Complete | 2026-04-10 |
| 22: Import YT Cookies | v1.5 | ✓ Complete | 2026-04-07 |
| 23: Fix YT Playback (cookies) | v1.5 | ✓ Complete | 2026-04-07 |
| 24: Tag Chip FlowBox | v1.5 | ✓ Complete | 2026-04-08 |
| 25: Filter Chip Overflow | v1.5 | ✓ Complete | 2026-04-08 |
| 26: Edit Button Fix | v1.5 | ✓ Complete | 2026-04-08 |
| 27: Multi-Stream Model | v1.5 | ✓ Complete | 2026-04-08 |
| 28: Stream Failover | v1.5 | ✓ Complete | 2026-04-09 |
| 29: Hamburger Menu Consolidation | v1.5 | ✓ Complete | 2026-04-09 |
| 30: Elapsed Time Counter | v1.5 | ✓ Complete | 2026-04-09 |
| 31: Twitch via Streamlink | v1.5 | ✓ Complete | 2026-04-09 |
| 32: Twitch OAuth Token | v1.5 | ✓ Complete | 2026-04-10 |
| 33: YT 15s Wait + Toast | v1.5 | ✓ Complete | 2026-04-10 |
| 34: Deferred Items from Phase 33 | v1.5 | ✓ Complete | 2026-04-10 |

---
## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-11 — Phase 69 (Debug why AAC streams aren't playing in Windows) complete. WIN-05 closed. New `tools/check_bundle_plugins.py` source-of-truth helper enumerating `REQUIRED_PLUGIN_DLLS = {"gstlibav.dll": ("avdec_aac", "gst-libav"), "gstaudioparsers.dll": ("aacparse", "gst-plugins-good")}`. `packaging/windows/build.ps1` step 4b plugin-presence guard with exit code 10 (WR-01-compliant `Write-Host -ForegroundColor Red`). Conda recipe in `packaging/windows/README.md` expanded with `gst-libav gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly` (rediscovered Phase 43 spike findings were never fully productionized — the recipe shipped only `gstreamer` meta-package which has zero plugin runtime deps). Two new drift-guard pytests in `tests/test_packaging_spec.py` (8/8 pass). CONCERNS.md GStreamer Windows Plugin Availability section reconciled. Also productionized Phase 43.1 Pitfall #1 mid-UAT — added `pyside6` to the conda recipe + loosened `pyproject.toml` PySide6 pin to `>=6.10` (conda-forge's pyside6 6.10.1; pip's 6.11.0 wheel is ICU-ABI-incompatible with conda-forge's ICU 78 after gst-libav's transitive deps bumped it). Empirical PASS on Win11 VM: new step 4b guard fired live during rebuild when env was missing gst-libav (validating G-01); after env recreate, all tested AAC streams (multiple AA + SomaFM) play on the rebuilt installer. Verification 10/10.*

*Phase 68 (Live performance stream detection — DI.fm) complete — 2026-05-10. New pure-Python module `musicstreamer/aa_live.py` with `fetch_live_map`, `_parse_live_map` (UTC-coerced ISO 8601 with Z-suffix defense), `detect_live_from_icy` (LIVE: / LIVE - prefix only, no false positives), `get_di_channel_key`. NowPlayingPanel grew an inline `LIVE` badge next to the ICY title plus an `_AaLiveWorker` (QThread) polling `https://api.audioaddict.com/v1/di/events` (no-auth) on adaptive cadence — 60s while playing DI.fm, 5min otherwise. Three transition toasts (bind-to-already-live, off→on, on→off) via new `live_status_toast` signal wired to ToastOverlay (QA-05 bound method). StationListPanel grew a "Live now" filter chip (hidden when no `audioaddict_listen_key`) backed by StationFilterProxyModel `set_live_map`/`set_live_only` with Pitfall 7 invalidate guard. MainWindow lifecycle wires poll start in __init__, stop+wait(16s) in closeEvent, and `_check_and_start_aa_poll` reactive hook on AccountsDialog/ImportDialog close (B-04). Code review surfaced 4 blockers — all fixed inline (Z-suffix normalization, worker.wait on close, try/except in reschedule, idempotent start). 254 Phase 68 tests pass; verification 12/12 must-haves.*

*Phase 67 (Show Similar Stations) — complete. NowPlayingPanel master-toggle "Similar Stations" container with Same-provider + Same-tag pools (5 random each), refresh ↻, ▾/▸ collapse, click→play. SQLite key `show_similar_stations` (default off). Phase 64 sibling line untouched. Pure helpers `pick_similar_stations` + `render_similar_html` in `url_helpers.py`. 188 tests; 9/9 must-haves.*
