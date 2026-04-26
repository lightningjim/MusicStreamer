---
phase: 42-settings-export-import
plan: 03
subsystem: ui
tags: [pyside6, qthread, signals, pytest-qt, sqlite, settings-import, regression]

# Dependency graph
requires:
  - phase: 42-settings-export-import
    provides: SettingsImportDialog + _ImportCommitWorker (plan 42-02)
provides:
  - "_ImportCommitWorker custom signals renamed to commit_done / commit_error to avoid shadowing QThread.finished"
  - "Real-filesystem integration regression test (chmod 0o444) guarding against future QThread signal-shadowing bugs"
  - "Anti-pattern comment block documenting why monkeypatch-based tests missed the original bug"
affects: [42-settings-export-import, future-phases-using-qthread-signals]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Custom Signal names on QThread subclasses must not collide with QThread built-ins (finished, started)"
    - "Qt worker integration tests should exercise real OS-level failure paths when the failure mode is OS-level (permissions, disk, etc.) — monkeypatching the inner function can mask signal-routing bugs"

key-files:
  created:
    - ".planning/phases/42-settings-export-import/42-03-SUMMARY.md"
    - ".planning/phases/42-settings-export-import/deferred-items.md"
  modified:
    - "musicstreamer/ui_qt/settings_import_dialog.py"
    - "tests/test_settings_import_dialog.py"

key-decisions:
  - "Rename the custom success signal commit_done rather than keep `finished` and reroute via a different attribute — Qt's C++ QThread::finished is always emitted on thread exit; only a distinct name (not shadowing) prevents the wrong slot from firing."
  - "Added a real-chmod integration test alongside the existing monkeypatch test rather than replacing it — the monkeypatch test still covers the synchronous error-emit code path in a fast unit form; the chmod test is the regression guard for the signal-shadowing class of bugs."
  - "Initialize schema via db_init() in the test (not Repo.__init__) because Repo does not run schema init. This ensures commit_import's failure is the OS read-only chmod, not a missing-table error masquerading as the same code path."

patterns-established:
  - "QThread subclass signals: NEVER name a Signal `finished` or `started` — they shadow C++ built-ins."
  - "Import-failure UAT tests: use tmp_path + os.chmod(..., 0o444) + db_init() to trigger the real SQLite read-only failure; restore 0o644 in the finally block so pytest can clean the tmp dir."

requirements-completed: [SYNC-04]

# Metrics
duration: ~20min
completed: 2026-04-17
---

# Phase 42 Plan 03: Gap Closure — QThread Signal Shadowing Fix Summary

**Renamed `_ImportCommitWorker.finished` → `commit_done` (and `error` → `commit_error`) so PySide6's C++ `QThread::finished` stops misrouting error-path thread exits through the success slot; added a real-filesystem chmod 0o444 regression test the previous monkeypatch test was blind to.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-17T14:48:00Z
- **Completed:** 2026-04-17T14:52:00Z
- **Tasks:** 3 (2 code tasks + 1 verification gate)
- **Files modified:** 2

## Accomplishments

- `_ImportCommitWorker.finished` / `error` attributes removed; renamed to `commit_done` / `commit_error` with docstring explaining the shadowing pitfall.
- All three call sites updated (two `emit()` in `run()`, two `connect()` in `SettingsImportDialog._on_import`).
- New integration regression test `test_commit_error_on_readonly_db_real_filesystem` exercises the actual UAT test 8 failure mode (chmod 0o444 on a real SQLite file) and asserts: `commit_error` fires, `commit_done` does NOT fire, dialog stays visible, toast starts with "Import failed", Import button re-enabled.
- Anti-pattern comment block + updated docstring on the existing monkeypatch test documents why it missed the bug and where the real-FS test lives.
- TDD RED proof verified: the new test fails with `AttributeError: '_ImportCommitWorker' object has no attribute 'commit_done'` when run against the pre-fix code (confirmed via a temporary `git revert 8c72bc4` on a scratch basis, then aborted).
- Phase-42 test suite: 28/28 passing (was 27/27 pre-fix, +1 regression test).

## Task Commits

Each task was committed atomically (worktree branch, `--no-verify` per parallel-executor protocol):

1. **Task 1: Rename `_ImportCommitWorker` signals + update all call sites** — `8c72bc4` (fix)
2. **Task 2: Update existing test docstring + add real-FS regression test** — `c1be3e8` (test)
3. **Task 3: Full phase-42 test suite verification gate** — no code changes (pure verification; results documented here and in `deferred-items.md`)

**Plan metadata:** will be committed by worktree agent on exit (SUMMARY.md + deferred-items.md).

## Files Created/Modified

- `musicstreamer/ui_qt/settings_import_dialog.py` — `_ImportCommitWorker` signal rename (shadowing fix), docstring, call-site updates.
- `tests/test_settings_import_dialog.py` — docstring update on `test_commit_error_shows_toast_and_reenables_button` + new `test_commit_error_on_readonly_db_real_filesystem` regression test (+ anti-pattern comment block).
- `.planning/phases/42-settings-export-import/42-03-SUMMARY.md` — this file.
- `.planning/phases/42-settings-export-import/deferred-items.md` — logs pre-existing environment-level test failures that are scope-out per SCOPE BOUNDARY.

## Decisions Made

- **Rename over re-route:** The fix is a pure rename, not a complex re-routing of the existing `finished` name. PySide6 emits the C++ `QThread::finished` regardless of any Python attribute shadowing it; only a fresh name cleanly separates success-path emit from thread-exit emit.
- **Integration test uses `db_init(schema_con)` not `Repo(con)`:** `Repo.__init__` does not run schema init in this codebase. Calling `db_init()` on a writable connection first guarantees the SQLite file has a real schema before `chmod 0o444`, so the commit_import failure is specifically the OS write-block and not a "no such table" confusion.
- **Both tests retained:** The monkeypatch test (`test_commit_error_shows_toast_and_reenables_button`) still covers the fast unit path (toast + button state after synchronous exception). The new real-FS test is the defense-in-depth layer for the signal-shadowing class of bugs. Deleting the monkeypatch test would lose coverage of the ~20 ms fast-unit path and reduce test suite speed signal.

## Deviations from Plan

None — plan executed exactly as written.

The plan called out one executor-side adaptation in the `Notes for the executor` block: *"If `Repo(con)` does not run schema init in this codebase, fall back to opening `sqlite3.connect` against a writable path and committing a trivial no-op..."*. I applied the better fallback — `db_init(schema_con)` — since it is both the documented canonical schema initializer in `musicstreamer/repo.py` AND it produces a schema commit_import can actually write against. This is a planned-for adaptation, not a deviation.

## Issues Encountered

### Pre-existing cross-phase test failures (scope-out)

`python -m pytest tests/` does not exit 0 in this worktree environment because several test modules require optional dependencies not installed here: `yt_dlp`, `streamlink`, and the pytest-qt `QtTest` binding. These failures reproduce on the base commit `81bf97a` (verified via a temporary checkout), so they are pre-existing and unrelated to the 42-03 changes. Details in `.planning/phases/42-settings-export-import/deferred-items.md`.

The 42-03 plan's phase-42-scoped test gate (`tests/test_settings_export.py` + `tests/test_settings_import_dialog.py`) IS 100% green (28/28 passing), which closes the UAT test 8 gap at the automated-test layer as specified in the `<success_criteria>`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- UAT test 8 gap closed at the automated-test layer. Manual UAT re-run remains the user's responsibility (not in scope for this plan).
- Phase-42 settings export/import is ready for the v2.0 Linux↔Windows round-trip UAT validation inherited by Phase 44.
- The established "QThread Signal shadowing" anti-pattern is now documented in-code (worker docstring) and in-tests (anti-pattern comment block) so future phases adding QThread-based workers will inherit the defensive pattern.

## Self-Check: PASSED

- FOUND: `musicstreamer/ui_qt/settings_import_dialog.py`
- FOUND: `tests/test_settings_import_dialog.py`
- FOUND: `.planning/phases/42-settings-export-import/42-03-SUMMARY.md`
- FOUND: `.planning/phases/42-settings-export-import/deferred-items.md`
- FOUND commit: `8c72bc4` (Task 1 — signal rename)
- FOUND commit: `c1be3e8` (Task 2 — real-FS regression test)

---
*Phase: 42-settings-export-import*
*Completed: 2026-04-17*
