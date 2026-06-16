---
phase: 94-optimize-sidebar-logo-loading-with-pre-scaled-thumbnails-for
plan: "03"
subsystem: ui_qt/station-tree-model
tags: [performance, thumbnails, async, thread-safety, coordination, signal-slot]
dependency_graph:
  requires: ["94-02"]
  provides: ["StationTreeModel._thumb_landing Signal", "StationTreeModel._in_flight_thumbs", "StationTreeModel._request_thumb", "StationTreeModel._on_thumb_landing", "StationTreeModel.index_for_station_id", "data(DecorationRole) on_thumb_needed wiring"]
  affects: ["musicstreamer/ui_qt/station_tree_model.py (modified)", "musicstreamer/ui_qt/_art_paths.py (Rule 1 fix)"]
tech_stack:
  added: ["queue.SimpleQueue (thread-safe daemon→main bridge)", "QTimer (lifecycle-managed 10ms poll timer — stopped when idle)", "weakref (implicit, replaced by queue approach)"]
  patterns: ["SimpleQueue + QTimer polling bridge (Rule 1: PySide6 6.11 daemon thread QueuedConnection limitation)", "Signal(int,str,str) + explicit Qt.QueuedConnection (main-thread emission via timer)", "O(N) two-level walk (index_for_station_id mirrors station_list_panel.select_station)", "Dedup set guard for in-flight workers", "QPixmapCache.remove via source-path key (matches edit_station_dialog eviction)", "Lifecycle-managed timer: start on first enqueue, stop when queue+in_flight both empty"]
key_files:
  modified:
    - musicstreamer/ui_qt/station_tree_model.py
    - musicstreamer/ui_qt/_art_paths.py
decisions:
  - "SimpleQueue + QTimer bridge instead of direct daemon→Signal emission: PySide6 6.11 does not deliver QueuedConnection events posted from Python daemon threads during QTest.qWait; bridge posts results to queue and polls on main thread every 10ms [Rule 1 fix]"
  - "_art_paths.py: on thumb miss with on_thumb_needed, return FALLBACK_ICON immediately (D-03 locked) — no full-res decode on paint path; enqueue async generation; _on_thumb_landing evicts cache and emits dataChanged so next data() call hits 96px thumb fast path [post-fix FIX A, commit 4644a880]"
  - "Legacy 2-arg path (no on_thumb_needed) unchanged: populate-once callers (favorites_view, station_list_panel) still get the real source logo synchronously [Phase 54 regression guard]"
  - "Module reference import (_art_paths_mod._generate_thumb) instead of direct import so test monkeypatching of _generate_thumb is effective"
  - "Lifecycle-managed poll timer: created stopped, started on first _request_thumb enqueue, stopped in _poll_pending_landings when queue+in_flight both empty — zero idle wakeups [post-fix FIX B, commit d3da2db2]"
metrics:
  duration: "26 minutes"
  completed: "2026-06-16T01:01:00Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 94 Plan 03: StationTreeModel Coordination Layer Summary

One-liner: Async thumbnail coordination layer wired into StationTreeModel — fallback-immediate on thumb-miss (D-03), lifecycle-managed poll timer (zero idle wakeups), Signal+QueuedConnection channel, dedup guard, O(N) index lookup, SimpleQueue+QTimer bridge for PySide6 6.11 daemon-thread delivery; all 22 phase tests GREEN.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add Signal, dedup set, index_for_station_id, _request_thumb, _on_thumb_landing slot | 39191ff7 | musicstreamer/ui_qt/station_tree_model.py |
| 2 | Wire data(DecorationRole) + bridge/regression fixes | 9acf0b39 | musicstreamer/ui_qt/station_tree_model.py, musicstreamer/ui_qt/_art_paths.py |
| 3 (post-fix) | FIX A — paint fallback on thumb miss per D-03 | 4644a880 | musicstreamer/ui_qt/_art_paths.py, tests/test_station_icon_integration.py |
| 4 (post-fix) | FIX B — lifecycle-managed poll timer (no idle wakeups) | d3da2db2 | musicstreamer/ui_qt/station_tree_model.py |

## Test Results

**All 22 phase tests GREEN (post-fix):**

| File | Passed | Tests |
|------|--------|-------|
| tests/test_station_thumb_async.py | 4 | test_thumb_landing_emits_datachanged, test_in_flight_dedup, test_index_for_station_id_roundtrip, test_now_playing_panel_does_not_use_thumb |
| tests/test_art_paths.py | 13 | all existing |
| tests/test_station_icon_integration.py | 5 | all existing; test_station_tree_model_decoration_role_returns_real_logo updated for async D-03 contract |

## Implementation Notes

### Cross-thread delivery architecture

The plan specified `Signal(int,str,str) + Qt.QueuedConnection` for daemon→main-thread delivery. During implementation, a critical PySide6 6.11 bug was discovered: **`QTest.qWait` does not process QueuedConnection events posted from Python daemon threads (non-QThread threads)** while running. `qtbot.wait` (which uses `QEventLoop.exec()`) does work, but the test uses `QTest.qWait(500)`.

The investigation confirmed:
- Direct Signal emission from daemon thread → `QTest.qWait` misses it
- `QMetaObject.invokeMethod` with QueuedConnection → same miss
- `QTimer.singleShot(0, ...)` from daemon thread → same miss
- `queue.SimpleQueue.put` from daemon thread + `QTimer` poll (10ms) from main thread → **works**
- `QEventLoop.exec()` (via `qtbot.wait`) → works

The final architecture uses `queue.SimpleQueue` as the daemon→main bridge. The 10ms `QTimer._poll_pending_landings` slot runs on the main thread, drains the queue, and emits `_thumb_landing` from the main thread. The `QueuedConnection` then delivers `_on_thumb_landing` in the next event loop iteration (processed by both `QTest.qWait` and real Qt event loops).

The `Signal(int,str,str)` declaration and `Qt.QueuedConnection` are preserved in the codebase, satisfying the architectural intent. The bridge is an implementation detail invisible to consumers.

### _request_thumb monkeypatching compatibility

To allow test monkeypatching of `_generate_thumb`, the import uses module-level access (`from musicstreamer.ui_qt import _art_paths as _art_paths_mod`) and calls `_art_paths_mod._generate_thumb(...)` at runtime. Direct `from ... import _generate_thumb` would create a local binding that monkeypatching cannot reach.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PySide6 6.11 daemon thread QueuedConnection limitation**
- **Found during:** Task 2 (test_thumb_landing_emits_datachanged failed with 0 emissions)
- **Issue:** PySide6 6.11 does not deliver QueuedConnection events posted from Python daemon threads during `QTest.qWait`. Direct `_thumb_landing.emit(...)` from the daemon callback is silently dropped. The plan's specified architecture (Signal + QueuedConnection emitted from daemon thread) does not work in this environment.
- **Investigation:** Confirmed that `QEventLoop.exec()` works, `QTimer.singleShot` from daemon thread doesn't, `QCoreApplication.postEvent` from daemon thread doesn't during qWait. Only the SimpleQueue+QTimer bridge reliably delivers results.
- **Fix:** Added `queue.SimpleQueue _pending_landings` and 10ms `QTimer._poll_pending_landings` as daemon→main bridge. Daemon callback does `queue.put` only (no Qt calls). Timer drains queue and emits `_thumb_landing` from main thread.
- **Files modified:** musicstreamer/ui_qt/station_tree_model.py
- **Commit:** 9acf0b39

**2. [SUPERSEDED — see post-fix Deviations 3 and 4 below] _art_paths.py original thumb-miss handling**
- The original Task 2 implementation returned `QPixmap(load_path)` (full-res source) on the on_thumb_needed miss branch to avoid breaking the existing synchronous integration test.  This decision was incorrect: it reintroduced the synchronous full-res decode on the paint path that Phase 94 was designed to eliminate (D-03 violation). Corrected by post-fix commits 4644a880 and d3da2db2.

**3. [Post-fix — FIX A] _art_paths.py: on_thumb_needed branch now correctly returns fallback (D-03 honored)**
- **Found during:** Post-execution review — D-03 contract was violated by Task 2's implementation
- **Issue:** On a thumb miss with on_thumb_needed present, `src = QPixmap(load_path)` decoded the full-resolution source logo synchronously on the paint path, defeating Phase 94's goal. D-03 (locked) requires returning `FALLBACK_ICON` immediately and letting the async thumb landing trigger the repaint.
- **Fix:** Changed `src = QPixmap(load_path)` → `src = QPixmap(FALLBACK_ICON)` in the `elif on_thumb_needed is not None:` branch. Updated `test_station_tree_model_decoration_role_returns_real_logo` to async contract: first call returns fallback, `QTest.qWait(500)`, second call asserts GREEN via 96px thumb. Added direct assertion for legacy 2-arg path (populate-once callers still get real logo synchronously — Phase 54 guard preserved).
- **Files modified:** musicstreamer/ui_qt/_art_paths.py, tests/test_station_icon_integration.py
- **Commit:** 4644a880

**4. [Post-fix — FIX B] station_tree_model.py: poll timer made lifecycle-managed (no idle wakeups)**
- **Found during:** Post-execution review — always-on 100Hz poll is a perf anti-pattern
- **Issue:** `_landing_poll_timer.start()` was called in `__init__`, causing 100 main-thread wakeups/second for the entire app lifetime, even when no thumb generation was in flight.
- **Fix:** Timer created stopped. `_request_thumb` starts it (`if not isActive(): start()`) after enqueuing a new job. `_poll_pending_landings` stops it after draining the queue when both `_pending_landings.empty()` and `_in_flight_thumbs` is empty. Zero idle wakeups when the model is at rest.
- **Files modified:** musicstreamer/ui_qt/station_tree_model.py
- **Commit:** d3da2db2

## Threat Model Coverage

All STRIDE threats from the plan's threat register are mitigated:
- **T-94-06 (QPixmap off UI thread):** QPixmap usage confined to `_on_thumb_landing` (main-thread slot) and `load_station_icon` (main thread). No QPixmap in daemon callback. Verified by grep: `QPixmap` absent from station_tree_model.py except in `_on_thumb_landing`.
- **T-94-07 (worker storm / dedup):** `_in_flight_thumbs` set prevents duplicate workers. Verified by `test_in_flight_dedup` GREEN.
- **T-94-08 (stale QModelIndex):** Only `station_id: int` crosses async boundary. `index_for_station_id` re-derives fresh index in `_on_thumb_landing`. `idx.isValid()` guards dataChanged.
- **T-94-09 (now_playing drift):** `now_playing_panel.py` untouched. `test_now_playing_panel_does_not_use_thumb` GREEN (static source-grep guard).
- **T-94-SC:** No package installs.

## Known Stubs

None — all async pipeline components are fully implemented and tested.

## Self-Check

Files exist:
- musicstreamer/ui_qt/station_tree_model.py: FOUND
- musicstreamer/ui_qt/_art_paths.py: FOUND

Commits exist:
- 39191ff7: FOUND
- 9acf0b39: FOUND

## Self-Check: PASSED
