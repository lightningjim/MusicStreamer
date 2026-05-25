---
phase: 77-test-infrastructure-stabilization-fix-pre-existing-test-doub
plan: "04"
subsystem: test-infrastructure
tags: [test-infrastructure, test-impl-drift, cleanup, streamlink, qt-tests]
dependency_graph:
  requires: ["77-01"]
  provides: ["INFRA-01-d", "INFRA-01-e", "INFRA-01-f", "INFRA-01-g"]
  affects: []
tech_stack:
  added: []
  patterns:
    - "MagicMock(spec=Streamlink) drift-guard prevents reintroducing removed API"
    - "Stack page-index as semantic visibility proxy for unshown top-level widgets"
    - "min(N, len(seq)) pattern for seed-data-robust count assertions"
key_files:
  modified:
    - tests/test_import_dialog_qt.py
    - tests/test_twitch_auth.py
    - tests/test_station_list_panel.py
  created: []
decisions:
  - "D-04: _aa_quality orphan — test follows impl; both orphan functions deleted wholesale"
  - "D-05 REVISED: set_plugin_option→set_option — test follows impl; MagicMock(spec=Streamlink) drift-guard installed"
  - "D-06: recent count 3→min(5,len) — test follows production list_recently_played(5)"
  - "D-15 REVISED: isVisibleTo deleted — panel never shown; currentIndex() is sufficient semantic proxy"
metrics:
  duration_minutes: 45
  completed_date: "2026-05-17T17:24:14Z"
  tasks_completed: 3
  files_changed: 3
---

# Phase 77 Plan 04: Four test↔impl drift fixes (3 tasks) Summary

Four pre-existing test↔implementation drift items closed. Tests rewritten to match production. Zero production code changes.

## What Was Built

Closed four test↔impl drift items from the CONTEXT.md cluster list:

- **D-04 (Cluster 4):** Deleted 2 orphan `_aa_quality` functions from `tests/test_import_dialog_qt.py` — `test_audioaddict_tab_widgets` and `test_audioaddict_quality_combo` both asserted `dialog._aa_quality` which was deleted in Phase 56 commit `414e236`.

- **D-05 REVISED (Cluster 6):** Rewrote `tests/test_twitch_auth.py` to assert `session.set_option("twitch-api-header", ...)` matching production `player.py:1156`. `Streamlink.set_plugin_option()` was removed in streamlink 6.0.0 (PR #5033, 2023-07-20). All 6 prior `set_plugin_option` references replaced. `MagicMock(spec=Streamlink)` drift-guard installed so reintroducing the removed API raises `AttributeError` at test time.

- **D-06 (Cluster 5a):** Fixed `test_refresh_recent_updates_list` rowCount assertion from `== 3` to `== min(5, len(repo._recent))`, matching production `list_recently_played(5)` at `station_list_panel.py:492`.

- **D-15 REVISED (Cluster 5b):** Deleted 2 `isVisibleTo(panel)` assertions from `test_filter_strip_hidden_in_favorites_mode`. Root cause: `panel.show()` is never called; `isVisibleTo()` returns False for any widget whose top-level was never shown. The existing `_stack.currentIndex()` checks are the correct semantic proxy.

## Metrics

| Item | Count |
|------|-------|
| Test functions deleted | 2 (both `_aa_quality` orphans) |
| Test functions renamed | 1 (`set_plugin_option` → `set_option` Twitch test) |
| `set_plugin_option` references replaced | 6 |
| `isVisibleTo` assertions removed | 2 |
| Production code changes | 0 — `git diff musicstreamer/` is empty |
| Streamlink probe baseline | `hasattr(Streamlink(), 'set_plugin_option') == False`, `hasattr(Streamlink(), 'set_option') == True` |

## Task Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: Delete `_aa_quality` orphan assertions (D-04) | `060ee3f` | tests/test_import_dialog_qt.py |
| Task 2: Rewrite test_twitch_auth.py for production API (D-05) | `41b3d9e` | tests/test_twitch_auth.py |
| Task 3: isVisibleTo swap + recent count fix (D-06+D-15) | `acc53b7` | tests/test_station_list_panel.py |

## Deviations from Plan

### Environment Issue Resolved Inline

**Worktree venv missing `gi` module and `pytest-qt`**

- **Found during:** Task 2 verification
- **Issue:** The worktree's uv-managed CPython 3.14.5 venv did not have `gi` (PyGObject/GStreamer bindings) in its site-packages, causing `from musicstreamer.player import Player` to fail at collection time. The system gi is compiled for Python 3.14 (`_gi.cpython-314-x86_64-linux-gnu.so`) and installed at `/usr/lib/python3/dist-packages/gi`.
- **Fix:** Added `/usr/lib/python3/dist-packages` to the worktree venv via a `.pth` file (`system-gi.pth`). Added `pytest-qt` to the worktree venv via `uv add --dev pytest-qt`. These are test-infrastructure fixes, not production changes.
- **Note:** The test was already a "pre-existing failure" in Phase 71 deferred-items.md (listed under Cluster 6) — it was failing with `AssertionError` on `set_plugin_option.assert_called_once_with`. After the Task 2 rewrite + environment fix, all 6 tests pass.
- **Files modified:** `.venv/lib/python3.14/site-packages/system-gi.pth` (not tracked by git), `uv.lock` (updated by `uv add`)

## Test Results

| File | Tests Passed | Notes |
|------|-------------|-------|
| tests/test_import_dialog_qt.py | 22 passed, 1 deselected | `test_yt_scan_passes_through` deselected per plan (Plan 77-05 scope) |
| tests/test_twitch_auth.py | 6 passed | All 3 streamlink-mocking tests use `MagicMock(spec=Streamlink)` |
| tests/test_station_list_panel.py | 38 passed | `test_recently_played_populated` (out of scope per D-03) untouched |

## Known Stubs

None — all test fixes match production behavior. No stub patterns introduced.

## Threat Flags

None — zero production code changed; no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `tests/test_import_dialog_qt.py` exists | FOUND |
| `tests/test_twitch_auth.py` exists | FOUND |
| `tests/test_station_list_panel.py` exists | FOUND |
| `77-04-SUMMARY.md` exists | FOUND |
| commit `060ee3f` (Task 1) | FOUND |
| commit `41b3d9e` (Task 2) | FOUND |
| commit `acc53b7` (Task 3) | FOUND |
| `_aa_quality` refs in test_import_dialog_qt.py | 0 |
| `set_plugin_option` refs in test_twitch_auth.py | 0 |
| `isVisibleTo` refs in test_station_list_panel.py | 0 |
| `min(5, len(repo._recent))` in test_station_list_panel.py | 1 |
| `git diff musicstreamer/` lines | 0 (production unchanged) |
