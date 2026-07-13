# Phase 89: YouTube Channel-Avatar Fetch + Cover-Slot Swap — Research

**Researched:** 2026-06-16
**Domain:** yt-dlp channel info extraction, Qt cover-slot threading, SQLite column plumbing, QPainter circular crop
**Confidence:** HIGH (all critical findings verified from source — yt-dlp extractor source, live codebase reads)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Avatar auto-fetches on debounced URL paste/edit in `EditStationDialog` (~600ms after URL field settles), matching Phase 6/17 YT-thumbnail auto-fetch precedent. Not on Save/OK, not on every keystroke. Satisfies ART-AVATAR-05.
- **D-02:** Dialog shows inline avatar thumbnail preview + brief status line ("Fetching avatar…" → "Avatar found"). Reuse worker-thread + queued-Signal marshalling pattern from `now_playing_panel` (`cover_art_ready` precedent).
- **D-03:** On fetch failure, show a non-blocking inline message ("No avatar found — cover will use the station thumbnail"). Save always allowed. Column stays NULL and cover slot falls back.
- **D-04:** YT-gated now, structured for reuse. Avatar fetch/preview/refresh UI activates only when URL detected as YouTube. Fetch dispatch is written as per-provider hook/registry so Phase 89b adds Twitch by registering its fetcher.
- **D-05:** Circular crop applies to separate avatar render path ONLY. Real covers (`_set_cover_pixmap`, iTunes/MB-CAA) and station-thumbnail-in-cover fallback (`_show_station_logo_in_cover_slot`) keep existing square render. Do NOT alter Phase 72.3 cover behavior.
- **D-06:** No border/ring — render clean circular crop with smooth antialiased edge (QPainter antialiasing).
- **D-07 (Claude's Discretion):** Exact circle diameter vs. padding within the square slot. Center-crop source to square before clipping to circle.
- **D-08:** ICY-disabled YouTube station with no usable avatar reverts to exactly today's behavior — `_show_station_logo_in_cover_slot()`. No generic placeholder asset. Avatar is purely additive when present.
- **D-09:** During load window on station-bind: show station thumbnail immediately, then swap to circular avatar once cached PNG loads. No flicker-to-blank.
- **D-10:** "Refresh avatar" button enabled only for avatar-capable (detected-YouTube) URLs.
- **D-11:** Refresh click runs same async worker fetch path as auto-fetch. On failure the old cached avatar is kept.
- **D-12:** Successful re-fetch overwrites cached PNG atomically — write to temp file then atomic-rename over `assets/channel-avatars/<station-id>.png`.
- **D-13:** Thread `channel_avatar_path` through `Station` dataclass (`models.py`), the row→`Station` mappers, and `save_station()` (`repo.py`). Store relative to `data_dir()` (e.g. `assets/channel-avatars/12.png`). Use `paths.channel_avatars_dir()` for all path construction — no hardcoded strings.
- **D-14:** Cover-resolver source order stays `ICY → iTunes → MB-CAA → channel-avatar → placeholder`. Source-grep drift-guard `test_cover_resolution_precedence::test_mb_caa_runs_before_channel_avatar` must confirm `_mb_caa_lookup` appears before `_channel_avatar_lookup` in source (ART-AVATAR-09). Named functions must live in same source file.
- **D-15:** Phase 71 sibling-render parity preserved — drift-guard `test_richtext_baseline_unchanged_by_phase_89` mirrors existing Phase 71 baseline test (ART-AVATAR-10).

### Claude's Discretion
- Exact circle diameter/inset (D-07).
- Debounce interval (≈600ms suggested — match Phase 6/17 thumbnail precedent).
- Inline status/preview widget layout within `EditStationDialog`.
- Whether avatar render path needs its own `_last_avatar_path`-style tracked state so `_apply_art_tier` re-renders the circular avatar correctly on panel resize.

### Deferred Ideas (OUT OF SCOPE)
- Twitch Helix `profile_image_url` fetch — Phase 89b (ART-AVATAR-04).
- Channel avatar in the logo slot — explicitly rejected.
- Per-play avatar refresh — explicitly rejected.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ART-AVATAR-03 | `yt_import.fetch_channel_avatar(channel_url) -> bytes`; filters `thumbnails[]` for `id == 'avatar_uncropped'` (preferred) or `id == 'avatar'`; rejects `width != height` | yt-dlp extractor source confirms `avatar_uncropped` is added in `_tab.py`; `_extract_thumbnails` does NOT set `id` on cropped entries — see Pitfall 1 |
| ART-AVATAR-05 | Auto-fetch on URL paste + "Refresh avatar" button | Debounce pattern in `edit_station_dialog.py`: `_url_timer` (500ms, not 600ms); `_on_url_text_changed` → `_on_url_timer_timeout` → `_LogoFetchWorker` |
| ART-AVATAR-06 | ICY-disabled YT station with avatar: cover slot shows circular-cropped avatar instead of station thumbnail | `bind_station` ICY-disabled path at L887; `_apply_art_tier` branching at L2082; new `_last_avatar_path` tracked state pattern |
| ART-AVATAR-07 | Cover-resolver precedence `ICY → iTunes → MB-CAA → channel-avatar → placeholder` | `fetch_cover_art` in `cover_art.py`; new `_mb_caa_lookup` and `_channel_avatar_lookup` named functions required there |
| ART-AVATAR-08 | Avatar load <1s from station-bind (cached); falls back to current behavior on failure | Cached PNG read via `QPixmap` is instant; `bind_station` → `_show_station_logo_in_cover_slot()` is today's fallback |
| ART-AVATAR-09 | Source-grep drift-guard: `_mb_caa_lookup` appears before `_channel_avatar_lookup` in source | Both functions must be in `cover_art.py` — the file already imports `cover_art_mb`; drift-guard style confirmed from `test_gbs_marquee_drift_guard.py` and `test_constants_drift.py` |
| ART-AVATAR-10 | Phase 71 sibling parity drift-guard `test_richtext_baseline_unchanged_by_phase_89` | Existing test is `test_richtext_baseline_unchanged_by_phase_71` in `tests/test_constants_drift.py` at L82; `EXPECTED_RICHTEXT_COUNT = 3`; new test appends to same file |

</phase_requirements>

---

## Summary

Phase 89 delivers the YouTube channel-avatar feature end-to-end: a new `fetch_channel_avatar()` function in `yt_import.py`, column plumbing through `Station`/mappers/`save_station()` (deferred from 89a), a debounced auto-fetch + "Refresh avatar" button in `EditStationDialog`, a circular-crop render path in `now_playing_panel`, and two source-grep drift-guards.

The codebase read confirms that all integration surfaces are well-established and the implementation is a series of targeted additive changes. No new external packages are needed — yt-dlp and PySide6 are already in the project. The primary complexity is in the `cover_art.py` refactor (naming the existing MB-CAA call path as `_mb_caa_lookup` and adding `_channel_avatar_lookup` after it) and the `_apply_art_tier` extension to replay the circular avatar on resize.

**Primary recommendation:** Follow the existing patterns exactly — worker-thread + queued Signal, stale-token discard, keyword-default args on write boundaries, `_root_override` test isolation. The Phase 73 `cover_art_source` column plumbing is the canonical template for `channel_avatar_path`. The debounce timer in the dialog is 500ms (verified), not the 600ms mentioned in CONTEXT.md — match the actual code.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Avatar fetch (yt-dlp call, HTTP download) | Background thread | — | Network I/O; never on Qt main thread (WR-04 contract) |
| Avatar persistence (PNG write + column update) | Background thread | — | Disk write; follows same thread as fetch to avoid races |
| Avatar preview in dialog | Qt main thread (via Signal marshal) | — | Widget access only on main thread; queued Signal carries result |
| Circular-crop render in now_playing_panel | Qt main thread | — | QPainter + QLabel; only render on main thread |
| Cover-resolver precedence dispatch | `cover_art.py` module | — | Same file as existing iTunes/MB-CAA dispatch; grep guard requires co-location |
| `channel_avatar_path` storage | SQLite DB via `repo.py` | Filesystem `assets/channel-avatars/` | Column stores relative path; PNG lives on disk |
| Path construction | `paths.py` | — | Single source of truth; `_root_override` for test isolation |

---

## Standard Stack

### Core (already in project — no new installs)

| Library | Version (installed) | Purpose | Why Standard |
|---------|---------------------|---------|--------------|
| yt-dlp | 2026.3.17 (latest: 2026.6.9) [VERIFIED: PyPI] | Channel info extraction; `thumbnails[]` with `id == 'avatar_uncropped'` | Already used in `yt_import.py`; no alternative |
| PySide6 | 6.10.2 (latest: 6.11.1) [VERIFIED: PyPI] | QPainter circular crop; QThread worker; Signal/slot marshal | Already in project; all Qt code uses PySide6 |
| sqlite3 | stdlib | `channel_avatar_path` column write via `repo.update_station_avatar_path()` | Already the DB layer |
| urllib.request | stdlib | Download avatar PNG bytes after yt-dlp returns thumbnail URL | Same pattern as `_itunes_attempt` and `_LogoFetchWorker` |
| tempfile | stdlib | Atomic-write temp file for D-12 PNG overwrite | Same pattern as `_itunes_attempt` |
| threading | stdlib | Background fetch thread in `yt_import.fetch_channel_avatar` | Same as `_itunes_attempt` daemon thread |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| QThread (like _LogoFetchWorker) | threading.Thread daemon | Both work; `threading.Thread` is used in `cover_art.py`; `QThread` is used in `edit_station_dialog.py`. Either is fine for the dialog worker (use `QThread` to match `_LogoFetchWorker` pattern in same file) |
| `os.rename` atomic overwrite | `shutil.move` | `os.rename` is atomic on POSIX within same filesystem; `shutil.move` has the same behavior. Use `os.replace` (Python 3.3+) — it is cross-platform atomic overwrite unlike `os.rename` on Windows |

**Installation:** No new packages to install. All dependencies are present.

---

## Package Legitimacy Audit

| Package | Registry | Age | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|
| yt-dlp | PyPI | 5+ yrs | [OK] | Approved — already in project |
| PySide6 | PyPI | 4+ yrs | [OK] | Approved — already in project |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
URL paste in EditStationDialog
        |
        v
_on_url_text_changed → _url_timer.start() [500ms debounce]
        |
        v
_on_url_timer_timeout → detect YouTube URL?
        |                    YES
        v
_AvatarFetchWorker (QThread)
    → yt_import.fetch_channel_avatar(channel_url)
         → yt_dlp.YoutubeDL.extract_info(url, download=False)
         → filter thumbnails[]: id == 'avatar_uncropped' (preferred) or 'avatar'
         → reject if width != height
         → urllib.request: download image bytes
         → return bytes
    → atomic PNG write: tempfile → os.replace → assets/channel-avatars/<id>.png
    → emit avatar_fetch_done Signal(tmp_path, token)
        |
        v (queued connection — marshals to main thread)
_on_avatar_fetched slot (main thread)
    → stale-token check
    → update _avatar_path in dialog
    → _refresh_avatar_preview() — show 64x64 inline preview
    → _avatar_status.setText("Avatar found")
    → repo.update_channel_avatar_path(station_id, rel_path)
    → station.channel_avatar_path = rel_path

─────────────────────────────────────────
Station bind flow (now_playing_panel):

bind_station(station)
    → _show_station_logo_in_cover_slot()  [immediate thumbnail]
    → if icy_disabled AND station.channel_avatar_path:
        load QPixmap from abs path
        _set_avatar_pixmap(pix)           [circular crop render]
        _last_avatar_path = rel_path

_apply_art_tier (on resize):
    → resize logo_label + cover_label
    → _show_station_logo()
    → if _last_cover_path is not None:
          _set_cover_pixmap(_last_cover_path)
      elif _last_avatar_path is not None:       ← NEW BRANCH
          _set_avatar_pixmap_from_path(_last_avatar_path)
      else:
          _show_station_logo_in_cover_slot()

─────────────────────────────────────────
cover_art.py dispatch (ICY title arrives):

fetch_cover_art(icy_string, callback, source='auto'):
    → is_junk_title gate
    → source routing:
        'auto':
            _itunes_attempt → on_miss → _mb_caa_lookup → on_miss → _channel_avatar_lookup
        'itunes_only': _itunes_attempt
        'mb_only': _mb_caa_lookup
    (channel_avatar fallback only fires when ICY is empty/disabled — NOT via fetch_cover_art path)
```

**Note on cover_art.py:** The `_channel_avatar_lookup` in `cover_art.py` is a stretch goal for the ICY-enabled path. For the primary requirement (ART-AVATAR-06), the avatar is loaded at bind-time, not via the ICY-triggered cover-art fetch path. The source-grep drift-guard (ART-AVATAR-09) requires both `_mb_caa_lookup` and `_channel_avatar_lookup` to exist as named functions in `cover_art.py`, and `_mb_caa_lookup` must appear first in the file.

### Recommended Project Structure

No new directories beyond what 89a created. New files/changes:

```
musicstreamer/
├── yt_import.py              # + fetch_channel_avatar(channel_url) -> bytes
├── cover_art.py              # + _mb_caa_lookup(), _channel_avatar_lookup() named wrappers
├── models.py                 # + channel_avatar_path: Optional[str] = None
├── repo.py                   # + channel_avatar_path in all 4 Station mappers + save boundary
├── assets.py                 # + atomic_write_avatar(station_id, data) -> str
└── ui_qt/
    ├── now_playing_panel.py  # + _last_avatar_path, _set_avatar_pixmap, _apply_art_tier branch
    └── edit_station_dialog.py # + avatar preview row, _AvatarFetchWorker, debounce wiring
tests/
├── test_constants_drift.py   # + test_richtext_baseline_unchanged_by_phase_89 (ART-AVATAR-10)
└── test_cover_art_avatar.py  # new: field-filter unit tests, precedence drift-guard (ART-AVATAR-09)
```

### Pattern 1: yt-dlp channel info extraction (fetch_channel_avatar)

**What:** Call `yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True})` with a channel URL (not `extract_flat`), filter `thumbnails[]` for `id == 'avatar_uncropped'` first, then `id == 'avatar'`, reject where `width != height`, download the URL bytes.

**When to use:** `fetch_channel_avatar(channel_url) -> bytes` — called from the dialog worker thread.

**Source-verified shape of `thumbnails[]` from yt-dlp `_tab.py` (L655-663):**
[VERIFIED: `/tools/linux-build/.../yt_dlp/extractor/youtube/_tab.py`]

The channel tab extractor produces:
- **Cropped avatar entry** (from `_extract_thumbnails(metadata_renderer, 'avatar')`): contains `{'url': ..., 'width': int_or_none(...), 'height': int_or_none(...)}` — NO `id` field set by `_extract_thumbnails`. After `YoutubeDL._sort_thumbnails`, `t['id']` is assigned as `str(idx)` if not already present (see `YoutubeDL.py:L2720`).
- **Uncropped avatar entry** (appended manually): `{'url': ..., 'id': 'avatar_uncropped', 'preference': 1}` — no `width`/`height` fields. The uncropped URL is constructed as `url.split('=')[0] + '=s0'` (full resolution, square by YouTube convention).

**Critical implication for ART-AVATAR-03:** The `id == 'avatar_uncropped'` filter reliably identifies the uncropped entry. The `id == 'avatar'` filter will NOT match the cropped entry by string comparison — the cropped entry gets `id = str(0)` (numeric index as string) not `'avatar'`. The correct filter is: prefer `'avatar_uncropped'` first; the requirement text's `'avatar'` fallback is aspirational — in practice only `'avatar_uncropped'` has a stable string id. The `width != height` reject guard is the safety net for the `'avatar_uncropped'` case; since the uncropped URL has no width/height in the dict, `width` and `height` will both be `None` — the filter `width != height` evaluates `None != None` → `False`, so the entry is NOT rejected. This is the desired behavior (uncropped is always square). The planner should note this semantic.

**Example pattern:**
```python
# Source: verified from yt_dlp/extractor/youtube/_tab.py L655-663 + YoutubeDL.py L2718-2720
def fetch_channel_avatar(channel_url: str) -> bytes:
    opts = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "js_runtimes": yt_dlp_opts.build_js_runtimes(None),
        "remote_components": {"ejs:github"},
    }
    with cookie_utils.temp_cookies_copy() as cookiefile:
        if cookiefile is not None:
            opts["cookiefile"] = cookiefile
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
    thumbnails = (info or {}).get("thumbnails", [])
    # Prefer avatar_uncropped (explicit id); fall back to first entry with id == 'avatar'
    avatar_entry = next(
        (t for t in thumbnails if t.get("id") == "avatar_uncropped"), None
    ) or next(
        (t for t in thumbnails if t.get("id") == "avatar"), None
    )
    if avatar_entry is None:
        raise ValueError("No channel avatar found")
    w = avatar_entry.get("width")
    h = avatar_entry.get("height")
    if w is not None and h is not None and w != h:
        raise ValueError(f"Avatar is not square: {w}x{h}")
    url = avatar_entry["url"]
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.read()
```

### Pattern 2: cover_art.py named-function refactor for drift-guard

**What:** Wrap the existing MB-CAA call in a named function `_mb_caa_lookup`, add `_channel_avatar_lookup` after it. Both live in `cover_art.py`. The source-grep drift-guard confirms `_mb_caa_lookup` appears before `_channel_avatar_lookup` in the file.

**Current state of `cover_art.py`:** [VERIFIED: codebase read]
- `fetch_cover_art` at L147 dispatches to `_itunes_attempt` and `_cover_art_mb.fetch_mb_cover`.
- There is currently NO named `_mb_caa_lookup` function — `_cover_art_mb.fetch_mb_cover` is called inline.
- The refactor: rename the inline call to `_mb_caa_lookup(artist, title, callback)` which internally calls `_cover_art_mb.fetch_mb_cover(artist, title, callback)`.
- Add `_channel_avatar_lookup(station, callback)` below it.

**Example:**
```python
# Source: cover_art.py refactor — adds named wrappers for drift-guard
def _mb_caa_lookup(artist: str, title: str, callback):
    """Named wrapper so the source-grep drift-guard (ART-AVATAR-09) is stable."""
    _cover_art_mb.fetch_mb_cover(artist, title, callback)


def _channel_avatar_lookup(station, callback):
    """Named fallback for avatar tier (ART-AVATAR-07).
    
    Only fires when ICY is empty/disabled AND MB-CAA returned None.
    Reads station.channel_avatar_path and calls callback(abs_path) if stored.
    """
    ...
```

### Pattern 3: _apply_art_tier extension (now_playing_panel)

**Current state** [VERIFIED: codebase read at L2043-2085]:
```python
if self._last_cover_path is not None:
    self._set_cover_pixmap(self._last_cover_path)
else:
    self._show_station_logo_in_cover_slot()
```

**Phase 89 extension:** Add `_last_avatar_path: Optional[str] = None` in `__init__` (alongside `_last_cover_path` at L316). Extend `_apply_art_tier`:
```python
if self._last_cover_path is not None:
    self._set_cover_pixmap(self._last_cover_path)
elif self._last_avatar_path is not None:          # Phase 89 — circular avatar re-render
    self._set_avatar_pixmap_from_path(self._last_avatar_path)
else:
    self._show_station_logo_in_cover_slot()
```

`_set_avatar_pixmap_from_path` loads the PNG, calls `_make_circular_pixmap(pix, n)`, and updates `cover_label`. **Does NOT set `_last_cover_path`** — keeps the two state variables orthogonal.

### Pattern 4: Circular crop (QPainter antialiased)

**What:** Center-crop source pixmap to square, clip to inscribed circle, no border, smooth antialiased edge.

```python
# Source: QPainter antialiased circular clip — standard Qt pattern [ASSUMED: training knowledge; PySide6 QPainter docs]
def _make_circular_pixmap(source: QPixmap, size: int) -> QPixmap:
    """Center-crop source to square, clip to circle, antialiased edge."""
    # Step 1: scale source to fill the square
    sq = source.scaled(
        QSize(size, size), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    )
    # Step 2: center-crop to exact square
    if sq.width() != size or sq.height() != size:
        x = (sq.width() - size) // 2
        y = (sq.height() - size) // 2
        sq = sq.copy(x, y, size, size)
    # Step 3: paint into circular mask
    result = QPixmap(size, size)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, sq)
    painter.end()
    return result
```

Requires: `from PySide6.QtGui import QPainter, QPainterPath` (already imported in `now_playing_panel.py` — verify before adding).

### Pattern 5: Atomic PNG overwrite (assets.py)

**Current state of `assets.py`** [VERIFIED: codebase read]: No atomic-write helper exists today — `copy_asset_for_station` uses `shutil.copy2` which is not atomic. For D-12, the convention is:
1. Write to a temp file in the same directory (same filesystem → `os.replace` is atomic).
2. `os.replace(tmp, dst)` — POSIX atomic rename; overwrites atomically on Linux/macOS/Windows.

```python
# Source: D-12 atomic overwrite convention — no existing helper; new function in assets.py [ASSUMED: os.replace semantics]
def write_channel_avatar(station_id: int, data: bytes) -> str:
    """Write avatar PNG atomically. Returns path relative to data_dir()."""
    import os, tempfile
    dst_dir = paths.channel_avatars_dir()
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, f"{station_id}.png")
    fd, tmp = tempfile.mkstemp(dir=dst_dir, suffix=".png.tmp")
    try:
        os.write(fd, data)
        os.close(fd)
        os.replace(tmp, dst)
    except Exception:
        os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return os.path.relpath(dst, paths.data_dir())
```

### Pattern 6: Per-provider fetch registry (D-04)

Minimal registry — a dict mapping provider name to a fetcher callable. Lives in a new module or in `yt_import.py`:

```python
# Per-provider avatar fetcher registry (D-04) [ASSUMED: minimal design]
_AVATAR_FETCHERS: dict[str, Callable[[str], bytes]] = {}

def register_avatar_fetcher(provider: str, fetcher: Callable[[str], bytes]) -> None:
    _AVATAR_FETCHERS[provider] = fetcher

def get_avatar_fetcher(provider: str) -> Optional[Callable[[str], bytes]]:
    return _AVATAR_FETCHERS.get(provider)

# Register YouTube fetcher at module load
register_avatar_fetcher("youtube", fetch_channel_avatar)
```

Phase 89b (Twitch) calls `register_avatar_fetcher("twitch", twitch_helix.fetch_channel_avatar)` with zero dialog/cover-slot rework.

### Pattern 7: EditStationDialog avatar UI wiring

**Existing URL debounce** [VERIFIED: `edit_station_dialog.py` L357-369]:
- `_url_timer = QTimer()`, `setSingleShot(True)`, `setInterval(500)` — **500ms not 600ms**
- `url_edit.textChanged` → `_on_url_text_changed` → `_url_timer.start()`
- `_url_timer.timeout` → `_on_url_timer_timeout` → spawns `_LogoFetchWorker`
- Manual: `_fetch_logo_btn.clicked` → `_on_fetch_logo_clicked` → `_url_timer.stop()` → `_on_url_timer_timeout()`

**Phase 89 addition:** Alongside the existing logo fetch, add a parallel avatar fetch path triggered by the same `_on_url_timer_timeout` (or a separate `_on_url_avatar_timer_timeout` if the avatar fetch needs its own debounce). Recommended: share the same 500ms timer; `_on_url_timer_timeout` checks if URL is YouTube and, if so, also launches `_AvatarFetchWorker`.

The avatar section attaches **after** `cover_art_source_combo` (at L418) as a new form row:
- Avatar preview: `QLabel` 64×64 with `setAlignment(Qt.AlignCenter)`
- Status: `QLabel` for "Fetching avatar…" / "Avatar found" / "No avatar found"
- Refresh button: `QPushButton("Refresh avatar")` — enabled only for YouTube URLs

### Anti-Patterns to Avoid

- **Calling `_set_cover_pixmap` for circular avatars:** `_set_cover_pixmap` sets `_last_cover_path`, which causes `_apply_art_tier` to replay a square crop on resize. The avatar path needs its own `_last_avatar_path` so the circular re-render fires on tier change.
- **Using `extract_flat='in_playlist'` for channel avatar fetch:** `scan_playlist` uses `extract_flat` which short-circuits per-entry JS solving but also means `thumbnails[]` is sparse/absent. Avatar fetch needs a full `extract_info` without `extract_flat`.
- **Filtering `id == 'avatar'` expecting a string match on cropped entry:** The cropped entry's id is `str(0)` (numeric index), not the string `'avatar'`. Only `'avatar_uncropped'` is a stable named id.
- **Writing avatar PNG directly to final path without temp file:** Interrupted write leaves a corrupt file. Use `tempfile.mkstemp(dir=dst_dir)` + `os.replace`.
- **Spawning a new thread inside `fetch_cover_art`'s `_channel_avatar_lookup`:** The channel avatar lookup reads a local file path and calls `QPixmap` — this MUST happen on the main thread, not in a worker. The `_channel_avatar_lookup` in `cover_art.py` should be a synchronous path-returner, not a thread launcher.
- **Modifying `_show_station_logo_in_cover_slot`:** This is the D-08 fallback. Never alter it — add the avatar path as a separate `elif` branch in `_apply_art_tier` and a separate call in `bind_station`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Avatar image download | Custom HTTP client | `urllib.request.urlopen` (existing pattern in `_itunes_attempt`) | Already proven; handles timeouts; no new deps |
| Cross-thread result delivery | Direct widget access from thread | `Signal(str)` with `QueuedConnection` (existing `cover_art_ready` pattern) | Only safe way to update Qt widgets from non-Qt thread |
| Atomic file overwrite | Write directly to destination | `tempfile.mkstemp` + `os.replace` | Prevents partial-file corruption on crash/interrupt |
| YouTube thumbnail URL parsing | Custom regex on YouTube CDN URL | Let yt-dlp return the `thumbnails[]` list with `id == 'avatar_uncropped'` | yt-dlp already handles the `=s0` uncropped pattern |
| Stale-response handling | Timestamp comparison | Monotonic integer token (existing `_cover_fetch_token` pattern) | Simpler, cheaper, and already battle-tested in this codebase |

---

## Common Pitfalls

### Pitfall 1: `id == 'avatar'` does not match the cropped entry

**What goes wrong:** The requirement text says filter for `id == 'avatar'` as a fallback. But `_extract_thumbnails` does NOT set `id` on thumbnail entries — `YoutubeDL` assigns `id = str(idx)` to entries that lack one (line 2720 of `YoutubeDL.py`). The cropped avatar entry will get `id = '0'` (or some numeric index string), not `'avatar'`.

**Why it happens:** The `'avatar_uncropped'` entry is manually constructed in `_tab.py` with a literal `'id'` key. The cropped entry comes from `_extract_thumbnails` which only sets `url`, `width`, and `height`.

**How to avoid:** Only rely on `id == 'avatar_uncropped'`. The `id == 'avatar'` branch in the filter can remain as a belt-and-suspenders fallback (in case a future yt-dlp version does name the cropped entry), but it should be understood that in current yt-dlp (2026.3.17) it will never match.

**Warning signs:** Unit test for field filter passes on `'avatar_uncropped'` case but `'avatar'` branch is never exercised.

### Pitfall 2: `avatar_uncropped` has no width/height — `width != height` reject fires incorrectly

**What goes wrong:** The `avatar_uncropped` entry is constructed manually in `_tab.py` with only `url`, `id`, and `preference` — no `width` or `height`. The filter `width != height` would evaluate `None != None` → `False` in Python, so the entry is NOT rejected. This is correct behavior. BUT if the implementer uses `if not (width and height) or width != height`, this accidentally rejects all entries with None dimensions.

**How to avoid:** The `width != height` reject filter should be: `if w is not None and h is not None and w != h: reject`. Null dimensions = allow through (uncropped avatar is always square by construction).

### Pitfall 3: `extract_flat` suppresses thumbnail extraction

**What goes wrong:** `scan_playlist` uses `extract_flat='in_playlist'` which dramatically reduces the info returned per entry. Channel-level metadata (including `thumbnails[]`) may be absent or partial. `fetch_channel_avatar` MUST NOT use `extract_flat`.

**How to avoid:** Call `ydl.extract_info(url, download=False)` without `extract_flat`. Pass the channel URL directly (e.g. `https://www.youtube.com/@LofiGirl`), not a video URL. The channel tab extractor in `_tab.py` will run and populate `thumbnails[]`.

### Pitfall 4: Station bind clears `_last_avatar_path` — avatar lost on tab change

**What goes wrong:** `bind_station` calls `_show_station_logo_in_cover_slot()` at L901, which sets `_last_cover_path = None`. If `_last_avatar_path` is not also reset here, a previous station's avatar could persist.

**How to avoid:** In `bind_station`, reset both `_last_cover_path = None` (already done via `_show_station_logo_in_cover_slot`) AND `_last_avatar_path = None` before the new station's avatar is loaded. Then check `station.channel_avatar_path` and set `_last_avatar_path` for the new station.

### Pitfall 5: `update_station` signature — `channel_avatar_path` keyword default

**What goes wrong:** Following the Phase 73 `cover_art_source` precedent, adding `channel_avatar_path` as a keyword-default arg to `update_station` means callers that omit the kwarg silently reset the column to NULL. This is intentional but must be documented.

**How to avoid:** Add a dedicated `update_channel_avatar_path(station_id, path)` method (like `update_station_art` for station art) rather than polluting `update_station`. This avoids the silent-reset footgun for callers that don't need to write the avatar path. The `update_station` method (called by `EditStationDialog._on_save`) does NOT write `channel_avatar_path` — that column is written only by the avatar fetch path.

### Pitfall 6: `_apply_art_tier` elif ordering

**What goes wrong:** If `_last_cover_path` is set AND `_last_avatar_path` is set (shouldn't happen, but defensive), `_last_cover_path` must win. The elif ordering enforces precedence: real cover > avatar > thumbnail fallback.

**How to avoid:** Keep the existing `if self._last_cover_path is not None:` branch first. Avatar is `elif`. The two should never both be set simultaneously — real cover resets avatar state, and avatar only fires in `icy_disabled` stations where real covers don't arrive.

### Pitfall 7: cover_art.py `_channel_avatar_lookup` is called on ICY-enabled path

**What goes wrong:** The `fetch_cover_art` dispatch (`auto` / `mb_only` mode) chains: iTunes → MB-CAA → channel-avatar. For ICY-enabled stations, the channel-avatar lookup in `cover_art.py` would fire AFTER MB-CAA misses — this would apply the avatar for every track where MB-CAA also misses, which is wrong. The avatar should ONLY appear when ICY is disabled, not as an ICY cover-art fallback.

**How to avoid:** `_channel_avatar_lookup` in `cover_art.py` must check `station.icy_disabled` AND the trigger context. Better: `_channel_avatar_lookup` is a no-op placeholder in `cover_art.py` (satisfies the source-grep drift-guard) but the REAL avatar swap for ICY-disabled stations is handled at `bind_station` time in `now_playing_panel`, not via the cover-art fetch pipeline. The two mechanisms are complementary, not redundant.

### Pitfall 8: QPixmap construction outside main thread

**What goes wrong:** Loading the avatar PNG at bind-time via `QPixmap(path)` on a non-main thread crashes or silently fails (Qt pixmap operations are not thread-safe).

**How to avoid:** The bind-time avatar load in `bind_station` is on the main thread (bind_station is always called from the main thread in this codebase). The dialog's avatar fetch result (bytes or path) is delivered via a queued Signal to the main thread before `QPixmap` is constructed.

---

## Code Examples

### Research Question 1: yt-dlp `thumbnails[]` shape for channel URL

[VERIFIED: `/tools/linux-build/.../yt_dlp/extractor/youtube/_tab.py` L640-703]

For a channel URL like `https://www.youtube.com/@LofiGirl`:
- `info["thumbnails"]` is a list mixing primary playlist thumbnails, avatar thumbnails, and banner thumbnails (see `_tab.py` L703: `'thumbnails': (primary_thumbnails or playlist_thumbnails) + avatar_thumbnails + channel_banners`)
- Avatar entries: one cropped entry with `url`, `width`, `height` (from `_extract_thumbnails`), and one `avatar_uncropped` entry with `url`, `id='avatar_uncropped'`, `preference=1`, NO `width`/`height`
- After `YoutubeDL._sort_thumbnails + _fill_common_fields`: the cropped entry gets `id='0'` (or numeric-string index), the uncropped retains `id='avatar_uncropped'`

### Research Question 2: cover_art.py placement for `_mb_caa_lookup` / `_channel_avatar_lookup`

[VERIFIED: `musicstreamer/cover_art.py` L1-227]

Current `cover_art.py` structure:
1. `is_junk_title` (L41)
2. `_build_itunes_query` (L46)
3. `last_itunes_result` (L61)
4. `_parse_itunes_result` / `_parse_artwork_url` (L64-88)
5. `_itunes_attempt` (L91-128)
6. `_split_artist_title` (L131-144)
7. `fetch_cover_art` (L147-227) — the router; calls `_cover_art_mb.fetch_mb_cover` inline

The refactor adds two named functions **between** `_split_artist_title` and `fetch_cover_art`:

```
_split_artist_title   (L131)
_mb_caa_lookup        (NEW — thin wrapper around _cover_art_mb.fetch_mb_cover)
_channel_avatar_lookup (NEW — avatar tier placeholder; see Pitfall 7)
fetch_cover_art       (L147+offset — updated to call _mb_caa_lookup instead of _cover_art_mb.fetch_mb_cover directly)
```

The source-grep drift-guard checks that `_mb_caa_lookup` appears before `_channel_avatar_lookup` in the file — this ordering is stable as long as both functions stay in the same file and the `_mb_caa_lookup` definition precedes `_channel_avatar_lookup`.

### Research Question 3: now_playing_panel cover-slot threading

[VERIFIED: `musicstreamer/ui_qt/now_playing_panel.py` — multiple locations]

Key state variables (L292, L316):
```python
self._cover_fetch_token: int = 0
self._last_cover_path: Optional[str] = None
```

Signal/slot wiring (L231, L851-853):
```python
cover_art_ready = Signal(str)  # class-level
# in __init__:
self.cover_art_ready.connect(self._on_cover_art_ready, Qt.ConnectionType.QueuedConnection)
```

`_on_cover_art_ready` (L2126-2139): token check, then `_set_cover_pixmap(path)` or `_show_station_logo_in_cover_slot()`

`_set_cover_pixmap` (L2141-2156): sets `self._last_cover_path = path`

`_apply_art_tier` (L2043-2085): `if self._last_cover_path is not None: _set_cover_pixmap` else `_show_station_logo_in_cover_slot()`

`bind_station` ICY-disabled (L887-888): sets `icy_label.setText(station.name)` but does NOT currently load the avatar — Phase 89 adds the avatar load here.

`_show_station_logo_in_cover_slot` (L2197-2204): sets `_last_cover_path = None` (resets to fallback state).

**New state variable needed:** `self._last_avatar_path: Optional[str] = None` — tracks the circular avatar so `_apply_art_tier` can re-render on resize. Reset to None in `bind_station` alongside `_last_cover_path`.

### Research Question 4: Existing Phase 71 baseline test to mirror

[VERIFIED: `tests/test_constants_drift.py` L82-108]

```python
EXPECTED_RICHTEXT_COUNT = 3

def test_richtext_baseline_unchanged_by_phase_71():
    pkg_root = Path(__file__).parent.parent / "musicstreamer"
    needle = "setTextFormat(Qt.RichText)"
    count = 0
    for py in pkg_root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        count += text.count(needle)
    assert count == EXPECTED_RICHTEXT_COUNT, ...
```

**New test to append to same file (ART-AVATAR-10):**
```python
def test_richtext_baseline_unchanged_by_phase_89():
    """ART-AVATAR-10: Phase 89 must not add new setTextFormat(Qt.RichText) calls.
    
    The baseline is 3 (established by Phase 71). Phase 89 adds a circular-crop
    avatar path that does NOT use Qt.RichText — this test stays GREEN after Phase 89.
    """
    pkg_root = Path(__file__).parent.parent / "musicstreamer"
    needle = "setTextFormat(Qt.RichText)"
    count = 0
    for py in pkg_root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        count += text.count(needle)
    assert count == EXPECTED_RICHTEXT_COUNT, (
        f"ART-AVATAR-10 / Phase 89: expected {EXPECTED_RICHTEXT_COUNT} "
        f"setTextFormat(Qt.RichText) calls in musicstreamer/, found {count}. "
        "Phase 89 must not add new RichText labels."
    )
```

### Research Question 5: Source-grep drift-guard for precedence (ART-AVATAR-09)

Modeled after `test_gbs_marquee_drift_guard.py` [VERIFIED: codebase read] and `test_constants_drift.py`. New test file `tests/test_cover_art_avatar.py` or appended to `tests/test_cover_art.py`:

```python
def test_mb_caa_runs_before_channel_avatar():
    """ART-AVATAR-09: _mb_caa_lookup must appear before _channel_avatar_lookup in cover_art.py.
    
    Source-grep gate: precedence/ordering enforced by grepping source, not mocking
    (per feedback_gstreamer_mock_blind_spot.md).
    """
    src_path = Path(__file__).parent.parent / "musicstreamer" / "cover_art.py"
    src = src_path.read_text(encoding="utf-8")
    mb_pos = src.find("def _mb_caa_lookup")
    avatar_pos = src.find("def _channel_avatar_lookup")
    assert mb_pos != -1, "cover_art.py must define _mb_caa_lookup"
    assert avatar_pos != -1, "cover_art.py must define _channel_avatar_lookup"
    assert mb_pos < avatar_pos, (
        "ART-AVATAR-09: _mb_caa_lookup must appear BEFORE _channel_avatar_lookup in cover_art.py "
        "(cover-resolver precedence: ICY → iTunes → MB-CAA → channel-avatar → placeholder)"
    )
```

### Research Question 6: Column plumbing (D-13)

[VERIFIED: `musicstreamer/models.py`, `musicstreamer/repo.py` L550-574, L583-611, L703-722, L818-836]

**4 Station constructors in `repo.py`** that need `channel_avatar_path`:
1. `list_stations` (L556) — rows joined with providers
2. `get_station` (L595) — single station fetch
3. `list_recently_played` (L704) — last N played
4. `list_favorite_stations` (L819) — favorites

Each Station constructor call adds: `channel_avatar_path=r["channel_avatar_path"]`

**`models.py` addition** (after `prerolls_fetched_at`):
```python
channel_avatar_path: Optional[str] = None  # Phase 89 D-13
```

**Write boundary:** Add `update_channel_avatar_path(station_id: int, path: Optional[str]) -> None` to `Repo` (modeled after `update_station_art`). Does NOT go through `update_station` — avoids silent-reset footgun.

**Defensive default in mappers:**
```python
channel_avatar_path=r["channel_avatar_path"],  # None if not set (89a column default)
```

### Research Question 7: Debounce interval — actual is 500ms

[VERIFIED: `edit_station_dialog.py` L361]

```python
self._url_timer.setInterval(500)
```

CONTEXT.md says "~600ms" but the actual implementation is 500ms. Phase 89's avatar debounce should use the same 500ms to stay consistent with the existing logo fetch debounce.

### Research Question 8: Dialog URL-detection pattern for YouTube gating (D-04/D-10)

[VERIFIED: `edit_station_dialog.py` L1286-1292]

Existing YouTube detection in `_on_logo_fetched`:
```python
lower = url.lower()
if "youtube.com" in lower or "youtu.be" in lower or _is_aa_url(url):
```

For the avatar path, use `yt_import.is_yt_playlist_url(url)` OR the same inline check. The "Refresh avatar" button should be enabled/disabled based on this check in `_on_url_text_changed` or after each URL debounce.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| yt-dlp YouTube tab extractor used `avatarArt.thumbnails` | Now uses `metadata_renderer.avatar.thumbnails` + manual `avatar_uncropped` append (via `=s0` URL transform) | yt-dlp ~2022 (issue #2237) | `avatar_uncropped` id is stable and reliable |
| Direct `_cover_art_mb.fetch_mb_cover` call inline | Named `_mb_caa_lookup` wrapper (Phase 89 refactor) | Phase 89 | Enables source-grep drift-guard |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `QPainter.RenderHint.Antialiasing` + `QPainterPath.addEllipse` is the correct PySide6 circular-clip pattern | Code Examples §Pattern 4 | QPainter API may differ; verify import names in PySide6 (RenderHint.Antialiasing vs Antialiasing enum path) |
| A2 | `os.replace` is atomic overwrite on Linux (same filesystem) | Code Examples §Pattern 5 | On different filesystems (unlikely for temp-to-dest), `os.replace` may copy not rename; using `mkstemp(dir=dst_dir)` ensures same filesystem |
| A3 | `id == 'avatar'` in the filter never matches the cropped entry in current yt-dlp | Pitfall 1, Pattern 1 | A future yt-dlp version could add `id='avatar'` to the cropped entry — filter is future-safe |
| A4 | The circular avatar render path does NOT require `QPainter.CompositionMode_SourceIn` mask technique | Pattern 4 | Some Qt circular crop implementations use a QBitmap mask instead of QPainterPath clip; both work, but `QPainterPath` with `setClipPath` is cleaner for antialiasing |
| A5 | `fetch_channel_avatar` should use same `cookie_utils.temp_cookies_copy` wrapper as `scan_playlist` | Pattern 1 | If not wrapped, yt-dlp may write to the canonical cookies.txt on exit (same Pitfall 1 documented in scan_playlist) |

---

## Open Questions (RESOLVED)

All three open questions were resolved during planning; the resolutions are implemented in the Phase 89 plans (89-02, 89-03).

1. **Does yt-dlp need `remote_components: {'ejs:github'}` for channel URL extraction?**
   - RESOLVED: Include the same options as `scan_playlist` for parity; the cost is near-zero for a non-download extraction. **Adopted in 89-02 Task 1.**

2. **Does `_channel_avatar_lookup` in `cover_art.py` need to be callable with real behavior or just a named placeholder?**
   - RESOLVED: `_channel_avatar_lookup` is a real synchronous stub that reads `station.channel_avatar_path`; it is never reached for ICY-enabled stations because the ICY-disabled path performs the avatar swap at `bind_station` time, bypassing `fetch_cover_art`. Its source position (immediately after `_mb_caa_lookup`) anchors the ART-AVATAR-09 drift-guard. **Adopted in 89-03 Task 1.**

3. **Should `fetch_channel_avatar` support video URLs as well as channel URLs?**
   - RESOLVED: Yes — `fetch_channel_avatar` extracts `channel_url` from a video's info dict (`info.get('channel_url')`) and re-resolves (two-step lookup), adding one `extract_info` call for video URLs. **Adopted in 89-02 Task 1.**

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| yt-dlp | `fetch_channel_avatar` | ✓ | 2026.3.17 | — |
| PySide6 | `QPainter` circular crop, `QThread` dialog worker | ✓ | 6.10.2 | — |
| Python stdlib (`os`, `tempfile`, `threading`, `urllib.request`) | atomic write, fetch, thread | ✓ | 3.12 | — |

No missing dependencies.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pyproject.toml` |
| Quick run command | `.venv/bin/python -m pytest tests/test_cover_art_avatar.py tests/test_constants_drift.py::test_richtext_baseline_unchanged_by_phase_89 tests/test_yt_import_library.py -x` |
| Full suite command | `.venv/bin/python -m pytest tests/ -x` (>600s; scope it) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ART-AVATAR-03 | `fetch_channel_avatar` filters `id == 'avatar_uncropped'`; rejects `width != height` | unit | `.venv/bin/python -m pytest tests/test_yt_import_library.py -k avatar -x` | ❌ Wave 0 (add to existing test_yt_import_library.py) |
| ART-AVATAR-05 | Auto-fetch on URL paste + Refresh button present | unit (Qt) | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k avatar -x` | ❌ Wave 0 (add to existing test_edit_station_dialog.py) |
| ART-AVATAR-06 | ICY-disabled station shows circular avatar in cover slot | unit (Qt) | `.venv/bin/python -m pytest tests/test_now_playing_panel.py -k avatar -x` | ❌ Wave 0 (add to existing test_now_playing_panel.py) |
| ART-AVATAR-07 | Precedence `ICY → iTunes → MB-CAA → channel-avatar → placeholder` | source-grep | `.venv/bin/python -m pytest tests/test_cover_art_avatar.py::test_mb_caa_runs_before_channel_avatar -x` | ❌ Wave 0 (new file) |
| ART-AVATAR-08 | Avatar load <1s (cached PNG via QPixmap); fallback to station thumbnail | unit (timing) | manual-verify in bind_station test; <1s assertion on local file | ❌ Wave 0 |
| ART-AVATAR-09 | Source-grep: `_mb_caa_lookup` before `_channel_avatar_lookup` in `cover_art.py` | source-grep | `.venv/bin/python -m pytest tests/test_cover_art_avatar.py::test_mb_caa_runs_before_channel_avatar -x` | ❌ Wave 0 |
| ART-AVATAR-10 | Phase 71 sibling parity: `setTextFormat(Qt.RichText)` count unchanged | source-grep | `.venv/bin/python -m pytest tests/test_constants_drift.py::test_richtext_baseline_unchanged_by_phase_89 -x` | ❌ Wave 0 (append to existing file) |

### Sampling Rate

- **Per task commit:** `.venv/bin/python -m pytest tests/test_cover_art_avatar.py tests/test_constants_drift.py -x`
- **Per wave merge:** `.venv/bin/python -m pytest tests/test_cover_art.py tests/test_cover_art_avatar.py tests/test_yt_import_library.py tests/test_edit_station_dialog.py tests/test_now_playing_panel.py tests/test_constants_drift.py tests/test_repo.py tests/test_paths.py -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_cover_art_avatar.py` — new file; covers ART-AVATAR-07 (source-grep), ART-AVATAR-09 (drift-guard)
- [ ] Add avatar field-filter tests to `tests/test_yt_import_library.py` — covers ART-AVATAR-03
- [ ] Add avatar UI tests to `tests/test_edit_station_dialog.py` — covers ART-AVATAR-05
- [ ] Add avatar cover-slot tests to `tests/test_now_playing_panel.py` — covers ART-AVATAR-06/08
- [ ] Append `test_richtext_baseline_unchanged_by_phase_89` to `tests/test_constants_drift.py` — covers ART-AVATAR-10

---

## Security Domain

> `security_enforcement` absent from config — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | URL detection via `is_yt_playlist_url`; avatar bytes validated via `QPixmap.isNull()` |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious avatar URL from tampered yt-dlp response | Tampering | `QPixmap.isNull()` check rejects non-image bytes; no exec or eval of downloaded content |
| Corrupt PNG write (partial file on crash) | Denial of Service | Atomic write via `tempfile.mkstemp` + `os.replace` (D-12) |
| Path traversal via `station_id` in filename | Tampering | Station ID is an int from SQLite — no user-controlled string in path |
| yt-dlp cookies written to canonical file | Information Disclosure | `cookie_utils.temp_cookies_copy()` wrapper required (same as `scan_playlist`) |

---

## Sources

### Primary (HIGH confidence)
- `musicstreamer/yt_import.py` — existing yt-dlp call style; `scan_playlist` opts pattern
- `musicstreamer/cover_art.py` — current `fetch_cover_art` dispatch structure (L147-227)
- `musicstreamer/ui_qt/now_playing_panel.py` — `_apply_art_tier`, `_set_cover_pixmap`, `_last_cover_path`, `cover_art_ready`, `bind_station` (verified L231, L292, L316, L851-853, L878-948, L2043-2085, L2103-2204)
- `musicstreamer/ui_qt/edit_station_dialog.py` — debounce timer interval (500ms, L361), `_logo_fetch_token` pattern, `_on_url_timer_timeout` (L1185-1216)
- `musicstreamer/models.py` — `Station` dataclass (verified all fields)
- `musicstreamer/repo.py` — 4 Station mappers (L556, L595, L704, L819), `update_station` signature (L617-663)
- `musicstreamer/assets.py` — `ensure_dirs`, `copy_asset_for_station` (no atomic helper)
- `musicstreamer/paths.py` — `channel_avatars_dir()` (L103-110), `_root_override` convention
- `tests/test_constants_drift.py` — Phase 71 `test_richtext_baseline_unchanged_by_phase_71` (L82-108)
- `tests/test_gbs_marquee_drift_guard.py` — source-grep drift-guard style (L65-201)
- `tools/linux-build/.../yt_dlp/extractor/youtube/_tab.py` L640-703 — `avatar_uncropped` construction, `_extract_thumbnails` call
- `tools/linux-build/.../yt_dlp/extractor/youtube/_base.py` L1159-1181 — `_extract_thumbnails` does NOT set `id` field
- `tools/linux-build/.../yt_dlp/YoutubeDL.py` L2718-2720 — assigns `id = str(idx)` to thumbnails lacking `id`

### Secondary (MEDIUM confidence)
- PyPI registry: yt-dlp 2026.6.9 latest, PySide6 6.11.1 latest [VERIFIED: pip index versions]
- slopcheck: both packages [OK] [VERIFIED: slopcheck CLI]

---

## Metadata

**Confidence breakdown:**
- yt-dlp thumbnail extraction: HIGH — verified from bundled yt-dlp source
- cover_art.py placement: HIGH — read full file, confirmed exact structure
- now_playing_panel threading: HIGH — verified all relevant methods and line numbers
- EditStationDialog wiring: HIGH — verified 500ms debounce, token pattern, fetch worker
- Repo column plumbing: HIGH — verified all 4 Station constructors, update_station signature
- QPainter circular crop: MEDIUM — pattern is standard Qt but PySide6 API names assumed from training (A1, A4 in Assumptions Log)
- Atomic write pattern: HIGH — `os.replace` POSIX semantics well-established

**Research date:** 2026-06-16
**Valid until:** 2026-07-16 (stable libraries; yt-dlp extractor format could change but avatar_uncropped pattern predates 2022)
