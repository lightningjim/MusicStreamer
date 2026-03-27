# Pitfalls Research

**Domain:** GTK4/Python internet radio app — Discovery & Favorites (v1.3)
**Researched:** 2026-03-27
**Confidence:** MEDIUM (codebase inspection + training knowledge; external search unavailable)

---

## Critical Pitfalls

---

### Pitfall 1: Radio-Browser.info — Hardcoded Server IP Instead of DNS Round-Robin

**What goes wrong:** Radio-Browser.info runs multiple community servers. The recommended access pattern is a DNS lookup against `all.api.radio-browser.info` which round-robins across available servers. Hardcoding a specific server IP or hostname (e.g. `de1.api.radio-browser.info`) means requests fail silently if that node goes down, with no fallback.

**Why it happens:** The DNS-based server-selection pattern is non-obvious. Developers hit the first working URL they find in examples and stop there.

**How to avoid:** At startup, resolve `all.api.radio-browser.info` via DNS (Python `socket.getaddrinfo`), pick one resolved IP at random, and use it for the session. On connection error, re-resolve and retry once. The API returns JSON from any server — no session affinity needed.

**Warning signs:** Requests work in development but fail intermittently in production; error logs show connection refused to a specific IP.

**Phase to address:** Radio-Browser discovery phase (DISC-01).

---

### Pitfall 2: Radio-Browser.info — Sync HTTP Call Blocks GTK Main Loop

**What goes wrong:** A search query to Radio-Browser.info is a network call (50–500ms). If issued synchronously on the GTK main loop thread (e.g., in a `Gtk.SearchEntry` `search-changed` handler), the UI freezes for every keystroke. This is the same class of bug as blocking yt-dlp, but more likely to slip through because `urllib.request.urlopen` looks synchronous and harmless.

**Why it happens:** The existing cover art and YouTube thumbnail fetches already use `threading.Thread` + `GLib.idle_add`. Developers sometimes forget to apply the same pattern to a new network call, especially for "quick" lookups.

**How to avoid:** All Radio-Browser.info calls must go through a daemon thread. Pattern: `threading.Thread(target=_worker, daemon=True).start()` where `_worker` does the HTTP call and calls `GLib.idle_add(self._apply_results, data)` to update the UI. Debounce search-changed signals by at least 300ms (use `GLib.timeout_add`) to avoid firing a thread per keystroke.

**Warning signs:** UI briefly freezes after typing in the discovery search box; spinning cursor visible between keystrokes.

**Phase to address:** Radio-Browser discovery phase (DISC-01).

---

### Pitfall 3: Radio-Browser.info — Unbounded Response Size

**What goes wrong:** The `/json/stations/search` endpoint with a broad query (e.g., `name=jazz`) can return thousands of stations. Deserializing and building GTK rows for 5,000+ results in one pass causes multi-second pauses and excessive memory use.

**Why it happens:** Developers test with specific queries ("DI.fm", "Soma.FM") that return small result sets. The general-case browse or a common genre search hits the unbounded path.

**How to avoid:** Always pass `limit=100` (or similar) as a query parameter. Display results as a flat scrollable list with a "Load more" button rather than auto-fetching all pages. The API supports `offset` + `limit` pagination.

**Warning signs:** Memory spikes sharply after a broad search; UI stalls while building the result list.

**Phase to address:** Radio-Browser discovery phase (DISC-01).

---

### Pitfall 4: AudioAddict — API Key Stored as Plaintext in Settings Table

**What goes wrong:** The API key gives access to premium streams. If stored carelessly (e.g., as a visible plaintext string in a settings dialog label, or logged to stdout during import), it leaks from the app. For a personal desktop app this is low severity, but the key is tied to the user's DI.fm premium account — leaking it gives others free premium access.

**Why it happens:** The natural implementation puts the key in the `settings` table (existing pattern) and displays it in a dialog for editing. This is fine for storage, but developers sometimes log it for debugging or display it fully unmasked in the UI.

**How to avoid:** Store in `settings` table (existing pattern is correct). Never log the key. In the UI, display as a password-style entry (`Gtk.PasswordEntry` or `entry.set_visibility(False)`). Mask in debug output with `key[:4] + "..."`.

**Warning signs:** Key appears in stdout during import; key visible in plain text in editor dialog.

**Phase to address:** AudioAddict import phase (DISC-04).

---

### Pitfall 5: AudioAddict — PLS URL Format Assumptions Break on Quality Tier Change

**What goes wrong:** AudioAddict streams use URLs like `https://prem2.di.fm/[channel]?[listen_key]` where the subdomain (`prem1`, `prem2`, `prem4`) encodes quality tier. The PLS file for a given quality tier contains the correct subdomain. If quality tier is changed post-import by substituting the subdomain string, the URL may be wrong — DI.fm changes server assignments without notice, and the substitution pattern `prem2 → prem4` is not stable.

**Why it happens:** Developers see the pattern, try to construct quality-variant URLs by string manipulation, and it works until DI.fm rotates their CDN.

**How to avoid:** Re-fetch the PLS file for the selected quality tier at import time rather than constructing variant URLs. The AudioAddict API returns separate PLS URLs per quality level — use the correct one directly. Never string-substitute subdomains.

**Warning signs:** Imported stations 404 after a quality tier switch; certain streams consistently fail while others at the same quality work.

**Phase to address:** AudioAddict import phase (DISC-04, DISC-05).

---

### Pitfall 6: YouTube Playlist Import — yt-dlp Subprocess Blocking GTK Main Loop

**What goes wrong:** `yt-dlp --flat-playlist` on a large YouTube playlist (50+ items) can take 10–30 seconds. If called via `subprocess.run(...)` or `subprocess.Popen(...); proc.wait()` on the main thread, the entire GTK window freezes for the duration. This is the same pattern the existing player already avoids for playback, but import is a one-off action that feels "safe" to do synchronously.

**Why it happens:** Import is triggered by a button click (not a continuous event), so it doesn't feel like it needs debouncing. The subprocess is short enough to feel okay in testing with a 5-item test playlist.

**How to avoid:** Always run `yt-dlp` import in a daemon thread. Pattern: `threading.Thread(target=_import_worker, daemon=True).start()`. Show a spinner (`Gtk.Spinner`) in the import button while running. Apply results via `GLib.idle_add`. The existing YouTube thumbnail fetch (`daemon thread + GLib.idle_add`) in the station editor is the correct template.

**Warning signs:** Window becomes unresponsive after clicking "Import Playlist"; can't resize or scroll during import.

**Phase to address:** YouTube playlist import phase (DISC-06).

---

### Pitfall 7: YouTube Playlist Import — Non-Live Streams Imported as Stations

**What goes wrong:** A YouTube playlist may contain a mix of live streams, past live stream recordings (which become regular videos), and uploaded music videos. Importing everything creates broken stations — regular videos are not streams and GStreamer/mpv can't play them as radio.

**Why it happens:** `yt-dlp --flat-playlist` returns all items without discriminating by live status. The `is_live` flag is only reliably set when fetching full metadata per-video, not in the flat playlist pass.

**How to avoid:** During playlist parsing, check `entry.get("is_live")` or `entry.get("live_status") == "is_live"`. Skip any entry where `is_live` is `False` or `None`. If yt-dlp flat playlist doesn't return `is_live` reliably, do a second lightweight fetch (`--no-download --print is_live`) for each candidate. Alternatively, only import items matching a channel allowlist (e.g., known live-stream channels like Lofi Girl).

Show a count: "Imported 3 live streams, skipped 12 non-live videos."

**Warning signs:** Imported stations fail to play immediately; `mpv` exits with error code; no audio after clicking a playlist-imported station.

**Phase to address:** YouTube playlist import phase (DISC-06).

---

### Pitfall 8: Favorites — Duplicate Detection Missing for Identical ICY Titles

**What goes wrong:** ICY TAG messages fire continuously and may repeat. If the star button fires `INSERT INTO favorites` without a uniqueness check, the same `(station_id, track_title)` pair accumulates duplicate rows. The favorites view then shows the same song multiple times.

**Why it happens:** The favorites DB write is triggered by a button click, which feels single-fire. But if the user clicks twice, or if the UI allows starring while the same ICY title is playing a second session, duplicates accumulate.

**How to avoid:** Use `INSERT OR IGNORE` with a `UNIQUE(station_id, title)` constraint on the `favorites` table. The constraint enforces deduplication at the DB level regardless of how many times the insert is called. Add the constraint in `db_init` via the `ALTER TABLE ... ADD UNIQUE` try/except migration pattern already used for `icy_disabled` and `last_played_at`.

**Warning signs:** Favorites view shows the same song 2–3x after repeated playback sessions; count badge shows inflated number.

**Phase to address:** Favorites DB + star action phase (FAVES-01, FAVES-02).

---

### Pitfall 9: Favorites — ICY Title Junk Stored as Favorites

**What goes wrong:** Some ICY streams emit junk titles during ads, silence, or buffer events: `"advertisement"`, `"commercial break"`, empty string, `"StreamTitle=;"`. If the star button is active during these moments (e.g., auto-starring recent tracks), junk gets saved to favorites.

**Why it happens:** The junk detection logic already exists in `cover_art.py` (`is_junk_title`, `JUNK_TITLES` frozenset) but is only applied to cover art lookups. Favorites writes don't go through this path.

**How to avoid:** Import and call `is_junk_title(current_icy_title)` before allowing the star action. Disable the star button (set insensitive) whenever the current ICY title is junk or empty. The `JUNK_TITLES` frozenset and `is_junk_title()` function in `cover_art.py` should be moved to a shared utility (e.g., `filter_utils.py` or a new `icy_utils.py`) so favorites and cover art both use the same logic.

**Warning signs:** Favorites view contains entries like `"advertisement"` or blank titles; star button can be clicked during ads.

**Phase to address:** Favorites DB + star action phase (FAVES-01, FAVES-02).

---

### Pitfall 10: DB Migration — Missing `favorites` Table on Existing Installs

**What goes wrong:** The `favorites` table doesn't exist on any current install. If v1.3 launches and the table is missing, any code path that queries `favorites` raises `sqlite3.OperationalError: no such table`. This crashes or silently swallows the error depending on error handling.

**Why it happens:** The `db_init` function uses `CREATE TABLE IF NOT EXISTS` for tables that existed at v1.0. New tables added in v1.3 must also use this pattern. The existing `icy_disabled` and `last_played_at` migrations (try/except `ALTER TABLE`) are the correct model for new columns, but an entirely new table needs `CREATE TABLE IF NOT EXISTS` in the main `executescript` or a separate guarded block.

**How to avoid:** Add `CREATE TABLE IF NOT EXISTS favorites (...)` inside `db_init`'s `executescript` block — not as an `ALTER TABLE`. This is idempotent and runs on every startup. Add it alongside the existing station/provider/settings table creation.

**Warning signs:** `sqlite3.OperationalError: no such table: favorites` on first launch after update; favorites view crashes immediately on open.

**Phase to address:** Favorites DB phase (FAVES-02) — must be the first favorites work done.

---

### Pitfall 11: Radio-Browser.info — Click Count Voting Fired Accidentally

**What goes wrong:** Radio-Browser.info's API has a `/json/url/{stationuuid}` endpoint that both returns the stream URL AND records a click count vote. If the app calls this endpoint during search result display (e.g., to resolve final stream URLs for all results), it artificially inflates click counts for stations the user never actually played.

**Why it happens:** The endpoint looks like a simple URL resolver. The side-effect (vote recording) is a secondary concern documented in the API but easy to miss.

**How to avoid:** Only call `/json/url/{stationuuid}` (the click-counting endpoint) when the user actually plays or saves the station. For display in the browse list, use the `url` field already present in the `/json/stations/search` response — no separate URL resolution needed.

**Warning signs:** Station click counts in Radio-Browser.info inflate for stations never played; network logs show `/json/url/` calls during search.

**Phase to address:** Radio-Browser discovery phase (DISC-01, DISC-02).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode quality tier subdomains for AudioAddict | Avoid PLS re-fetch on quality change | Breaks when DI.fm rotates CDN | Never |
| Skip `is_live` check in YouTube playlist import | Simpler import code | Broken stations in library | Never |
| Synchronous yt-dlp subprocess for playlist import | Simpler threading | Frozen UI for large playlists | Never |
| `INSERT` without uniqueness constraint on favorites | Faster initial implementation | Duplicate favorites, inflated counts | Never |
| Move `is_junk_title` inline into favorites code | Avoid refactor | Divergent junk detection logic between favorites and cover art | Never |
| Fetch full Radio-Browser.info results without `limit` | No pagination UI needed | Multi-second freeze on broad queries | Never — always cap at 100–200 |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Radio-Browser.info | Hardcode `de1.api.radio-browser.info` | DNS resolve `all.api.radio-browser.info`, pick random IP |
| Radio-Browser.info | Call `/json/url/{uuid}` during browse | Only call on play/save; use `url` field for display |
| Radio-Browser.info | No result limit on search | Always pass `limit=100` + pagination |
| AudioAddict | Construct quality-variant URL by subdomain substitution | Re-fetch PLS for each quality tier |
| AudioAddict | Log or display API key in full | Mask in UI (`set_visibility(False)`), truncate in logs |
| YouTube import | `subprocess.run` on main thread | Daemon thread + `GLib.idle_add` for results |
| YouTube import | Import all playlist items | Filter to `is_live == True` only |
| Favorites | `INSERT` without uniqueness | `INSERT OR IGNORE` + `UNIQUE(station_id, title)` constraint |
| Favorites | Allow starring junk ICY titles | Gate star action on `not is_junk_title(current_title)` |
| Favorites table | Missing table on existing install | `CREATE TABLE IF NOT EXISTS` in `db_init` executescript |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Unbounded Radio-Browser search response | Multi-second freeze after broad search, memory spike | `limit=100` query param, pagination | Any query returning >200 stations |
| Building GTK rows for all search results before displaying | Visible stall before results appear | Build rows incrementally or in batches via `GLib.idle_add` chunks | >50 results |
| yt-dlp `--flat-playlist` on 100+ item playlist without threading | Full window freeze 10–30 seconds | Daemon thread, progress indication | Any playlist >10 items |
| No debounce on Radio-Browser search-changed | Thread spawned per keystroke, responses arrive out of order | 300ms `GLib.timeout_add` debounce, cancel previous thread by token | Typing fast (>3 chars/sec) |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| AudioAddict API key logged to stdout during import | Key exposed in terminal/journal | Never log key; mask as `key[:4] + "..."` in debug |
| AudioAddict API key visible in plaintext UI entry | Key visible to shoulder-surfers, screenshots | Use `Gtk.PasswordEntry` or `entry.set_visibility(False)` |
| Importing arbitrary YouTube playlist URLs without validation | yt-dlp could process malformed URLs causing unexpected subprocess behavior | Validate URL scheme (`https://`) and domain (`youtube.com`, `youtu.be`) before passing to yt-dlp |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No feedback during playlist import (can take 30s) | User thinks app is frozen, clicks again, double-import | Show spinner + "Importing…" status, disable button during import |
| No feedback during Radio-Browser search (async) | User types, nothing happens, types again | Show spinner in search field while request is in flight |
| Favorites view replaces station list with no navigation hint | User doesn't know how to get back to stations | Toggle button clearly labeled "Stations / Favorites" with active state |
| Star button enabled when ICY title is junk/ad | User stars an ad accidentally | Disable star button when `is_junk_title(current_title)` is True |
| Importing AudioAddict overwrites existing stations of the same name | User loses custom edits (art, tags) | Check by name+provider before insert; skip or confirm on collision |
| Radio-Browser station saved without provider assignment | Station appears ungrouped in station list | Auto-assign provider from Radio-Browser `country`/`tags` or prompt user |

---

## "Looks Done But Isn't" Checklist

- [ ] **Radio-Browser discovery:** Results are shown — but is the click-count endpoint only called on play/save, not on display?
- [ ] **Radio-Browser discovery:** Search works — but is there a result limit preventing unbounded fetches?
- [ ] **Radio-Browser server selection:** Requests succeed — but is DNS round-robin used, not a hardcoded server?
- [ ] **AudioAddict import:** Stations import — but is the API key masked in the UI and never logged?
- [ ] **AudioAddict import:** Quality tiers work — but is each tier using its own PLS-resolved URL, not a subdomain substitution?
- [ ] **YouTube import:** Stations appear after import — but are non-live videos filtered out?
- [ ] **YouTube import:** Import completes — but does the UI stay responsive during it (no main-thread block)?
- [ ] **Favorites:** Stars save — but is there a `UNIQUE` constraint preventing duplicates?
- [ ] **Favorites:** Star action works — but is the star button disabled for junk/ad ICY titles?
- [ ] **Favorites:** View shows correct data — but does it work on a fresh install (table migration in `db_init`)?

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Hardcoded Radio-Browser server | LOW | Change constant, re-deploy |
| Click-count endpoint called during browse | LOW | Change call site to play/save only |
| Duplicate favorites from missing UNIQUE constraint | MEDIUM | Add constraint + `DELETE` duplicates in migration |
| Junk titles in favorites | LOW | Add `is_junk_title` gate + one-time cleanup query |
| Missing favorites table on existing install | LOW | Add `CREATE TABLE IF NOT EXISTS` to `db_init`, re-run |
| Non-live videos imported as stations | MEDIUM | Add `is_live` filter + cleanup pass to delete broken stations |
| AudioAddict quality URLs from subdomain substitution | LOW | Re-import with PLS fetch per quality tier |
| Blocking yt-dlp import on main thread | LOW | Wrap in daemon thread |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Radio-Browser DNS round-robin (P1) | DISC-01 Radio-Browser browse | DNS resolve confirmed in code; no hardcoded hostname |
| Radio-Browser sync HTTP on main thread (P2) | DISC-01 Radio-Browser browse | UI stays responsive while search is in flight |
| Radio-Browser unbounded response (P3) | DISC-01 Radio-Browser browse | `limit=` param present in all search calls |
| AudioAddict API key security (P4) | DISC-04 AudioAddict import | Key masked in UI; not present in stdout during import |
| AudioAddict PLS URL per quality tier (P5) | DISC-05 AudioAddict quality | PLS re-fetched per tier; no subdomain substitution in code |
| YouTube import blocking main loop (P6) | DISC-06 YouTube playlist import | Window remains responsive during 20+ item import |
| YouTube non-live filter (P7) | DISC-06 YouTube playlist import | Only `is_live=True` items imported; count shown to user |
| Favorites duplicate detection (P8) | FAVES-02 Favorites DB schema | `UNIQUE(station_id, title)` constraint in table DDL |
| Favorites junk title guard (P9) | FAVES-01 Star action | Star button insensitive when `is_junk_title` is True |
| Favorites DB migration (P10) | FAVES-02 Favorites DB schema — first | `CREATE TABLE IF NOT EXISTS favorites` in `db_init`; tested on existing DB |
| Radio-Browser click-count side effect (P11) | DISC-02 Play without import | `/json/url/` only called at play/save time |

---

## Sources

- Codebase inspection: `musicstreamer/cover_art.py`, `musicstreamer/repo.py`, `musicstreamer/player.py` (2026-03-27)
- Existing PITFALLS.md v1.2 research (2026-03-18) — GTK4/GStreamer pitfalls
- Radio-Browser.info API design: training knowledge — MEDIUM confidence (API is stable and community-documented; DNS round-robin is the officially recommended approach)
- AudioAddict/DI.fm PLS URL structure: training knowledge — MEDIUM confidence (URL pattern observed from public PLS files; subdomain rotation risk is inferred from CDN practices)
- yt-dlp `is_live` field behavior: training knowledge — MEDIUM confidence (flat playlist `is_live` flag documented in yt-dlp output templates; validate empirically against a real mixed playlist)
- SQLite `INSERT OR IGNORE` + `UNIQUE` constraint pattern: HIGH confidence (standard SQLite behavior)
- GLib `idle_add` / daemon thread pattern: HIGH confidence (established GTK cross-thread pattern; already used in this codebase for cover art and YT thumbnails)

---
*Pitfalls research for: GTK4/Python internet radio — v1.3 Discovery & Favorites*
*Researched: 2026-03-27*
