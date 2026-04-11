---
phase: 36-qt-scaffold-gtk-cutover
verified: 2026-04-11T00:00:00Z
status: passed
score: 5/5 success criteria verified; 6/6 requirements satisfied
overrides_applied: 0
---

# Phase 36: Qt Scaffold + GTK Cutover Verification Report

**Phase Goal:** The app is a Qt application: bare QMainWindow launches, GTK codebase is deleted, icons are bundled, and the test harness uses offscreen Qt.
**Verified:** 2026-04-11
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `python -m musicstreamer` opens a Qt window (not GTK) on Linux | PASSED | `musicstreamer/__main__.py:98 _run_gui` constructs `QApplication` + `MainWindow` + `show()` + `app.exec()`; `--help` shows argparse surface with `--smoke` default-off (GUI is default path). MainWindow instantiates under offscreen Qt in `test_main_window_constructs_and_renders`. |
| 2 | `musicstreamer/ui/` does not exist; `musicstreamer/ui_qt/` is the only UI package | PASSED | `test -d musicstreamer/ui` → absent. `musicstreamer/ui_qt/` present with `__init__.py`, `main_window.py`, `icons.qrc`, `icons_rc.py`, `icons/` (app-icon.svg, open-menu-symbolic.svg, LICENSE). Grep for `from musicstreamer.ui[ .]` across repo → zero matches. |
| 3 | `pytest` runs with offscreen Qt platform and all phase-35 tests still pass (modulo documented fetch_* deletions) | PASSED | `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q` → **266 passed** in 1.64s. Math: 272 (phase 35 baseline) − 5 (fetch_aa_logo ×2 + fetch_yt_thumbnail ×3 documented in 36-02) − 9 (test_mpris.py documented in 36-03) + 8 (36-04 new scaffold/palette tests) = 266. ✓ |
| 4 | Bundled SVG icons load from .qrc resource; no missing-icon errors | PASSED | `tests/test_ui_qt_scaffold.py::test_bundled_app_icon_loads` and `test_bundled_open_menu_icon_loads` both assert `QIcon(":/icons/…svg").isNull() is False`. `test_fromtheme_fallback_uses_bundled_svg` verifies the `QIcon.fromTheme("nonexistent", fallback)` pattern returns non-null — the PORT-08 fallback path. icons_rc.py is committed and auto-imported at top of `main_window.py`. |
| 5 | Windows dark-mode regression does not occur (Fusion style enforced on Windows) | PASSED (code path) | `_apply_windows_palette` exists at `__main__.py:65`. Call site at `__main__.py:110-112` gates on `sys.platform == "win32"` and calls `app.setStyle("Fusion")` BEFORE widget construction, then applies dark palette. `tests/test_windows_palette.py` exercises all 3 colorScheme branches (Dark → QColor(53,53,53); Light/Unknown → no-op). Cannot execute on Linux (correct — gate prevents it), but code path is unit-tested. |

**Score:** 5/5 success criteria verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/ui_qt/__init__.py` | Package marker | VERIFIED | Present |
| `musicstreamer/ui_qt/main_window.py` | MainWindow(QMainWindow) scaffold | VERIFIED | 56 lines, QMainWindow subclass with title, icon, menubar, central widget, statusbar, `icons_rc` side-effect import at top |
| `musicstreamer/ui_qt/icons.qrc` | Qt resource descriptor | VERIFIED | Present |
| `musicstreamer/ui_qt/icons_rc.py` | Compiled resource module | VERIFIED | Present, auto-imported by main_window.py |
| `musicstreamer/ui_qt/icons/app-icon.svg` | App icon | VERIFIED | Present |
| `musicstreamer/ui_qt/icons/open-menu-symbolic.svg` | Hamburger icon | VERIFIED | Present, verbatim from Adwaita |
| `musicstreamer/ui_qt/icons/LICENSE` | CC-BY-SA attribution | VERIFIED | Present |
| `musicstreamer/url_helpers.py` | Pure URL helpers (extracted) | VERIFIED | 4 functions, zero GTK/Qt coupling |
| `musicstreamer/__main__.py` | Qt entry with --smoke flag | VERIFIED | argparse dispatcher, _run_gui + _run_smoke split, _apply_windows_palette helper |
| `tests/test_ui_qt_scaffold.py` | QA-01 scaffold smoke tests | VERIFIED | 5 tests present |
| `tests/test_windows_palette.py` | PORT-07 palette tests | VERIFIED | 3 tests present, all 3 colorScheme branches |
| `musicstreamer/ui/` | Deleted | VERIFIED | Absent |
| `musicstreamer/mpris.py` | Deleted | VERIFIED | Absent |
| `tests/test_mpris.py` | Deleted | VERIFIED | Absent |
| `build/` | Deleted | VERIFIED | Absent |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `__main__._run_gui` | `ui_qt.main_window.MainWindow` | lazy import + construct | WIRED (line 107-114) |
| `__main__._run_gui` | `ui_qt.icons_rc` | side-effect import | WIRED (line 106) |
| `main_window.MainWindow` | `ui_qt.icons_rc` | top-of-module side-effect import | WIRED (line 14) |
| `__main__._run_gui` | `_apply_windows_palette` | `sys.platform == "win32"` gate | WIRED (line 110-112) |
| `_apply_windows_palette` | `QApplication.setPalette` | early-return unless `Qt.ColorScheme.Dark` | WIRED (line 76-95) |
| `__main__._run_smoke` | `Player` + `QCoreApplication` | function-local imports, no ui_qt | WIRED (line 16-62, D-05/D-24 verified — no ui_qt in smoke path) |
| `__main__._run_gui` | `migration.run_migration` | pre-widget call | WIRED (line 102-103) |
| `url_helpers` | `aa_import.NETWORKS` | module-level import | WIRED |
| `tests/test_aa_url_detection.py` | `url_helpers` | import rewired | WIRED |
| `tests/test_yt_thumbnail.py` | `url_helpers._is_youtube_url` | import rewired | WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full offscreen test suite passes | `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q` | 266 passed in 1.64s | PASS |
| Entry point help runs without error | `.venv/bin/python -m musicstreamer --help` | exits 0, shows `--smoke [URL]` | PASS |
| `musicstreamer/ui/` absent | `test -d musicstreamer/ui` | absent | PASS |
| `musicstreamer/mpris.py` absent | `test -f musicstreamer/mpris.py` | absent | PASS |
| `tests/test_mpris.py` absent | `test -f tests/test_mpris.py` | absent | PASS |
| Zero `from musicstreamer.ui` references | grep repo-wide `.py` | 0 matches | PASS |
| Zero `from musicstreamer.mpris` references | grep repo-wide `.py` | 0 matches | PASS |
| Zero `import dbus` / `from dbus` / `DBusGMainLoop` | grep repo-wide `.py` | 0 matches | PASS |
| Zero `Gtk` / `Adw` / `GdkPixbuf` imports | grep repo-wide `.py` | 0 matches | PASS |
| Only `Gst` + `GLib` from `gi.repository` (expected per Phase 35) | grep | `__main__.py` (Gst), `player.py` (Gst), `gst_bus_bridge.py` (GLib) | PASS (expected) |
| `_apply_windows_palette` exists and is win32-gated | grep `__main__.py` | line 65 def, line 110-112 call under `sys.platform == "win32"` | PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| PORT-03 | Qt scaffold (`QApplication` + `QMainWindow`) replaces GTK/Libadwaita widgets; app launches with empty window | SATISFIED | `ui_qt/main_window.py` MainWindow(QMainWindow); `__main__._run_gui` constructs QApplication + MainWindow; `test_main_window_constructs_and_renders` confirms offscreen render |
| PORT-04 | `musicstreamer/ui/` deleted; `ui_qt/` is the only UI package; hard cutover | SATISFIED | `ui/` absent; `ui_qt/` present; grep for `from musicstreamer.ui` → 0 matches in musicstreamer/ and tests/ |
| PORT-07 | Force Qt Fusion style on Windows with dark-mode detection and accent-color handling | SATISFIED | `__main__.py:110-112` sets Fusion + applies dark palette when `sys.platform == "win32"`; `test_windows_palette.py` exercises all 3 colorScheme branches |
| PORT-08 | Bundled SVG icon set shipped via `.qrc`; `QIcon.fromTheme("name", QIcon(":/icons/name.svg"))` fallback pattern | SATISFIED | `icons.qrc` + `icons_rc.py` + 2 SVGs shipped; `main_window.py:35-38` uses fromTheme+fallback for windowIcon; `test_fromtheme_fallback_uses_bundled_svg` verifies fallback returns non-null |
| QA-01 | `pytest-qt` with offscreen platform replaces GTK fake-display; v1.5 tests ported | SATISFIED | `conftest.py` sets `QT_QPA_PLATFORM=offscreen`; pytest-qt `qtbot` used; `test_ui_qt_scaffold.py::test_main_window_constructs_and_renders` uses `qtbot.waitExposed` as D-19 evidence |
| QA-04 | Per-phase "no new behavior" gate enforced | SATISFIED | Phase 36 only scaffold + delete + test — no new user-facing features. Plan summaries document strict scope containment (hamburger menu is empty placeholder, central widget empty, deferring UI-10/UI-01/UI-02 to later phases) |

No orphaned requirements detected — REQUIREMENTS.md Traceability table aligns with what this phase delivered.

### Anti-Patterns Found

Known intentional placeholders (documented in plan summaries, not blockers):

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `musicstreamer/ui_qt/icons/app-icon.svg` | Placeholder blue rounded-rect SVG | Info | Intentional per D-11 — Phase 37+ replaces with real branding |
| `musicstreamer/ui_qt/main_window.py` | Empty central widget QVBoxLayout | Info | Intentional per D-01 — Phase 37 populates |
| `musicstreamer/ui_qt/main_window.py` | Empty hamburger menu (no QAction children) | Info | Intentional per D-03 — Phase 40 wires UI-10 |
| `musicstreamer/ui_qt/main_window.py` | Empty QStatusBar | Info | Intentional per D-01 — Phase 37 adds toast overlay |

No TODOs, no `return null/[]/{}` in load-bearing paths, no orphaned stubs that would block phase goal. All are scoped to Phase 37+ per the phase boundary and documented in the plan summaries.

### Human Verification Required

None. All 5 success criteria verifiable programmatically:
- Criterion 1 (Qt window opens): verified via offscreen `qtbot.waitExposed(MainWindow)` in test_ui_qt_scaffold
- Criterion 2 (ui/ deleted): verified via filesystem + grep
- Criterion 3 (266 tests pass): verified via pytest run
- Criterion 4 (icons load): verified via QIcon.isNull() checks
- Criterion 5 (Windows Fusion): code path verified via mocked styleHints; actual Windows VM verification deferred to Phase 43/44 per roadmap QA-03

No UI polish, user flow, or real-time behavior in this phase requires human eyes — the phase goal is explicitly "bare window launches" with structural-only containers.

### Gaps Summary

No gaps. Phase 36 achieves its goal exactly as scoped. All 5 ROADMAP success criteria pass, all 6 requirement IDs (PORT-03, PORT-04, PORT-07, PORT-08, QA-01, QA-04) are satisfied by real code and committed tests. 266 tests pass under offscreen Qt (matches plan summary claim). Grep sweeps for residual GTK/Adwaita/dbus-python imports are all empty. The entry point, MainWindow, bundled icons, Windows palette helper, and pytest-qt harness all exist, are substantive, are wired together, and are exercised by tests.

The `--smoke` headless backend path is preserved per D-05 and does not import `ui_qt`. The GUI path imports `icons_rc` as a side effect before MainWindow construction. The Windows Fusion gate is the single PORT-07 branch point and is unit-tested.

Phase 36 is complete and ready for Phase 37 (Station List + Now Playing).

---

*Verified: 2026-04-11*
*Verifier: Claude (gsd-verifier)*
