# Phase 94: Sidebar Logo Thumbnail Optimization — Research

**Researched:** 2026-06-15
**Domain:** PySide6 QAbstractItemModel painting / async off-UI-thread thumbnail generation / mtime-based cache invalidation
**Confidence:** HIGH — all findings verified from live codebase inspection and authoritative Qt source

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Sidebar renders pre-scaled thumbnail; full-res `station_art` unchanged for Now Playing.
- **D-02:** Lazy generation on cache/file miss, written to disk. No migration.
- **D-03:** Async off-UI-thread generation. Row paints fallback immediately; worker generates thumbnail; row repaints when thumb lands. QPixmap is NOT safe off the main thread — worker builds QImage and/or writes PNG; UI thread converts to QPixmap, inserts into QPixmapCache, emits dataChanged.
- **D-04:** Single 96px on-disk thumbnail per station (covers 1x–3x HiDPI).
- **D-05:** Thumbnail stored at `assets/{station_id}/station_art.thumb.png`.
- **D-06:** Staleness via mtime check on load — regenerate if thumb missing OR older than source logo.

### Claude's Discretion
- Exact worker/threading mechanism (thread pool vs QThread vs reuse of existing pattern)
- Placeholder icon choice during async gap
- Precise QPixmapCache key scheme
- PNG encoding parameters

### Deferred Ideas (OUT OF SCOPE)
- DPR-aware multi-size thumbnails (@1x/@2x/@3x)
- Eager import-time generation + startup backfill warmer
</user_constraints>

---

## Summary

The scroll-jank root cause is confirmed in the live code: `StationTreeModel.data()` at line 164 calls `load_station_icon(node.station)` synchronously for every uncached `DecorationRole` request during paint. Inside `load_station_icon` (_art_paths.py lines 79–104), a QPixmapCache miss triggers `QPixmap(full_res_path)` — a full PNG decode — followed by a `SmoothTransformation` scale to 32px. On a fast scroll through a large list (DI.fm + AudioAddict = 500+ stations), each newly-exposed row pays this cost once on the UI thread. The QPixmapCache (default 10 MB) comfortably stores all 32px scaled results (a 32px RGBA pixmap is ~4 KB; 500 stations total ~2 MB, well under the 10 MB limit), so re-scrolling is fast. Only the first-pass sweep of uncached rows causes jank.

The fix: refactor `load_station_icon` to check for a 96px on-disk thumbnail (`station_art.thumb.png`), load it if fresh, or enqueue async generation if missing/stale. The worker runs on a daemon thread (matching `cover_art.py`'s established idiom), writes a PNG via `QImage.save()` (thread-safe), then emits a signal back to the UI thread via a `Signal` on `StationTreeModel`. The UI-thread slot converts the PNG to `QPixmap`, inserts into `QPixmapCache`, and calls `dataChanged` to trigger a repaint of the affected row.

**Primary recommendation:** Implement async lazy thumbnail generation in `_art_paths.py` and `station_tree_model.py`, using `threading.Thread(daemon=True)` (matching `cover_art.py`), with `Signal(int, str)` on `StationTreeModel` as the cross-thread delivery channel, and `QImage`-based scaling + atomic PNG write in the worker.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Thumbnail existence/staleness check | `_art_paths.py` (load path) | — | The loader already owns all path resolution logic |
| Thumbnail generation (CPU scaling) | Worker daemon thread | — | Must not block UI thread (root cause of jank) |
| Atomic PNG write to disk | Worker daemon thread | — | File I/O is thread-safe; write before signaling |
| QImage→QPixmap conversion | UI thread only | — | QPixmap is NOT thread-safe (Qt hard rule) |
| QPixmapCache insert | UI thread only | — | QPixmapCache is NOT thread-safe off main thread |
| dataChanged emit | `StationTreeModel` slot | — | Model owns notification; must happen after cache insert |
| In-flight dedup set | `StationTreeModel` | — | Needs QObject affinity for lock-free main-thread access |
| mtime comparison | `_art_paths.py` (load path) | — | One `os.stat()` per call, same function that does path resolution |
| Cache key management | `_art_paths.py` | — | Cache key stays as `station-logo:{abs_source_path}` |
| Now Playing full-res path | `now_playing_panel._load_scaled_pixmap` | — | UNCHANGED — separate code path, no QPixmapCache |

---

## Standard Stack

### Core (no new packages — all existing project dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `PySide6.QtCore.QAbstractItemModel` | ≥6.10 (project floor) | Model base; `dataChanged` signal | Already in use |
| `PySide6.QtCore.Signal` | ≥6.10 | Cross-thread result delivery | Established idiom (cover_art.py, gbs_marquee.py) |
| `PySide6.QtGui.QImage` | ≥6.10 | Off-thread image scaling + PNG save | Thread-safe unlike QPixmap |
| `PySide6.QtGui.QPixmap` | ≥6.10 | On-disk PNG → in-memory GPU pixmap (main thread only) | Existing cache layer |
| `PySide6.QtGui.QPixmapCache` | ≥6.10 | In-memory hot-path cache (main thread only) | Already the cache layer |
| `threading.Thread(daemon=True)` | stdlib | Worker thread spawning | Matches `cover_art.py` idiom exactly |
| `os.stat()` / `st_mtime` | stdlib | Mtime comparison for staleness | Cheap, cross-platform |
| `tempfile.mkstemp` + `os.replace` | stdlib | Atomic PNG write | Matches `cookie_utils.py`/`desktop_install.py` idiom |

### No new packages needed. This phase adds no external dependencies.

## Package Legitimacy Audit

> Not applicable — phase introduces zero external packages.

---

## Architecture Patterns

### System Architecture Diagram

```
[Fast scroll — uncached rows]
        |
        v
StationTreeModel.data(DecorationRole)
        |
        v
load_station_icon(station)   ← entry point in _art_paths.py
        |
        +--[QPixmapCache HIT]--> return cached QIcon (fast, no change)
        |
        +--[MISS]
              |
              +--[thumb file present AND fresher than source]
              |       |
              |       v
              |   QPixmap(thumb_path) → paint HiDPI canvas → QPixmapCache.insert → return QIcon
              |   (FAST PATH: 96px file decode vs full-res)
              |
              +--[thumb missing OR stale]
                      |
                      v
               return FALLBACK_ICON immediately
                      |
                      +--[station_id NOT in _in_flight_thumbs]
                              |
                              v
                    _in_flight_thumbs.add(station_id)
                    StationTreeModel._thumb_landing.emit bound as callback
                              |
                              v
                    threading.Thread(daemon=True)
                    target: _generate_thumb(source_path, thumb_path, station_id, callback)
                              |
                              v
                    [Worker thread]:
                    QImage(source_path)   ← thread-safe
                    .scaled(96,96, SmoothTransformation)
                    atomic write to thumb_path (mkstemp + os.replace)
                    callback(station_id, thumb_path)   ← calls Signal.emit cross-thread
                              |
                              v
                    [Qt queues to main thread]
                              |
                              v
                    StationTreeModel._on_thumb_landing(station_id, thumb_path)
                    _in_flight_thumbs.discard(station_id)
                    QPixmap(thumb_path) → paint HiDPI canvas
                    QPixmapCache.insert(key, pix)
                    idx = self.index_for_station_id(station_id)
                    if idx.isValid():
                        self.dataChanged.emit(idx, idx, [Qt.DecorationRole])
                              |
                              v
                    [Qt repaints the row — now shows real logo]
```

### Recommended Project Structure

No new top-level modules. Changes are contained in:
```
musicstreamer/ui_qt/
├── _art_paths.py          # PRIMARY: load_station_icon refactor + _generate_thumb + path helpers
├── station_tree_model.py  # Signal + slot for cross-thread delivery + index_for_station_id
└── (no other files changed)
```

Test files:
```
tests/
├── test_art_paths.py                  # Extend: thumb file fast path + mtime staleness
├── test_station_icon_integration.py   # Extend: thumb fast path visible in DecorationRole
└── test_station_thumb_async.py        # NEW: async generation + dataChanged delivery
```

### Pattern 1: Daemon Thread + Signal Emit (established project idiom)

Exactly mirrors `cover_art.py`'s `_itunes_attempt` pattern:

```python
# Source: musicstreamer/cover_art.py lines 108-128
def _itunes_attempt(icy_string, on_done):
    def _worker():
        try:
            ...do blocking I/O...
            on_done(temp_path)
        except Exception:
            on_done(None)
    threading.Thread(target=_worker, daemon=True).start()
```

For thumbnail generation:
```python
# In musicstreamer/ui_qt/_art_paths.py
def _generate_thumb(source_path: str, thumb_path: str, station_id: int,
                    callback) -> None:
    """Spawn daemon thread to generate 96px thumbnail and call callback on completion."""
    def _worker():
        try:
            img = QImage(source_path)
            if img.isNull():
                callback(station_id, None)
                return
            scaled = img.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # Atomic write: tmp in same dir + os.replace (POSIX atomic)
            thumb_dir = os.path.dirname(thumb_path)
            os.makedirs(thumb_dir, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=thumb_dir, suffix='.thumb.tmp.png')
            try:
                os.close(fd)
                if scaled.save(tmp_path, 'PNG'):
                    os.replace(tmp_path, thumb_path)
                    callback(station_id, thumb_path)
                else:
                    callback(station_id, None)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                callback(station_id, None)
        except Exception:
            callback(station_id, None)
    threading.Thread(target=_worker, daemon=True).start()
```

### Pattern 2: Signal on StationTreeModel for cross-thread delivery

Exactly mirrors `now_playing_panel.cover_art_ready` Signal + QueuedConnection pattern:

```python
# In musicstreamer/ui_qt/station_tree_model.py
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal

class StationTreeModel(QAbstractItemModel):
    # Cross-thread: worker emits this from daemon thread; Qt queues to main thread.
    # Signal(int, str | None) — station_id, thumb_path (None = generation failed)
    _thumb_landing = Signal(int, object)   # object avoids Optional[str] typing issues

    def __init__(self, stations, parent=None):
        super().__init__(parent)
        self._in_flight_thumbs: set[int] = set()  # station_ids with pending workers
        self._root = _TreeNode(kind="root", label="")
        self._populate(stations)
        # QueuedConnection ensures slot runs on main thread even if emitted from worker.
        self._thumb_landing.connect(self._on_thumb_landing, Qt.QueuedConnection)
```

### Pattern 3: Mtime staleness check

```python
# In load_station_icon, after resolving thumb_path from abs_source_path:
def _is_thumb_fresh(source_path: str, thumb_path: str) -> bool:
    """Return True if thumb exists and is newer than (or same mtime as) source."""
    try:
        thumb_mtime = os.stat(thumb_path).st_mtime
        source_mtime = os.stat(source_path).st_mtime
        return thumb_mtime >= source_mtime
    except OSError:
        return False  # Either file missing — regenerate
```

### Pattern 4: Atomic write (established project idiom)

Matches `desktop_install._atomic_copy` and `cookie_utils`:
- `tempfile.mkstemp(dir=same_dir, suffix='.tmp.png')` — ensures same filesystem
- `QImage.save(tmp_path, 'PNG')` — write to temp
- `os.replace(tmp_path, final_path)` — atomic rename (POSIX; on Windows also atomic for non-open files)
- On failure: `os.unlink(tmp_path)` — clean up

### Pattern 5: index_for_station_id lookup (O(N) walk — acceptable)

```python
# In StationTreeModel — mirrors station_list_panel.select_station pattern:
def index_for_station_id(self, station_id: int) -> QModelIndex:
    """Return the source model QModelIndex for the station with the given id, or invalid."""
    for prov_row in range(len(self._root.children)):
        prov_node = self._root.children[prov_row]
        for child_row, child_node in enumerate(prov_node.children):
            if child_node.station is not None and child_node.station.id == station_id:
                return self.createIndex(child_row, 0, child_node)
    return QModelIndex()
```

For DI.fm-scale lists (≤500 stations): O(N) walk costs ~microseconds. Not a bottleneck — this runs on the main thread AFTER the worker has finished, when the user is no longer actively scrolling (the jank-causing scroll is over before the thumb lands).

An O(1) `dict[int, _TreeNode]` map built in `_populate` would be a valid optimization but is NOT necessary for the phase goal.

### Anti-Patterns to Avoid

- **QPixmap off main thread:** `QPixmap(path)` or `QPixmap(width, height)` in the worker thread is undefined behavior. Use `QImage` in the worker; convert to `QPixmap` only in the `_on_thumb_landing` slot.
- **QPixmapCache off main thread:** `QPixmapCache.find/insert` called from the worker thread is not thread-safe. Only call from the main thread.
- **Blocking main thread during mtime check:** `os.stat()` is cheap (<10 µs on local disk) and acceptable inside `data()`. Do not replace with async stat.
- **Storing QModelIndex across async calls:** QModelIndex can be invalidated by model changes (e.g., `refresh()`). Never store one in the worker. Store `station_id` (int) and re-derive the index via `index_for_station_id` in the slot after the worker finishes.
- **Re-enqueuing during fast scroll:** Without the `_in_flight_thumbs` set, `data()` is called ~10× per station during fast scroll, each call spawning a new worker for the same station. Guard with the set.
- **Not using QueuedConnection:** Default connection type for a Signal emitted from a non-QThread daemon thread is auto-detected by Qt as QueuedConnection, but explicit `Qt.QueuedConnection` in `connect()` makes the intent clear and prevents surprising behavior if the architecture changes.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-thread signal delivery | Custom event queue or threading.Queue + QTimer poll | Qt Signal/QueuedConnection | Already proven in this codebase (cover_art, gbs_marquee) |
| Atomic file write | `open(path, 'wb').write(...)` directly | `mkstemp` + `os.replace` | Direct write can produce a torn file if interrupted mid-write |
| Image scaling | Manual pixel math | `QImage.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)` | Same smooth scaling already used for the full-res path |
| PNG encoding | Raw bytes construction | `QImage.save(path, 'PNG')` | Correct PNG headers, lossless, well-tested |

**Key insight:** This phase reuses exactly the threading/signaling idiom already established in `cover_art.py` (daemon thread + Signal emit callback) and `gbs_marquee.py` (QThread + Signal). No new patterns are needed.

---

## Common Pitfalls

### Pitfall 1: QPixmap constructed off the main thread (CR-01 class of bug)
**What goes wrong:** Worker calls `QPixmap(path)` — crash or black/null pixmap because Qt's paint backend is not initialized on worker threads.
**Why it happens:** Confusion between `QImage` (CPU pixel buffer, thread-safe) and `QPixmap` (GPU-backed, not thread-safe).
**How to avoid:** Worker creates and saves `QImage` only. Signal delivers `thumb_path` string (not a QPixmap). `_on_thumb_landing` slot constructs `QPixmap(thumb_path)` on the main thread.
**Evidence:** `gbs_marquee.py` line 468 CR-01 annotation: "raw PNG bytes — CR-01: NO QPixmap off the GUI thread; main-thread slot decodes."

### Pitfall 2: Duplicate workers per station during fast scroll
**What goes wrong:** Without `_in_flight_thumbs`, each paint call that triggers a `DecorationRole` miss spawns a new daemon thread for the same station. Hundreds of threads are created for a 180-station list scroll, all writing to the same `station_art.thumb.png`. Race condition on the file; excess CPU.
**Why it happens:** `data()` is called for each exposed row on every scroll event.
**How to avoid:** Before spawning a worker, check `station_id in self._in_flight_thumbs`. Add to set before spawn. Remove in `_on_thumb_landing` (on main thread, no lock needed).

### Pitfall 3: Stale QModelIndex stored across async boundary
**What goes wrong:** Worker captures `QModelIndex` at enqueue time. By the time it signals back, `model.refresh()` has been called (e.g., station added), invalidating the index. `dataChanged(invalid, invalid)` silently no-ops or crashes.
**Why it happens:** QModelIndex validity is tied to model lifetime state, not a persistent ID.
**How to avoid:** Store `station_id: int` across the async boundary. Call `index_for_station_id(station_id)` inside `_on_thumb_landing` on the main thread. Guard with `if idx.isValid()` before emitting `dataChanged`.

### Pitfall 4: dataChanged storm on startup
**What goes wrong:** If a user with 500 existing stations starts the app, all 500 thumbnails are generated on first display, and 500 `dataChanged` signals fire in rapid succession. Each `dataChanged` triggers at least one paint event. The view repaints for every arrival, potentially queuing 500 paint events.
**Why it happens:** First-pass scroll with no cached thumbnails.
**Why it's acceptable:** Thumbnail generation is spread over time (each station lands as its worker finishes). Repaints are batched by the Qt paint system. The goal is to eliminate the synchronous full-res decode per row, replacing it with a fallback icon + async repaint. The total user-visible effect is: first scroll shows fallback icons, then real logos pop in as workers finish. This is the agreed-upon behavior (D-03).
**If it becomes a problem:** Rate-limit workers with a semaphore (e.g., 4 concurrent). NOT needed for the phase goal.

### Pitfall 5: Thumbnail path for station with no station_art_path
**What goes wrong:** `load_station_icon` is called for a station with `station_art_path=None`. Code attempts to derive `thumb_path` from `abs_source_path = None` → `AttributeError`.
**How to avoid:** Early-return on `not abs_path` (already done in current code for the `load_path = abs_path or FALLBACK_ICON` pattern). The thumbnail fast path should only activate when `abs_path` is not None. `station_art_path=None` → fallback icon, no worker spawned.

### Pitfall 6: Torn thumbnail from concurrent writes
**What goes wrong:** Two workers for the same station_id both reach the `QImage.save` step (if the `_in_flight_thumbs` guard was bypassed). One writes a partial file while the other replaces it via `os.replace`.
**Why it doesn't happen with atomic write + dedup:** The `_in_flight_thumbs` guard prevents double-enqueue. `os.replace` is atomic — the final file is always either the old version or the new complete version, never partially-written content.

### Pitfall 7: load_station_icon cache key semantics
**Current key:** `f"station-logo:{abs_path or FALLBACK_ICON}"` where `abs_path` is the absolute path of the FULL-RES source logo.
**New behavior:** The cache entry is still keyed on the full-res source path, but is populated from the 96px thumbnail (on the fast path) or from the fallback during the async gap.
**Consistency:** `edit_station_dialog._invalidate_cache_for(rel_path)` removes `f"station-logo:{resolved}"` using the same source-path key. This correctly evicts the cached thumbnail-derived entry when the user swaps art — the next `data()` call will find no cache entry, check mtime (thumb is now stale because source was overwritten), and enqueue regen.

### Pitfall 8: now_playing_panel must not be affected
**What goes wrong:** `_load_scaled_pixmap` in `now_playing_panel.py` is accidentally changed or starts using the thumbnail path.
**How to avoid:** `_load_scaled_pixmap` is a standalone module-level function (not `load_station_icon`). It reads from `abs_art_path(path)` and does NOT use `QPixmapCache`. The two code paths are entirely separate. Add a source-grep drift-guard test asserting `_load_scaled_pixmap` does NOT reference `station_art.thumb`.

---

## Code Examples

### Refactored load_station_icon (main-thread entry point)

```python
# Source: _art_paths.py (to be written for Phase 94)
THUMB_FILENAME = "station_art.thumb.png"

def _thumb_path_for(abs_source_path: str) -> str:
    """Derive the 96px thumbnail path from the full-res source path.
    
    e.g. .../assets/12/station_art.png -> .../assets/12/station_art.thumb.png
    """
    return os.path.join(os.path.dirname(abs_source_path), THUMB_FILENAME)

def _is_thumb_fresh(source_path: str, thumb_path: str) -> bool:
    """Return True iff thumb exists and mtime >= source mtime."""
    try:
        return os.stat(thumb_path).st_mtime >= os.stat(source_path).st_mtime
    except OSError:
        return False

def load_station_icon(station, size: int = STATION_ICON_SIZE,
                      on_thumb_needed=None) -> QIcon:
    """Return a QPixmapCache-backed QIcon for station with fallback.
    
    New behavior (Phase 94):
        - If thumb present + fresh: loads 96px file (fast cold-start path).
        - If thumb missing/stale:   returns fallback immediately and calls
          on_thumb_needed(station_id, source_path, thumb_path) to enqueue
          async generation.
    
    on_thumb_needed: callable(station_id: int, source_path: str, thumb_path: str)
        Called from the main thread; caller (StationTreeModel) owns the worker
        lifecycle. Ignored if station has no station_art_path.
    """
    rel = getattr(station, "station_art_path", None)
    abs_path = abs_art_path(rel)
    load_path = abs_path or FALLBACK_ICON
    key = f"station-logo:{load_path}"

    pix = QPixmap()
    if not QPixmapCache.find(key, pix):
        # --- NEW Phase 94 logic ---
        if abs_path is not None:
            thumb_path = _thumb_path_for(abs_path)
            if _is_thumb_fresh(abs_path, thumb_path):
                src = QPixmap(thumb_path)
            else:
                # Async gap: return fallback, request generation
                if on_thumb_needed is not None and station.id is not None:
                    on_thumb_needed(station.id, abs_path, thumb_path)
                src = QPixmap(FALLBACK_ICON)
        else:
            src = QPixmap(FALLBACK_ICON)
        # --- END new logic; existing HiDPI canvas logic below is UNCHANGED ---
        if src.isNull():
            src = QPixmap(FALLBACK_ICON)
        scaled = src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pix = QPixmap(size, size)
        pix.setDevicePixelRatio(scaled.devicePixelRatio())
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        x = (size - scaled.width()) // 2
        y = (size - scaled.height()) // 2
        painter.drawPixmap(QPoint(x, y), scaled)
        painter.end()
        QPixmapCache.insert(key, pix)
    return QIcon(pix)
```

### StationTreeModel changes

```python
# Source: station_tree_model.py (to be written for Phase 94)
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal

class StationTreeModel(QAbstractItemModel):
    # Cross-thread delivery: worker (daemon thread) emits → main thread slot
    _thumb_landing = Signal(int, object)  # (station_id, thumb_path or None)

    def __init__(self, stations, parent=None):
        super().__init__(parent)
        self._in_flight_thumbs: set[int] = set()
        self._root = _TreeNode(kind="root", label="")
        self._populate(stations)
        # QueuedConnection: slot runs on main thread even when signal emitted from worker.
        self._thumb_landing.connect(self._on_thumb_landing, Qt.QueuedConnection)

    def data(self, index, role=Qt.DisplayRole):
        ...
        if role == Qt.DecorationRole and node.kind == "station":
            return load_station_icon(node.station,
                                     on_thumb_needed=self._request_thumb)
        ...

    def _request_thumb(self, station_id: int, source_path: str,
                       thumb_path: str) -> None:
        """Called from main thread by load_station_icon on cache/thumb miss."""
        if station_id in self._in_flight_thumbs:
            return
        self._in_flight_thumbs.add(station_id)
        emit = self._thumb_landing.emit  # bound Signal.emit — no self-capture
        _generate_thumb(source_path, thumb_path, station_id,
                        lambda sid, path: emit(sid, path))

    def _on_thumb_landing(self, station_id: int, thumb_path) -> None:
        """Slot — always runs on main thread via QueuedConnection."""
        self._in_flight_thumbs.discard(station_id)
        if thumb_path is None:
            return  # generation failed; fallback stays cached, no repaint needed
        # Evict the fallback/stale entry so next paint loads the new thumb.
        # The key is keyed on source path; we need to reconstruct it.
        # Simplest: no explicit removal — the key-based lookup in load_station_icon
        # will use the thumb on disk next time since _is_thumb_fresh passes.
        # But: the fallback is CURRENTLY cached under this key. We must evict it.
        # Approach: derive the source path from thumb_path (reverse of _thumb_path_for)
        # OR: store source_path alongside station_id in the Signal payload.
        # Use Signal(int, str, str) = (station_id, source_path, thumb_path):
        pass  # see note below — Signal carries source_path too

    def index_for_station_id(self, station_id: int) -> QModelIndex:
        """O(N) walk to find the QModelIndex for a station by id."""
        for prov_node in self._root.children:
            for child_row, child_node in enumerate(prov_node.children):
                if child_node.station is not None and child_node.station.id == station_id:
                    return self.createIndex(child_row, 0, child_node)
        return QModelIndex()
```

**Note on Signal payload:** The planner should use `Signal(int, str, str)` carrying `(station_id, source_path, thumb_path)` so `_on_thumb_landing` can reconstruct the cache key (`f"station-logo:{source_path}"`) to evict the stale fallback entry before inserting the new thumbnail entry. Alternatively, store `thumb_path` only and re-derive source_path as `thumb_path.replace('.thumb.png', '.png')` (fragile). The three-arg Signal is cleaner.

### Cache eviction in _on_thumb_landing

```python
def _on_thumb_landing(self, station_id: int, source_path: str,
                      thumb_path: str) -> None:
    self._in_flight_thumbs.discard(station_id)
    if not thumb_path:
        return
    # Evict stale fallback entry (currently cached with FALLBACK_ICON path or source_path)
    key = f"station-logo:{source_path}"
    QPixmapCache.remove(key)
    # The next data() call will reload from thumb (fast path). We need a repaint.
    idx = self.index_for_station_id(station_id)
    if idx.isValid():
        self.dataChanged.emit(idx, idx, [Qt.DecorationRole])
```

**Important:** After `QPixmapCache.remove(key)`, the next `data()` call for this row will hit `load_station_icon` again — which will find the thumb on disk, load it via QPixmap, and re-insert under the same key. The `dataChanged` emit is what triggers that next `data()` call.

---

## Runtime State Inventory

> Phase is greenfield in terms of stored state — no rename/migration.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | No `station_art.thumb.png` files exist yet (thumbnails are generated on demand) | None — self-healing lazy generation |
| Live service config | None | None |
| OS-registered state | None | None |
| Secrets/env vars | None | None |
| Build artifacts | None | None |

**Nothing found in any category** — confirmed by codebase search showing no existing thumb files or migration state.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Load full-res PNG per uncached row during paint | Pre-scaled 96px thumb, async generation on miss | Phase 94 | Eliminates full-res decode on UI thread during fast scroll |
| Synchronous decode in DecorationRole | Fallback immediately + async repaint | Phase 94 | First-pass scroll stays smooth at the cost of a brief fallback icon flash |

**Deprecated/outdated (after this phase):**
- Calling `QPixmap(full_res_path)` inside `load_station_icon` when a fresh 96px thumb exists on disk.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x + pytest-qt 4.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/python -m pytest tests/test_art_paths.py tests/test_station_icon_integration.py tests/test_station_thumb_async.py -x -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ -x -q` |

**Note from project MEMORY.md:** Run tests with `.venv/bin/python -m pytest`, NOT `python3 -m pytest` or system Python — system python3 lacks PySide6.QtWidgets and produces false failures. Full suite takes >600s; scope to phase-relevant files during development.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| D-02 (lazy gen) | `load_station_icon` returns fallback when no thumb, enqueues generation | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_thumb_missing_returns_fallback -x` | ❌ Wave 0 |
| D-02 (disk write) | Worker writes valid PNG to `station_art.thumb.png` | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_generate_thumb_writes_png -x` | ❌ Wave 0 |
| D-03 (async repaint) | `dataChanged` emitted after thumb lands | integration | `.venv/bin/python -m pytest tests/test_station_thumb_async.py::test_thumb_landing_emits_datachanged -x` | ❌ Wave 0 |
| D-04 (96px size) | Generated thumb is ≤96px on longest axis | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_thumb_is_96px -x` | ❌ Wave 0 |
| D-05 (path) | Thumb lives at `assets/{id}/station_art.thumb.png` | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_thumb_path_derivation -x` | ❌ Wave 0 |
| D-06 (mtime) | Fresh thumb skips regen; stale thumb re-enqueues | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_thumb_freshness_check -x` | ❌ Wave 0 |
| D-01 (now_playing unchanged) | `_load_scaled_pixmap` does NOT reference `station_art.thumb` | drift-guard | `.venv/bin/python -m pytest tests/test_station_thumb_async.py::test_now_playing_panel_does_not_use_thumb -x` | ❌ Wave 0 |
| D-03 (dedup) | Same station not enqueued twice | unit | `.venv/bin/python -m pytest tests/test_station_thumb_async.py::test_in_flight_dedup -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** Quick run (art_paths + station_icon_integration + station_thumb_async)
- **Per wave merge:** Full suite
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_art_paths.py` — extend: thumb path derivation, freshness check, 96px size, miss/stale behavior (5 new tests)
- [ ] `tests/test_station_thumb_async.py` — NEW: async generation, dataChanged emit, in-flight dedup, drift-guard for now_playing (4 new tests)

*(Existing `tests/test_station_icon_integration.py` passes unchanged — the fallback behavior is preserved when no thumb exists.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | partial | Source image path is derived from DB-stored `station_art_path`; path traversal not possible since `abs_art_path()` roots relative paths under `paths.data_dir()` |
| V6 Cryptography | no | — |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Thumbnail path traversal | Tampering | Thumb path is always `os.path.dirname(abs_art_path) / THUMB_FILENAME`; abs_art_path is already trusted (see abs_art_path docstring) |
| Worker writing to unintended path | Tampering | `thumb_path` is fully derived from source path at main-thread call time; worker receives the already-computed path |
| Torn thumbnail file visible to renderer | Info disclosure | `mkstemp + os.replace` atomic write prevents partial-write visibility |

---

## Open Questions (RESOLVED)

1. **Signal arity: `(int, str, str)` vs `(int, str)`** — **RESOLVED:** three-arg `Signal(int, str, str)` emitting `(station_id, source_path, thumb_path)`. Locked into Plan 94-03 (`must_haves.artifacts` + Task 1 action) and PATTERNS.md.
   - What we know: `_on_thumb_landing` needs `station_id` to look up the model index, and either `source_path` (to compute cache key) or `thumb_path` (to load the pixmap).
   - Why: three-arg avoids fragile string surgery on the `.thumb.png` suffix when reconstructing the `station-logo:{source_path}` cache key for eviction.

2. **favorites_view.py and station_list_panel.py also call `load_station_icon`** — **RESOLVED:** no changes needed at those call sites for the phase goal (confirmed in Plan 94-02 Task 2 behavior — 2-arg callers preserved unchanged).
   - What we know: `favorites_view.py:153` and `station_list_panel.py:495` call `load_station_icon` during `_populate_stations()` (not during paint); they do not pass `on_thumb_needed`.
   - Why: the primary jank surface is `StationTreeModel.data()` (DecorationRole during paint). Populate-time callers are invoked once, not during scroll, and benefit from the thumbnail automatically on subsequent cache hits once a thumb exists.

---

## Environment Availability

> This phase has no external dependencies beyond the existing project stack.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PySide6 (QImage, QPixmap, Signal) | Core implementation | ✓ | ≥6.10 (project floor) | — |
| pytest-qt | Tests | ✓ | ≥4 (pyproject.toml) | — |
| `.venv/bin/python` | Test runner | ✓ | confirmed at `.venv/bin/python` | system Python3 (false failures — DO NOT USE) |

---

## Sources

### Primary (HIGH confidence — verified from live codebase)
- `musicstreamer/ui_qt/_art_paths.py` lines 48–105 — `load_station_icon` full implementation, cache key, HiDPI canvas logic
- `musicstreamer/ui_qt/station_tree_model.py` lines 155–174 — `data()` calling `load_station_icon` at DecorationRole
- `musicstreamer/cover_art.py` lines 91–128 — daemon thread + callback idiom (established project pattern)
- `musicstreamer/gbs_marquee.py` lines 437–644 — QThread + Signal(object) cross-thread delivery (CR-01 annotation)
- `musicstreamer/ui_qt/now_playing_panel.py` lines 204–216, 2103–2139 — `_load_scaled_pixmap` (must stay unchanged) + Signal emit callback pattern
- `musicstreamer/ui_qt/edit_station_dialog.py` lines 1321–1325 — `_invalidate_cache_for` (existing cache eviction on art change)
- `musicstreamer/desktop_install.py` lines 187–210 — `_atomic_copy` (mkstemp + os.replace pattern)
- `tests/test_art_paths.py` — existing test infrastructure for `load_station_icon`
- `tests/test_station_icon_integration.py` — StationTreeModel DecorationRole test patterns
- `tests/conftest.py` — `QT_QPA_PLATFORM=offscreen`, `_stub_bus_bridge` autouse fixture
- `tests/test_gbs_marquee.py` lines 229–350 — QThread Signal testing with `_get_qapp()` + `QTest.qWait()`

### Verified by tool call
- `QPixmapCache.cacheLimit()` = 10240 KB (10 MB) — [VERIFIED: live .venv Python invocation]
- `QImage.scaled(96, 96)` + `QImage.save(..., 'PNG')` work correctly off main thread — [VERIFIED: live .venv Python invocation]
- `QPixmap(path)` works correctly on main thread from a QImage-written PNG — [VERIFIED: live .venv Python invocation]
- mtime comparison via `os.stat().st_mtime` — sub-millisecond resolution, sufficient for staleness detection — [VERIFIED: live .venv Python invocation]

### Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | DI.fm + AA 6 networks ≈ 500 stations is the expected "large list" scale | Summary | If much larger (>2500), O(N) `index_for_station_id` walk costs >1ms — add dict map |
| A2 | `QPixmapCache.remove(key)` + subsequent `dataChanged` triggers a re-query of `data()` | Code Examples | If Qt batches / skips the repaint, thumb never shows — verify in integration test |

**If this table is empty otherwise:** All other claims in this research were verified or cited directly from the live codebase.

---

## Metadata

**Confidence breakdown:**
- Root cause diagnosis: HIGH — code confirmed at `station_tree_model.py:164` and `_art_paths.py:80`
- Threading pattern: HIGH — matches established `cover_art.py` and `gbs_marquee.py` idioms
- QImage thread-safety: HIGH — verified by live Python invocation off main thread
- QPixmap/QPixmapCache main-thread-only: HIGH — confirmed by `gbs_marquee.py` CR-01 annotation + Qt architectural rule
- Mtime check: HIGH — verified by live Python invocation
- Atomic write pattern: HIGH — matches `desktop_install._atomic_copy` idiom
- dataChanged → repaint chain: MEDIUM — standard Qt model behavior, but verify in integration test (A2)

**Research date:** 2026-06-15
**Valid until:** 2026-07-15 (30 days; PySide6 6.10+ stable APIs)
