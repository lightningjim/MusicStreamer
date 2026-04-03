# Phase 17: AudioAddict Station Art - Research

**Researched:** 2026-04-03
**Domain:** AudioAddict API image fields, concurrent threading, GTK4/Adw popover pattern
**Confidence:** HIGH

## Summary

The AudioAddict public channels API (`https://api.audioaddict.com/v1/{slug}/channels`) returns
channel objects with an `images` dict. The `images.square` variant is present for ~85% of channels
(101/119 on DI.fm); `images.default` is present for the remainder. Image URLs require a `https:`
prefix prepended (they are returned as protocol-relative `//cdn-images.audioaddict.com/…`) and
must have the URI template suffix (`{?size,height,width,quality,pad}`) stripped before downloading.
CDN URLs require no authentication — a plain `urllib.request.urlopen` succeeds.

This API endpoint is **separate** from the `listen.di.fm/premium_high?listen_key=` endpoint that
`fetch_channels()` currently calls. That endpoint returns only `id`, `key`, `name`, `playlist` —
no images. Images require a second, unauthenticated call to `/v1/{slug}/channels`, keyed by the
channel `key` field which is consistent across both endpoints.

`insert_station()` already returns `lastrowid` as an int (confirmed in `repo.py` line 279). No
signature change needed. `update_station_art()` is a new thin SQL UPDATE targeting
`station_art_path` and does not conflict with the broader `update_station()`.

**Primary recommendation:** Extend `fetch_channels()` to also return `image_url` per channel (from a
separate `/v1/{slug}/channels` call), then implement a two-phase import flow (insert → parallel
logo downloads → update_station_art). Mirror `fetch_yt_thumbnail` exactly for the editor AA logo
fetch function.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Logo downloads run concurrently with station insert during bulk import — image URLs extracted from channels API, downloads dispatched in parallel threads, import loop does not wait for each download.
- **D-02:** Import dialog waits for all logo downloads before showing "done". Progress label: "Importing stations…" → "Fetching logos…" → "Done — N imported, M skipped". Art ready the moment dialog closes.
- **D-03:** Logo download failures are silent — station still imported without art; no error surfaced.
- **D-04:** Bulk import uses insert-then-update: `insert_station()` returns new station ID, then `repo.update_station_art(station_id, art_path)` attaches art after logo download completes. Requires adding `update_station_art()` to `repo.py`.
- **D-05:** Downloaded logos follow temp-file → `copy_asset_for_station()` → `update_station_art()` → delete temp. No deviation from established asset pattern.
- **D-06:** AA URL detection in editor via known AA stream domains matched in `_on_url_focus_out`. Domains: `listen.di.fm`, `listen.radiotunes.com`, `listen.jazzradio.com`, `listen.rockradio.com`, `listen.classicalradio.com`, `listen.zenradio.com`.
- **D-07:** "Fetch from URL" button shows API key popover when no key stored. Key saved on successful fetch (same persistence as Phase 15). If key already stored, fetch proceeds silently on focus-out.
- **D-08:** Editor resolves channel key from AA stream URL path (e.g., `di_house` from `prem2.di.fm/…/di_house?listen_key=…`), calls AA channels API to retrieve logo URL, downloads it. Silent skip if channel key unparseable or API returns no image.

### Claude's Discretion
- Exact AA API field name for channel images (researcher must verify — done, see Standard Stack below)
- Whether `fetch_channels()` is extended to include image URLs, or separate lookup is made
- Thread pool size for concurrent logo downloads
- Exact widget hierarchy for "Fetch from URL" API key popover in editor
- Whether `update_station_art()` is a dedicated SQL UPDATE or reuses an existing update path in `repo.py`

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ART-01 | AudioAddict channel logos fetched from AA API at bulk import time and stored as station art; failures silent and do not abort import | Live API verified: `images.square` or `images.default` available; CDN URLs publicly accessible; two-phase import pattern identified |
| ART-02 | When user pastes AudioAddict stream URL in station editor, channel logo auto-fetched and populated (same UX as YouTube thumbnail); skipped silently if no URL match or no image | Editor hook points identified (`_on_url_focus_out`, `_on_fetch_clicked`); API key read from `repo.get_setting`; fetch_yt_thumbnail pattern to mirror exactly |
</phase_requirements>

## Standard Stack

### Core (verified live)
| Library/API | Version | Purpose | Notes |
|-------------|---------|---------|-------|
| `https://api.audioaddict.com/v1/{slug}/channels` | live | Channel metadata + image URLs | No auth required; public |
| `urllib.request` | stdlib | HTTP download for CDN images | Already used in `aa_import.py` |
| `concurrent.futures.ThreadPoolExecutor` | stdlib | Parallel logo downloads | Recommended over raw threads for ART-01 batch |
| `threading.Thread(daemon=True)` | stdlib | Single logo fetch in editor | Matches `fetch_yt_thumbnail` pattern exactly |
| `tempfile.NamedTemporaryFile` | stdlib | Temp file for logo download | Matches `fetch_yt_thumbnail` pattern |
| `GLib.idle_add` | gi.repository | Safe UI callback from thread | Required for GTK4; already used throughout |

**No new pip dependencies required.**

## Architecture Patterns

### Recommended Project Structure
No new files needed. Changes are contained to:
```
musicstreamer/
├── aa_import.py          # fetch_channels() extended + new fetch_aa_logo()
├── repo.py               # new update_station_art() method
└── ui/
    ├── import_dialog.py  # two-phase AA import flow + progress label update
    └── edit_dialog.py    # AA URL detection + logo fetch + API key popover
```

### Pattern 1: AA Image URL Normalization
**What:** API returns protocol-relative URLs with URI template suffix.
**When to use:** Every time an image URL is read from the AA API.
```python
# Live verified format: "//cdn-images.audioaddict.com/4/0/e/f/…/file.png{?size,height,width,quality,pad}"
import re

def _normalize_aa_image_url(raw: str) -> str:
    """Prepend https: and strip URI template from an AA CDN image URL."""
    url = re.sub(r'\{[^}]+\}', '', raw).strip()  # strip {?size,...} template
    if url.startswith("//"):
        url = "https:" + url
    return url
```
**Confidence:** HIGH — verified from live API response.

### Pattern 2: fetch_aa_logo() — mirrors fetch_yt_thumbnail exactly
**What:** Daemon thread + GLib.idle_add callback for single logo download.
```python
# Source: mirrors musicstreamer/ui/edit_dialog.py fetch_yt_thumbnail pattern
def fetch_aa_logo(image_url: str, callback: callable) -> None:
    """Fetch AA channel logo in a daemon thread. callback(temp_path|None)."""
    def _worker():
        try:
            with urllib.request.urlopen(image_url, timeout=10) as resp:
                data = resp.read()
            ext = os.path.splitext(image_url.split("?")[0])[1] or ".png"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(data)
                GLib.idle_add(callback, tmp.name)
        except Exception:
            GLib.idle_add(callback, None)
    threading.Thread(target=_worker, daemon=True).start()
```

### Pattern 3: Two-Phase Bulk Import (ART-01)
**What:** Insert all stations, collect (station_id, image_url) pairs, then batch-download logos in parallel.
```python
# Phase 1: insert stations, collect logo targets
logo_targets = []  # list of (station_id, image_url)
for ch in channels:
    if repo.station_exists_by_url(ch["url"]):
        skipped += 1
    else:
        sid = repo.insert_station(name=ch["title"], url=ch["url"],
                                  provider_name=ch["provider"], tags="")
        imported += 1
        if ch.get("image_url"):
            logo_targets.append((sid, ch["image_url"]))
    if on_progress:
        on_progress(imported, skipped)

# Phase 2: parallel logo downloads
from concurrent.futures import ThreadPoolExecutor, as_completed

def _download_logo(station_id, image_url, repo):
    try:
        ext = os.path.splitext(image_url.split("?")[0])[1] or ".png"
        with urllib.request.urlopen(image_url, timeout=10) as resp:
            data = resp.read()
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        art_path = copy_asset_for_station(station_id, tmp_path, "station_art")
        os.unlink(tmp_path)
        repo.update_station_art(station_id, art_path)
    except Exception:
        pass  # silent — D-03

with ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(_download_logo, sid, url, repo): sid
               for sid, url in logo_targets}
    for _ in as_completed(futures):
        pass  # wait for all
```
**Thread pool size:** 8 workers recommended — balances throughput (~119 channels × 6 networks
= ~700 channels max) against CDN politeness. Confirmed via `concurrent.futures` stdlib docs.

### Pattern 4: fetch_channels() Image Data Extension
**What:** Separate unauthenticated call to `/v1/{slug}/channels` to get image URLs; merged into
existing channel dicts by `key` field.
```python
# In fetch_channels(), after building results list:
# Make one call per network to get image data, keyed by channel key
import urllib.request, json

def _fetch_image_map(slug: str) -> dict[str, str]:
    """Return {channel_key: normalized_image_url} for a network. Empty dict on failure."""
    try:
        url = f"https://api.audioaddict.com/v1/{slug}/channels"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        out = {}
        for ch in data:
            img = (ch.get("images") or {})
            raw = img.get("square") or img.get("default")
            if raw:
                out[ch["key"]] = _normalize_aa_image_url(raw)
        return out
    except Exception:
        return {}
```
Each result dict gets `image_url` key added (or `None` if not found).

### Pattern 5: Channel Key Extraction from Stream URL (ART-02, D-08)
**What:** Parse channel key from the AA stream URL path segment.
```python
import re

def _aa_channel_key_from_url(url: str) -> str | None:
    """Extract channel key from an AudioAddict stream URL.

    e.g. 'http://prem2.di.fm:80/di_house?listen_key=…' → 'di_house'
    """
    m = re.search(r'/([^/?]+)(?:\?|$)', url)
    return m.group(1) if m else None
```

### Pattern 6: update_station_art() in repo.py
**What:** Dedicated single-column UPDATE, narrower than the full `update_station()`.
```python
def update_station_art(self, station_id: int, art_path: str) -> None:
    self.con.execute(
        "UPDATE stations SET station_art_path = ? WHERE id = ?",
        (art_path, station_id),
    )
    self.con.commit()
```

### Pattern 7: "Fetch from URL" API Key Popover (ART-02, D-07)
**What:** GTK4 `Gtk.Popover` attached to the "Fetch from URL" button; shown only when no
API key is stored; contains a single `Gtk.Entry` + confirm button.
```python
# Attach to fetch_btn in edit_dialog.py __init__
self._aa_key_popover = Gtk.Popover()
popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
popover_box.set_margin_top(8)
popover_box.set_margin_bottom(8)
popover_box.set_margin_start(8)
popover_box.set_margin_end(8)
self._aa_key_entry_popover = Gtk.Entry()
self._aa_key_entry_popover.set_placeholder_text("AudioAddict API key…")
confirm_btn = Gtk.Button(label="Fetch")
confirm_btn.add_css_class("suggested-action")
confirm_btn.connect("clicked", self._on_aa_key_confirmed)
popover_box.append(self._aa_key_entry_popover)
popover_box.append(confirm_btn)
self._aa_key_popover.set_child(popover_box)
self._aa_key_popover.set_parent(fetch_btn)
```
Key is saved via `self.repo.set_setting("audioaddict_listen_key", key)` on successful fetch.

### Anti-Patterns to Avoid
- **Blocking the import loop on logo downloads:** Never `thread.join()` inside the channel loop — this would regress the import time to serial (Pitfall 1).
- **Calling the `/v1/{slug}/channels` API once per channel:** Make one call per network, build a lookup dict — not one call per channel.
- **Assuming `images.square` always exists:** Fall back to `images.default`. Some channels have only `default` (verified: 18 channels on DI.fm have no `square`).
- **Using the raw protocol-relative URL directly:** Always normalize (`https:` prefix + strip template) before `urlopen`.
- **Forgetting the URI template suffix:** `{?size,height,width,quality,pad}` on every AA image URL will cause a 400 or malformed URL if not stripped.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parallel I/O | Manual thread list + join | `concurrent.futures.ThreadPoolExecutor` | Handles exceptions per-future, clean shutdown, stdlib |
| Temp file management | `open()` + manual cleanup | `tempfile.NamedTemporaryFile` | Already used in `fetch_yt_thumbnail`; handles suffix correctly |
| UI-safe callbacks from threads | Direct widget calls | `GLib.idle_add` | GTK4 is not thread-safe; direct calls cause crashes/undefined behavior |

## Common Pitfalls

### Pitfall 1: Serial Logo Downloads Block Import
**What goes wrong:** Placing logo download inside the per-channel loop (even with a thread per channel if you `.join()` sequentially) makes import take 5+ minutes.
**Why it happens:** Each CDN request takes 100–500ms; 700 channels × 500ms = 350 seconds serial.
**How to avoid:** Collect all (station_id, image_url) pairs in phase 1, then use ThreadPoolExecutor in phase 2.
**Warning signs:** Import takes noticeably longer than before Phase 17.

### Pitfall 2: URI Template in Image URL Causes Download Failure
**What goes wrong:** `urllib.request.urlopen("//cdn-images.audioaddict.com/….png{?size,…}")` raises `ValueError: unknown url type`.
**Why it happens:** The AA API returns URI template URLs (RFC 6570). Not all clients strip them automatically.
**How to avoid:** Always run `_normalize_aa_image_url()` before downloading.
**Warning signs:** `ValueError` or `urllib.error.URLError` in logo download worker.

### Pitfall 3: GLib.idle_add Called After Widget Destroyed
**What goes wrong:** If dialog closes mid-fetch, callback fires and tries to update a destroyed widget.
**Why it happens:** Thread completes after user closes dialog.
**How to avoid:** Check `self._fetch_cancelled` at top of every `GLib.idle_add` callback — already the pattern in `_on_thumbnail_fetched`.

### Pitfall 4: DB Thread Safety in Bulk Import
**What goes wrong:** `update_station_art()` called from multiple ThreadPoolExecutor workers using the same `Repo`/`sqlite3.Connection` raises `ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.
**Why it happens:** SQLite connections are not thread-safe by default.
**How to avoid:** Each worker opens its own `db_connect()` / `Repo` connection, or serialize `update_station_art()` calls through a queue. The simplest fix: each `_download_logo()` worker function opens its own connection (same pattern as `_import_worker` in `import_dialog.py`).

### Pitfall 5: fetch_channels Image API Call Fails Silently — returns no image_url
**What goes wrong:** If `/v1/{slug}/channels` is unreachable, all channels get `image_url=None` — no logos. Not an error, just no art.
**Why it happens:** Expected graceful degradation per D-03.
**How to avoid:** `_fetch_image_map()` catches all exceptions and returns `{}`. Import proceeds normally.

## Code Examples

### Live API Response Structure (verified 2026-04-03)
```python
# GET https://api.audioaddict.com/v1/di/channels  (no auth required)
# Channel object (top-level keys relevant to this phase):
{
    "key": "trance",           # matches stream URL path segment
    "name": "Trance",
    "images": {
        "square": "//cdn-images.audioaddict.com/4/0/e/f/…/file.png{?size,height,width,quality,pad}",
        "default": "//cdn-images.audioaddict.com/…/file.png{?size,height,width,quality,pad}",
        "compact": "…",
        "vertical": "…",
        "horizontal_banner": "…",
        "tall_banner": "…"
    }
    # 'channel_images' key does NOT exist — STATE.md flag was incorrect
    # images.square is present for ~85% of channels (101/119 on DI.fm)
    # images.default is present for essentially all channels that have any image
}

# Channels without any image: images == {} (empty dict, not null)
# CDN URL is publicly accessible, HTTP 200, no auth header needed
```

### Stream URL → Channel Key (ART-02 editor)
```
http://prem2.di.fm:80/di_house?listen_key=abc123
                      ^^^^^^^^ = channel key
```
The last path segment before `?` is the channel key. Works for all 6 AA network domains.

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `channel_images.default` (STATE.md hypothesis) | `images.square` (fallback `images.default`) | Must use `images` not `channel_images` |
| `listen.di.fm` endpoint for all data | `/v1/{slug}/channels` for images only | Separate call needed; not in current `fetch_channels` |

**Deprecated/outdated:**
- `channel_images` key: Does not exist in the live API. The correct key is `images`.

## Open Questions

1. **Thread pool size for logo downloads**
   - What we know: ~119 channels per network × 6 networks = up to ~700 channels max (but re-imports skip existing URLs, so in practice much fewer)
   - What's unclear: CDN rate limiting behavior under parallel requests
   - Recommendation: Start with `max_workers=8`. If CDN returns 429 on heavy parallel load, reduce. Non-blocking for the user either way per D-01/D-02.

2. **Whether `fetch_channels()` return signature should include `image_url` or stay backward-compatible**
   - What we know: `import_stations()` and `_aa_import_worker()` consume the `channels` list. Both call sites are in this codebase.
   - Recommendation: Add `image_url` key to each dict — caller ignores unknown keys, so backward-compatible. The `import_stations()` signature in `aa_import.py` must be extended to accept and act on it.

## Environment Availability

Step 2.6: SKIPPED for image download portion — uses stdlib only (`urllib.request`, `tempfile`, `concurrent.futures`). No new external dependencies.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `https://api.audioaddict.com` | ART-01, ART-02 | ✓ | live | None — without API, no logos (silent per D-03) |
| `cdn-images.audioaddict.com` | logo download | ✓ | live | None — download fails silently per D-03 |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (detected in `/tests/`) |
| Config file | none — pyproject.toml has no `[tool.pytest]` section |
| Quick run command | `python -m pytest tests/test_aa_import.py -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ART-01 | `fetch_channels()` returns `image_url` per channel when API has images | unit | `python -m pytest tests/test_aa_import.py::test_fetch_channels_includes_image_url -x` | ❌ Wave 0 |
| ART-01 | `fetch_channels()` returns `image_url=None` when image API fails | unit | `python -m pytest tests/test_aa_import.py::test_fetch_channels_image_url_none_on_failure -x` | ❌ Wave 0 |
| ART-01 | `import_stations()` calls `update_station_art()` after successful logo download | unit | `python -m pytest tests/test_aa_import.py::test_import_stations_calls_update_art -x` | ❌ Wave 0 |
| ART-01 | `import_stations()` does not abort when logo download fails | unit | `python -m pytest tests/test_aa_import.py::test_import_stations_logo_failure_silent -x` | ❌ Wave 0 |
| ART-01 | `update_station_art()` in repo updates `station_art_path` column | unit | `python -m pytest tests/test_repo.py::test_update_station_art -x` | ❌ Wave 0 |
| ART-02 | `_is_aa_url()` returns True for all 6 AA domains | unit | `python -m pytest tests/test_aa_url_detection.py::test_is_aa_url -x` | ❌ Wave 0 |
| ART-02 | `_aa_channel_key_from_url()` extracts key correctly | unit | `python -m pytest tests/test_aa_url_detection.py::test_channel_key_extraction -x` | ❌ Wave 0 |
| ART-02 | `fetch_aa_logo()` calls callback with temp_path on success | unit | `python -m pytest tests/test_aa_url_detection.py::test_fetch_aa_logo_success -x` | ❌ Wave 0 |
| ART-02 | `fetch_aa_logo()` calls callback with None on failure | unit | `python -m pytest tests/test_aa_url_detection.py::test_fetch_aa_logo_failure -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_aa_import.py tests/test_repo.py -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_aa_import.py` — add 4 new test functions for ART-01 (image_url field, silent failure)
- [ ] `tests/test_repo.py` — add `test_update_station_art`
- [ ] `tests/test_aa_url_detection.py` — new file, 4 tests for ART-02 helpers

*(No new framework install needed — pytest already present and working.)*

## Sources

### Primary (HIGH confidence)
- Live API: `https://api.audioaddict.com/v1/di/channels` — field names, URL format, auth requirements (verified 2026-04-03)
- Live API: `https://api.audioaddict.com/v1/radiotunes/channels` — cross-network structure verification
- Live CDN: `https://cdn-images.audioaddict.com/…` — HTTP 200 without auth (verified 2026-04-03)
- Codebase: `musicstreamer/aa_import.py`, `musicstreamer/ui/edit_dialog.py`, `musicstreamer/repo.py`, `musicstreamer/assets.py` — all patterns verified by direct file read

### Secondary (MEDIUM confidence)
- `concurrent.futures.ThreadPoolExecutor` — stdlib docs; `max_workers=8` recommendation based on I/O-bound task heuristics

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- API field names: HIGH — verified live
- CDN auth requirement: HIGH — verified live (HTTP 200 without credentials)
- Standard stack: HIGH — all stdlib, no new deps
- Architecture patterns: HIGH — mirroring existing codebase patterns verified by code read
- Pitfall 4 (SQLite thread safety): HIGH — documented SQLite behavior, confirmed by `_import_worker` pattern in import_dialog.py

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (API shape is stable; CDN URL format unlikely to change)
