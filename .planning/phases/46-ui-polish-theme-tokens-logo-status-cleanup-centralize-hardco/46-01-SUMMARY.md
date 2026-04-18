---
phase: 46-ui-polish-theme-tokens-logo-status-cleanup
plan: 01
subsystem: ui
tags: [pyside6, qt, theme-tokens, design-system, refactor]

# Dependency graph
requires:
  - phase: 45-unify-station-icon-loader
    provides: _art_paths.py module (naming/layout template for _theme.py; load_station_icon default-arg site)
  - phase: 42-settings-export-import
    provides: _ERROR_COLOR local QColor token in settings_import_dialog.py (folded into shared module)
provides:
  - musicstreamer/ui_qt/_theme.py module with ERROR_COLOR_HEX, ERROR_COLOR_QCOLOR, STATION_ICON_SIZE
  - tests/test_theme.py unit + grep-regression test file
  - 9 of 10 hex-literal call sites migrated (10th in edit_station_dialog.py deferred to Plan 46-02 Task 2)
  - all 3 QSize(32, 32) station-icon call sites migrated
  - load_station_icon default arg now sourced from STATION_ICON_SIZE
affects: [46-02, future dark-mode phase, future QSS-migration phase]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Design-token module pattern: underscore-prefixed _theme.py co-located with ui_qt/, module-level constants, two-constant form (hex string + QColor) for widgets consuming both APIs"
    - "Grep-regression test pattern: pathlib walk + re.search over source tree to enforce no-raw-literal invariants at test time"

key-files:
  created:
    - musicstreamer/ui_qt/_theme.py
    - tests/test_theme.py
    - .planning/phases/46-ui-polish-theme-tokens-logo-status-cleanup-centralize-hardco/deferred-items.md
  modified:
    - musicstreamer/ui_qt/_art_paths.py
    - musicstreamer/ui_qt/settings_import_dialog.py
    - musicstreamer/ui_qt/import_dialog.py
    - musicstreamer/ui_qt/cookie_import_dialog.py
    - musicstreamer/ui_qt/accent_color_dialog.py
    - musicstreamer/ui_qt/station_list_panel.py
    - musicstreamer/ui_qt/favorites_view.py

key-decisions:
  - "Two-constant form (ERROR_COLOR_HEX + ERROR_COLOR_QCOLOR) exported because QSS strings need a hex str and QTreeWidgetItem.setForeground needs a QColor; a single constant would force repeat QColor(...) construction at every call site (D-02)"
  - "_theme.py owns STATION_ICON_SIZE (not _art_paths.py) — icon size is a visual token, not a path-resolution concern (D-06)"
  - "QColor import removed entirely from settings_import_dialog.py — the local _ERROR_COLOR was the only use; no other QColor references in the file"
  - "edit_station_dialog.py:131 left untouched; Plan 46-02 Task 2 owns that single-site migration to keep Wave 1 files_modified disjoint between parallel plans"

patterns-established:
  - "Design-token module convention: `from musicstreamer.ui_qt._theme import TOKEN_NAME` at file-import site; tokens consumed via f-string interpolation for QSS (f\"color: {ERROR_COLOR_HEX};\") or direct pass-through for QColor/int APIs"
  - "Phase 46 dark-mode unblocker: every future palette-switch feature has exactly one module to retarget"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-04-17
---

# Phase 46 Plan 01: UI theme tokens (ERROR_COLOR + STATION_ICON_SIZE) Summary

**New `_theme.py` design-token module with ERROR_COLOR_HEX/QCOLOR + STATION_ICON_SIZE; 9 hex sites and all 3 icon-size sites migrated; `edit_station_dialog.py:131` deliberately deferred to Plan 46-02 Task 2 for Wave 1 parallel-execution disjointness**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-17T23:44:37Z
- **Completed:** 2026-04-17T23:49:40Z
- **Tasks:** 2/2
- **Files created:** 3 (incl. deferred-items.md)
- **Files modified:** 7

## Accomplishments

- `_theme.py` exports the three tokens exactly as specified: `ERROR_COLOR_HEX: str = "#c0392b"`, `ERROR_COLOR_QCOLOR: QColor` (named `#c0392b`), `STATION_ICON_SIZE: int = 32`.
- `tests/test_theme.py` contains 5 tests: 3 unit tests + 2 grep-regression guards. 4 pass; `test_no_raw_error_hex_outside_theme` intentionally fails until Plan 46-02 Task 2 lands.
- 9 of 10 raw `#c0392b` hex literals folded into imports from `_theme`. The 10th (`edit_station_dialog.py:131`) remains — Plan 46-02 Task 2 owns it.
- 3 of 3 `QSize(32, 32)` station-icon sites migrated to `QSize(STATION_ICON_SIZE, STATION_ICON_SIZE)`.
- `load_station_icon(station, size: int = STATION_ICON_SIZE)` — default arg wired.
- `settings_import_dialog.py` lost its local `_ERROR_COLOR` QColor token AND its `QColor` import (no other uses in the file).

## Task Commits

1. **Task 1: Create _theme.py module + tests/test_theme.py (RED→GREEN)** — `f5b834b` (feat)
2. **Task 2: Migrate 12 of 13 call sites to consume _theme constants** — `7cde58c` (refactor)

## Files Created/Modified

### Created

- `musicstreamer/ui_qt/_theme.py` — new design-token module with 3 constants.
- `tests/test_theme.py` — 5 tests (3 unit + 2 grep-regression).
- `.planning/phases/46-ui-polish-theme-tokens-logo-status-cleanup-centralize-hardco/deferred-items.md` — logs the pre-existing `test_filter_strip_hidden_in_favorites_mode` failure encountered during the regression sweep.

### Modified — site-by-site before/after

| File | Line (pre-migration) | Before | After |
|---|---|---|---|
| `_art_paths.py` | 26-28 (imports) | `from musicstreamer import paths` | +`from musicstreamer.ui_qt._theme import STATION_ICON_SIZE` |
| `_art_paths.py` | 47 | `def load_station_icon(station, size: int = 32) -> QIcon:` | `def load_station_icon(station, size: int = STATION_ICON_SIZE) -> QIcon:` |
| `settings_import_dialog.py` | 25 | `from PySide6.QtGui import QColor, QFont` | `from PySide6.QtGui import QFont` (QColor import removed — no other uses) |
| `settings_import_dialog.py` | 40-46 | `_ERROR_COLOR = QColor("#c0392b")` + comment block | Deleted; replaced with `from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX, ERROR_COLOR_QCOLOR` |
| `settings_import_dialog.py` | 139-141 | `"color: #c0392b; font-size: 9pt;"` | `f"color: {ERROR_COLOR_HEX}; font-size: 9pt;"` |
| `settings_import_dialog.py` | 179-180 | `item.setForeground(..., _ERROR_COLOR)` × 2 | `item.setForeground(..., ERROR_COLOR_QCOLOR)` × 2 |
| `import_dialog.py` | 45 (import block) | — | +`from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX` |
| `import_dialog.py` | 264, 292, 339, 433, 466 | `.setStyleSheet("color: #c0392b;")` × 5 | `.setStyleSheet(f"color: {ERROR_COLOR_HEX};")` × 5 |
| `cookie_import_dialog.py` | 42 (import block) | — | +`from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX` |
| `cookie_import_dialog.py` | 106 | `.setStyleSheet("color: #c0392b;")` | `.setStyleSheet(f"color: {ERROR_COLOR_HEX};")` |
| `accent_color_dialog.py` | 34 (import block) | — | +`from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX` |
| `accent_color_dialog.py` | 166 | `.setStyleSheet("border: 1px solid #c0392b;")` | `.setStyleSheet(f"border: 1px solid {ERROR_COLOR_HEX};")` |
| `station_list_panel.py` | 40 (import block) | — | +`from musicstreamer.ui_qt._theme import STATION_ICON_SIZE` |
| `station_list_panel.py` | 151 | `self.recent_view.setIconSize(QSize(32, 32))` | `self.recent_view.setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))` |
| `station_list_panel.py` | 257 | `self.tree.setIconSize(QSize(32, 32))` | `self.tree.setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))` |
| `favorites_view.py` | 36 (import block) | — | +`from musicstreamer.ui_qt._theme import STATION_ICON_SIZE` |
| `favorites_view.py` | 97 | `self._stations_list.setIconSize(QSize(32, 32))` | `self._stations_list.setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))` |

### Not modified (intentional)

- `musicstreamer/ui_qt/edit_station_dialog.py` — out of scope per `<parallel_note>`. `edit_station_dialog.py:131` (`_DELETE_BTN_QSS = "QPushButton { color: #c0392b; }"`) is migrated by Plan 46-02 Task 2 instead, so Plan 46-01 and Plan 46-02 can run in parallel in Wave 1 without worktree import-block conflicts.

### QColor import disposition in settings_import_dialog.py

Removed. Prior to this plan the file had `from PySide6.QtGui import QColor, QFont` on line 25 and `_ERROR_COLOR = QColor("#c0392b")` on line 46; a `grep` for `QColor` across the file showed no other uses. Both were dropped.

### test_station_list_panel.py iconSize assertions

Confirmed still passing. `tests/test_station_list_panel.py::test_recent_view_max_height_and_icon_size` and the two `iconSize() == QSize(32, 32)` asserts read the widget's actual iconSize property, not the source text. Because `STATION_ICON_SIZE == 32`, the widget property is unchanged by the migration and the assertions remain green.

## Decisions Made

- **QColor import dropped** from `settings_import_dialog.py` (was only used for the now-deleted `_ERROR_COLOR`). Keeping it would have been a dead import.
- **No backwards-compat alias** for `_ERROR_COLOR` in `settings_import_dialog.py` — per D-03 preference. All usages migrated in the same commit.
- **Deferred-items file created** for the unrelated pre-existing `test_filter_strip_hidden_in_favorites_mode` failure encountered in the regression sweep. Verified pre-existing by stashing plan changes and re-running on the clean Phase 46 base — same failure reproduced.

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria and phase-wide verification checks met:

- Zero raw `#c0392b` in `musicstreamer/ui_qt/*.py` except `_theme.py` (3 occurrences: docstring x2 + declaration) and `edit_station_dialog.py:131` (awaiting Plan 46-02 Task 2).
- Zero raw `QSize(32, 32)` in `musicstreamer/ui_qt/`.
- 7 migrated files each have exactly one `from musicstreamer.ui_qt._theme import …` line.
- Plan-specific verify command: `pytest tests/test_theme.py::test_no_raw_icon_size_in_migrated_sites tests/test_art_paths.py tests/test_station_list_panel.py tests/test_settings_import_dialog.py tests/test_import_dialog.py -v` → 25 passed, 1 deselected (the pre-existing failure — unrelated).
- 4 phase-wide plan tests pass; `test_no_raw_error_hex_outside_theme` intentionally fails until Plan 46-02 Task 2 lands.

## Issues Encountered

- **Worktree branch base drift** — the worktree branch HEAD started on commit `e1cd77c` (Phase 47 doc update) rather than the Phase 46 base `383618e`. Resolved by the `<worktree_branch_check>` hard-reset.
- **Pre-existing unrelated test failure** — `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode` fails with `_search_box.isVisibleTo(panel) == False`. Verified pre-existing by stashing plan changes and re-running. Logged to `deferred-items.md`. Out of scope for Plan 46-01 (not touched by any migration, not part of the plan's verify command).

## User Setup Required

None.

## Next Phase Readiness

- **Plan 46-02** (parallel sibling in Wave 1) must complete its Task 2 (`edit_station_dialog.py:131` migration) for the last of the 5 theme tests (`test_no_raw_error_hex_outside_theme`) to turn green. The module exports required by Plan 46-02 are already provided by this plan.
- **Plan 46-03** (Wave 2 — `EditStationDialog` behavioral changes per D-07/D-09/D-10) will consume `ERROR_COLOR_HEX` from `_theme.py` directly when it refactors the logo-status label path.
- **Future dark-mode phase** is now unblocked — all error-color and station-icon size literals route through `_theme.py`.

## Self-Check: PASSED

- FOUND: `musicstreamer/ui_qt/_theme.py`
- FOUND: `tests/test_theme.py`
- FOUND: commit `f5b834b`
- FOUND: commit `7cde58c`
- FOUND: 7 modified files (per `git show --stat 7cde58c`)
- FOUND: `.planning/phases/46-ui-polish-theme-tokens-logo-status-cleanup-centralize-hardco/deferred-items.md`

---

*Phase: 46-ui-polish-theme-tokens-logo-status-cleanup*
*Plan: 01 (centralize hardcoded UI constants into _theme.py)*
*Completed: 2026-04-17*
