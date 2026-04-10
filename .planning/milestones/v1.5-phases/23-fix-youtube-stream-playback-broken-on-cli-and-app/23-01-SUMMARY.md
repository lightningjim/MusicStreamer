---
phase: 23-fix-youtube-stream-playback-broken-on-cli-and-app
plan: "01"
subsystem: playback
tags: [youtube, cookies, tempfile, mpv, yt-dlp, tdd]
dependency_graph:
  requires: []
  provides: [temp-cookie-copy-for-ytdlp, temp-cookie-copy-for-mpv, retry-without-cookies]
  affects: [musicstreamer/player.py, musicstreamer/yt_import.py]
tech_stack:
  added: [tempfile, shutil]
  patterns: [mkstemp-copy-unlink, try-finally-cleanup, fast-exit-retry]
key_files:
  created: [tests/test_cookies.py (section 5 — 8 new tests)]
  modified:
    - musicstreamer/player.py
    - musicstreamer/yt_import.py
    - tests/test_cookies.py
decisions:
  - "Use mkstemp + shutil.copy2 for temp cookie copies — O_EXCL safety, 0o600 perms, no race"
  - "time.sleep(2) + poll() for fast-exit retry — simple and avoids threading complexity"
  - "OSError fallback to no-cookies — keep playback working even if /tmp is full"
metrics:
  duration: "~12 min"
  completed: "2026-04-07T12:43:19Z"
  tasks_completed: 2
  files_changed: 3
---

# Phase 23 Plan 01: Temp Cookie Copy for yt-dlp and mpv Summary

**One-liner:** Both yt-dlp and mpv now receive per-invocation temp copies of cookies.txt via mkstemp, with cleanup in finally/stop and retry-without-cookies on fast mpv exit.

## What Was Built

Fixed YouTube stream playback regression where yt-dlp's `--cookies` flag both reads AND writes the cookie file, corrupting the user's clean imported cookies with Chrome-epoch timestamps. Now both `scan_playlist` (yt-dlp) and `_play_youtube` (mpv) make a temp copy via `tempfile.mkstemp` + `shutil.copy2`, pass the temp path to the subprocess, and delete it when done.

### Key behaviors implemented

- `yt_import.scan_playlist`: mkstemp temp copy → `--cookies <tmp>` → cleanup in `finally` block
- `player._play_youtube`: mkstemp temp copy → `--ytdl-raw-options=cookies=<tmp>` → stored in `self._yt_cookie_tmp`
- `player._cleanup_cookie_tmp()`: unlinks `_yt_cookie_tmp` if it exists, resets to None
- `player._stop_yt_proc()`: calls `_cleanup_cookie_tmp()` after terminating process
- Copy failure (OSError) → fallback to no-cookies invocation in both files
- Fast-exit retry: if mpv exits within 2s with cookies, retries without cookies (corrupted file guard)

## Tests

8 new tests added in `tests/test_cookies.py` section 5 (Phase 23):

| Test | Behavior verified |
|------|------------------|
| `test_ytdlp_uses_temp_cookie_copy` | Path passed to --cookies differs from COOKIES_PATH; original unchanged |
| `test_ytdlp_cleans_up_temp_cookie` | Temp file absent after scan_playlist returns |
| `test_ytdlp_fallback_no_cookies_on_copy_failure` | --cookies absent when shutil.copy2 raises OSError |
| `test_mpv_uses_temp_cookie_copy` | Path in --ytdl-raw-options=cookies= differs from COOKIES_PATH; original unchanged |
| `test_mpv_cleans_up_temp_cookie_on_stop` | Temp file absent after _stop_yt_proc() |
| `test_mpv_retry_without_cookies_on_fast_exit` | Popen called twice; second call has no cookies flag |
| `test_mpv_no_retry_on_slow_exit` | Popen called once when poll() returns None after sleep |
| `test_mpv_fallback_no_cookies_on_copy_failure` | --ytdl-raw-options=cookies= absent when copy fails |

Full suite: 193 tests passing (up from 153 at phase start — 40 added across v1.5 phases).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated stale section 2/3 tests that asserted original COOKIES_PATH was passed directly**
- **Found during:** Task 2 GREEN phase
- **Issue:** `test_ytdlp_uses_cookies_when_file_exists` asserted `cmd[idx+1] == str(cookies_file)` (original path). `test_mpv_uses_cookies_when_file_exists` asserted exact flag with original path. Both broke once temp-copy was implemented.
- **Fix:** Updated both tests to assert `--cookies` / `--ytdl-raw-options=cookies=` is present (any path), since temp-copy behavior is now fully tested in section 5. Also added `time.sleep` mock to mpv tests to prevent real 2s delay.
- **Files modified:** `tests/test_cookies.py`
- **Commit:** a0acfa3

## Known Stubs

None.

## Threat Flags

None — threat model was pre-assessed in plan frontmatter. mkstemp creates files with 0o600 perms by default; unlinked after use (T-23-01 mitigated).

## Self-Check: PASSED

- musicstreamer/player.py: FOUND
- musicstreamer/yt_import.py: FOUND
- tests/test_cookies.py: FOUND
- Commit 9ff7095 (RED phase): FOUND
- Commit a0acfa3 (GREEN phase): FOUND
