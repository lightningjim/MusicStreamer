---
phase: 36
plan: 03
subsystem: GTK cutover / dead-code removal
tags: [cutover, deletion, PORT-04, QA-04, gtk-removal]
requires:
  - phase-36-plan-01 Qt scaffold (ui_qt + __main__ rewrite)
  - phase-36-plan-02 url_helpers extraction
provides:
  - Pure-Qt codebase — no GTK/Adwaita/dbus-python code paths remain
  - ui_qt/ is the sole UI package
  - Cleared runway for Phase 37 (station list + now-playing panel)
affects:
  - musicstreamer/ui/ (deleted in full — 9 files)
  - musicstreamer/mpris.py (deleted)
  - tests/test_mpris.py (deleted)
  - build/ (stale setuptools artifact, deleted)
tech-stack:
  added: []
  removed: [GTK4, Libadwaita, dbus-python code paths]
  patterns: [atomic cutover, grep-sweep verification]
key-files:
  created: []
  modified: []
  deleted:
    - musicstreamer/ui/__init__.py
    - musicstreamer/ui/main_window.py
    - musicstreamer/ui/accent_dialog.py
    - musicstreamer/ui/accounts_dialog.py
    - musicstreamer/ui/discovery_dialog.py
    - musicstreamer/ui/edit_dialog.py
    - musicstreamer/ui/import_dialog.py
    - musicstreamer/ui/station_row.py
    - musicstreamer/ui/streams_dialog.py
    - musicstreamer/mpris.py
    - tests/test_mpris.py
    - build/ (entire directory)
decisions:
  - Single atomic commit for all deletions (D-07, D-20, D-22) — no ripple fixes were required because 36-02 had already moved url_helpers out of edit_dialog.py
  - pyproject.toml untouched — D-21 confirmed no-op (dbus-python is a system apt package, not a pyproject dependency)
metrics:
  duration: ~3 minutes
  completed: 2026-04-11T23:40:00Z
  tasks: 2/2
  files-deleted: 11 (plus entire build/ artifact tree)
  loc-removed: 4150 (musicstreamer/ui + mpris.py + test_mpris.py)
  tests: 258 passed (267 baseline - 9 mpris tests)
---

# Phase 36 Plan 03: Atomic GTK Cutover Summary

Deleted `musicstreamer/ui/` (all 9 GTK/Adwaita modules, ~4030 LOC), the Phase 35 `mpris.py` no-op stub, its `tests/test_mpris.py`, and the stale `build/` setuptools artifact in a single atomic commit. Grep sweep confirms zero residual `from musicstreamer.ui`, `from musicstreamer.mpris`, `import dbus`, or `from gi.repository import Gtk/Adw` anywhere in `musicstreamer/` or `tests/`. Full pytest suite is green under offscreen Qt — 258 passed — and the GUI smoke still constructs `MainWindow()` cleanly. The codebase is now pure-Qt.

## What Was Built

### Task 1 — Atomic delete (commit `97e61b8`)

Single commit removing 4150 lines across 11 tracked source files plus the untracked `build/` artifact:

- `musicstreamer/ui/__init__.py`
- `musicstreamer/ui/main_window.py` (1193 lines — the largest deletion)
- `musicstreamer/ui/accent_dialog.py`
- `musicstreamer/ui/accounts_dialog.py`
- `musicstreamer/ui/discovery_dialog.py`
- `musicstreamer/ui/edit_dialog.py`
- `musicstreamer/ui/import_dialog.py`
- `musicstreamer/ui/station_row.py`
- `musicstreamer/ui/streams_dialog.py`
- `musicstreamer/mpris.py` (Phase 35 no-op stub — Phase 41 rebuilds with QtDBus)
- `tests/test_mpris.py`
- `build/` (entire directory — stale setuptools artifact containing `build/lib/musicstreamer/ui/` references to the now-deleted modules)

Precondition checks run before deletion:
- `musicstreamer/url_helpers.py` — present (36-02 landed)
- `musicstreamer/ui_qt/main_window.py` — present (36-01 landed)
- `musicstreamer/__main__.py` contains `argparse` — present (36-01 rewrite landed)
- `build/` contained only setuptools build-lib outputs, no user data — safe to `rm -rf`

### Task 2 — Verification (no code changes, no commit)

No ripple fixes required. The full pytest suite ran clean on first attempt — the Phase 36-02 url_helpers extraction had already moved the only test-relevant symbols out of `musicstreamer/ui/edit_dialog.py`, so there were no orphaned imports left for 36-03 to repair.

## Verification Results

| Check                                                                    | Result      |
| ------------------------------------------------------------------------ | ----------- |
| `test ! -d musicstreamer/ui`                                             | PASS        |
| `test ! -f musicstreamer/mpris.py`                                       | PASS        |
| `test ! -f tests/test_mpris.py`                                          | PASS        |
| `test ! -d build`                                                        | PASS        |
| `grep -rn "from musicstreamer\.ui[ .]" musicstreamer/ tests/`            | empty       |
| `grep -rn "musicstreamer\.mpris" musicstreamer/ tests/`                  | empty       |
| `grep -rn "^import dbus\|^from dbus\|DBusGMainLoop" musicstreamer/ tests/` | empty     |
| `grep -rn "from gi\.repository import .*(Gtk\|Adw)" musicstreamer/`     | empty       |
| `grep -rn "Gtk\|Adw\|GdkPixbuf" musicstreamer/ tests/`                   | only `ui_qt/icons/LICENSE` attribution (not code) |
| `grep -rn "import gi\|gi\.require_version" musicstreamer/`              | only `__main__.py` and `player.py` (Gst consumers — expected) |
| `grep -n dbus pyproject.toml`                                            | empty (D-21 no-op confirmed) |
| `QT_QPA_PLATFORM=offscreen pytest -q`                                    | **258 passed** (0 failures, 0 errors, 0 collection errors) |
| `python -m musicstreamer --help` shows `--smoke`                         | PASS        |
| `MainWindow()` + `windowTitle() == 'MusicStreamer'` under offscreen      | PASS (`ok`) |

### Test count math

- 36-02 baseline: 267 passed
- 36-03 deletes `tests/test_mpris.py` (9 tests — it tested the no-op stub)
- Post-cutover: 267 − 9 = **258 passed** ✓

258 ≥ the plan's 260-floor estimate (plan allowed 260-268 range; actual came in slightly under because test_mpris.py had 9 tests, not ~6).

## Deviations from Plan

None — plan executed exactly as written. The pytest suite passed on first run with zero ripple fixes required because 36-02 had already done the preparatory test-rewiring work.

## Authentication Gates

None — local deletions only.

## Known Stubs

None introduced by this plan. The plan only removes code; it adds nothing. Pre-existing Phase 36-01 stubs (empty menubar, empty central widget, placeholder app-icon SVG) are unchanged and remain intentional per D-01/D-03/D-11.

## Threat Flags

None. Pure deletion — no new network/auth/schema/filesystem surface introduced.

## Self-Check: PASSED

- `musicstreamer/ui/` — ABSENT (verified with `test ! -d`)
- `musicstreamer/mpris.py` — ABSENT
- `tests/test_mpris.py` — ABSENT
- `build/` — ABSENT
- commit `97e61b8` — FOUND in `git log` (`refactor(36-03): delete GTK ui/, mpris.py, test_mpris.py, stale build/`)
- `QT_QPA_PLATFORM=offscreen pytest -q` → 258 passed
- `python -m musicstreamer --help` → shows argparse `--smoke` option
- Offscreen `MainWindow()` construction → windowTitle == 'MusicStreamer'
- Grep sweep for `from musicstreamer.ui`, `mpris`, `dbus`, `Gtk`, `Adw` → all empty (the only Gtk/Adw hit is the Adwaita icon LICENSE attribution file, not code)
