---
phase: 46-ui-polish-theme-tokens-logo-status-cleanup
plan: 02
subsystem: ui

tags: [pyside6, qt, qtimer, qcursor, edit-station-dialog, tdd]

# Dependency graph
requires:
  - phase: 46-01
    provides: "musicstreamer/ui_qt/_theme.py exporting ERROR_COLOR_HEX (and sibling tokens); required at module-import time by edit_station_dialog.py"
provides:
  - "3-arg _LogoFetchWorker.finished signal (tmp_path, token, classification) distinguishing AA-URL-but-no-key from other unsupported URLs"
  - "Parented _logo_status_clear_timer (QTimer(self), 3000ms, single-shot) auto-clearing terminal status messages"
  - "Wait cursor override stack-balanced 1:1 with a single restore at the top of _on_logo_fetched (before stale-token check)"
  - "_DELETE_BTN_QSS migrated from raw #c0392b to f-string consuming ERROR_COLOR_HEX (completes the edit_station_dialog hex-removal half of Plan 46-01's scope)"
affects: [phase-47, phase-48]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cancellable QTimer attribute pattern (QTimer(self) + setSingleShot + setInterval + timeout.connect + .start()/.stop()) for deferred-and-cancellable UI actions — contrasts with the free-function QTimer.singleShot form used elsewhere"
    - "Cursor override paired 1:1 at top of sole finished slot (before stale-token early return) so every setOverrideCursor has exactly one matching restoreOverrideCursor regardless of which branch returns"
    - "Signal-arity widening with default-valued slot signature so existing positional-call tests keep working (token: int = 0, classification: str = '')"

key-files:
  created: []
  modified:
    - "musicstreamer/ui_qt/edit_station_dialog.py — AA classification, auto-clear timer, cursor override, _DELETE_BTN_QSS hex migration"
    - "tests/test_edit_station_dialog.py — 4 new behavioral tests (AA-no-key message, 3s auto-clear, textChanged cancel, worker emit classification)"

key-decisions:
  - "Classification emitted BEFORE the _fetch_image_map import so the aa_no_key early-return branch does not depend on aa_import being importable (reduces failure coupling)"
  - "QTimer(self) parented form chosen over the existing unparented QTimer() pattern for the new clear timer (G-1 safety — timer cleaned up with dialog)"
  - "'Enter a URL first' status now also arms the 3s auto-clear timer for UX uniformity (minor extension of D-09 beyond the strict plan)"
  - "Cursor restoreOverrideCursor called at the TOP of _on_logo_fetched (before stale-token check) — guarantees stack balance even under rapid-retype races (Pitfall P-1)"
  - "_DELETE_BTN_QSS uses an f-string with doubled braces ({{ ... }}) so QSS selector braces survive formatting"

patterns-established:
  - "3-arg finished signal with classification string sentinel — extensible to other worker classes that need to distinguish failure modes without adding new signals"
  - "Terminal-status + auto-clear timer pattern for transient UI feedback labels (applicable to other status-feedback widgets across dialogs)"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-04-17
---

# Phase 46 Plan 02: EditStationDialog logo UX — AA classification, auto-clear, cursor override Summary

**Three-arg _LogoFetchWorker signal distinguishes AudioAddict-URL-but-no-key from generic unsupported URLs, a parented 3s auto-clear timer scrubs stale status, and a stack-balanced wait cursor covers the fetch window.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-17T23:44:55Z
- **Completed:** 2026-04-17T23:49:15Z
- **Tasks:** 2 (1 RED test, 1 GREEN implementation)
- **Files modified:** 2

## Accomplishments

- Widened `_LogoFetchWorker.finished` to `Signal(str, int, str)` with a classification third arg; all 7 emit sites updated (6 success/failure/generic emits use `""`, 1 AA-no-key path emits `"aa_no_key"`).
- `_on_logo_fetched` now accepts `classification: str = ""` default, branches on `"aa_no_key"` to show the exact message `"AudioAddict station — use Choose File to supply a logo"` (U+2014 em-dash), and restores the wait cursor BEFORE the stale-token early return (Pitfall P-1 mitigation).
- New parented `_logo_status_clear_timer = QTimer(self)` (3000ms, single-shot, wired to `_logo_status.clear`); armed on every terminal status (`Fetched`, `Fetch failed`, `Fetch not supported`, `AudioAddict station — use Choose File`, `Enter a URL first`); stopped + label cleared immediately by `_on_url_text_changed`.
- `QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))` added at fetch dispatch (`_on_url_timer_timeout`, immediately before `worker.start()`); `QApplication.restoreOverrideCursor()` called exactly once at the top of `_on_logo_fetched` — stack balance is 1:1 per fetch regardless of stale-token outcome.
- `_DELETE_BTN_QSS` migrated from raw `"#c0392b"` hex literal to f-string `f"QPushButton {{ color: {ERROR_COLOR_HEX}; }}"` sourcing from `musicstreamer.ui_qt._theme` (the one hex-migration site relocated from Plan 46-01 to avoid worktree conflict in the import block).
- 4 new behavioral tests added and passing; all 16 pre-existing tests in `test_edit_station_dialog.py` still pass (tests/test_edit_station_dialog.py::test_auto_fetch_completion_copies_via_assets confirms the default-arg signature preservation at P-5).

## Task Commits

1. **Task 1: RED — 4 failing tests for classification, auto-clear, and textChanged cancel** — `7ea3d46` (test)
2. **Task 2: GREEN — AA classification + auto-clear timer + cursor override + _DELETE_BTN_QSS hex migration** — `bc9b95a` (feat)

## Files Created/Modified

- `musicstreamer/ui_qt/edit_station_dialog.py` (modified):
  - L23: `QCursor` added to `PySide6.QtGui` import.
  - L25-43: `QApplication` added to `PySide6.QtWidgets` import block.
  - L48: new `from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX` (depends on Plan 46-01's `_theme.py`).
  - L51-76: `_LogoFetchWorker` — `finished = Signal(str, int, str)`; docstring updated; AA-no-key branch emits before `_fetch_image_map` import.
  - L78-115: `_LogoFetchWorker.run` — all 7 `self.finished.emit(...)` sites updated to 3 args (6 with `""`, 1 with `"aa_no_key"`).
  - L141-143: `_DELETE_BTN_QSS` migrated to f-string using `ERROR_COLOR_HEX`.
  - L217-221: new `_logo_status_clear_timer = QTimer(self)` wired to `_logo_status.clear` with 3000ms single-shot.
  - L445-450: `_on_url_text_changed` augmented — stops clear timer + clears label immediately, then starts debounce as before.
  - L466-471: cursor override added in `_on_url_timer_timeout` immediately before `worker.start()`.
  - L473-481: `_on_fetch_logo_clicked` — "Enter a URL first" path now also arms the auto-clear timer.
  - L529-590: `_on_logo_fetched` rewritten — new `classification: str = ""` param; cursor restore at very top; `aa_no_key` branch emits the AA-distinct message; auto-clear timer started on every terminal setText.
- `tests/test_edit_station_dialog.py` (modified):
  - 4 new tests appended: `test_aa_no_key_message_string`, `test_logo_status_clears_after_3s`, `test_text_changed_cancels_pending_clear`, `test_aa_url_no_key_worker_emits_aa_no_key_classification`.
  - Tests 2 and 3 monkeypatch `_LogoFetchWorker` to a MagicMock to prevent the debounce-triggered real worker from racing the 3s wait / synchronous assertions.

## Decisions Made

- Performed AA classification via `self.finished.emit("", token, "aa_no_key")` BEFORE importing `_fetch_image_map` — the no-key branch now has no dependency on `aa_import` being importable, reducing failure coupling (pairs with Pitfall P-4 mitigation at plan level).
- Used parented `QTimer(self)` for the new clear timer (research G-1), NOT the existing unparented `QTimer()` pattern at line ~209. The existing pattern works because the object is referenced via `self._url_timer`, but the new timer uses the explicit parent form as cheap insurance.
- Extended D-09 slightly: `_on_fetch_logo_clicked`'s "Enter a URL first" path now also arms the 3s auto-clear. The plan marked this optional (§F); the cost is a single line and matches the uniform behavior stated in CONTEXT §D-09.
- Wait cursor restore placed at the TOP of `_on_logo_fetched` (before the stale-token early return) — matches Pitfall P-1: every `setOverrideCursor` must pair with exactly one `restoreOverrideCursor` regardless of token freshness, or rapid URL typing leaks cursor-stack levels.

## Deviations from Plan

**None** — plan executed exactly as written. The only minor extension is §F (arm auto-clear timer in the "Enter a URL first" path), which the plan marked explicitly as optional and recommended; adopted for uniform behavior.

## Verification notes

- Cursor-override grep: `grep -c "QApplication.setOverrideCursor" musicstreamer/ui_qt/edit_station_dialog.py` → 1; `grep -c "QApplication.restoreOverrideCursor" musicstreamer/ui_qt/edit_station_dialog.py` → 1 (single restore per P-1/P-2).
- Signal-arity grep: `grep -c "finished = Signal(str, int, str)" musicstreamer/ui_qt/edit_station_dialog.py` → 1; AA-no-key emit path isolated at exactly 1 site.
- Hex purge: `grep -c "#c0392b" musicstreamer/ui_qt/edit_station_dialog.py` → 0 (migrated to ERROR_COLOR_HEX f-string).
- Clear-timer wiring: `grep -c "self._logo_status_clear_timer.start()" musicstreamer/ui_qt/edit_station_dialog.py` → 3 (AA-no-key branch, unsupported/failed branch, success branch); `grep -c "self._logo_status_clear_timer.stop()" musicstreamer/ui_qt/edit_station_dialog.py` → 1 (inside `_on_url_text_changed`). Additionally, `_on_fetch_logo_clicked`'s "Enter a URL first" path starts the timer — total `.start()` occurrences = 4, but the acceptance criteria required `>= 3`.
- AA message string: exactly one literal `"AudioAddict station \u2014 use Choose File to supply a logo"` in the source.
- Test result in this worktree: `pytest tests/test_edit_station_dialog.py -v` → 20 passed (16 pre-existing + 4 new) when a minimal `_theme.py` stub was present locally. Stub deleted before commit per parallel_note — the real `_theme.py` lands via Plan 46-01 merge.

## Issues Encountered

- Worktree branch base mismatch on startup: `git merge-base` returned commit `e1cd77c` but the expected base per the spawn prompt was `383618e` (ahead of the merge-base). Resolved via the prescribed `git reset --hard 383618eff...` at the top of `<worktree_branch_check>`; HEAD confirmed at the correct commit before any plan work.
- `_theme.py` unavailable in this worktree (scheduled for creation by sibling worktree 46-01). A minimal stub `_theme.py = 'ERROR_COLOR_HEX = "#c0392b"'` was used for local test verification only, then DELETED before committing Task 2 so it does not land in the merge. After deletion, `python -c "from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog"` fails with `ModuleNotFoundError: No module named 'musicstreamer.ui_qt._theme'` — this is expected and will resolve after 46-01 merges. The orchestrator's post-merge test gate validates the combined state.

## Cursor-override lifecycle (verification of P-1/P-2/G-7)

| Event                                                        | Cursor stack depth |
| ------------------------------------------------------------ | ------------------ |
| Dialog open (no fetch)                                       | 0                  |
| User types URL → debounce fires → `_on_url_timer_timeout`    | 1 (one override)   |
| Worker.finished → `_on_logo_fetched` top: `restoreOverrideCursor` | 0 (balanced)       |
| Rapid URL retype → second dispatch happens BEFORE first finished | 2                  |
| First worker's stale finished → restore at top → early return | 1 (one override still active) |
| Second worker's finished → restore at top → success path     | 0 (fully balanced) |

Every `setOverrideCursor` in this codepath has exactly one matching `restoreOverrideCursor`, regardless of stale-token outcome.

## User Setup Required

None — no external service configuration required.

## Known Gaps (Deferred)

- **`closeEvent` / `reject` 2s hang during in-flight fetch** — documented in CONTEXT §Deferred Ideas. D-10 covers only the fetch-in-flight cursor/feedback, not the discard-while-fetching path. Not addressed in this phase.
- **Stale-token race where a late finished overwrites a textChanged-cleared label** — noted in RESEARCH G-3 as pre-existing; D-09 timer-cancellation semantics do not fully fix the write-after-textChanged race for a fetch that completes AFTER the user types. Deferred to a future phase if it surfaces in UAT.

## Self-Check: PASSED

- [x] `tests/test_edit_station_dialog.py` exists and contains the 4 new tests: grep confirms.
- [x] `musicstreamer/ui_qt/edit_station_dialog.py` contains all expected patterns: grep confirms (see Verification notes).
- [x] Task 1 commit `7ea3d46` present in git log.
- [x] Task 2 commit `bc9b95a` present in git log.
- [x] Temporary `_theme.py` stub deleted (verified via `ls: no such file or directory`).
- [x] Pre-existing `test_auto_fetch_completion_copies_via_assets` still passes (P-5 preservation).

## Next Phase Readiness

- Plan 46-02 half of the edit_station_dialog hex migration complete. After Plan 46-01 merges (creating `_theme.py` with `ERROR_COLOR_HEX`, `ERROR_COLOR_QCOLOR`, `STATION_ICON_SIZE`), `edit_station_dialog.py` is expected to import cleanly; post-merge `pytest -x` should be green.
- No Phase 47/48 dependencies on the behaviors added here; future phases can consume the classification-string pattern if other workers need multi-branch failure distinctions.

---

*Phase: 46-ui-polish-theme-tokens-logo-status-cleanup, Plan 02*
*Completed: 2026-04-17*
