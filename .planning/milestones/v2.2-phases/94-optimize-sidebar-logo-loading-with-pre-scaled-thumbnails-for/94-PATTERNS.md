# Phase 94: Sidebar Logo Thumbnail Optimization - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 4 (2 modify, 1 extend, 1 create)
**Analogs found:** 4 / 4

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `musicstreamer/ui_qt/_art_paths.py` | utility (loader + worker spawner) | file-I/O + async | `musicstreamer/cover_art.py` (`_itunes_attempt`) | exact — same daemon-thread + callback idiom |
| `musicstreamer/ui_qt/station_tree_model.py` | model (QAbstractItemModel) | event-driven (Signal/slot) | `musicstreamer/gbs_marquee.py` (`GbsMarqueeWorker`) | role-match — Signal + QueuedConnection cross-thread delivery |
| `tests/test_art_paths.py` | test (unit, extend) | — | `tests/test_art_paths.py` itself | self (extend existing file) |
| `tests/test_station_thumb_async.py` | test (integration, new) | — | `tests/test_gbs_marquee.py` (lines 229–350) | role-match — QTest.qWait + daemon-thread signal delivery |

---

## Pattern Assignments

### `musicstreamer/ui_qt/_art_paths.py` (utility, file-I/O + async)

**Primary analog:** `musicstreamer/cover_art.py`

This file gains: `THUMB_FILENAME` constant, `_thumb_path_for()`, `_is_thumb_fresh()`, `_generate_thumb()`, and a modified `load_station_icon()` signature that accepts an `on_thumb_needed` callback.

#### Imports pattern — from `cover_art.py` lines 20–29

```python
import tempfile
import threading

# New imports needed in _art_paths.py (add to existing import block):
import os
import tempfile
import threading

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap, QPixmapCache
# QImage is new — required for off-thread scaling (QPixmap is NOT thread-safe).
```

Current `_art_paths.py` imports (lines 18–29 — READ, do not re-import `os`, it is already there):

```python
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap, QPixmapCache

from musicstreamer import paths
from musicstreamer.ui_qt._theme import STATION_ICON_SIZE
from musicstreamer.ui_qt import icons_rc  # noqa: F401
```

Add `import tempfile`, `import threading`, and `QImage` to the QtGui import line.

#### Daemon-thread worker pattern — from `cover_art.py` lines 108–128

This is the **canonical project idiom** for all off-UI-thread work. Copy its shape exactly:

```python
# cover_art.py lines 108–128
def _itunes_attempt(
    icy_string: str,
    on_done: Callable[[Optional[str]], None],
) -> None:
    query_url = _build_itunes_query(icy_string)

    def _worker():
        try:
            ...blocking I/O / computation...
            on_done(temp_path)
        except Exception:
            on_done(None)

    threading.Thread(target=_worker, daemon=True).start()
```

The `_generate_thumb` function replicates this shape exactly — inner `_worker` closure, outer function just spawns the thread. The callback (`on_done` analog = `callback(station_id, thumb_path_or_none)`) delivers the result cross-thread; the Signal on StationTreeModel bridges it to the main thread.

#### Atomic file write pattern — from `desktop_install.py` lines 187–210

```python
# desktop_install.py lines 201–210
with tempfile.NamedTemporaryFile(
    dir=str(dst.parent), prefix=f".{dst.name}.", delete=False
) as tmp:
    tmp_path = Path(tmp.name)
try:
    shutil.copy2(src, tmp_path)
    os.replace(tmp_path, dst)
except Exception:
    tmp_path.unlink(missing_ok=True)
    raise
```

For `_generate_thumb`, use `tempfile.mkstemp(dir=thumb_dir, suffix='.thumb.tmp.png')` (lower-level than `NamedTemporaryFile` because `QImage.save()` needs a path string, not a file object) then `os.replace(tmp_path, thumb_path)`. On failure call `os.unlink(tmp_path)` inside an `except OSError: pass` guard — matching the `unlink(missing_ok=True)` spirit.

#### Core `load_station_icon` modification — existing function lines 48–105

The current function signature is:
```python
def load_station_icon(station, size: int = STATION_ICON_SIZE) -> QIcon:
```

Phase 94 adds one keyword parameter:
```python
def load_station_icon(station, size: int = STATION_ICON_SIZE,
                      on_thumb_needed=None) -> QIcon:
```

`on_thumb_needed` is `Optional[Callable[[int, str, str], None]]` — `(station_id, source_abs_path, thumb_abs_path)`. Default `None` preserves the existing two-argument call signature at all existing call sites (favorites_view, station_list_panel._populate_recent) — they continue working without modification.

The existing HiDPI canvas block (lines 91–104) is **unchanged**:

```python
# _art_paths.py lines 91–104 — COPY VERBATIM, no edits
pix = QPixmap(size, size)
pix.setDevicePixelRatio(scaled.devicePixelRatio())
pix.fill(Qt.transparent)
painter = QPainter(pix)
x = (size - scaled.width()) // 2
y = (size - scaled.height()) // 2
painter.drawPixmap(QPoint(x, y), scaled)
painter.end()
QPixmapCache.insert(key, pix)
```

Only the `src = QPixmap(load_path)` line (current line 80) is replaced with the thumb-path branch + async enqueue logic. The canvas code and cache insert run identically regardless of whether `src` came from the thumb, the full-res logo, or the fallback.

#### QPixmapCache key pattern — existing, lines 75–76

```python
# _art_paths.py lines 75–76 — KEY STAYS KEYED ON SOURCE PATH (not thumb path)
load_path = abs_path or FALLBACK_ICON
key = f"station-logo:{load_path}"
```

The key is keyed on the **full-res source path** (or `FALLBACK_ICON`), not on the thumb path. This is critical: `edit_station_dialog._invalidate_cache_for()` (see below) evicts by this exact key. The Phase 94 refactor must not change the key scheme.

---

### `musicstreamer/ui_qt/station_tree_model.py` (model, event-driven)

**Primary analog:** `musicstreamer/gbs_marquee.py` (`GbsMarqueeWorker`) for the Signal + QueuedConnection cross-thread delivery pattern. **Secondary analog:** `station_list_panel.py` lines 476–486 for the O(N) station walk.

#### Signal declaration — from `gbs_marquee.py` lines 468–470

```python
# gbs_marquee.py lines 468–470 — canonical Signal declaration shape
themed_logo_ready = Signal(object)   # raw PNG bytes — CR-01: NO QPixmap off the GUI thread; main-thread slot decodes
marquee_ready = Signal(str, str)     # (first_segment, full_text)
cadence_changed_internal = Signal(int)  # ms — cross-thread cadence bridge
```

For the station thumb Signal, declare at class level with three args:

```python
# station_tree_model.py — add to class body, after class line
_thumb_landing = Signal(int, str, str)  # (station_id, source_abs_path, thumb_abs_path)
# CR-01: worker emits PNG path (not QPixmap). Main-thread slot decodes.
```

Signal arity is `(int, str, str)` — three args — so `_on_thumb_landing` receives `source_abs_path` and can reconstruct the cache key `f"station-logo:{source_abs_path}"` for `QPixmapCache.remove()` without fragile string surgery.

#### QueuedConnection wiring — from `gbs_marquee.py` lines 480–484

```python
# gbs_marquee.py lines 480–484 — explicit QueuedConnection for cross-thread Signal
self.cadence_changed_internal.connect(
    self._apply_cadence_on_worker_thread, Qt.QueuedConnection
)
```

Mirror in `StationTreeModel.__init__`:

```python
# station_tree_model.py — add to __init__ after super().__init__ + _populate
self._in_flight_thumbs: set[int] = set()
self._thumb_landing.connect(self._on_thumb_landing, Qt.QueuedConnection)
```

`Qt.QueuedConnection` must be explicit — it ensures the slot runs on the main thread even when the Signal is emitted from the daemon thread's callback lambda (which runs on the daemon thread). The default `AutoConnection` would also work for this case but explicit `QueuedConnection` documents the intent and matches the `gbs_marquee.py` precedent.

#### Required import additions for `station_tree_model.py`

Current imports (lines 14–23):

```python
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QFont

from musicstreamer.models import Station
from musicstreamer.ui_qt._art_paths import load_station_icon
```

Add:

```python
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QFont, QPixmap, QPixmapCache
```

`QPixmap` and `QPixmapCache` are needed in `_on_thumb_landing` (the main-thread slot) to load the thumb PNG and evict the stale cache entry. `Signal` is the cross-thread delivery mechanism.

Also add the `_generate_thumb` import from `_art_paths`:

```python
from musicstreamer.ui_qt._art_paths import load_station_icon, _generate_thumb
```

#### O(N) station walk — from `station_list_panel.py` lines 476–486

```python
# station_list_panel.py lines 476–486 — O(N) tree walk to find station by id
for prov_row in range(self.model.rowCount()):
    prov_idx = self.model.index(prov_row, 0)
    for child_row in range(self.model.rowCount(prov_idx)):
        child_idx = self.model.index(child_row, 0, prov_idx)
        station = self.model.station_for_index(child_idx)
        if station is not None and station.id == station_id:
            proxy_idx = self._proxy.mapFromSource(child_idx)
            self.tree.expand(proxy_idx.parent())
            self.tree.setCurrentIndex(proxy_idx)
            self.tree.scrollTo(proxy_idx)
            return
```

`index_for_station_id` in `StationTreeModel` mirrors this but operates on the source model's internal node list (no proxy). Walk `self._root.children` (provider nodes), then each provider's `.children` (station nodes). Use `self.createIndex(child_row, 0, child_node)` to return the result — matching how `StationTreeModel.index()` builds indices (lines 119–129):

```python
# station_tree_model.py lines 119–129 — createIndex shape to replicate
def index(self, row, column, parent=QModelIndex()) -> QModelIndex:
    ...
    return self.createIndex(row, 0, parent_node.children[row])
```

#### Cache eviction pattern — from `edit_station_dialog.py` lines 1321–1325

```python
# edit_station_dialog.py lines 1321–1325 — QPixmapCache eviction by source-path key
def _invalidate_cache_for(self, rel_path: Optional[str]) -> None:
    if not rel_path:
        return
    resolved = abs_art_path(rel_path)
    QPixmapCache.remove(f"station-logo:{resolved}")
```

`_on_thumb_landing` evicts the stale entry (which cached the fallback icon) with the same key pattern:

```python
key = f"station-logo:{source_abs_path}"
QPixmapCache.remove(key)
```

After eviction, `dataChanged` triggers a re-query of `data()` for the row, which calls `load_station_icon` again — this time finding the fresh thumb on disk and populating the cache with the real logo.

#### `data()` call site modification — existing lines 163–164

```python
# station_tree_model.py lines 163–164 — CURRENT
if role == Qt.DecorationRole and node.kind == "station":
    return load_station_icon(node.station)
```

Changes to:

```python
# station_tree_model.py — Phase 94 replacement
if role == Qt.DecorationRole and node.kind == "station":
    return load_station_icon(node.station, on_thumb_needed=self._request_thumb)
```

`_request_thumb` is the main-thread method that guards via `_in_flight_thumbs` before calling `_generate_thumb`.

---

### `tests/test_art_paths.py` (test, extend)

**Analog:** itself — `tests/test_art_paths.py` (existing, 267 lines). Extend with new test functions appended after the existing tests.

#### Fixture pattern — lines 57–69 (replicate, do not change)

```python
# test_art_paths.py lines 57–69 — autouse fixture + tmp_data_dir (reuse as-is)
@pytest.fixture(autouse=True)
def _isolate_pixmap_cache():
    QPixmapCache.clear()
    yield
    QPixmapCache.clear()

@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    return str(tmp_path)
```

All new tests in this file must accept `tmp_data_dir` and `qtbot` as parameters — same shape as `test_relative_station_art_path_resolves_via_abs_art_path` (lines 104–132).

#### Helper `_write_logo` — lines 38–54 (reuse as-is)

```python
# test_art_paths.py lines 38–54 — write fixture PNG
def _write_logo(path, size=64, width=None, height=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    w = width if width is not None else size
    h = height if height is not None else size
    pix = QPixmap(w, h)
    pix.fill(Qt.red)
    assert pix.save(path, "PNG"), f"failed to write fixture logo at {path}"
```

New tests that need a source logo call `_write_logo(abs_source_path)`. Tests for `_is_thumb_fresh` also need `_write_logo` to write a thumb PNG at a known mtime.

#### New import additions for `test_art_paths.py`

```python
# Add to existing imports:
import time
from musicstreamer.ui_qt._art_paths import (
    FALLBACK_ICON,
    load_station_icon,
    _thumb_path_for,      # new helper
    _is_thumb_fresh,      # new helper
    _generate_thumb,      # new helper
)
```

---

### `tests/test_station_thumb_async.py` (test, new file)

**Analog:** `tests/test_gbs_marquee.py` lines 229–350 — pattern for testing daemon-thread Signal delivery via `QTest.qWait()`.

#### QApplication singleton pattern — from `test_gbs_marquee.py` lines 229–236

```python
# test_gbs_marquee.py lines 229–236
def _get_qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app
```

Copy this helper verbatim into `test_station_thumb_async.py`. Required because `StationTreeModel` (a `QAbstractItemModel`) and Signal delivery need a running `QApplication`.

#### QTest.qWait pattern — from `test_gbs_marquee.py` lines 239–275

```python
# test_gbs_marquee.py lines 249–261 — wait for QueuedConnection delivery
from PySide6.QtTest import QTest
worker = GbsMarqueeWorker()
try:
    worker.start()
    worker.set_cadence(60_000)
    QTest.qWait(200)  # allow QueuedConnection delivery
    assert worker.current_interval_ms() == 60_000
finally:
    worker.stop_and_wait(timeout_ms=3_000)
```

For `test_station_thumb_async.py`, the pattern is `QTest.qWait(500)` — daemon threads writing a PNG are slower than an in-process Signal bridge, so use a larger wait (500ms) than the cadence tests (200ms). After `qWait`, assert that `dataChanged` was emitted.

To capture `dataChanged` emissions in a test:

```python
emissions = []
model.dataChanged.connect(lambda tl, br, roles: emissions.append((tl, br, roles)))
# ... trigger thumb miss path ...
QTest.qWait(500)
assert len(emissions) == 1
top_left, bottom_right, roles = emissions[0]
assert top_left == bottom_right  # single row
assert Qt.DecorationRole in roles
```

#### Conftest fixtures reused by `test_station_thumb_async.py`

```python
# tests/conftest.py lines 22–32 — autouse _stub_bus_bridge (already applies)
# tests/conftest.py line 14 — QT_QPA_PLATFORM=offscreen (already applies)
```

No additional conftest changes needed. The `_stub_bus_bridge` autouse fixture applies to all tests; `QT_QPA_PLATFORM=offscreen` is set at module level.

Additional fixtures to replicate from `test_station_icon_integration.py` lines 77–87:

```python
# test_station_icon_integration.py lines 77–87 — (replicate in test_station_thumb_async.py)
@pytest.fixture(autouse=True)
def _isolate_pixmap_cache():
    QPixmapCache.clear()
    yield
    QPixmapCache.clear()

@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    return str(tmp_path)
```

And replicate `_make_station` from `test_station_icon_integration.py` lines 39–51 to build `Station` objects with all required fields.

---

## Shared Patterns

### Thread-safety rule: QImage in worker, QPixmap on main thread
**Source:** `musicstreamer/gbs_marquee.py` line 468 (CR-01 annotation)
**Apply to:** `_generate_thumb` (worker) and `_on_thumb_landing` (main-thread slot)

```python
# gbs_marquee.py line 468 — the rule, annotated
themed_logo_ready = Signal(object)   # raw PNG bytes — CR-01: NO QPixmap off the GUI thread; main-thread slot decodes
```

Worker: use `QImage(source_path).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)` and `QImage.save(tmp_path, 'PNG')`. Signal payload: file path string. Main-thread slot: `QPixmap(thumb_path)`.

### QPixmapCache key scheme
**Source:** `musicstreamer/ui_qt/_art_paths.py` lines 75–76 and `musicstreamer/ui_qt/edit_station_dialog.py` lines 1321–1325
**Apply to:** `load_station_icon` (cache insert), `_on_thumb_landing` (cache eviction)

```python
# Key is always keyed on the full-res SOURCE path, not the thumb path:
key = f"station-logo:{abs_path or FALLBACK_ICON}"
# Eviction in _on_thumb_landing:
QPixmapCache.remove(f"station-logo:{source_abs_path}")
```

Both the loader and the invalidation path in `edit_station_dialog` already use this key. Phase 94 must not change the key scheme — changing it would break existing invalidation.

### In-flight dedup guard
**Source:** no direct analog — this is new state. But pattern mirrors `gbs_marquee.py`'s `_themed_day_detected_this_session` boolean guard (single QObject affinity, no lock needed on main thread).
**Apply to:** `StationTreeModel._request_thumb`

```python
# _in_flight_thumbs is a plain set[int] with main-thread-only access.
# No lock required: _request_thumb is always called from load_station_icon
# which is called from data() which runs on the main thread.
if station_id in self._in_flight_thumbs:
    return
self._in_flight_thumbs.add(station_id)
```

### Atomic write
**Source:** `musicstreamer/desktop_install.py` lines 187–210
**Apply to:** `_generate_thumb` (inside `_worker` closure)

```python
# desktop_install.py lines 200–210 — atomic write idiom
fd, tmp_path = tempfile.mkstemp(dir=thumb_dir, suffix='.thumb.tmp.png')
try:
    os.close(fd)
    if scaled.save(tmp_path, 'PNG'):
        os.replace(tmp_path, thumb_path)
        callback(station_id, source_path, thumb_path)
    else:
        callback(station_id, source_path, None)
except Exception:
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
    callback(station_id, source_path, None)
```

`mkstemp` creates the temp file in the same directory as the final thumb to guarantee same-filesystem rename (POSIX atomic). `os.replace` is atomic — reader sees either the old complete file or the new complete file, never a partial write.

---

## No Analog Found

No files in scope are entirely without an analog. All patterns have direct precedent in the codebase.

---

## Metadata

**Analog search scope:** `musicstreamer/`, `musicstreamer/ui_qt/`, `tests/`
**Files read:** 10 (6 source, 4 test)
**Pattern extraction date:** 2026-06-15

### Anti-patterns documented in analogs (planner must avoid)

| Anti-pattern | Evidence | Guard |
|---|---|---|
| `QPixmap(path)` off main thread | `gbs_marquee.py:468` CR-01 annotation | Worker uses `QImage` only; `QPixmap` created in `_on_thumb_landing` slot |
| `QPixmapCache.find/insert` off main thread | Qt architectural rule, confirmed in RESEARCH.md | Only called from main-thread `load_station_icon` and `_on_thumb_landing` slot |
| Storing `QModelIndex` across async boundary | RESEARCH.md Pitfall #3 | Store `station_id: int` in Signal payload; call `index_for_station_id()` in slot |
| Double-enqueue during fast scroll | RESEARCH.md Pitfall #2 | `_in_flight_thumbs` set checked before `_generate_thumb` call |
| Direct file write (`open(path, 'wb')`) | RESEARCH.md § Don't Hand-Roll | `mkstemp + os.replace` atomic pattern from `desktop_install.py` |
