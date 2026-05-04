---
phase: 60-gbs-fm-integration
plan: "07"
subsystem: ui
tags: [phase60, search-submit, dialog, gbs-fm, pyside6, qt, tdd, wave4]

# Dependency graph
requires:
  - phase: 60-02
    provides: "gbs_api.search, gbs_api.submit, GbsAuthExpiredError, load_auth_context signatures"
  - phase: 60-04
    provides: "paths.gbs_cookies_path() for D-08c login-gate check; _is_gbs_connected predicate"

provides:
  - "musicstreamer/ui_qt/gbs_search_dialog.py: GBSSearchDialog(QDialog) + _GbsSearchWorker + _GbsSubmitWorker"
  - "musicstreamer/ui_qt/main_window.py: 'Search GBS.FM...' hamburger entry + _open_gbs_search_dialog handler"
  - "tests/test_gbs_search_dialog.py: 16 pytest-qt tests covering search/submit/login-gate/pagination/auth-expired/HIGH-5"

affects:
  - "Any future plan adding 'submit history' UI (can connect submission_completed signal)"
  - "Any future plan extending the hamburger menu (test_hamburger_menu_actions lock at 11 actions)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GBSSearchDialog inherits DiscoveryDialog shape: QStandardItemModel + QTableView + per-row QPushButton via setIndexWidget"
    - "_make_submit_slot(row_idx) closure factory for QA-05-compliant per-row connections (no self-capturing lambda)"
    - "HIGH 5 fix: monotonic _search_version token incremented on each search; _GbsSubmitWorker.search_version stamp used to discard stale callbacks"
    - "sender() is not None guard for stale-discard: None sender = direct call (tests), not stale signal"
    - "D-08c login gate: _refresh_login_gate() called on __init__ + showEvent; disables search UI until cookies present"
    - "D-08d message disambiguation: success vs error by keyword scan of Django messages cookie text"
    - "D-08e Prev/Next pagination from total_pages returned by gbs_api.search"

key-files:
  created:
    - "musicstreamer/ui_qt/gbs_search_dialog.py"
    - "tests/test_gbs_search_dialog.py"
  modified:
    - "musicstreamer/ui_qt/main_window.py"
    - "tests/test_main_window_integration.py"

key-decisions:
  - "sender() returns None in direct test calls — treat as valid (not stale); only discard when sender is non-None with mismatched version"
  - "'enough tokens' added alongside 'not enough tokens' in is_error keyword list (covers GBS.FM's actual message: 'don't have enough tokens')"
  - "_open_gbs_search_dialog does NOT connect submission_completed (submit doesn't change local library; no station-list refresh needed)"

patterns-established:
  - "Per-row action in GBS search dialog uses _make_submit_slot factory (exact mirror of discovery_dialog._make_save_slot)"
  - "Auth-expired toast path in both search and submit workers: 'GBS.FM session expired — reconnect via Accounts'"

requirements-completed: [GBS-01e]

# Metrics
duration: 7min
completed: 2026-05-04
---

# Phase 60 Plan 07: Search + Submit Summary

**GBSSearchDialog (D-08) with worker-thread search + per-row submit, full D-08c login gate, inline errors for duplicate/quota (D-08d), Prev/Next pagination (D-08e), and HIGH 5 stale-submit discard via monotonic search_version token**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-04T20:36:06Z
- **Completed:** 2026-05-04T20:43:07Z
- **Tasks:** 3 completed
- **Files modified:** 4 (2 created + 2 modified)

## Accomplishments

- Created `musicstreamer/ui_qt/gbs_search_dialog.py` (436 LOC) with:
  - `GBSSearchDialog(QDialog)`: non-modal, 640x480 minimum, D-08c login gate on `__init__` + `showEvent`
  - `_GbsSearchWorker(QThread)`: emits `finished(list, int, int)` (results, page, total_pages) + `error(str)`
  - `_GbsSubmitWorker(QThread)`: emits `finished(str, int)` (Django messages text, row_idx) + `error(str, int)`
  - Per-row "Add!" buttons via `_make_submit_slot` closure factory (QA-05, no self-capturing lambda)
  - Prev/Next pagination from `total_pages` in `gbs_api.search` response
  - HIGH 5 monotonic `_search_version` token discards stale submit callbacks after re-search
- Added "Search GBS.FM…" menu entry + `_open_gbs_search_dialog` handler to `main_window.py`
- Created `tests/test_gbs_search_dialog.py` (264 LOC, 16 tests) covering all D-08 requirement rows
- Updated `EXPECTED_ACTION_TEXTS` in `test_main_window_integration.py` (11 actions, BLOCKER 2 fix)

## Task Commits

1. **Task 1: Create gbs_search_dialog.py** - `7635038` (feat)
2. **Task 2 RED: Update EXPECTED_ACTION_TEXTS** - `b034851` (test)
3. **Task 2 GREEN: Add menu entry + handler to main_window.py** - `409e064` (feat)
4. **Task 3: Create test_gbs_search_dialog.py + fix sender/keyword bugs** - `62f7997` (feat)

## Files Created/Modified

- `musicstreamer/ui_qt/gbs_search_dialog.py` — 436 LOC; GBSSearchDialog + 2 worker classes; login gate; inline error; Prev/Next pagination; submission_completed signal
- `musicstreamer/ui_qt/main_window.py` — 16 lines added: act_gbs_search menu action + _open_gbs_search_dialog handler
- `tests/test_gbs_search_dialog.py` — 264 LOC; 16 tests covering D-08a/b/c/d/e, QA-05 grep guard, HIGH 5 stale discard
- `tests/test_main_window_integration.py` — EXPECTED_ACTION_TEXTS updated to include "Search GBS.FM…" (11 actions)

## Decisions Made

- **sender() None check**: `sender()` returns None when `_on_submit_finished` / `_on_submit_error` are called directly in tests (not via Qt signal). Changed stale-discard guard from `if worker is None or version != current` to `if worker is not None and version != current`. This correctly allows direct test calls while still discarding stale signal callbacks.
- **Token-quota keyword expansion**: GBS.FM's actual token-quota message is "You don't have enough tokens", which does not contain the phrase "not enough tokens" that was in the plan's `is_error` keyword list. Added `"enough tokens"` as a broader match to catch this variant (Pitfall 8 real-world message).
- **submission_completed not connected in handler**: The `_open_gbs_search_dialog` handler does not connect the `submission_completed` signal to `_refresh_station_list`. Submitting a GBS.FM song does not modify the local library, so no station-list refresh is needed. Future plans that add a "submit history" widget can connect the signal at that point.

## TDD Gate Compliance

- **Task 1 RED gate**: `test_gbs_search_dialog_red.py::test_gbs_search_dialog_exists` failed with `ModuleNotFoundError` before `gbs_search_dialog.py` existed. Removed temp file after GREEN.
- **Task 1 GREEN gate**: Module created; all import checks passed.
- **Task 2 RED gate**: `test_hamburger_menu_actions` failed after `EXPECTED_ACTION_TEXTS` was updated with "Search GBS.FM…" (commit b034851). Test expected 11 actions; menu had 10.
- **Task 2 GREEN gate**: Menu entry + handler added; `test_hamburger_menu_actions` passes (commit 409e064).
- **Task 3 GREEN gate**: 16 tests pass in `test_gbs_search_dialog.py`; 18 in `test_gbs_api.py`; 46 in `test_main_window_integration.py`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] sender() None check caused tests to be discarded as stale**

- **Found during:** Task 3 (GREEN phase — test_submit_success_toasts_track_added)
- **Issue:** `_on_submit_finished` used `if worker is None or version != current_version: return`. Since `self.sender()` returns `None` when called directly in tests (not via Qt signal), ALL direct test calls to `_on_submit_finished` / `_on_submit_error` were being discarded as stale.
- **Fix:** Changed guard to `if worker is not None and version != current_version: return`. A `None` sender means the method was called directly (test or programmatic call) — not stale; proceed normally. A non-None sender with mismatched version is definitively stale.
- **Files modified:** `musicstreamer/ui_qt/gbs_search_dialog.py`
- **Committed in:** `62f7997` (Task 3)

**2. [Rule 1 - Bug] Token-quota keyword 'not enough tokens' didn't match GBS.FM's actual message**

- **Found during:** Task 3 (test_submit_inline_error_on_token_quota failing)
- **Issue:** The plan's `is_error` keyword list included `"not enough tokens"` but GBS.FM sends `"You don't have enough tokens"`. The substring `"not enough tokens"` is not present in `"don't have enough tokens"`.
- **Fix:** Added `"enough tokens"` to the keyword list, which is a substring of GBS.FM's actual message. The original `"not enough tokens"` is retained for any alternative message variants.
- **Files modified:** `musicstreamer/ui_qt/gbs_search_dialog.py`
- **Committed in:** `62f7997` (Task 3)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — correctness bugs found during GREEN)
**Impact on plan:** Both fixes were necessary for tests to pass. No scope creep; no behavioral changes from user perspective.

## Known Stubs

None — all search, submit, pagination, and login-gate flows are fully wired to `gbs_api` functions. No hardcoded empty values flow to the UI rendering path.

## Threat Flags

No new security surface beyond the plan's `<threat_model>`. The dialog makes no direct HTTP calls — all network access goes through `gbs_api.search` and `gbs_api.submit` which have their own STRIDE mitigations (T-60-34 through T-60-41). The dialog itself:
- Only reads user-controlled query text (urlencoded by gbs_api.search)
- Renders server results via QStandardItem PlainText (T-60-39 / T-40-04)
- Surfaces Django messages cookie text verbatim in inline error or toast (T-60-36)

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `musicstreamer/ui_qt/gbs_search_dialog.py` exists (436 LOC) | FOUND |
| `tests/test_gbs_search_dialog.py` exists (264 LOC, 16 tests) | FOUND |
| "Search GBS.FM…" in main_window.py menu | FOUND |
| `_open_gbs_search_dialog` handler exists | FOUND |
| Commit 7635038 (Task 1) | FOUND |
| Commit b034851 (Task 2 RED) | FOUND |
| Commit 409e064 (Task 2 GREEN) | FOUND |
| Commit 62f7997 (Task 3) | FOUND |
| 16 tests in test_gbs_search_dialog.py pass | PASS |
| 46 tests in test_main_window_integration.py pass | PASS |
| 18 tests in test_gbs_api.py pass | PASS |
| No QA-05 lambda violations | PASS |
| No new network endpoints in dialog (all via gbs_api) | PASS |

---
*Phase: 60-gbs-fm-integration*
*Completed: 2026-05-04*
