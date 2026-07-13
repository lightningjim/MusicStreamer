---
phase: 96
plan: "01"
subsystem: tests
tags: [wave-0, nyquist, test-scaffolding, tdd-red]
dependency_graph:
  requires: []
  provides:
    - "D-01..D-10 Wave 0 RED test coverage (16 named test ids across 4 files)"
    - "tests/test_live_refresh_dialog.py (new)"
  affects:
    - tests/test_repo.py
    - tests/test_station_tree_model.py
    - tests/test_edit_station_dialog.py
    - tests/test_live_refresh_dialog.py
tech_stack:
  added: []
  patterns:
    - "Gated ImportError at call time (not module level) to allow collection before module exists"
    - "pytest.fixture + tmp_path SQLite Repo for isolation (mirrors test_repo.py pattern)"
    - "MagicMock repo for apply-logic tests without real DB dependency"
key_files:
  created:
    - tests/test_live_refresh_dialog.py
  modified:
    - tests/test_repo.py
    - tests/test_station_tree_model.py
    - tests/test_edit_station_dialog.py
decisions:
  - "Tests gate ImportError at *call* time via _require_module() helper rather than pytest.skip, so all 7 dialog tests show as FAILED (RED) not SKIPPED before Plan 04 creates the module"
  - "apply_refresh and default_check_state exposed as module-level callables in live_refresh_dialog — seam required by test_conservative_defaults and test_apply_* tests"
  - "build_row_data and _build_row_suggestions treated as testable seams; Plan 04 must expose them on LiveRefreshDialog or at module level"
metrics:
  duration: "6 minutes"
  completed: "2026-06-21T17:45:14Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 4
---

# Phase 96 Plan 01: Wave 0 Nyquist Test Scaffolding Summary

**One-liner:** 16 named RED tests across 4 files scaffold every D-01..D-10 decision before implementation begins.

## What Was Built

Wave 0 Nyquist test scaffolding for Phase 96 — one new test file and three test-file additions. All tests are collectible by pytest and RED (FAILED) against not-yet-built production code, providing the feedback substrate for Plans 02–05.

### Task 1: Repo migration + setter + query tests (D-01/D-03/D-04/D-06)

Appended 7 new tests to `tests/test_repo.py` mirroring the `test_cover_art_source_migration_idempotent` PRAGMA-introspection shape:

| Test | Decision |
|------|----------|
| `test_live_url_syncs_from_channel_migration_idempotent` | D-01 |
| `test_live_url_syncs_from_channel_round_trip` | D-01 |
| `test_station_live_flag_loaded_from_db` | D-01 (Pitfall 2 guard) |
| `test_live_url_title_anchor_migration_idempotent` | D-03 |
| `test_live_url_title_anchor_round_trip` | D-03 |
| `test_provider_channel_scan_url_migration_idempotent` | D-04 |
| `test_list_flagged_stations_for_provider` | D-06 |

All 7 RED (AttributeError on missing setter methods).

### Task 2: Tree-model + EditStationDialog gating tests (D-04/D-02)

Added to `tests/test_station_tree_model.py`:
- `test_tree_node_carries_provider_id` — asserts `_TreeNode.provider_id` field exists and equals `st.provider_id` from the first station in each group; Ungrouped group has `provider_id=None`

Added to `tests/test_edit_station_dialog.py`:
- `test_live_resync_checkbox_gating` — asserts `_live_resync_checkbox` enabled for youtube.com, disabled for twitch.tv (YouTube-only gate, D-02), and disabled+unchecked for non-provider URLs

Both RED (AttributeError on missing `_live_resync_checkbox` / missing `_TreeNode.provider_id`).

### Task 3: NEW tests/test_live_refresh_dialog.py (D-05..D-10)

Created `tests/test_live_refresh_dialog.py` with 7 tests covering D-05 through D-10 plus the D-09 node_runtime forwarding landmine (B2):

| Test | Decision |
|------|----------|
| `test_scan_worker_uses_qthread` | D-09 — QThread subclass, Signal shape, node_runtime kwarg |
| `test_scan_worker_forwards_node_runtime` | D-09 / B2 — run() forwards sentinel to scan_playlist |
| `test_suggestions_pre_order_no_auto_apply` | D-05 — anchor match first, no auto-staged change |
| `test_apply_remap_preserves_metadata` | D-06 — URL updated, label/quality/etc preserved |
| `test_apply_drop_and_add_actions` | D-07 — delete_station + insert_station + flag |
| `test_name_field_prepopulation` | D-08 — ADD=scan title, REMAP=existing station name |
| `test_conservative_defaults` | D-10 / W4 / W5 — DROP/ADD unchecked, REMAP checked, empty-apply zero mutations |

All 7 RED (ModuleNotFoundError — module not yet created). Import is gated at file level so collection always succeeds; tests raise at call time.

## Verification

Collection:
```
.venv/bin/python -m pytest tests/test_repo.py tests/test_station_tree_model.py \
  tests/test_edit_station_dialog.py tests/test_live_refresh_dialog.py \
  --collect-only -q
```
Lists all 16 new test ids (plus existing tests).

RED status confirmed:
- 7 repo tests: FAILED (AttributeError missing setter methods)
- 2 tree-model/dialog tests: FAILED (AttributeError missing fields)
- 7 live-refresh-dialog tests: FAILED (ModuleNotFoundError)

Only `tests/` files modified — zero production code changes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Changed pytest.skip to call-time ImportError raise in test_live_refresh_dialog.py**
- **Found during:** Task 3 verification
- **Issue:** Initial implementation used `pytest.skip()` when the module was not importable, causing tests to show as SKIPPED rather than FAILED (RED). Acceptance criteria requires RED status.
- **Fix:** Replaced `_skip_if_no_import()` with `_require_module()` which re-raises the caught ImportError at call time, yielding FAILED status while preserving collection-time safety.
- **Files modified:** tests/test_live_refresh_dialog.py
- **Commit:** 4769da82 (included in Task 3 commit)

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: Repo tests | da5da3a5 | tests/test_repo.py (+132 lines) |
| Task 2: Tree-model + EditStationDialog | 80a6ce5f | tests/test_station_tree_model.py, tests/test_edit_station_dialog.py (+115 lines) |
| Task 3: Live refresh dialog tests | 4769da82 | tests/test_live_refresh_dialog.py (new, +416 lines) |

## Known Stubs

None — this is a test-only scaffolding plan. No production code stubs created.

## Threat Flags

None — tests construct throwaway tmp_path SQLite DBs only; no production data touched.

## Self-Check: PASSED

- tests/test_live_refresh_dialog.py exists: FOUND
- tests/test_repo.py modified: FOUND (7 new tests, all collectible and RED)
- tests/test_station_tree_model.py modified: FOUND (1 new test, RED)
- tests/test_edit_station_dialog.py modified: FOUND (1 new test, RED)
- Commit da5da3a5: FOUND
- Commit 80a6ce5f: FOUND
- Commit 4769da82: FOUND
- git diff --name-only: only tests/ files modified
