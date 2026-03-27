# Feature Research

**Domain:** Personal GNOME desktop internet radio — v1.3 Discovery & Favorites
**Researched:** 2026-03-27
**Confidence note:** Web access unavailable. Findings draw on training knowledge of
Radio-Browser.info API (stable, well-documented), AudioAddict PLS auth pattern
(publicly documented), yt-dlp playlist extraction (well-established CLI), and UX
patterns from Shortwave, RadioDroid, and general GNOME media apps (knowledge cutoff
Aug 2025). Confidence levels noted per claim.

---

## Scope Boundary

This file covers ONLY the four v1.3 feature groups. Existing v1.2 features are not
re-analyzed. Anti-features from v1.0 research that now apply here are explicitly
re-evaluated.

---

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Radio-Browser.info: search by name | Every discovery tool (Shortwave, RadioDroid, iHeartRadio) supports name search. Without it, browsing 30k stations is unusable. | LOW | GET `/json/stations/search?name=...&limit=50`. No auth. Returns JSON array. |
| Radio-Browser.info: preview/play before saving | Users expect to audition before committing to library. Any radio directory app does this. | LOW | Same GStreamer pipeline — just pass `url` without inserting DB row. Need a transient "preview" state distinct from "library station playing". |
| Radio-Browser.info: save to library | Only reason to open a directory is to keep stations. If you can browse but not save, it's a dead end. | LOW | Map RB station fields → local `Station` model. Provider = source hostname or network name. |
| AudioAddict import: all four properties | DI.fm, ZenRadio, JazzRadio, RockRadio share the same API/PLS format. Users expect a single flow to import from all. | MEDIUM | Four base URLs, same auth pattern. One dialog handles all. |
| AudioAddict: quality selection | AudioAddict offers hi/med/low streams. Users with metered connections need control. PLS URL encodes quality. | LOW | Radio button or dropdown in import dialog. Three variants per channel in the PLS. |
| Favorite songs: star current ICY track | Core affordance of any music app with track metadata. Users who discover songs via radio want to save them. | LOW | Star button in now-playing panel, active only when ICY track title is non-empty. |
| Favorite songs: stored with context | Context (station name, provider) is what makes the favorite meaningful — you know where you heard it. The user note explicitly requires this. | LOW | DB table: `id`, `title`, `station_name`, `provider`, `starred_at`. No foreign key needed — stations can be deleted. |
| Favorite songs: inline list view | Toggle between Stations and Favorites in the same panel space. Standard tabbed/segmented pattern in media apps. | LOW–MED | Gtk.Stack swap between station list widget and favorites list widget. Segmented button or toggle at top. |
| Favorite songs: remove from favorites | Every favorites list needs a delete path. Without it, bad favorites accumulate forever. | LOW | Swipe-to-delete or context menu item. `Adw.ActionRow` supports swipe via `Adw.SwipeActionRow` or a row-level delete button. |
| YouTube playlist import: paste URL | The only reasonable input method for a public playlist — users copy from browser. | LOW | Single text entry dialog. Pass to yt-dlp `--flat-playlist --dump-json`. |
| YouTube playlist import: live streams only | YT playlists can mix VOD and live. User only wants live streams as radio stations. | MED | Filter yt-dlp output: `is_live == true` or `was_live == false` heuristic on returned metadata. |

---

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Radio-Browser.info: filter by tag/genre | Name search gets you to known stations. Tag filter gets you to discovery ("find me ambient stations"). Shortwave supports tag filtering; many simple apps don't. | MEDIUM | `/json/tags` for tag list, `/json/stations/search?tag=...`. Combine with name search. |
| Radio-Browser.info: filter by country | Useful for non-English radio listeners. Country filter is a standard RB feature. | LOW | `/json/countrycodes` → dropdown. Adds one param to search query. |
| AudioAddict import: incremental (add missing only) | Re-running import shouldn't duplicate stations. Smart merge (match on URL or channel slug) is better than "delete all and reimport". | MEDIUM | Check existing station URLs before insert. Skip if URL already exists. Optional: update name/art if changed. |
| Favorite songs: iTunes metadata on star | When starring a track, pull genre/artwork from iTunes if available. Enriches the favorite record at no extra cost since iTunes is already queried for cover art. | LOW | Reuse existing iTunes fetch. Store `genre` and `artwork_url` in favorites table if returned. |
| YouTube playlist import: auto-title from metadata | yt-dlp returns `title`, `uploader`, `thumbnail` per entry. Pre-populate station name and art rather than generic URL. | LOW | Already done for single-station YT import — extend to batch. `title` → station name, `thumbnail` → station art URL. |

---

### Anti-Features

| Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Radio-Browser.info: full "discover" tab replacing station list | 30k stations visible at once destroys the app's core value ("right station in 2 clicks"). The directory is a tool for populating your library, not your primary UI. | Keep discovery as a modal/sheet opened from a button. Search results are a temporary view, not a persistent state. |
| AudioAddict: import with no quality choice | Silently importing hi-fi for a user on a slow connection is a silent failure they'll notice as stuttering. | Always present quality selection before import. Default to medium. |
| Favorites: social sharing or export | Scope creep. This is a single-user local app. | Not applicable. Store locally only. |
| YouTube playlist import: VOD as "stations" | VOD YouTube videos are not streams — they'll behave unpredictably with GStreamer + yt-dlp in stream mode. | Filter to `is_live=true` during import. Show a count of skipped non-live entries. |
| Radio-Browser.info: auto-refresh / sync | Polling the RB API periodically to update saved stations adds background complexity with minimal value. Users manage their library. | Import once, user manages manually. |
| Favorites: playback history (all played tracks) | Different feature from favorites. Auto-history is invisible, gets large fast, and needs separate UI. | Keep favorites as intentional, user-starred saves only. |

---

## API Behavior Documentation

### Radio-Browser.info API

**Confidence: HIGH** — Stable public API, unchanged for years, widely used by Shortwave and RadioDroid.

- **Base URL:** DNS-round-robined via `all.api.radio-browser.info`. Client should resolve SRV records or use `all.api.radio-browser.info` directly.
- **Auth:** None. Public API, no key required.
- **Rate limit:** No official hard limit. Reasonable desktop usage (search on keypress with 300ms debounce) is fine.
- **User-Agent:** Best practice to set a descriptive User-Agent (`MusicStreamer/1.3 ...`). Not enforced but good citizenship.
- **Key endpoints:**
  - `GET /json/stations/search?name={query}&limit=50&hidebroken=true` — name search
  - `GET /json/stations/search?tag={tag}&limit=100&hidebroken=true` — tag filter
  - `GET /json/tags?limit=100&order=stationcount&reverse=true` — popular tags
  - `GET /json/countrycodes` — country list
  - `POST /json/url/{stationuuid}` — click tracking (optional, good citizen call when playing)
- **Station fields returned:**
  - `stationuuid` — stable UUID
  - `name` — station name
  - `url` — direct stream URL (may redirect)
  - `url_resolved` — pre-resolved stream URL (prefer this)
  - `homepage` — website
  - `favicon` — logo URL (may be empty or broken)
  - `tags` — comma-separated tags
  - `country`, `countrycode`, `language`
  - `codec`, `bitrate`
  - `votes`, `clickcount`, `clicktrend` — popularity signals
- **Mapping to local Station model:** `name` → name, `url_resolved` (fallback `url`) → stream_url, tags → tags, `favicon` → art source.
- **`hidebroken=true`:** Always pass this. Filters stations with confirmed dead streams.

### AudioAddict PLS Auth Pattern

**Confidence: MEDIUM** — Based on training knowledge of public DI.fm documentation and community sources. No live verification.

- **Auth mechanism:** API key embedded in the PLS playlist URL, not in HTTP headers.
- **PLS URL format:** `https://listen.di.fm/premium_high/{channel}.pls?listen_key={api_key}`
- **Quality tiers:** `premium_high` / `premium_medium` / `premium_low` in the URL path. Some sources show `public3` (mp3 128k) as a free tier.
- **Channel list endpoint:** `https://api.audioaddict.com/v1/{network}/channels` where `{network}` is one of: `difm` (DI.fm), `zenradio`, `jazzradio`, `rockradio`.
- **Response fields:** `key` (channel slug), `name`, `description`, `asset_url` (logo), `channel_filters` (genre tags).
- **PLS content:** Standard PLS format — `File1=`, `Title1=`, `Length1=-1`. Parse with Python's `configparser` (PLS is INI-compatible).
- **Import flow:**
  1. User enters API key once (store in app config / keyring).
  2. Fetch channel list per network via channels endpoint.
  3. For each channel, construct PLS URL with quality + key.
  4. Fetch PLS, extract stream URL from `File1=`.
  5. Create Station: name from channel `name`, provider from network name, stream_url from PLS, art from `asset_url`, tags from `channel_filters`.
- **Caveat:** AudioAddict may have changed their API since training data. Key structure and PLS URL format have been stable for years but should be verified against a live account before phase implementation.

### YouTube Playlist Import (yt-dlp)

**Confidence: HIGH** — yt-dlp is already used in the app; playlist extraction is a core yt-dlp feature.

- **Command:** `yt-dlp --flat-playlist --dump-json "{playlist_url}"` — prints one JSON object per entry, no download.
- **Live stream detection:** Entry metadata includes `"is_live": true` for active live streams. Also check `"live_status": "is_live"` (more reliable in newer yt-dlp).
- **Fields per entry:** `id`, `title`, `url` (watch URL), `uploader`, `thumbnail`, `duration` (null for live), `is_live`, `live_status`.
- **Getting stream URL:** For each live entry, a second yt-dlp call is needed to resolve the actual stream URL: `yt-dlp -g "{watch_url}"`. Or: store the watch URL and resolve at play time (lazy resolution — already how single-station YT works in the app).
- **Recommendation:** Store watch URLs at import time, resolve at play time. Avoids N extra yt-dlp calls during import and handles URL expiry (YT stream URLs expire ~6h).
- **Async requirement:** `--flat-playlist` on a large playlist (100+ items) can take 10–30s. Must run in a daemon thread. Progress feedback is important.

---

## Feature Dependencies

```
FAVES-01 (star track)
    requires existing: ICY metadata display (already built in v1.2)
    requires existing: now-playing panel (already built)

FAVES-02 (DB storage)
    requires: FAVES-01 (star action)
    requires: new DB migration (favorites table)

FAVES-03 (favorites view)
    requires: FAVES-02 (data to show)
    requires: Gtk.Stack toggle in sidebar

FAVES-04 (remove favorite)
    requires: FAVES-03 (view to remove from)

DISC-01 (RB browse/search)
    requires: nothing existing — new panel/sheet
    async network I/O: yes (urllib or http.client)

DISC-02 (play RB station without saving)
    requires: DISC-01 (station selected from results)
    requires: transient "preview" player state (no DB write)
    NOTE: must not clobber currently-playing library station state

DISC-03 (save RB station)
    requires: DISC-01 (station selected from results)
    requires: existing station repo insert path

DISC-04 (AudioAddict import)
    requires: new import dialog
    requires: API key storage (config file or libsecret)
    requires: http fetch + PLS parsing (configparser)
    requires: existing station repo bulk insert

DISC-05 (quality selection)
    requires: DISC-04 flow (part of same dialog)

DISC-06 (YouTube playlist import)
    requires: existing yt-dlp integration
    requires: async thread + GLib.idle_add progress pattern (already established)
    NOTE: play-time URL resolution already works — reuse same path
```

### Dependency Notes

- **DISC-02 (preview without saving):** This is the trickiest dependency. The player currently assumes the playing station is always in the DB. A preview state requires either a nullable station reference or a transient Station object that never touches the DB. Needs design thought before implementation.
- **FAVES-03 and station list:** The toggle between Stations and Favorites shares the same sidebar panel. Use `Gtk.Stack` child swap — this is the established pattern in the app (already used for art slots and now-playing).
- **AudioAddict API key storage:** Simplest approach is the existing JSON config file at `~/.local/share/musicstreamer/config.json`. libsecret/keyring adds a dependency. Config file is fine for a personal app.

---

## MVP Definition for v1.3

### Launch With (all four feature groups are the scope)

- [ ] FAVES-01–04: Star ICY track, store with context, view in sidebar, remove — **essential, low risk**
- [ ] DISC-01–03: Radio-Browser.info browse/search/preview/save — **core discovery**
- [ ] DISC-04–05: AudioAddict import with quality selection — **medium complexity, well-defined API**
- [ ] DISC-06: YouTube playlist import — **reuses existing yt-dlp path, mostly plumbing**

### Phase Ordering Recommendation

Build in risk-ascending order:

1. **Favorites** (FAVES-01–04) — Zero new network I/O. Pure DB + UI. Lowest risk, fast win.
2. **Radio-Browser.info** (DISC-01–03) — New panel + network, but clean REST API. Medium risk.
3. **YouTube playlist import** (DISC-06) — Reuses existing yt-dlp pattern. Low-medium risk.
4. **AudioAddict import** (DISC-04–05) — External API with uncertain current state. Highest risk of API changes. Do last.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Favorite songs (all 4 sub-features) | HIGH | LOW | P1 |
| Radio-Browser.info browse + search | HIGH | MEDIUM | P1 |
| Radio-Browser.info play preview | HIGH | MEDIUM | P1 |
| Radio-Browser.info save to library | HIGH | LOW | P1 |
| Radio-Browser.info tag/country filter | MEDIUM | LOW | P2 |
| AudioAddict import (all 4 networks) | HIGH | MEDIUM | P1 |
| AudioAddict quality selection | MEDIUM | LOW | P1 |
| YouTube playlist import | HIGH | MEDIUM | P1 |
| YouTube playlist: progress feedback | MEDIUM | LOW | P2 |
| AudioAddict incremental import (dedup) | MEDIUM | MEDIUM | P2 |
| Favorites: iTunes metadata on star | LOW | LOW | P2 |

---

## Re-evaluation of v1.0 Anti-Feature

The v1.0 FEATURES.md listed "In-app station discovery / radio directory browser" as an
anti-feature. That was correct for v1.0–1.2 scope. For v1.3 it is explicitly in scope.

The anti-feature concern was valid: a full "browse mode" as the primary UI undermines the
curated library model. The correct resolution (and what v1.3 should build) is a **modal
or sidebar panel** for discovery — distinct from the station list — that feeds back into
the library rather than replacing it. Discovery is a population tool, not the primary UX.

---

## Sources

- Radio-Browser.info API: training knowledge of public REST API (`api.radio-browser.info`) — HIGH confidence (stable, widely documented)
- AudioAddict/DI.fm PLS auth pattern: training knowledge of public community documentation — MEDIUM confidence (verify against live account)
- yt-dlp flat-playlist behavior: training knowledge + existing app usage — HIGH confidence
- Shortwave (GNOME radio app) UX patterns: training knowledge — MEDIUM confidence
- User note: `.planning/notes/2026-03-22-favorite-songs-from-icy.md` — HIGH confidence (direct source)
- PROJECT.md v1.3 requirements: `.planning/PROJECT.md` — HIGH confidence (direct source)

---
*Feature research for: MusicStreamer v1.3 Discovery & Favorites*
*Researched: 2026-03-27*
