---
phase: 71-sister-station-expansion
plan: 06
subsystem: ui
tags: [pyside6, qt-signals, sibling-stations, toast, signal-wiring, qa-05]

# Dependency graph
requires:
  - phase: 71-03
    provides: EditStationDialog.sibling_toast = Signal(str) — emitted from chip × click and Add-sibling OK with "Linked to X" / "Unlinked from Y" strings
  - phase: 51
    provides: dlg.navigate_to_sibling.connect(self._on_navigate_to_sibling) wiring pattern at the two EditStationDialog spawn sites
  - phase: 68
    provides: live_status_toast.connect(self.show_toast) symmetric precedent — same bound-method (QA-05) shape applied here
provides:
  - MainWindow now routes EditStationDialog.sibling_toast → ToastOverlay so "Linked to X" / "Unlinked from Y" feedback reaches the user on every link/unlink action, from both the "+ Add station" (_on_add_station) and "Edit station" (_on_edit_requested) flows
affects: [71-07, 71-08, future toast wiring patterns]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bound-method Signal.connect at every EditStationDialog spawn site (QA-05) — placed immediately after the prior-phase navigate_to_sibling.connect for symmetric, scannable wiring"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/main_window.py — two new wiring lines (789, 804)

key-decisions:
  - "Placed sibling_toast.connect immediately after navigate_to_sibling.connect at each spawn site for visual symmetry with the existing Phase 51 wiring (matches 71-PATTERNS.md guidance and 71-PLAN read_first §Q6)"
  - "Used bound-method `self.show_toast` (QA-05) — no lambda/closure — mirroring Phase 68 `live_status_toast.connect(self.show_toast)` precedent (tests/test_main_window_integration.py:1362 enforces the same shape for that signal)"
  - "No new tests added — the Plan 71-03 Signal-emission tests cover the sending half; the connect site is verified by the plan's grep-based acceptance criteria and structural assertions"

patterns-established:
  - "When a child dialog gains a `Signal(str)` toast for a per-action user notification, wire it at every spawn site of that dialog in MainWindow with `dlg.<signal>.connect(self.show_toast)` — bound method, comment-tagged with the originating phase/decision"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-05-12
---

# Phase 71 Plan 06: MainWindow sibling_toast Wiring Summary

**Routes `EditStationDialog.sibling_toast(str)` to `MainWindow.show_toast` at both EditStationDialog spawn sites (bound-method, QA-05), closing the user-feedback loop for every Phase 71 link/unlink action.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-12T22:27:59Z
- **Completed:** 2026-05-12T22:32:46Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- `dlg.sibling_toast.connect(self.show_toast)` added at `_on_add_station` (line 789) and `_on_edit_requested` (line 804).
- Each new line sits **immediately after** the existing Phase 51 `dlg.navigate_to_sibling.connect(self._on_navigate_to_sibling)` and **before** `dlg.exec()` — symmetric placement with the prior-phase pattern.
- Both connections use the **bound method** `self.show_toast` (no lambda, no closure, no intermediate slot) — QA-05 compliant, structurally identical to the Phase 68 `live_status_toast.connect(self.show_toast)` precedent.
- `show_toast` signature unchanged: `Signal(str)` payload maps to `text: str`; `duration_ms` defaults to 3000.
- Diff is purely additive (`git diff` shows zero deletions; two `+` lines only).
- Existing Phase 51 `navigate_to_sibling` wiring preserved unchanged.

## Task Commits

1. **Task 1: Add two sibling_toast → show_toast wiring lines in MainWindow** — `4e82528` (feat)

**Plan metadata:** [will be added in final docs commit]

## Files Created/Modified
- `musicstreamer/ui_qt/main_window.py` — added line 789 (in `_on_add_station`) and line 804 (in `_on_edit_requested`), each:
  ```python
  dlg.sibling_toast.connect(self.show_toast)   # Phase 71 / D-14 / D-11
  ```

## Decisions Made
- **Placement:** immediately after `dlg.navigate_to_sibling.connect(...)` in each method, matching 71-PATTERNS.md §"musicstreamer/ui_qt/main_window.py" (lines 749-781). Symmetric to Phase 51's wiring pattern at the same two sites — a future reader scanning the EditStationDialog spawn block sees the full set of dialog-signal wirings as a tight three-line group.
- **No-lambda:** QA-05 (project rule: bound methods over lambdas for Qt connect calls). Direct reference precedent: `tests/test_main_window_integration.py::test_no_lambda_on_live_status_toast_connection` (Phase 68) asserts `live_status_toast.connect(lambda" not in src` — the same structural property holds here.
- **No new tests:** the Signal-emission side is verified by `tests/test_edit_station_dialog.py` (Plan 71-03 tests for chip × and Add-sibling OK). The connect site is verified by the plan's acceptance-criteria grep (count = 2) and confirmed by re-running the 137-test MainWindow+EditStationDialog suite (all green, no regression).

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- **Test environment baseline (not a regression):** The broader `pytest tests/` run produces ~34 unrelated failures due to missing `gi` (PyGObject/GStreamer) and `dbus` modules in the uv-managed environment. These are pre-existing baseline failures, identical to the state Plans 71-00 through 71-05 completed against. None of the failures reference `sibling_toast`, `show_toast`, EditStationDialog wiring, or any Phase 71-touched code.
- **One network-dependent test deselected:** `tests/test_edit_station_dialog.py::test_logo_status_clears_after_3s` hangs on a live network logo download (`edit_station_dialog.py:119` urlretrieve). Pre-existing; orthogonal to this plan. Targeted suite of 137 MainWindow+EditStationDialog tests all pass with this test deselected.
- **Stash-pop conflict on uv.lock:** During baseline-comparison run, `git stash pop` conflicted because `uv` had rewritten `uv.lock` between stash and pop. Recovered cleanly by `git checkout stash@{0} -- musicstreamer/ui_qt/main_window.py` and `git checkout -- uv.lock` — no committed change to `uv.lock`, no committed change other than the two intended wiring lines.

## User Setup Required

None.

## Next Phase Readiness

- Plan 71-07 / 71-08 (subsequent waves) inherit a fully wired sibling-toast feedback loop; nothing further is required from MainWindow for D-14 surfacing.
- Phase 71 user flows now produce visible toast feedback on every link/unlink action from both the new-station and edit-station entry points.
- No blockers, no concerns.

## Self-Check

- File `musicstreamer/ui_qt/main_window.py` exists and contains both new wiring lines (lines 789, 804) ✅
- Commit `4e82528` exists in `git log` ✅
- `grep -c "dlg\.sibling_toast\.connect(self\.show_toast)" musicstreamer/ui_qt/main_window.py` returns `2` ✅
- `grep -c "lambda.*sibling_toast\|sibling_toast.*lambda" musicstreamer/ui_qt/main_window.py` returns `0` ✅
- `grep -c "navigate_to_sibling.connect" musicstreamer/ui_qt/main_window.py` returns `2` ✅
- Targeted test suite (137 tests in tests/test_main_window_integration.py + tests/test_edit_station_dialog.py) all pass with no regression ✅

## Self-Check: PASSED

---
*Phase: 71-sister-station-expansion-1-add-ability-to-link-sister-statio*
*Completed: 2026-05-12*
