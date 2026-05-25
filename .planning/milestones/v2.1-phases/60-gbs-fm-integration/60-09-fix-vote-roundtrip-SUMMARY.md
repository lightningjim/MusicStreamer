---
phase: 60-gbs-fm-integration
plan: "09"
subsystem: ui
tags: [phase60, gap-closure, vote, optimistic-ui, ui-affordance, qa-05, pyside6, tdd]

# Dependency graph
requires:
  - phase: 60-05-active-playlist
    provides: "_on_gbs_playlist_ready signal pipeline and entryid stamp"
  - phase: 60-06-vote
    provides: "_on_gbs_vote_clicked handler, gbs_vote_error_toast Signal, _last_confirmed_vote"
provides:
  - "Vote button enable/disable gate (_apply_vote_buttons_enabled) backed by entryid stamp"
  - "Cookies-None toast emission in _on_gbs_vote_clicked cookies-None guard"
  - "test_gbs_vote_no_entryid_ignores_click updated to bypass Qt-level gate so in-handler guard remains exercised"
affects:
  - "60-gbs-fm-integration"
  - "now_playing_panel vote affordance"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_apply_vote_buttons_enabled(bool) as a single-responsibility enable-gate helper (parallel to _apply_vote_highlight)"
    - "setEnabled(False) in constructor loop placed AFTER clicked.connect (PINNED: wiring intact, button intentionally not yet usable)"
    - "Test isolation via monkeypatch of instance method (_on_gbs_poll_tick) to break recursion in test fixture"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py
    - tests/test_now_playing_panel.py

key-decisions:
  - "60-09-D1: setEnabled(False) placed AFTER btn.clicked.connect in constructor loop (PINNED) — documents that signal wiring is intact and the button is intentionally not yet usable; functionally equivalent to other orderings but pinned to remove future ambiguity"
  - "60-09-D2: _apply_vote_buttons_enabled(True) placed INSIDE the `if new_entryid is not None:` block in _on_gbs_playlist_ready — only enables when we actually have an entryid"
  - "60-09-D3: _apply_vote_buttons_enabled(False) added inside the `if not should_show:` branch of _refresh_gbs_visibility — leaving GBS context re-disables buttons"
  - "60-09-D4: toast message 'GBS.FM session expired — reconnect via Accounts' matches the auth_expired message already used by _on_gbs_vote_error for UX consistency"
  - "60-09-D5: test_gbs_vote_emits_toast_when_cookies_disappear_mid_click stubs _on_gbs_poll_tick to prevent recursion — production avoids the recursion because actual file removal changes _is_gbs_logged_in(); test decouples them without weakening the tested path"
  - "60-09-D6: test_gbs_vote_no_entryid_ignores_click updated to setEnabled(True) before click so the in-handler entryid-None guard remains exercised (defense-in-depth); test was passing for the wrong reason after Step 2a (Qt-level gate, not in-handler guard)"

patterns-established:
  - "Enable-gate helper pattern: _apply_vote_buttons_enabled(bool) mirrors _apply_vote_highlight — single-responsibility, all 5 buttons toggled in one call"
  - "Stub instance methods via monkeypatch.setattr(panel, '_method', lambda: None) to break recursion in Qt-based tests"

requirements-completed: [GBS-01d]

# Metrics
duration: 5min
completed: 2026-05-04
---

# Phase 60 Plan 09: Fix Vote Roundtrip Summary

**Vote buttons disabled at construction via setEnabled(False), re-enabled by _on_gbs_playlist_ready once entryid is known; cookies-None guard in _on_gbs_vote_clicked now emits gbs_vote_error_toast before rolling back (T10 + T11 closed)**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-04T23:20:15Z
- **Completed:** 2026-05-04T23:24:36Z
- **Tasks:** 2 (TDD-RED + TDD-GREEN)
- **Files modified:** 2

## Accomplishments

- T10 closed: vote buttons are visibly disabled (greyed) until the first /ajax response stamps `_gbs_current_entryid`; clicks during the disabled window are physically blocked (no silent drop, no false affordance)
- T11 closed: the cookies-None guard in `_on_gbs_vote_clicked` now emits `gbs_vote_error_toast` with the auth-expired UX message before rolling back, matching the existing `_on_gbs_vote_error` toast path
- `_apply_vote_buttons_enabled(bool)` helper added as a single-responsibility enable-gate (3 occurrences: definition + 2 call sites in `_on_gbs_playlist_ready` and `_refresh_gbs_visibility`)
- `test_gbs_vote_no_entryid_ignores_click` updated to bypass the new Qt-level disabled-button gate via `setEnabled(True)` so the in-handler entryid-None guard remains exercised (defense-in-depth)
- 74 tests pass (71 pre-existing + 3 new); `test_gbs_api.py` pre-existing 5 failures unaffected

## Task Commits

Each task was committed atomically (TDD pattern):

1. **Task 1 (TDD-RED): 3 failing tests for T10 + T11** - `5471d19` (test)
2. **Task 2 (TDD-GREEN): production fix + test_gbs_vote_no_entryid_ignores_click update** - `d421cc9` (fix)

**Plan metadata:** committed with SUMMARY in this commit (docs)

_Note: TDD tasks have two commits (test RED → fix GREEN). test_gbs_vote_no_entryid_ignores_click update committed in GREEN because it is a direct consequence of Step 2a (disabled-button gate)._

## Files Created/Modified

- `musicstreamer/ui_qt/now_playing_panel.py` — added `_apply_vote_buttons_enabled(bool)` helper; added `setEnabled(False)` in constructor loop (pinned after `clicked.connect`); wired `_apply_vote_buttons_enabled(True)` in `_on_gbs_playlist_ready`; wired `_apply_vote_buttons_enabled(False)` in `_refresh_gbs_visibility` hide path; added `gbs_vote_error_toast.emit(...)` before the cookies-None early-return in `_on_gbs_vote_clicked`
- `tests/test_now_playing_panel.py` — added 3 new tests (`test_gbs_vote_buttons_disabled_until_entryid_stamped`, `test_gbs_vote_buttons_enabled_after_first_ajax`, `test_gbs_vote_emits_toast_when_cookies_disappear_mid_click`); updated `test_gbs_vote_no_entryid_ignores_click` to bypass Qt-level gate via `setEnabled(True)`

## Decisions Made

- Used `_apply_vote_buttons_enabled(bool)` helper (parallel to `_apply_vote_highlight`) rather than inlining `setEnabled` calls — single call site per toggle direction, clear intent
- `setEnabled(False)` placed AFTER `btn.clicked.connect(...)` in constructor loop (PINNED placement per revision-2 directive) — documents that signal wiring is intact and the button is intentionally not yet usable
- Toast message reuses exact string `"GBS.FM session expired — reconnect via Accounts"` from `_on_gbs_vote_error` line 1090 for UX consistency
- `test_gbs_vote_emits_toast_when_cookies_disappear_mid_click` stubs `panel._on_gbs_poll_tick` to prevent recursion — in production, the actual file removal also changes `_is_gbs_logged_in()`, breaking the recursion naturally; in the test, these are decoupled by monkeypatching

## TDD Gate Compliance

- RED gate: `test(60-09): add failing tests...` commit `5471d19` — 3 new tests fail with expected assertion shapes (isEnabled True when should be False; signal not emitted)
- GREEN gate: `fix(60-09): disable vote buttons...` commit `d421cc9` — all 74 tests pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Stubbed _on_gbs_poll_tick in test to break recursion**
- **Found during:** Task 2 (GREEN — test_gbs_vote_emits_toast_when_cookies_disappear_mid_click)
- **Issue:** When `gbs_api.load_auth_context` returns `None` but the cookie FILE still exists on disk, `_on_gbs_poll_tick` calls `_refresh_gbs_visibility` which calls `_on_gbs_poll_tick` again (infinite recursion). This only manifests in the test fixture where the two conditions are decoupled (file exists + auth_context=None). In production, removing the cookie file also changes `_is_gbs_logged_in()`, breaking the recursion naturally.
- **Fix:** Added `monkeypatch.setattr(panel, "_on_gbs_poll_tick", lambda: None)` in the test after `load_auth_context` is patched to `None`. The tested path (click → cookies-None branch → toast emit → rollback → `_refresh_gbs_visibility`) is exercised correctly; only the recursive `_on_gbs_poll_tick` re-entry inside `_refresh_gbs_visibility` is stubbed out.
- **Files modified:** `tests/test_now_playing_panel.py`
- **Verification:** `test_gbs_vote_emits_toast_when_cookies_disappear_mid_click` passes, `qtbot.waitSignal` fires, `blocker.args[0]` contains "session expired"
- **Committed in:** `d421cc9` (Task 2 GREEN commit)

Note (per revision-2 plan directive): `test_gbs_vote_no_entryid_ignores_click` was updated to bypass the new disabled-button Qt gate so the in-handler guard remains exercised — this is documented in the plan's Step 2f and is not an unplanned deviation, but rather an explicitly required update.

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing test isolation for recursive call path)
**Impact on plan:** Fix is purely in test infrastructure, not production code. Does not weaken coverage of the cookies-None toast path. No scope creep.

## Issues Encountered

None beyond the test recursion issue documented in Deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- T10 and T11 are closed. Vote buttons now behave correctly:
  - Disabled (greyed) at construction; enabled after first /ajax response
  - Cookies-None mid-click surfaces a toast matching the auth-expired UX
- No blockers. 60-10 and 60-11 gap-closure plans are independent.

## Known Stubs

None. All production code paths are wired; no placeholder values or TODO markers introduced.

## Threat Flags

None. Changes are strictly UI state management (enable/disable QPushButton) and toast emission. No new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check

Files created/modified:

- [x] `musicstreamer/ui_qt/now_playing_panel.py` — exists and modified
- [x] `tests/test_now_playing_panel.py` — exists and modified

Commits:

- [x] `5471d19` — RED test commit
- [x] `d421cc9` — GREEN fix commit

## Self-Check: PASSED

---
*Phase: 60-gbs-fm-integration*
*Completed: 2026-05-04*
