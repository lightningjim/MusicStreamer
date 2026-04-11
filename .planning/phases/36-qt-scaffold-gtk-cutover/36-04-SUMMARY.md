---
phase: 36
plan: 04
subsystem: tests / Qt harness verification
tags: [qt, pyside6, pytest-qt, PORT-07, PORT-08, QA-01]
requires:
  - phase-36-plan-01 MainWindow scaffold + _apply_windows_palette helper
  - phase-36-plan-03 GTK cutover (258-test baseline)
  - pytest-qt offscreen harness from Phase 35
provides:
  - QA-01 pytest-qt evidence that MainWindow actually renders under offscreen Qt
  - PORT-08 QIcon.fromTheme bundled-SVG fallback verification
  - PORT-07 Windows Fusion dark-palette code-path coverage without a Windows VM
affects:
  - tests/test_ui_qt_scaffold.py (created)
  - tests/test_windows_palette.py (created)
tech-stack:
  added: [pytest-qt qtbot/qapp fixtures, unittest.mock.patch on PySide6.QtGui.QGuiApplication.styleHints]
  patterns: [qtbot.waitExposed scaffold smoke, module-attribute patching for function-scope imports, palette snapshot/restore fixture]
key-files:
  created:
    - tests/test_ui_qt_scaffold.py
    - tests/test_windows_palette.py
  modified: []
decisions:
  - Patch PySide6.QtGui.QGuiApplication.styleHints directly (not musicstreamer.__main__.QGuiApplication) because _apply_windows_palette imports QGuiApplication at function scope, not module scope. Plan 36-04 explicitly allowed this fallback; no Phase 36-01 rework needed.
  - Added a restore_palette fixture that snapshots/restores the qapp palette around each test so the dark-palette mutation in test_apply_windows_palette_dark doesn't leak into sibling tests (test isolation — the qapp is session-scoped under pytest-qt).
  - Used a synthetic non-existent theme name ("musicstreamer-nonexistent-theme-name-xyz") for the fromTheme fallback assertion to avoid false positives on Linux boxes that happen to have the GNOME Adwaita theme installed.
metrics:
  duration: ~2 minutes
  completed: 2026-04-11T23:43:00Z
  tasks: 2/2
  files-created: 2
  files-modified: 0
  tests-added: 8 (5 scaffold + 3 palette)
  tests: 266 passed (258 baseline + 8 new)
requirements: [QA-01, PORT-08, PORT-07]
---

# Phase 36 Plan 04: Qt Scaffold Smoke Tests Summary

pytest-qt smoke tests prove the Qt harness actually renders `MainWindow` under `QT_QPA_PLATFORM=offscreen` (QA-01), the bundled `:/icons/` SVG resources load and `QIcon.fromTheme` fallback returns non-null (PORT-08), and the Windows Fusion dark-palette code path in `_apply_windows_palette` is correct when `QGuiApplication.styleHints().colorScheme()` is mocked to `Qt.ColorScheme.Dark` (PORT-07). Full test suite lands at 266 passed — up from the 258 post-cutover baseline.

## What Was Built

### Task 1 — `tests/test_ui_qt_scaffold.py` (commit `73589e6`)

5 tests covering MainWindow rendering + bundled icon resources:

- **`test_main_window_constructs_and_renders`** — instantiates `MainWindow()`, adds via `qtbot.addWidget`, calls `show()`, waits via `qtbot.waitExposed(window)`. Asserts `windowTitle() == "MusicStreamer"`, the instance is `QMainWindow`, and `menuBar()` / `centralWidget()` / `statusBar()` are all present and are `QMenuBar` / `QWidget` / `QStatusBar` instances respectively. This is the D-19 / QA-01 evidence that the scaffold actually renders under offscreen Qt.
- **`test_bundled_app_icon_loads`** — loads `QIcon(":/icons/app-icon.svg")` and asserts `icon.isNull() is False`. Proves the compiled `icons_rc.py` resource registration succeeded and the `:/icons/` prefix resolves.
- **`test_bundled_open_menu_icon_loads`** — same for `:/icons/open-menu-symbolic.svg`.
- **`test_fromtheme_fallback_uses_bundled_svg`** — PORT-08 fallback verification: `QIcon.fromTheme("musicstreamer-nonexistent-theme-name-xyz", QIcon(":/icons/app-icon.svg"))` must return a non-null icon. Synthetic theme name guarantees the system theme can't satisfy the lookup, so the bundled fallback is exercised.
- **`test_main_window_default_geometry`** — loose bounds `width() >= 800` / `height() >= 600` on a re-constructed + shown window. Exact 1200×800 is aspirational under offscreen Qt (which may clamp); loose bounds keep the test robust across platforms.

Module-level side-effect import `from musicstreamer.ui_qt import icons_rc  # noqa: F401` makes the test self-documenting even though `main_window.py` also does it.

### Task 2 — `tests/test_windows_palette.py` (commit `a70ce1e`)

3 tests covering the three `colorScheme()` branches of `_apply_windows_palette`:

- **`test_apply_windows_palette_dark`** — patches `PySide6.QtGui.QGuiApplication.styleHints` to return a `MagicMock` whose `colorScheme()` returns `Qt.ColorScheme.Dark`. Calls `_apply_windows_palette(qapp)`. Asserts `qapp.palette().color(QPalette.ColorRole.Window) == QColor(53, 53, 53)` — the canonical dark-Fusion window color from the helper's recipe.
- **`test_apply_windows_palette_light_noop`** — same but `Qt.ColorScheme.Light`. Snapshots the pre-call window color, calls the helper, asserts post == pre (early-return on non-Dark per D-15).
- **`test_apply_windows_palette_unknown_scheme_noop`** — same for `Qt.ColorScheme.Unknown`, proving the early-return also covers the "no preference known" case gracefully (no crash, no palette mutation).

Key implementation choice: `_apply_windows_palette` imports `QGuiApplication` at function scope (Plan 36-01 delivered it that way), so `patch("musicstreamer.__main__.QGuiApplication.styleHints")` would fail — the symbol doesn't exist at module scope. The plan explicitly allowed falling back to `patch("PySide6.QtGui.QGuiApplication.styleHints")`, which is what this plan uses. No changes to `musicstreamer/__main__.py` were required.

A `restore_palette` pytest fixture wraps each test to snapshot `qapp.palette()` before the test and `qapp.setPalette(original)` after, so the `test_apply_windows_palette_dark` mutation doesn't leak into the session-shared `qapp` and contaminate other tests later in the suite.

## Verification Results

| Check                                                              | Result          |
| ------------------------------------------------------------------ | --------------- |
| `test -f tests/test_ui_qt_scaffold.py`                             | PASS            |
| `test -f tests/test_windows_palette.py`                            | PASS            |
| `grep def test_main_window_constructs_and_renders`                 | found           |
| `grep def test_bundled_app_icon_loads`                             | found           |
| `grep def test_fromtheme_fallback_uses_bundled_svg`                | found           |
| `grep qtbot.waitExposed`                                           | found           |
| `grep 'windowTitle() == "MusicStreamer"'`                          | found           |
| `grep QIcon.fromTheme`                                             | found           |
| `grep def test_apply_windows_palette_dark`                         | found           |
| `grep def test_apply_windows_palette_light_noop`                   | found           |
| `grep _apply_windows_palette`                                      | found           |
| `grep 'QColor(53, 53, 53)'`                                        | found           |
| `grep Qt.ColorScheme.Dark`                                         | found           |
| `QT_QPA_PLATFORM=offscreen pytest tests/test_ui_qt_scaffold.py -q` | 5 passed        |
| `QT_QPA_PLATFORM=offscreen pytest tests/test_windows_palette.py -q`| 3 passed        |
| `QT_QPA_PLATFORM=offscreen pytest -q` (full suite)                 | **266 passed**  |
| `python -m musicstreamer --help` shows `--smoke`                   | PASS            |
| Zero `import gi` / `from gi` / `Gtk` / `Adw` in new test files     | PASS (grep empty) |

### Test count math

- 36-03 baseline: 258 passed
- 36-04 adds: 5 (scaffold) + 3 (palette) = 8
- 258 + 8 = **266 passed** — matches observed, exceeds the ≥263 floor from the execution-context rules.

## Phase 36 Requirements Coverage

All 6 phase requirements are now satisfied by at least one plan in Phase 36:

| Req     | Satisfied by            | Evidence                                                                                 |
| ------- | ----------------------- | ---------------------------------------------------------------------------------------- |
| PORT-03 | 36-01                   | `musicstreamer/ui_qt/` package with `MainWindow(QMainWindow)` scaffold                   |
| PORT-04 | 36-03                   | Entire `musicstreamer/ui/` GTK package + `mpris.py` deleted in atomic commit             |
| PORT-07 | 36-01 + **36-04**       | `_apply_windows_palette` helper exists; plan 04 unit-tests dark/light/unknown code paths |
| PORT-08 | 36-01 + **36-04**       | Bundled `:/icons/app-icon.svg` + `:/icons/open-menu-symbolic.svg`; plan 04 verifies `QIcon.fromTheme` fallback is non-null |
| QA-01   | **36-04**               | `tests/test_ui_qt_scaffold.py` — pytest-qt `qtbot.waitExposed(MainWindow)` proves the harness renders |
| QA-04   | 36-02 + 36-03           | No new behavior introduced — 36-02 extracted helpers, 36-03 deleted GTK, no feature parity ported |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] Patched `PySide6.QtGui.QGuiApplication.styleHints` directly instead of the `musicstreamer.__main__` attribute path**

- **Found during:** Task 2 planning (reading `_apply_windows_palette` in `musicstreamer/__main__.py`).
- **Issue:** The plan's primary template patched `musicstreamer.__main__.QGuiApplication.styleHints`, but Phase 36-01 delivered `_apply_windows_palette` with `from PySide6.QtGui import QGuiApplication` at **function scope**, not module scope. `musicstreamer.__main__.QGuiApplication` therefore doesn't exist as a module-level attribute and the patch would fail with `AttributeError: ... has no attribute 'QGuiApplication'`.
- **Fix:** Used the plan-authorized fallback — `patch("PySide6.QtGui.QGuiApplication.styleHints", ...)` — which patches at the source PySide6 module. This works regardless of where the helper imports it. No changes to `musicstreamer/__main__.py` were needed, so this is NOT a Phase 36-01 gap requiring a fix commit (the checkpoint policy was satisfied by staying within the plan's explicit fallback provision).
- **Files modified:** none beyond the new test file.
- **Commit:** `a70ce1e` (Task 2 commit — the fallback is baked into the initial test implementation).

**2. [Rule 2 — Auto-added critical functionality] `restore_palette` fixture for test isolation**

- **Found during:** Task 2 implementation review.
- **Issue:** The plan's template used the raw `qapp` fixture directly, but pytest-qt's `qapp` is session-scoped, meaning the `test_apply_windows_palette_dark` mutation (which actually calls `app.setPalette(dark_recipe)`) would bleed into every test that runs after it in the same session. The `light_noop` / `unknown_scheme_noop` tests handle this by comparing post vs pre, but any downstream test that constructs a widget and inspects default colors could observe the leaked dark palette.
- **Fix:** Added a `restore_palette` pytest fixture that snapshots `QPalette(qapp.palette())` before the test and `qapp.setPalette(original)` in the teardown. Each of the three palette tests uses this fixture instead of `qapp` directly. Verified: the full suite runs green with 266 passed, no color-related failures in tests after `test_apply_windows_palette_dark`.
- **Files modified:** `tests/test_windows_palette.py` (initial write).
- **Commit:** `a70ce1e` (folded into Task 2 commit).

## Authentication Gates

None — local test-only plan.

## Known Stubs

None introduced. Pre-existing Phase 36-01 stubs (placeholder `app-icon.svg`, empty menubar/central/status containers) remain intentional per D-01/D-03/D-11 and are unchanged.

## Threat Flags

None — pure test-file additions, no new runtime surface.

## Self-Check: PASSED

- `tests/test_ui_qt_scaffold.py` — FOUND
- `tests/test_windows_palette.py` — FOUND
- commit `73589e6` — FOUND (`test(36-04): add Qt scaffold smoke tests (QA-01, PORT-08)`)
- commit `a70ce1e` — FOUND (`test(36-04): add Windows Fusion dark-palette code-path tests (PORT-07)`)
- `QT_QPA_PLATFORM=offscreen pytest -q` → 266 passed
- `python -m musicstreamer --help` → shows argparse `--smoke`
- No `import gi` / `from gi` / `Gtk` / `Adw` in the new test files → confirmed via grep
