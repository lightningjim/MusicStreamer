---
phase: 65-show-current-version-in-app
plan: 01
subsystem: ui
tags: [versioning, qt, hamburger-menu, importlib-metadata, ver-02]

requires:
  - phase: 63
    provides: pyproject.toml [project].version single-write site (auto-bump hook)
provides:
  - Runtime read site for the running app's version, sourced via importlib.metadata
  - Disabled v{version} footer at the bottom of the hamburger menu (D-01..D-03, D-12)
  - app.setApplicationVersion(...) wired in _run_gui (D-07) so Qt internals see the value
  - Locking tests for the version-read mechanism (VER-02-A, VER-02-B)
  - Locking tests for menu surface (VER-02-C, VER-02-D, VER-02-E)
  - Locking test for source-text setter ordering (VER-02-F)
  - Backfilled VER-02 row in REQUIREMENTS.md ledger + traceability
  - Backfilled Phase 65 entry in ROADMAP.md (Goal/Requirements/Success Criteria/Plans)
affects: [phase-65-02 (PyInstaller spec edit consumes the same import path), phase-65-03 (deletes __version__.py — D-06a grep gate confirmed clean here)]

tech-stack:
  added: [importlib.metadata (stdlib — no third-party dep)]
  patterns:
    - "_pkg_version = importlib.metadata.version helper alias at top-of-file imports"
    - "Read version directly at the menu construction site (not via QCoreApplication.applicationVersion) to sidestep Landmine 1: pytest-qt fixtures don't run _run_gui"
    - "No try/except PackageNotFoundError fallback — hard-fail is more informative than v(unknown) (CONTEXT D-08 / RESEARCH §defensive-fallback)"

key-files:
  created:
    - tests/test_version.py
    - .planning/phases/65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb/deferred-items.md
  modified:
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - musicstreamer/__main__.py
    - musicstreamer/ui_qt/main_window.py
    - tests/test_main_window_integration.py
    - tests/test_main_run_gui_ordering.py

key-decisions:
  - "Read importlib.metadata directly at the menu construction site, not via QCoreApplication.applicationVersion (D-11 deviation per RESEARCH Landmine 1)"
  - "No try/except PackageNotFoundError fallback (CONTEXT D-08 / RESEARCH §v(unknown))"
  - "Place setApplicationVersion between setApplicationDisplayName and setDesktopFileName (CONTEXT D-07 placement)"
  - "Place version footer AFTER the conditional Phase 44 Node-missing block so it is the literal last entry in either branch"

patterns-established:
  - "Phase 65 version footer pattern: addSeparator() + addAction(f\"v{_pkg_version('musicstreamer')}\") + setEnabled(False) — reusable for any future disabled informational footer"

requirements-completed: [VER-02]

duration: 11min
completed: 2026-05-08
---

# Phase 65 Plan 01: Runtime Version Read Site Summary

**Runtime version-read path wired: `app.setApplicationVersion(_pkg_version('musicstreamer'))` in `_run_gui` plus disabled `v{version}` footer at the bottom of the hamburger menu, both sourced from `importlib.metadata` against `pyproject.toml [project].version`.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-05-08T19:38:34Z
- **Completed:** 2026-05-08T19:49:39Z
- **Tasks:** 3 (1 docs + 2 TDD pairs)
- **Files modified:** 6 (+1 created: tests/test_version.py)

## Accomplishments

- VER-02 traceability landed in `.planning/REQUIREMENTS.md` ledger; Phase 65 entry backfilled in `.planning/ROADMAP.md` from `[To be planned]` placeholder to a real Goal / Requirements / Success Criteria / 3-plan listing.
- D-06a pre-flight grep gate ran with zero hits, recorded for Plan 65-03 reuse.
- `_pkg_version("musicstreamer")` now drives both the Qt-internal slot (D-07) and the user-visible menu footer (D-01..D-03, D-12), reading from `pyproject.toml [project].version` via `importlib.metadata` — Phase 63 auto-bump's downstream consumer is live.
- 6 new tests cover VER-02-A/B/C/D/E/F; existing `test_hamburger_menu_actions` and `test_hamburger_menu_separators` extended in place (slice + regex + separator count 3→4) without disturbing the EXPECTED_ACTION_TEXTS literal list.

## Task Commits

Each task was committed atomically. TDD-flagged tasks have separate RED-test and GREEN-feat commits.

1. **Task 1: Pre-flight grep gate + REQUIREMENTS/ROADMAP backfill** — `0d30213` (docs)
2. **Task 2 RED: setApplicationVersion + version-read tests** — `364974a` (test)
3. **Task 2 GREEN: setApplicationVersion in _run_gui** — `4202782` (feat)
4. **Task 3 RED: hamburger menu version footer tests** — `9745685` (test)
5. **Task 3 GREEN: disabled v{version} footer in hamburger menu** — `b52b9f5` (feat)

_Note: Task 1 had no separate RED phase — the production "tests" for it are grep assertions on the planning files, which are atomically tied to the same edits._

## Files Created/Modified

- `.planning/REQUIREMENTS.md` — Added VER-02 bullet under Versioning Convention (VER), VER-02 row in Traceability table; bumped v2.1 totals 17→18 / Pending 15→16.
- `.planning/ROADMAP.md` — Replaced Phase 65 placeholder with full entry (Goal, Depends on, Requirements: VER-02, 6-item Success Criteria, 3-plan listing); added Progress Table row `| 65. Show current version in app | 0/3 | In progress | — |`.
- `musicstreamer/__main__.py` — Added top-of-file `from importlib.metadata import version as _pkg_version`; inserted `app.setApplicationVersion(_pkg_version("musicstreamer"))` between `setApplicationDisplayName` and `setDesktopFileName` in `_run_gui`.
- `musicstreamer/ui_qt/main_window.py` — Added top-of-file `from importlib.metadata import version as _pkg_version`; appended unconditional `addSeparator()` + `self._act_version = self._menu.addAction(f"v{_pkg_version('musicstreamer')}")` + `setEnabled(False)` AFTER the conditional Phase 44 Node-missing block (so the footer is the literal last entry in either branch).
- `tests/test_version.py` (NEW, 35 lines) — VER-02-A `test_metadata_version_matches_pyproject` + VER-02-B `test_metadata_version_is_semver_triple`. Imports `tomllib` + uses the `Path(__file__).resolve().parent.parent` anchor pattern from `tests/test_media_keys_smtc.py`.
- `tests/test_main_window_integration.py` — `test_hamburger_menu_actions` rewritten for slice + regex (12 actions, last `^v\d+\.\d+\.\d+$`); `test_hamburger_menu_separators` flipped 3→4; new `test_version_action_is_disabled_and_last`. EXPECTED_ACTION_TEXTS unchanged at 11 entries.
- `tests/test_main_run_gui_ordering.py` — Appended `test_set_application_version_in_run_gui` (VER-02-F) using existing `main_source` fixture + `_index` helper.

## Decisions Made

- **D-11 deviation (read site mechanism)** — Followed RESEARCH Landmine 1: read `importlib.metadata.version("musicstreamer")` directly at the menu construction site rather than via `QCoreApplication.applicationVersion()`. Rationale: pytest-qt `qtbot` fixture provides a bare QApplication and never runs `_run_gui`, so `QCoreApplication.applicationVersion()` returns "" in tests on Linux. The Qt slot is still set in `__main__.py` (D-07) for Qt-internal reasons (QSettings, crash handlers).
- **No defensive `v(unknown)` fallback** — Per CONTEXT D-08 + RESEARCH §"On the v(unknown) defensive fallback": `PackageNotFoundError` propagating is more informative than a silent placeholder. VER-02-A is the CI guard.
- **Placement of new menu code AFTER the Phase 44 Node-missing block** — Ensures the version footer is the literal last entry whether or not Node-missing is conditionally present (covered by VER-02-C `actions[-1] is window._act_version` assertion).

## Deviations from Plan

None - plan executed exactly as written. All decisions above are CONTEXT/RESEARCH-locked and pre-documented in the plan's `<interfaces>` and `<decision_coverage>` blocks.

## Issues Encountered

### Pre-existing test failures (out of scope per SCOPE BOUNDARY rule)

Confirmed pre-existing on commit `f033cca` (the parent of all Plan 65-01 work):

1. **`tests/test_import_dialog_qt.py::test_yt_scan_passes_through`** — Qt fatal abort during `_YtScanWorker` thread cleanup when run as part of the full suite (passes 25/25 in isolation). Pre-existing flake unrelated to Phase 65.
2. **`_FakePlayer` missing `underrun_recovery_started` signal** — 18 errors + 16 failures across `tests/test_main_window_media_keys.py`, `tests/test_main_window_gbs.py`, `tests/test_media_keys_mpris2.py`, `tests/test_station_list_panel.py`, `tests/test_twitch_auth.py`, `tests/test_ui_qt_scaffold.py`, `tests/ui_qt/test_main_window_node_indicator.py`. Phase 62 added `Player.underrun_recovery_started` and connected it in `MainWindow.__init__:304`, but local `_FakePlayer` stubs in these test files were not updated. Reproduced at `f033cca` baseline — **not caused by Phase 65-01**.

Both logged in `deferred-items.md`. With these pre-existing failures deselected, the full suite runs **1145 passed / 0 failed**.

### Recovery from inadvertent stash conflict

During diagnostic work on the test_import_dialog_qt flake, an inadvertent `git stash pop` auto-applied a stash from a different branch (`stash@{0}: On main: phase56-state-2`) creating merge conflicts in `.planning/ROADMAP.md`, `.planning/STATE.md`, `uv.lock`. Resolved by `git checkout HEAD -- <conflicted-files>` to restore Task 1's committed state. All commits stayed intact. Working tree returned to a clean state matching HEAD before SUMMARY.md was written. Stash list left untouched (the popped stash is from another agent's work and does not belong to this worktree).

## Verification

**Plan-level quick suite (per plan `<verification>`):**

```
$ uv run pytest tests/test_version.py tests/test_main_window_integration.py tests/test_main_run_gui_ordering.py -x
====== 52 passed, 1 warning in 1.11s ======
```

All 5 new/extended tests GREEN: VER-02-A, VER-02-B (test_version.py); VER-02-C, VER-02-D, VER-02-E (test_main_window_integration.py); VER-02-F (test_main_run_gui_ordering.py). Pre-existing tests in those files unchanged.

**Full suite (excluding pre-existing failures documented above):**

```
$ uv run pytest --deselect <pre-existing failures>
====== 1145 passed, 42 deselected, 13 warnings in 12.08s ======
```

**D-06a grep gate** ran clean before any code edit AND after all edits — zero importers of `__version__.py` remain, so Plan 65-03's deletion is provably safe.

## Cross-references for downstream plans

- **VER-02-G** (the deleted-`__version__.py` post-condition) — stays unverified until **Plan 65-03**.
- **VER-02-H** (PyInstaller spec `copy_metadata("musicstreamer")`) — stays unverified until **Plan 65-02**.
- **VER-02-I, VER-02-J** — manual UAT items for `/gsd-verify-work` after the bundle ships.
- **D-06a grep gate** — confirmed clean here; Plan 65-03 should re-run the same `git grep` invocation immediately before deleting `musicstreamer/__version__.py`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 65-02 unblocked: PyInstaller spec edit can land any time; this plan's import path (`importlib.metadata.version("musicstreamer")`) is what `copy_metadata("musicstreamer")` needs to feed in the bundled exe.
- Plan 65-03 unblocked: D-06a grep gate is clean; `musicstreamer/__version__.py` is safe to delete with zero remaining importers.
- The pre-existing `_FakePlayer` test stubs missing `underrun_recovery_started` should be filed as a Phase 62 follow-up (not blocking Phase 65 closeout).

---
*Phase: 65-show-current-version-in-app*
*Completed: 2026-05-08*
