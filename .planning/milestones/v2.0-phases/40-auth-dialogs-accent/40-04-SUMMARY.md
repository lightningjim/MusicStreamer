---
phase: 40-auth-dialogs-accent
plan: "04"
subsystem: ui_qt/main_window
tags: [hamburger-menu, accent-color, dialog-wiring, subprocess-utils, PKG-03]
dependency_graph:
  requires: [40-01, 40-02, 40-03]
  provides: [UI-10, UI-11, PKG-03]
  affects: [musicstreamer/ui_qt/main_window.py, musicstreamer/subprocess_utils.py]
tech_stack:
  added: [subprocess_utils._popen]
  patterns: [QMenu wiring, apply_accent_palette on startup, QAction.setEnabled/setToolTip]
key_files:
  created:
    - musicstreamer/subprocess_utils.py
  modified:
    - musicstreamer/ui_qt/main_window.py
    - tests/test_main_window_integration.py
decisions:
  - "_open_*_dialog() as bound methods per QA-05 — no self-capturing lambdas in signal connections"
  - "apply_accent_palette called inline in __init__ via QApplication.instance() — no stored app reference"
  - "subprocess_utils is a compliance stub — Phase 40 uses QProcess; _popen ready for future raw subprocess usage"
metrics:
  duration: "~15 min"
  completed: "2026-04-13T18:23:44Z"
  tasks_completed: 2
  files_changed: 3
---

# Phase 40 Plan 04: Hamburger Menu Wiring + Accent Startup Load Summary

**One-liner:** Wired 7-action hamburger menu (3 separator-divided groups) to all five dialog classes plus accent-color startup load from SQLite; added PKG-03 subprocess_utils stub.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | subprocess_utils.py (PKG-03) | 6218c30 | musicstreamer/subprocess_utils.py |
| 2 RED | Failing tests for menu wiring + accent startup | f534df9 | tests/test_main_window_integration.py |
| 2 GREEN | Hamburger menu wiring + accent startup load | 8fb1410 | musicstreamer/ui_qt/main_window.py |

## What Was Built

**subprocess_utils.py:** Centralized `_popen()` helper that adds `CREATE_NO_WINDOW` on Windows to suppress console flashes (PKG-03). Stub for now since Phase 40 uses QProcess; ready for future phases.

**Hamburger menu (UI-10):** Replaced the `≡` placeholder in `MainWindow.__init__` with a fully wired `self._menu` containing:
- Group 1: Discover Stations → `_open_discovery_dialog()`, Import Stations → `_open_import_dialog()`
- Separator
- Group 2: Accent Color → `_open_accent_dialog()`, YouTube Cookies → `_open_cookie_dialog()`, Accounts → `_open_accounts_dialog()`
- Separator
- Group 3: Export Settings (disabled, tooltip "Coming in a future update"), Import Settings (disabled, same tooltip)

**Accent startup load (UI-11):** After menu construction, reads `accent_color` from repo and calls `apply_accent_palette(QApplication.instance(), hex)` if non-empty. Runs every time MainWindow is constructed so the saved color is always in effect from first render.

**Dialog launchers:** Five `_open_*_dialog()` bound methods per QA-05. Discovery and Import call `_refresh_station_list()` after exec so newly imported stations appear immediately.

## Tests

7 new tests added to `tests/test_main_window_integration.py` (TDD RED→GREEN):

- `test_hamburger_menu_actions` — exactly 7 non-separator actions with correct text
- `test_hamburger_menu_separators` — exactly 2 separators
- `test_sync_actions_disabled` — Export/Import Settings `.isEnabled() is False`
- `test_sync_actions_tooltip` — tooltip == "Coming in a future update"
- `test_accent_loaded_on_startup` — palette Highlight color matches saved hex
- `test_discover_action_opens_dialog` — DiscoveryDialog.exec called on trigger
- `test_import_action_opens_dialog` — ImportDialog.exec called on trigger

**Result:** 30/30 integration tests pass. Plan-relevant suite (main_window + 3 dialog test files): 61/61 pass.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

T-40-11 (accent_color from SQLite injected to palette) is mitigated: `apply_accent_palette` calls `build_accent_qss` which uses `_is_valid_hex` to validate before QSS interpolation; invalid values are ignored (empty string returned). MainWindow startup load uses the same path.

T-40-12 (subprocess _popen with unbounded args) is mitigated: `_popen` never uses `shell=True`; args are always explicit lists passed by callers.

## Self-Check: PASSED

- `musicstreamer/subprocess_utils.py` — FOUND
- `musicstreamer/ui_qt/main_window.py` — contains `Discover Stations`, `Accounts`, `apply_accent_palette` — FOUND
- `tests/test_main_window_integration.py` — contains `test_hamburger_menu_actions`, `test_accent_loaded_on_startup` — FOUND
- Commits 6218c30, f534df9, 8fb1410 — FOUND
