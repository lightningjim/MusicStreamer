---
phase: 20-os-media-keys-integration
plan: "02"
subsystem: mpris2-dbus
tags: [mpris2, dbus, media-keys, tdd, gtk4]
dependency_graph:
  requires: [20-01]
  provides: [MprisService, MPRIS2-bus-registration, playerctl-integration]
  affects: [musicstreamer/mpris.py, musicstreamer/ui/main_window.py]
tech_stack:
  added: [dbus-python 1.4.0 (system)]
  patterns: [TDD red-green, GLib.idle_add thread dispatch, dbus.service.Object subclass]
key_files:
  created:
    - musicstreamer/mpris.py
    - tests/test_mpris.py
  modified:
    - musicstreamer/ui/main_window.py
decisions:
  - "DBusGMainLoop(set_as_default=True) called at module import time in mpris.py before class definition (Pitfall 1 from RESEARCH.md)"
  - "All D-Bus handlers use GLib.idle_add() dispatch — never touch GTK state directly from D-Bus thread (T-20-04)"
  - "MprisService instantiation wrapped in try/except; app starts normally when D-Bus unavailable"
  - "import dbus deferred to call sites in main_window.py (inside if self.mpris blocks) to avoid import errors when mpris=None"
metrics:
  duration: ~18min
  completed: 2026-04-05
  tasks_completed: 2
  files_modified: 3
---

# Phase 20 Plan 02: MPRIS2 D-Bus Service Summary

MPRIS2 service registered as org.mpris.MediaPlayer2.MusicStreamer on session D-Bus using dbus-python; OS media keys and playerctl now control pause/resume and stop, with metadata (station name, ICY track title) emitted via PropertiesChanged on state changes.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create MprisService module with tests (TDD) | 3bdf590 | musicstreamer/mpris.py, tests/test_mpris.py |
| 2 | Wire MprisService into MainWindow and emit metadata updates | 93bbb2d | musicstreamer/ui/main_window.py |

## What Was Built

**Task 1 (TDD):**
- `musicstreamer/mpris.py`: `MprisService(dbus.service.Object)` implementing both `org.mpris.MediaPlayer2` (root) and `org.mpris.MediaPlayer2.Player` interfaces
- `DBusGMainLoop(set_as_default=True)` at module level before class definition
- `PlayPause`, `Play`, `Pause`, `Stop`, `Next`, `Previous` methods — all dispatch via `GLib.idle_add()`
- `GetAll`, `Get`, `PropertiesChanged` signal, `emit_properties_changed` helper
- `_get_all_root()`, `_get_all_player()`, `_build_metadata()` with ICY title as `xesam:artist`
- `tests/test_mpris.py`: 10 unit tests, all passing — mocks entire dbus hierarchy via `patch.dict(sys.modules, ...)`
- TDD RED (ModuleNotFoundError) → GREEN (10 passed) confirmed

**Task 2:**
- `from musicstreamer.mpris import MprisService` import added to `main_window.py`
- `self.mpris = MprisService(self)` in `__init__` with `try/except` fallback to `None`
- `emit_properties_changed` called in 4 locations:
  - `_on_cover_art`: emits Metadata + PlaybackStatus on ICY title change
  - `_play_station`: emits `PlaybackStatus="Playing"` + Metadata after pause reset
  - `_stop`: emits `PlaybackStatus="Stopped"` + Metadata after state clear
  - `_toggle_pause`: emits current `_playback_status()` after each branch

## Verification

```
python3 -m pytest tests/test_mpris.py -x -q   # 10 passed
python3 -m pytest tests/ -x -q                 # 184 passed
grep -n "class MprisService" musicstreamer/mpris.py   # line 24: found
grep -n "MprisService" musicstreamer/ui/main_window.py  # lines 18, 35, 37: found
grep -n "emit_properties_changed" musicstreamer/ui/main_window.py  # 4 occurrences: found
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] gi.repository.GLib re-import conflict in tests**
- **Found during:** Task 1 — first test run attempt
- **Issue:** `_fresh_import()` pattern re-imported the module per test, causing `RuntimeError: Unable to register enum 'PyGLibUserDirectory'` on the second GLib import
- **Fix:** Restructured tests to import `musicstreamer.mpris` once at module level with `patch.dict(sys.modules, ...)`, then use `patch.object(_mpris_mod, "GLib", mock_glib)` per test
- **Files modified:** tests/test_mpris.py

## Known Stubs

None. All MPRIS properties return live state from `MainWindow`. `emit_properties_changed` is called at every state transition. No hardcoded or placeholder values flow to playerctl/GNOME overlay.

## Threat Flags

No new trust boundaries introduced beyond those documented in the plan's threat model (T-20-03 through T-20-06). All D-Bus handlers dispatch to GTK thread via `GLib.idle_add()` per T-20-04 mitigation.

## Self-Check: PASSED
