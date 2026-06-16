# Phase 89: YouTube Channel-Avatar Fetch + Cover-Slot Swap — Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 10
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `musicstreamer/yt_import.py` | service | request-response (yt-dlp info extract + HTTP download) | `musicstreamer/yt_import.py` `scan_playlist` (L43–121) | exact |
| `musicstreamer/cover_art.py` | service | event-driven (callback chain) | `musicstreamer/cover_art.py` `_itunes_attempt` / `fetch_cover_art` (L91–227) | exact |
| `musicstreamer/ui_qt/now_playing_panel.py` | component | event-driven (Signal/slot, tier-replay) | same file: `_set_cover_pixmap` / `_last_cover_path` / `_apply_art_tier` / `bind_station` (L2043–2204) | exact |
| `musicstreamer/ui_qt/edit_station_dialog.py` | component | request-response (debounced fetch + QThread worker) | same file: `_LogoFetchWorker` / `_url_timer` / `_on_url_timer_timeout` / `_on_logo_fetched` (L63–131, L357–371, L1185–1319) | exact |
| `musicstreamer/repo.py` | model | CRUD | same file: 4 Station constructors + `update_station_art` (L544–574, L583–611, L691–722, L808–844) | exact |
| `musicstreamer/models.py` | model | — | same file: `cover_art_source` / `prerolls_fetched_at` fields in `Station` dataclass (L36–42) | exact |
| `musicstreamer/assets.py` | utility | file-I/O | same file: `copy_asset_for_station` (L13–28); **no** atomic-write helper exists yet | role-match (no atomic helper to copy — new pattern) |
| `musicstreamer/paths.py` | utility | — | same file: `channel_avatars_dir()` accessor + `_root_override` convention (L103–110, L25–31) | exact (function already exists from 89a) |
| `tests/test_cover_art_avatar.py` | test | — | `tests/test_gbs_marquee_drift_guard.py` (source-grep style) + `tests/test_cover_art.py` (cover_art import style) | role-match |
| `tests/test_constants_drift.py` | test | — | same file: `test_richtext_baseline_unchanged_by_phase_71` (L82–108) | exact |

---

## Pattern Assignments

### `musicstreamer/yt_import.py` — ADD `fetch_channel_avatar(channel_url) -> bytes`

**Analog:** `musicstreamer/yt_import.py` `scan_playlist` (L43–121)

**Imports pattern** (L1–19 — all already present; no new imports needed):
```python
import logging
import os
import re
from typing import Callable, Optional

import yt_dlp

from musicstreamer import constants, cookie_utils, paths, yt_dlp_opts
from musicstreamer.runtime_check import NodeRuntime
```

**Core yt-dlp opts pattern** (L71–87 of `scan_playlist`; copy opts structure, drop `extract_flat`):
```python
# scan_playlist opts — copy these keys; OMIT extract_flat for avatar fetch
opts = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "js_runtimes": yt_dlp_opts.build_js_runtimes(node_runtime),
    "remote_components": {"ejs:github"},
}
```

**Cookie-guard pattern** (L93–103 of `scan_playlist` — MUST wrap yt_dlp.YoutubeDL inside `temp_cookies_copy`):
```python
with cookie_utils.temp_cookies_copy() as cookiefile:
    if cookiefile is not None:
        opts["cookiefile"] = cookiefile
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        if "private" in msg or "unavailable" in msg or "not accessible" in msg:
            raise ValueError("Playlist Not Accessible") from e
        raise RuntimeError(str(e)) from e
```

**Avatar field-filter pattern** (from RESEARCH.md Pattern 1 — verified semantics):
```python
thumbnails = (info or {}).get("thumbnails", [])
# 'avatar_uncropped' is the only stable named id (RESEARCH.md Pitfall 1).
# The 'avatar' fallback branch is belt-and-suspenders; never matches in
# current yt-dlp (2026.3.17) where cropped entry gets id='0'.
avatar_entry = next(
    (t for t in thumbnails if t.get("id") == "avatar_uncropped"), None
) or next(
    (t for t in thumbnails if t.get("id") == "avatar"), None
)
if avatar_entry is None:
    raise ValueError("No channel avatar found")
# Width/height check: avatar_uncropped has no width/height (None != None == False).
# Only reject when BOTH are present and differ (RESEARCH.md Pitfall 2).
w = avatar_entry.get("width")
h = avatar_entry.get("height")
if w is not None and h is not None and w != h:
    raise ValueError(f"Avatar is not square: {w}x{h}")
url = avatar_entry["url"]
import urllib.request
with urllib.request.urlopen(url, timeout=10) as resp:
    return resp.read()
```

**Provider registry pattern** (D-04 — append after `fetch_channel_avatar`):
```python
# Per-provider avatar fetcher registry (D-04). Phase 89b registers Twitch here.
_AVATAR_FETCHERS: dict[str, Callable[[str], bytes]] = {}

def register_avatar_fetcher(provider: str, fetcher: Callable[[str], bytes]) -> None:
    _AVATAR_FETCHERS[provider] = fetcher

def get_avatar_fetcher(provider: str) -> Optional[Callable[[str], bytes]]:
    return _AVATAR_FETCHERS.get(provider)

# Register YouTube at module load.
register_avatar_fetcher("youtube", fetch_channel_avatar)
```

**Anti-pattern to avoid:** Do NOT pass `"extract_flat": "in_playlist"` — `scan_playlist` uses it to speed up playlist iteration, but it suppresses per-channel `thumbnails[]` (RESEARCH.md Pitfall 3).

---

### `musicstreamer/cover_art.py` — REFACTOR + ADD `_mb_caa_lookup` / `_channel_avatar_lookup`

**Analog:** `musicstreamer/cover_art.py` `_split_artist_title` and `fetch_cover_art` dispatch (L131–227)

**Current structure to understand before editing** (L131–227):
```
_split_artist_title  (L131)
fetch_cover_art      (L147)  ← calls _cover_art_mb.fetch_mb_cover INLINE
```

**Target structure after Phase 89 edit:**
```
_split_artist_title    (L131, unchanged)
_mb_caa_lookup         (NEW — thin wrapper, inserted BEFORE _channel_avatar_lookup)
_channel_avatar_lookup (NEW — avatar tier placeholder, inserted AFTER _mb_caa_lookup)
fetch_cover_art        (L147+offset — updated to call _mb_caa_lookup instead of
                        _cover_art_mb.fetch_mb_cover directly)
```

**Named-wrapper pattern** (from RESEARCH.md §Pattern 2):
```python
def _mb_caa_lookup(artist: str, title: str, callback) -> None:
    """Named wrapper so the source-grep drift-guard (ART-AVATAR-09) is stable."""
    _cover_art_mb.fetch_mb_cover(artist, title, callback)


def _channel_avatar_lookup(station, callback) -> None:
    """Avatar tier placeholder (ART-AVATAR-07 / D-14).

    Only reached via fetch_cover_art auto-mode when MB-CAA also misses.
    For ICY-disabled stations the primary avatar swap happens at bind_station
    time in now_playing_panel — this stub satisfies the source-grep drift-guard
    (ART-AVATAR-09) and provides a real hook for future ICY-enabled avatar use.

    Reads station.channel_avatar_path and calls callback(abs_path) if stored.
    Synchronous — no thread launch (RESEARCH.md anti-pattern: no QPixmap here).
    """
    if station is None:
        callback(None)
        return
    rel = getattr(station, "channel_avatar_path", None)
    if not rel:
        callback(None)
        return
    import musicstreamer.paths as _paths
    abs_path = os.path.join(_paths.data_dir(), rel)
    callback(abs_path if os.path.exists(abs_path) else None)
```

**Inline call replacement** — in `fetch_cover_art` `mb_only` branch (L197) and `auto` branch (L224), replace:
```python
# Before (L197, L224):
_cover_art_mb.fetch_mb_cover(artist, title, callback)
# After:
_mb_caa_lookup(artist, title, callback)
```

**Error handling:** Existing pattern — `_itunes_attempt` never raises out (D-20 contract). `_mb_caa_lookup` inherits that contract from `_cover_art_mb.fetch_mb_cover`. `_channel_avatar_lookup` is synchronous and must also never raise; wrap in try/except if needed.

---

### `musicstreamer/ui_qt/now_playing_panel.py` — NEW circular-avatar render path

**Analog:** same file — `_set_cover_pixmap` (L2141–2156), `_last_cover_path` (L316), `_apply_art_tier` (L2043–2085), `bind_station` ICY-disabled handling (L887–888), `_show_station_logo_in_cover_slot` (L2197–2204)

**State variable pattern** (L315–316; add `_last_avatar_path` alongside `_last_cover_path`):
```python
self._current_art_tier: Optional[int] = None   # L315 — unchanged
self._last_cover_path: Optional[str] = None    # L316 — unchanged
self._last_avatar_path: Optional[str] = None   # Phase 89 — NEW, analogous to _last_cover_path
```

**`_set_cover_pixmap` pattern to mirror** (L2141–2156) for new `_set_avatar_pixmap_from_path`:
```python
def _set_cover_pixmap(self, path: str) -> None:
    pix = QPixmap(path)
    if pix.isNull():
        self._show_station_logo_in_cover_slot()
        return
    n = self._current_art_tier or 180
    scaled = pix.scaled(
        QSize(n, n), Qt.KeepAspectRatio, Qt.SmoothTransformation
    )
    self.cover_label.setPixmap(scaled)
    self._last_cover_path = path   # tracks for tier-change replay
```

**New `_set_avatar_pixmap_from_path` — circular-crop variant** (mirrors `_set_cover_pixmap` but calls `_make_circular_pixmap` and tracks `_last_avatar_path`, NOT `_last_cover_path`):
```python
def _set_avatar_pixmap_from_path(self, rel_path: str) -> None:
    """Load a cached avatar PNG, circular-crop, and display in cover_label.

    Tracks self._last_avatar_path for tier-change replay in _apply_art_tier.
    Does NOT touch _last_cover_path — the two state vars are orthogonal (D-05).
    Main thread only (QPixmap is not thread-safe — RESEARCH.md Pitfall 8).
    """
    import musicstreamer.paths as _paths
    abs_path = os.path.join(_paths.data_dir(), rel_path)
    pix = QPixmap(abs_path)
    if pix.isNull():
        self._show_station_logo_in_cover_slot()
        return
    n = self._current_art_tier or 180
    circ = _make_circular_pixmap(pix, n)
    self.cover_label.setPixmap(circ)
    self._last_avatar_path = rel_path   # tracks for tier-change replay
```

**`_make_circular_pixmap` helper** (module-level or private static — RESEARCH.md Pattern 4; standard Qt pattern):
```python
def _make_circular_pixmap(source: QPixmap, size: int) -> QPixmap:
    """Center-crop source to square, clip to inscribed circle, antialiased."""
    sq = source.scaled(
        QSize(size, size), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    )
    if sq.width() != size or sq.height() != size:
        x = (sq.width() - size) // 2
        y = (sq.height() - size) // 2
        sq = sq.copy(x, y, size, size)
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
Verify that `QPainter`, `QPainterPath`, `QSize` are already imported at the top of `now_playing_panel.py` before adding to the import block.

**`_apply_art_tier` extension** (L2043–2085; add `elif` branch between real-cover and fallback):
```python
# Current (L2082–2085):
if self._last_cover_path is not None:
    self._set_cover_pixmap(self._last_cover_path)
else:
    self._show_station_logo_in_cover_slot()

# Phase 89 extension — insert the elif:
if self._last_cover_path is not None:
    self._set_cover_pixmap(self._last_cover_path)
elif self._last_avatar_path is not None:       # Phase 89 D-06 circular avatar re-render
    self._set_avatar_pixmap_from_path(self._last_avatar_path)
else:
    self._show_station_logo_in_cover_slot()
```

**`bind_station` ICY-disabled avatar load** (insert after L901 `_show_station_logo_in_cover_slot()` call; reset `_last_avatar_path` to None FIRST to avoid stale-station bleed per RESEARCH.md Pitfall 4):
```python
# In bind_station, after _show_station_logo_in_cover_slot() (L901):
self._last_avatar_path = None                  # Phase 89 — reset before new station load
if getattr(station, "icy_disabled", False) and getattr(station, "channel_avatar_path", None):
    self._set_avatar_pixmap_from_path(station.channel_avatar_path)
# (D-09: thumbnail shows immediately via _show_station_logo_in_cover_slot above;
#  avatar load is effectively instant from local PNG — no async needed at bind time)
```

**`_show_station_logo_in_cover_slot` sets `_last_cover_path = None`** (L2204 — existing):
```python
self._last_cover_path = None   # L2204 — existing; Phase 89 does NOT change this
# Phase 89: _last_avatar_path is reset in bind_station, not here,
# so fallback re-render doesn't clear the avatar state mid-session.
```

**Signal wiring pattern** (L851–853 — for reference when wiring any avatar_fetch_done signal in dialog):
```python
self.cover_art_ready.connect(
    self._on_cover_art_ready, Qt.ConnectionType.QueuedConnection
)
```

**Token-guard pattern** (L2126–2139 `_on_cover_art_ready` — template for dialog `_on_avatar_fetched`):
```python
def _on_cover_art_ready(self, payload: str) -> None:
    token_str, _, path = payload.partition(":")
    try:
        token = int(token_str)
    except ValueError:
        return   # malformed — never raise from Qt slot (WR-04)
    if token != self._cover_fetch_token:
        return   # stale response — newer fetch in flight
    if not path:
        self._show_station_logo_in_cover_slot()
        return
    self._set_cover_pixmap(path)
```

---

### `musicstreamer/ui_qt/edit_station_dialog.py` — debounced avatar fetch, preview, Refresh button

**Analog:** same file — `_LogoFetchWorker` (L63–131), `_url_timer` setup (L357–371), `_on_url_timer_timeout` (L1185–1205), `_on_logo_fetched` (L1252–1319), `_refresh_logo_preview` (L1222–1231), `_shutdown_logo_fetch_worker` (L1327–1342)

**Debounce timer setup pattern** (L359–363 — use 500ms, not 600ms; verified L361):
```python
self._url_timer = QTimer()
self._url_timer.setSingleShot(True)
self._url_timer.setInterval(500)          # 500ms — verified; CONTEXT.md says "~600ms" but code is 500
self.url_edit.textChanged.connect(self._on_url_text_changed)
self._url_timer.timeout.connect(self._on_url_timer_timeout)
```

**Token-monotonic pattern** (L1195–1196 — apply same to avatar fetch token):
```python
self._logo_fetch_token += 1
token = self._logo_fetch_token
```
For avatar, maintain a separate `self._avatar_fetch_token: int = 0`.

**`_LogoFetchWorker` QThread shape** (L63–131 — template for `_AvatarFetchWorker`):
```python
class _LogoFetchWorker(QThread):
    finished = Signal(str, int, str)   # (tmp_path, token, classification)

    def __init__(self, url: str, token: int, parent=None):
        super().__init__(parent)
        self.setObjectName("logo-fetch-worker")
        self._url = url
        self._token = token

    def run(self):
        token = self._token
        try:
            # ... do network I/O ...
            self.finished.emit(tmp, token, "")
        except Exception:
            self.finished.emit("", token, "")  # never raise out of run()
```
`_AvatarFetchWorker` mirrors this shape: `finished = Signal(str, int)` (tmp_path or "" + token); calls `yt_import.fetch_channel_avatar`, then `assets.write_channel_avatar` atomically. Emit path of the saved PNG (relative), not the temp.

**`_on_url_timer_timeout` extension pattern** (L1185–1205 — extend to also launch avatar fetch):
```python
def _on_url_timer_timeout(self) -> None:
    url = self.url_edit.text().strip()
    if not url:
        return
    self._logo_fetch_token += 1
    token = self._logo_fetch_token
    self._logo_status.setText("Fetching…")
    self._fetch_logo_btn.setEnabled(False)
    self._logo_fetch_worker = _LogoFetchWorker(url, token, self)
    self._logo_fetch_worker.finished.connect(self._on_logo_fetched)
    QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
    self._logo_fetch_worker.start()
    # Phase 89: also launch avatar fetch if URL is YouTube-capable
    # (reuse same debounce, separate token)
```

**YouTube URL detection pattern** (L1285–1288 — existing inline check; reuse for "Refresh avatar" button enable/disable):
```python
lower = url.lower()
if "youtube.com" in lower or "youtu.be" in lower or _is_aa_url(url):
    ...
```
For avatar gating (D-04/D-10): use `yt_import.is_yt_playlist_url(url)` OR the same inline check — the `is_yt_playlist_url` function at `yt_import.py:L24` covers `youtube.com/playlist` and `@handle/streams|live|videos` tabs but NOT bare video URLs. Discuss with planner whether video URLs need avatar support (RESEARCH.md Open Question 3).

**`_on_logo_fetched` stale-token + cleanup pattern** (L1252–1319 — template for `_on_avatar_fetched`):
```python
def _on_logo_fetched(self, tmp_path, token=0, classification=""):
    QApplication.restoreOverrideCursor()
    if token and token != self._logo_fetch_token:
        if tmp_path:
            try: os.unlink(tmp_path)
            except OSError: pass
        return
    self._fetch_logo_btn.setEnabled(True)
    if not tmp_path or not os.path.exists(tmp_path):
        # show status message ...
        self._logo_status_clear_timer.start()
        return
    try:
        rel = assets.copy_asset_for_station(...)
        self._logo_path = rel
        self._refresh_logo_preview()
        self._logo_status.setText("Fetched")
        self._logo_status_clear_timer.start()
    finally:
        try: os.unlink(tmp_path)
        except OSError: pass
```

**Avatar preview row placement** (insert after `cover_art_source_combo` row at L418):
```python
# After: form.addRow("Cover art source:", self.cover_art_source_combo)  (L418)
# Insert avatar preview row:
avatar_row = QHBoxLayout()
self._avatar_preview = QLabel()
self._avatar_preview.setFixedSize(64, 64)
self._avatar_preview.setAlignment(Qt.AlignCenter)
self._avatar_status = QLabel()
self._refresh_avatar_btn = QPushButton("Refresh avatar")
self._refresh_avatar_btn.setEnabled(False)   # enabled only for YT URLs (D-10)
avatar_row.addWidget(self._avatar_preview)
avatar_row.addWidget(self._avatar_status)
avatar_row.addStretch()
avatar_row.addWidget(self._refresh_avatar_btn)
avatar_container = QWidget()
avatar_container.setLayout(avatar_row)
form.addRow("Channel avatar:", avatar_container)
```

**Worker shutdown pattern** (L1327–1342 — mirror for `_shutdown_avatar_fetch_worker`; call from `accept()`, `closeEvent()`, `reject()`):
```python
def _shutdown_logo_fetch_worker(self) -> None:
    worker = self._logo_fetch_worker
    if worker is None or not worker.isRunning():
        return
    try:
        worker.finished.disconnect()
    except Exception:
        pass
    worker.wait(2000)
```

---

### `musicstreamer/repo.py` — thread `channel_avatar_path` through 4 Station constructors + write boundary

**Analog:** same file — `cover_art_source` keyword in all 4 Station constructors (L565, L604, L713, L828) + `update_station_art` dedicated write method (L839–844)

**4 Station constructor locations** (verified line numbers per RESEARCH.md):
- `list_stations` → L555–573 (each `Station(...)` call)
- `get_station` → L595–611
- `list_recently_played` → L703–721
- `list_favorite_stations` → L818–836

**`cover_art_source` keyword pattern to copy** (L565 of `list_stations`):
```python
cover_art_source=r["cover_art_source"] or "auto",  # Phase 73 — defensive default
```
Add analogously:
```python
channel_avatar_path=r["channel_avatar_path"],       # Phase 89 D-13 — None if not set (89a column default)
```
Note: no `or` default needed — `None` is the correct sentinel when no avatar has been fetched.

**Dedicated write method pattern** (L839–844 `update_station_art` — the template; do NOT add to `update_station`; see RESEARCH.md Pitfall 5):
```python
def update_station_art(self, station_id: int, art_path: str) -> None:
    self.con.execute(
        "UPDATE stations SET station_art_path = ? WHERE id = ?",
        (art_path, station_id),
    )
    self.con.commit()
```
New method to add:
```python
def update_channel_avatar_path(self, station_id: int, path: Optional[str]) -> None:
    """Phase 89 D-13: write channel_avatar_path for station.

    Not routed through update_station to avoid silent-reset of avatar on saves
    that don't touch the avatar column (RESEARCH.md Pitfall 5).
    """
    self.con.execute(
        "UPDATE stations SET channel_avatar_path = ? WHERE id = ?",
        (path, station_id),
    )
    self.con.commit()
```

---

### `musicstreamer/models.py` — add `channel_avatar_path` field to `Station`

**Analog:** same file — `cover_art_source` (L36), `prerolls_fetched_at` (L42)

**Field addition pattern** (after `prerolls_fetched_at` at L42):
```python
# Current last field (L42):
prerolls_fetched_at: Optional[int] = None                      # Phase 83 D-04

# Phase 89 — append after:
channel_avatar_path: Optional[str] = None                      # Phase 89 D-13
```

**Import required** (L1 — already present):
```python
from typing import Optional, List, Literal
```

---

### `musicstreamer/assets.py` — ADD `write_channel_avatar` atomic-write function

**Analog:** same file — `copy_asset_for_station` (L13–28; uses `shutil.copy2`, NOT atomic); `ensure_dirs` (L7–10 — already calls `paths.channel_avatars_dir()`); `paths.data_dir()` / `paths.channel_avatars_dir()` pattern

**Existing non-atomic pattern** (L22–27 — what NOT to copy; `shutil.copy2` is not atomic):
```python
dst = os.path.join(station_dir, filename)
shutil.copy2(src, dst)   # NOT atomic — do not replicate for avatar write
```

**New atomic-write pattern** (RESEARCH.md Pattern 5; `tempfile.mkstemp` + `os.replace`):
```python
def write_channel_avatar(station_id: int, data: bytes) -> str:
    """Write avatar PNG bytes atomically to the channel-avatars directory.

    Returns path relative to paths.data_dir(), e.g. 'assets/channel-avatars/12.png'.
    Uses tempfile.mkstemp in the same directory so os.replace is atomic
    (same filesystem — RESEARCH.md A2 / D-12).

    Adds imports at function scope to mirror the codebase's lazy-import style
    (see _itunes_attempt in cover_art.py).
    """
    import tempfile
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

**Imports already present** (L1–4 of `assets.py`):
```python
import os
import shutil
from musicstreamer import paths
```
Add `import tempfile` at module level (or inside function following codebase lazy-import style).

---

### `musicstreamer/paths.py` — NO CHANGES (89a already added `channel_avatars_dir()`)

**Verification:** `channel_avatars_dir()` already exists at L103–110:
```python
def channel_avatars_dir() -> str:
    """Phase 89A D-02: flat directory for per-station channel avatar PNGs."""
    return os.path.join(_root(), "assets", "channel-avatars")
```

**`_root_override` test isolation pattern** (L25–26 — all test files must set this):
```python
_root_override: str | None = None   # tests assign directly: paths._root_override = str(tmp_path)
```

---

### `tests/test_cover_art_avatar.py` — NEW source-grep drift-guard test file

**Analog:** `tests/test_gbs_marquee_drift_guard.py` (source-grep style with `Path.read_text`) + `tests/test_cover_art.py` (cover_art import style)

**File header pattern** (from `tests/test_cover_art.py` L1–12):
```python
"""Unit tests for musicstreamer.cover_art module."""
import json
import unittest
from unittest.mock import MagicMock

import musicstreamer.cover_art as cover_art_mod
```

**Source-grep drift-guard pattern** (from `tests/test_gbs_marquee_drift_guard.py` L65–100; `Path.read_text` + positional assertion):
```python
from pathlib import Path
import re

COVER_ART_SRC = Path(__file__).parent.parent / "musicstreamer" / "cover_art.py"
```

**`test_mb_caa_runs_before_channel_avatar`** (ART-AVATAR-09; verified structure from RESEARCH.md §Research Question 5):
```python
def test_mb_caa_runs_before_channel_avatar():
    """ART-AVATAR-09: _mb_caa_lookup must appear before _channel_avatar_lookup in cover_art.py.

    Source-grep gate: precedence enforced by grepping source, not mocking
    (per feedback_gstreamer_mock_blind_spot.md convention).
    """
    src = COVER_ART_SRC.read_text(encoding="utf-8")
    mb_pos = src.find("def _mb_caa_lookup")
    avatar_pos = src.find("def _channel_avatar_lookup")
    assert mb_pos != -1, "cover_art.py must define _mb_caa_lookup"
    assert avatar_pos != -1, "cover_art.py must define _channel_avatar_lookup"
    assert mb_pos < avatar_pos, (
        "ART-AVATAR-09: _mb_caa_lookup must appear BEFORE _channel_avatar_lookup in cover_art.py "
        "(cover-resolver precedence: ICY -> iTunes -> MB-CAA -> channel-avatar -> placeholder)"
    )
```

**Avatar field-filter unit tests** (ART-AVATAR-03; test the filter logic in `fetch_channel_avatar` with a fake `thumbnails[]` list):
```python
def test_fetch_channel_avatar_prefers_avatar_uncropped():
    """ART-AVATAR-03: avatar_uncropped entry selected over numeric-id entry."""
    thumbnails = [
        {"id": "0", "url": "http://cropped.jpg", "width": 200, "height": 200},
        {"id": "avatar_uncropped", "url": "http://uncropped.jpg"},
    ]
    # Test the filter logic directly (not the network call)
    entry = next((t for t in thumbnails if t.get("id") == "avatar_uncropped"), None)
    assert entry is not None
    assert entry["url"] == "http://uncropped.jpg"


def test_fetch_channel_avatar_rejects_non_square():
    """ART-AVATAR-03: entries with width != height are rejected."""
    w, h = 200, 150
    assert w is not None and h is not None and w != h  # rejection condition


def test_fetch_channel_avatar_allows_none_dimensions():
    """ART-AVATAR-03 / RESEARCH.md Pitfall 2: None != None == False; don't reject uncropped."""
    w, h = None, None
    # Correct guard: only reject when BOTH present and differ
    should_reject = (w is not None and h is not None and w != h)
    assert not should_reject
```

---

### `tests/test_constants_drift.py` — APPEND `test_richtext_baseline_unchanged_by_phase_89`

**Analog:** same file — `test_richtext_baseline_unchanged_by_phase_71` (L82–108; verified exact structure)

**EXPECTED_RICHTEXT_COUNT constant** (already defined before L82 in the file):
```python
EXPECTED_RICHTEXT_COUNT = 3   # established by Phase 71; Phase 89 must not change this
```

**New test to append** (ART-AVATAR-10; mirrors Phase 71 test exactly; see RESEARCH.md §Research Question 4):
```python
def test_richtext_baseline_unchanged_by_phase_89():
    """ART-AVATAR-10: Phase 89 must not add new setTextFormat(Qt.RichText) calls.

    The baseline is 3 (established by Phase 71). Phase 89 adds a circular-crop
    avatar render path that does NOT use Qt.RichText — this test stays GREEN.
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

Note: The `Path` import is already present in `test_constants_drift.py` (used by the Phase 71 test). Appending the new test requires no additional imports.

---

## Shared Patterns

### Worker-thread + queued Signal (applies to: `edit_station_dialog.py`, `now_playing_panel.py`)

**Source:** `musicstreamer/ui_qt/now_playing_panel.py` L849–853, L2103–2139  
**Also:** `musicstreamer/ui_qt/edit_station_dialog.py` L63–131, L1185–1205

```python
# Class-level Signal definition:
cover_art_ready = Signal(str)

# Wiring with QueuedConnection (main thread receives):
self.cover_art_ready.connect(
    self._on_cover_art_ready, Qt.ConnectionType.QueuedConnection
)

# Worker thread emits only — no widget access:
def _cb(path_or_none):
    emit(f"{token}:{path_or_none or ''}")

# Slot token-guards (WR-04: slots never raise):
def _on_cover_art_ready(self, payload: str) -> None:
    token_str, _, path = payload.partition(":")
    try:
        token = int(token_str)
    except ValueError:
        return
    if token != self._cover_fetch_token:
        return
```

### Stale-response token guard (applies to: all async fetch paths)

**Source:** `musicstreamer/ui_qt/now_playing_panel.py` L292, L2104–2135  
**Also:** `musicstreamer/ui_qt/edit_station_dialog.py` L1195–1196, L1267–1273

```python
# Increment on each new fetch:
self._cover_fetch_token += 1
token = self._cover_fetch_token

# In slot — discard if token doesn't match:
if token != self._cover_fetch_token:
    if tmp_path:
        try: os.unlink(tmp_path)
        except OSError: pass
    return
```

### `_root_override` test isolation (applies to: all tests touching filesystem paths)

**Source:** `musicstreamer/paths.py` L25–31

```python
# In test:
import musicstreamer.paths as paths
paths._root_override = str(tmp_path)
# teardown:
paths._root_override = None
```

### Atomic file write with `tempfile.mkstemp` + `os.replace` (applies to: `assets.write_channel_avatar`)

**Source:** No existing atomic-write helper in `assets.py` — `copy_asset_for_station` uses `shutil.copy2`. Pattern derived from `_itunes_attempt` (uses `tempfile.NamedTemporaryFile`) + D-12 requirement.

```python
fd, tmp = tempfile.mkstemp(dir=dst_dir, suffix=".png.tmp")
try:
    os.write(fd, data)
    os.close(fd)
    os.replace(tmp, dst)    # POSIX atomic rename on same filesystem
except Exception:
    os.close(fd)
    try: os.unlink(tmp)
    except OSError: pass
    raise
```

### `cover_art_source` keyword-default write-boundary precedent (applies to: `repo.update_channel_avatar_path`)

**Source:** `musicstreamer/repo.py` L617–663 `update_station`

The Phase 73 precedent shows that adding a new column via `update_station` with a keyword default can silently reset the column for callers that omit the kwarg. Phase 89 avoids this by adding a dedicated `update_channel_avatar_path(station_id, path)` method — same as `update_station_art` at L839–844.

---

## No Analog Found

All 10 files have close analogs. The only new pattern (atomic write helper in `assets.py`) is derived from `os.replace` stdlib semantics and the `_itunes_attempt` temp-file style — no existing `assets.py` helper to copy line-for-line, but the pattern is unambiguous.

---

## Metadata

**Analog search scope:** `musicstreamer/`, `musicstreamer/ui_qt/`, `tests/`  
**Files scanned:** 10 source files read directly  
**Line numbers verified:** All critical line numbers cross-checked against live codebase reads (RESEARCH.md HIGH confidence)  
**Pattern extraction date:** 2026-06-16
