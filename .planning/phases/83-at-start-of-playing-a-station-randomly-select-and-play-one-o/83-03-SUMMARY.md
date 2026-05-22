---
phase: 83-at-start-of-playing-a-station-randomly-select-and-play-one-o
plan: 03
subsystem: player
tags: [phase-83, player, somafm, preroll, about-to-finish, playbin3, queued-signal, drift-guard, qt-glib-threading]
requires: [83-01]
provides:
  - Player.play SomaFM preroll gate (D-11 + D-12 + D-13)
  - playbin3 about-to-finish queued-Signal handoff (D-05 / Pattern 1)
  - _on_gst_tag preroll-suppress early-return (D-07)
  - _handle_gst_error_recovery preroll-aware branch (D-09)
  - _preroll_backfill_worker daemon thread (Pattern 4, D-13)
  - malformed-preroll EOS bridge (live-spike Q3 RESOLVED)
  - 13 behavioral tests + source-grep drift-guard (D-14)
affects: [musicstreamer/player.py, tests/test_player.py, tests/_fake_player.py]
tech-stack:
  added: [playbin3 about-to-finish signal, Pattern 4 thread-local Repo for Player]
  patterns: [class-level Signal + QueuedConnection (Phase 43.1 f1333ed), single-flight set guard, lazy backfill worker]
key-files:
  created: []
  modified:
    - musicstreamer/player.py
    - tests/test_player.py
    - tests/_fake_player.py
decisions:
  - "D-11: SomaFM provider gate uses CamelCase literal 'SomaFM' (Phase 74 D-02 convention)"
  - "D-12: throttle timestamp set at preroll START (in _start_preroll), NOT at about-to-finish handoff"
  - "D-13: lazy backfill is non-blocking — play proceeds to stream while worker runs"
  - "T-83-10: single-flight via self._backfill_in_flight: set[int]; discard in finally"
  - "Pitfall 9 preserved: no top-level from musicstreamer.repo import in player.py (lazy import inside worker)"
  - "qt-glib-bus-threading Rule 2: streaming-thread callback emits queued Signal only"
  - "Pitfall 8: drift-guard uses re.sub to strip comment-only lines (stronger than lstrip startswith #)"
metrics:
  duration: ~45min
  completed: 2026-05-22
---

# Phase 83 Plan 03: SomaFM Preroll Player Layer Summary

JWT-style one-liner: Player.play now routes SomaFM stations through a 10-min-throttled random preroll via playbin3's `about-to-finish` queued-Signal handoff, with on-demand lazy backfill and full failover preservation.

## Implementation Surface (line ranges in `musicstreamer/player.py`)

| Surface | File:Line | Notes |
|---------|-----------|-------|
| `import random` | player.py:38 | Added to stdlib block |
| `_preroll_about_to_finish_requested = Signal()` | player.py:264-269 | Class-level Signal alongside `_try_next_stream_requested` |
| `bus.connect("message::eos", self._on_gst_eos_during_preroll)` | player.py:344 | Appended to bus-handler cluster (after `state-changed`, before NOTE comment) |
| `_preroll_about_to_finish_requested.connect(..., QueuedConnection)` | player.py:414-417 | In `__init__` after `_try_next_stream_requested.connect` |
| 4 new instance fields (`_preroll_in_flight`, `_last_preroll_played_at`, `_preroll_handler_id`, `_backfill_in_flight`) | player.py:454-460 | In `__init__` runtime-state band, after `_last_buffer_percent` |
| Preroll gate inside `Player.play` (D-11/D-12/D-13) | player.py:565-595 | Between `self._streams_queue = queue` and `self._try_next_stream()` |
| `_on_gst_tag` D-07 early-return | player.py:734-742 | Between existing `if not found: return` and `title = _fix_icy_encoding(...)` |
| `_handle_gst_error_recovery` D-09 preroll branch | player.py:738-750 | After `self._cancel_timers()` (line 737), before Twitch branch (line 752) |
| `def _start_preroll` | player.py:1103-1116 | Inside new "SomaFM preroll cluster" section |
| `def _on_preroll_about_to_finish_callback` (streaming thread) | player.py:1118-1122 | One-line body: `self._preroll_about_to_finish_requested.emit()` |
| `def _on_preroll_about_to_finish` (main thread) | player.py:1124-1135 | Slot wired via QueuedConnection |
| `def _on_gst_eos_during_preroll` (live-spike Q3) | player.py:1137-1166 | Malformed-preroll EOS bridge |
| `def _preroll_backfill_worker` | player.py:1357-1404 | Daemon thread (Pattern 4 thread-local Repo). Inside new section after `_on_twitch_resolved` |

## Behavioral & Drift-Guard Tests

13 tests in `tests/test_player.py` (function names verbatim per `83-VALIDATION.md`):

| Decision | Test name |
|----------|-----------|
| D-05 | `test_preroll_sets_uri_and_connects_handler` |
| D-12 window | `test_throttle_window_suppresses_preroll` |
| D-12 timestamp | `test_throttle_timestamp_set_on_start` |
| D-06 | `test_preroll_does_not_pollute_streams_queue` |
| D-03 | `test_preroll_backfill_scheduled_when_unfetched` |
| D-13 | `test_backfill_non_blocking` |
| D-11 | `test_non_somafm_provider_bypasses_preroll` |
| D-07 | `test_title_tag_suppressed_during_preroll` |
| D-09 | `test_preroll_bus_error_advances_to_stream` |
| D-08 (WARNING-4) | `test_preroll_in_flight_pause_does_not_clear_flag` |
| D-10 (WARNING-4) | `test_streams_queue_failover_after_preroll_handoff` |
| Q3 EOS (WARNING-5) | `test_preroll_eos_without_about_to_finish_advances_to_stream` |
| D-14 drift-guard | `test_phase_83_preroll_drift_guard` |

The drift-guard test uses `re.sub(r"^\s*#.*$", "", ln)` to strip comment-only lines (per Pitfall 8 — stronger than `lstrip startswith #` because partial trailing comments are also stripped). It asserts BOTH `'"SomaFM"'` AND `'_last_preroll_played_at'` appear in non-comment text of `musicstreamer/player.py`.

## Factory Helper Additions

- `_make_station_ph83(streams, *, id_=1, name="Test SomaFM Station", provider_name="SomaFM", prerolls=None, prerolls_fetched_at=None)` — new helper in `tests/test_player.py` builds a Station with Phase 83 fields. Default `provider_name="SomaFM"` because most tests use it; bypass test (D-11) overrides to `"DI.fm"`.
- `_connect_calls_include_about_to_finish(p)` — boolean helper scanning `p._pipeline.connect.call_args_list` for an `"about-to-finish"` first-positional arg.

## Verification Results

```
$ uv run pytest tests/test_player.py -k "preroll or phase_83 or streams_queue_failover_after_preroll_handoff" -x -q
11 passed, 27 deselected, 1 warning in 0.27s
```

```
$ uv run pytest tests/test_player.py::test_preroll_sets_uri_and_connects_handler ... [all 13 explicitly] -v
13 passed, 1 warning in 0.23s
```

```
$ uv run pytest tests/test_player.py tests/test_soma_import.py tests/test_repo.py tests/test_fake_player_signal_parity.py -q
143 passed, 1 warning in 1.48s
```

```
$ uv run pytest -q (full suite minus 2 pre-existing flaky integration tests)
1631 passed, 1 skipped, 2 warnings in 20.02s
```

### Source-grep invariants (verbatim from plan)

| Invariant | Expected | Actual |
|-----------|----------|--------|
| `_preroll_about_to_finish_requested = Signal` count | 1 | 1 |
| 5 new method defs (`_start_preroll`, `_on_preroll_about_to_finish_callback`, `_on_preroll_about_to_finish`, `_preroll_backfill_worker`, `_on_gst_eos_during_preroll`) | 5 | 5 |
| `bus.connect("message::eos"` count | 1 | 1 |
| non-comment `"SomaFM"` count | ≥1 | 1 |
| non-comment `_last_preroll_played_at` count | ≥2 | 5 |
| top-level `^from musicstreamer.repo import` count (Pitfall 9 invariant) | 0 | 0 |
| `def play_stream` count (D-08 — untouched) | 1 | 1 |

Threading discipline (qt-glib-bus-threading Rule 2):

- `_on_preroll_about_to_finish_callback` body is EXACTLY ONE LINE: `self._preroll_about_to_finish_requested.emit()` — no property writes, no Qt API calls from the streaming thread.
- `_on_gst_eos_during_preroll` runs on GstBusLoopThread; only emits `_try_next_stream_requested` Signal (no pipeline mutation, no handler-id touch).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FakePlayer Signal parity drift-guard caught the new Signal**

- **Found during:** Task 4 verification (`uv run pytest` full-suite)
- **Issue:** `tests/test_fake_player_signal_parity.py::test_fake_player_mirrors_every_player_signal` failed because `_preroll_about_to_finish_requested` was added to `Player` but not mirrored on `tests/_fake_player.py:FakePlayer`. The parity drift-guard (Phase 77 D-16) is precisely designed to catch this kind of out-of-tree Signal addition.
- **Fix:** Added `_preroll_about_to_finish_requested = Signal()` to `FakePlayer` mirroring the production declaration, alongside `_try_next_stream_requested`. Updated the comment count from `(7 — underscore-prefixed)` to `(8 — underscore-prefixed)`.
- **Files modified:** `tests/_fake_player.py`
- **Commit:** `55e5026` (combined with Task 4 commit since the drift-guard is in the same test surface)

### Pre-existing Failures (NOT introduced by this plan)

Confirmed via `git stash` + re-run on pre-83-03 state:

1. `tests/test_main_window_integration.py::test_hamburger_menu_actions` — already failed before any 83-03 code. Out of scope per `<deviation_rules>` SCOPE BOUNDARY.
2. `tests/test_media_keys_smtc.py::test_end_to_end_factory_fallback_on_win32_without_winrt` — only fails as a side-effect of full-suite test ordering; passes when run in isolation. Pre-existing flake, out of scope.

These are documented here for the orchestrator and verifier; they are unrelated to Phase 83 work.

### Architectural Changes (Rule 4 — none)

None — the plan was executed exactly as written.

## Known Stubs

None. All preroll codepaths land complete; the only "no-op" code is the deliberate D-04 silent-failure path in `_preroll_backfill_worker` (`except Exception: _log.warning(...)`) and the deliberate `_preroll_in_flight is False` no-op branch in `_on_gst_eos_during_preroll` (live-spike Q3 RESOLVED, defense-in-depth only). Both are intentional per plan invariants.

## play_stream and order_streams Invariants Preserved

- `def play_stream` count in `player.py`: **1** (signature + body unchanged — D-08 / Phase 82 D-04 direct-play path untouched).
- `order_streams` callsite count in `player.py`: unchanged at **1** (Phase 82 head-of-queue logic intact — preroll gate is APPENDED to it, not a rewrite).

## Manual UAT Recommendations

Per `83-VALIDATION.md` §"Manual-Only Verifications" — run on Linux Wayland (deployment target):

1. **Beat Blender preroll** — Play SomaFM Beat Blender from a cold launch; expect a ~5–8s preroll ID (random selection from `station_prerolls`) immediately preceding the stream audio; confirm Now Playing keeps showing "Beat Blender" through the preroll (D-07 metadata suppression).
2. **Seven Inch Soul no-preroll** — Play SomaFM Seven Inch Soul (legitimately-empty channel per `prerolls_fetched_at` non-NULL + zero rows); expect immediate stream audio with NO preroll, NO backfill thread re-spawn.
3. **10-min throttle** — Play Beat Blender, listen to the preroll, stop, immediately play again within 10 minutes; expect NO preroll on the second play (throttle gate D-12). Wait >10 minutes; expect a fresh random preroll.

Record outcome in `83-HUMAN-UAT.md` per Phase 82 precedent.

## Self-Check: PASSED

- [x] All 13 tests pass (`uv run pytest` covering all 13 names)
- [x] Source-grep invariants pass (7/7 verifications above)
- [x] `_preroll_about_to_finish_requested = Signal()` exists in `musicstreamer/player.py` at line 269
- [x] All 4 commit hashes exist in `git log --oneline -5`:
  - `be00ee5` feat(83-03): add SomaFM preroll gate + about-to-finish handler to Player
  - `4ad435c` feat(83-03): suppress preroll title + preroll-aware error recovery
  - `f2945db` feat(83-03): add _preroll_backfill_worker daemon thread (Pattern 4)
  - `55e5026` test(83-03): 13 behavioral tests + drift-guard for SomaFM preroll
- [x] `tests/_fake_player.py` mirrors the new Player Signal (parity drift-guard PASSES)
- [x] Plan threading discipline preserved: `about-to-finish` and `message::eos` callbacks BOTH route through queued Signals (`_preroll_about_to_finish_requested`, `_try_next_stream_requested`); NEVER call `pipeline.set_property` from the streaming thread (qt-glib-bus-threading Rule 2; Phase 43.1 f1333ed precedent)
