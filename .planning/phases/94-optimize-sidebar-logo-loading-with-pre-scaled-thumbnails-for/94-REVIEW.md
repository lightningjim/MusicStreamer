---
phase: 94-optimize-sidebar-logo-loading-with-pre-scaled-thumbnails-for
reviewed: 2026-06-15T00:00:00Z
depth: deep
files_reviewed: 5
files_reviewed_list:
  - musicstreamer/ui_qt/_art_paths.py
  - musicstreamer/ui_qt/station_tree_model.py
  - tests/test_art_paths.py
  - tests/test_station_thumb_async.py
  - tests/test_station_icon_integration.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 94: Code Review Report

**Reviewed:** 2026-06-15T00:00:00Z
**Depth:** deep
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 94 introduces a 96px pre-scaled thumbnail fast path for the sidebar station list, with async daemon-thread generation, a `SimpleQueue + QTimer` bridge for cross-thread delivery, and a QPixmapCache eviction/repaint cycle. The overall architecture is sound: the thread-safety boundary is correctly drawn (QImage-only in the worker, QPixmap only on the main thread), the dedup guard prevents duplicate spawns, and the cache eviction key matches the insert key. The `refresh()` + in-flight race is handled gracefully via `set.discard()` and `index_for_station_id()` re-derivation.

One genuine resource-leak bug was found in `_generate_thumb`: orphaned temp files when `QImage.save()` returns `False` without raising an exception. Three warning-level issues cover a duplicate comment block left by refactoring, a HiDPI quality degradation introduced by this phase, and a timing-dependent test assertion. Two info items address test coverage gaps and a minor inline-comment inconsistency.

---

## Critical Issues

### CR-01: Temp file leaked when `QImage.save()` returns `False`

**File:** `musicstreamer/ui_qt/_art_paths.py:112-116`

**Issue:** `tempfile.mkstemp()` creates a file at line 109 and the FD is closed at line 111. If `scaled.save(tmp, "PNG")` returns `False` (a documented non-exception failure — e.g., disk full, unsupported format, Qt internal error), execution falls to the `else` branch at line 115 which calls `callback(station_id, source_path, None)` and returns. The `try/except Exception` block on line 117 is never entered, so the cleanup at line 119 (`os.unlink(tmp)`) is skipped. The temp file (`*.thumb.tmp.png` in the same directory as the source art) is orphaned on disk indefinitely.

The exception path (lines 117-122) correctly unlinks the temp file, but `QImage.save()` does not raise on failure — it returns `bool`. This means every save failure silently leaves a `.thumb.tmp.png` file in the station art directory.

**Fix:**
```python
fd, tmp = tempfile.mkstemp(dir=thumb_dir, suffix=".thumb.tmp.png")
try:
    os.close(fd)
    if scaled.save(tmp, "PNG"):
        os.replace(tmp, thumb_path)
        callback(station_id, source_path, thumb_path)
    else:
        # save() returns bool on failure — not an exception — so the
        # except block below is not reached. Clean up explicitly.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        callback(station_id, source_path, None)
except Exception:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    callback(station_id, source_path, None)
```

---

## Warnings

### WR-01: Duplicate comment block in `StationTreeModel.__init__`

**File:** `musicstreamer/ui_qt/station_tree_model.py:50-53`

**Issue:** Lines 50-53 contain two consecutive near-identical comment blocks describing `_in_flight_thumbs`. The first (lines 50-51) says "called from data() and slot"; the second (lines 52-53) says "called from data() and _poll_pending_landings". This is an editing artifact — one version was from before the SimpleQueue bridge was added, the other from after — and neither was removed. The contradictory comments will confuse future maintainers trying to understand the concurrency invariants.

```
50        # Dedup guard: station ids currently being processed by a daemon worker.
51        # Access is main-thread-only (called from data() and slot); no lock needed.
52        # Dedup guard: station ids currently being processed by a daemon worker.
53        # Access is main-thread-only (called from data() and _poll_pending_landings); no lock needed.
```

**Fix:** Remove lines 50-51 (the stale first copy). Keep lines 52-53 which correctly names `_poll_pending_landings` as the second access site.

---

### WR-02: Thumbnail fast path degrades icon quality on HiDPI displays

**File:** `musicstreamer/ui_qt/_art_paths.py:182`

**Issue:** When the 96px thumb fast path is taken, `src = QPixmap(thumb_path)` loads a PNG that was written from a `QImage` with no device pixel ratio marker. Qt loads it with `devicePixelRatio() == 1.0`. After scaling to `size × size` logical pixels, the code propagates this DPR=1.0 to the output canvas via `pix.setDevicePixelRatio(scaled.devicePixelRatio())` (line 216).

On a 2× HiDPI screen (Wayland fractional, macOS Retina, Windows 1.5×/2×), the icon cell is `size × size` logical = `2*size × 2*size` physical pixels, but the pixmap has only `size × size` physical pixels. Qt upscales it 2× with nearest-neighbor or bilinear interpolation, producing a visibly blurry logo. The legacy synchronous path (`QPixmap(load_path)` for a source PNG, or `QPixmap(FALLBACK_ICON)` for an SVG) does not have this problem because the source pixmap inherits the screen DPR or is an SVG rendered at native resolution.

This phase introduced a quality regression for the majority of users on HiDPI hardware whenever a thumbnail is served from the fast path.

**Fix (short-term):** In `_generate_thumb`, scale to `96 * ceil(max_screen_dpr)` rather than a fixed 96px, so the thumb has enough physical pixels for 2× screens. The DPR cannot easily be passed to the daemon worker (it's a QScreen query), but the maximum screen DPR could be captured on the main thread before spawning and passed as a parameter.

**Fix (long-term):** Follow Qt's `@2x` file convention: generate a second thumb at `192 × 192` px with `@2x` in the filename, load it when screen DPR ≥ 1.5, and set its DPR=2.0. Or generate only the `@2x` thumb and always set `pix.setDevicePixelRatio(2.0)`.

---

### WR-03: `test_thumb_landing_emits_datachanged` relies on a 500ms hard timeout

**File:** `tests/test_station_thumb_async.py:129`

**Issue:** The test uses `QTest.qWait(500)` and then asserts `len(emissions) == 1`. The 500ms timeout assumes that a daemon thread will: load a 64×64 PNG via `QImage`, scale it, write a temp file, atomically replace it, push to the queue, wait for a 10ms timer tick, emit a signal, and deliver a QueuedConnection slot — all within 500ms. On a CI host under memory pressure (especially relevant given the project's known frozen-build environment issues), this timeout may not be reliable.

A flaky "exactly 1 emission" assertion is particularly dangerous: if the daemon thread takes >500ms, the assertion will see 0 emissions and fail with an obscure message that looks like a functional regression.

**Fix:** Replace the fixed timeout with a polling loop or use `qtbot.waitSignal`:
```python
with qtbot.waitSignal(model.dataChanged, timeout=5000) as blocker:
    model.data(station_idx, Qt.DecorationRole)

assert len(emissions) == 1
```
Alternatively, use `qtbot.waitUntil(lambda: len(emissions) >= 1, timeout=5000)` after triggering, which gives a 5s window and fails with a clear timeout message.

---

## Info

### IN-01: No test for cache hit suppressing repeated `on_thumb_needed` calls after generation failure

**File:** `tests/test_art_paths.py` (missing test)

**Issue:** When `_generate_thumb` fails (callback called with `None`), `_on_thumb_landing` discards `station_id` from `_in_flight_thumbs` but does NOT evict the cache entry (the fallback pixmap cached under `source_path` key from the initial miss). Subsequent `data()` calls hit that cache entry and `on_thumb_needed` is never called again — so a station with a permanently unwritable or corrupted source image will silently show the fallback forever, with no retry.

This behavior is arguably correct (no retry loop) but there is no test exercising: (a) the failure path reaching the permanent-fallback-cache state, or (b) that on_thumb_needed is not called on second data() invocation after failure. If a future refactor accidentally evicts the cache entry on failure, it would cause an infinite retry loop with no test to catch it.

**Fix:** Add a test that patches `_generate_thumb` to call back with `None`, then calls `load_station_icon` twice and asserts `on_thumb_needed` spy is called exactly once across both invocations.

---

### IN-02: Inline comment tracking number in `_art_paths.py` conflicts with module-level doc numbering

**File:** `musicstreamer/ui_qt/_art_paths.py:89`

**Issue:** The docstring at line 89 reads `CR-01: the worker uses QImage only...`. In this codebase's review convention, `CR-01` is a code-review finding ID. The usage here as an inline implementation note creates ambiguity — a future reviewer seeing `CR-01` may search for a code review report where this was a critical finding, rather than treating it as a rationale note. The `station_tree_model.py` uses the same prefix on line 43 (`CR-01: NO QPixmap off the GUI thread`).

**Fix:** Replace with a decision reference consistent with the phase-doc conventions already used elsewhere in the file (e.g., `# Thread-safety invariant (D-02): worker uses QImage only...` and `# Thread-safety note (D-02): QPixmap is not thread-safe — QImage only in worker.`).

---

_Reviewed: 2026-06-15T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
