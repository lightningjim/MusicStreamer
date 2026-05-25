---
phase: 71
plan: "00"
subsystem: tests
wave: 0
tags: [tdd-red, sibling-stations, test-scaffolding, drift-guard]
requirements:
  - D-01
  - D-05
  - D-06
  - D-07
  - D-08
  - D-11
  - D-12
  - D-13
  - D-14
  - D-15
  - T-40-04
dependency_graph:
  requires: []
  provides:
    - "22+ RED tests across 6 files locking Phase 71 implementation contract"
    - "Fixture-mirroring imports that fail at collection until Plans 71-01..07 land"
    - "T-40-04 RichText drift-guard (count must drop to 3 after Plan 71-03)"
  affects:
    - "Plans 71-01..71-07 must turn these tests GREEN"
tech_stack:
  added: []
  patterns:
    - "fixture-mirroring (RED via ImportError/AttributeError; no pytest.fail placeholders)"
    - "PRAGMA foreign_keys = ON in every CASCADE-exercising fixture (RESEARCH Pitfall 6)"
    - "FakeRepo + qtbot dialog pattern (mirrors test_discovery_dialog.py)"
    - "MagicMock repo + qtbot pattern (mirrors existing test_edit_station_dialog.py)"
    - "Source-file grep gate (Phase 60.3 precedent; extends test_constants_drift.py)"
key_files:
  created:
    - "tests/test_station_siblings.py (235 lines, 13 tests)"
    - "tests/test_add_sibling_dialog.py (214 lines, 9 tests)"
  modified:
    - "tests/test_edit_station_dialog.py (+131 lines, 6 new tests appended)"
    - "tests/test_now_playing_panel.py (+60 lines, 1 new test + _FakeRepoWithSiblings subclass)"
    - "tests/test_settings_export.py (+153 lines, 3 new tests appended)"
    - "tests/test_constants_drift.py (+40 lines, 1 new test + EXPECTED_RICHTEXT_COUNT = 3 constant)"
decisions:
  - "RED state delivered via fixture-mirroring (ImportError) per Phases 47/62/68/70 convention — NO pytest.fail / importorskip placeholders anywhere."
  - "_FakeRepoWithSiblings created as in-test subclass in test_now_playing_panel.py rather than mutating the shared FakeRepo class (preserves existing 100+ tests untouched)."
  - "EXPECTED_RICHTEXT_COUNT = 3 locks the post-Plan-71-03 target; this test is intentionally RED today (count=4) until Plan 71-03 removes EditStationDialog._sibling_label."
  - "test_aa_chip_has_no_x_button passes vacuously today (no chip row yet) and continues to pass after Plan 71-03 — the assertion locks the D-15 contract against future regression."
metrics:
  start: "2026-05-12T21:41:53Z"
  end: "2026-05-12T21:51:35Z"
  duration_seconds: 582
  tasks_completed: 4
  files_created: 2
  files_modified: 4
  new_test_functions: 33
  commits: 3
---

# Phase 71 Plan 00: Sister Station Expansion — Wave 0 RED Contract — Summary

Wave 0 RED test scaffolding for sibling-station expansion: 22 + verification-locking tests across 6 files, all RED today via ImportError/AttributeError/AssertionError on the not-yet-implemented helpers, schema, widgets, and signal that Plans 71-01..71-07 will produce.

## Objective Recap

Lock the exact behavioral contract for:
- `Repo.add_sibling_link` / `remove_sibling_link` / `list_sibling_links` (Plan 71-01)
- `find_manual_siblings` + `merge_siblings` pure helpers (Plan 71-02)
- `EditStationDialog` chip row with `sibling_toast` Signal + `+ Add sibling` button (Plan 71-03)
- `AddSiblingDialog` two-step provider→station picker (Plan 71-04)
- `NowPlayingPanel` merged AA + manual siblings display (Plan 71-05)
- `settings_export` ZIP siblings round-trip by name (Plan 71-07)
- T-40-04 RichText drift-guard pegged to post-Plan-71-03 target (3)

## Files Created (2)

| File | Lines | Tests | RED via |
|---|---|---|---|
| `tests/test_station_siblings.py` | 235 | 13 | `ImportError: cannot import name 'find_manual_siblings' from 'musicstreamer.url_helpers'` |
| `tests/test_add_sibling_dialog.py` | 214 | 9 | `ModuleNotFoundError: No module named 'musicstreamer.ui_qt.add_sibling_dialog'` |

## Files Extended (4) — appendix-only, zero modifications to existing test bodies

| File | Lines added | New tests | RED via |
|---|---|---|---|
| `tests/test_edit_station_dialog.py` | +131 | 6 | `AttributeError: 'EditStationDialog' object has no attribute 'sibling_toast'`; `findChild(QWidget, "sibling_chip_42") is None` |
| `tests/test_now_playing_panel.py` | +60 | 1 | `'Manual Drone' not in 'Also on: <a href="sibling://2">ZenRadio</a>'` |
| `tests/test_settings_export.py` | +153 | 3 | `sqlite3.OperationalError: no such table: station_siblings` |
| `tests/test_constants_drift.py` | +40 | 1 | `assert 4 == 3` (current baseline; drops to 3 after Plan 71-03 removes EditStationDialog._sibling_label) |

`git diff --stat` confirms additions-only — no `-` lines in any existing test body (verified at Task 3 acceptance and before commit b7c3d36).

## Final RED Test Count per File

| File | Test count | Notes |
|---|---|---|
| `tests/test_station_siblings.py` | 13 | All RED via collection-time ImportError |
| `tests/test_add_sibling_dialog.py` | 9 | All RED via collection-time ModuleNotFoundError |
| `tests/test_edit_station_dialog.py` (new) | 6 | 5 fail at runtime; 1 (`test_aa_chip_has_no_x_button`) passes vacuously today and continues to pass post-71-03 — locks D-15 contract against future regression |
| `tests/test_now_playing_panel.py` (new) | 1 | Fails at runtime — manual sibling not yet in merged display |
| `tests/test_settings_export.py` (new) | 3 | Fail at runtime — `station_siblings` table does not yet exist |
| `tests/test_constants_drift.py` (new) | 1 | Fails at runtime — count is 4 today, locked target is 3 |
| **Total** | **33** | Exceeds the 22-row Wave 0 minimum in 71-VALIDATION.md |

## RichText Baseline Today

```bash
$ grep -rn "setTextFormat(Qt\.RichText)" musicstreamer/ | wc -l
4
```

Per-file breakdown:
- `musicstreamer/ui_qt/now_playing_panel.py`: 3 (lines 355, 617, 633) — preserved
- `musicstreamer/ui_qt/edit_station_dialog.py`: 1 (line 487) — removed by Plan 71-03

Locked constant in `tests/test_constants_drift.py`:
```python
EXPECTED_RICHTEXT_COUNT = 3  # post-Plan-71-03 target
```

The new `test_richtext_baseline_unchanged_by_phase_71` test is intentionally RED today (`assert 4 == 3` fails). It turns GREEN the moment Plan 71-03 removes the `_sibling_label` QLabel from `EditStationDialog`. If Phase 71 accidentally adds a new `setTextFormat(Qt.RichText)` call anywhere in `musicstreamer/`, the count will not drop to 3 and this test will continue to fail — catching the T-40-04 invariant violation before merge.

## Self-Check: Tests Are RED (Wave 0 Contract)

Per the phase_notes: "Tests must FAIL in this wave (intentional RED)."

**Verification commands run:**

```bash
$ pytest tests/test_station_siblings.py tests/test_add_sibling_dialog.py --collect-only
# Output: 2 collection errors (ImportError + ModuleNotFoundError) — RED state ✓

$ pytest tests/test_edit_station_dialog.py tests/test_now_playing_panel.py tests/test_settings_export.py tests/test_constants_drift.py --tb=no -q
# Output: 10 failed, 239 passed
# The 10 failures are exactly the 10 new tests that fail at runtime:
#   test_add_sibling_button_present       — AssertionError (None is not None)
#   test_manual_chip_has_x_button         — AssertionError (None is not None)
#   test_x_click_calls_remove_sibling_link — AttributeError (no sibling_chip_42)
#   test_x_click_fires_unlinked_toast     — AttributeError (no sibling_toast)
#   test_chip_click_emits_navigate_signal — AttributeError (no sibling_chip_42)
#   test_now_playing_shows_merged_siblings — AssertionError (manual name missing)
#   test_siblings_round_trip              — sqlite3.OperationalError (no table)
#   test_siblings_missing_key_defaults_empty — sqlite3.OperationalError
#   test_siblings_unresolved_name_silently_dropped — sqlite3.OperationalError
#   test_richtext_baseline_unchanged_by_phase_71 — AssertionError (4 != 3)
# The 11th new test (test_aa_chip_has_no_x_button) passes vacuously
# (today the chip row does not exist so findChild returns None either way).
# Zero pre-existing tests regressed.
```

RED state CONFIRMED. Failures cluster on the correct missing artifacts that Plans 71-01..07 will produce.

## Deviations from Plan

None. The plan was executed exactly as written, with two minor adaptations that the plan explicitly allowed:

1. **`_FakeRepoWithSiblings` subclass over mutating shared `FakeRepo`** — Plan Task 3 action note offered both options; subclass chosen to keep 100+ existing test_now_playing_panel.py tests untouched.
2. **`repo_with_siblings` fixture in test_edit_station_dialog.py** — Plan Task 3 action note pre-authorized this as an alternative to extending the existing `repo` MagicMock fixture if it was "parametrized or otherwise inflexible." Both used: `repo_with_siblings` for the `add_sibling_button_present` test that uses the default-config station; per-test inline mutation of `aa_repo.list_sibling_links` for the five tests that need a seeded sibling (mirrors the existing `aa_dialog`/`aa_repo` pattern).

## Auth Gates Encountered

None. Pure test scaffolding work — no network, no credentials, no external services.

## Known Stubs

None. All new tests assert real behavioral contracts; no `pytest.fail`, no `pytest.skip`, no `importorskip` placeholders anywhere (verified via `grep -cE "pytest\.fail|pytest\.skip|importorskip"` returning 0 in test code; matches inside docstrings explaining what we DON'T use are not stubs).

## Threat Surface Scan

No new threat surface introduced — this plan delivers tests only, no production code. The plan's `<threat_model>` (T-71-01..T-71-05) is locked but the mitigations land in Plans 71-03 and 71-07. The Wave 0 contract reflects the threat model:

- T-71-01 mitigation tested by `test_manual_chip_has_x_button` (compound chip uses QPushButton, not QLabel with RichText — preserved T-40-04).
- T-71-02 mitigation already in place at `url_helpers.py:263` (`html.escape(quote=True)`); no new test needed (existing `test_render_sibling_html_html_escapes_station_name` covers it).
- T-71-03 mitigation tested by `test_siblings_unresolved_name_silently_dropped`.
- T-71-04 mitigation already in place at `edit_station_dialog.py:1260`; Wave 0 `test_chip_click_emits_navigate_signal` exercises the happy path.
- T-71-05 disposition is `accept` — no test required.

## Commit Chain

| Task | Commit | Files | Summary |
|---|---|---|---|
| 1 | `ec1388d` | `tests/test_station_siblings.py` (new) | 13 RED tests — repo CRUD, schema, find_manual_siblings, merge_siblings |
| 2 | `76a157c` | `tests/test_add_sibling_dialog.py` (new) | 9 RED tests — AddSiblingDialog picker behavior |
| 3 | `b7c3d36` | 4 existing test files (appended) | 11 RED tests — chip row, merged display, ZIP siblings, RichText drift-guard |
| 4 | (verification-only — no file modifications per plan spec) | — | Confirmed 33 new tests + baseline RichText count = 4 + EXPECTED_RICHTEXT_COUNT = 3 |

## Validation-Map Coverage (22 of 22 rows in 71-VALIDATION.md)

| Decision / Invariant | Test name | File |
|---|---|---|
| D-05 schema CHECK+UNIQUE+CASCADE | `test_schema_create_with_check_unique_cascade` | test_station_siblings.py |
| D-06 db_init idempotent | `test_db_init_idempotent_with_siblings_table` | test_station_siblings.py |
| D-07 ZIP round-trip | `test_siblings_round_trip` | test_settings_export.py |
| D-07 missing key forward-compat | `test_siblings_missing_key_defaults_empty` | test_settings_export.py |
| D-07 unresolved name dropped | `test_siblings_unresolved_name_silently_dropped` | test_settings_export.py |
| D-08 ON DELETE CASCADE | `test_cascade_on_station_delete` | test_station_siblings.py |
| D-01 merged display | `test_now_playing_shows_merged_siblings` | test_now_playing_panel.py |
| D-11 + Add sibling button | `test_add_sibling_button_present` | test_edit_station_dialog.py |
| D-12 provider switch reloads | `test_provider_switch_reloads_station_list` | test_add_sibling_dialog.py |
| D-13 self/already-linked excluded | `test_self_excluded_from_list` + `test_already_linked_excluded_from_list` | test_add_sibling_dialog.py |
| D-13 OK gate on single select | `test_ok_disabled_initially` + `test_accept_calls_add_sibling_link` | test_add_sibling_dialog.py |
| D-14 × calls remove + refresh | `test_x_click_calls_remove_sibling_link` | test_edit_station_dialog.py |
| D-14 × fires unlinked toast | `test_x_click_fires_unlinked_toast` | test_edit_station_dialog.py |
| D-15 AA chip no × | `test_aa_chip_has_no_x_button` | test_edit_station_dialog.py |
| Merge dedup AA wins | `test_merge_siblings_dedup_by_station_id` | test_station_siblings.py |
| Symmetric storage | `test_list_sibling_links_symmetric` | test_station_siblings.py |
| Idempotent CRUD (INSERT OR IGNORE) | `test_add_sibling_link_idempotent` | test_station_siblings.py |
| Normalizes (lo, hi) | `test_add_sibling_link_normalizes_order` | test_station_siblings.py |
| T-40-04 RichText baseline | `test_richtext_baseline_unchanged_by_phase_71` | test_constants_drift.py |
| Navigation invariant | `test_chip_click_emits_navigate_signal` | test_edit_station_dialog.py |
| find_manual_siblings tuple shape | `test_find_manual_siblings_tuple_shape` | test_station_siblings.py |
| find_manual_siblings excludes self | `test_find_manual_siblings_excludes_self` | test_station_siblings.py |

All 22 rows mapped. Additional tests beyond the 22-row minimum:

- `test_add_sibling_link_round_trip`, `test_remove_sibling_link`, `test_remove_sibling_link_noop_when_absent` (round-trip completeness)
- `test_find_manual_siblings_sorts_alphabetically` (sort-order invariant)
- `test_dialog_window_title_is_add_sibling_station`, `test_ok_button_label_is_link_station`, `test_dismiss_button_label_is_dont_link`, `test_provider_combo_defaults_to_current_station_provider` (UI-SPEC copy contracts)

## Self-Check Verification

Files created exist:

```bash
$ ls -la tests/test_station_siblings.py tests/test_add_sibling_dialog.py
```

Result: both files present at expected paths.

Commits exist:

```bash
$ git log --oneline HEAD~3..HEAD
b7c3d36 test(71-00): extend 4 test files with Phase 71 RED contract
76a157c test(71-00): add RED contract for AddSiblingDialog picker
ec1388d test(71-00): add RED contract for station_siblings repo + helpers
```

All three commit hashes (`ec1388d`, `76a157c`, `b7c3d36`) present in the worktree branch's log.

## Self-Check: PASSED

- All files claimed as created exist.
- All three commit hashes are present in `git log`.
- All new tests are in RED state via expected failure modes (ImportError / ModuleNotFoundError / AttributeError / AssertionError / sqlite3.OperationalError).
- No `pytest.fail` / `pytest.skip` / `importorskip` placeholders anywhere in new test code.
- `PRAGMA foreign_keys = ON` enforced in both new CASCADE-exercising fixtures.
- Pre-existing 239 tests in extended files all pass — zero regression.
- `EXPECTED_RICHTEXT_COUNT = 3` locked in test_constants_drift.py at module scope.
- Today's `setTextFormat(Qt.RichText)` baseline in `musicstreamer/` is exactly 4 (will become 3 after Plan 71-03).
