---
phase: 33-fix-yt-video-playback-delay-until-all-streams-failed-toast
verified: 2026-04-10T00:00:00Z
status: passed
score: 12/12 must-haves verified
overrides_applied: 0
---

# Phase 33: Fix YT Video Playback Delay Verification Report

**Phase Goal:** Fix premature YouTube failover and missing user feedback by adding a 15s hard minimum wait window for YT streams and a "Connecting…" toast on every play()/play_stream() invocation.

**Verified:** 2026-04-10
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Must-Haves)

| # | Must-Have | Status | Evidence |
|---|-----------|--------|----------|
| 1 | FIX-07 marked complete in REQUIREMENTS.md | VERIFIED | `.planning/REQUIREMENTS.md:18` — `- [x] **FIX-07**:` with sub-criteria (a)–(e); traceability row at :157 `\| FIX-07 \| Phase 33 \| Complete \|` |
| 2 | `constants.py` defines `YT_MIN_WAIT_S = 15` | VERIFIED | `musicstreamer/constants.py:30-31` with Phase 33 / FIX-07 / D-01 comment |
| 3 | `_yt_poll_cb` gates `_try_next_stream()` on `elapsed >= YT_MIN_WAIT_S` | VERIFIED | `player.py:208-233` — 4-branch logic: alive+>=15 returns False (success), alive+<15 returns True (keep polling), exited+<15 returns True (sit idle), exited+>=15 calls `_try_next_stream()` |
| 4 | `_play_youtube` seeds `self._yt_attempt_start_ts = time.monotonic()` | VERIFIED | `player.py:281` — immediately after initial `subprocess.Popen(...)` |
| 5 | `_check_cookie_retry` re-seeds `_yt_attempt_start_ts` after replacement Popen | VERIFIED | `player.py:300` — inside nested `_check_cookie_retry`, after replacement `self._yt_proc = subprocess.Popen(cmd_no_cookies, ...)` |
| 6 | `_cancel_failover_timer` clears `_yt_attempt_start_ts` | VERIFIED | `player.py:99` — `self._yt_attempt_start_ts = None` at end of method |
| 7 | `_on_play` calls `self._show_toast("Connecting…", timeout=4)` before `player.play(...)` | VERIFIED | `main_window.py:968` — `self._show_toast("Connecting\u2026", timeout=4)` immediately precedes `self.player.play(st, ...)` at :969 |
| 8 | `_on_stream_picker_row_activated` calls same toast before `player.play_stream(...)` | VERIFIED | `main_window.py:1045` — `self._show_toast("Connecting\u2026", timeout=4)` immediately precedes `self.player.play_stream(...)` at :1046 |
| 9 | 4 new tests in tests/test_player_failover.py (premature exit, alive at window, cookie reseed, cancel clears) | VERIFIED | `test_player_failover.py:384, 426, 465, 514` — all 4 test functions present with correct names and assertions |
| 10 | test_cookies.py monotonic iterator fix (itertools.count) | VERIFIED | `test_cookies.py:310-312` — `import itertools; monotonic_values = itertools.count(start=0.0, step=1.0)` replaces fixed 2-value iter, addresses new time.monotonic() calls in `_yt_poll_cb` |
| 11 | Full test suite: 264 passed, 1 pre-existing twitch failure documented | VERIFIED | `33-02-SUMMARY.md` reports "264 passed, 1 pre-existing twitch test failure"; `deferred-items.md` documents `test_streamlink_called_with_correct_args` as pre-existing Phase 32 staleness, unrelated to FIX-07 |
| 12 | Manual UAT performed, YT + HTTP + Twitch confirmed working | VERIFIED | `33-02-SUMMARY.md` UAT Results table — HTTP passed, YouTube passed, Twitch passed; stream picker covered by code-review of same helper |

**Score:** 12/12 must-haves verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/constants.py` | `YT_MIN_WAIT_S = 15` | VERIFIED | Line 31 |
| `musicstreamer/player.py` | `_yt_attempt_start_ts` state + 15s gate + seed + reseed + cancel clear + `YT_MIN_WAIT_S` import | VERIFIED | Init :49, import :11, cancel :99, `_yt_poll_cb` :208-233, seed :281, reseed :300 — all 6 touch points present; also `_open_mpv_log` helper :235-249 for mpv diagnostic logging |
| `musicstreamer/ui/main_window.py` | Connecting toast at both play() and play_stream() sites | VERIFIED | :968 (play), :1045 (play_stream) |
| `tests/test_player_failover.py` | 4 new FIX-07 test functions | VERIFIED | All 4 present and structurally correct (patches `musicstreamer.player.time`, drives `mock_time.monotonic.side_effect`, captures timeout callbacks) |
| `tests/test_cookies.py` | itertools.count iterator fix | VERIFIED | :310-312 |
| `.planning/REQUIREMENTS.md` | FIX-07 defined + marked complete | VERIFIED | :18 checked, :157 Complete |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `player.py::_yt_poll_cb` | `constants.YT_MIN_WAIT_S` | `from musicstreamer.constants import ... YT_MIN_WAIT_S` at :11 | WIRED (used at :220, :226) |
| `player.py::_play_youtube` | `self._yt_attempt_start_ts` | `time.monotonic()` after Popen | WIRED (:281) |
| `player.py::_check_cookie_retry` | `self._yt_attempt_start_ts` | `time.monotonic()` after replacement Popen | WIRED (:300) |
| `player.py::_cancel_failover_timer` | `self._yt_attempt_start_ts = None` | direct assignment | WIRED (:99) |
| `main_window.py::_on_play` | `self._show_toast("Connecting…")` | precedes `self.player.play(...)` | WIRED (:968→:969) |
| `main_window.py::_on_stream_picker_row_activated` | `self._show_toast("Connecting…")` | precedes `self.player.play_stream(...)` | WIRED (:1045→:1046) |

### Data-Flow Trace (Level 4)

`_yt_attempt_start_ts` is seeded from `time.monotonic()` at two call sites (initial Popen, cookie-retry Popen) and consumed by `_yt_poll_cb` via `elapsed = time.monotonic() - self._yt_attempt_start_ts`. Cleared in `_cancel_failover_timer` and in the two terminal branches of `_yt_poll_cb`. Real data flow confirmed — no stubs.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FIX-07 (a) | 33-01 | YT mpv exit <15s does NOT call `_try_next_stream` | SATISFIED | `_yt_poll_cb` exited+<15s branch returns True without calling `_try_next_stream`; `test_yt_premature_exit_does_not_failover_before_15s` |
| FIX-07 (b) | 33-01 | YT mpv alive >=15s clears poll timer + attempt ts | SATISFIED | alive+>=15 branch :220-223; `test_yt_alive_at_window_close_succeeds` |
| FIX-07 (c) | 33-01 | Cookie-retry substitution re-seeds attempt ts | SATISFIED | `_check_cookie_retry` :300; `test_cookie_retry_reseeds_yt_window` |
| FIX-07 (d) | 33-02 | Connecting toast on every play()/play_stream() | SATISFIED | `main_window.py:968, :1045`; manual UAT confirmed |
| FIX-07 (e) | 33-01 | `_cancel_failover_timer` clears attempt ts | SATISFIED | `player.py:99`; `test_cancel_clears_yt_attempt_ts` |

### Anti-Patterns Found

None blocking. Notable observations:
- `_open_mpv_log` added mid-UAT (not in original plan) — documented as justified deviation in 33-02-SUMMARY.md. Uses append mode with no rotation; noted as potential future concern but acceptable as diagnostic aid.
- Pre-existing twitch test failure (`test_streamlink_called_with_correct_args`) — unrelated to Phase 33, documented in deferred-items.md with root cause (Phase 32 `--twitch-api-header` staleness).

### Decision Coverage (D-01 through D-07)

| Decision | Status | Evidence |
|----------|--------|----------|
| D-01: 15s hard minimum wait window | VERIFIED | `YT_MIN_WAIT_S = 15` + gate in `_yt_poll_cb` |
| D-02: Applies to every YT attempt in queue | VERIFIED | `_yt_attempt_start_ts` seeded on each `_play_youtube` call, not just first |
| D-03: Alive at 15s = success signal | VERIFIED | `_yt_poll_cb` :218-223 — exit_code is None + elapsed>=15 → return False |
| D-04: Connecting toast on every play/play_stream, all stream types | VERIFIED | Both call sites instrumented, unconditional |
| D-05: ~4s auto-dismiss | VERIFIED | `timeout=4` on both toasts |
| D-06: Preserves Phase 28 failover semantics | VERIFIED | `_is_first_attempt` suppression preserved in `_try_next_stream` :118-120 |
| D-07: Cookie-retry re-seeds window | VERIFIED | `_check_cookie_retry` :300 re-seeds after replacement Popen |

## Summary

All 12 must-haves verified. Every locked user decision (D-01 through D-07) has corresponding implementation evidence in the codebase. The 15s gate is wired correctly in the `_yt_poll_cb` state machine with full coverage of the four quadrants (alive/exited × before/after window). Connecting toast fires unconditionally at both entry points. Tests cover the gate mechanics at unit level; manual UAT confirmed end-to-end behavior for HTTP, YouTube, and Twitch stream types.

The mid-UAT `_open_mpv_log` addition is a justified scope expansion documented transparently in 33-02-SUMMARY.md — it was needed to diagnose a real UAT failure and is a benign append-only diagnostic helper.

The pre-existing twitch test failure is correctly isolated in deferred-items.md as unrelated to FIX-07.

---

*Verified: 2026-04-10*
*Verifier: Claude (gsd-verifier)*
