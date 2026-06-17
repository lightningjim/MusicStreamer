# Phase 89c: Provider Brand-Avatar Cover-Slot Fallback - Pattern Map

**Mapped:** 2026-06-17
**Files analyzed:** 6 (2 new, 1 new asset dir, 1 new test file, 2 modified)
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `musicstreamer/brand_avatars.py` (NEW) | registry/utility | request-response (lookup) | `musicstreamer/yt_import.py` L263-284 | exact — same dict+lookup registry shape |
| `musicstreamer/ui_qt/brand-avatars/` (NEW dir) | config/asset | file-I/O | `musicstreamer/ui_qt/icons/` + `packaging/windows/MusicStreamer.spec:122-125` | exact — same loose package-data pattern |
| `tests/test_brand_avatars.py` (NEW) | test | transform | `tests/test_cover_art_avatar.py` | exact — same source-grep + unit-test style |
| `musicstreamer/ui_qt/now_playing_panel.py` (MODIFY) | component | request-response + file-I/O | self — extend existing `_set_avatar_pixmap_from_path` / `_apply_art_tier` patterns | exact (self-analog) |
| `musicstreamer/ui_qt/edit_station_dialog.py` (MODIFY) | component | file-I/O | self — extend existing `_on_choose_logo` / `_on_avatar_fetched` patterns | exact (self-analog) |
| `packaging/windows/MusicStreamer.spec` (MODIFY) | config | file-I/O | self — existing `datas` list at L122-125 | exact (self-analog) |

---

## Pattern Assignments

### `musicstreamer/brand_avatars.py` (NEW — registry/utility, request-response)

**Analog:** `musicstreamer/yt_import.py` L263-284

**Imports pattern** (yt_import.py L14-20):
```python
import logging
import os
import re
import urllib.request
from typing import Callable, Optional

import yt_dlp
```

For brand_avatars.py — simpler; only stdlib needed:
```python
import importlib.resources as _res
import os
from typing import Optional
```

**Registry + lookup pattern** (yt_import.py L263-284):
```python
# Per-provider avatar fetcher registry (D-04)
_AVATAR_FETCHERS: dict[str, Callable[[str], bytes]] = {}


def register_avatar_fetcher(provider: str, fetcher: Callable[[str], bytes]) -> None:
    """Register a per-provider avatar fetcher callable."""
    _AVATAR_FETCHERS[provider] = fetcher


def get_avatar_fetcher(provider: str) -> Optional[Callable[[str], bytes]]:
    """Return the registered avatar fetcher for the given provider, or None."""
    return _AVATAR_FETCHERS.get(provider)
```

Copy this shape verbatim for brand_avatars.py but as a static dict + single lookup:
```python
_REGISTRY: dict[str, str] = {
    "SomaFM":         "SomaFM.png",
    "DI.fm":          "DI.fm.png",
    "RadioTunes":     "RadioTunes.png",
    "JazzRadio":      "JazzRadio.png",
    "RockRadio":      "RockRadio.png",
    "ClassicalRadio": "ClassicalRadio.png",
    "ZenRadio":       "ZenRadio.png",
}

def lookup(provider_name: str) -> Optional[str]:
    """Return absolute path to bundled brand PNG if it exists, else None."""
    filename = _REGISTRY.get(provider_name)
    if filename is None:
        return None
    pkg_path = _res.files("musicstreamer.ui_qt") / "brand-avatars" / filename
    abs_str = str(pkg_path)
    if not os.path.isfile(abs_str):
        return None
    return abs_str
```

**Provider_name string literals** (aa_import.py L106-111, soma_import.py L306):
```
"SomaFM"        (soma_import.py:306 — CamelCase, no space, no period)
"DI.fm"         (aa_import.py:106)
"RadioTunes"    (aa_import.py:107)
"JazzRadio"     (aa_import.py:108)
"RockRadio"     (aa_import.py:109)
"ClassicalRadio"(aa_import.py:110)
"ZenRadio"      (aa_import.py:111)
```
These exact strings must be the dict keys. GBS.FM is NOT registered (D-01).

**Error handling:** `lookup()` must return `None` on missing file, never raise. Mirror the `get_avatar_fetcher` never-raise contract.

---

### `musicstreamer/ui_qt/brand-avatars/` (NEW asset dir + PyInstaller datas)

**Analog:** `musicstreamer/ui_qt/icons/` dir + `packaging/windows/MusicStreamer.spec` L122-125

**Existing icons datas entry** (MusicStreamer.spec L122-125):
```python
datas=[
    ("../../musicstreamer/ui_qt/icons", "musicstreamer/ui_qt/icons"),  # SVG source
    ("icons/MusicStreamer.ico", "icons"),                              # installed icon
] + _cn_datas + ...
```

**New entry to add** (mirror the icons line exactly):
```python
("../../musicstreamer/ui_qt/brand-avatars", "musicstreamer/ui_qt/brand-avatars"),
```

Destination path must be `musicstreamer/ui_qt/brand-avatars` — not just `brand-avatars` — so `importlib.resources.files("musicstreamer.ui_qt") / "brand-avatars"` resolves correctly in the frozen bundle (Pitfall 9).

**pyproject.toml:** No explicit `package-data` stanza needed; setuptools auto-discovers via VCS (git ls-files). Requires `git add musicstreamer/ui_qt/brand-avatars/` (even as an empty dir with `.gitkeep`) so the directory is tracked.

---

### `tests/test_brand_avatars.py` (NEW — test, source-grep + unit)

**Analog:** `tests/test_cover_art_avatar.py` L1-70

**File-header + source path pattern** (test_cover_art_avatar.py L1-15):
```python
"""Source-grep drift-guard and field-filter unit tests for Phase 89 cover-art avatar path.

ART-AVATAR-07/09: precedence lock — _mb_caa_lookup must appear before
_channel_avatar_lookup in cover_art.py source (structural drift-guard over
named functions, not behavioral mocks).
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import musicstreamer.cover_art as cover_art_mod

COVER_ART_SRC = Path(__file__).parent.parent / "musicstreamer" / "cover_art.py"
```

For test_brand_avatars.py — replace with:
```python
from pathlib import Path
from unittest.mock import patch
import importlib

NOW_PLAYING_SRC = Path(__file__).parent.parent / "musicstreamer" / "ui_qt" / "now_playing_panel.py"
```

**Source-grep test pattern** (test_cover_art_avatar.py L23-38):
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
        "ART-AVATAR-09: _mb_caa_lookup must appear BEFORE _channel_avatar_lookup ..."
    )
```

Mirror this pattern for the Phase 89c drift-guards:

1. `test_brand_lookup_only_in_cover_exhausted_branch` — read `now_playing_panel.py` as text; find `def _on_cover_art_ready`; assert `_resolve_brand_avatar_fallback` appears after that position and before the next `def ` boundary; assert it does NOT appear in `bind_station` or `fetch_cover_art`.
2. `test_apply_art_tier_has_brand_avatar_branch` — find `def _apply_art_tier`; assert `_last_brand_avatar` appears within the function body.
3. `test_bind_station_resets_brand_avatar` — find `def bind_station`; assert `_last_brand_avatar = None` appears within the function body.

**Unit test pattern with monkeypatch** (mirroring test_cover_art_avatar.py L77-80):
```python
def test_channel_avatar_lookup_none_station_calls_cb_none():
    """_channel_avatar_lookup(None, cb) must call cb(None), never raise."""
    cb = MagicMock()
    cover_art_mod._channel_avatar_lookup(None, cb)
```

For brand_avatars unit tests, use `tmp_path` + `monkeypatch` to stub `importlib.resources.files`:
```python
def test_lookup_registered_providers(tmp_path, monkeypatch):
    # Place stub PNG at expected path
    d = tmp_path / "musicstreamer" / "ui_qt" / "brand-avatars"
    d.mkdir(parents=True)
    (d / "SomaFM.png").write_bytes(b"\x89PNG...")
    # Monkeypatch importlib.resources.files
    import musicstreamer.brand_avatars as ba
    monkeypatch.setattr(ba._res, "files", lambda pkg: tmp_path / pkg.replace(".", "/"))
    result = ba.lookup("SomaFM")
    assert result is not None and result.endswith("SomaFM.png")
```

---

### `musicstreamer/ui_qt/now_playing_panel.py` (MODIFY — component, file-I/O + request-response)

**Self-analog:** all patterns from this file's existing Phase 89 machinery.

**__init__ state var declaration** (now_playing_panel.py L346-347):
```python
self._last_cover_path: Optional[str] = None
self._last_avatar_path: Optional[str] = None   # Phase 89 D-13 — circular avatar tier-replay
```

Add immediately after L347:
```python
self._last_brand_avatar: Optional[str] = None   # Phase 89c D-11
```

**bind_station reset pattern** (now_playing_panel.py L935-943):
```python
# Reset _last_avatar_path FIRST to avoid stale-station bleed (Pitfall 4 / T-89-12).
self._last_avatar_path = None
if getattr(station, "icy_disabled", False):
    _provider_rel = getattr(station, "provider_avatar_path", None)
    if _provider_rel:
        from musicstreamer import paths as _p
        import os as _os
        if _os.path.isfile(_os.path.join(_p.data_dir(), _provider_rel)):
            self._set_avatar_pixmap_from_path(_provider_rel)
```

Add alongside the `_last_avatar_path = None` reset (L936):
```python
self._last_brand_avatar = None   # Phase 89c D-11: stale-station bleed guard
```

**_apply_art_tier 3-branch structure** (now_playing_panel.py L2127-2132):
```python
if self._last_cover_path is not None:
    self._set_cover_pixmap(self._last_cover_path)
elif self._last_avatar_path is not None:       # Phase 89 D-06 circular avatar re-render
    self._set_avatar_pixmap_from_path(self._last_avatar_path)
else:
    self._show_station_logo_in_cover_slot()
```

Replace `else:` with a 4th branch (insert between `_last_avatar_path` and `else`):
```python
if self._last_cover_path is not None:
    self._set_cover_pixmap(self._last_cover_path)
elif self._last_avatar_path is not None:
    self._set_avatar_pixmap_from_path(self._last_avatar_path)
elif self._last_brand_avatar is not None:      # Phase 89c D-11 brand avatar re-render
    self._set_brand_avatar_pixmap(self._last_brand_avatar)
else:
    self._show_station_logo_in_cover_slot()
```

**Trigger hook** (now_playing_panel.py L2183-2185 — THE HOOK POINT):
```python
if not path:
    self._show_station_logo_in_cover_slot()
    return
```

Replace body with:
```python
if not path:
    self._resolve_brand_avatar_fallback()   # D-07/D-08: three-tier resolution
    return
```

**_set_avatar_pixmap_from_path — the exact analog to copy for _set_brand_avatar_pixmap** (now_playing_panel.py L2205-2226):
```python
def _set_avatar_pixmap_from_path(self, rel_path: str) -> None:
    """Phase 89 ART-AVATAR-06: load cached avatar PNG, circular-crop, display in cover_label.

    Tracks self._last_avatar_path for tier-change replay in _apply_art_tier.
    Does NOT touch _last_cover_path — the two state vars are orthogonal (D-05).
    On QPixmap.isNull() (load failure), clears _last_avatar_path = None BEFORE
    falling back to _show_station_logo_in_cover_slot() so a subsequent
    _apply_art_tier resize does NOT retry the corrupt path (T-89-10 self-healing).
    Main thread only — QPixmap/QPainter are not thread-safe (RESEARCH Pitfall 8).
    """
    from musicstreamer import paths as _paths
    abs_path = os.path.join(_paths.data_dir(), rel_path)
    pix = QPixmap(abs_path)
    if pix.isNull():
        # Clear bad path FIRST so subsequent _apply_art_tier skips avatar branch.
        self._last_avatar_path = None
        self._show_station_logo_in_cover_slot()
        return
    n = self._current_art_tier or 180
    circ = _make_circular_pixmap(pix, n)
    self.cover_label.setPixmap(circ)
    self._last_avatar_path = rel_path   # tracks for tier-change replay; NOT _last_cover_path
```

New `_set_brand_avatar_pixmap` copies this shape exactly, but:
- Takes `abs_path: str` (already absolute — package-data path from `brand_avatars.lookup()`), NOT a `data_dir()`-relative path (Pitfall 1)
- Tracks `self._last_brand_avatar = abs_path` instead of `_last_avatar_path`
- Does NOT call `os.path.join(_paths.data_dir(), ...)` — the path is already absolute

```python
def _set_brand_avatar_pixmap(self, abs_path: str) -> None:
    """Phase 89c D-11: load bundled brand PNG from absolute package-data path.

    Tracks _last_brand_avatar for tier-change replay in _apply_art_tier.
    Does NOT touch _last_cover_path or _last_avatar_path.
    On load failure, clears _last_brand_avatar = None and falls back to logo.
    Main thread only — QPixmap/QPainter are not thread-safe (Phase 89 Pitfall 8).
    """
    pix = QPixmap(abs_path)
    if pix.isNull():
        self._last_brand_avatar = None
        self._show_station_logo_in_cover_slot()
        return
    n = self._current_art_tier or 180
    circ = _make_circular_pixmap(pix, n)
    self.cover_label.setPixmap(circ)
    self._last_brand_avatar = abs_path   # absolute path (package data); tracks for replay
```

**_make_circular_pixmap** (now_playing_panel.py L219-246 — reused without modification):
```python
def _make_circular_pixmap(source: QPixmap, size: int) -> QPixmap:
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

**_resolve_brand_avatar_fallback** — new method, placed near `_set_brand_avatar_pixmap` (after `_set_avatar_pixmap_from_path`). D-08 three-tier resolution:

```python
def _resolve_brand_avatar_fallback(self) -> None:
    """D-07/D-08: three-tier resolution at the cover-resolution-exhausted branch.

    Called ONLY from _on_cover_art_ready when not path (L2183).
    Never called from fetch_cover_art dispatch chain (D-12 source-grep drift-guard).
    """
    # D-08 step 1: user-override via providers.avatar_path (Phase 89.1 column).
    if self._station is not None:
        rel = getattr(self._station, "provider_avatar_path", None)
        if rel:
            from musicstreamer import paths as _p
            import os as _os
            if _os.path.isfile(_os.path.join(_p.data_dir(), rel)):
                self._set_avatar_pixmap_from_path(rel)   # sets _last_avatar_path
                return
    # D-08 step 2: bundled brand registry.
    if self._station is not None:
        from musicstreamer import brand_avatars
        abs_path = brand_avatars.lookup(self._station.provider_name or "")
        if abs_path:
            self._set_brand_avatar_pixmap(abs_path)   # sets _last_brand_avatar
            return
    # D-08 step 3: existing fallback.
    self._show_station_logo_in_cover_slot()
```

**_show_station_logo_in_cover_slot** (now_playing_panel.py L2267-2274 — kept as final fallback, no changes):
```python
def _show_station_logo_in_cover_slot(self) -> None:
    path = self._station.station_art_path if self._station else None
    n = self._current_art_tier or 180
    self.cover_label.setPixmap(_load_scaled_pixmap(path, QSize(n, n)))
    self._last_cover_path = None
```

---

### `musicstreamer/ui_qt/edit_station_dialog.py` (MODIFY — component, file-I/O)

**Self-analog:** existing `_on_choose_logo` (L1384) + existing `_on_avatar_fetched` (L1478) patterns.

**Avatar row layout** (edit_station_dialog.py L498-514 — where new button attaches):
```python
avatar_row = QHBoxLayout()
avatar_row.setContentsMargins(0, 0, 0, 0)
avatar_row.setSpacing(8)
self._avatar_preview = QLabel(self)
self._avatar_preview.setFixedSize(64, 64)
self._avatar_preview.setAlignment(Qt.AlignCenter)
self._avatar_status = QLabel("", self)
self._refresh_avatar_btn = QPushButton("Refresh avatar", self)
self._refresh_avatar_btn.setEnabled(False)
avatar_row.addWidget(self._avatar_preview)
avatar_row.addWidget(self._avatar_status)
avatar_row.addStretch()
avatar_row.addWidget(self._refresh_avatar_btn)
_avatar_container = QWidget(self)
_avatar_container.setLayout(avatar_row)
form.addRow("Channel avatar:", _avatar_container)
self._refresh_avatar_btn.clicked.connect(self._on_refresh_avatar_clicked)
```

New button to add after `_refresh_avatar_btn.clicked.connect(...)`:
```python
self._choose_brand_image_btn = QPushButton("Choose brand image…", self)
avatar_row.addWidget(self._choose_brand_image_btn)
self._choose_brand_image_btn.clicked.connect(self._on_choose_brand_image)
```

**_on_choose_logo — exact pattern to copy for _on_choose_brand_image** (edit_station_dialog.py L1384-1395):
```python
def _on_choose_logo(self) -> None:
    path, _ = QFileDialog.getOpenFileName(
        self, "Choose station logo", "",
        "Images (*.png *.jpg *.jpeg *.webp *.svg)",
    )
    if not path:
        return
    old_path = self._logo_path
    rel = assets.copy_asset_for_station(self._station.id, path, "station_art")
    self._logo_path = rel
    self._refresh_logo_preview()
    self._invalidate_cache_for(old_path)
```

New `_on_choose_brand_image` copies this shape but uses `write_provider_avatar` + `update_provider_avatar_path`:
```python
def _on_choose_brand_image(self) -> None:
    # Guard: provider_id is None for new/unsaved station (mirrors Pitfall-7 guard at L1331).
    if self._station.provider_id is None:
        self._avatar_status.setText("Save station first to set a brand image")
        return
    path, _ = QFileDialog.getOpenFileName(
        self, "Choose brand image", "",
        "Images (*.png *.jpg *.jpeg *.webp)",
    )
    if not path:
        return
    with open(path, "rb") as f:
        data = f.read()
    from musicstreamer import assets as _assets
    rel_path = _assets.write_provider_avatar(self._station.provider_id, data)
    self._station.provider_avatar_path = rel_path
    self._refresh_avatar_preview()
    self._avatar_status.setText("Brand image saved")
    self._repo.update_provider_avatar_path(self._station.provider_id, rel_path)
```

**Pitfall-7 guard pattern** (edit_station_dialog.py L1331-1335):
```python
if self._station.provider_id is None:
    self._avatar_status.setText(
        "No channel avatar (station has no provider)"
    )
    return
```

Mirror this guard at the top of `_on_choose_brand_image` with equivalent text.

**_on_avatar_fetched persist pattern** (edit_station_dialog.py L1501-1514 — the canonical non-silent-reset persist):
```python
self._station.provider_avatar_path = rel_path              # Phase 89.1 D-05
self._refresh_avatar_preview()
...
self._repo.update_provider_avatar_path(self._station.provider_id, rel_path)
```

Use this same 3-step sequence in `_on_choose_brand_image`: update in-memory model → refresh preview → persist to DB.

**_refresh_avatar_preview** (edit_station_dialog.py L1558-1582 — called after brand image chosen, no changes):
```python
def _refresh_avatar_preview(self) -> None:
    rel = getattr(self._station, "provider_avatar_path", None)
    if not rel:
        self._avatar_preview.clear()
        return
    from musicstreamer import paths as _paths
    abs_path = os.path.join(_paths.data_dir(), rel)
    if not os.path.exists(abs_path):
        self._avatar_preview.clear()
        return
    pix = QPixmap(abs_path)
    if pix.isNull():
        self._avatar_preview.clear()
        return
    self._avatar_preview.setPixmap(
        pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    )
```

This already reads `provider_avatar_path` (Phase 89.1 D-05) — no change needed; it correctly previews the file written by `_on_choose_brand_image`.

**assets.write_provider_avatar — reused as-is** (assets.py L63-89):
```python
def write_provider_avatar(provider_id: int, data: bytes) -> str:
    """Atomic mkstemp+os.replace, returns data_dir()-relative path."""
    dst_dir = paths.channel_avatars_dir()
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, f"{provider_id}.png")
    fd, tmp = tempfile.mkstemp(dir=dst_dir, suffix=".png.tmp")
    try:
        os.write(fd, data)
        os.close(fd)
        os.replace(tmp, dst)
    except Exception:
        ...
        raise
    return os.path.relpath(dst, paths.data_dir())
```

**repo.update_provider_avatar_path — reused as-is** (repo.py L965-976):
```python
def update_provider_avatar_path(self, provider_id: int, path: Optional[str]) -> None:
    """Phase 89.1 D-09: write avatar_path for provider (non-silent-reset, dedicated single-column UPDATE)."""
    self.con.execute(
        "UPDATE providers SET avatar_path = ? WHERE id = ?",
        (path, provider_id),
    )
    self.con.commit()
```

---

### `packaging/windows/MusicStreamer.spec` (MODIFY — config, file-I/O)

**Analog:** Self — existing datas list at MusicStreamer.spec L122-125.

**Existing datas pattern** (MusicStreamer.spec L122-125):
```python
datas=[
    ("../../musicstreamer/ui_qt/icons", "musicstreamer/ui_qt/icons"),  # SVG source
    ("icons/MusicStreamer.ico", "icons"),                              # installed icon
] + _cn_datas + _sl_datas + _yt_datas + _ms_datas ...
```

**Add brand-avatars entry immediately after icons line** (L123):
```python
datas=[
    ("../../musicstreamer/ui_qt/icons", "musicstreamer/ui_qt/icons"),  # SVG source
    ("../../musicstreamer/ui_qt/brand-avatars", "musicstreamer/ui_qt/brand-avatars"),  # Phase 89c D-05
    ("icons/MusicStreamer.ico", "icons"),
] + _cn_datas + ...
```

The source path `../../musicstreamer/ui_qt/brand-avatars` is relative to the spec file location (`packaging/windows/`). The destination `musicstreamer/ui_qt/brand-avatars` must match the `importlib.resources.files("musicstreamer.ui_qt") / "brand-avatars"` namespace exactly (Pitfall 9).

---

## Shared Patterns

### Circular Pixmap Rendering
**Source:** `musicstreamer/ui_qt/now_playing_panel.py` L219-246 (`_make_circular_pixmap`)
**Apply to:** `_set_brand_avatar_pixmap` in now_playing_panel.py
```python
n = self._current_art_tier or 180
circ = _make_circular_pixmap(pix, n)
self.cover_label.setPixmap(circ)
```
Pre-composed circular PNGs pass through `_make_circular_pixmap` cleanly (D-03/D-06) — no special handling needed.

### Non-Silent-Reset Persist Pattern
**Source:** `musicstreamer/repo.py` L965-976 (`update_provider_avatar_path`) + `musicstreamer/ui_qt/edit_station_dialog.py` L1501-1514
**Apply to:** `_on_choose_brand_image` in edit_station_dialog.py
Always use the dedicated single-column UPDATE, never a broad `save_station` or `update_provider` call that could zero out other columns.

### Source-Grep Drift-Guard Test Pattern
**Source:** `tests/test_cover_art_avatar.py` L23-38 (`test_mb_caa_runs_before_channel_avatar`)
**Apply to:** All D-12 drift-guard tests in `tests/test_brand_avatars.py`
Pattern: `src = SRC_FILE.read_text(encoding="utf-8")` → `find("def <anchor>")` → positional assertion.

### Stale-Token / Stale-Station Bleed Guard Pattern
**Source:** `musicstreamer/ui_qt/now_playing_panel.py` L935-936 (`bind_station` reset block)
**Apply to:** `_last_brand_avatar = None` reset in `bind_station` — place alongside `self._last_avatar_path = None` at L936.

### Provider-Id None Guard
**Source:** `musicstreamer/ui_qt/edit_station_dialog.py` L1331-1335
**Apply to:** Top of `_on_choose_brand_image` — disable button or return early if `self._station.provider_id is None`.

### isNull + clear-before-fallback Pattern
**Source:** `musicstreamer/ui_qt/now_playing_panel.py` L2218-2222 (`_set_avatar_pixmap_from_path`):
```python
if pix.isNull():
    self._last_avatar_path = None   # clear FIRST
    self._show_station_logo_in_cover_slot()
    return
```
**Apply to:** `_set_brand_avatar_pixmap` — clear `_last_brand_avatar = None` BEFORE calling `_show_station_logo_in_cover_slot()`.

---

## No Analog Found

All files have close analogs. No entries.

---

## Key Integration Points Summary

| Symbol | File | Line | Role |
|--------|------|------|------|
| `_make_circular_pixmap(source, size)` | now_playing_panel.py | L219 | Reused unmodified for brand PNG circular crop |
| `_last_avatar_path` | now_playing_panel.py | L347 | Analog for `_last_brand_avatar` (new sibling) |
| `_apply_art_tier` 3-branch | now_playing_panel.py | L2127-2132 | 4th branch inserts between `_last_avatar_path` and `else` |
| `if not path:` trigger | now_playing_panel.py | L2183 | THE HOOK — replace body with `_resolve_brand_avatar_fallback()` |
| `_set_avatar_pixmap_from_path` | now_playing_panel.py | L2205 | Analog for `_set_brand_avatar_pixmap`; reused for D-08 step-1 user override |
| `_show_station_logo_in_cover_slot` | now_playing_panel.py | L2267 | Kept as D-08 step-3 final fallback |
| `bind_station` reset block | now_playing_panel.py | L935-936 | Add `_last_brand_avatar = None` here |
| `_on_choose_logo` | edit_station_dialog.py | L1384 | Exact shape to copy for `_on_choose_brand_image` |
| avatar row layout | edit_station_dialog.py | L498-516 | New button appended to this `QHBoxLayout` |
| `_refresh_avatar_preview` | edit_station_dialog.py | L1558 | Called unmodified after brand image written |
| `write_provider_avatar` | assets.py | L63 | Reused as-is for D-09 upload |
| `update_provider_avatar_path` | repo.py | L965 | Reused as-is for D-09 persist |
| `register_avatar_fetcher`/`get_avatar_fetcher` | yt_import.py | L269/278 | Registry shape to mirror in brand_avatars.py |
| `test_mb_caa_runs_before_channel_avatar` | test_cover_art_avatar.py | L23 | Drift-guard test pattern to mirror |
| icons datas entry | MusicStreamer.spec | L123 | Exact pattern to copy for brand-avatars datas entry |

---

## Metadata

**Analog search scope:** `musicstreamer/`, `musicstreamer/ui_qt/`, `tests/`, `packaging/windows/`
**Files read:** 11 (now_playing_panel.py [6 ranges], edit_station_dialog.py [5 ranges], yt_import.py, test_cover_art_avatar.py, assets.py, repo.py, MusicStreamer.spec, aa_import.py + soma_import.py [via RESEARCH.md verified])
**Pattern extraction date:** 2026-06-17
