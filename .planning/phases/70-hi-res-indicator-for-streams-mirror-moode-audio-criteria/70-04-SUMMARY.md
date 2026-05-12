---
phase: 70
plan: "04"
subsystem: player
tags: [player, gstreamer, caps, signal, threading, tdd-green]
dependency_graph:
  requires: [70-00, 70-01, 70-02]
  provides: [Player.audio_caps_detected Signal, Player._on_caps_negotiated, Player._arm_caps_watch_for_current_stream]
  affects: [musicstreamer/player.py]
tech_stack:
  added: []
  patterns: [notify::caps on audio pad, QueuedConnection cross-thread Signal, Pattern 1b dual-path caps read]
key_files:
  modified: [musicstreamer/player.py]
decisions:
  - "Receiver-side QueuedConnection (MainWindow in Plan 70-05) — Player does not self-connect audio_caps_detected (Pitfall 9 Option A: Player has no repo handle)"
  - "Defensive dual-path rate extraction guards both (bool, int) tuple from get_int() and fallback dict-access; also handles MagicMock in tests via isinstance(result, tuple) guard"
  - "Pattern 1b: _arm_caps_watch_for_current_stream called from both _set_uri (async notify::caps) and _on_playbin_state_changed (main-thread synchronous path)"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-12"
  tasks: 2
  files: 1
---

# Phase 70 Plan 04: Player Audio Caps Detection Signal Summary

Wave 2 GREEN — wired GStreamer audio-sink-pad caps detection into Player and exposed `audio_caps_detected = Signal(int, int, int)` for consumption by MainWindow in Plan 70-05.

## What Was Built

Player gains three capabilities:

1. `audio_caps_detected = Signal(int, int, int)` — class-level Signal carrying `(stream_id, rate_hz, bit_depth)`, declared parallel to existing Phase 62 bus-loop Signals.

2. `_arm_caps_watch_for_current_stream()` — per-URL caps watcher lifecycle manager: disconnects prior pad watch, arms `_caps_armed_for_stream_id` one-shot guard, fetches the audio pad from playbin3, connects `notify::caps`, then performs an immediate synchronous read in case caps are already negotiated.

3. `_on_caps_negotiated(pad, _pspec)` — streaming-thread handler that reads `pad.get_current_caps()`, extracts rate and format, calls `bit_depth_from_format()`, and emits `audio_caps_detected` exactly once per stream URL (Pitfall 6 one-shot disarm).

Pattern 1b dual-path: `_arm_caps_watch_for_current_stream` is hooked in both `_set_uri` (async path for HLS/re-negotiation) and `_on_playbin_state_changed` (main-thread synchronous path for HTTP streams where caps are already stable at PLAYING).

## Threading Invariant

`_on_caps_negotiated` runs on the GStreamer streaming thread. It emits only `self.audio_caps_detected.emit(sid, rate, depth)` and returns. No Qt widget access, no `repo` calls, no `self._pipeline.set_property` mutations. MainWindow (Plan 70-05) connects with `Qt.ConnectionType.QueuedConnection` for automatic cross-thread delivery.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Defensive tuple unpacking for `s.get_int("rate")`**
- **Found during:** Task 2 regression run (test_player_buffering.py::test_dedup_resets_on_new_stream failed)
- **Issue:** RESEARCH Pattern 1 used bare `rate_ok, rate = s.get_int("rate")`. In tests where the mock pipeline is set up for buffering tests (not caps tests), the MagicMock `s.get_int("rate")` returned a MagicMock (not a 2-tuple), causing `ValueError: not enough values to unpack`. Additionally, the fallback `int(s["rate"])` on a MagicMock returns 1 (MagicMock.__int__ == 1), which would cause `test_caps_ignores_zero_rate` to fail.
- **Fix:** Replaced bare tuple unpack with `isinstance(result, tuple) and len(result) == 2` guard; added `_rate_found` flag so the dict-access fallback only applies when `get_int` did NOT return a valid `(True, int)` result.
- **Files modified:** musicstreamer/player.py (lines 787-806)
- **Commit:** d528203

## Test Results

| Suite | Count | Result |
|-------|-------|--------|
| tests/test_player_caps.py | 6 | GREEN |
| tests/test_player_tag.py | 10 | GREEN (no regression) |
| tests/test_player_buffering.py | 4 | GREEN (no regression) |
| tests/test_main_window_integration.py | 59 | GREEN (no regression) |
| Full Wave 1+2 suite (hi_res, repo, stream_ordering, player_caps) | 136 | GREEN |

## Grep Gates (Verified)

| Gate | Expected | Actual |
|------|----------|--------|
| `audio_caps_detected = Signal(int, int, int)` in non-comment lines | 1 | 1 |
| `self.audio_caps_detected.connect` in non-comment lines | 0 | 0 (deferred to Plan 70-05) |
| `_caps_armed_for_stream_id = 0` inside `_on_caps_negotiated` | >= 1 | 1 |
| `QTimer.singleShot` inside `_on_caps_negotiated` | 0 | 0 |
| `setVisible/setText/setStyleSheet` inside `_on_caps_negotiated` | 0 | 0 |
| `set_property/set_state` inside `_on_caps_negotiated` | 0 | 0 |
| `from musicstreamer.hi_res import bit_depth_from_format` | 1 | 1 |

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1: Signal + state fields | b60e86c | feat(70-04): declare audio_caps_detected Signal + caps-watch state on Player |
| Task 2: Handlers + wiring | d528203 | feat(70-04): implement _on_caps_negotiated + _arm_caps_watch + Pattern 1b hook |

## Self-Check: PASSED

- musicstreamer/player.py modified: present
- Commit b60e86c: found
- Commit d528203: found
- 6/6 test_player_caps.py tests GREEN
- No regression in adjacent Player tests
