---
phase: 36
plan: 01
subsystem: ui_qt / entry-point
tags: [qt, pyside6, scaffold, cutover, PORT-03, PORT-07, PORT-08]
requires:
  - phase-35 Player(QObject) + typed Qt signals
  - phase-35 migration.run_migration
  - pyside6-rcc toolchain (PySide6 >=6.11 in pyproject)
provides:
  - musicstreamer.ui_qt package with MainWindow(QMainWindow) scaffold
  - bundled Adwaita SVG icons via :/icons/ Qt resource prefix
  - argparse-dispatched __main__ (GUI default, --smoke headless)
  - _apply_windows_palette helper (Fusion dark, win32-only)
affects:
  - musicstreamer/__main__.py (rewritten)
  - tests/test_headless_entry.py (updated to drive --smoke path)
tech-stack:
  added: [PySide6.QtWidgets.QMainWindow, PySide6.QtGui.QPalette, pyside6-rcc]
  patterns: [lazy imports for GUI/smoke split, side-effect resource registration, argparse parse_known_args]
key-files:
  created:
    - musicstreamer/ui_qt/__init__.py
    - musicstreamer/ui_qt/main_window.py
    - musicstreamer/ui_qt/icons.qrc
    - musicstreamer/ui_qt/icons_rc.py
    - musicstreamer/ui_qt/icons/app-icon.svg
    - musicstreamer/ui_qt/icons/open-menu-symbolic.svg
    - musicstreamer/ui_qt/icons/LICENSE
  modified:
    - musicstreamer/__main__.py
    - tests/test_headless_entry.py
decisions:
  - Use <file alias="..."> in icons.qrc so resources live at :/icons/<name>.svg instead of :/icons/icons/<name>.svg (rcc compiles file paths relative to the .qrc directory, which would otherwise nest the prefix)
  - _run_smoke keeps PySide6.QtCore import function-local so tests can patch it via PySide6.QtCore.QCoreApplication directly
metrics:
  duration: ~6 minutes
  completed: 2026-04-11T23:32:03Z
  tasks: 2/2
  files-created: 7
  files-modified: 2
  tests: 272 passed (unchanged from Phase 35 baseline)
---

# Phase 36 Plan 01: Qt Scaffold + Entry-Point Cutover Summary

Qt/PySide6 replaces the GTK entry point: new `ui_qt` package with a bare-chrome `MainWindow(QMainWindow)`, bundled Adwaita SVG icons compiled via `pyside6-rcc`, and an argparse-dispatched `__main__.py` that opens the Qt window by default while preserving the Phase 35 headless smoke harness behind `--smoke URL`.

## What Was Built

### Task 1 — `ui_qt` package + bundled icons (commit `061fa33`)

- `musicstreamer/ui_qt/__init__.py` — empty package marker (per D-23).
- `musicstreamer/ui_qt/main_window.py` — `MainWindow(QMainWindow)` subclass with structural containers only (D-01):
  - `setWindowTitle("MusicStreamer")`, `resize(1200, 800)` (D-02).
  - `QIcon.fromTheme("application-x-executable", QIcon(":/icons/app-icon.svg"))` (PORT-08 fallback pattern).
  - Menubar placeholder: `menuBar().addMenu("≡")` — one empty menu, zero `QAction` children (D-03, defers UI-10 to Phase 40).
  - Central `QWidget` with empty zero-margin/zero-spacing `QVBoxLayout` (Phase 37 populates).
  - Empty `QStatusBar` (Phase 37 adds toast overlay per UI-12).
  - Top-of-file side-effect import `from musicstreamer.ui_qt import icons_rc  # noqa: F401` so tests that construct `MainWindow` get resources registered automatically (D-24, research Pitfall 2).
- `musicstreamer/ui_qt/icons/open-menu-symbolic.svg` — copied verbatim from `/usr/share/icons/Adwaita/symbolic/actions/open-menu-symbolic.svg` (D-10, D-11).
- `musicstreamer/ui_qt/icons/app-icon.svg` — minimal 16×16 blue rounded rectangle placeholder (D-11; Phase 37+ replaces).
- `musicstreamer/ui_qt/icons/LICENSE` — CC-BY-SA 3.0 attribution for GNOME Project (D-10).
- `musicstreamer/ui_qt/icons.qrc` — Qt resource descriptor with `<qresource prefix="/icons">` and `<file alias="...">` entries so resources resolve at `:/icons/<filename>.svg`.
- `musicstreamer/ui_qt/icons_rc.py` — `pyside6-rcc`-generated resource module, committed per D-12/D-23. Reproducible: regenerating with `pyside6-rcc musicstreamer/ui_qt/icons.qrc -o ...` produces byte-identical output.

### Task 2 — `__main__.py` rewrite (commit `9ba66fe`)

- Argparse dispatcher with `--smoke [URL]` flag (nargs='?' + `const=DEFAULT_SMOKE_URL` so bare `--smoke` picks the default SomaFM URL) using `parse_known_args` so Qt-specific flags (`-platform`, `-style`, etc.) pass through to `QApplication` (research Pattern 4).
- `_run_gui(argv)` — GUI path: `Gst.init` → `migration.run_migration` → lazy imports of `QApplication`, `icons_rc` (side-effect), `MainWindow` → `QApplication(argv)` → Windows-only `app.setStyle("Fusion")` + `_apply_windows_palette(app)` (D-14, D-15, PORT-07) → `MainWindow()` + `show()` + `app.exec()`.
- `_run_smoke(argv, url)` — exact Phase 35 behavior preserved: `Gst.init`, `migration.run_migration`, `QCoreApplication`, `Player()`, four signal `print` connections, `QTimer.singleShot(0, ...)`. Accepts URL as a parameter instead of slicing `argv[1]`. All PySide6/Player/migration imports are function-local so the smoke path never touches `ui_qt` (D-05, D-24).
- `_apply_windows_palette(app)` — canonical 15-color Fusion dark `QPalette` recipe from research Pattern 3. Early-return when `QGuiApplication.styleHints().colorScheme() != Qt.ColorScheme.Dark` (light Fusion is acceptable per D-15). Helper is invoked only under the `sys.platform == "win32"` gate — single PORT-07 branch point.
- No imports from `musicstreamer.ui` (D-08 gate satisfied).

## Verification Results

| Check                                                              | Result        |
| ------------------------------------------------------------------ | ------------- |
| `python -c "from musicstreamer.ui_qt.main_window import MainWindow"` | PASS          |
| `QFile(":/icons/app-icon.svg").exists()` after `icons_rc` import   | `True`        |
| `QFile(":/icons/open-menu-symbolic.svg").exists()`                  | `True`        |
| `pyside6-rcc ... -o /tmp/icons_rc_regen.py && diff`                 | byte-identical |
| Offscreen `MainWindow()` — title/menubar/central/statusbar         | all present   |
| `python -m musicstreamer --help` shows `--smoke`                    | PASS          |
| `QT_QPA_PLATFORM=offscreen pytest -q`                               | **272 passed** (unchanged) |
| `grep "from musicstreamer.ui" musicstreamer/__main__.py`            | no matches (D-08) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] icons.qrc produced nested resource path `:/icons/icons/<name>.svg`**

- **Found during:** Task 1 verification — running `MainWindow()` emitted `qt.svg: Cannot open file ':/icons/app-icon.svg'`.
- **Root cause:** `pyside6-rcc` resolves `<file>` entries relative to the `.qrc` directory, so `icons/app-icon.svg` combined with the `/icons` prefix produced `:/icons/icons/app-icon.svg`. The plan's qrc content was literally what's in the plan, but the spec ("files accessible via `:/icons/` prefix") required aliasing.
- **Fix:** Added `alias="<filename>"` attributes so resources resolve at `:/icons/app-icon.svg` and `:/icons/open-menu-symbolic.svg` — matching the pattern `QIcon(":/icons/app-icon.svg")` in `main_window.py` and the PORT-08 research Pattern 6.
- **Files modified:** `musicstreamer/ui_qt/icons.qrc`, regenerated `musicstreamer/ui_qt/icons_rc.py`.
- **Commit:** folded into `061fa33` (Task 1 commit, discovered before commit).

**2. [Rule 3 — Blocking issue] `tests/test_headless_entry.py` broke on Phase 36 entry rewrite**

- **Found during:** Task 2 verification (`pytest -q`) — 1 test failing with `AttributeError: 'module' object at musicstreamer.__main__ has no attribute 'Player'`.
- **Root cause:** The Phase 35 test monkeypatched `musicstreamer.__main__.Player`, `Gst.init`, `migration.run_migration`, `QCoreApplication`, and `QTimer` as module-level names. Phase 36 moved those imports inside `_run_smoke` so the `--smoke` path stays decoupled from widgets (D-05/D-24), which erases the module-level names. The test also passed `["prog", URL]` positionally, but the Phase 36 CLI requires `--smoke URL`.
- **Fix:** Updated the test to (a) call `main(["prog", "--smoke", URL])`, (b) patch `musicstreamer.player.Player`, `musicstreamer.migration.run_migration`, and `PySide6.QtCore.QCoreApplication` at their canonical module paths. Still stubs `Gst.init` at `musicstreamer.__main__.Gst.init` (module-level — still present). Renamed the test function and updated its docstring to reflect Phase 36 semantics.
- **Files modified:** `tests/test_headless_entry.py`.
- **Commit:** `9ba66fe` (Task 2 commit).
- **D-18 compliance:** 272 passed after the fix (matches Phase 35 baseline).

## Authentication Gates

None — this plan is local-only.

## Known Stubs

- `musicstreamer/ui_qt/icons/app-icon.svg` — placeholder blue rounded-rect per D-11. Deliberate; Phase 37+ replaces with real branding.
- `MainWindow` central widget/menubar/status bar are empty placeholders by design (D-01/D-03). Phase 37+ populates. Not bugs — expected Phase 36 state.

## Threat Flags

None — additive scaffold, no new network/auth/schema surface.

## Self-Check: PASSED

- `musicstreamer/ui_qt/__init__.py` — FOUND
- `musicstreamer/ui_qt/main_window.py` — FOUND
- `musicstreamer/ui_qt/icons.qrc` — FOUND
- `musicstreamer/ui_qt/icons_rc.py` — FOUND (contains `qInitResources`)
- `musicstreamer/ui_qt/icons/app-icon.svg` — FOUND
- `musicstreamer/ui_qt/icons/open-menu-symbolic.svg` — FOUND
- `musicstreamer/ui_qt/icons/LICENSE` — FOUND (contains `CC-BY-SA`)
- `musicstreamer/__main__.py` — MODIFIED (argparse + Qt GUI + smoke split)
- commit `061fa33` — FOUND (Task 1)
- commit `9ba66fe` — FOUND (Task 2)
- `QT_QPA_PLATFORM=offscreen pytest -q` — 272 passed
