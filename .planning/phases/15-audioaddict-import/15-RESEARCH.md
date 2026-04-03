# Phase 15: AudioAddict Import - Research

**Researched:** 2026-04-03
**Domain:** AudioAddict network API + GTK4/libadwaita dialog refactor
**Confidence:** MEDIUM (API verified against multiple third-party implementations; no official docs available)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** The existing "Import" button in the header bar is expanded into a **unified Import dialog** with two tabs: "YouTube Playlist" and "AudioAddict". Both sources share one dialog — the `ImportDialog` class is refactored to support tab switching rather than creating a second dialog class.
- **D-02:** API key is **persisted in SQLite** using the existing app settings/config pattern (same mechanism as volume persistence). The AudioAddict tab pre-fills the key on open if previously saved. User only types it once.
- **D-03:** Import **all supported networks at once** — no network selection step. User sees a single "Import" action; if they want to remove channels from a particular network, they delete stations after import. Keeps the flow minimal.
- **D-04:** Quality is selected via an **`Adw.ToggleGroup`** with three buttons: Hi | Med | Low. Matches the existing Stations/Favorites toggle pattern in the app. Default: Hi.
- **D-05:** Import runs with real-time progress feedback matching Phase 14 pattern: spinner + label updating as each station is processed ("3 imported, 1 skipped"). Duplicate stations (URL match) are counted in "skipped" — quiet skip, no error shown.

### Claude's Discretion
- Exact AudioAddict API endpoint, network identifiers, and PLS URL construction — researcher must verify against the live API before any code is written
- How to handle invalid/expired API key (inline error label in the dialog)
- Whether quality setting persists between sessions (reasonable to save alongside the API key)
- Dialog widget hierarchy and sizing within the new tabbed structure
- How the existing `ImportDialog` is refactored to accommodate the tab view

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IMPORT-02 | User can enter an AudioAddict API key to import channels from all AudioAddict networks, skipping stations already in library by URL | API endpoint verified: `https://listen.{domain}/{quality_tier}` returns JSON channel list; URL match via `repo.station_exists_by_url` already implemented |
| IMPORT-03 | User can select stream quality (hi / med / low) before importing AudioAddict channels | Quality tiers confirmed: `premium_high` (320k MP3), `premium` (128k AAC), `premium_medium` (64k AAC); map directly to Hi/Med/Low toggle buttons |
</phase_requirements>

---

## Summary

The AudioAddict API has no official public documentation — it disappeared circa 2014 — but is thoroughly reverse-engineered across multiple maintained third-party projects (Plex plugins, Mopidy extensions, terminal players). The API pattern is stable and consistent across all sources.

The critical clarification: what AudioAddict calls the "Listen Key" in their user settings UI is the same credential used as the `listen_key` query parameter in stream URLs. Users find it at `https://www.di.fm/settings` under hardware player settings. It is NOT an API key in the OAuth sense — it is a static opaque token tied to the premium account.

The import backend (`aa_import.py`) has two phases: (1) fetch the channels JSON list for each network using the quality tier URL, (2) construct the stream URL for each channel and call `repo.insert_station`. No authentication call is needed — the listen key is embedded directly in channel list requests.

**Primary recommendation:** Fetch `https://listen.{domain}/{quality_tier}.json?{listen_key}` for each network, parse the JSON array, construct stream URLs as `https://listen.{domain}/{quality_tier}/{channel_key}.pls?{listen_key}`, then insert via `repo.insert_station`.

---

## AudioAddict API — Critical Research Flag Resolution

This section directly answers the six questions from STATE.md.

### 1. Correct API Base URL

Two separate URL bases are used:

| Use | URL |
|-----|-----|
| Channel list (JSON) | `https://listen.{domain}/{quality_tier}` (returns JSON array) |
| Individual stream | `https://listen.{domain}/{quality_tier}/{channel_key}.pls?{listen_key}` |
| Auth (not needed for this phase) | `https://api.audioaddict.com/v1/{network}/members/authenticate` |

The `api.audioaddict.com` base is used for user authentication (username/password → listen_key). Since users paste their listen key directly, no auth call is needed.

**Confidence: MEDIUM** — Consistent across 5+ independent implementations. The `.json` suffix variant appears in some sources as `https://listen.{domain}/{quality_tier}.json`; treat the no-extension form as canonical since some implementations use it without the suffix and rely on JSON content-type.

### 2. Network Slug List

| Slug | Domain | Service |
|------|--------|---------|
| `di` | `listen.di.fm` | DI.fm (Digitally Imported) |
| `radiotunes` | `listen.radiotunes.com` | RadioTunes |
| `jazzradio` | `listen.jazzradio.com` | JazzRadio |
| `rockradio` | `listen.rockradio.com` | RockRadio |
| `classicalradio` | `listen.classicalradio.com` | ClassicalRadio |
| `zenradio` | `listen.zenradio.com` | ZenRadio |

**Confidence: HIGH** — All six slugs appear consistently across phrawzty/AudioAddict.bundle, di-tui, and geertjohan/tune.

Note: The `api.audioaddict.com` calls use the slug (e.g. `/v1/di/`); the listen URLs use the domain. Both are needed.

### 3. How the API Key (Listen Key) is Passed

The listen key is appended as a **bare query string** (no key= prefix in some sources, `listen_key=` in others):

```
# Pattern A (most common — PLS format):
https://listen.di.fm/premium_high/ambient.pls?listen_key=abc123xyz

# Pattern B (seen in some channel list endpoints):
https://listen.di.fm/premium_high?abc123xyz
```

**Recommendation:** Use `listen_key=` named parameter for clarity and future compatibility. Multiple sources (danielmiessler.com, phrawzty bundle) confirm this form works.

**Confidence: MEDIUM** — The bare form (`?abc123xyz`) and named form (`?listen_key=abc123xyz`) are both documented. Use named form.

### 4. Stream URL Format for Each Quality Tier

| Toggle | Internal Key | Domain Path | Format | Bitrate |
|--------|-------------|------------|--------|---------|
| Hi | `premium_high` | `/{domain}/premium_high/{channel_key}.pls?listen_key={key}` | MP3 | 320 kbps |
| Med | `premium` | `/{domain}/premium/{channel_key}.pls?listen_key={key}` | AAC | 128 kbps |
| Low | `premium_medium` | `/{domain}/premium_medium/{channel_key}.pls?listen_key={key}` | AAC | 64 kbps |

Example (Hi, DI.fm, ambient channel):
```
https://listen.di.fm/premium_high/ambient.pls?listen_key=abc123
```

**Confidence: HIGH** — Three-tier mapping confirmed in phrawzty/AudioAddict.bundle Python source and GeertJohan/tune Go library independently.

### 5. Does the Channels Endpoint Require Authentication?

**Yes — the listen key is required.** Free streams exist but return a looping audio message, not music. The listen key must be present in the channels list request as well.

Channel list URL (returns JSON array of channel objects):
```
https://listen.di.fm/premium_high?listen_key=abc123
```

**Confidence: MEDIUM** — Inferred from multiple sources stating "without listen key you only get free streams which no longer have music." The list endpoint itself may be public but channels within it are only usable with the key.

### 6. PLS Format and Listen Key Embedding

The `.pls` URL is a playlist redirect. GStreamer plays it directly — no PLS parsing needed in MusicStreamer. Store the full PLS URL (with `?listen_key=...`) as the station URL in SQLite. GStreamer handles PLS playlists natively.

```
# Store this as station.url:
https://listen.di.fm/premium_high/ambient.pls?listen_key=abc123
```

The listen key is embedded in the stored URL. This means changing quality requires re-importing (or editing stations individually). This is acceptable per D-03.

**Confidence: HIGH** — GStreamer PLS handling is established in existing app; same pattern.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `urllib.request` / `urllib.error` | stdlib | Fetch channels JSON from AudioAddict | No external dep; sufficient for simple GET |
| `json` | stdlib | Parse channel list response | Direct JSON array |
| `threading` | stdlib | Background import worker | Established pattern from Phase 14 |
| `GLib.idle_add` | gi.repository | Thread-safe UI callbacks | Established pattern in app |
| `Gtk.Notebook` | gi.repository.Gtk | Two-tab layout in ImportDialog | Per UI-SPEC D-01 |
| `Adw.ToggleGroup` | gi.repository.Adw | Hi/Med/Low quality selector | Per D-04; already used in app |

### No New Dependencies
No pip packages needed. `urllib.request` is sufficient for the simple authenticated GET to the AudioAddict JSON endpoint. Avoids adding `requests` as a dependency.

### Installation
```bash
# No new packages — stdlib only
```

---

## Architecture Patterns

### New File: `musicstreamer/aa_import.py`

Mirrors `yt_import.py` exactly in structure.

```python
# Public API mirrors yt_import.py
def fetch_channels(listen_key: str, quality: str) -> list[dict]:
    """Fetch all channels across all 6 networks.
    Returns list of {"title", "url", "provider"} dicts.
    Raises ValueError on 401/403 (invalid key).
    Raises RuntimeError on network failure.
    """

def import_stations(channels: list[dict], repo, on_progress=None) -> tuple[int, int]:
    """Same signature as yt_import.import_stations.
    Uses repo.station_exists_by_url + repo.insert_station.
    """
```

### Network Table (in aa_import.py)

```python
NETWORKS = [
    {"slug": "di",            "domain": "listen.di.fm",             "name": "DI.fm"},
    {"slug": "radiotunes",    "domain": "listen.radiotunes.com",     "name": "RadioTunes"},
    {"slug": "jazzradio",     "domain": "listen.jazzradio.com",      "name": "JazzRadio"},
    {"slug": "rockradio",     "domain": "listen.rockradio.com",      "name": "RockRadio"},
    {"slug": "classicalradio","domain": "listen.classicalradio.com", "name": "ClassicalRadio"},
    {"slug": "zenradio",      "domain": "listen.zenradio.com",       "name": "ZenRadio"},
]

QUALITY_TIERS = {
    "hi":  "premium_high",
    "med": "premium",
    "low": "premium_medium",
}
```

### Channel Fetch Logic

```python
import urllib.request
import urllib.error
import json

def fetch_channels(listen_key: str, quality: str) -> list[dict]:
    tier = QUALITY_TIERS[quality]  # "premium_high" | "premium" | "premium_medium"
    channels = []
    for net in NETWORKS:
        url = f"https://{net['domain']}/{tier}?listen_key={listen_key}"
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise ValueError("invalid_key")
            raise RuntimeError(f"HTTP {e.code} for {net['domain']}")
        except Exception as e:
            raise RuntimeError(str(e))
        for ch in data:
            stream_url = f"https://{net['domain']}/{tier}/{ch['key']}.pls?listen_key={listen_key}"
            channels.append({
                "title": ch["name"],
                "url": stream_url,
                "provider": net["name"],
            })
    return channels
```

### ImportDialog Refactor

The existing `ImportDialog` class is refactored by wrapping the existing content in a `Gtk.Notebook` page. The class stays as `ImportDialog`; `main_window._open_import` needs no change.

```python
# Refactor pattern:
# 1. Build Gtk.Notebook
# 2. Move existing YouTube content box into Tab 0: "YouTube Playlist"
# 3. Build new AudioAddict content box as Tab 1: "AudioAddict"
# 4. Connect Notebook page-switch signal to remember last tab
```

Settings keys added to SQLite:
```python
repo.get_setting("audioaddict_listen_key", "")
repo.get_setting("audioaddict_quality", "hi")
repo.set_setting("audioaddict_listen_key", key)
repo.set_setting("audioaddict_quality", quality)
```

### Anti-Patterns to Avoid

- **Don't store listen_key in memory only** — persist to SQLite on every change, not just on successful import.
- **Don't construct channel name as `{network} - {channel}`** — provider is the network; name is the channel title; `repo.insert_station` handles the provider grouping automatically.
- **Don't fetch all networks in parallel threads** — sequential fetch is simpler, fast enough (~6 networks × ~200ms = ~1.2s), and avoids threading complexity in the worker.
- **Don't import error handling in the dialog** — raise from `aa_import.fetch_channels`, catch in `_import_worker`, dispatch to UI via `GLib.idle_add`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PLS playlist parsing | Custom PLS parser | Store PLS URL as-is; GStreamer handles PLS natively | GStreamer already plays PLS URLs in existing stations |
| HTTP with auth headers | Custom auth layer | `urllib.request` + `?listen_key=` query param | AudioAddict uses query param, not headers |
| Quality bitrate negotiation | Bitrate detection logic | Hardcode 3 tier keys | Tiers are fixed per AudioAddict API |
| Provider grouping | Custom provider field | Pass network name as `provider_name` to `repo.insert_station` | `ensure_provider` handles INSERT OR IGNORE; stations group by provider in list |

---

## Common Pitfalls

### Pitfall 1: Invalid Key Returns 401 vs. Empty Array
**What goes wrong:** An expired or wrong listen_key may return a 401 HTTP error on some networks but an empty array on others. Code that only checks `len(data) == 0` will silently "succeed" with 0 imports for a bad key.
**Why it happens:** AudioAddict network behavior is inconsistent across the 6 domains.
**How to avoid:** Treat both 401/403 AND empty array from ALL networks as potential key errors. Show inline error if zero channels are returned across all networks.
**Warning signs:** "0 imported, 0 skipped" with no error — investigate whether key is valid.

### Pitfall 2: Channel `key` Field vs. `name` Field
**What goes wrong:** Using `ch["name"]` as the URL slug instead of `ch["key"]`. Names may have spaces/caps; keys are lowercase slugs.
**Why it happens:** Channel objects have both fields; `name` is display text, `key` is the URL token.
**How to avoid:** Always use `ch["key"]` for URL construction; `ch["name"]` for display name.

### Pitfall 3: SQLite Thread Safety in Import Worker
**What goes wrong:** Passing `self.repo` (main thread connection) into the background import worker causes `ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.
**Why it happens:** Phase 14 already encountered this. See `STATE.md` decision note.
**How to avoid:** Open a thread-local connection in `_aa_import_worker` using `db_connect()`, exactly as Phase 14 does.

### Pitfall 4: Notebook Tab State on Dialog Re-Open
**What goes wrong:** Dialog creates a new instance each time `_open_import` is called — per-instance state is lost. The "last used tab" won't persist.
**Why it happens:** `ImportDialog` is instantiated fresh on each open.
**How to avoid:** Store last tab index in a module-level or class-level variable, not an instance variable.

### Pitfall 5: `Adw.ToggleGroup` Initial Active State
**What goes wrong:** `Adw.ToggleGroup` requires setting the active button after all buttons are appended; setting it before append is ignored.
**How to avoid:** Call `toggle_group.set_active_name("Hi")` after all three buttons are appended.

### Pitfall 6: ZenRadio Network Availability
**What goes wrong:** ZenRadio may have lower channel counts or may redirect — it's the least-documented network.
**How to avoid:** On per-network HTTP errors that are not 401/403, log but continue to next network. Don't abort all 6 networks if one fails.

---

## Code Examples

### aa_import.fetch_channels pattern
```python
# Source: phrawzty/AudioAddict.bundle + danielmiessler.com stream URL docs
import urllib.request, urllib.error, json

QUALITY_TIERS = {"hi": "premium_high", "med": "premium", "low": "premium_medium"}
NETWORKS = [
    {"domain": "listen.di.fm",             "name": "DI.fm"},
    {"domain": "listen.radiotunes.com",     "name": "RadioTunes"},
    {"domain": "listen.jazzradio.com",      "name": "JazzRadio"},
    {"domain": "listen.rockradio.com",      "name": "RockRadio"},
    {"domain": "listen.classicalradio.com", "name": "ClassicalRadio"},
    {"domain": "listen.zenradio.com",       "name": "ZenRadio"},
]

def fetch_channels(listen_key: str, quality: str) -> list[dict]:
    tier = QUALITY_TIERS[quality]
    results = []
    for net in NETWORKS:
        url = f"https://{net['domain']}/{tier}?listen_key={listen_key}"
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise ValueError("invalid_key")
            continue  # skip this network on other HTTP errors
        for ch in data:
            stream_url = f"https://{net['domain']}/{tier}/{ch['key']}.pls?listen_key={listen_key}"
            results.append({"title": ch["name"], "url": stream_url, "provider": net["name"]})
    if not results:
        raise ValueError("no_channels")
    return results
```

### Settings persistence pattern (existing repo.py)
```python
# Read on dialog open:
key = repo.get_setting("audioaddict_listen_key", "")
quality = repo.get_setting("audioaddict_quality", "hi")

# Write when user changes key entry or quality toggle:
repo.set_setting("audioaddict_listen_key", entry.get_text().strip())
repo.set_setting("audioaddict_quality", active_quality)
```

### Thread-local SQLite in import worker (Phase 14 pattern)
```python
# Source: import_dialog.py _import_worker (Phase 14)
def _aa_import_worker(self, channels: list[dict]):
    def on_progress(imp, skip):
        GLib.idle_add(self._update_aa_progress, imp, skip)
    con = db_connect()
    try:
        thread_repo = Repo(con)
        imported, skipped = aa_import.import_stations(channels, thread_repo, on_progress=on_progress)
    finally:
        con.close()
    GLib.idle_add(self._on_aa_import_done, imported, skipped)
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `urllib.request` | AudioAddict API fetch | ✓ | stdlib | — |
| `json` | Channel list parsing | ✓ | stdlib | — |
| `pytest` | Test suite | ✓ | 9.0.2 | — |
| Internet / AudioAddict endpoints | Live fetch | assumed ✓ | — | Offline: mock in tests |

No new packages required.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none — tests run from project root |
| Quick run command | `python3 -m pytest tests/test_aa_import.py -x` |
| Full suite command | `python3 -m pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IMPORT-02 | fetch_channels returns expected list | unit | `pytest tests/test_aa_import.py::test_fetch_channels_returns_list -x` | ❌ Wave 0 |
| IMPORT-02 | fetch_channels raises ValueError on 401 | unit | `pytest tests/test_aa_import.py::test_fetch_channels_invalid_key -x` | ❌ Wave 0 |
| IMPORT-02 | import_stations skips URL duplicates | unit | `pytest tests/test_aa_import.py::test_import_skips_duplicate -x` | ❌ Wave 0 |
| IMPORT-02 | import_stations inserts new station | unit | `pytest tests/test_aa_import.py::test_import_creates_station -x` | ❌ Wave 0 |
| IMPORT-03 | quality "hi" maps to "premium_high" in URL | unit | `pytest tests/test_aa_import.py::test_quality_tier_mapping -x` | ❌ Wave 0 |
| IMPORT-03 | quality "med" maps to "premium" in URL | unit | `pytest tests/test_aa_import.py::test_quality_tier_mapping -x` | ❌ Wave 0 |
| IMPORT-03 | quality "low" maps to "premium_medium" in URL | unit | `pytest tests/test_aa_import.py::test_quality_tier_mapping -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_aa_import.py -x`
- **Per wave merge:** `python3 -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_aa_import.py` — covers all IMPORT-02 and IMPORT-03 backend requirements
  - Mock `urllib.request.urlopen` to return fixture JSON
  - Use same mock-repo pattern as `test_import_dialog.py`

*(Existing test infrastructure (pytest, conftest-less, MagicMock pattern) is sufficient — no new fixtures needed)*

---

## Open Questions

1. **Does `listen.{domain}/{tier}` return pure JSON or does it vary by Accept header?**
   - What we know: Multiple sources confirm JSON is returned by this endpoint
   - What's unclear: Whether Content-Type must be set, or if a `.json` suffix is needed
   - Recommendation: Try without suffix first; add `.json` suffix as fallback if first attempt returns non-JSON

2. **ZenRadio network status**
   - What we know: All major implementations list it as a valid network
   - What's unclear: Whether ZenRadio is still active in 2026 or has been shut down
   - Recommendation: Include it in NETWORKS list; handle per-network failure gracefully (continue to next network)

3. **What the user sees vs. what we call it**
   - What we know: DI.fm settings page shows "Listen Key" not "API Key"; the CONTEXT.md uses "API key" terminology
   - Recommendation: In the dialog, label the entry "Listen Key" or "API Key" — either works; match the CONTEXT.md phrasing ("API key") for consistency with the requirements spec. Note in help text that it's found at di.fm/settings.

---

## Sources

### Primary (HIGH confidence)
- [phrawzty/AudioAddict.bundle — audioaddict.py](https://github.com/phrawzty/AudioAddict.bundle/blob/main/Contents/Code/audioaddict.py) — Python implementation; network list, quality tiers, batch update endpoint, listen_key embedding
- [acaloiaro/di-tui](https://github.com/acaloiaro/di-tui) — Go implementation; confirm network slugs, stream URL format, listen_key as query param
- [geertjohan/tune/api — pkg.go.dev](https://pkg.go.dev/github.com/geertjohan/tune/api) — Go API structs; Account.ListenKey, Network.Key, quality encoding, Streamlist keys

### Secondary (MEDIUM confidence)
- [danielmiessler.com — Digitally Imported High Quality URLs](https://danielmiessler.com/blog/digitally-imported-high-quality-station-urls) — Stream URL format `listen.di.fm/premium_high/{channel}.pls?listen_key=` confirmed
- [hackruu gist — di.fm playlist generator](https://gist.github.com/hackruu/6fc318e677b899f99751) — listen_key extraction from authenticate endpoint; PLS format confirmation
- [nilicule/mopidy-audioaddict commit](https://github.com/nilicule/mopidy-audioaddict/commit/de63361172b57ba777f1c907c471346104645d1b) — quality tier keys `premium_high / premium / premium_medium / premium_low`; network list

### Tertiary (LOW confidence — not independently verified with live account)
- Stream URL construction for `zenradio` — all other 5 domains verified by multiple sources; zenradio included in network lists but fewer specific stream URL examples found

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib only, no new deps
- API endpoint + network list: MEDIUM — reverse-engineered from multiple implementations; no official docs exist; live account verification still recommended before final code
- Architecture patterns: HIGH — directly mirrors Phase 14 patterns already in codebase
- Pitfalls: HIGH — most derived from existing codebase patterns and Phase 14 decisions

**Research date:** 2026-04-03
**Valid until:** 2026-07-03 (AudioAddict API has been stable for years; low churn risk)
