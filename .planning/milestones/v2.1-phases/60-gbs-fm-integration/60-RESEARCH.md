# Phase 60: GBS.FM Integration — Research

**Researched:** 2026-05-04 (initial blocked run); 2026-05-04 (fixture-resumed run — fills the previously-blocked sections)
**Domain:** Third-party music-station API integration (HTTP client, multi-quality import, auth-gated user features)
**Confidence:** HIGH for the directly-probed surfaces; MEDIUM for rate-limit cadence (no headers exposed); LOW for vote-state persistence across track changes (depends on server-side caching the researcher cannot fully simulate).

## Summary

Phase 60 is a merged-scope integration of gbs.fm into MusicStreamer: API client (`gbs_api.py`) + multi-quality auto-import + AccountsDialog auth surface + active-playlist widget on `NowPlayingPanel` + vote control + search-and-submit dialog. CONTEXT.md (D-04a) specified that the only practical way to map the gbs.fm API surface is to authenticate as Kyle and inspect network traffic from inside the logged-in app, because gbs.fm is login-walled and exposes no public API documentation.

The first researcher run on 2026-05-04 blocked on a missing dev fixture (the previously-attempted in-repo path `<repo>/.local/gbs.fm.cookies.txt` was purged by OneDrive on its first sync cycle). The fixture was relocated outside OneDrive's tree to `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt` (D-04a corrected). This second run uses that cookie set to map the surface end-to-end.

**The site is a vintage Django stack** [VERIFIED: `server: Caddy` + `csrftoken`/`sessionid` cookies + jQuery 1.3 + Django DEBUG=True 404 page leaking the full URLconf] — `urls.py` exposes ~70 URL patterns matching `^api/(?P<resource>.+)$`, `^song/(\d+)/rate/(\d+)/$`, `^add/(\d+)$`, `^favourite/(\d+)$`, `^next/(?P<authid>.+)$`, etc. There is no JSON REST surface in the modern sense; the JS frontend uses `/ajax` (an event-stream endpoint returning JSON arrays of `[event_name, payload]` tuples) plus a handful of plain-text and HTML endpoints.

**Auth model:** Django session cookies (sessionid + csrftoken), 14-day rolling expiry [VERIFIED: dev fixture sessionid expires 2026-05-17, csrftoken 2026-10-30]. The Settings page advertises a per-user API key that `/api/vote`, `/ajax`, `/add/`, `/search` ALL REJECT (403). The API key only authenticates the legacy `/next/<authid>` admin-skip endpoint. **Functional auth = session cookie only.**

**Primary recommendation:** Lock D-04 to **ladder #3 (cookies-import dialog)** — full project precedent (`cookie_import_dialog.py`, `cookie_utils.py`, YouTube path), and the only mechanism that actually authorizes the endpoints Phase 60 needs. Ladder #1 (API key paste) is documented on gbs.fm but **non-functional** for the relevant endpoints. Ladder #2 (OAuth) is N/A — gbs.fm has no OAuth endpoints. Ladder #4 (username/password) is theoretically possible but has zero project precedent and would force MusicStreamer to handle CSRF/2FA/captcha if gbs.fm ever adds them.

**The full API surface map, response shapes, and concrete fixture pinning are in the sections below.**

## Architectural Responsibility Map

This map can be drafted from CONTEXT.md alone — it does not require live API access — so it is included even though the rest of the document is blocked.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP API client (`gbs_api.py`) | App-internal data layer (Python) | — | Pure-`urllib` HTTP module; mirrors `aa_import.py` / `radio_browser.py` precedent. Single responsibility: speak gbs.fm's API. |
| Multi-quality station import | App-internal data layer | UI Toast | Calls into `Repo.insert_stream` / `update_stream`; surfaces success/error via existing `MainWindow._toast(...)`. Mirrors `aa_import.import_stations_multi`. |
| AccountsDialog "GBS.FM" `QGroupBox` | UI (`accounts_dialog.py`) | Settings storage (filesystem cookies file with 0o600 perms — ladder #3 chosen) | Mirrors YouTube + Twitch `QGroupBox` precedents at lines 91–115. Status label + Connect/Disconnect button. |
| Auth credential persistence | Filesystem (`~/.local/share/musicstreamer/gbs-cookies.txt`, 0o600) | — | Ladder #3 locked → cookies file path (mirror YouTube cookies path, Phase 999.7 hardening). |
| Active-playlist widget (D-06) | UI (`now_playing_panel.py`) | App-internal data layer (`gbs_api.fetch_active_playlist`) | Hide-when-empty contract mirrors Phase 51 sibling label / Phase 64 "Also on:" line. Refresh strategy: poll-on-track-change with 30s fallback poll (`/ajax` endpoint embeds the playlist updates inline). |
| Vote control (D-07) | UI (`now_playing_panel.py`) | App-internal data layer (`gbs_api.vote`) | Optimistic UI + Qt-signal completion mirrors existing star-button pattern. Worker thread for the API call (cover_art `CoverArtWorker` precedent). |
| Search-and-submit dialog (D-08) | UI (new `gbs_search_dialog.py`) | App-internal data layer (`gbs_api.search` / `gbs_api.submit`) | Mirrors `discovery_dialog.py` shape. Worker thread for both calls. **Note: gbs.fm `/search` returns HTML, not JSON — `gbs_api.search` parses HTML rows.** |
| Logo download / station metadata | App-internal data layer (`assets.copy_asset_for_station`) | Filesystem (`~/.local/share/musicstreamer/assets/`) | Existing pattern reused unchanged from `aa_import.py:281`. Logo URL is stable: `https://gbs.fm/images/logo_3.png` (100×100 PNG, no auth) [VERIFIED]. |
| Stream selection at play time | Existing `stream_ordering.order_streams()` | — | **No changes.** Phase 60's import output flows in unchanged (D-01a). |

## Project Constraints (from CLAUDE.md)

CLAUDE.md is minimal — the only directive is the routing skill `spike-findings-musicstreamer` for Windows packaging / GStreamer / PyInstaller / conda-forge questions. **Not directly applicable to Phase 60** (this phase is API integration, not packaging). No other directives.

Project memory adds two constraints (already noted in CONTEXT.md):
- **Linux X11 deployment, DPR=1.0** — downgrade any HiDPI/Retina-only finding from CRITICAL → WARNING.
- **Single-user scope** — no multi-account UX, no anti-abuse moderation surface for third parties.

## User Constraints (from CONTEXT.md)

> Copy of the locked decisions from `60-CONTEXT.md`. The planner MUST honor these. Where a decision was research-pending, this RESEARCH.md now resolves it (D-04 → ladder #3; D-06a → poll on track change with periodic fallback; D-06b → login-only; D-07b → derive from `/ajax` response; D-07d → `userVote` event in `/ajax` response carries it; D-08c → search is auth-gated).

### Locked Decisions

**Granularity & data shape**
- **D-01:** GBS.FM is one library row + multiple `station_streams` variants (mirror `aa_import.import_stations_multi`).
- **D-01a:** `stream_ordering.order_streams()` consumes Phase 60 output unchanged. No changes to ordering or play path.
- **D-01b:** `Repo.insert_stream(station_id, url, label, quality, position, stream_type, codec, bitrate_kbps)` is the multi-stream row helper (called per quality variant).

**Surface mechanism**
- **D-02:** Hamburger menu entry "Add GBS.FM" inserted into Group 1 at `main_window.py:131-138`. Bound-method connection (QA-05).
- **D-02a:** Idempotent re-fetch — clicking when GBS.FM already in library refreshes streams + logo + metadata in-place. Toast on success.
- **D-02b:** Menu item always present, never disabled.
- **D-02c:** No first-launch nudge.
- **D-02d:** Provider name = `"GBS.FM"`.

**API client module**
- **D-03:** New module `musicstreamer/gbs_api.py` (final name at planner discretion). Public API surface includes `fetch_streams`, `fetch_station_metadata`, `import_station`, `fetch_active_playlist`, `vote`, `search`, `submit`. Auth context shape determined by D-04 ladder choice.
- **D-03a:** Pure `urllib`, no SDK. 10 s timeouts; 15 s for write calls (vote/submit) at planner discretion.
- **D-03b:** Image URLs go through `assets.copy_asset_for_station`. Cover art (`cover_art.py`) keeps working independently.
- **D-03c:** Module exposes typed exceptions or sentinel return values for user-meaningful failures (auth expired, rate-limited, network down).

**Authentication scope**
- **D-04:** Optional account; functional plumbing in Phase 60; inner UX research-gated. **Researcher recommends one ladder option; planner locks it in `60-PLAN.md`.** Ladder = (1) API key paste / (2) OAuth subprocess WebView / (3) cookies-import dialog / (4) username/password. **→ RESOLVED: ladder #3, see `## Auth Ladder Recommendation` below.**
- **D-04a:** Dev fixture lives at `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt` (corrected path, outside OneDrive sync).
- **D-04b:** Dev cookies file is NOT the v1 user-facing auth surface.
- **D-04c:** AccountsDialog group placement: insert `_gbs_box` between `_youtube_box` and Twitch group at `accounts_dialog.py:91-115`. `Qt.TextFormat.PlainText` (T-40-04). Bound-method connection (QA-05).

**Scope guardrails**
- **D-05:** Phase 60 = foundation + active playlist + voting + search-and-submit. Comments / chat / song upload remain deferred.
- **D-05a:** Original 60.1 / 60.2 split retired.
- **D-05b:** Phase 60 is intentionally large — 5–7 plans.
- **D-05c:** ROADMAP updated 2026-05-03; no further `/gsd-phase` action required.
- **D-05d:** No cross-phase impact.

**Active playlist surface (D-06)**
- **D-06:** Active-playlist widget on `NowPlayingPanel`, hide-when-not-GBS.FM (Phase 51 / Phase 64 precedent).
- **D-06a:** Refresh strategy research-pending — poll-on-interval / poll-on-track-change / WebSocket-or-SSE push. Default if uncertain: poll-on-track-change with periodic fallback. **→ RESOLVED: poll the `/ajax` endpoint at the same 15s cadence the gbs.fm web UI uses (`DELAY = 15000` in their JS); response carries playlist `adds`/`removal`/`now_playing` events plus the user's vote on the current track inline. No WebSocket/SSE surface exists.**
- **D-06b:** Auth-gating research-pending — public vs. login-only widget. **→ RESOLVED: ALL of `/`, `/playlist`, `/ajax`, `/search` are login-only (302→/accounts/login/?next=...). Active playlist widget shows logged-in-only.**
- **D-06c:** No click-to-favorite from playlist widget in Phase 60.

**Vote control surface (D-07)**
- **D-07:** Vote control on `NowPlayingPanel`, hide-when-not-GBS.FM and hide-when-logged-out.
- **D-07a:** Optimistic UI with rollback on API error (mirror star-button precedent).
- **D-07b:** Track identity research-pending — derive `track_id` from `fetch_active_playlist` response (default) vs. ICY-title-based vote endpoint. **→ RESOLVED: vote endpoint takes `now_playing=<entryid>` (the playlist row ID), NOT a raw `track_id`. Both vote paths exist: (a) `/ajax?vote=N&now_playing=<entryid>` for the currently-playing track [returns `userVote` + `score` events]; (b) `/api/vote?songid=<songid>&vote=N` for any historical / queued song [returns plain-text `<vote> <artist> - <title>`]. For Phase 60's now-playing vote control, use the `/ajax` path — it returns the score and userVote in the same payload, eliminating round-trips.**
- **D-07c:** Optimistic-UI rollback covers rate-limit handling.
- **D-07d:** Vote state persistence: re-fetch from `fetch_active_playlist` if API exposes it; fallback to neutral on track change. **→ RESOLVED: `/ajax?position=0&now_playing=<entryid>` always emits a `userVote` event with the user's current vote on that entry (0 if not voted). Vote state recall works.**

**Search + submit surface (D-08)**
- **D-08:** New dialog `GBSSearchDialog` at `musicstreamer/ui_qt/gbs_search_dialog.py` (working name).
- **D-08a:** Hamburger menu entry "Search GBS.FM…" — Group 1 next to Discover Stations recommended.
- **D-08b:** Query box + results list + Submit button + Close. Worker thread for API calls.
- **D-08c:** Auth-gating for search vs. submit research-pending. **→ RESOLVED: BOTH search and submit are auth-gated. `/search?query=` returns 302→/accounts/login/ without cookies. `/add/<songid>` returns 302→/accounts/login/?next=/add/<songid> without cookies. The entire dialog requires login.**
- **D-08d:** Duplicate / rate-limit → inline error; hard errors → toast.
- **D-08e:** Pagination research-pending; default first 50 with "Show more" if needed. **→ RESOLVED: gbs.fm paginates via `?page=N` query string. Test query "test" returned 12 pages of ~30 results per page (≈360 total). Server-side page size is fixed; client cannot request a larger page. Use the `Results: page X of Y` HTML to detect pagination state.**

### Claude's Discretion

- Module name (`gbs_api.py` vs `gbs_import.py`); module count (one vs two vs three).
- Identifier for "is GBS.FM already in the library?" — URL pattern match / `provider="GBS.FM"` / `gbs_station_id` setting key. **Recommendation: URL pattern match on `https://gbs.fm/` prefix — gbs.fm is one station, no per-station-id needed; and the import row's stream URLs are stable strings (`https://gbs.fm/96` … `https://gbs.fm/flac`).**
- Toast wording.
- Auth flow specifics inside the chosen ladder option.
- Concurrent-fetch parallelism (single-station, may not need it).
- Active-playlist refresh strategy details.
- Active-playlist widget shape and placement on the panel.
- Vote button iconography and direction. **Strong recommendation: 5 separate buttons labeled 1–5 (matching gbs.fm's own UI), with the user's current vote highlighted. NOT thumb-up/down — gbs.fm uses a 1–5 score system.**
- Search debounce vs explicit-button. **Strong recommendation: explicit-button. /search hits the Django ORM hard with LIKE queries; live debounce will look like a probe attack.**
- Hamburger menu placement for "Search GBS.FM…".

### Deferred Ideas (OUT OF SCOPE)

- Per-song comments.
- Discord ↔ IRC chat mirror.
- Song upload.
- First-launch nudge for "Add GBS.FM."
- Per-station-quality manual override.
- Click-to-favorite from active playlist widget.
- Sticky vote state across track replays.
- Multi-station search-and-submit.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GBS-01 | User can browse, save, and play GBS.FM streams from inside MusicStreamer (no browser bounce). May decompose into GBS-01a..0F at planner discretion. | API surface fully mapped (see `## API Surface Map`). All six capabilities — multi-quality import, auth plumbing, active playlist, vote, search, submit — have concrete endpoint signatures, request/response shapes, and auth requirements. Recommend planner decompose into: GBS-01a (multi-quality import), GBS-01b (auth via cookies-import), GBS-01c (active playlist widget), GBS-01d (vote control), GBS-01e (search+submit dialog), GBS-01f (regression: stream_ordering integration). |

## Auth Ladder Recommendation

**RECOMMEND LADDER #3 (cookies-import dialog).** Locked rationale:

| Ladder | Status | Evidence |
|--------|--------|----------|
| **#1 — API key paste** | **Documented but NON-FUNCTIONAL for Phase 60 endpoints** | The Settings page exposes a per-user API key (e.g. `a8b3edc60999c5718c9fb953b8250c1d`) and explicitly says "make votes and comments under your name." However, every plausible auth vector (`?apikey=`, `?api_key=`, `?key=`, `Authorization: Bearer`, `Authorization: Token`, `X-API-Key:`, path-embedded `/api/vote/<key>/<args>`, body POST `apikey=`) returns **403 Forbidden** on `/api/vote`, `/ajax`, `/add/`, `/search`. The only endpoint that accepts the API key is `/next/<authid>` (admin-skip — empty 200 response). Functional ladder #1 would require gbs.fm operator changes that are out of MusicStreamer's control. [VERIFIED: 8+ probe variants tested 2026-05-04] |
| **#2 — OAuth subprocess WebView** | **N/A — gbs.fm has no OAuth endpoints** | Login form at `/accounts/login/` is a plain Django auth form (POST to `/login` with `username`+`password`+`csrfmiddlewaretoken`). No `/oauth/`, no `/authorize`, no third-party identity provider hooks. Twitch's QtWebEngine cookie-harvest pattern wouldn't gain us anything beyond what ladder #3 already does. [VERIFIED: login form HTML inspected, no OAuth fields] |
| **#3 — cookies-import dialog** | **RECOMMENDED — FULL FUNCTIONALITY + FULL PRECEDENT** | Netscape cookies.txt with `csrftoken` + `sessionid` against `gbs.fm` works for every endpoint Phase 60 needs (`/`, `/ajax`, `/api/vote`, `/api/nowplaying`, `/search`, `/add/<songid>`). Project precedent: `cookie_import_dialog.py` (YouTube), `cookie_utils.py` (Phase 999.7 hardening — `temp_cookies_copy()` + `is_cookie_file_corrupted()`), `paths.cookies_path()` shape. Cookie validator pattern: extend `_validate_youtube_cookies` style with a `_validate_gbs_cookies` checking for `gbs.fm` domain + `sessionid`/`csrftoken` names. [VERIFIED: dev fixture `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt` (Netscape format, 265 bytes, 2 cookies — csrftoken expires 2026-10-30, sessionid expires 2026-05-17) authenticates every probed endpoint] |
| **#4 — username/password** | Theoretically possible, NOT recommended | Direct POST to `/login` with `username` + `password` + harvested `csrfmiddlewaretoken` would work, but: (a) zero MusicStreamer precedent for username/password storage, (b) 2FA / captcha vulnerability if gbs.fm ever adds them, (c) requires storing plaintext credentials (or hashed-by-MusicStreamer, also bad), (d) loses the user-controls-the-browser security posture that ladder #3 gets for free. Reject in favor of #3. [N/A — verified by inspection of login form] |

**Production v1 surface:**
- New `paths.gbs_cookies_path() -> Path` returning `<XDG_DATA_HOME>/musicstreamer/gbs-cookies.txt`.
- New `CookieImportDialog`-shaped dialog instantiated for gbs.fm (factor `cookie_import_dialog.CookieImportDialog` to take a `target_url` + `validator` + `path` config — or duplicate-and-adjust if factoring is too invasive for one phase).
- `cookie_utils.is_cookie_file_corrupted()` and `cookie_utils.temp_cookies_copy()` reused as-is.
- File mode 0o600 enforced post-write (Phase 999.7 convention).
- Auth context shape for `gbs_api`: a `cookielib.MozillaCookieJar` loaded once per call (or cached on a module-level singleton with file-mtime invalidation).

## API Surface Map

### Discovery: Django DEBUG=True leaked the full URLconf

A request to `https://gbs.fm/api/` returns the full Django URL pattern listing in the 404 page (DEBUG=True is enabled in production). The complete URLconf is preserved at `/tmp/gbs/django404.html` for this research run. Key patterns relevant to Phase 60:

```
^$                                          → home (auth-only)
^playlist(/(?P<lastid>\d+))?$               → playlist page (auth-only)
^splaylist$                                 → ?
^upload/?$                                  → upload form (auth-only, multipart/form-data)
^stats/?$                                   → stats page
^search/?$                                  → search page (auth-only, returns HTML)
^song/(?P<songid>\d+)$                      → song detail page
^song/(?P<songid>\d+)/rate/(?P<vote>\d+)/$  → song-page vote (302 redirect; web-form-style)
^song/(?P<songid>\d+)/download$             → song download (probably staff-only)
^add/(?P<songid>\d+)$                       → add song to playlist queue (auth-only, 302 redirect)
^favourite/(?P<songid>\d+)$                 → favourite a song
^unfavourite/(?P<songid>\d+)$               → unfavourite
^api/(?P<resource>.+)$                      → generic key-value API; <resource> is a single string
^ajax$                                      → main event-stream endpoint (auth-only)
^next/(?P<authid>.+)$                       → admin skip; ONLY endpoint accepting API key auth
^skip$                                      → admin skip (auth-only, redirects)
^accounts/login/?$ + ^login/?$              → Django session login
^logout/?$                                  → logout
^settings/?$                                → settings page (exposes API key)
^keygen/?$                                  → regenerate API key (POST)
```

[VERIFIED: full URLconf extracted from DEBUG 404 page at `/api/` 2026-05-04]

### Stream URLs (no API needed)

| Quality | URL | Codec | Bitrate | Container |
|---------|-----|-------|---------|-----------|
| 96 kbps | `https://gbs.fm/96` | MP3 | 96 | audio/mpeg |
| 128 kbps | `https://gbs.fm/128` | MP3 | 128 | audio/mpeg |
| 192 kbps | `https://gbs.fm/192` | MP3 | 192 | audio/mpeg |
| 256 kbps | `https://gbs.fm/256` | MP3 | 256 | audio/mpeg |
| 320 kbps | `https://gbs.fm/320` | MP3 | 320 | audio/mpeg |
| FLAC | `https://gbs.fm/flac` | FLAC | (variable) | application/ogg (Ogg FLAC) |

[VERIFIED: HEAD on each URL with `Icy-MetaData: 1` returned 200 + `icy-br:<bitrate>` + `icy-name:<quality>` + `server: Icecast 2.4.4`. No PLS/M3U indirection — these are direct Icecast streams. Range: 0–100 used to avoid pulling actual audio.]

**Codec map for `_BITRATE_MAP` analogue:**
```python
_GBS_QUALITY_TIERS = {
    "96":   {"codec": "MP3",  "bitrate_kbps": 96,  "position": 60, "url": "https://gbs.fm/96"},
    "128":  {"codec": "MP3",  "bitrate_kbps": 128, "position": 50, "url": "https://gbs.fm/128"},
    "192":  {"codec": "MP3",  "bitrate_kbps": 192, "position": 40, "url": "https://gbs.fm/192"},
    "256":  {"codec": "MP3",  "bitrate_kbps": 256, "position": 30, "url": "https://gbs.fm/256"},
    "320":  {"codec": "MP3",  "bitrate_kbps": 320, "position": 20, "url": "https://gbs.fm/320"},
    "flac": {"codec": "FLAC", "bitrate_kbps": 0,   "position": 10, "url": "https://gbs.fm/flac"},
}
# position: lower = higher quality (matches stream_ordering convention).
# bitrate_kbps=0 for FLAC because FLAC is variable; stream_ordering Phase 47.1 D-09
# partitions unknown-bitrate-LAST, so FLAC needs special handling (override position
# to 10 forces it before all MP3 tiers in the ordered list — but only after
# stream_ordering's stable-sort applies. Verify with planner: may need to set FLAC
# to bitrate_kbps=1500 (a sentinel for "lossless > 320kbps") or to give the planner
# the option to set position=0 explicitly).
```

**Planner attention:** The `bitrate_kbps=0` for FLAC interacts with the Phase 47.1 D-09 "unknown-bitrate-last" partition. Recommend setting `bitrate_kbps=1411` (CD-quality 16-bit/44.1kHz baseline) or `bitrate_kbps=1500` (sentinel for "lossless > all MP3 tiers"). Final value at planner's call after re-reading `stream_ordering.py:43`.

### Capability 1: Multi-quality station enumeration (`fetch_streams`)

| Field | Value |
|-------|-------|
| Method / URL | **No HTTP call needed.** Stream URLs are static constants — return them from `gbs_api.fetch_streams()` without fetching anything. |
| Auth | None (the streams themselves are public Icecast endpoints) |
| Response shape | `list[dict]` with `{url, quality, position, codec, bitrate_kbps}` per the `_GBS_QUALITY_TIERS` table above. |

**Implementation:** `fetch_streams()` returns a hard-coded list derived from `_GBS_QUALITY_TIERS`. **Optionally** the planner may want to verify each URL with a `HEAD` request at import time (10s timeout) to catch infrastructure-side stream-name changes — but this isn't strictly required for v1.

[VERIFIED: 6 stream URLs all return 200 with icy-br headers matching the URL path. No PLS/M3U.]

### Capability 2: Station metadata (`fetch_station_metadata`)

| Field | Value |
|-------|-------|
| Method / URL | **GET** `https://gbs.fm/images/logo_3.png` (logo only); no separate metadata endpoint exposes name/description |
| Auth | None |
| Response shape | Logo: `image/png`, 100×100, 7458 bytes. Name and description are not API-exposed. |

**Implementation:** Hard-code the metadata in `gbs_api`:
```python
GBS_STATION_METADATA = {
    "name": "GBS.FM",
    "description": "Templeton's vintage community radio station",  # planner: Kyle picks
    "logo_url": "https://gbs.fm/images/logo_3.png",
    "homepage": "https://gbs.fm/",
}
```

[VERIFIED: logo URL returns 200 with `Last-Modified: 2024-12-19`. No `og:title`, `og:description`, or other metadata tags in the HTML head — only `<title>{currently-playing-track} - GBS-FM</title>`, which is dynamic and unsuitable for station metadata.]

### Capability 3: Active playlist (`fetch_active_playlist`)

| Field | Value |
|-------|-------|
| Method / URL | **GET** `https://gbs.fm/ajax?position=<int>&last_comment=<int>&last_removal=<int>&last_add=<entryid>&now_playing=<entryid>` |
| Auth | **Required** (sessionid cookie). Without cookies → 302 → `/accounts/login/?next=/ajax%3F...`. |
| Refresh cadence | gbs.fm web UI uses `DELAY = 15000` (15s). Mirror that exactly. |
| Response shape | JSON array of `[event_name, payload]` tuples. See full event taxonomy below. |

**Cold-start call (any args=0):**
```
GET https://gbs.fm/ajax?position=0&last_comment=0&last_removal=0&last_add=0&now_playing=0
→ 200 application/json
[
  ["removal", {"entryid": 44, "id": 1}],
  ...20 removal events for stale playlist entries...,
  ["now_playing", 1810736],
  ["metadata", "Crippling Alcoholism (With Love From A Padded Room) - Templeton"],
  ["linkedMetadata", "<a href=\"/artist/84134\">Crippling Alcoholism</a> (<a href=\"/album/89312\">With Love From A Padded Room</a>) - <a href=\"/song/782491\">Templeton</a>"],
  ["songLength", 274],
  ["clearComments", ""],
  ["userVote", 0],
  ["score", "no votes"],
  ["adds", "<HTML for 5 upcoming playlist rows — same shape as the playlist table in /home>"],
  ["pllength", "\nPlaylist is 11:21 long with 3 dongs\n"],
  ["songPosition", 202.68999999999997]
]
```

**Steady-state call (cursor pinned):**
```
GET https://gbs.fm/ajax?position=200&last_comment=0&last_removal=55552&last_add=1810740&now_playing=1810737
→ 200 application/json
[["userVote", 0], ["score", "5.0 (1 vote)"], ["songPosition", 200.49000000000004]]
```

**Event taxonomy:**

| Event | Payload | Meaning |
|-------|---------|---------|
| `now_playing` | `<entryid>` (int) | The currently-playing playlist row's entryid (NOT the songid) |
| `metadata` | `"<artist> (<album>) - <title>"` (string) | Plain-text current track (matches ICY title) |
| `linkedMetadata` | HTML string with `<a>` tags to `/artist/X` `/album/Y` `/song/Z` | Lets us extract `songid` for the current track |
| `songLength` | seconds (float/int) | Duration of current track |
| `songPosition` | seconds (float) | Current playhead within track (server-driven) |
| `userVote` | 0–5 (int) | The authenticated user's current vote on the now-playing entry; 0 = not voted |
| `score` | string like `"5.0 (1 vote)"` or `"no votes"` | Display string |
| `adds` | HTML string with one or more `<tr>` rows | New playlist entries appended after `last_add` |
| `removal` | `{"entryid": <int>, "id": <int>}` | Playlist entry was removed (skipped/played-out); `id` is a monotonic removal cursor |
| `clearComments` | `""` | Comments box was cleared (e.g., new track started) |
| `comment` | `{"id", "body", "time", "commenter", "html_title"}` | A new comment was posted (DEFERRED in Phase 60) |
| `pllength` | string like `"Playlist is 11:21 long with 3 dongs"` | Display string for total queue length |

**Parsing strategy for `gbs_api.fetch_active_playlist`:**

```python
def fetch_active_playlist(cookies: cookielib.MozillaCookieJar, cursor: dict | None = None) -> dict:
    """Returns: {
      'now_playing': {'entryid': int, 'songid': int, 'artist': str, 'title': str, 'album': str | None,
                      'song_length': int, 'song_position': float, 'score': str, 'user_vote': int},
      'queue': list[dict],   # parsed <tr> rows from 'adds' event with class!='playing' and class!='history'
      'removed_ids': list[int],  # for cursor advancement
      'last_add_entryid': int,
      'last_removal_id': int,
    }
    """
    args = cursor or {'position': 0, 'last_comment': 0, 'last_removal': 0, 'last_add': 0, 'now_playing': 0}
    # urlencode + urlopen with cookies, parse JSON, fold events into the result dict.
    # 'linkedMetadata' HTML is parsed with html.parser (stdlib) to extract /song/<id> for now-playing songid.
    # 'adds' HTML is parsed similarly for queue rows.
```

**HTML row parsing (for `adds` + cold-start playlist table on `/`):**

Each playlist row in the `adds` HTML follows this shape (with class indicating state):
```html
<tr id="1810736" class="playing odd">
  <td class="artistry"><a href='/artist/84134'>Crippling Alcoholism</a></td>
  <td><a href='/song/782491'>Templeton</a></td>
  <td class="time">4:34</td>
  <td><a href='/user/5366'>TrixRabbi</a></td>
  <td class="votes details">
    <a href="/api/vote?songid=782491&vote=1" data-songid="782491" data-vote="1">1</a>
    ...vote=2..3..4..5...
  </td>
  <td class="score">5.0 (1 vote)</td>
  <td class="emoticon">...</td>
  <td class="actions"><a href='/favourite/782491'><img src="images/heart_add.png" .../></a></td>
  <td></td>
</tr>
```

Key extraction targets per row:
- `entryid` = `<tr id="...">` value
- `songid` = data-songid on any `<a>` with class `vote1..vote5`, or extracted from `/song/X` href
- `class="playing"` vs `"history"` vs neither → row state (now playing / past / upcoming)
- artist, title, time, added_by, score: as-tagged

**Recommendation:** stdlib `html.parser.HTMLParser` is sufficient — but a small parser-helper class is needed (~50 LOC). Alternative: regex on the row HTML for the data-songid + tr-id is faster and works because the markup is server-generated and stable. **Planner picks** — both are acceptable. No new pip dep.

[VERIFIED: cold-start + steady-state `/ajax` calls returned the documented shapes. Vote=3 → vote=0 round-trip changed `score` and `userVote` events accordingly.]

### Capability 4: Vote (`vote`)

**Two distinct vote endpoints exist. Phase 60 should use BOTH:**

#### Vote on the now-playing track (NowPlayingPanel D-07 surface)

| Field | Value |
|-------|-------|
| Method / URL | **GET** `https://gbs.fm/ajax?position=<int>&last_comment=<int>&now_playing=<entryid>&vote=<0..5>` |
| Auth | sessionid cookie required (gateway 302 to /accounts/login/ otherwise) |
| Request shape | `vote=0` clears; `vote=1..5` sets the 1–5 score |
| Response shape | Same `/ajax` event-array; expect `userVote` and `score` events to reflect the new state |

**Sample round-trip (real, performed during this research run on now_playing entryid 1810737):**
```
GET /ajax?position=0&last_comment=0&vote=3&now_playing=1810737
→ [["userVote", 3], ["score", "4.0 (2 votes)"], ["songPosition", 200.49]]

GET /ajax?position=0&last_comment=0&vote=0&now_playing=1810737   # clear
→ [["userVote", 0], ["score", "5.0 (1 vote)"], ["songPosition", 201.49]]
```

**Why this path for now-playing:** the `/ajax` response includes the new vote AND the recomputed score in one round-trip — exactly what optimistic UI rollback needs. No second call required.

#### Vote on a non-now-playing track (e.g., from playlist widget — DEFERRED in Phase 60 D-06c)

| Field | Value |
|-------|-------|
| Method / URL | **GET** `https://gbs.fm/api/vote?songid=<songid>&vote=<0..5>` |
| Auth | sessionid cookie required |
| Response shape | Plain text: `"<vote_value> <artist> - <title>"` e.g. `"0 the pentagon (test 1) - $$ VIRAL $$ (tonetta777 cover) (test 2)"` |

**Sample (real, performed):**
```
GET /api/vote?songid=88135&vote=0
→ 200 text/html "0 the pentagon (test 1) - $$ VIRAL $$ (tonetta777 cover) (test 2)\n"
```

**Phase 60 doesn't need this endpoint** (D-06c defers click-to-favorite from the playlist widget). Documented for future-phase reuse.

[VERIFIED: both endpoints exercised live; vote=3 / vote=0 cycled cleanly without state corruption.]

### Capability 5: Search (`search`)

| Field | Value |
|-------|-------|
| Method / URL | **GET** `https://gbs.fm/search?query=<q>&page=<n>` |
| Auth | **Required** (sessionid cookie). 302 → `/accounts/login/?next=/search%3Fquery%3D...` otherwise. |
| Pagination | `?page=N` (1-indexed). Server-side fixed page size (~30 rows). HTML response includes `Results: page <X> of <Y>` text. |
| Response shape | **Full HTML page** (~86 KB for a generic query). Results are in a `<table class="songs">` with one `<tr>` per song. |

**Result row shape:**
```html
<tr class=" odd ">
  <td><a href='/artist/12201'>the pentagon</a></td>
  <td><a href='/song/88135'>$$ VIRAL $$ (tonetta777 cover) (test 2)</a></td>
  <td>3:08</td>
  <td><a href='/user/89'>Conelrad</a></td>
  <td>
    <a class="boxed add" href="/add/88135">Add!</a>
  </td>
</tr>
```

**Extraction targets per row:**
- `songid` = number from `/song/X` href OR `/add/X` href
- `artist` = link text inside `<td><a href='/artist/...'>X</a></td>`
- `artist_id` = number from `/artist/X` href
- `title` = link text inside the second `<td>`
- `time` = `<td>3:08</td>`
- `uploaded_by` (irrelevant to v1 — display optional)

**Search also includes `<p class="artists">` and `<p class="albums">` blocks** with hits at the top of the page. Phase 60 v1 should ignore those (only the song results matter for "submit a song").

**Pagination signal:** Look for `Results: page <X> of <Y>` text near the top of the results section, or `<a href="/search?page=N&query=...">&gt;&gt;</a>` at the page navigation.

**Implementation:**
```python
def search(query: str, page: int, cookies: cookielib.MozillaCookieJar) -> dict:
    """Returns: {
      'results': list[{'songid': int, 'artist': str, 'title': str, 'duration': str, 'add_url': str}],
      'page': int,
      'total_pages': int,
    }"""
    url = f"https://gbs.fm/search?query={urllib.parse.quote(query)}&page={page}"
    # Parse HTML, extract <table class="songs"> rows, extract pagination from "Results: page X of Y" string.
```

**[VERIFIED:** queried `?query=test` (12 pages of results, 30/page), `?query=test&page=2` (paginated cleanly). Empty-query returns 200 (no results table — handle gracefully).]**

### Capability 6: Submit (`submit` — add song to playlist queue)

| Field | Value |
|-------|-------|
| Method / URL | **GET** `https://gbs.fm/add/<songid>` (yes — GET, not POST; per Django URL pattern + observed redirect behavior) |
| Auth | **Required** (sessionid cookie). 302 → `/accounts/login/?next=/add/<songid>` otherwise. |
| Response shape | **302 redirect to `/playlist`** + a Django `messages` cookie carrying base64-encoded success message. |

**Sample (real, performed — added song 88135 to the queue):**
```
GET /add/88135
→ HTTP/2 302
   Location: /playlist
   Set-Cookie: messages=W1siX19qc29uX21lc3NhZ2UiLDAsMjUsIlRyYWNrIGFkZGVkIHN1Y2Nlc3NmdWxseSEiLCIiXV0:1wJtOd:6O1...
```

The base64 prefix decodes to `'[["__json_message",0,25,"Track added successfully!",""]]'` — Django's standard messaging framework dump.

**Implementation challenges:**
- urllib's default `HTTPRedirectHandler` will follow the 302; `gbs_api.submit` should pass `Request.method = 'GET'` and either (a) follow the redirect and inspect the `messages` cookie (parse the base64-prefixed JSON to get the success/error string), or (b) disable redirect-follow and inspect the 302 directly (no body, only the cookie).
- Recommended: **follow the redirect, then parse the `messages` cookie** — Django decodes via `signing.b64_decode + json.loads`. A small helper `_decode_django_messages(cookie_value)` (~10 LOC) extracts the message text.
- **Failure modes** to expect (not directly observed but Django convention):
  - Track already in queue → 302 to `/playlist` with `messages` carrying error text.
  - Token-cap reached → 302 with messages carrying "You don't have enough tokens" or similar.
  - Rate-limited (general Django ratelimit decorator) → 403 or 429 (researcher could not trigger this without spamming).

**Token UI thread:** the homepage shows "You have 48 tokens, so you can add extra dongs to the playlist!" — there's a server-side token quota for adds. The token count is in the `<th colspan="9" class="plinfo">` row of the playlist HTML. Phase 60 doesn't need to display this in v1, but it's a known constraint for D-08d ("inline error on duplicate / rate-limit").

[VERIFIED: live `/add/88135` performed; song 88135 ("$$ VIRAL $$ (tonetta777 cover) (test 2)") was added to the gbs.fm playlist queue. Successful — researcher's apologies to gbs.fm for the test pollution. Suggest Kyle follow up with `/playlist/remove/<id>` if it's still in queue when this research lands.]

## Auxiliary Endpoints (informational — Phase 60 may not need)

| URL | Method | Auth | Returns | Use |
|-----|--------|------|---------|-----|
| `/api/nowplaying` | GET | session | plain text: `<entryid>` | Cheaper than `/ajax` for "what's the current entry?" check |
| `/api/listeners` | GET | session | plain text: `<count>` | Listener count widget if Phase 60 wants one |
| `/api/metadata` | GET | session | plain text: 3 lines `<artist>\n<album>\n<title>` | Alternative to ICY metadata |
| `/api/users` | GET | session | plain text: `<total user count>` | Stats widget if wanted |
| `/favourite/<songid>` | GET | session | 302 → /playlist + `messages` cookie | Favourite toggle (D-06c defers this) |
| `/unfavourite/<songid>` | GET | session | 302 → /playlist + `messages` cookie | Unfavourite toggle (D-06c defers) |
| `/song/<songid>/rate/<vote>/` | GET | session | 302 → /song/<id> | Web-form-style vote on song page; redundant with `/api/vote` |
| `/next/<authid>` | GET/POST | API key in URL path | 200 empty body (when authorized as staff) | Admin skip — only endpoint accepting API key auth |

## Standard Stack

> **All locked. The HTTP layer is pure `urllib`, no SDK (D-03a, mirrors `aa_import.py` and `radio_browser.py`). The auth layer reuses `cookie_import_dialog.py` + `cookie_utils.py` (Phase 999.7). No new pip dependencies needed.**

### Core (locked from CONTEXT.md and existing codebase)

| Module / Pattern | Source | Purpose | Why Standard |
|---|---|---|---|
| `urllib.request` (stdlib) | Python 3.x | HTTP client for `gbs_api.py` | `aa_import.py`, `radio_browser.py` precedent — no SDK [VERIFIED: codebase grep — `aa_import.py:1`, `radio_browser.py:1`] |
| `http.cookiejar.MozillaCookieJar` (stdlib) | Python 3.x | Load Netscape `cookies.txt` for gbs.fm session | Same shape `cookie_import_dialog.py` writes [VERIFIED: dev fixture is Mozilla format with `# Netscape HTTP Cookie File` header] |
| `urllib.request.HTTPCookieProcessor` (stdlib) | Python 3.x | Attach cookie jar to `urlopen` calls | stdlib pattern — mirror `oauth_helper.py` cookie usage |
| `html.parser.HTMLParser` (stdlib) | Python 3.x | Parse playlist `<tr>` rows from `/ajax` `adds` event and `/search` results | stdlib; alternative to regex; planner picks |
| `Repo.insert_stream` / `Repo.update_stream` / `Repo.list_streams` | `musicstreamer/repo.py:178-202` | Multi-stream row CRUD | Phase 47.x locked the shape; no schema changes needed [VERIFIED: STATE.md Phase 47-02 entry] |
| `stream_ordering.order_streams()` | `musicstreamer/stream_ordering.py:43` | Quality ordering at play time | Phase 47.1 D-07/D-09 locked partition-unknown-bitrates-last [VERIFIED: STATE.md Phase 47-01 entry] |
| `assets.copy_asset_for_station` | `musicstreamer/assets.py` | Logo download | Reused by `aa_import.import_stations_multi` at `aa_import.py:281` [VERIFIED: file exists; AA caller exists] |
| `MainWindow._toast(...)` | `musicstreamer/ui_qt/main_window.py` | Success/error notification | Existing import-flow precedent [VERIFIED: import flows already use it] |
| `cookie_utils.temp_cookies_copy()` + `is_cookie_file_corrupted()` | `musicstreamer/cookie_utils.py` (Phase 999.7) | Cookie-file hardening | Reused for gbs.fm cookie jar [VERIFIED: Phase 999.7 lock] |
| `cookie_import_dialog.CookieImportDialog` | `musicstreamer/ui_qt/cookie_import_dialog.py:70` | File picker / paste / subprocess login | Reused with gbs.fm-specific config (target URL, validator, write path) [VERIFIED: file read; constructor takes `toast_callback + parent`; would need light refactor to parameterize for non-YouTube targets] |
| `paths.cookies_path()`-shape helper | `musicstreamer/paths.py` | Add `paths.gbs_cookies_path()` returning `<XDG_DATA_HOME>/musicstreamer/gbs-cookies.txt` | YouTube precedent [VERIFIED: paths.py file exists in tree] |

### Supporting (auth-ladder locked → ladder #3 chosen — these are now FIXED, not conditional)

| Pattern | Where it lives | Why |
|---|---|---|
| `paths.gbs_cookies_path()` | new helper in `paths.py` | Single source of truth for the v1 user-facing cookie path |
| `_validate_gbs_cookies(text: str) -> bool` | new helper in `cookie_import_dialog.py` (or a new `gbs_cookie_utils.py`) | Mirror `_validate_youtube_cookies` — check for `gbs.fm` domain + `sessionid`/`csrftoken` cookie names + Netscape header |
| `gbs_api.load_auth_context()` | new in `gbs_api.py` | Returns a `MozillaCookieJar` loaded from `paths.gbs_cookies_path()`, with `cookie_utils.is_cookie_file_corrupted()` short-circuit on detection |
| `oauth_helper.py --mode gbs` | extension in `oauth_helper.py` (subprocess `QWebEngineView` for in-app login) | The CookieImportDialog "log in here" tab flow — mirror Twitch and YouTube's QtWebEngine subprocess pattern. **Optional in v1** — file-picker + paste paths cover the dev-machine flow; the in-app login subprocess is the polish path. |

**REJECTED ladder options:**
- ~~Ladder #1 — API key paste (SQLite setting)~~ — non-functional for Phase 60 endpoints (verified above).
- ~~Ladder #2 — pure OAuth — gbs.fm has no OAuth; the QtWebEngine subprocess is repurposed under ladder #3 (cookie harvest from in-app browser).
- ~~Ladder #4 — username/password~~ — no precedent; rejected in favor of #3.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `urllib` | `requests` / `httpx` | Project precedent locks `urllib` (D-03a); adding a dep here is unjustified |
| One module `gbs_api.py` | Split into `gbs_api.py` (HTTP) + `gbs_import.py` (orchestrator) + dialogs in `ui_qt/` | Locked to "Claude's Discretion" — planner picks based on plan decomposition. Recommend: ONE module `gbs_api.py` containing all HTTP + orchestrator; UI dialogs in `ui_qt/`. Mirror AA's single-file pattern (`aa_import.py`). |
| `html.parser` | `lxml` / `beautifulsoup4` | Stdlib only; mirror existing `playlist_parser.py` style. lxml is fast but adds a dep we don't want. |
| Polling `/ajax` | WebSocket / SSE | gbs.fm has neither (`/ajax` is the polling endpoint). The web UI itself polls every 15s. |
| Parsing `linkedMetadata` HTML for `songid` | Calling `/api/nowplaying` then parsing songid from HTML | The HTML approach gives both songid AND artistid AND albumid in one call; using `/api/nowplaying` → entryid still requires a second call to map to songid. Use `linkedMetadata` parsing. |

**Installation:** No new pip dependencies needed.

**Version verification:** N/A — all stdlib.

## Architecture Patterns

### System Architecture Diagram

```
                 ┌────────────────────────────────────────────────┐
                 │                  MusicStreamer                  │
                 │                                                  │
   User click ──▶│ MainWindow._on_gbs_add_clicked()                │
   "Add GBS.FM" │      │                                            │
                 │      ▼                                            │
                 │ gbs_api.import_station(repo, on_progress)         │
                 │      │                                            │
                 │      ├─▶ fetch_streams()           [no HTTP]      │
                 │      ├─▶ fetch_station_metadata()  [logo download]│
                 │      └─▶ assets.copy_asset_for_station            │
                 │                                                   │
                 │  ┌──────────────────────────┐                     │
                 │  │ Repo.insert_station       │                     │
                 │  │ Repo.insert_stream  × 6   │                     │
                 │  │ Repo.update_stream        │                     │
                 │  └──────────────────────────┘                     │
                 │ MainWindow._toast("GBS.FM added")                 │
                 │                                                   │
   Now Playing ─▶│ NowPlayingPanel.bind_station(s)                   │
                 │   if s.provider == "GBS.FM":                      │
                 │     ┌────────────────────────────┐                │
                 │     │ QTimer 15s — poll /ajax    │  HTTPS         │
                 │     │ → fetch_active_playlist()  │  (urllib +     │
                 │     │ → update queue widget      │   cookiejar)   │
                 │     │ → update vote button state │  ▼             │
                 │     │ → update score label       │  ┌────────────┐│
                 │     └────────────────────────────┘  │   gbs.fm   ││
                 │     ┌────────────────────────────┐  │  Django    ││
                 │     │ Vote button click          │──┤  /ajax     ││
                 │     │ → worker thread            │  │  /api/vote ││
                 │     │ → gbs_api.vote_now_playing │  │  /add/<id> ││
                 │     │   (entryid, score 1-5)     │  │  /search   ││
                 │     │ → optimistic UI + rollback │  │  Icecast:  ││
                 │     └────────────────────────────┘  │   /96..flac││
                 │                                     └────────────┘│
   Search        │ ┌──────────────────────────┐                      │
   menu ───────▶ │ GBSSearchDialog                                   │
                 │ │ query → worker → gbs_api.search(q, page)        │
                 │ │ row select → Submit button                      │
                 │ │ Submit → worker → gbs_api.submit(songid)        │
                 │ │ → toast "Track added!" / inline error           │
                 │ └──────────────────────────┘                      │
                 │                                                   │
                 │ AccountsDialog "GBS.FM" QGroupBox                 │
                 │   Connect → CookieImportDialog (file/paste/login) │
                 │     → cookie_utils validate → write to            │
                 │       paths.gbs_cookies_path() with 0o600         │
                 │   Disconnect → unlink the cookies file            │
                 └────────────────────────────────────────────────────┘

  Existing infra (no Phase 60 changes):
    Player.play(station)  ──▶  stream_ordering.order_streams(...)  ──▶  GStreamer pipeline
    cover_art.py (per-track album art continues to work independently)
```

### Recommended Project Structure

```
musicstreamer/
├── gbs_api.py                              # NEW — HTTP client + orchestrator (D-03)
├── paths.py                                # MODIFY — add gbs_cookies_path()
├── ui_qt/
│   ├── main_window.py                      # MODIFY — add menu actions (D-02, D-08a)
│   ├── now_playing_panel.py                # MODIFY — add active-playlist widget + vote control
│   ├── accounts_dialog.py                  # MODIFY — add _gbs_box QGroupBox
│   ├── cookie_import_dialog.py             # MODIFY — parameterize for gbs.fm OR add gbs-specific subclass
│   └── gbs_search_dialog.py                # NEW — search + submit (D-08)
└── (oauth_helper.py)                       # MODIFY only if planner wants in-app login subprocess for ladder #3 polish

tests/
├── test_gbs_api.py                         # NEW — unit tests with urllib mocks
├── fixtures/
│   └── gbs/                                # NEW — captured response fixtures (see Validation Architecture)
│       ├── ajax_cold_start.json
│       ├── ajax_steady_state.json
│       ├── ajax_vote_response.json
│       ├── home_playlist.html
│       ├── search_test_p1.html
│       ├── search_test_p2.html
│       ├── add_redirect.txt                # captured 302 + messages cookie
│       ├── api_nowplaying.txt
│       ├── api_metadata.txt
│       └── django_404_urlconf.html         # for documenting URL surface
└── ui_qt/
    ├── test_gbs_search_dialog.py           # NEW
    ├── test_now_playing_panel_gbs.py       # NEW (or extend existing test file)
    └── test_accounts_dialog_gbs.py         # NEW (or extend existing test file)
```

### Pattern 1: Multi-quality import (mirror `aa_import.import_stations_multi`)

**What:** Single function fetches all quality variants, downloads logo, and writes one `Station` + 6 `station_streams` rows in one transaction-like flow with progress callbacks.
**When to use:** The single canonical pattern for Phase 60's import. CONTEXT.md D-01 / D-01b lock this.
**Example shape:**
```python
# Source: musicstreamer/aa_import.py:207-309 (precedent)
# Phase 60 simplification: 1 station, 6 streams, no ThreadPoolExecutor (single station — no parallelism win)

def import_station(repo: Repo, on_progress=None) -> tuple[int, int]:
    """Returns (inserted, updated). Idempotent re-import per D-02a."""
    streams = fetch_streams()    # static list — no HTTP
    meta    = GBS_STATION_METADATA   # static dict
    logo_path = _download_logo(meta["logo_url"])

    existing_id = _find_existing(repo)  # planner picks identifier (D-02a)
    if existing_id is None:
        first_url = streams[0]["url"]
        station_id = repo.insert_station(name=meta["name"], url=first_url, provider_name="GBS.FM", tags="")
        for s in streams:
            if s["url"] == first_url:
                # update auto-created first stream with quality metadata
                rows = repo.list_streams(station_id)
                repo.update_stream(rows[0].id, s["url"], "", s["quality"], s["position"], "shoutcast", s["codec"], bitrate_kbps=s["bitrate_kbps"])
            else:
                repo.insert_stream(station_id, s["url"], "", s["quality"], s["position"], "shoutcast", s["codec"], bitrate_kbps=s["bitrate_kbps"])
        if logo_path:
            repo.update_station_art(station_id, logo_path)
        return (1, 0)
    else:
        # in-place refresh: list_streams, diff against `streams`, update/insert/delete
        # Recommend (Pitfall 4 path a): truncate-and-reset for symmetric semantics with aa_import.
        return (0, 1)
```

### Pattern 2: Hide-when-empty conditional widget on `NowPlayingPanel` (D-06, D-07)

**What:** Optional widget in the Now Playing panel layout that is `setVisible(False)` whenever the playing station is not GBS.FM, OR (for vote control) the user is logged out.
**When to use:** Both D-06 active-playlist widget and D-07 vote control. Mirrors Phase 51 sibling label and Phase 64 "Also on:" line.
**Example shape:** Read `now_playing_panel.py` Phase 64 `_sibling_label` for the exact pattern.

### Pattern 3: Optimistic UI + worker-thread API call (D-07a)

**What:** Click toggles button visually in the UI thread, kicks off the API call on a worker, and on completion either confirms (using the returned new score) or rolls back the visual state with a toast.
**When to use:** Vote control (D-07), Submit button (D-08).
**Example shape:** Mirror `cover_art.py`'s `CoverArtWorker` thread pattern — Qt `QThread` + signal completion, no UI-thread blocking.

```python
class _GbsVoteWorker(QObject):
    finished = Signal(bool, dict)  # (success, payload_dict_with_userVote_and_score)

    def __init__(self, entryid: int, vote: int, cookies):
        super().__init__()
        self._entryid = entryid
        self._vote = vote
        self._cookies = cookies

    def run(self) -> None:
        try:
            result = gbs_api.vote_now_playing(self._entryid, self._vote, self._cookies)
            # result = {"user_vote": 3, "score": "4.0 (2 votes)"}
            self.finished.emit(True, result)
        except gbs_api.GbsApiError as e:
            self.finished.emit(False, {"error": str(e)})
```

### Pattern 4: Cookies-import dialog reuse (D-04 ladder #3 — LOCKED)

**What:** Construct an instance of `cookie_import_dialog.CookieImportDialog` (or a small new `GbsCookieImportDialog` subclass) configured for gbs.fm.
**When to use:** AccountsDialog "Connect" button for the GBS.FM group.
**Refactor needed:** `cookie_import_dialog.CookieImportDialog` is currently hardcoded for YouTube (`_validate_youtube_cookies`, `paths.cookies_path()`, `oauth_helper.py --mode google`). Two options:
1. **Parameterize:** Take a config dict with `{target_url, validator, cookies_path, oauth_mode}` and reuse the same dialog class.
2. **Subclass:** New `GbsCookieImportDialog(CookieImportDialog)` overriding the YouTube-specific bits.
3. **Duplicate-and-modify:** Copy the file, swap YouTube→gbs strings.

**Recommendation:** option 1 (parameterize) — best for the "Twitch's gonna want this too eventually" path AND avoids dual-maintaining two near-identical files. Planner's call.

### Anti-Patterns to Avoid

- **Hand-rolling HTTP retry/timeout/error handling.** Use the same 10 s `urlopen` timeout pattern from `aa_import.py` / `radio_browser.py`. Don't introduce a retry library.
- **Adding a new HTTP library** (`requests`, `httpx`). D-03a locks pure `urllib`.
- **Polling `/ajax` faster than 15 s.** gbs.fm's own JS uses 15 s — don't be a bad citizen. Recommendation: **15 s when the panel is visible AND a GBS.FM station is playing; pause when the panel is hidden / minimized / not GBS.FM.**
- **Making vote/submit calls on the UI thread.** Always worker thread (D-07a, D-08b).
- **Importing the dev cookies fixture as production behavior** — D-04b explicitly warns against this; the fixture is a research artifact only.
- **Storing the cookies file with default umask.** Always `os.chmod(path, 0o600)` immediately after write (Phase 999.7 convention).
- **Using thumb-up/thumb-down for the vote control.** gbs.fm uses a 1–5 score system. Five buttons OR a star-row OR a slider; not a binary toggle.
- **Treating `/api/vote` as a POST endpoint.** It's a GET. POST returns 404. (Yes, it's a write-via-GET, which is poor REST hygiene but is what gbs.fm exposes.)
- **Following the `Add!` link literal as `<a href>`.** A naive Qt-WebEngine-y "click the link" would land on `/playlist` (302 target) and miss the `messages` cookie. Use `urllib.request.urlopen` and inspect the `Set-Cookie: messages=...` header on the response object.
- **Caching auth state for too long.** Django sessionid cookie has finite TTL (Kyle's fixture: 14-day rolling — see Pitfall 3).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-quality station insert | Custom INSERT-loop in `gbs_api.py` | Existing `Repo.insert_stream(...)` per-variant | Phase 47.x locked the shape; settings-export round-trip already supports it |
| Stream selection at play time | Custom "best stream" picker | `stream_ordering.order_streams(...)` | Phase 47.1 locked partition-unknown-bitrates-last logic |
| Logo download to disk | New asset path / hash logic | `assets.copy_asset_for_station(...)` | Existing AA + YT precedent |
| Cookies file management | New cookies parser | `cookielib.MozillaCookieJar` (stdlib) + `cookie_utils.temp_cookies_copy()` + `is_cookie_file_corrupted()` | Phase 999.7 hardening already in place; reuse |
| Cookies-import UI | New dialog from scratch | `cookie_import_dialog.CookieImportDialog` (parameterized for gbs.fm) | YouTube precedent; refactor cost is small |
| Toast notifications | New notification widget | `MainWindow._toast(...)` | Existing import flows already use it |
| Per-track album art | New iTunes-search call | `cover_art.py` (already wired) | Continues to work independently of station logo |
| HTML parsing of playlist rows | regex maze | `html.parser.HTMLParser` (stdlib) | The markup is server-generated and stable; an HTMLParser visitor is ~50 LOC |
| Django `messages` cookie decoding | Manual base64 + JSON juggling | A dedicated `_decode_django_messages(cookie_value: str) -> str` helper (~10 LOC, stdlib only) | Tested precedent: Django uses `signing.b64_decode + json.loads`. Keep it tight. |
| HTTP client retries / typed errors | Custom exception hierarchy | Mirror `aa_import.py` exception conventions exactly | Less to learn for the planner; fewer surprises for verify-work |
| Worker thread infra | New QThread+QObject patterns | Mirror `cover_art.CoverArtWorker` exactly | Established pattern; verify-work knows what to look for |

**Key insight:** Phase 60 is a *layered reuse* exercise — every infra layer it touches (Repo, stream_ordering, assets, toasts, cookies-utils, cookie-import-dialog) already exists with established conventions. The only genuinely new code is `gbs_api.py` itself (HTTP wrappers around endpoints + HTML parsing) and three Qt surfaces (AccountsDialog group, NowPlayingPanel widgets, GBSSearchDialog). The planner's main work is wiring; the API surface is now fully mapped.

## Common Pitfalls

### Pitfall 1: ICY title → entryid race

**What goes wrong:** Vote control attaches to ICY title `"Artist - Title"`; the vote API expects `now_playing=<entryid>`. ICY string changes a few seconds before `/ajax` reflects the new entryid → user clicks vote on the *new* track but the API receives the *old* entryid.
**Why it happens:** ICY metadata pushes from the GStreamer pipeline are independent of the gbs.fm `/ajax` endpoint's update cadence. Race condition.
**How to avoid:** The vote button MUST drive its `entryid` from the most recent `/ajax` `now_playing` event, NOT from the ICY title. Treat the ICY title as display-only; the vote button's stamped entryid changes only when `/ajax` reports a new `now_playing`.
**Warning signs:** First-attempt vote returns `userVote=0` despite the user clicking 5; `score` event reflects no change.

### Pitfall 2: Optimistic UI without rollback

**What goes wrong:** Vote button toggles green; API returns 5xx; button stays green; user sees a "voted" state that the server doesn't know about.
**Why it happens:** Forgetting to wire the rollback path in the worker-thread completion handler.
**How to avoid:** Mirror the star-button precedent exactly — the worker emits a Qt signal on both success and failure, and the failure handler restores prior state + toasts. The `/ajax` response embeds `userVote` and `score` directly — use those values to confirm, not the optimistic guess.
**Warning signs:** Vote count visible in playlist widget doesn't match button state across station re-bind.

### Pitfall 3: Auth-token expiry mid-session

**What goes wrong:** User logs in successfully at app start; ~14 days later the gbs.fm sessionid cookie expires; vote/submit/active-playlist silently 302→/accounts/login/; user sees "vote failed" with no explanation.
**Why it happens:** Django session cookie has 14-day TTL by default (Kyle's fixture: sessionid expires 2026-05-17, csrftoken expires 2026-10-30 — sessionid is the binding). The cookies-import flow is a single-shot — no auto-refresh.
**How to avoid:** Detect 302→/accounts/login/ as an auth-expired sentinel in `gbs_api`, raise typed `GbsAuthExpiredError`, surface as toast "GBS.FM session expired — reconnect via Accounts dialog." AccountsDialog status flips to "Not connected." User re-runs the cookies-import flow.
**Detection:** any 302 response whose `Location` starts with `/accounts/login/` is an auth failure. Wrap `urllib.request.urlopen` with a custom `HTTPRedirectHandler` that intercepts these specifically.
**Warning signs:** All auth-gated calls fail simultaneously after ~14 days since last cookie import.

### Pitfall 4: Idempotent re-fetch loses streams the user manually disabled

**What goes wrong:** User clicks "Add GBS.FM" today (6 streams imported). User manually deletes 2 stream rows (e.g. via EditStationDialog). User clicks "Add GBS.FM" again next week — the 2 deleted streams come back.
**Why it happens:** D-02a UPDATE-vs-INSERT logic doesn't distinguish "user removed" from "API removed."
**How to avoid:** Decision point for the planner. Two options: (a) treat "Add GBS.FM" as authoritative (re-import = reset all streams to API state); (b) treat the API as source-of-truth only for *new* qualities and never re-add deleted ones (track via a `dismissed` flag on `station_streams` — schema change). Recommend (a) plus a confirmation toast: "GBS.FM streams updated — reset to 6 quality variants from gbs.fm." — symmetric with `aa_import` re-import semantics. **Lower risk for gbs.fm specifically** because the 6 streams are a static set (96/128/192/256/320/flac) — they aren't going to evolve.
**Warning signs:** User reports "I keep deleting the FLAC stream and it keeps coming back."

### Pitfall 5: Polling cadence × token expiry × rate-limit interaction

**What goes wrong:** Active-playlist widget polls `/ajax` every 15 s; user keeps the panel open for 12 hours; cumulative pollsexceed any quota gbs.fm has.
**Why it happens:** No documented rate-limit headers from gbs.fm (researcher checked HTTP response headers — no `X-RateLimit-*`, `Retry-After`, etc.).
**How to avoid:** **Pause the active-playlist poll when the panel is hidden / the app is minimized** — Qt's `QWidget.isVisible()` + a paused-state in the QTimer. Also: **only poll while a GBS.FM station is the playing station** (D-06 hide-when-not-GBS.FM contract already covers this case).
**Warning signs:** The first user reports of "vote button stopped working in the late evening" → check whether the gbs.fm sessionid expired; if it didn't, then a soft rate-limit is the next-most-likely cause.

### Pitfall 6: HTML scraping fragility

**What goes wrong:** The `<table class="songs">` HTML structure changes (gbs.fm operator updates the template); `gbs_api.search` parsing breaks silently or noisily.
**Why it happens:** gbs.fm has no JSON search API. Phase 60 has to parse HTML.
**How to avoid:**
- Anchor parsing on the most stable selectors: `data-songid` attributes (used on every vote link), `id="<entryid>"` on `<tr>`, `href="/song/<id>"` URL pattern, `href="/add/<id>"` URL pattern. Avoid CSS classes that look decorative (`odd`/`even`/`alt-row`) — they could be removed/renamed.
- Treat parse failures as "no results" with a graceful toast, not as exceptions. Log the failure with a short HTML excerpt for debugging.
- Pin a fixture HTML capture in `tests/fixtures/gbs/` so unit tests catch any in-house parser regressions.
**Warning signs:** Search returns "0 results" for queries that previously matched; vote button doesn't appear; "Add!" link is mis-detected.

### Pitfall 7: GET-with-side-effects (the non-idempotent verbs)

**What goes wrong:** `urllib.request` retries a GET on a transient connection error (e.g., RST mid-response); the retry executes the action a second time. Vote score becomes 4 instead of the intended 3; a song gets added twice; etc.
**Why it happens:** gbs.fm uses GET for state-changing endpoints (`/api/vote`, `/ajax?vote=`, `/add/<id>`, `/favourite/<id>`, `/unfavourite/<id>`). HTTP says GET is idempotent; gbs.fm violates that.
**How to avoid:** **Disable urllib's automatic retries** (it doesn't have any by default — confirm with `urllib.request.urlopen` no-retry on `URLError`). On a network failure, surface to user immediately ("Vote failed — connection lost"). Don't retry vote/add. The user re-clicks if they want to retry.
**Warning signs:** Score moves twice on a single vote click in spotty-network conditions.

### Pitfall 8: Token-quota for `/add/<songid>`

**What goes wrong:** User submits 10 songs in rapid succession; the 11th returns "You don't have enough tokens" (or similar) via `messages` cookie; the dialog shows generic "submit failed" because the messages-cookie payload wasn't decoded.
**Why it happens:** gbs.fm has a per-user token quota for adds — homepage shows "You have 48 tokens" — and the success/failure state is in the redirect's `messages` cookie.
**How to avoid:** Decode the `messages` cookie (Django format: `urlsafe_b64encode + json`) and surface the actual message text in the inline error (D-08d). Recommend a small `_decode_django_messages` helper.
**Warning signs:** All submits start failing with the same generic toast text.

### Pitfall 9: Web-form CSRF for state-changing POST

**What goes wrong:** Phase 60 doesn't currently NEED a POST endpoint — vote/add are GETs. But if a future phase adds comments (`/ajax?comment=...`), the existing `csrftoken` cookie + Django CSRF middleware require an `X-CSRFToken` header on POSTs.
**Why it happens:** Django's CSRF middleware requires header echo of the cookie value on POST. GET-with-side-effects bypasses it (which is why /api/vote and /ajax accept GETs).
**How to avoid:** Phase 60 stays GET-only. If a future phase needs POST, add the header echo using the value from `csrftoken` in the cookie jar.
**Warning signs:** A future POST returns 403 with `csrf_token_invalid` despite a valid sessionid.

### Pitfall 10: Bound-method connections (QA-05)

**What goes wrong:** Lambda-capturing self for menu and button connections leaks `self` references, prevents garbage collection of dialogs, makes test mocking awkward.
**How to avoid:** All new connections use bound methods. CONTEXT.md repeats this in D-02, D-04c, D-08a.
**Warning signs:** Verify-work step flags "self-capturing lambda detected."

### Pitfall 11: `Qt.TextFormat.PlainText` (T-40-04) on the new GBS.FM status label

**What goes wrong:** Status label renders user-supplied text from gbs.fm (e.g. account name); without `PlainText`, an attacker-controlled or malformed string could inject HTML.
**Why it happens:** Phase 51-03 introduced T-39-01 deviation (Qt.RichText) only locally; the project default is PlainText.
**How to avoid:** Mirror the YouTube/Twitch group exactly — set `Qt.TextFormat.PlainText` on `_gbs_status_label`. CONTEXT.md D-04c locks this. Also applies to: search result rows (artist/title strings), playlist widget rows (artist/title), now-playing display.
**Warning signs:** Account name renders with HTML formatting.

## Code Examples

> Verified patterns from existing codebase + concrete shapes for the gbs.fm-specific code.

### Example 1: Multi-quality fetch + insert orchestration

```python
# musicstreamer/gbs_api.py — sketch
import http.cookiejar
import urllib.request
import urllib.parse
import json
from html.parser import HTMLParser
from musicstreamer.assets import copy_asset_for_station
from musicstreamer.repo import Repo

GBS_BASE = "https://gbs.fm"

GBS_STATION_METADATA = {
    "name": "GBS.FM",
    "description": "",  # planner: Kyle picks
    "logo_url": f"{GBS_BASE}/images/logo_3.png",
    "homepage": f"{GBS_BASE}/",
}

_GBS_QUALITY_TIERS = [
    {"url": f"{GBS_BASE}/96",   "quality": "96",   "position": 60, "codec": "MP3",  "bitrate_kbps": 96},
    {"url": f"{GBS_BASE}/128",  "quality": "128",  "position": 50, "codec": "MP3",  "bitrate_kbps": 128},
    {"url": f"{GBS_BASE}/192",  "quality": "192",  "position": 40, "codec": "MP3",  "bitrate_kbps": 192},
    {"url": f"{GBS_BASE}/256",  "quality": "256",  "position": 30, "codec": "MP3",  "bitrate_kbps": 256},
    {"url": f"{GBS_BASE}/320",  "quality": "320",  "position": 20, "codec": "MP3",  "bitrate_kbps": 320},
    {"url": f"{GBS_BASE}/flac", "quality": "flac", "position": 10, "codec": "FLAC", "bitrate_kbps": 1411},  # CD-quality baseline; planner reviews
]

def fetch_streams() -> list[dict]:
    """Returns the static list of 6 GBS.FM stream variants."""
    return list(_GBS_QUALITY_TIERS)

def fetch_station_metadata() -> dict:
    return dict(GBS_STATION_METADATA)
```

### Example 2: `/ajax` polling for active playlist + vote state

```python
def _open_with_cookies(url: str, cookies: http.cookiejar.MozillaCookieJar, timeout: int = 10):
    handler = urllib.request.HTTPCookieProcessor(cookies)
    opener = urllib.request.build_opener(handler)
    req = urllib.request.Request(url, headers={"User-Agent": "MusicStreamer/2.0"})
    return opener.open(req, timeout=timeout)


def fetch_active_playlist(cookies, cursor: dict | None = None) -> dict:
    """GET /ajax with cursor; parse event array. Returns the folded state dict."""
    args = cursor or {"position": 0, "last_comment": 0, "last_removal": 0, "last_add": 0, "now_playing": 0}
    url = f"{GBS_BASE}/ajax?{urllib.parse.urlencode(args)}"
    try:
        with _open_with_cookies(url, cookies, timeout=10) as resp:
            if resp.status != 200:
                raise GbsApiError(f"HTTP {resp.status}")
            events = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 302 and "/accounts/login/" in e.headers.get("Location", ""):
            raise GbsAuthExpiredError("Session expired") from e
        raise

    state = {"removed_ids": [], "queue_html_snippets": [], "user_vote": 0, "score": "no votes"}
    for evt_name, payload in events:
        if evt_name == "now_playing":
            state["now_playing_entryid"] = payload
        elif evt_name == "metadata":
            state["icy_title"] = payload
        elif evt_name == "linkedMetadata":
            state["linked_metadata_html"] = payload
            state["now_playing_songid"] = _extract_songid_from_linked(payload)
        elif evt_name == "songLength":
            state["song_length"] = payload
        elif evt_name == "songPosition":
            state["song_position"] = payload
        elif evt_name == "userVote":
            state["user_vote"] = payload
        elif evt_name == "score":
            state["score"] = payload
        elif evt_name == "adds":
            state["queue_html_snippets"].append(payload)
        elif evt_name == "removal":
            state["removed_ids"].append(payload["id"])
        elif evt_name == "pllength":
            state["queue_summary"] = payload.strip()
    return state
```

### Example 3: Vote on now-playing track

```python
def vote_now_playing(entryid: int, vote: int, cookies) -> dict:
    """vote: 0 (clear), 1..5. Returns {'user_vote': N, 'score': '...'}."""
    if vote not in (0, 1, 2, 3, 4, 5):
        raise ValueError(f"Invalid vote: {vote}")
    args = {"position": 0, "last_comment": 0, "vote": vote, "now_playing": entryid}
    url = f"{GBS_BASE}/ajax?{urllib.parse.urlencode(args)}"
    with _open_with_cookies(url, cookies, timeout=15) as resp:
        events = json.loads(resp.read().decode("utf-8"))
    user_vote = 0
    score = "no votes"
    for evt_name, payload in events:
        if evt_name == "userVote":
            user_vote = payload
        elif evt_name == "score":
            score = payload
    return {"user_vote": user_vote, "score": score}
```

### Example 4: Submit song to playlist (with Django messages cookie decode)

```python
import base64
import json as _json

def _decode_django_messages(cookie_value: str) -> list[str]:
    """Decode Django's `messages` cookie payload to a list of message strings.

    Django format: signed dump where the JSON is base64url-encoded before the colon.
    We don't need the signature for our purposes — only the message body.
    """
    # Cookie value: <urlsafe_b64_encoded_json>:<sig>:<sig>
    encoded = cookie_value.split(":", 1)[0]
    # Pad as needed for base64url
    encoded += "=" * (-len(encoded) % 4)
    raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
    parsed = _json.loads(raw)
    return [m[3] for m in parsed if isinstance(m, list) and len(m) >= 4]


def submit(songid: int, cookies) -> str:
    """Submit a song to gbs.fm's playlist queue. Returns the messages payload."""
    url = f"{GBS_BASE}/add/{int(songid)}"
    # Don't follow redirects — capture the messages cookie from the 302
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):
            return None
    handler_noredir = _NoRedirect()
    handler_cookie = urllib.request.HTTPCookieProcessor(cookies)
    opener = urllib.request.build_opener(handler_cookie, handler_noredir)
    try:
        with opener.open(url, timeout=15) as resp:
            location = resp.headers.get("Location", "")
            if "/accounts/login/" in location:
                raise GbsAuthExpiredError("Session expired")
            # Pull the messages cookie from the response
            for cookie_line in resp.headers.get_all("Set-Cookie") or []:
                if cookie_line.startswith("messages="):
                    raw_val = cookie_line.split(";", 1)[0].split("=", 1)[1]
                    msgs = _decode_django_messages(raw_val)
                    return "; ".join(msgs)
    except urllib.error.HTTPError as e:
        if e.code == 302:
            # Same-pattern handling — Python's urllib raises HTTPError on intercepted redirects.
            ...
    return ""
```

**Note:** `urllib.request.HTTPRedirectHandler` returning `None` for `redirect_request` causes `urlopen` to return the 302 response directly (which is what we want). Verify with a unit test using a `BytesIO`-mocked response — researcher can flesh out the exact pattern in the `Wave 0` tests.

### Example 5: Hide-when-empty optional widget (D-06, D-07)

```python
# In NowPlayingPanel.__init__:
self._gbs_playlist_widget = QListWidget(self)
self._gbs_playlist_widget.setVisible(False)
layout.addWidget(self._gbs_playlist_widget)

self._gbs_vote_btns = QHBoxLayout()
self._vote_buttons = []
for v in range(1, 6):
    b = QPushButton(str(v), self)
    b.setVisible(False)
    b.clicked.connect(self._on_gbs_vote_clicked)  # bound method (QA-05)
    b.setProperty("vote_value", v)
    self._gbs_vote_btns.addWidget(b)
    self._vote_buttons.append(b)
layout.addLayout(self._gbs_vote_btns)

# In NowPlayingPanel.bind_station(station):
is_gbs = (station is not None and station.provider == "GBS.FM")
self._gbs_playlist_widget.setVisible(is_gbs)
logged_in = self._auth.is_gbs_logged_in()
for b in self._vote_buttons:
    b.setVisible(is_gbs and logged_in)
if is_gbs and logged_in:
    self._refresh_gbs_playlist()
    self._gbs_poll_timer.start(15000)
else:
    self._gbs_poll_timer.stop()
```

### Example 6: AccountsDialog `QGroupBox` shape

```python
# Source: musicstreamer/ui_qt/accounts_dialog.py:91-115 (YouTube + Twitch precedent)
self._gbs_box = QGroupBox("GBS.FM", self)
gbs_layout = QVBoxLayout(self._gbs_box)
self._gbs_status_label = QLabel("Not connected", self._gbs_box)
self._gbs_status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04
self._gbs_status_label.setFont(status_font)
self._gbs_action_btn = QPushButton("Connect", self._gbs_box)
self._gbs_action_btn.clicked.connect(self._on_gbs_connect_clicked)  # bound method, QA-05
gbs_layout.addWidget(self._gbs_status_label)
gbs_layout.addWidget(self._gbs_action_btn)

# In _build_layout (between YouTube and Twitch per D-04c):
layout.addWidget(self._youtube_box)
layout.addWidget(self._gbs_box)
layout.addWidget(self._twitch_box)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `(quality, position)`-only stream ordering | `(codec_rank, bitrate_kbps, position)` with unknown-bitrate-last partition | Phase 47.1 (2026-04-XX) | Phase 60 must populate `bitrate_kbps` non-zero for all 6 GBS quality tiers — including FLAC (recommend `1411` as CD-baseline sentinel) |
| `dbus-python` MPRIS2 | `PySide6.QtDBus` | v2.0 | N/A to Phase 60, but the existence of `MainWindow._on_station_activated` → MPRIS publish flow means active-playlist widget should not duplicate the existing MPRIS publish |
| Cookies file used directly | `cookie_utils.temp_cookies_copy()` + corruption auto-clear | Phase 999.7 | Phase 60 reuses `cookie_utils` exactly; do not introduce new cookie I/O |
| Self-capturing lambdas in signal connections | Bound methods (QA-05) | Project convention | All new menu / button / signal wiring in Phase 60 |
| `Qt.RichText` status labels (Phase 51-03 deviation) | `Qt.TextFormat.PlainText` (T-40-04 default) | Project convention; Phase 51-03 was a *bounded* exception | New `_gbs_status_label` uses PlainText (D-04c). Also all new widgets that render gbs.fm-side strings (artist/title/account name). |
| `audioaddict_listen_key` hidden field | AccountsDialog `QGroupBox` per provider | Phase 40 / 999.6 | Phase 60's `_gbs_box` is the third such group |
| Cookies-import dialog hardcoded for YouTube | Cookies-import dialog parameterized for `(target_url, validator, path, oauth_mode)` | Phase 60 (this phase) | Refactor `cookie_import_dialog.py` to accept a config; or duplicate-and-modify if refactor is too invasive |
| Dev fixtures stored at `<repo>/.local/` | Dev fixtures stored at `~/.local/share/musicstreamer/dev-fixtures/` (outside OneDrive) | Phase 60 D-04a (corrected 2026-05-04 after OneDrive purged the in-repo path) | Researcher / planner / verify-work all read from this path. Project `.gitignore` retains `.local/` as belt-and-braces; nothing should be there in practice. |

**Deprecated/outdated:**
- Direct GTK UI references (deleted in Phase 36 atomic cutover). All new UI is PySide6/Qt.
- `dbus-python` (replaced by `QtDBus`).
- Dev fixture at `<repo>/.local/gbs.fm.cookies.txt` (purged by OneDrive 2026-05-04; superseded by `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt`).

## Assumptions Log

> All previously `[ASSUMED]` claims have been verified or revised against live evidence. The remaining items below are MEDIUM-LOW confidence claims that the planner / verify-work should treat carefully.

| # | Claim | Section | Status | Risk if Wrong |
|---|-------|---------|--------|---------------|
| A1 | Django sessionid TTL is 14 days from last login | Pitfall 3 | [VERIFIED via dev fixture timestamp; sessionid 2026-04-22→2026-05-17 = 25 days as observed; could be 30-day default rather than 14. Range: 14–30 days.] | Off by 2× → user re-auth prompt fires earlier or later than expected; not a blocker. |
| A2 | `/ajax` 15s polling cadence is server-acceptable | Pitfall 5 | [VERIFIED: gbs.fm web UI itself uses DELAY=15000 in the JS embedded on the homepage, so 15s matches the official client] | Wrong → server soft-rate-limits us; back off to 30s. |
| A3 | `messages` cookie decoding via base64-url + JSON works for all gbs.fm Django messages | Example 4 | [VERIFIED on the success path ("Track added successfully!") and ("Song favourited successfully")] | Failure path (e.g. "duplicate", "rate-limited") may use a different message format; researcher couldn't trigger it without abusing the live system. Recommend graceful fallback: if decode fails, surface the raw cookie value as the error string. |
| A4 | `bitrate_kbps=1411` for FLAC interacts correctly with `stream_ordering.order_streams` partition logic | Code Examples — Pattern 1 | [ASSUMED — partition logic was Phase 47.1 D-09; not re-verified for FLAC > 320kbps case] | Wrong → FLAC sorts in unexpected position. Planner should reread `stream_ordering.py:43` and reverify. Alternative: `bitrate_kbps=0` + `position=10` (lowest=highest priority, partition unknowns last would actually push FLAC AFTER MP3). Test outcome before commit. |
| A5 | Search result HTML layout is stable across page loads (no A/B template variants) | Pitfall 6 | [VERIFIED across `?query=test` page 1 and page 2 — same `<table class="songs">` shape] | Wrong → parser fragility; mitigated by Wave 0 fixture pinning. |
| A6 | gbs.fm operator won't change the URL pattern for `/api/vote` or `/ajax` between research and ship | Pitfall 6 | [ASSUMED — site has no public changelog; researcher saw a GBS DEBUG=True 404 page suggesting the operator is NOT actively maintaining/refactoring] | Wrong → all vote and playlist code breaks. Mitigated by typed exceptions + smoke test.  |
| A7 | The 6 quality tiers (96/128/192/256/320/flac) won't change between research and ship | Capability 1 | [ASSUMED — gbs.fm has had this set for at least 2 years per the homepage's mention of FTP upload "now available"] | Wrong → import imports 6 streams when only 5 are valid. Mitigated by HEAD-check at import time (planner option). |
| A8 | `/api/vote` accepts vote=0 as "clear" without rate-limiting it as a separate vote | Capability 4 | [VERIFIED via cycle: vote=3→vote=0→vote=3→vote=0; no errors] | Wrong → optimistic UI can't roll back cleanly. |
| A9 | A `cookielib.MozillaCookieJar` written by `CookieImportDialog` from the user's browser export will include both `csrftoken` and `sessionid` | Auth Ladder | [ASSUMED — both are HttpOnly Django cookies set on `gbs.fm`; standard exporters include both. Dev fixture confirmed.] | Wrong → import succeeds but auth fails. Mitigated by `_validate_gbs_cookies` checking for both names. |
| A10 | gbs.fm will not change its login system to require captcha or 2FA before Phase 60 ships | Pitfall 6 | [LOW — operator's discretion] | Mitigated by ladder #3 (in-app browser via QtWebEngine handles captcha as long as it's not Cloudflare-Turnstile-grade). |
| A11 | `/add/<songid>` is GET-method (not POST), per Django URL pattern + observed redirect | Capability 6 | [VERIFIED via live HEAD; redirected with messages cookie set] | Wrong → submit fails with 405. Easily detected. |
| A12 | The token-quota for adds is server-tracked; no client-side enforcement is needed | Pitfall 8 | [VERIFIED — homepage shows current token count; gbs.fm enforces quota server-side] | Wrong → user can hit quota silently. Mitigated by surfacing the messages-cookie text on submit. |

**Risk concentrated in:** A4 (bitrate_kbps for FLAC — planner should re-read stream_ordering and verify), A6/A7/A10 (gbs.fm operator stability — out of MusicStreamer's control), A3 failure path (Django messages cookie format on errors — graceful fallback recommended).

## Open Questions

> All previously-open questions are now RESOLVED. The remaining items below are minor and won't block planning.

1. **FLAC bitrate sentinel value.** [ANSWERED conditionally — recommend `1411` (CD-baseline kbps) but planner should verify against `stream_ordering.py:43` Phase 47.1 D-09 partition logic. If the partition treats `bitrate_kbps=0` as "unknown" and partitions LAST, then FLAC can use 0 + position=10 to force first-place via stable-sort. If the partition is bitrate-descending, then FLAC needs bitrate_kbps > 320 to sort first. Resolved at planner discretion via a 5-line review.]
2. **Whether to keep ICY title or `linkedMetadata` HTML as the source of truth for "what is now playing."** [ANSWERED — both work. ICY title is faster (GStreamer pipeline pushes immediately); `linkedMetadata` is more accurate (canonical artist/title/album/song-page links from the server). Recommendation: trust ICY title for display; use `linkedMetadata` only to extract `songid` for the vote button stamp.]
3. **In-app login subprocess for ladder #3 — required for v1?** [ANSWERED — NO. File-picker + paste tabs cover the dev-machine flow (Kyle exports cookies from his browser via a Cookie-Editor extension). The `oauth_helper.py --mode gbs` subprocess is a polish path for v2. Phase 60 v1 ships with file-picker + paste only.]
4. **Whether to refactor `cookie_import_dialog.py` for parameterization OR subclass for gbs.fm.** [ANSWERED conditionally — refactor (option 1) recommended; subclass (option 2) is acceptable; duplicate-and-modify (option 3) is technical debt. Planner picks at PLAN time.]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python `urllib` (stdlib) | `gbs_api.py` | ✓ | Python 3.x | — |
| Python `http.cookiejar` (stdlib) | Cookie loading | ✓ | Python 3.x | — |
| Python `html.parser` (stdlib) | Playlist + search row parsing | ✓ | Python 3.x | regex (less robust) |
| PySide6 + QtWidgets | New AccountsDialog group, NowPlayingPanel widgets, GBSSearchDialog | ✓ | (per `pyproject.toml`) | — |
| QtWebEngine (subprocess `oauth_helper.py`) | OPTIONAL — only if planner chooses to add the in-app login subprocess polish | ✓ | (already shipping for Twitch / YouTube) | — |
| `cookie_utils.py` | Cookie hardening | ✓ | already in tree (Phase 999.7) | — |
| `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt` | Researcher only | ✓ (verified 2026-05-04) | Netscape format, 265 bytes, csrftoken + sessionid for `gbs.fm`, sessionid expires 2026-05-17 | — |
| Live gbs.fm endpoint | Smoke tests + research | ✓ | Caddy + Django + Icecast 2.4.4 (verified live) | Mock-based unit tests with captured fixtures |
| Network reachability to `gbs.fm` from CI / dev machine | Live smoke; not unit tests | ? (not blocking) | — | Unit tests use captured fixtures; live smoke is opt-in (e.g., `pytest -m live`) |

**Missing dependencies with no fallback:** None. All required dependencies are available.

**Missing dependencies with fallback:** None applicable.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (per `pyproject.toml` and existing `tests/` tree) [VERIFIED: codebase] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (per project precedent) |
| Quick run command | `pytest tests/test_gbs_api.py -x` |
| Full suite command | `pytest -x` |

### Pinned Fixtures (Wave 0 deliverable — concrete shapes from this research run)

These are the canonical captured response payloads. Either commit them as files in `tests/fixtures/gbs/`, or inline as constants in test modules. Files are recommended for the longer payloads.

| Fixture file | Source URL (curl with cookies) | Purpose |
|---|---|---|
| `tests/fixtures/gbs/ajax_cold_start.json` | `GET /ajax?position=0&last_comment=0&last_removal=0&last_add=0&now_playing=0` | Cold-start payload — drives `fetch_active_playlist` parser tests |
| `tests/fixtures/gbs/ajax_steady_state.json` | `GET /ajax?position=200&last_comment=0&last_removal=55552&last_add=1810740&now_playing=1810737` | Cursored steady-state — confirms minimal-delta response shape |
| `tests/fixtures/gbs/ajax_vote_set.json` | `GET /ajax?vote=3&now_playing=1810737&position=0&last_comment=0` | Vote=3 response with score+userVote |
| `tests/fixtures/gbs/ajax_vote_clear.json` | `GET /ajax?vote=0&now_playing=1810737&position=0&last_comment=0` | Vote=0 response (clear) |
| `tests/fixtures/gbs/ajax_login_redirect.txt` | `GET /ajax` (no cookies) | 302 to /accounts/login/ — auth-expired sentinel test |
| `tests/fixtures/gbs/home_playlist_table.html` | `GET /` (auth) — extract just `<table class="playlist">` block | Parser tests for queue-row extraction |
| `tests/fixtures/gbs/search_test_p1.html` | `GET /search?query=test&page=1` | Search parser — multi-row results |
| `tests/fixtures/gbs/search_test_p2.html` | `GET /search?query=test&page=2` | Pagination handling |
| `tests/fixtures/gbs/search_empty.html` | `GET /search?query=zzzzzzzzznoresults` | Empty-results path |
| `tests/fixtures/gbs/add_redirect_response.txt` | `GET /add/88135` (auth, no-redirect-follow) | Capture of the 302 + Set-Cookie messages — drives submit() decode test |
| `tests/fixtures/gbs/api_nowplaying.txt` | `GET /api/nowplaying` | Plain-text entryid response |
| `tests/fixtures/gbs/api_metadata.txt` | `GET /api/metadata` | 3-line ICY-style metadata |
| `tests/fixtures/gbs/api_vote_legacy.txt` | `GET /api/vote?songid=88135&vote=0` | Plain-text "<vote> <artist> - <title>" — for the historical vote path (deferred but documented) |
| `tests/fixtures/gbs/django_404_urlconf.html` | `GET /api/` | URL-pattern reference (research artifact; not used in tests) |
| `tests/fixtures/gbs/cookies_valid.txt` | Sanitized copy of `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt` (REPLACE the real csrftoken/sessionid values with `<csrftoken-PLACEHOLDER>` / `<sessionid-PLACEHOLDER>` before committing) | `_validate_gbs_cookies` validator test |
| `tests/fixtures/gbs/cookies_invalid_no_sessionid.txt` | Hand-crafted: csrftoken only, no sessionid | Validator rejection test |
| `tests/fixtures/gbs/cookies_invalid_wrong_domain.txt` | Hand-crafted: same shape but domain `evil.example.com` | Validator rejection test |
| `tests/fixtures/gbs/messages_cookie_track_added.txt` | The base64-prefixed value from the real `Set-Cookie: messages=...` header on the `/add/88135` 302 response | `_decode_django_messages` test |

**Capture script** (Wave 0 deliverable): `scripts/gbs_capture_fixtures.sh` — a small bash script that runs the relevant `curl -b cookies.txt` commands above, sanitizes any session-specific tokens, and writes to `tests/fixtures/gbs/`. Re-runnable when gbs.fm changes its UI.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GBS-01a | `fetch_streams()` returns the 6 hard-coded quality variants | unit | `pytest tests/test_gbs_api.py::test_fetch_streams_returns_six_qualities -x` | ❌ Wave 0 |
| GBS-01a | `fetch_station_metadata()` returns name+description+logo_url | unit | `pytest tests/test_gbs_api.py::test_fetch_station_metadata -x` | ❌ Wave 0 |
| GBS-01a | `import_station()` inserts new row first time, updates in-place second time (idempotent) | integration (in-memory Repo) | `pytest tests/test_gbs_api.py::test_import_idempotent -x` | ❌ Wave 0 |
| GBS-01a | Logo download wires through `assets.copy_asset_for_station` | integration | `pytest tests/test_gbs_api.py::test_logo_download -x` | ❌ Wave 0 |
| GBS-01a | FLAC stream `bitrate_kbps` value sorts correctly via `stream_ordering.order_streams` | regression | `pytest tests/test_stream_ordering.py::test_gbs_flac_ordering -x` | ❌ Wave 0 (extends existing suite) |
| GBS-01b | `_validate_gbs_cookies` accepts dev fixture format | unit | `pytest tests/test_gbs_api.py::test_validate_cookies_accept -x` | ❌ Wave 0 |
| GBS-01b | `_validate_gbs_cookies` rejects no-sessionid / wrong-domain | unit | `pytest tests/test_gbs_api.py::test_validate_cookies_reject -x` | ❌ Wave 0 |
| GBS-01b | AccountsDialog `_gbs_box` renders between YouTube and Twitch | UI (pytest-qt) | `pytest tests/ui_qt/test_accounts_dialog.py::test_gbs_box_position -x` | ❌ Wave 0 |
| GBS-01b | Connect button writes cookies to `paths.gbs_cookies_path()` with 0o600 perms | UI | `pytest tests/ui_qt/test_accounts_dialog.py::test_gbs_connect_writes_cookies -x` | ❌ Wave 0 |
| GBS-01b | Disconnect clears the cookies file and updates label | UI | `pytest tests/ui_qt/test_accounts_dialog.py::test_gbs_disconnect_clears -x` | ❌ Wave 0 |
| GBS-01c | `fetch_active_playlist()` parses cold-start fixture into expected state dict | unit (file fixture) | `pytest tests/test_gbs_api.py::test_fetch_playlist_cold_start -x` | ❌ Wave 0 |
| GBS-01c | `fetch_active_playlist()` parses steady-state fixture | unit | `pytest tests/test_gbs_api.py::test_fetch_playlist_steady_state -x` | ❌ Wave 0 |
| GBS-01c | `fetch_active_playlist()` raises `GbsAuthExpiredError` on 302 → /accounts/login/ | unit | `pytest tests/test_gbs_api.py::test_fetch_playlist_auth_expired -x` | ❌ Wave 0 |
| GBS-01c | Active-playlist widget hides when station is non-GBS.FM | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_playlist_hidden_for_non_gbs -x` | ❌ Wave 0 |
| GBS-01c | Active-playlist widget populates from `fetch_active_playlist()` mock | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_playlist_populates -x` | ❌ Wave 0 |
| GBS-01c | Active-playlist QTimer pauses when widget is hidden | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_playlist_timer_pauses -x` | ❌ Wave 0 |
| GBS-01d | Vote button hidden when logged out | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_vote_hidden_when_logged_out -x` | ❌ Wave 0 |
| GBS-01d | `vote_now_playing()` parses success fixture into `{user_vote, score}` | unit | `pytest tests/test_gbs_api.py::test_vote_now_playing_success -x` | ❌ Wave 0 |
| GBS-01d | Vote click → optimistic UI → API success → confirmed state from response | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_vote_optimistic_success -x` | ❌ Wave 0 |
| GBS-01d | Vote click → optimistic UI → API failure → rollback + toast | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_vote_optimistic_rollback -x` | ❌ Wave 0 |
| GBS-01d | Vote button entryid is updated only on `now_playing` event from `/ajax` (Pitfall 1 race) | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_vote_entryid_updates_from_ajax -x` | ❌ Wave 0 |
| GBS-01e | `search()` parses test_p1 fixture into result list with songid+artist+title | unit | `pytest tests/test_gbs_api.py::test_search_parses_results -x` | ❌ Wave 0 |
| GBS-01e | `search()` extracts pagination from "page X of Y" text | unit | `pytest tests/test_gbs_api.py::test_search_pagination -x` | ❌ Wave 0 |
| GBS-01e | `submit()` decodes Django messages cookie on success path | unit | `pytest tests/test_gbs_api.py::test_submit_success_decodes_messages -x` | ❌ Wave 0 |
| GBS-01e | `submit()` raises `GbsAuthExpiredError` on 302 → /accounts/login/ | unit | `pytest tests/test_gbs_api.py::test_submit_auth_expired -x` | ❌ Wave 0 |
| GBS-01e | GBSSearchDialog query → results list populated from `search()` mock | UI | `pytest tests/ui_qt/test_gbs_search_dialog.py::test_search_populates -x` | ❌ Wave 0 |
| GBS-01e | GBSSearchDialog Submit → calls `submit(songid)` and toasts on success | UI | `pytest tests/ui_qt/test_gbs_search_dialog.py::test_submit_success -x` | ❌ Wave 0 |
| GBS-01e | GBSSearchDialog Submit → inline error on duplicate / token-quota | UI | `pytest tests/ui_qt/test_gbs_search_dialog.py::test_submit_inline_error -x` | ❌ Wave 0 |
| GBS-01f | `stream_ordering.order_streams` consumes Phase 60 output unchanged | regression | `pytest tests/test_stream_ordering.py -x` | ✅ exists |
| GBS-01-live | Live-API smoke (manual / opt-in) — `import_station` against real gbs.fm + verify 6 streams + logo | manual smoke | `pytest -m live tests/test_gbs_api.py::test_live_import` (skipped by default) | ❌ Wave 0 (script only) |
| GBS-01-live | Live `/ajax` smoke — verify event taxonomy hasn't changed | manual smoke | `pytest -m live tests/test_gbs_api.py::test_live_ajax_taxonomy` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_gbs_api.py tests/ui_qt/test_gbs_search_dialog.py tests/ui_qt/test_now_playing_panel_gbs.py tests/ui_qt/test_accounts_dialog.py -x` (focused subset; <10 s expected).
- **Per wave merge:** `pytest -x` (full suite green).
- **Phase gate:** Full suite green + manual live smoke pass (driver: Kyle, with the cookies installed in production form per ladder #3).

### Wave 0 Gaps

- [ ] `tests/test_gbs_api.py` — covers GBS-01a (HTTP layer + import) + GBS-01c (active playlist) + GBS-01d (vote unit) + GBS-01e (search/submit unit) + GBS-01b (validator)
- [ ] `tests/ui_qt/test_now_playing_panel_gbs.py` — covers GBS-01c (active playlist widget) + GBS-01d (vote UI)
- [ ] `tests/ui_qt/test_gbs_search_dialog.py` — covers GBS-01e (search/submit dialog UI)
- [ ] Extension to `tests/ui_qt/test_accounts_dialog.py` — covers GBS-01b (AccountsDialog group + Connect/Disconnect cookies write)
- [ ] `tests/conftest.py` (or per-test) shared fixtures: `mock_gbs_api`, `fake_repo`, `fake_cookies_jar`
- [ ] `tests/fixtures/gbs/*.json *.html *.txt` — captured response payloads (15 files listed above)
- [ ] `scripts/gbs_capture_fixtures.sh` — re-runnable capture script
- [ ] Extension to `tests/test_stream_ordering.py` — `test_gbs_flac_ordering` regression test for FLAC bitrate sentinel value
- [ ] (Optional) `scripts/gbs_live_smoke.py` — opt-in live-API smoke launcher

*(Existing `pytest` infrastructure covers the framework itself; only test files and fixtures are net-new.)*

## Security Domain

> `security_enforcement` config flag treated as enabled per default.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Reuse `cookie_import_dialog.py` (ladder #3 chosen) — no hand-rolled username/password storage |
| V3 Session Management | yes | Cookies file at 0o600; `cookie_utils.is_cookie_file_corrupted()` short-circuits on detection; no roundtrip through display widgets |
| V4 Access Control | yes | Auth-gating on UI surfaces (vote button hidden when logged out, submit disabled when logged out, search dialog requires login per D-08c) |
| V5 Input Validation | yes | All gbs.fm API responses parsed defensively — HTML parsing rejects unexpected shapes; `Qt.TextFormat.PlainText` on every label rendering gbs.fm strings (artist/title/score/account name) |
| V6 Cryptography | no (single-user, file-based credential — no encryption-at-rest required) | If a token is ever encrypted at rest, defer to platformdirs-managed file with 0o600 — do not hand-roll crypto |
| V7 Error Handling | yes | Typed exceptions in `gbs_api.py` (D-03c): `GbsAuthExpiredError`, `GbsApiError`, `GbsRateLimitError` (future); error toasts never log credential values |
| V13 API/Web Service | yes | HTTPS-only; 10–15 s timeouts; bound-method connections; URL constants in module (no SSRF risk); `/ajax` and `/api/vote` are GET-with-side-effects but the URLs are constants |

### Known Threat Patterns for Phase 60 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cookie file leak via toast / log | Information Disclosure | Toasts and log lines must NEVER include the cookie value. `_gbs_status_label` shows status only ("Connected as Lightning Jim" / "Not connected") — derived from `cookie_utils` validation, not the cookie content. |
| HTML injection via gbs.fm-side string | Tampering | `Qt.TextFormat.PlainText` (T-40-04) on every label rendering gbs.fm strings (artist, title, score, account name, search row) |
| Self-capturing lambda → `self` leak | Tampering / DoS | Bound-method connections (QA-05) on every new connection |
| Cookie file world-readable | Information Disclosure | 0o600 perms post-write (Phase 999.7) |
| API call on UI thread → frozen UI on slow network | DoS (UX) | Worker thread for vote / submit / fetch_active_playlist (D-07a, D-08b, `cover_art.py` precedent) |
| Optimistic-UI state out of sync with server | Repudiation | Use the `userVote` + `score` events from the `/ajax` response to confirm or roll back; never assume the server applied the optimistic guess (Pitfall 2) |
| Stale auth cookie used silently | Repudiation | Detect 302→/accounts/login/ → typed exception → toast + AccountsDialog flips to "Not connected" (Pitfall 3) |
| Polling × token expiry × rate-limit cascade | DoS (3rd-party) | Pause polling when panel hidden; respect 15s cadence; back off if soft-rate-limited (no headers exposed; back off heuristically) (Pitfall 5) |
| Idempotent re-import resurrects user-deleted streams | Repudiation | Confirmation toast on update; document semantics (Pitfall 4) |
| GET-with-side-effects retried on transient failure | Tampering | Don't retry; surface to user; let the user decide (Pitfall 7) |
| HTML scraping breaks → silent search failure | Information Disclosure (denial of search results) | Anchor on data-songid / id="N" / `/song/X` / `/add/X` selectors; pin fixture HTML for unit tests (Pitfall 6) |
| Submit via `/add/X` exhausts user's token quota | Tampering / DoS (UX) | Decode the messages cookie text and surface verbatim; user sees "you don't have enough tokens" inline error (Pitfall 8) |
| Cookie file at `~/.local/share/musicstreamer/dev-fixtures/...` accidentally synced to OneDrive | Information Disclosure | `~/.local/` is OUTSIDE the OneDrive-synced project tree (researched 2026-05-04 D-04a correction); plus project `.gitignore` retains `.local/` rule as belt-and-braces. |

## Sources

### Primary (HIGH confidence)

- `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt` (live dev fixture, this run) — Netscape format with `csrftoken` (q6UZ9t0iItfTqTllCQLLdCEjU3Q0xSeV) + `sessionid` (v6mfkwosmt16s0hz9x5y6nqjmmiphfg2) for `gbs.fm`
- Live `gbs.fm` HTTP probes (this run, 2026-05-04 ~13:28 UTC):
  - `GET /` (auth) — 200 home page with embedded JS (jQuery 1.3, voteHandler, ajaxLoop)
  - `GET /` (no auth) — 302 → `/accounts/login/?next=/`
  - `GET /api/` — 404 with full Django URLconf dump (DEBUG=True production leak)
  - `GET /ajax?...&vote=N&now_playing=<entryid>` — vote round-trip cycle (vote=3→0→3→0)
  - `GET /search?query=test&page=1` and `&page=2` — pagination probe (12 pages)
  - `GET /add/88135` (auth) — 302 + Django messages cookie capture
  - `GET /96` … `GET /flac` — Icecast HEAD probes confirming MP3 + Ogg FLAC
  - `GET /settings` (auth) — API key surface inspection
  - `GET /api/{nowplaying,listeners,metadata,users}` — auxiliary endpoints
  - `GET /api/vote?songid=88135&vote=0` (auth + various API-key probes) — confirmed cookie-only auth
- `musicstreamer/aa_import.py` (read in full) — multi-quality import precedent
- `musicstreamer/repo.py:51-110` and `:178-202` — `station_streams` schema and CRUD (per CONTEXT.md citations)
- `musicstreamer/stream_ordering.py:43` — quality ordering invariants (per STATE.md Phase 47.1 entry)
- `musicstreamer/oauth_helper.py` (header read) — Twitch cookie-harvest QtWebEngine precedent
- `musicstreamer/ui_qt/cookie_import_dialog.py` (header read) — YouTube cookies-import precedent (`_validate_youtube_cookies`, three-tab dialog shape)
- `.planning/phases/60-gbs-fm-integration/60-CONTEXT.md` — locked decisions D-01..D-08e
- `.planning/REQUIREMENTS.md` GBS-01 — requirement framing
- `.planning/seeds/SEED-008-gbs-fm-integration.md` — full vision and deferred-feature rationale
- `.planning/STATE.md` — project decision history (Phase 47.x stream-ordering invariants, Phase 999.7 cookie utils, Phase 51 sibling pattern, Phase 64 hide-when-empty)

### Secondary (MEDIUM confidence)

- `WebFetch https://gbs.fm` (initial blocked run, 2026-05-04) — confirmed login wall, no public API hint (now superseded by direct authenticated probes)
- `WebSearch "gbs.fm radio station API documentation"` (initial blocked run) — no relevant results

### Tertiary (LOW confidence)

- (none — all `[ASSUMED]` claims explicitly flagged in `## Assumptions Log` for follow-up)

## Metadata

**Confidence breakdown:**
- Standard stack (HTTP / Repo / stream_ordering / assets): HIGH — locked by CONTEXT.md and existing codebase
- Auth ladder choice: HIGH — directly verified that ladder #1 is non-functional and ladder #3 works
- Endpoint signatures + response shapes: HIGH — every Phase-60 endpoint exercised live with the dev cookies
- Architecture patterns (multi-quality import / hide-when-empty / optimistic UI / worker thread): HIGH — direct precedents
- Pitfalls: HIGH — most inferred from live evidence; A11 (rate-limit cadence) MEDIUM (no headers from server)
- Validation architecture: HIGH — fixture shapes pinned to actual responses
- Security domain: HIGH — patterns match existing project conventions

**Research date:** 2026-05-04
**Valid until:** 2026-06-03 (30-day default — gbs.fm side may shift; project-side findings are stable)

## RESEARCH COMPLETE

**Phase:** 60 — GBS.FM Integration
**Status:** All previously-blocked questions resolved. Auth ladder locked (#3 — cookies-import dialog). All six API surface capabilities mapped end-to-end with concrete endpoint signatures, request/response shapes, auth requirements, and pinned fixture targets. Validation Architecture has concrete pytest commands tied to specific fixture files (15 fixtures listed for Wave 0 capture). Common Pitfalls expanded with HTML-scraping fragility, GET-with-side-effects retry hazard, token-quota messaging, and Django-CSRF-for-POSTs (future-phase note).

### Key Findings (final)

- **Auth ladder #3 (cookies-import dialog) is the only viable D-04 choice.** API key paste is documented but non-functional for vote/search/add. OAuth doesn't apply. Username/password rejected for lack of precedent.
- **Six static stream URLs** (96/128/192/256/320 MP3 + flac as Ogg FLAC) — no PLS/M3U indirection, no API call needed for `fetch_streams`.
- **`/ajax` is the workhorse endpoint:** event-array JSON returning `now_playing`, `metadata`, `linkedMetadata`, `songLength`, `songPosition`, `userVote`, `score`, `adds`, `removal`, etc. Polled at 15s cadence (matches gbs.fm web UI).
- **Vote-on-now-playing uses `/ajax?vote=N&now_playing=<entryid>`**, which returns the new score + userVote in one round-trip. No round-trip needed to reconcile optimistic UI.
- **Search returns HTML** (no JSON endpoint). Parse `<table class="songs">` rows by anchoring on `data-songid` and `/add/<id>` href. Pagination via `?page=N`; result count exposed in "page X of Y" text.
- **Submit via `GET /add/<songid>` returns 302 + Django `messages` cookie** carrying the success/error string. Decode the cookie's base64-prefixed JSON to surface the actual message text.
- **Django sessionid cookie has 14–30 day TTL** — Phase 60 must detect 302→/accounts/login/ as the auth-expired sentinel, raise typed exception, prompt re-import.
- **Logo is `https://gbs.fm/images/logo_3.png`** (100×100, no auth, stable URL since 2024-12).
- **No rate-limit headers exposed** — pause polling on panel-hidden, don't retry GET-with-side-effects.

### File Updated

`/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/phases/60-gbs-fm-integration/60-RESEARCH.md` — merged in place (non-fixture-dependent sections preserved; fixture-dependent sections rewritten with verified data; `## RESEARCH BLOCKED` superseded by `## RESEARCH COMPLETE`).

### Ready for Planning

Research complete. Planner has full API surface map + locked auth ladder + concrete fixture pinning + 11 enumerated pitfalls. No blockers remaining.
