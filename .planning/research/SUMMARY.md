# Project Research Summary

**Project:** MusicStreamer v1.3 — Discovery & Favorites
**Domain:** GTK4/Python personal desktop internet radio player
**Researched:** 2026-03-27
**Confidence:** HIGH (stack/architecture/favorites); MEDIUM (AudioAddict API)

## Executive Summary

MusicStreamer v1.3 adds four discrete feature groups to a well-established GTK4/GStreamer codebase: Favorites (star ICY tracks), Radio-Browser.info discovery, AudioAddict import, and YouTube playlist import. All research converges on the same conclusion: zero new dependencies are required. Every capability maps directly onto existing patterns — urllib for REST calls, yt-dlp for playlist extraction, SQLite for favorites storage, and the daemon-thread + GLib.idle_add pattern for all async network I/O.

The recommended build order is risk-ascending: Favorites first (pure DB + UI, no network), Radio-Browser second (clean public REST API), YouTube playlist third (extends existing yt-dlp integration), AudioAddict last (unofficial API, highest external uncertainty). Architecture research identifies clear module boundaries — importer modules are GTK-free, returning plain dicts/lists; dialogs own the GLib wiring; FavoritesRepo shares `repo.con` to avoid SQLite write-lock contention.

The primary risk is the AudioAddict unofficial API. URL construction patterns and PLS format have been stable for years across community implementations, but cannot be verified without a live account. Build this phase last and treat empirical API verification as the first step of that phase. All other risks are implementation hygiene: threading discipline, result limits on Radio-Browser queries, ICY junk-title gating, and DB migration idempotency.

## Key Findings

### Recommended Stack

No new pip dependencies for any v1.3 feature. The existing stack (GTK4/Libadwaita, GStreamer, PyGObject, SQLite3, yt-dlp, urllib, threading/GLib.idle_add) covers all requirements. Radio-Browser.info uses urllib with DNS-discovered server selection (`all.api.radio-browser.info`). AudioAddict uses urllib + configparser (stdlib) for PLS parsing. YouTube playlist import uses the existing yt-dlp Python API with `extract_flat=True`. Favorites storage is a new `favorites` table in the existing SQLite DB, added via `CREATE TABLE IF NOT EXISTS` in `db_init()`.

**Core technologies:**
- `urllib.request` (stdlib): Radio-Browser + AudioAddict API calls — already used for iTunes, identical pattern
- `yt_dlp` (existing): YouTube playlist flat extraction — direct extension of single-video usage
- `sqlite3` (stdlib): favorites table — `CREATE TABLE IF NOT EXISTS` migration in existing `db_init()`
- `threading` + `GLib.idle_add` (existing): all async network I/O — established pattern, no new primitives
- `configparser` (stdlib): AudioAddict PLS parsing — INI-compatible format, no parsing library needed

### Expected Features

**Must have (table stakes):**
- Star current ICY track — core affordance of any music app with track metadata
- Favorites stored with station context (name, provider) — denormalized for station-deletion resilience
- Favorites inline list view with Stations/Favorites toggle in sidebar
- Remove from favorites — required; bad favorites accumulate without it
- Radio-Browser.info search by name — unusable without it given 30k+ stations
- Radio-Browser.info preview (play without saving) — audition before committing to library
- Radio-Browser.info save to library — the only reason to open a directory
- AudioAddict import across all four networks with quality selection
- YouTube playlist import filtered to live streams only

**Should have (competitive):**
- Radio-Browser.info tag/country filter — discovery vs. just finding known stations
- AudioAddict incremental import (skip existing by URL) — no duplicates on re-run
- Favorites: iTunes genre metadata on star — enriches record at zero extra cost (iTunes already queried)
- YouTube import: progress feedback (spinner, count of imported/skipped)

**Defer (v2+):**
- Social sharing or export of favorites
- Full persistent "browse mode" as primary UI (anti-feature — undermines curated library model)
- Auto-refresh of saved Radio-Browser stations
- Playback history distinct from intentional favorites

### Architecture Approach

The v1.3 architecture is purely additive. Three new `importers/` modules (radio_browser, audioaddict, youtube), one new `favorites_repo.py`, three new UI files (favorites_view, discovery_dialog, import_dialog), and targeted additions to main_window.py and models.py. Existing modules (repo, player, cover_art, assets, filter_utils) are untouched except extending the cover_art callback to `(path, genre_or_None)`. Phases A (Favorites) and B (Radio-Browser) are fully independent; C (AudioAddict) and D (YouTube) share the ImportDialog shell.

**Major components:**
1. `importers/radio_browser.py` — DNS server discovery + REST search, returns plain dicts; zero GTK imports
2. `importers/audioaddict.py` — channel list fetch + PLS parse, returns station dicts; zero GTK imports
3. `importers/youtube.py` — yt-dlp extract_flat + live filter, returns station dicts; zero GTK imports
4. `favorites_repo.py` — CRUD for favorites table; shares `repo.con` (no second connection)
5. `ui/favorites_view.py` — ListBox of favorited tracks with inline delete per row
6. `ui/discovery_dialog.py` — Radio-Browser search/preview/save modal
7. `ui/import_dialog.py` — tabbed AudioAddict + YouTube import with progress bar

### Critical Pitfalls

1. **Radio-Browser sync HTTP on GTK main thread** — all urllib calls go to daemon threads; debounce search-changed by 300ms via `GLib.timeout_add` to avoid a thread per keystroke
2. **YouTube yt-dlp blocking main thread** — always run `extract_info` in a daemon thread; show spinner during import; window freezes 10–30s otherwise
3. **Favorites duplicates from missing UNIQUE constraint** — use `INSERT OR IGNORE` with `UNIQUE(station_id, track_title)` in DDL; add in `db_init` executescript from day one
4. **Star button active during junk/ad ICY titles** — move `is_junk_title` from cover_art.py to filter_utils.py; gate star button on `not is_junk_title(current_title)`
5. **favorites table missing on existing installs** — `CREATE TABLE IF NOT EXISTS favorites` in `db_init` executescript (not ALTER TABLE); must be in Phase 1, not an afterthought
6. **AudioAddict PLS quality-tier URL construction by subdomain substitution** — never do this; re-fetch the PLS for each quality tier; DI.fm rotates subdomains without notice
7. **Radio-Browser unbounded result set** — always pass `limit=100` query param; broad queries like "jazz" return thousands of rows and freeze the UI without it

## Implications for Roadmap

All research agrees on a four-phase build in risk-ascending order. Phases A and B are fully independent and could be parallelized; C and D must be sequential (they share ImportDialog).

### Phase 1: Favorites (FAVES-01–04)
**Rationale:** Zero new network I/O; pure DB + UI. Fastest value delivery. Establishes the Stations/Favorites sidebar toggle and the `is_junk_title` refactor that later phases depend on.
**Delivers:** Star button in now-playing (gated on non-junk ICY title), favorites table with UNIQUE constraint, FavoritesView with inline delete, Stations/Favorites toggle, cover_art callback extended to `(path, genre_or_None)`.
**Addresses:** FAVES-01 (star), FAVES-02 (DB migration + UNIQUE constraint), FAVES-03 (view), FAVES-04 (delete)
**Avoids:** Pitfalls 3 (duplicate detection), 4 (junk title guard), 5 (DB migration idempotency)
**Research flag:** Standard patterns — skip `research-phase`

### Phase 2: Radio-Browser Discovery (DISC-01–03)
**Rationale:** Clean, well-documented public REST API with no auth. Introduces the importer module pattern (GTK-free dicts, GLib wiring in dialog) that AudioAddict and YouTube phases reuse. Medium complexity, low risk.
**Delivers:** DiscoveryDialog with search/browse/preview/save; RadioBrowserClient with DNS server selection; "Discover" button in toolbar.
**Addresses:** DISC-01 (browse/search), DISC-02 (preview without saving — transient `Station(id=-1, ...)`), DISC-03 (save to library)
**Avoids:** Pitfalls 1 (DNS round-robin, not hardcoded server), 2 (sync HTTP), 3 (result limits + pagination), 7 (click-count endpoint only on play/save)
**Research flag:** Standard patterns — skip `research-phase`

### Phase 3: YouTube Playlist Import (DISC-06)
**Rationale:** Directly extends existing yt-dlp integration. Lower risk than AudioAddict since yt-dlp is an already-verified dependency. Introduces ImportDialog shell that Phase 4 extends with an AudioAddict tab.
**Delivers:** ImportDialog (YouTube tab), YouTubeImporter, live-stream filter with imported/skipped count feedback.
**Addresses:** DISC-06 (playlist import), live-only filter, progress indication
**Avoids:** Pitfalls 1 (blocking main loop), 2 (non-live videos as stations)
**Research flag:** Validate `is_live` field presence in yt-dlp flat playlist mode against a real mixed playlist before writing filter logic — see Gaps

### Phase 4: AudioAddict Import (DISC-04–05)
**Rationale:** Highest external uncertainty (unofficial API). Building last ensures ImportDialog shell is in place (Phase 3) and the app is otherwise feature-complete. Empirical API verification is the first task of this phase.
**Delivers:** AudioAddict tab in ImportDialog, AudioAddictImporter with PLS-per-quality-tier fetch, quality selection (hi/med/low), API key stored masked.
**Addresses:** DISC-04 (import all four networks), DISC-05 (quality selection)
**Avoids:** Pitfalls 4 (API key security — masked in UI, never logged), 5 (PLS re-fetch per tier, no subdomain substitution)
**Research flag:** Verify API endpoint network identifiers and PLS URL auth pattern against a live DI.fm account before writing any import code

### Phase Ordering Rationale

- Favorites is independent of all discovery work; doing it first proves the sidebar toggle and DB migration patterns without network risk
- Radio-Browser before AudioAddict: public vs. unofficial API; establish the importer module pattern on a safe surface first
- YouTube before AudioAddict: reuses existing yt-dlp dependency with known behavior; creates the ImportDialog shell Phase 4 extends
- AudioAddict last: only phase requiring live-account verification; isolated scope means failure doesn't block the rest of v1.3

### Research Flags

Phases needing deeper research or empirical validation during implementation:
- **Phase 3 (YouTube):** Validate `is_live` field presence in yt-dlp `extract_flat` mode against a real mixed playlist (live + VOD) before writing the filter. If the flag is unreliable in flat mode, a secondary lightweight per-video fetch strategy is needed.
- **Phase 4 (AudioAddict):** Unofficial API — verify `api.audioaddict.com/v1/{network}/channels` endpoint and exact network identifiers (`di` vs. `difm`, `zen` vs. `radiotunes`) against a live account before writing any code. Also confirm whether PLS auth is query param (`?listen_key={key}`) or embedded in the URL path.

Phases with standard patterns (skip `research-phase`):
- **Phase 1 (Favorites):** Pure SQLite + GTK — established patterns, well-understood
- **Phase 2 (Radio-Browser):** Public REST API, stable for years, widely used by Shortwave and RadioDroid

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new dependencies; all patterns proven in existing codebase; stdlib-only additions |
| Features | HIGH | Table stakes, anti-features, and phase ordering are well-reasoned; AudioAddict feature set is MEDIUM pending live verification |
| Architecture | HIGH | Existing codebase is ground truth; module boundaries are explicit and consistent across all research files |
| Pitfalls | HIGH (GTK/SQLite), MEDIUM (AudioAddict/YT) | GTK threading and SQLite pitfalls are settled; yt-dlp `is_live` flat-playlist reliability and AudioAddict subdomain rotation need empirical validation |

**Overall confidence:** HIGH

### Gaps to Address

- **AudioAddict network identifiers:** Research shows both `di`/`zen` and `difm`/`radiotunes` as possible values. Verify against `api.audioaddict.com` before Phase 4 implementation.
- **yt-dlp `is_live` in flat playlist:** The flag may not be reliably populated in `extract_flat` mode without a full per-video metadata fetch. Test against a real mixed playlist early in Phase 3.
- **AudioAddict PLS URL auth mechanism:** Research shows API key as query param (`?listen_key={key}`) but also as direct URL component. Confirm before implementing PLS fetch logic.
- **`is_junk_title` refactor scope:** Function is currently in `cover_art.py`; must be moved to `filter_utils.py` in Phase 1 to avoid duplicating junk detection logic in favorites. This is a pure refactor but needs care to not break existing cover art behavior.

## Sources

### Primary (HIGH confidence)
- Existing codebase `musicstreamer/` — architecture, threading patterns, DB migration approach
- Radio-Browser.info REST API (training knowledge + community documentation) — endpoints, field names, DNS round-robin pattern
- yt-dlp Python API `extract_flat=True` (existing codebase usage + yt-dlp documentation) — playlist extraction, `is_live` field
- SQLite `INSERT OR IGNORE` + `UNIQUE` constraint behavior — standard SQLite semantics
- GTK4 `GLib.idle_add` + daemon thread cross-thread pattern — proven in this codebase for cover art and YT thumbnails

### Secondary (MEDIUM confidence)
- AudioAddict/DI.fm API — `github.com/DannyBen/audio_addict` and project memory note (2026-03-21) — channel list endpoint, stream URL pattern, network identifiers
- Shortwave (GNOME radio app) UX patterns — discovery-as-modal-not-primary-view recommendation
- iTunes `primaryGenreName` field — present in most API responses but not guaranteed

### Tertiary (needs live validation)
- AudioAddict PLS URL quality subdomains (`prem1`/`prem2`/`prem4`) — rotation risk noted; verify at Phase 4 start
- yt-dlp flat playlist `is_live` reliability — validate against a real mixed playlist before Phase 3 filter implementation

---
*Research completed: 2026-03-27*
*Ready for roadmap: yes*
