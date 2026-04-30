# Phase 54: Station Logo Aspect Ratio Fix - Pattern Map

**Mapped:** 2026-04-29
**Files analyzed:** 2 (1 test + 1 conditional production)
**Analogs found:** 2 / 2

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/test_art_paths.py` (Path A — required) | test (unit) | request-response (synthetic-fixture → loader → assertion) | Same file (`test_default_size_is_32px` line 120 + `test_explicit_size_honored` line 132) | exact (in-file analog) |
| `musicstreamer/ui_qt/_art_paths.py` (Path B-1 — conditional) | utility (icon loader / image transform) | transform (path → QPixmap → QIcon) | `musicstreamer/ui_qt/now_playing_panel.py:79–91` (`_load_scaled_pixmap`) | role-match (parallel aspect-preserving loader; both call `pix.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)` and use the same FALLBACK_ICON branch) |

**Note:** Path B-1 has no exact analog for the "paint scaled pixmap onto a transparent square QPixmap canvas" idiom in this repo — `eq_response_curve.py:135` is the only `QPainter(...)` usage, and it paints into a widget (`QPainter(self)`), not a QPixmap. This means Path B-1 is the **first** transparent-canvas-paint pattern in the codebase. The Qt idiom is well-defined (it mirrors standard Qt examples) and the code excerpt in §3 of `54-RESEARCH.md` is the spec.

## Pattern Assignments

### `tests/test_art_paths.py` (test, request-response) — Path A

**Analog:** Same file. Two new tests sit alongside the existing 7 tests and reuse every existing fixture.

#### Imports pattern (lines 10–23, ALREADY PRESENT — no new imports needed)

```python
from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPixmapCache

from musicstreamer import paths
from musicstreamer.models import Station
from musicstreamer.ui_qt._art_paths import FALLBACK_ICON, load_station_icon
# Side-effect import: registers the :/icons/ resource prefix so QPixmap can
# resolve FALLBACK_ICON in tests.
from musicstreamer.ui_qt import icons_rc  # noqa: F401
```

**Note:** Tests will need `QSize` from `PySide6.QtCore` for `icon.pixmap(QSize(32, 32))`. Add to existing `from PySide6.QtCore import Qt` line:
```python
from PySide6.QtCore import QSize, Qt
```

#### Helper extension pattern — `_write_logo` (lines 38–43)

**Current signature:**
```python
def _write_logo(path: str, size: int = 64) -> None:
    """Write a real PNG file to ``path`` so QPixmap(path) returns a non-null pixmap."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pix = QPixmap(size, size)
    pix.fill(Qt.red)
    assert pix.save(path, "PNG"), f"failed to write fixture logo at {path}"
```

**Extend to (preserving all 7 existing call sites — `width`/`height` default to `None`):**
```python
def _write_logo(
    path: str,
    size: int = 64,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Write a real PNG file to ``path`` so QPixmap(path) returns a non-null pixmap.

    When ``width``/``height`` are provided, they override ``size`` and produce
    a non-square fixture (e.g. width=50, height=100 for a 1:2 portrait).
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    w = width if width is not None else size
    h = height if height is not None else size
    pix = QPixmap(w, h)
    pix.fill(Qt.red)
    assert pix.save(path, "PNG"), f"failed to write fixture logo at {path}"
```

#### Fixture pattern (lines 46–58, REUSED AS-IS)

```python
@pytest.fixture(autouse=True)
def _isolate_pixmap_cache():
    """Each test starts with a fresh QPixmapCache so cache-hit tests are deterministic."""
    QPixmapCache.clear()
    yield
    QPixmapCache.clear()


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Point paths.data_dir() at a temporary directory for the test."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    return str(tmp_path)
```

**Apply to new tests:** both new tests take `tmp_data_dir, qtbot` as parameters (same as `test_default_size_is_32px` line 120, `test_explicit_size_honored` line 132).

#### Core test pattern — Test 1: portrait aspect preserved

**Closest in-file analog:** `test_default_size_is_32px` (lines 120–129) — uses `_write_logo` + `_make_station` + `load_station_icon` + `icon.pixmap(...)` + size assertion. Copy this structure.

```python
def test_load_station_icon_preserves_portrait_aspect(tmp_data_dir, qtbot):
    """A 50w x 100h portrait source pixmap loads as 16w x 32h inside the QIcon
    (aspect ratio preserved, no center crop). Regression lock for BUG-05 / SC #3.
    """
    rel = "assets/5/portrait.png"
    _write_logo(os.path.join(tmp_data_dir, rel), width=50, height=100)

    station = _make_station(rel)
    icon = load_station_icon(station)

    pix = icon.pixmap(QSize(32, 32))
    assert pix.width() == 16, f"expected pillarboxed 16w, got {pix.width()}w"
    assert pix.height() == 32, f"expected full-height 32h, got {pix.height()}h"
```

#### Core test pattern — Test 2: landscape aspect preserved

```python
def test_load_station_icon_preserves_landscape_aspect(tmp_data_dir, qtbot):
    """A 100w x 50h landscape source pixmap loads as 32w x 16h inside the QIcon
    (aspect ratio preserved, no center crop). Covers BUG-05 / SC #2.
    """
    rel = "assets/6/landscape.png"
    _write_logo(os.path.join(tmp_data_dir, rel), width=100, height=50)

    station = _make_station(rel)
    icon = load_station_icon(station)

    pix = icon.pixmap(QSize(32, 32))
    assert pix.width() == 32, f"expected full-width 32w, got {pix.width()}w"
    assert pix.height() == 16, f"expected letterboxed 16h, got {pix.height()}h"
```

#### Path-resolution pattern (REUSED FROM lines 65–85)

Both new tests use the **relative path → `_make_station` → `load_station_icon`** flow that all existing tests use. This exercises `abs_art_path()` resolution + the `QPixmap(load_path)` branch in `_art_paths.py:75`. Do NOT pass the synthetic pixmap in-memory — `load_station_icon` only accepts a `Station` whose `station_art_path` is a string path. (See `54-RESEARCH.md` Pitfall 3.)

#### Assertion-shape rationale

The existing `test_default_size_is_32px` (line 129) uses:
```python
assert max(pix.width(), pix.height()) <= 32
```

The new tests **strengthen** that to assert exact dimensions on **both axes** because the bug being regression-locked is about the smaller axis being preserved (i.e. portrait must keep `width == 16`, not just `width <= 32`).

---

### `musicstreamer/ui_qt/_art_paths.py` (utility, transform) — Path B-1 (CONDITIONAL)

**Trigger:** Only ship if UAT step 3 (synthetic portrait fixture in EditStationDialog) shows actual cropping. Otherwise skip entirely.

**Analog:** `musicstreamer/ui_qt/now_playing_panel.py:79–91` — same role (path → aspect-preserved QPixmap), same `Qt.KeepAspectRatio` + `Qt.SmoothTransformation` style, same `FALLBACK_ICON` fall-through.

#### Existing aspect-preserving loader pattern — `_load_scaled_pixmap` (now_playing_panel.py lines 79–91)

```python
def _load_scaled_pixmap(path: Optional[str], size: QSize) -> QPixmap:
    """Load ``path`` and scale into ``size`` preserving aspect ratio.

    Falls back to the bundled generic audio icon on load failure. The returned
    pixmap is never null.
    """
    resolved = abs_art_path(path)
    pix = QPixmap()
    if resolved:
        pix = QPixmap(resolved)
    if pix.isNull():
        pix = QPixmap(_FALLBACK_ICON)
    return pix.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
```

This is the parallel pattern. Path B-1 differs only in adding a transparent-canvas paint step **after** the scale, before wrapping in QIcon.

#### Existing target — `load_station_icon` (`_art_paths.py` lines 48–80)

```python
def load_station_icon(station, size: int = STATION_ICON_SIZE) -> QIcon:
    rel = getattr(station, "station_art_path", None)
    abs_path = abs_art_path(rel)
    load_path = abs_path or FALLBACK_ICON
    key = f"station-logo:{load_path}"

    pix = QPixmap()
    if not QPixmapCache.find(key, pix):
        pix = QPixmap(load_path)
        if pix.isNull():
            pix = QPixmap(FALLBACK_ICON)
        pix = pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        QPixmapCache.insert(key, pix)
    return QIcon(pix)
```

#### Path B-1 transform — paint onto transparent square canvas (~10 line diff)

Per `54-RESEARCH.md` §3 Path B-1:

```python
# musicstreamer/ui_qt/_art_paths.py — replace lines 73–80
# NEW IMPORTS (add at top of file, alongside existing PySide6 imports)
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap, QPixmapCache

# REPLACE lines 73–80
pix = QPixmap()
if not QPixmapCache.find(key, pix):
    src = QPixmap(load_path)
    if src.isNull():
        src = QPixmap(FALLBACK_ICON)
    scaled = src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    # Paint onto a transparent square canvas so QIcon stores a perfectly
    # square pixmap with the logo centered and pillarbox/letterbox transparent.
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    x = (size - scaled.width()) // 2
    y = (size - scaled.height()) // 2
    painter.drawPixmap(QPoint(x, y), scaled)
    painter.end()
    QPixmapCache.insert(key, pix)
return QIcon(pix)
```

#### Constraints preserved

| Constraint | How preserved |
|------------|---------------|
| D-04 (transparent pillarbox) | `pix.fill(Qt.transparent)` |
| D-05 (edge-to-edge on longer axis) | `(size - scaled.width()) // 2` centering math — when `scaled.width() == size` (longer axis), `x == 0` → flush to edge |
| D-07 (uniform loader, no YouTube branch) | Single code path; no per-station type branching |
| D-09 (smallest diff) | ~10 lines in one function in one file; no callers affected |
| D-11 (no cache key bump) | Cache key string `f"station-logo:{load_path}"` unchanged |
| Fallback path | `if src.isNull(): src = QPixmap(FALLBACK_ICON)` retained verbatim |
| QPainter resource discipline | `painter.end()` called explicitly before `QPixmapCache.insert` (mirrors Qt idiom; no widget-paint analog in repo so this is the first instance) |

#### Error-handling pattern (UNCHANGED)

The existing function has no try/except — it relies on Qt's own null-pixmap semantics (`QPixmap.isNull()`). Path B-1 preserves this exactly. No new error paths.

#### Test impact

Path A tests (above) **also validate Path B-1** when run after the patch. With Path B-1 applied, the QIcon wraps a 32×32 square pixmap — but `icon.pixmap(QSize(32, 32))` still returns the same 16×32 / 32×16 visible content because Qt's QIcon internally tracks the painted region. **Caveat for the planner:** if Path B-1 is taken, the assertion shape may need to change from "exact dimensions" to "non-transparent pixel region within the pixmap" — verify empirically before locking the test shape. The current test assertions assume Path A behavior (icon stores the 16×32 directly).

---

## Shared Patterns

### Synthetic-fixture-to-disk pattern

**Source:** `tests/test_art_paths.py` lines 38–43, 65–73
**Apply to:** Both new tests
**Why:** `load_station_icon` resolves via `station.station_art_path` → `abs_art_path` → `QPixmap(load_path)`. There is no in-memory pixmap entry point, so synthetic fixtures must be written to disk before being loaded.

```python
rel = "assets/N/fixture.png"
_write_logo(os.path.join(tmp_data_dir, rel), width=W, height=H)
station = _make_station(rel)
icon = load_station_icon(station)
```

### Cache-isolation pattern (autouse)

**Source:** `tests/test_art_paths.py` lines 46–51 (`_isolate_pixmap_cache`)
**Apply to:** Automatic — every test in the file gets a fresh `QPixmapCache` before and after.
**Why:** Both new tests load fresh synthetic pixmaps; previous tests may have populated the cache with same-key entries that would mask actual loader behavior.

### Aspect-preserving scale (already pervasive)

**Source:** Three existing call sites
- `_art_paths.py:78` — `pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)`
- `now_playing_panel.py:91` — `pix.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)`
- `edit_station_dialog.py:759` — same pattern

**Apply to:** Path B-1 keeps line 78's behavior (the `scaled = src.scaled(...)` step) verbatim — the canvas-paint is layered **after** scaling, not instead of it.

### `_make_station` test factory

**Source:** `tests/test_art_paths.py` lines 26–35 (REUSED AS-IS by both new tests)

```python
def _make_station(art_path):
    return Station(
        id=1,
        name="Test Station",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=art_path,
        album_fallback_path=None,
    )
```

---

## No Analog Found

| File | Aspect | Reason | Mitigation |
|------|--------|--------|------------|
| `_art_paths.py` Path B-1 transparent-canvas-paint | The "paint scaled QPixmap onto a transparent square QPixmap canvas via QPainter" pattern has no in-repo precedent | The only other `QPainter(...)` usage in the codebase (`eq_response_curve.py:135`) paints into a widget (`QPainter(self)`), not a QPixmap. No existing `QPixmap.fill(Qt.transparent)` call sites. | The Qt idiom is well-defined (mirrors `now_playing_panel.py:91`'s scale style and standard Qt examples). RESEARCH.md §3 supplies the exact 10-line excerpt. Path B-1 is conditional on UAT — if not triggered, this gap is moot. |

---

## Metadata

**Analog search scope:**
- `tests/test_art_paths.py` (in-file analogs for Path A)
- `musicstreamer/ui_qt/_art_paths.py` (target)
- `musicstreamer/ui_qt/now_playing_panel.py` (parallel aspect-preserving loader)
- `musicstreamer/ui_qt/station_star_delegate.py` (delegate pattern, for context — NOT modified)
- `musicstreamer/ui_qt/eq_response_curve.py` (only other QPainter usage in repo)

**Files scanned:** 5 (greps over `musicstreamer/` for `QPainter`, `fill(Qt.transparent`, `drawPixmap`, `QPixmap(size`, `load_station_icon`)
**Pattern extraction date:** 2026-04-29
