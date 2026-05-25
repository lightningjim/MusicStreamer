---
phase: 67
plan: "04"
subsystem: ui_qt/main_window
tags: [pyside6, qaction, sqlite-settings, qa-05, hamburger-menu, tdd-green, wave-3]

# Dependency graph
dependency_graph:
  requires: [67-01, 67-02, 67-03]
  provides:
    - MainWindow._act_show_similar (checkable QAction in hamburger Group 2)
    - MainWindow._on_show_similar_toggled (persist + panel visibility slot)
    - MainWindow._on_similar_activated (one-line delegate to _on_station_activated)
    - similar_activated signal connected to _on_similar_activated
    - initial-state push: set_similar_visible(_act_show_similar.isChecked())
  affects:
    - musicstreamer/ui_qt/main_window.py
    - tests/test_main_window_integration.py

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Atomic Tasks 1+2 commit: connect() resolves bound methods eagerly — same
      as Plan 03's deviation #3; both insertions committed together"
    - "Hamburger Group 2 ordering: Theme → Show similar stations → Accent Color
      (Phase 66 D-15, Phase 67 S-01 M-01)"
    - "_on_similar_activated one-line delegate mirrors Phase 64 _on_sibling_activated exactly"
    - "_on_show_similar_toggled dual-write mirrors Phase 47.1 _on_stats_toggled exactly"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/main_window.py (+57 lines: 1 QAction block, 1 signal connection,
      1 initial-push line, 2 new slot methods)
    - tests/test_main_window_integration.py (+9 lines / -7 lines: EXPECTED_ACTION_TEXTS
      updated to include Theme + Show similar stations; counts corrected to 13/14)

decisions:
  - "Tasks 1+2 committed atomically: _act_show_similar.toggled.connect(self._on_show_similar_toggled)
    resolves the bound method at connect()-call-time (not emission-time). Slot must exist
    before construction. Mirrors Plan 03 deviation #3 exactly."
  - "test_hamburger_menu_actions EXPECTED_ACTION_TEXTS fixed to include 'Theme' (Phase 66 D-15,
    pre-existing gap) and 'Show similar stations' (Phase 67). Pre-existing test_audioaddict_tab_widgets
    failure noted as out-of-scope (pre-existing, unrelated to Phase 67)."

metrics:
  duration: "10 minutes"
  completed: "2026-05-10T13:42:17Z"
  tasks: 2
  files_modified: 2
---

# Phase 67 Plan 04: MainWindow Wiring — Hamburger Toggle + Click Delegation Summary

Hamburger toggle QAction for "Show similar stations" wired into Group 2 (between Theme and Accent Color), similar_activated signal connected, initial-state visibility push added, and two new slot methods (_on_show_similar_toggled, _on_similar_activated) landed. Turns all 6 Phase 67 RED integration tests GREEN; closes Phase 67 milestone.

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-10T13:31:27Z
- **Completed:** 2026-05-10T13:42:17Z
- **Tasks:** 2 (committed atomically)
- **Files modified:** 2

## Accomplishments

- Added checkable `_act_show_similar` QAction in hamburger menu Group 2, positioned between Phase 66 Theme picker and Accent Color per CONTEXT.md M-01. Reads `show_similar_stations` setting on construction (SIM-01/S-01).
- Connected `now_playing.similar_activated` to new `_on_similar_activated` slot via bound method (QA-05 / I-02). Distinct signal from `sibling_activated` for independent testability.
- Added initial-state push `set_similar_visible(_act_show_similar.isChecked())` immediately after the Phase 47.1 WR-02 `set_stats_visible` call — locks single-source-of-truth invariant (Pitfall 4 / M-02).
- Added `_on_show_similar_toggled(checked: bool)`: persists setting via `repo.set_setting("show_similar_stations", ...)` and calls `now_playing.set_similar_visible(checked)` — mirrors Phase 47.1 `_on_stats_toggled` exactly.
- Added `_on_similar_activated(station: Station)`: one-line delegate to `_on_station_activated(station)` — mirrors Phase 64 `_on_sibling_activated` exactly.
- Fixed pre-existing gap in `test_hamburger_menu_actions`: `EXPECTED_ACTION_TEXTS` was missing "Theme" (Phase 66 D-15 addition) and index offset for version footer was wrong. Updated to 13 named actions + 1 version footer = 14 total.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1+2 (atomic) | Add QAction + signal connection + initial push + 2 slots | 7e68ef1 | main_window.py (+57), test_main_window_integration.py (+9/-7) |

## Verification Results

- `pytest tests/test_main_window_integration.py -k "show_similar or similar_link or no_lambda_on_similar"`: 6 tests — all passed (RED → GREEN)
- `pytest tests/test_main_window_integration.py`: 53 tests — all passed (Phase 47.1 + Phase 64 + Phase 66 baselines preserved)
- `pytest tests/test_pick_similar_stations.py tests/test_now_playing_panel.py tests/test_main_window_integration.py tests/test_aa_siblings.py tests/test_filter_utils.py`: 245 tests — all passed

## Acceptance Criteria Verification

- `_act_show_similar = self._menu.addAction("Show similar stations")`: 1 ✓
- `_act_show_similar.setCheckable(True)`: 1 ✓
- `_act_show_similar.setChecked(...)`: 1 ✓
- `"show_similar_stations", "0"` setting read: 1 ✓
- `_act_show_similar.toggled.connect(self._on_show_similar_toggled)`: 1 ✓
- `now_playing.similar_activated.connect(self._on_similar_activated)`: 1 ✓
- `set_similar_visible(self._act_show_similar.isChecked())`: 1 ✓
- `def _on_similar_activated(self, station: Station) -> None`: 1 ✓
- `def _on_show_similar_toggled(self, checked: bool) -> None`: 1 ✓
- `self._repo.set_setting("show_similar_stations"`: 1 ✓
- `self.now_playing.set_similar_visible(checked)`: 1 ✓
- `self._on_station_activated(station)` count: 2 (sibling + similar) ✓
- lambda count in main_window.py: 5 (unchanged) ✓ QA-05
- All 6 Phase 67 integration tests pass ✓
- Phase 47.1 baseline: test_stats_action_is_checkable + test_stats_toggle_persists_and_toggles_panel ✓
- Phase 64 baseline: test_sibling_click_switches_playback_via_main_window ✓
- Full diff is purely additive (no existing function bodies modified) ✓

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Tasks 1+2 committed atomically (mirrors Plan 03 deviation #3)**
- **Found during:** Task 1 first test run
- **Issue:** `_act_show_similar.toggled.connect(self._on_show_similar_toggled)` raised `AttributeError: 'MainWindow' object has no attribute '_on_show_similar_toggled'` at panel construction time. Python's `self._on_show_similar_toggled` lookup happens eagerly at `connect()` call time, NOT at signal-emission time as noted in the plan. This is identical to Plan 03's deviation #3 (documented in 67-03-SUMMARY.md).
- **Fix:** Both Task 1 and Task 2 changes implemented before committing.
- **Files modified:** `musicstreamer/ui_qt/main_window.py`
- **Commit:** 7e68ef1

**2. [Rule 1 - Bug] Fixed pre-existing test_hamburger_menu_actions failure**
- **Found during:** Full integration test run after Task 1+2
- **Issue:** `test_hamburger_menu_actions` was already failing before Phase 67 changes because Phase 66 added "Theme" to Group 2 without updating `EXPECTED_ACTION_TEXTS`. Phase 67 further adds "Show similar stations". Test used `texts[:11]` and `len == 12` / `texts[11]` — all stale.
- **Fix:** Updated `EXPECTED_ACTION_TEXTS` to include "Theme" and "Show similar stations"; updated slice, count, and version-footer index to 13/14/13 respectively.
- **Files modified:** `tests/test_main_window_integration.py`
- **Commit:** 7e68ef1 (included in the atomic commit)

## Known Stubs

None. All methods are fully implemented and wired to the test corpus.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes. All new code is in-process MainWindow wiring:
- `_act_show_similar.toggled` to `_on_show_similar_toggled`: T-67-04-01 (spoofing) mitigated via bound method, QA-05 lock test passes
- `_on_show_similar_toggled` persistence: T-67-04-02 (tampering) mitigated — compile-time string literals only
- `similar_activated.connect(_on_similar_activated)`: T-67-04-01 mitigated, QA-05 structural lock passes
- `_on_similar_activated` delegate: T-67-04-04/07 accepted (same disposition as Phase 64 _on_sibling_activated)

## TDD Gate Compliance

This plan is `type: execute` with tasks `tdd="true"`. Due to the atomic dependency between Tasks 1 and 2 (eager connect resolution), both were committed together. RED state was confirmed in 67-01-SUMMARY.md (AttributeError on `_act_show_similar`). All 6 Phase 67 tests were GREEN after the single atomic commit.

1. RED state: confirmed in 67-01-SUMMARY.md — all 6 main_window integration tests failed with AttributeError
2. GREEN commit: `feat(67-04)` 7e68ef1 — all 6 tests pass

## Phase 67 Closure

With Plans 01-04 all green, Phase 67 is complete:
- SIM-01: hamburger "Show similar stations" QAction, checkable, reads setting ✓
- SIM-02: initial-state push hides container by default; toggling shows/hides ✓
- SIM-08: similar-station click switches active playback via _on_station_activated chain ✓
- QA-05: bound-method connections only (no lambda on similar_activated or toggled) ✓
- Plan 02 (pick_similar_stations/render_similar_html) + Plan 03 (panel widget surface) baselines preserved ✓

The hamburger menu now offers a "Show similar stations" toggle (default off). When ON, the NowPlayingPanel surfaces the Phase 67 Similar Stations section with two pools (same provider, same tag), refresh, collapse/expand, and click-to-switch behavior routing through the canonical _on_station_activated side-effect chain.

## Self-Check: PASSED

Files exist:
- `musicstreamer/ui_qt/main_window.py` — FOUND ✓
- `tests/test_main_window_integration.py` — FOUND ✓

Commits exist:
- 7e68ef1 — FOUND ✓
