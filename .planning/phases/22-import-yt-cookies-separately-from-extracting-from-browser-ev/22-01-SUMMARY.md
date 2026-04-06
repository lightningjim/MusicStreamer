---
phase: 22-import-yt-cookies-separately-from-extracting-from-browser-ev
plan: "01"
subsystem: playback
tags: [cookies, yt-dlp, mpv, tdd]
dependency_graph:
  requires: []
  provides: [COOKIES_PATH constant, cookie flag injection for yt-dlp and mpv, clear_cookies utility]
  affects: [musicstreamer/constants.py, musicstreamer/yt_import.py, musicstreamer/player.py]
tech_stack:
  added: []
  patterns: [monkeypatch COOKIES_PATH in tests, subprocess.run/Popen mock inspection]
key_files:
  created:
    - tests/test_cookies.py
  modified:
    - musicstreamer/constants.py
    - musicstreamer/yt_import.py
    - musicstreamer/player.py
decisions:
  - "Placed clear_cookies() in constants.py alongside COOKIES_PATH — single source of truth for cookie file location"
  - "Used monkeypatch to override COOKIES_PATH module attribute in tests — avoids filesystem coupling to real DATA_DIR"
metrics:
  duration: "~5 min"
  completed: "2026-04-06"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 4
---

# Phase 22 Plan 01: Cookie Flag Injection Summary

**One-liner:** COOKIES_PATH constant wired into yt-dlp (--no-cookies-from-browser always; --cookies when file exists) and mpv (--ytdl-raw-options=cookies=<path> when file exists), with clear_cookies() utility and 9 TDD tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | TDD — COOKIES_PATH constant and yt-dlp/mpv flag injection | 8988f8e | musicstreamer/constants.py, musicstreamer/yt_import.py, musicstreamer/player.py, tests/test_cookies.py |

## What Was Built

- `COOKIES_PATH = os.path.join(DATA_DIR, "cookies.txt")` added to `musicstreamer/constants.py`
- `clear_cookies() -> bool` utility added to `musicstreamer/constants.py`
- `musicstreamer/yt_import.scan_playlist()` now always passes `--no-cookies-from-browser` and conditionally `--cookies COOKIES_PATH`
- `musicstreamer/player._play_youtube()` now conditionally passes `--ytdl-raw-options=cookies=<path>`
- 9 tests in `tests/test_cookies.py` covering all behaviors (RED → GREEN confirmed)
- Full suite: 193 passed, 0 failures

## Decisions Made

- `clear_cookies()` placed in `constants.py` alongside `COOKIES_PATH` — keeps cookie file management co-located with the path constant.
- Tests use `monkeypatch.setattr("musicstreamer.yt_import.COOKIES_PATH", ...)` to override the module-level attribute, allowing tmp_path-based isolation without touching the real `~/.local/share/musicstreamer/` directory.

## Deviations from Plan

None — plan executed exactly as written. 9 tests written (plan specified 7 minimum; split the "always" test into two parameterized cases for file-exists and file-absent clarity).

## Known Stubs

None.

## Threat Flags

None — `COOKIES_PATH` is a hardcoded constant derived from `DATA_DIR`, not user input. No injection vector introduced. File permissions for cookies.txt at write time are deferred to Plan 02 per T-22-02.

## Self-Check: PASSED

- `musicstreamer/constants.py` — FOUND (contains COOKIES_PATH and clear_cookies)
- `musicstreamer/yt_import.py` — FOUND (contains --no-cookies-from-browser)
- `musicstreamer/player.py` — FOUND (contains --ytdl-raw-options=cookies=)
- `tests/test_cookies.py` — FOUND (9 tests)
- Commit 8988f8e — FOUND
