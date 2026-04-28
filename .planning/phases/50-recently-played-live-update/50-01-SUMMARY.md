---
phase: 50-recently-played-live-update
plan: 01
subsystem: ui
tags: [qt, pyside6, recently-played, station-list, bug-fix, tdd]

# Dependency graph
requires:
  - phase: 37-station-list-now-playing
    provides: StationListPanel with recent_view QListView and _populate_recent private rebuild
provides:
  - "StationListPanel.refresh_recent() — public no-arg method that rebuilds ONLY the Recently Played QListView from Repo (no provider tree touch)"
  - "MainWindow._on_station_activated → station_panel.refresh_recent() call wired immediately after Repo.update_last_played()"
  - "Three regression tests pinning the contract: refresh_recent updates the list, refresh_recent does not touch the tree, station_activated triggers a refresh"
affects: [station-list-panel, main-window-slots, recently-played, future-edit-dialog-fixes-phase-55]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Narrow public refresh entry point (refresh_recent) parallel to refresh_model — preserves SC #3 by NOT calling _sync_tree_expansion or model.refresh"
    - "DB-write-then-UI-refresh ordering enforced at call site (update_last_played → refresh_recent) — order is load-bearing per Pitfall #1"

key-files:
  created: []
  modified:
    - "musicstreamer/ui_qt/station_list_panel.py — added refresh_recent() public method (12 lines, delegates to _populate_recent)"
    - "musicstreamer/ui_qt/main_window.py — one new line in _on_station_activated calling station_panel.refresh_recent() after update_last_played"
    - "tests/test_station_list_panel.py — added test_refresh_recent_updates_list and test_refresh_recent_does_not_touch_tree"
    - "tests/test_main_window_integration.py — added test_station_activated_refreshes_recent_list"

key-decisions:
  - "Method named refresh_recent (no leading underscore) — public API parallel to existing refresh_model; placed in the '# Public refresh API' block of StationListPanel"
  - "Direct method call from MainWindow._on_station_activated — no signal indirection, no Qt.QueuedConnection, no QTimer.singleShot (D-04)"
  - "DB-write-then-UI-refresh ordering enforced inline (update_last_played BEFORE refresh_recent) rather than via a wrapper — keeps the call site readable and one-line-grep-verifiable"
  - "refresh_recent intentionally does NOT call self.model.refresh() or self._sync_tree_expansion() — preserves provider tree expand/collapse state (SC #3, Pitfall #2)"
  - "Strengthened integration test (RED Task 1) to require update_last_played to actually drive the refresh — the vacuous version of the test would have passed against the unfixed codebase, hiding the bug"

patterns-established:
  - "Narrow refresh entry points: when only one sub-view of a panel needs updating, expose a focused public method (refresh_recent) rather than calling the full-rebuild method (refresh_model). Future Phase 55 (Edit Station Preserves Section State) is the closest analog."
  - "TDD ordering: RED test first, run pytest, confirm AttributeError or assertion failure on at least one test, then GREEN implementation in a separate commit. Both commits scoped strictly to the named files."

requirements-completed:
  - BUG-01

# Metrics
duration: ~25min (executor wall-clock from RED commit to UAT approval)
completed: 2026-04-27
---

# Phase 50 Plan 01: Recently Played Live Update Summary

**Wired StationListPanel.refresh_recent() into MainWindow._on_station_activated so the Recently Played list updates the moment a station is clicked — provider tree expand/collapse state preserved.**

## Performance

- **Duration:** ~25 min (executor wall-clock from RED commit to UAT approval; full plan from planner-handoff to SUMMARY ~50 min)
- **Started:** 2026-04-27T21:55:13-05:00 (planner handoff — patterns commit ce731d7)
- **RED commit:** 2026-04-27T21:59:13-05:00 (57e4b0c)
- **GREEN commit:** 2026-04-27T22:00:33-05:00 (1cf6781)
- **UAT approved:** 2026-04-27 (post-22:00 by user "approved" message)
- **Tasks:** 3 of 3 (Task 1 RED, Task 2 GREEN, Task 3 human-verify checkpoint)
- **Files modified:** 4 (2 production, 2 test)

## Accomplishments

- Public `StationListPanel.refresh_recent()` method exposed — narrow rebuild of only the Recently Played QListView (12 lines including docstring; method body is a one-line delegate to `_populate_recent`).
- `MainWindow._on_station_activated` now calls `self.station_panel.refresh_recent()` on the line immediately after `self._repo.update_last_played(station.id)` (order is load-bearing per Pitfall #1).
- Three new tests pin the contract: two unit tests on the panel (one for list update, one proving the tree is untouched), one integration test on MainWindow (proving the signal triggers the refresh end-to-end).
- BUG-01 closed with all three Phase 50 success criteria visually confirmed live by user UAT.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Add three failing tests covering refresh_recent contract** — `57e4b0c` (test)
2. **Task 2 (GREEN): Add refresh_recent() and call it from _on_station_activated** — `1cf6781` (feat)
3. **Task 3 (UAT): Full-suite green + human visual confirmation of live update** — no commit (human-verify checkpoint, outcome recorded here)

**Plan metadata:** _to be appended after this commit lands_ (docs: complete plan 50-01)

_TDD note: this plan ran the standard RED → GREEN cycle. No REFACTOR commit was needed — the GREEN implementation was already minimal (one one-line method body, one one-line call site insertion)._

## Files Created/Modified

- `musicstreamer/ui_qt/station_list_panel.py` — added `refresh_recent(self) -> None` (a public delegate to `_populate_recent`) inserted between `refresh_model` and `_sync_tree_expansion` so it sits inside the "# Public refresh API" block. Method explicitly does NOT touch the provider tree.
- `musicstreamer/ui_qt/main_window.py` — inserted `self.station_panel.refresh_recent()  # Phase 50 / BUG-01: live recent-list update (D-01, D-04)` immediately after the `update_last_played` line in `_on_station_activated`.
- `tests/test_station_list_panel.py` — appended `test_refresh_recent_updates_list` (mutates `repo._recent` then asserts row 0 in the QListView matches the new top station) and `test_refresh_recent_does_not_touch_tree` (asserts `panel.tree.model().rowCount()` is unchanged across the call).
- `tests/test_main_window_integration.py` — appended `test_station_activated_refreshes_recent_list` (seeds `_recent=[]`, monkey-patches `update_last_played` to prepend to `_recent`, asserts `recent_view` row count goes from 0 to 1 after the signal fires).

## Decisions Made

- **Method named `refresh_recent`** (no leading underscore) — public API parallel to existing `refresh_model`. Decision recorded in 50-RESEARCH.md "Open Question RESOLVED" and locked in PATTERNS.md.
- **Direct method call** (not `Signal` + `connect`, not `QTimer.singleShot`, not `Qt.QueuedConnection`) — D-04 from 50-CONTEXT.md. Synchronous rebuild of an in-process QStandardItemModel is cheap (n=3 SQLite query + 3 row appends); indirection would only delay the visual update.
- **Order at call site:** `update_last_played` BEFORE `refresh_recent`. Pitfall #1: `list_recently_played` reads the DB at call time, so the write must commit first. Verified by grep-verifiable acceptance criterion (`grep -B1 station_panel.refresh_recent | grep update_last_played`).
- **No call to `model.refresh` or `_sync_tree_expansion` from `refresh_recent`** — Pitfall #2 / SC #3. Calling `refresh_model` would have been the obvious "fix" but would collapse expanded provider groups every click. The narrow refresh is the whole point.
- **Strengthened the integration test (RED Task 1) when the original version threatened to pass vacuously.** The PLAN.md anticipated this exact failure mode and supplied a stronger version that monkey-patches `update_last_played` to mutate `_recent` — used as written.

## Deviations from Plan

None — plan executed exactly as written.

The plan included an "if integration test passes vacuously, use this stronger version" branch in Task 1's `<action>`. The stronger version was used (committed in 57e4b0c). This is plan-prescribed and not a deviation.

No deviation rules (Rule 1 bug, Rule 2 missing critical, Rule 3 blocking, Rule 4 architectural) fired during execution.

## Issues Encountered

None. The plan was small, the diff was tight, the test contracts were already encoded in PATTERNS.md, and the call-site insertion was a single line.

## User Setup Required

None — no external service configuration required.

## UAT Outcome (Task 3 — checkpoint:human-verify)

User ran the live app and confirmed:

- **SC #1 (clicked station appears at row 0 of Recently Played within the same session):** ✓ verified
- **SC #2 (previously-top station moves down or off the n=3 list):** ✓ verified
- **SC #3 (expanded provider group is preserved — no tree collapse):** ✓ verified
- **D-02 sanity check (failed plays stay at top, no rollback):** not specifically tested; not gating per user. No rollback behavior was disproven during the UAT.

User signal: "approved" (with all three success criteria explicitly called out as passing).

## Out-of-Scope Finding (NOT addressed in this phase)

During an unrelated launch hang, the OS force-quit dialog displayed `org.example.MusicStreamer` instead of `MusicStreamer`. This is a Linux WM display-name / WM_CLASS / `Gtk.set_program_name` / `QGuiApplication.setApplicationName` / GApplication-id surface — Linux parallel to the Windows AUMID/Start-Menu shortcut work in Phase 56 (WIN-02). Per the user, this is out of scope for Phase 50; the orchestrator will capture it as a backlog item after the plan closes. Logging it here for traceability — do NOT treat this as a Phase 50 deviation or auto-fix candidate.

## Next Phase Readiness

- BUG-01 closed; v2.1 phase counter advances to Phase 51 (AudioAddict Cross-Network Siblings).
- Pattern established (narrow public refresh entry point + DB-write-before-UI-refresh ordering) is directly applicable to upcoming Phase 55 (Edit Station Preserves Section State, BUG-06), which has structurally identical "save action collapses sections" symptom.
- No carryover blockers.

## Self-Check: PASSED

- `musicstreamer/ui_qt/station_list_panel.py` — verified contains `def refresh_recent(self) -> None` (commit 1cf6781).
- `musicstreamer/ui_qt/main_window.py` — verified contains `self.station_panel.refresh_recent()` call (commit 1cf6781).
- `tests/test_station_list_panel.py` — verified contains `def test_refresh_recent_updates_list` and `def test_refresh_recent_does_not_touch_tree` (commit 57e4b0c).
- `tests/test_main_window_integration.py` — verified contains `def test_station_activated_refreshes_recent_list` (commit 57e4b0c).
- Commit `57e4b0c` — verified present in `git log` (Task 1 RED).
- Commit `1cf6781` — verified present in `git log` (Task 2 GREEN).
- TDD gate sequence — verified: `test(50-01)` commit (57e4b0c) precedes `feat(50-01)` commit (1cf6781) in git log. RED → GREEN order satisfied.

---
*Phase: 50-recently-played-live-update*
*Completed: 2026-04-27*
