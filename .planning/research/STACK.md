# Technology Stack

**Project:** MusicStreamer v1.3 — Discovery & Favorites additions
**Researched:** 2026-03-27
**Scope:** New capabilities only. Existing stack (GTK4/Libadwaita, GStreamer, SQLite, yt-dlp, urllib, threading/GLib.idle_add) is validated and unchanged.

---

## Existing Stack (Do Not Change)

| Technology | Role |
|------------|------|
| Python 3.x | Application language |
| GTK 4.0 / Libadwaita 1 | GUI framework |
| GStreamer 1.0 (`playbin`) | Streaming playback |
| PyGObject (`gi`) | GObject introspection bindings |
| SQLite3 (stdlib) | Persistence |
| yt-dlp (latest) | YouTube URL resolution |
| urllib (stdlib) | HTTP GET (iTunes API) |
| threading + GLib.idle_add | Cross-thread UI dispatch |

---

## New Stack: Radio-Browser.info Integration

### Approach: Direct REST API via urllib (no new library)

Radio-Browser.info exposes a public JSON REST API with no authentication required. The API is accessed via one of several mirror servers; the recommended approach is DNS-based server discovery.

**No new libraries required.** `urllib.request` already handles JSON GETs.

| Component | Purpose | Notes |
|-----------|---------|-------|
| `urllib.request` (stdlib) | All API calls | Already used for iTunes; identical pattern |
| DNS lookup for server selection | Discover mirror: `all.api.radio-browser.info` → picks a live server | Use `socket.getaddrinfo("all.api.radio-browser.info", 80)` or hardcode `de1.api.radio-browser.info` for simplicity |

**Endpoints used:**

| Endpoint | Purpose |
|----------|---------|
| `GET /json/stations/search?name={q}&limit=50&order=votes&reverse=true` | Browse/search stations |
| `GET /json/stations/byuuid/{uuid}` | Single station lookup (for save-to-library) |
| `POST /json/url/{stationuuid}` | Click counter (optional — community courtesy) |

**Response fields needed per station:**

| Field | Maps to |
|-------|---------|
| `stationuuid` | External ID (store for dedup) |
| `name` | Station name |
| `url_resolved` | Actual stream URL (prefer over `url`) |
| `favicon` | Station art URL (download + save to assets) |
| `tags` | Comma-separated genre tags |
| `country` | Optional context |
| `votes` | Sort order for results |

**Base URL:** `https://de1.api.radio-browser.info` (hardcode this mirror; it's a primary EU server, reliable). No auth headers needed. Set `User-Agent: MusicStreamer/1.3` as a courtesy.

**Rate limits:** No documented hard limit; pagination recommended for large queries. `limit=50` per page is sufficient for interactive browse.

**Confidence:** HIGH — Radio-Browser.info is a well-established community API (active since ~2015), JSON endpoints and field names are stable and widely used by open source radio players (Rhythmbox plugin, etc.). `url_resolved` over `url` is the documented recommendation for direct playback.

**What NOT to use:**
- `pyradios` pip package — thin wrapper around the same API; adds a dependency for zero benefit when urllib is already in use
- `url` field directly — may be a redirect or PLS URL; `url_resolved` is the pre-resolved direct stream URL

---

## New Stack: AudioAddict Import

### Approach: Unofficial REST API + PLS parsing (stdlib only)

AudioAddict exposes an unofficial but stable REST API used by their own web/mobile clients. The API key from the user's DI.fm account authenticates channel access; stream URLs follow a documented pattern.

**No new libraries required.** urllib handles the API calls; PLS is a simple INI-like text format parseable with `configparser` (stdlib) or plain string splitting.

| Component | Purpose | Notes |
|-----------|---------|-------|
| `urllib.request` (stdlib) | Fetch channel list JSON | Same pattern as iTunes/Radio-Browser calls |
| `configparser` (stdlib) | Parse `.pls` playlist files | PLS is INI-format; `configparser.RawConfigParser` reads it cleanly |

**API endpoints:**

| Endpoint | Purpose |
|----------|---------|
| `GET https://api.audioaddict.com/v1/{network}/channels` | Full channel list for a property |
| `GET https://listen.di.fm/premium_{quality}/{channel_key}?{api_key}` | Direct stream URL pattern |

**Network identifiers:**

| Property | Network value |
|----------|--------------|
| DI.fm | `di` |
| ZenRadio | `zen` |
| JazzRadio | `jazzradio` |
| RockRadio | `rockradio` |

**Quality suffixes:**

| Quality | Suffix | Bitrate |
|---------|--------|---------|
| High | `_hi` | 320 kbps mp3 |
| Medium | `_premium` | 128 kbps aac |
| Low | `_premium_low` | 64 kbps aac |

**Channel list response fields needed:**

| Field | Maps to |
|-------|---------|
| `key` | Stream slug (used in URL construction) |
| `name` | Station display name |
| `images.default` | Station art URL |
| `description` | Optional — can populate as tag |

**Stream URL construction (no PLS needed):**
```
https://listen.di.fm/premium_{quality}/{channel_key}?{api_key}
```
This is a direct stream URL GStreamer can play. PLS files are the alternative (dual-server failover) but constructing direct URLs is simpler and sufficient.

**API key storage:** Store as a plain string in the `settings` table (key: `audioaddict_api_key`). The existing `settings` table in `repo.py` handles this.

**Confidence:** MEDIUM — AudioAddict's API is unofficial/reverse-engineered. The channel list endpoint and stream URL pattern are well-documented in community projects (e.g., `https://github.com/DannyBen/audio_addict`, confirmed in project memory). Endpoint stability is not guaranteed by AudioAddict but has been stable for years. The `api.audioaddict.com/v1/{network}/channels` pattern is confirmed by multiple community implementations.

**What NOT to use:**
- PLS parsing as primary approach — direct URL construction is simpler and equivalent for single-stream use; PLS dual-server failover is unnecessary complexity for this app
- `mutagen` or audio metadata libs — not needed; we're constructing URLs, not reading files
- Storing the API key in a dotfile or separate config — `settings` table already exists and handles persistence

---

## New Stack: YouTube Playlist Import

### Approach: yt-dlp (already installed) — flat playlist extraction

yt-dlp handles YouTube playlist extraction natively. No new library needed.

| Component | Purpose | Notes |
|-----------|---------|-------|
| `yt-dlp` (existing) | Extract playlist entries as flat list | Already used for single video URL resolution |
| `threading.Thread` (stdlib) | Run yt-dlp off GTK main thread | Same pattern as YT thumbnail fetch in v1.1 |

**yt-dlp invocation for playlist:**

```python
import yt_dlp

opts = {
    "quiet": True,
    "extract_flat": True,   # don't resolve each entry — just get metadata
    "playlist_items": "1-50",  # limit to first 50 entries
}
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info(playlist_url, download=False)
    entries = info.get("entries", [])
```

**Fields per entry (from `extract_flat`):**

| Field | Maps to |
|-------|---------|
| `url` | YouTube video URL (use as station URL — yt-dlp resolves at play time) |
| `title` | Station name |
| `thumbnails[-1].url` | Station art (download async, same pattern as single-station YT thumbnail) |

**Filtering entries:** `extract_flat` returns all playlist items including non-live videos. Filter by `entry.get("live_status") == "is_live"` or accept all and let the player handle non-live entries gracefully (current behavior).

**Confidence:** HIGH — `extract_flat=True` is the documented yt-dlp option for playlist metadata without full resolution. The existing codebase already imports `yt_dlp` and uses the same `YoutubeDL` context manager pattern. This is a direct extension of existing usage.

**What NOT to use:**
- YouTube Data API v3 — requires an API key and quota management; yt-dlp achieves the same result without credentials
- `pytube` — separate library, unnecessary when yt-dlp is already present and more capable

---

## New Stack: Favorites DB Schema

### Approach: New `favorites` table in existing SQLite DB

No new library. Schema addition via `ALTER TABLE` / `CREATE TABLE IF NOT EXISTS` pattern already established in `db_init()`.

**New table:**

```sql
CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_title TEXT NOT NULL,
    station_id INTEGER,
    station_name TEXT NOT NULL,
    provider_name TEXT,
    favorited_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE SET NULL
);
```

**Design notes:**
- `station_id` nullable FK — station may be deleted after favoriting; `station_name` + `provider_name` are denormalized for display without JOIN
- `track_title` is the raw ICY title string (same value shown in now-playing)
- `strftime('%Y-%m-%dT%H:%M:%f', 'now')` matches the ms-precision pattern already used for `last_played_at` (logged in KEY DECISIONS — second-level granularity caused ordering failures)
- No dedup constraint — user may favorite the same song from different stations; uniqueness on `(track_title, station_id)` would prevent that

**New `Favorite` dataclass (models.py):**

```python
@dataclass
class Favorite:
    id: int
    track_title: str
    station_id: Optional[int]
    station_name: str
    provider_name: Optional[str]
    favorited_at: Optional[str]
```

**Confidence:** HIGH — direct extension of existing SQLite schema patterns in the codebase.

---

## Installation

No new pip dependencies for any v1.3 feature. All capabilities are covered by:
- `urllib.request` (stdlib) — Radio-Browser.info + AudioAddict API calls
- `configparser` (stdlib) — PLS parsing if needed
- `socket` (stdlib) — optional DNS mirror discovery for Radio-Browser
- `yt_dlp` (existing) — YouTube playlist import
- `sqlite3` (stdlib) — favorites schema
- `threading` + `GLib.idle_add` (existing pattern) — async API calls

```bash
# No new dependencies — existing uv.lock unchanged
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Radio-Browser API client | urllib (stdlib) | `pyradios` pip package | Thin wrapper around same endpoints; adds pip dep for zero functional benefit |
| AudioAddict stream URLs | Direct URL construction | PLS file parsing | PLS dual-server failover not needed; direct URL is simpler and GStreamer handles stream failures |
| YouTube playlist | yt-dlp `extract_flat` | YouTube Data API v3 | Requires API key + quota; yt-dlp is already a dependency |
| Favorites storage | SQLite `favorites` table | Separate file (JSON/CSV) | SQLite already used; keeps all persistence in one place with FK relationships |

---

## What NOT to Add

| Avoid | Why |
|-------|-----|
| `requests` library | urllib covers all HTTP needs; requests adds a dependency with no benefit at this scale |
| `pyradios` | Wrapper for Radio-Browser API; stdlib urllib is sufficient |
| YouTube Data API | Requires API key; yt-dlp covers the use case without credentials |
| `mutagen` | Audio metadata parsing library; not needed — we're constructing URLs and reading ICY via GStreamer |

---

## Sources

| Source | Confidence | Notes |
|--------|------------|-------|
| Radio-Browser.info API docs (training data + community usage) | HIGH | JSON REST API structure, `url_resolved` recommendation, no-auth model are stable and widely documented |
| AudioAddict API — `github.com/DannyBen/audio_addict` (project memory, 2026-03-21) | MEDIUM | Unofficial reverse-engineered API; URL pattern confirmed in memory note; network identifiers from community docs |
| yt-dlp `extract_flat` option (existing codebase usage) | HIGH | Already in use in this codebase; `extract_flat=True` is documented yt-dlp behavior |
| SQLite schema patterns (existing repo.py) | HIGH | Direct extension of established db_init() migration pattern |

---

*Stack research for: MusicStreamer v1.3 Discovery & Favorites*
*Researched: 2026-03-27*
