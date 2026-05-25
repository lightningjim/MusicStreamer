---
phase: 60-gbs-fm-integration
plan: "04"
subsystem: ui
tags: [phase60, accounts, cookies, gbs-fm, pyside6, qt, cookie-import]

# Dependency graph
requires:
  - phase: 60-02
    provides: "paths.gbs_cookies_path(), gbs_api._validate_gbs_cookies() — used for CookieImportDialog config"

provides:
  - "CookieImportDialog parameterized for any cookie-based auth provider (target_label/cookies_path/validator/oauth_mode kwargs)"
  - "AccountsDialog 'GBS.FM' QGroupBox between YouTube and Twitch (D-04c)"
  - "_on_gbs_action_clicked: Connect opens parameterized CookieImportDialog with GBS.FM config; Disconnect removes gbs-cookies.txt"
  - "_is_gbs_connected: os.path.exists(paths.gbs_cookies_path()) predicate"
  - "10 new tests (4 cookie_import_dialog + 6 accounts_dialog) covering regression + GBS.FM paths"

affects:
  - "60-05-now-playing-panel (GBS.FM vote/playlist visibility depends on _is_gbs_connected path)"
  - "60-06-search-submit (AccountsDialog GBS.FM status visible before search dialog)"
  - "Any future provider added via CookieImportDialog — parameterized interface is now stable"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Keyword-only constructor args (*) for per-instance dialog config — all providers share CookieImportDialog via kwargs"
    - "OSError catch (not just FileNotFoundError) for file removal in Disconnect handlers (HIGH 2 fix)"
    - "QA-05 bound-method connection for _gbs_action_btn.clicked (no self-capturing lambda)"
    - "T-40-04 Qt.TextFormat.PlainText on _gbs_status_label (defense against gbs.fm-side HTML)"
    - "Phase 999.7 0o600 inherited by GBS.FM write path via _write_cookies refactor"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/cookie_import_dialog.py
    - musicstreamer/ui_qt/accounts_dialog.py
    - tests/test_cookie_import_dialog.py
    - tests/test_accounts_dialog.py

key-decisions:
  - "D-04 ladder #3 LOCKED: CookieImportDialog refactor (Option 1 — parameterize, not subclass) per RESEARCH §Pattern 4"
  - "oauth_mode=None for GBS.FM v1 — only File + Paste tabs; OAuth subprocess deferred (RESEARCH Q3)"
  - "OSError catch replaces FileNotFoundError catch in _on_gbs_action_clicked — broader error tolerance"
  - "test_group_order updated to assert YouTube->GBS.FM->Twitch->AudioAddict ordering"

patterns-established:
  - "Per-provider CookieImportDialog: pass target_label/cookies_path/validator/oauth_mode as keyword-only args"
  - "AccountsDialog provider QGroupBox shape: status_label (PlainText + status_font) + action_btn (bound-method)"

requirements-completed: [GBS-01b]

# Metrics
duration: 25min
completed: 2026-05-04
---

# Phase 60 Plan 04: Accounts Summary

**AccountsDialog GBS.FM QGroupBox (D-04c) with Connect/Disconnect flow, and CookieImportDialog refactored to accept per-instance provider config via keyword-only kwargs (target_label/cookies_path/validator/oauth_mode)**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-04T19:54:00Z
- **Completed:** 2026-05-04T20:19:48Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 4

## Accomplishments

- Refactored `CookieImportDialog` to accept 4 keyword-only kwargs with YouTube-preserving defaults; all 15 prior tests continue to pass
- Added `AccountsDialog._gbs_box` QGroupBox between YouTube and Twitch per D-04c; status label uses PlainText (T-40-04) and shared status_font (T-11-A)
- `_on_gbs_action_clicked` opens CookieImportDialog with `target_label="GBS.FM"`, `cookies_path=paths.gbs_cookies_path`, `validator=gbs_api._validate_gbs_cookies`, `oauth_mode=None`
- Cookie file written with 0o600 perms at `paths.gbs_cookies_path()` via `_write_cookies` refactor
- 10 new tests added (4 in `test_cookie_import_dialog.py`, 6 in `test_accounts_dialog.py`)

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1 RED: Failing tests for CookieImportDialog** - `5f2ddfc` (test)
2. **Task 1 GREEN: Parameterize CookieImportDialog** - `9b0e6aa` (feat)
3. **Task 2 RED: Failing tests for AccountsDialog GBS** - `4252d36` (test)
4. **Task 2 GREEN: Add GBS.FM QGroupBox to AccountsDialog** - `570f295` (feat)

## TDD Gate Compliance

- RED gate commits exist: `5f2ddfc` (Task 1), `4252d36` (Task 2)
- GREEN gate commits exist: `9b0e6aa` (Task 1), `570f295` (Task 2)

## Files Created/Modified

- `musicstreamer/ui_qt/cookie_import_dialog.py` — Added `target_label`/`cookies_path`/`validator`/`oauth_mode` keyword-only args; replaced all hardcoded YouTube strings/paths/validators with per-instance config; oauth_mode=None disables OAuth tab
- `musicstreamer/ui_qt/accounts_dialog.py` — Added `_gbs_box` QGroupBox block, `_is_gbs_connected()`, extended `_update_status()`, added `_on_gbs_action_clicked()` handler
- `tests/test_cookie_import_dialog.py` — 4 new Phase 60 tests (regression + GBS.FM construction, error label, write+0o600)
- `tests/test_accounts_dialog.py` — 6 new `TestAccountsDialogGBS` tests; updated `test_group_order` assertion to include GBS.FM

## Decisions Made

- D-04 ladder #3 LOCKED: parameterize `CookieImportDialog` (Option 1 per RESEARCH §Pattern 4) — one dialog class serves all providers via kwargs, no subclass/duplication
- `oauth_mode=None` for GBS.FM v1 per RESEARCH Q3: only File + Paste tabs rendered; OAuth subprocess is optional polish for a future plan
- Disconnect handler catches `OSError` (not just `FileNotFoundError`) to tolerate race conditions including PermissionError and IsADirectoryError

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Changed isVisible() to isHidden() in test_gbs_paste_invalid_shows_target_specific_error**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** `dlg._error_label.isVisible()` returns False when the dialog is not shown (widget not realized), even after `setVisible(True)` is called. Existing tests in the file use `not dlg._error_label.isHidden()` which checks the widget's own explicit visibility flag.
- **Fix:** Changed test assertion from `assert dlg._error_label.isVisible()` to `assert not dlg._error_label.isHidden()` to match the established pattern in the file.
- **Files modified:** `tests/test_cookie_import_dialog.py`
- **Verification:** Test passes with assertion fix; error label is correctly set to visible by `_show_error()`
- **Committed in:** `9b0e6aa` (Task 1 GREEN)

**2. [Rule 1 - Bug] Updated test_group_order to assert new 4-group ordering**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** Existing `test_group_order` expected `["YouTube", "Twitch", "AudioAddict"]`; after adding the GBS.FM group, the layout now has 4 groups. The test correctly identified the new state as a regression — but the regression was expected and intentional (we added a new group).
- **Fix:** Updated assertion to `["YouTube", "GBS.FM", "Twitch", "AudioAddict"]` to reflect D-04c group ordering.
- **Files modified:** `tests/test_accounts_dialog.py`
- **Verification:** Test passes; confirms GBS.FM group is in correct position.
- **Committed in:** `570f295` (Task 2 GREEN)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — test adjustments)
**Impact on plan:** Minor test correctness fixes. No scope creep; no behavioral changes.

## Issues Encountered

- Pre-existing `tests/test_media_keys_mpris2.py::test_linux_mpris_backend_constructs` failure (D-Bus not available in headless test environment) — unrelated to Plan 60-04; confirmed pre-existing by stash verification.

## Known Stubs

None — all GBS.FM status detection and cookie write paths are fully wired. The "Connect" button opens a real dialog that writes to `paths.gbs_cookies_path()`. The status detection reads from the same path. No hardcoded or placeholder data flows to the UI.

## Threat Flags

No new security surface introduced beyond the plan's threat model. The parameterized `CookieImportDialog` keeps the validator/path paired in a single constructor call (T-60-18), and the GBS.FM status label uses PlainText format (T-60-21).

## Next Phase Readiness

- `paths.gbs_cookies_path()` + `_is_gbs_connected()` predicate ready for use by Plans 60-05/60-06 (vote/playlist panel: show controls only when GBS.FM connected)
- `CookieImportDialog` parameterization is stable; any future provider needs only to supply its own `target_label`/`cookies_path`/`validator` kwargs

---
*Phase: 60-gbs-fm-integration*
*Completed: 2026-05-04*
