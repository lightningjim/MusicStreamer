---
phase: 33
plan: 01
subsystem: player
tags: [bugfix, youtube, failover, timer, FIX-07]
dependency-graph:
  requires: [player.py, constants.py, tests/test_player_failover.py]
  provides:
    - "Player._yt_attempt_start_ts state field"
    - "15s YT minimum wait window gate in _yt_poll_cb"
    - "YT_MIN_WAIT_S = 15 constant"
    - "FIX-07 requirement definition"
  affects: [Player.play, Player._cancel_failover_timer, Player._play_youtube]
tech-stack:
  added: []
  patterns:
    - "time.monotonic() gate on existing GLib.timeout_add poll loop"
key-files:
  created:
    - .planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md
  modified:
    - .planning/REQUIREMENTS.md
    - musicstreamer/constants.py
    - musicstreamer/player.py
    - tests/test_player_failover.py
decisions:
  - "Monotonic-timestamp gate on existing 1s poll loop instead of a second GLib.timeout_add(15000) guard — less state, less leak surface"
  - "Cookie-retry substitution re-seeds _yt_attempt_start_ts so replacement mpv gets a full 15s (D-07)"
  - "Alive-at-window-close clears poll timer as success signal (D-03)"
metrics:
  duration: "~8 minutes"
  completed: 2026-04-10
  tasks: 2
  files_touched: 5
  commits: 2
---

# Phase 33 Plan 01: 15s YouTube minimum wait window Summary

Added FIX-07 requirement plus the core `time.monotonic()` gate in `_yt_poll_cb` that defers YT failover until `YT_MIN_WAIT_S` (15s) has elapsed since the current mpv process was launched; seeded in `_play_youtube` and re-seeded in the cookie-retry substitution path.

## What Changed

**`.planning/REQUIREMENTS.md`**
- Added FIX-07 under Bug Fixes with sub-criteria (a)–(e) covering the 15s gate, alive-at-window-close clearing, cookie-retry re-seed, connecting toast (deferred to Plan 02), and cancel cleanup.
- Added FIX-07 row to the Traceability table.
- Bumped coverage counts 52 → 53.
- Updated `Last updated` footer to `2026-04-10 after Phase 33 planning`.

**`musicstreamer/constants.py`**
- Added `YT_MIN_WAIT_S = 15` with Phase 33 / FIX-07 / D-01 comment immediately after `BUFFER_SIZE_BYTES`.

**`musicstreamer/player.py`** (5 edits, 0 removals)
1. Import `YT_MIN_WAIT_S` from constants.
2. `__init__`: `self._yt_attempt_start_ts: float | None = None` (alongside `_is_first_attempt`).
3. `_cancel_failover_timer`: appends `self._yt_attempt_start_ts = None` so every cancel path clears it.
4. `_yt_poll_cb`: full rewrite of the poll logic to a 4-branch decision:
   - `exit_code is None` + `elapsed >= YT_MIN_WAIT_S` → return False (success, mpv is alive at window close).
   - `exit_code is None` + `elapsed < YT_MIN_WAIT_S` → return True (keep polling).
   - exited + `elapsed < YT_MIN_WAIT_S` → return True (keep polling — sit idle until the window closes even though mpv is dead).
   - exited + `elapsed >= YT_MIN_WAIT_S` → clear state, call `_try_next_stream()` if nonzero, return False.
5. `_play_youtube`: seeds `self._yt_attempt_start_ts = time.monotonic()` immediately after the main `Popen`; the nested `_check_cookie_retry` re-seeds after its replacement `Popen` so the cookies-less mpv gets its own 15s window.

**`tests/test_player_failover.py`** (4 new pytest functions at end of file)
- `test_yt_premature_exit_does_not_failover_before_15s` — mpv exits at 1s, asserts poll returns True, stream unchanged, timer still live.
- `test_yt_alive_at_window_close_succeeds` — mpv still running at 15.1s, asserts poll returns False, state cleared.
- `test_cookie_retry_reseeds_yt_window` — invokes the 2000ms cookie-retry callback directly, asserts `_yt_attempt_start_ts == 2.0` (not 0.0).
- `test_cancel_clears_yt_attempt_ts` — sets mid-attempt state manually, calls `_cancel_failover_timer`, asserts both cleared.

## How It Works

`_yt_poll_cb` is called every 1000ms by `GLib.timeout_add`. Before any failover trigger, it now computes `elapsed = time.monotonic() - self._yt_attempt_start_ts` and uses that to gate `_try_next_stream()`. The function's return value alone drives GLib's repeat/stop semantics — the elapsed check never short-circuits the timer loop unless either (a) mpv is alive at window close (success) or (b) mpv has exited AND the window has closed (terminal).

The cookie-retry path was the subtle case: it replaces `self._yt_proc` at t≈2s with a cookies-less Popen, and without re-seeding it would inherit the original 0.0s start and only get ~13s. Re-seeding inside `_check_cookie_retry` matches D-07's intent — "a YT stream gets ~15s of mpv runtime to prove itself, regardless of cookie-retry substitution."

## Deviations from Plan

**None** — the plan executed exactly as written with one minor test-setup addition:

**[Process - Test fixture]** `test_cookie_retry_reseeds_yt_window` required an additional `patch("musicstreamer.player.os.unlink")` because `_cleanup_cookie_tmp` runs inside `_check_cookie_retry` and tries to `os.unlink("/tmp/fake_cookies.txt")` (a non-existent path used by the mock). Not a plan deviation — just a test-patching detail the plan didn't enumerate. Added in Task 1 before commit.

## Verification Results

| Test suite | Count | Result |
|------------|-------|--------|
| `tests/test_player_failover.py` | 17 (13 pre-existing + 4 new) | all pass |
| `tests/test_player_buffer.py` | 4 | all pass |
| `tests/test_twitch_playback.py` | 10 (1 deselected — pre-existing failure) | all selected pass |

Acceptance greps:
- `_yt_attempt_start_ts` in player.py: 8 occurrences (>=5 required)
- `YT_MIN_WAIT_S` in player.py: 4 occurrences (>=2 required)
- `time.monotonic` in player.py: 3 occurrences (>=2 required)
- `FIX-07` in REQUIREMENTS.md: present in Bug Fixes and Traceability table
- `YT_MIN_WAIT_S = 15` in constants.py: 1 occurrence
- All 4 FIX-07 test functions present and green

## Deferred Issues

**`tests/test_twitch_playback.py::test_streamlink_called_with_correct_args`** fails on master before any Phase 33 edits. Root cause: test expects `["streamlink", "--stream-url", url, "best"]` argv, but `_play_twitch` now passes `--twitch-api-header` when a token exists. Unrelated to FIX-07 and out of scope per GSD Rule: "Only auto-fix issues DIRECTLY caused by the current task's changes." Logged to `deferred-items.md`.

## Known Stubs

None. FIX-07 (a)(b)(c)(e) fully wired. FIX-07 (d) — the "Connecting…" Adw.Toast on every play() call — is intentionally deferred to Plan 33-02 (`main_window.py` edits) per the phase split.

## Commits

- `7ade3e4` — test(33-01): add FIX-07 requirement, YT_MIN_WAIT_S constant, 4 failing tests
- `a23a4a6` — feat(33-01): add 15s YT minimum wait window before failover (FIX-07)

## Self-Check: PASSED

- `.planning/REQUIREMENTS.md`: FOUND (FIX-07 present)
- `musicstreamer/constants.py`: FOUND (YT_MIN_WAIT_S = 15 present)
- `musicstreamer/player.py`: FOUND (gate wired)
- `tests/test_player_failover.py`: FOUND (4 new tests present and passing)
- `.planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md`: FOUND
- Commit `7ade3e4`: FOUND in `git log`
- Commit `a23a4a6`: FOUND in `git log`
