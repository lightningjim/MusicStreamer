---
phase: 35-backend-isolation
plan: 03
subsystem: backend
tags: [yt-dlp, mpris, library-api, stub]
requires:
  - "musicstreamer.paths.cookies_path() (provided by Plan 35-02)"
provides:
  - "musicstreamer.yt_import.scan_playlist via yt_dlp.YoutubeDL library API (zero subprocess)"
  - "musicstreamer.mpris.MprisService no-op stub preserving public surface"
affects:
  - musicstreamer/yt_import.py
  - musicstreamer/mpris.py
  - tests/test_yt_import_library.py
tech-stack:
  added:
    - "yt_dlp.YoutubeDL library API in yt_import.py"
  patterns:
    - "Mock yt_dlp.YoutubeDL via patch('musicstreamer.yt_import.yt_dlp.YoutubeDL') with __enter__/__exit__ context manager"
    - "live_status fallback when extract_flat leaves is_live=None (RESEARCH Pitfall 1)"
    - "Pure-Python stub preserving public method surface during phased rewrite"
key-files:
  created:
    - tests/test_yt_import_library.py
  modified:
    - musicstreamer/yt_import.py
    - musicstreamer/mpris.py
decisions:
  - "yt_import errors mapped: DownloadError(private/unavailable/not accessible) -> ValueError, all others -> RuntimeError"
  - "mpris stub kept at 38 lines (under 60-line cap) with zero dbus/gi/Qt imports — pure-Python only"
metrics:
  duration_min: 6
  tasks: 2
  files_changed: 3
  completed: 2026-04-11
requirements: [PORT-09]
---

# Phase 35 Plan 03: yt-dlp Library Port + MPRIS Stub Summary

**One-liner:** Replaced yt_import.py's `subprocess.Popen(['yt-dlp', ...])` with `yt_dlp.YoutubeDL.extract_info` and reduced mpris.py to a 38-line no-op stub preserving the GTK main_window public surface.

## What Shipped

1. **yt_import.py — full library-API rewrite** (50/49 line delta, replacing 79 lines of subprocess code).
   - `scan_playlist()` opens `yt_dlp.YoutubeDL({'extract_flat': 'in_playlist', 'quiet': True, 'no_warnings': True, 'skip_download': True})` and calls `extract_info(url, download=False)`.
   - Cookies routed via `paths.cookies_path()` (Plan 35-02 deliverable). Added to opts only when the file exists.
   - `_entry_is_live()` helper handles RESEARCH Pitfall 1: prefers `live_status` (`'is_live'`/`'was_live'`/`'not_live'`/`'post_live'`) over the often-None `is_live` field on sparse flat-playlist entries.
   - DownloadError mapping: substring match on `private`/`unavailable`/`not accessible` → `ValueError("Playlist Not Accessible")`; all other DownloadErrors → `RuntimeError(str(e))`.
   - `is_yt_playlist_url()` and `import_stations()` preserved verbatim.
   - Imports trimmed: dropped `json`, `shutil`, `subprocess`, `tempfile`; kept `os`, `re`; added `yt_dlp` and `from musicstreamer import paths`.

2. **mpris.py — full replacement with no-op stub** (170 → 38 lines).
   - `MprisService(window=None)` accepts the same constructor signature.
   - `emit_properties_changed(props)` is a no-op that ignores any dict shape, including the dbus-typed values that current `main_window.py` constructs locally on lines 700-709, 773-777, 807-812, 963-968.
   - `_build_metadata()` returns `{}`.
   - One-line `_log.debug("MprisService stub active — media keys disabled until Phase 41 (MEDIA-02)")` on construction (D-11).
   - Zero `dbus`, `dbus.service`, `gi`, `GLib`, `PySide6`, or `QtDBus` imports — verified by grep of import lines only.

3. **tests/test_yt_import_library.py** — new, 8 test cases:
   - `test_scan_playlist_happy_path_returns_live_entries`
   - `test_scan_playlist_uses_live_status_when_is_live_missing` (Pitfall 1)
   - `test_scan_playlist_private_raises_valueerror`
   - `test_scan_playlist_other_error_raises_runtimeerror`
   - `test_scan_playlist_passes_cookies_when_file_exists` (verifies opts dict)
   - `test_scan_playlist_omits_cookiefile_when_missing`
   - `test_is_yt_playlist_url_unchanged` (regression)
   - `test_import_stations_unchanged` (regression — dedup + on_progress callback ordering)
   - All 8 pass in 0.25s. Mocks `musicstreamer.yt_import.yt_dlp.YoutubeDL` so no real network or subprocess.

## Verification

- `pytest tests/test_yt_import_library.py -x` → 8 passed
- `pytest tests/test_yt_import_library.py tests/test_paths.py tests/test_migration.py -q` → 17 passed
- `grep -E "^import subprocess|subprocess\\.(run|Popen)|shutil|tempfile" musicstreamer/yt_import.py` → no matches
- `grep -q "import yt_dlp\|YoutubeDL\|extract_flat\|live_status\|from musicstreamer import paths" musicstreamer/yt_import.py` → 7 matches across patterns
- `python -c "from musicstreamer.mpris import MprisService; s=MprisService(None); s.emit_properties_changed({'a':1}); assert s._build_metadata()=={}"` → ok
- `grep -nE "^import dbus|^from dbus|^import gi|^from gi|^from PySide6|^import PySide6" musicstreamer/mpris.py` → no matches
- `wc -l musicstreamer/mpris.py` → 38 (cap was 60)
- `python -c "import ast; ast.parse(open('musicstreamer/ui/main_window.py').read())"` → ok (main_window.py syntax intact; imports of MprisService still resolve)

## Deviations from Plan

None — plan executed exactly as written. Plan 35-02 had already landed (`739d455 feat(35-02): add paths.py + migration.py with TDD tests`) before this plan started, so the `from musicstreamer import paths` / `paths.cookies_path()` route specified in the plan worked on the first try. The orchestrator's "use constants.py instead" fallback note in the prompt was not needed.

Note on final stub edit: the initial `_log.debug(...)` call was wrapped across 3 lines, which would have failed the plan's `_log\.(debug|info|warning).*stub` regex acceptance check. Collapsed to a single line (still under 60-line cap) so the regex matches. Not a deviation — same semantics, same call.

## Authentication Gates

None.

## Known-Failing Tests (handed off to Plan 35-05)

These two test files are intentionally left in a broken state by this plan and **must be addressed in Plan 35-05** (per RESEARCH.md Pitfall 8 and D-25):

1. **`tests/test_mpris.py`** — uses `patch.dict("sys.modules", _MODULE_PATCHES)` to mock `dbus`, `dbus.service`, `dbus.mainloop.glib`, and `gi.repository.GLib` at import time. Every test in this file references the old `MprisService` API surface (`Raise`, `PlayPause`, `Get`, `GetAll`, `PropertiesChanged`, etc.) that the no-op stub no longer exposes. Plan 35-05 Task 2 should rewrite this file from scratch as ~6 tests against the stub:
   - constructor accepts `(window)` and `(None)`
   - constructor logs the "stub active" debug line
   - `emit_properties_changed` accepts arbitrary dict and returns None
   - `emit_properties_changed` accepts a dict containing dbus-typed values without raising (proves main_window.py's local `import dbus` lines remain compatible until Phase 36 deletes them)
   - `_build_metadata` returns `{}`
   - module has no `dbus`/`gi`/`PySide6` imports (grep test, mirroring acceptance criterion)

2. **Any pre-existing yt-dlp subprocess mocks** — none found in the current `tests/` tree (`tests/test_yt_import.py` does not exist; `tests/test_aa_url_detection.py` does not call into `yt_import`). Verified via `ls tests/test_yt_import*` (only the new `test_yt_import_library.py` exists). No additional handoff needed for this category.

## Followups Tracked

- **Plan 35-04 unblocked:** `paths.cookies_path()` is in use, `mpris.py` no longer imports `dbus.mainloop.glib` (which would have polluted the GLib main loop the player rewrite needs to attach to), and `yt_import.py` no longer holds a subprocess reference that the future `_popen.py` helper would have to coordinate with.
- **Phase 36** still needs to delete the `import dbus` lines inside `main_window.py` (lines 701, 774, 808, 964) when it deletes GTK UI entirely. Until then, the stub's permissive `emit_properties_changed(props: dict)` signature accepts the dbus-typed values without raising.

## Self-Check: PASSED

- `musicstreamer/yt_import.py` → exists, contains `yt_dlp.YoutubeDL` and `paths.cookies_path()`
- `musicstreamer/mpris.py` → exists, 38 lines, contains `class MprisService` and `_log.debug` stub line
- `tests/test_yt_import_library.py` → exists, 8 tests pass
- Commits resolve in `git log`:
  - `2e8f5d4` test(35-03): add failing tests for yt_import library-API port
  - `8fe136b` feat(35-03): port yt_import.scan_playlist to yt_dlp library API
  - `133018e` feat(35-03): replace mpris.py with no-op stub
