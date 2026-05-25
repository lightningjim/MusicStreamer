---
phase: 82-twitch-only-station-still-tries-to-play-youtube-stream-first
plan: "02"
subsystem: player
tags: [phase-82, player, failover, preferred-stream, drift-guard, tdd]
dependency_graph:
  requires:
    - stations.preferred_stream_id column (from Plan 82-01)
    - Station.preferred_stream_id field Optional[int] = None (from Plan 82-01)
  provides:
    - Player.play() honors station.preferred_stream_id at queue head
    - preferred_stream_id beats preferred_quality kwarg (D-03 precedence)
    - Stale preferred_stream_id falls back gracefully to order_streams (RQ4)
    - Failover regression intact: queue advances through rest after picked stream fails
    - Source-grep drift-guard pinning preferred_stream_id in player.py non-comment lines
  affects:
    - musicstreamer/player.py (Player.play queue-build block rewritten)
    - tests/test_player.py (7 behavioral tests + 1 minimal RED + 1 drift-guard added)
tech_stack:
  added: []
  patterns:
    - getattr(station, 'preferred_stream_id', None) AttributeError-safe access
    - identity check (is not) for dedup — matches existing Phase 47 precedent
    - source-grep drift-guard with non-comment filter (Phase 51/55/61/63/81 idiom)
key_files:
  created: []
  modified:
    - musicstreamer/player.py
    - tests/test_player.py
decisions:
  - "getattr(station, 'preferred_stream_id', None) over direct attribute access — AttributeError safety for any non-Station object passed to play()"
  - "test_preferred_stream_id_none_falls_back_to_order_streams asserts _current_stream.id == 1 (position-sorted) not quality=='hi' — because order_streams D-07 sorts unknown-bitrate streams by position asc, not quality rank"
  - "Minimal RED test (test_preferred_stream_id_minimal_red) kept in final suite as extra coverage; Task 2 full suite adds 7 more tests"
metrics:
  duration: "~4 min"
  completed: "2026-05-22T13:15:46Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 82 Plan 02: Player preferred_stream_id Head-of-Queue Logic Summary

Rewrites the queue-build block in `Player.play()` so `station.preferred_stream_id` (set by the user via Plan 82-03's UI, written to DB by `Repo.set_preferred_stream`) is honored at the failover queue head. Adds 7 behavioral tests + 1 minimal TDD RED contract + 1 source-grep drift-guard. This is the single chokepoint fix per D-03 — all play entry points route through `Player.play()`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing test: preferred_stream_id not honored | 9193ac3 | tests/test_player.py |
| 1 (GREEN) | Rewrite Player.play() queue-build block | d98610f | musicstreamer/player.py |
| 2 (GREEN) | Add full behavioral suite + drift-guard | 363ab21 | tests/test_player.py |

## Output Spec Confirmations

**Exact line range of rewritten queue-build block in player.py:** Lines 521-544 (from the Phase 82 D-01/D-03 comment through `queue = list(streams_by_position)`). The `self._streams_queue = queue` and `self._try_next_stream()` calls at lines 546-547 are unchanged.

**Drift-guard test name:** `test_preferred_stream_id_drift_guard`
Non-comment grep expectation: reads `musicstreamer/player.py`, filters lines where `ln.lstrip().startswith("#")`, asserts `"preferred_stream_id" in non_comments`. Non-comment occurrence count: 3 (at least 2 required per plan verification).

**D-04 invariant confirmed:** `play_stream` at lines 549-559 was NOT modified. `grep -c 'def play_stream' musicstreamer/player.py` returns 1 with original signature intact.

**D-05 invariant confirmed:** `_try_next_stream`, `_handle_gst_error_recovery`, and `_on_youtube_resolution_failed` were NOT modified. Changes are strictly confined to the queue-build block inside `Player.play()`.

**Test count:** 8 new tests in tests/test_player.py (1 minimal RED + 7 behavioral):
1. `test_preferred_stream_id_minimal_red` — Task 1 TDD gate
2. `test_preferred_stream_id_at_queue_head` — D-03 head placement
3. `test_preferred_stream_id_not_duplicated` — no duplicate in queue
4. `test_preferred_stream_id_none_falls_back_to_order_streams` — None → order_streams
5. `test_preferred_stream_id_stale_resolves_to_none_falls_back` — stale id fallback
6. `test_preferred_stream_id_beats_preferred_quality` — D-03 precedence
7. `test_failover_after_preferred_stream_advances_queue` — D-05 regression
8. `test_preferred_stream_id_drift_guard` — source-grep pin

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_preferred_stream_id_none_falls_back_to_order_streams assertion corrected**
- **Found during:** Task 2 GREEN
- **Issue:** The plan's RESEARCH.md template comment "order_streams puts hi first (quality_rank hi=3 > low=1)" is only true when streams have known bitrate (bitrate_kbps > 0). Test streams with bitrate_kbps=0 (default) all land in the "unknown" partition and are sorted by `position asc` per D-07, not by quality rank. The original assertion `p._current_stream.quality == "hi"` was wrong against real `order_streams` behavior.
- **Fix:** Changed test to assert `p._current_stream.id == 1` (position=1 stream comes first in unknown-bitrate partition), with test setup providing stream id=1 at position=1. Comment documents why quality rank does not apply here.
- **Files modified:** tests/test_player.py
- **Commit:** 363ab21

## Verification Results

- `uv run pytest tests/test_player.py -k "preferred_stream_id or failover_after_preferred_stream" -x -q` — 8/8 pass
- `uv run pytest tests/test_player.py tests/test_player_failover.py -x -q` — 52/52 pass (no regressions)
- Source-grep: `grep -v '^\s*#' musicstreamer/player.py | grep -c preferred_stream_id` outputs 3 (at least 2 required)
- D-04: `grep -c 'def play_stream' musicstreamer/player.py` outputs 1 (signature unchanged)
- Full suite: `uv run pytest -q --tb=short` — 1687 passed, 2 failed (both pre-existing failures unrelated to this plan: test_hamburger_menu_actions and test_end_to_end_factory_fallback_on_win32_without_winrt)

## Known Stubs

None — `Player.play()` now reads `station.preferred_stream_id` and places the resolved stream at queue head. The write side (Plan 82-03 `_on_stream_selected` calling `Repo.set_preferred_stream`) and the UI affordance (stream-selector signal hookup) are deferred per the plan's stated scope boundary.

## Threat Flags

None — no new external input surface. `station.preferred_stream_id` is sourced from the trusted Station dataclass via `Repo.list_stations`/`get_station`. The Player reads it via `getattr(..., None)` and uses it as an int comparison against `StationStream.id` (INTEGER from DB). No file I/O or network paths added.

## Self-Check: PASSED

- musicstreamer/player.py: `preferred_stream_id` appears 4 times total (1 comment + 3 non-comment)
- musicstreamer/player.py: `def play_stream` present exactly once (D-04)
- tests/test_player.py: `grep -c preferred_stream_id` returns 28
- Commits: 9193ac3 (RED), d98610f (GREEN player), 363ab21 (GREEN tests) all verified in git log
