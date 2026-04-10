# Plan 33-02 Summary

**Phase:** 33-fix-yt-video-playback-delay-until-all-streams-failed-toast
**Plan:** 02 — Connecting toast + regression + UAT
**Completed:** 2026-04-10
**Status:** ✓ Complete

## What Was Built

- `main_window.py:968` — `self._show_toast("Connecting\u2026", timeout=4)` added before `self.player.play(st, ...)` in `_on_play`. Fires on every station click regardless of stream type.
- `main_window.py:1045` — same toast added before `self.player.play_stream(...)` in `_on_stream_picker_row_activated` so the manual stream picker also shows connecting feedback.
- `player.py:_open_mpv_log` — new diagnostic helper that opens `~/.local/share/musicstreamer/mpv.log` in append mode and writes a header (`===== <timestamp> [initial|cookie-retry] <url> =====`) before each mpv subprocess. Both the initial mpv launch and the cookie-retry path now pipe `stdout` and `stderr` to this log file instead of `DEVNULL`. Added during UAT to diagnose a YT failure that turned out to resolve on re-attempt.

## Tests

- Full suite: **264 passed**, 1 pre-existing twitch test failure (Phase 32 `--twitch-api-header` staleness, logged in `deferred-items.md`, not a Phase 33 regression).
- Player-related tests: **38 passed** after all Plan 33-02 changes (`test_cookies.py`, `test_player_failover.py`, `test_player_buffer.py`).
- Regression fix: `tests/test_cookies.py::test_mpv_retry_without_cookies_on_fast_exit` monkeypatch iterator extended from `iter([0.0, 1.0])` to `itertools.count(0.0, 1.0)` — the new `time.monotonic()` calls inside `_yt_poll_cb` were exhausting the fixed iterator.

## Decision Coverage

| Decision | Status |
|----------|--------|
| D-04 (Connecting toast on every play/play_stream, all stream types) | ✓ main_window.py:968 + :1045 |
| D-05 (4s auto-dismiss, stacking overlap accepted) | ✓ `timeout=4` on both toasts |
| D-06 (supersedes Phase 28 silent-first without removing failover toasts) | ✓ `_is_first_attempt` suppression preserved in player.py |

## UAT Results

| Step | Result |
|------|--------|
| HTTP station connecting toast + audio | ✓ passed |
| YouTube station connecting toast + audio | ✓ passed (after initial failure that resolved on re-attempt) |
| Twitch station still works | ✓ passed |
| Stream picker connecting toast | Covered by code review (same helper as main play) |

## Commits

- `e05bbd3` — feat(33-02): add Connecting toast at play/play_stream call sites (FIX-07d)
- `b3e066b` — fix(33-02): extend test_cookies monotonic iterator for YT watchdog
- `a58924c` — feat(33): log mpv stdout/stderr to ~/.local/share/musicstreamer/mpv.log

## Key Files

**Modified:**
- `musicstreamer/ui/main_window.py` (+2 lines at 968 and 1045)
- `musicstreamer/player.py` (+17 lines: `_open_mpv_log` helper + two log handle wires)
- `tests/test_cookies.py` (+2 lines: itertools.count iterator)

**Created:**
- `.planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md`

## Deviations

- **mpv.log diagnostic logging** was not in the original plan. Added mid-UAT when the user reported a YT failure we couldn't diagnose because `stderr=DEVNULL` was swallowing output. Kept as a permanent diagnostic aid at `~/.local/share/musicstreamer/mpv.log` (append mode). File will grow over time — future phase could add rotation if it becomes a concern.
- **Deferred twitch test** (`test_streamlink_called_with_correct_args`): confirmed pre-existing from Phase 32 by checking against commit `740f8fb` — the test predates the `--twitch-api-header` addition and does not monkeypatch `TWITCH_TOKEN_PATH`. Out of scope for Phase 33; noted in `deferred-items.md`.
