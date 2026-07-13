---
phase: 94-optimize-sidebar-logo-loading-with-pre-scaled-thumbnails-for
plan: "02"
subsystem: ui_qt/art-loader
tags: [performance, thumbnails, async, thread-safety, atomic-write]
dependency_graph:
  requires: ["94-01"]
  provides: ["THUMB_FILENAME", "_thumb_path_for", "_is_thumb_fresh", "_generate_thumb", "load_station_icon(on_thumb_needed)"]
  affects: ["musicstreamer/ui_qt/station_tree_model.py (Plan 03 consumer)"]
tech_stack:
  added: ["threading.Thread(daemon=True)", "tempfile.mkstemp", "QImage.scaled", "os.replace"]
  patterns: ["daemon-thread worker + callback (cover_art._itunes_attempt idiom)", "mkstemp + os.replace atomic write (desktop_install._atomic_copy idiom)", "QImage off-thread / QPixmap main-thread (CR-01)"]
key_files:
  modified: ["musicstreamer/ui_qt/_art_paths.py"]
decisions:
  - "Legacy 2-arg callers (favorites_view, station_list_panel) get original load_path behavior when on_thumb_needed=None to preserve existing test contracts [Rule 1 fix]"
  - "Cache key stays keyed on source abs_path (not thumb_path) to match edit_station_dialog._invalidate_cache_for eviction key"
  - "Worker uses QImage only (CR-01); QPixmap decoded on main thread only"
metrics:
  duration: "22 minutes"
  completed: "2026-06-16T00:22:26Z"
  tasks_completed: 2
  files_modified: 1
---

# Phase 94 Plan 02: Implement _art_paths.py Thumb Load Path Summary

One-liner: Off-UI-thread 96px thumbnail generator (QImage + mkstemp + os.replace) with freshness-gated fast path and on_thumb_needed enqueue callback added to `_art_paths.py`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add thumb-path helpers and _generate_thumb worker | c835341e | musicstreamer/ui_qt/_art_paths.py |
| 2 | Refactor load_station_icon with thumb fast path + on_thumb_needed | dd10d8e0 | musicstreamer/ui_qt/_art_paths.py |

## Test Results

**Plan 02 target tests (5 total) — ALL GREEN:**
- test_thumb_path_derivation: PASS
- test_thumb_is_96px: PASS
- test_generate_thumb_writes_png: PASS
- test_thumb_freshness_check: PASS
- test_thumb_missing_returns_fallback: PASS

**Regression tests — ALL GREEN (18 total):**
- tests/test_art_paths.py: 13 passed
- tests/test_station_icon_integration.py: 5 passed

**Expected RED (Plan 03 scope, not a regression):**
- tests/test_station_thumb_async.py: 3 failed (StationTreeModel changes in Plan 03)

## Implementation Notes

### _generate_thumb worker shape (Task 1)
Replicates `cover_art._itunes_attempt` pattern exactly: outer function spawns an inner `_worker` closure on a daemon thread. Worker uses `QImage(source_path)` (never `QPixmap` — CR-01 compliance), scales to 96px longest axis via `Qt.KeepAspectRatio + Qt.SmoothTransformation`, then writes atomically via `tempfile.mkstemp(dir=thumb_dir) + scaled.save(tmp, 'PNG') + os.replace(tmp, thumb_path)`. On any failure (null image, save error, exception) calls `callback(station_id, source_path, None)`.

### load_station_icon fast-path branching (Task 2)
Three cases on cache miss with abs_path present:
1. Fresh thumb (mtime >=source mtime): `src = QPixmap(thumb_path)` — 96px fast path.
2. Stale/missing thumb + on_thumb_needed provided: `src = QPixmap(FALLBACK_ICON)` + enqueue callback.
3. Stale/missing thumb + on_thumb_needed=None (legacy 2-arg callers): `src = QPixmap(load_path)` — original behavior preserved.

The third branch was a deviation fix (see below).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan behavior would break all existing logo-loading tests**
- **Found during:** Task 2 first run — `test_relative_station_art_path_resolves_via_abs_art_path` failed (expected red pixel, got transparent/fallback)
- **Issue:** The plan's `<action>` block specifies `src = QPixmap(FALLBACK_ICON)` whenever thumb is missing/stale, regardless of whether `on_thumb_needed` is None. This breaks existing 2-arg callers (favorites_view, station_list_panel) that don't provide `on_thumb_needed` — they'd get fallback icons instead of actual logos.
- **Fix:** Added a third branch: when `on_thumb_needed is None` and thumb is missing/stale, use `src = QPixmap(load_path)` (original behavior). This preserves backward compatibility while enabling the new async enqueue for callers that provide `on_thumb_needed`.
- **Impact:** Existing tests all GREEN; acceptance criteria "2-arg callers still work" satisfied; the new test `test_thumb_missing_returns_fallback` (which DOES provide `on_thumb_needed`) remains GREEN.
- **Files modified:** musicstreamer/ui_qt/_art_paths.py
- **Commit:** dd10d8e0 (incorporated into Task 2 commit)

## Threat Model Coverage

All STRIDE threats from the plan's threat register are mitigated:
- **T-94-02 (path traversal):** thumb_path computed as `dirname(abs_art_path(rel)) / THUMB_FILENAME` — no user string concatenated into write path.
- **T-94-03 (malformed PNG):** `QImage.isNull()` guard → callback(None); outer try/except in worker prevents exceptions from escaping.
- **T-94-04 (torn thumbnail):** mkstemp + os.replace — reader sees either old-complete or new-complete, never partial.
- **T-94-SC:** No package installs — zero new external dependencies.

## Self-Check

Files exist:
- musicstreamer/ui_qt/_art_paths.py: FOUND

Commits exist:
- c835341e: FOUND
- dd10d8e0: FOUND

## Self-Check: PASSED
