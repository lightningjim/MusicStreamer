---
phase: 34-implement-deferred-items-from-phase-33
plan: 01
subsystem: tests
tags: [tests, twitch, streamlink, deferred-cleanup]
requires: []
provides:
  - Deterministic no-token-branch twitch streamlink args test
affects:
  - tests/test_twitch_playback.py
tech-stack:
  added: []
  patterns:
    - "monkeypatch module-level path constant to force except OSError branch"
key-files:
  created: []
  modified:
    - tests/test_twitch_playback.py
    - .planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md
decisions:
  - Forced no-token branch via monkeypatching TWITCH_TOKEN_PATH to nonexistent tmp_path file (D-01)
  - Preserved exact-list assertion unchanged (D-02)
  - Did not add token-present branch test (D-03, out of scope)
metrics:
  duration: ~4 min
  completed: 2026-04-10
---

# Phase 34 Plan 01: Fix Twitch Test and Cleanup Summary

Monkeypatched `musicstreamer.player.TWITCH_TOKEN_PATH` in `test_streamlink_called_with_correct_args` to deterministically hit the no-token branch of `_play_twitch`, fixing a dev-environment failure introduced by phase 32's OAuth header prepending; also annotated the stale cookies entry in phase 33's deferred-items.md as already resolved in commit b3e066b.

## What Was Built

- **Task 1:** Added `tmp_path`/`monkeypatch` fixtures and a single `monkeypatch.setattr` call to `tests/test_twitch_playback.py::test_streamlink_called_with_correct_args`. Points `musicstreamer.player.TWITCH_TOKEN_PATH` at a nonexistent file inside `tmp_path` so `open()` raises `FileNotFoundError`, which hits the `except OSError: pass` branch at `player.py:329-330` and falls through to the bare `["streamlink", "--stream-url", url, "best"]` command. The exact-list assertion is byte-for-byte unchanged.
- **Task 2:** Annotated the cookies bullet in `.planning/phases/33-.../deferred-items.md` with `**RESOLVED in 33-02 (commit b3e066b):**` prefix and a trailing sentence noting the widening of the monotonic iterator. Also removed the stray `/gs` prefix that had corrupted the header line.
- **Task 3:** Verified full regression suite for `tests/test_twitch_playback.py` and `tests/test_cookies.py` — 28/28 passing.

## Before/After: Patched Test

**Before (signature + body start):**
```python
def test_streamlink_called_with_correct_args():
    """_play_twitch calls subprocess.run with args ["streamlink", "--stream-url", url, "best"],
    capture_output=True, text=True."""
    p = make_player()
```

**After:**
```python
def test_streamlink_called_with_correct_args(tmp_path, monkeypatch):
    """_play_twitch calls subprocess.run with args ["streamlink", "--stream-url", url, "best"],
    capture_output=True, text=True."""
    # Force no-token branch: point TWITCH_TOKEN_PATH at a file that does not exist
    # so open() raises FileNotFoundError (subclass of OSError) and _play_twitch
    # falls through to the bare `["streamlink", "--stream-url", url, "best"]` cmd.
    # Without this, a dev-local ~/.local/share/musicstreamer/twitch-token.txt would
    # cause streamlink to be invoked with --twitch-api-header (phase 32 behavior).
    monkeypatch.setattr(
        "musicstreamer.player.TWITCH_TOKEN_PATH",
        str(tmp_path / "nonexistent-twitch-token.txt"),
    )
    p = make_player()
```

Line 139 assertion (`assert call_args[0][0] == ["streamlink", "--stream-url", url, "best"]`) is unchanged.

## Before/After: deferred-items.md Cookies Bullet

**Before:**
```
/gs# Deferred items — Phase 33

- `tests/test_twitch_playback.py::test_streamlink_called_with_correct_args` is pre-existing failure ...
- `tests/test_cookies.py::test_mpv_retry_without_cookies_on_fast_exit` fails after 33-01 ... Should be fixed as a follow-up test-fixture patch.
```

**After:**
```
# Deferred items — Phase 33

- `tests/test_twitch_playback.py::test_streamlink_called_with_correct_args` is pre-existing failure ... (unchanged)
- **RESOLVED in 33-02 (commit b3e066b):** `tests/test_cookies.py::test_mpv_retry_without_cookies_on_fast_exit` fails after 33-01 ... Fixed in commit b3e066b by widening the monotonic iterator to `itertools.count(start=0.0, step=1.0)`.
```

Both bullets preserved; stray `/gs` prefix removed; resolution annotation added.

## Verification

```
$ uv run pytest tests/test_twitch_playback.py tests/test_cookies.py -v
============================= test session starts ==============================
platform linux -- Python 3.13.7, pytest-9.0.2, pluggy-1.6.0
collecting ... collected 28 items

tests/test_twitch_playback.py::test_twitch_url_detected PASSED           [  3%]
tests/test_twitch_playback.py::test_non_twitch_url_not_routed PASSED     [  7%]
tests/test_twitch_playback.py::test_streamlink_called_with_correct_args PASSED [ 10%]
tests/test_twitch_playback.py::test_streamlink_env_includes_local_bin PASSED [ 14%]
tests/test_twitch_playback.py::test_live_channel_calls_set_uri PASSED    [ 17%]
tests/test_twitch_playback.py::test_offline_channel_calls_on_offline PASSED [ 21%]
tests/test_twitch_playback.py::test_non_offline_error_calls_try_next PASSED [ 25%]
tests/test_twitch_playback.py::test_gst_error_twitch_re_resolves PASSED  [ 28%]
tests/test_twitch_playback.py::test_re_resolve_bounded_to_one PASSED     [ 32%]
tests/test_twitch_playback.py::test_failover_timer_not_armed_for_twitch PASSED [ 35%]
tests/test_twitch_playback.py::test_resolve_counter_resets_on_station_change PASSED [ 39%]
tests/test_cookies.py::test_cookie_path_constant PASSED                  [ 42%]
tests/test_cookies.py::test_ytdlp_no_cookies_from_browser_always_when_file_exists PASSED [ 46%]
tests/test_cookies.py::test_ytdlp_no_cookies_from_browser_always_when_file_absent PASSED [ 50%]
tests/test_cookies.py::test_ytdlp_uses_cookies_when_file_exists PASSED   [ 53%]
tests/test_cookies.py::test_ytdlp_no_cookies_flag_when_absent PASSED     [ 57%]
tests/test_cookies.py::test_mpv_uses_cookies_when_file_exists PASSED     [ 60%]
tests/test_cookies.py::test_mpv_no_cookies_when_absent PASSED            [ 64%]
tests/test_cookies.py::test_clear_removes_cookies_file PASSED            [ 67%]
tests/test_cookies.py::test_clear_returns_false_when_absent PASSED       [ 71%]
tests/test_cookies.py::test_ytdlp_uses_temp_cookie_copy PASSED           [ 75%]
tests/test_cookies.py::test_ytdlp_cleans_up_temp_cookie PASSED           [ 78%]
tests/test_cookies.py::test_ytdlp_fallback_no_cookies_on_copy_failure PASSED [ 82%]
tests/test_cookies.py::test_mpv_uses_temp_cookie_copy PASSED             [ 85%]
tests/test_cookies.py::test_mpv_cleans_up_temp_cookie_on_stop PASSED     [ 89%]
tests/test_cookies.py::test_mpv_retry_without_cookies_on_fast_exit PASSED [ 92%]
tests/test_cookies.py::test_mpv_no_retry_on_slow_exit PASSED             [ 96%]
tests/test_cookies.py::test_mpv_fallback_no_cookies_on_copy_failure PASSED [100%]

============================== 28 passed in 0.09s ==============================
```

**Production code untouched:** `git diff --stat musicstreamer/player.py` → empty.

## Deviations from Plan

None - plan executed exactly as written.

## Commits

- `bf6c655` test(34-01): force no-token branch in twitch streamlink args test
- `cb96950` docs(34-01): annotate phase-33 cookies deferred item as resolved

## Self-Check: PASSED

- tests/test_twitch_playback.py — modified, verified via grep
- .planning/phases/33-.../deferred-items.md — annotated, verified via grep
- Commits bf6c655 and cb96950 present in `git log`
- musicstreamer/player.py unchanged (`git diff --stat` empty)
- 28/28 tests passing
