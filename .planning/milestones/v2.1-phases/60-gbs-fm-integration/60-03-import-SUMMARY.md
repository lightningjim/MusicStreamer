---
phase: 60-gbs-fm-integration
plan: 03
subsystem: ui
tags: [phase60, import, hamburger-menu, gbs-fm, qthread, worker-thread, tdd]

# Dependency graph
requires:
  - phase: "60-02"
    provides: "musicstreamer/gbs_api.py: import_station() + GbsAuthExpiredError + GbsApiError"
provides:
  - "musicstreamer/ui_qt/main_window.py: _GbsImportWorker QThread + act_gbs_add menu entry + _on_gbs_add_clicked + _on_gbs_import_finished + _on_gbs_import_error"
  - "tests/test_main_window_gbs.py: 8 pytest-qt tests covering D-02, D-02a, D-02b, Pitfall 3, T-60-15, QA-05"
affects:
  - "60-04-accounts (UI companion for auth plumbing that workers invoke)"
  - "60-07-search-submit (will add sibling act_gbs_search at same menu location)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_GbsImportWorker QThread mirrors _ExportWorker shape: lazy gbs_api import in run(), emits finished(int,int)/error(str)"
    - "auth_expired sentinel string: GbsAuthExpiredError -> sentinel -> UI translates to reconnect toast (avoids raw exception text in toast)"
    - "SYNC-05 worker retention: self._gbs_import_worker held as instance attr, None-out on completion/error"
    - "QA-05 bound method: act_gbs_add.triggered.connect(self._on_gbs_add_clicked) — no lambda"

key-files:
  created:
    - "tests/test_main_window_gbs.py"
  modified:
    - "musicstreamer/ui_qt/main_window.py"
    - "tests/test_main_window_integration.py"

key-decisions:
  - "D-02 menu placement: 'Add GBS.FM' inserted between 'Import Stations' and first addSeparator in Group 1"
  - "D-02a idempotent toast: inserted=1 -> 'GBS.FM added'; updated=1 -> 'GBS.FM streams updated'; else -> 'GBS.FM import: no changes'"
  - "D-02b always-present: no hide/disable logic; action isEnabled() always True"
  - "Pitfall 3 auth sentinel: GbsAuthExpiredError -> emit 'auth_expired' string -> _on_gbs_import_error special-cases it"
  - "T-60-15 truncation: generic error messages truncated to 80 chars + ellipsis before toast display"
  - "BLOCKER 2 fix: EXPECTED_ACTION_TEXTS updated to include 'Add GBS.FM' (10 entries) so test_hamburger_menu_actions stays passing"

patterns-established:
  - "_GbsImportWorker pattern: lazy gbs_api import inside QThread.run() avoids import-time side-effects; mirrors _ExportWorker"

requirements-completed: [GBS-01a]

# Metrics
duration: 6min
completed: 2026-05-04
---

# Phase 60 Plan 03: GBS.FM Import UI Summary

**'Add GBS.FM' hamburger menu entry wired to gbs_api.import_station via _GbsImportWorker QThread with idempotent insert/update toasts, auth-expired reconnect prompt, and 8 passing pytest-qt tests**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-04T20:12:55Z
- **Completed:** 2026-05-04T20:18:54Z
- **Tasks:** 2 completed
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- Added `_GbsImportWorker(QThread)` class to `main_window.py` mirroring `_ExportWorker` shape: lazy gbs_api import in `run()`, `finished(int, int)` signal for `(inserted, updated)`, `error(str)` signal with `"auth_expired"` sentinel for `GbsAuthExpiredError`
- Wired "Add GBS.FM" hamburger menu entry in Group 1 (between "Import Stations" and first separator) with bound-method connection per QA-05
- Implemented `_on_gbs_add_clicked`, `_on_gbs_import_finished`, `_on_gbs_import_error` handlers: D-02a toast distinction (inserted/updated/no-changes), T-60-15 error truncation at 80 chars, Pitfall 3 reconnect prompt
- Applied BLOCKER 2 fix: updated `EXPECTED_ACTION_TEXTS` in `test_main_window_integration.py` to 10 entries so `test_hamburger_menu_actions` stays passing
- Created `tests/test_main_window_gbs.py` with 8 tests: menu entry presence, worker start, D-02a toast variants, Pitfall 3 reconnect toast, T-60-15 truncation, QA-05 grep guard

## Task Commits

1. **Task 1 RED: update EXPECTED_ACTION_TEXTS** - `d661ebb` (test)
2. **Task 1 GREEN: add _GbsImportWorker + menu entry + handlers** - `2d5ea35` (feat)
3. **Task 2: create tests/test_main_window_gbs.py** - `babb2fc` (feat)

## Files Created/Modified

- `musicstreamer/ui_qt/main_window.py` — `_GbsImportWorker` class (32 LOC) + menu entry + `_gbs_import_worker = None` init + 3 handler methods (41 LOC); total ~73 LOC added
- `tests/test_main_window_gbs.py` — 8 pytest-qt tests (242 LOC); covers D-02, D-02a, D-02b, Pitfall 3, T-60-15, QA-05
- `tests/test_main_window_integration.py` — `EXPECTED_ACTION_TEXTS` updated to include "Add GBS.FM" (10 entries); docstring updated to "exactly 10 non-separator actions"

## Decisions Made

- **auth_expired sentinel**: Rather than propagating the raw `GbsAuthExpiredError` message through the signal, the worker emits the string `"auth_expired"` as a sentinel. The error handler special-cases it to show a user-friendly reconnect toast. Mirrors D-03c typing approach from CONTEXT.md.
- **BLOCKER 2 fix mandatory**: Plan explicitly flagged updating `EXPECTED_ACTION_TEXTS` as a BLOCKER (not conditional). Applied as Step E of Task 1 action.
- **8 tests vs 7 in plan**: Added `test_import_error_long_message_truncated` to explicitly test T-60-15 truncation at 80 chars (plan listed 7 tests in behavior but 7 items including truncation; the test covers it as a distinct test).

## Deviations from Plan

None - plan executed exactly as written. BLOCKER 2 fix was part of the plan's mandatory Step E.

## Known Stubs

None — all handler methods are fully implemented. Worker invokes the real `gbs_api.import_station()` off-thread.

## Threat Flags

No new threat surface beyond what the plan's threat_model documented. All 5 STRIDE entries (T-60-12 through T-60-16) are mitigated:
- T-60-12 (DoS/UI thread): _GbsImportWorker offloads import off-main-thread; "Importing GBS.FM..." toast shown pre-emptively
- T-60-13 (Auth expiry): GbsAuthExpiredError -> "auth_expired" sentinel -> reconnect prompt
- T-60-14 (Lambda/self capture): QA-05 enforced by grep guard test
- T-60-15 (Long error text): truncated to 80 chars + ellipsis before toast
- T-60-16 (Worker GC race): self._gbs_import_worker retention + None-out on completion/error

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `musicstreamer/ui_qt/main_window.py` has `addAction("Add GBS.FM")` | FOUND |
| `musicstreamer/ui_qt/main_window.py` has `_GbsImportWorker` | FOUND |
| `musicstreamer/ui_qt/main_window.py` has `_on_gbs_add_clicked` | FOUND |
| `musicstreamer/ui_qt/main_window.py` has `GBS.FM streams updated` | FOUND |
| `musicstreamer/ui_qt/main_window.py` has `auth_expired` | FOUND |
| `tests/test_main_window_gbs.py` exists | FOUND |
| `tests/test_main_window_integration.py` has "Add GBS.FM" | FOUND |
| Commit d661ebb (Task 1 RED) | FOUND |
| Commit 2d5ea35 (Task 1 GREEN) | FOUND |
| Commit babb2fc (Task 2) | FOUND |
| `python -m pytest tests/test_main_window_gbs.py tests/test_gbs_api.py` | 26 passed |
| `test_hamburger_menu_actions` passes | PASSED |
| Module import: `from musicstreamer.ui_qt.main_window import MainWindow, _GbsImportWorker` | OK |
| QA-05 grep: `act_gbs_add.triggered.connect(self._on_gbs_add_clicked)` | FOUND |
| Syntax check: `ast.parse(main_window.py)` | OK |

## TDD Gate Compliance

- **RED gate**: `d661ebb` — `test(60-03): RED — add 'Add GBS.FM' to EXPECTED_ACTION_TEXTS` committed before implementation. `test_hamburger_menu_actions` failed confirming RED.
- **GREEN gate**: `2d5ea35` — `feat(60-03): add _GbsImportWorker + 'Add GBS.FM' menu entry + handler methods` committed after RED; `test_hamburger_menu_actions` passed confirming GREEN.
- No REFACTOR gate needed — code was clean on first pass.
