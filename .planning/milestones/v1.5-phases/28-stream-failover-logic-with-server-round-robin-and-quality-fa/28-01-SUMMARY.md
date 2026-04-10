---
phase: 28-stream-failover-logic-with-server-round-robin-and-quality-fa
plan: "01"
subsystem: player
tags: [failover, gstreamer, glib, tdd, streams]
dependency_graph:
  requires: [27-01]
  provides: [stream-failover-logic]
  affects: [musicstreamer/player.py]
tech_stack:
  added: []
  patterns: [GLib.timeout_add for deferred callbacks, GLib.idle_add for cross-thread UI, TDD red-green]
key_files:
  created:
    - tests/test_player_failover.py
  modified:
    - musicstreamer/player.py
decisions:
  - "Queue built with preferred quality first (identity comparison), then position order — avoids D-05 duplication pitfall"
  - "YouTube failover uses GLib.timeout_add poll (1s interval) on _yt_proc.poll() rather than GStreamer bus"
  - "on_failover callback pattern (not direct window reference) keeps Player dependency-free"
  - "_is_first_attempt flag distinguishes initial play from failover attempt for callback timing"
metrics:
  duration: "~12 min"
  completed: "2026-04-09"
  tasks_completed: 1
  files_changed: 2
---

# Phase 28 Plan 01: Stream Failover Logic Summary

**One-liner:** Failover-capable Player with GLib-timeout-based stream queue — preferred quality first, GStreamer error and 10s timeout both trigger automatic next-stream attempt.

## What Was Built

Extended `Player` to manage an ordered stream queue and automatically try the next stream on failure, satisfying requirements D-01 through D-05 and D-08.

### Key Changes in `musicstreamer/player.py`

**New instance variables:**
- `_streams_queue: list[StationStream]` — ordered list of streams to try
- `_failover_timer_id: int | None` — GLib source ID for 10s timeout
- `_yt_poll_timer_id: int | None` — GLib source ID for YouTube process polling
- `_on_failover: callable | None` — callback for window to show toasts
- `_current_stream: StationStream | None` — currently active stream
- `_current_station_name: str` — station name for title display
- `_is_first_attempt: bool` — distinguishes first play from failover

**New/modified methods:**
- `play()` — now accepts `preferred_quality` and `on_failover`; builds ordered queue; calls `_try_next_stream()`
- `play_stream()` — manual stream selection bypassing queue (D-08)
- `_try_next_stream()` — core failover loop: pops queue, plays stream, arms timeout
- `_cancel_failover_timer()` — cancels both GLib timers (T-28-02 mitigation)
- `_on_timeout_cb()` — fires after 10s with no audio; calls `_try_next_stream()`
- `_on_gst_error()` — now calls `_cancel_failover_timer()` then `_try_next_stream()`
- `_on_gst_tag()` — now calls `_cancel_failover_timer()` (stream working)
- `stop()` — now cancels timers and clears queue
- `pause()` — now cancels timers and clears queue
- `_yt_poll_cb()` — GLib poll callback for mpv process exit detection
- `_play_youtube()` — now arms `_yt_poll_timer_id` after subprocess launch

### Queue Construction Algorithm

```python
streams_by_position = sorted(station.streams, key=lambda s: s.position)
preferred = next((s for s in streams_by_position if s.quality == preferred_quality), None)
if preferred:
    queue = [preferred] + [s for s in streams_by_position if s is not preferred]
else:
    queue = list(streams_by_position)
```

Uses identity (`is not`) comparison to prevent preferred stream duplication (Pitfall 5).

## Tests

13 new tests in `tests/test_player_failover.py`:

| Test | What It Covers |
|------|----------------|
| `test_preferred_stream_first` | Preferred quality stream goes first in queue |
| `test_no_preferred_quality_uses_position_order` | Position order when no preference |
| `test_preferred_stream_not_duplicated` | Preferred stream appears exactly once |
| `test_gst_error_triggers_failover` | GStreamer error calls `_try_next_stream` |
| `test_timeout_triggers_failover` | 10s timeout calls `_try_next_stream`, returns False |
| `test_tag_received_cancels_timeout` | ICY tag cancels failover timer |
| `test_all_streams_exhausted` | Empty queue calls `on_failover(None)` |
| `test_failover_callback_called_on_attempt` | `on_failover(stream)` on failover attempt |
| `test_timer_cancelled_on_stop` | `stop()` cancels timer |
| `test_timer_cancelled_on_pause` | `pause()` cancels timer |
| `test_new_play_cancels_previous_failover` | New `play()` clears stale state |
| `test_play_stream_bypasses_queue` | Manual stream pick ignores queue |
| `test_youtube_failover_polling` | YouTube poll timer registered |

Full suite: 244 tests passing (was 231 before this plan).

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

T-28-02 (Denial of Service via orphaned timers) fully mitigated: `_cancel_failover_timer()` called in `stop()`, `pause()`, and at start of every `play()` call.

No new threat surface introduced beyond what the plan's threat model covers.

## Self-Check: PASSED

- `tests/test_player_failover.py` — FOUND
- `musicstreamer/player.py` — FOUND
- Commit `b3dec88` — FOUND
