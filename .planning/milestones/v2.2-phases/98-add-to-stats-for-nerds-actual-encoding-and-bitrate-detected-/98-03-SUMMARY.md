---
phase: 98-add-to-stats-for-nerds-actual-encoding-and-bitrate-detected
plan: "03"
subsystem: main_window
tags: [signal-wiring, queued-connection, integration, codec-detection, bitrate]
dependency_graph:
  requires: [98-01, 98-02]
  provides:
    - audio_format_detected QueuedConnection in MainWindow.__init__
    - _on_audio_format_detected slot (never-raise, no DB write)
    - update_detected_caps fan-out in _on_audio_caps_detected
  affects:
    - musicstreamer/ui_qt/main_window.py
tech_stack:
  added: []
  patterns:
    - QueuedConnection cross-thread signal delivery (qt-glib-bus-threading.md Rule 2)
    - never-raise slot pattern (try/except _log.exception)
    - hasattr-guarded panel fan-out
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/main_window.py
decisions:
  - "D-03 honored: _on_audio_format_detected performs no repo.update_stream; detected codec/bitrate are transient panel-only values"
  - "D-04 completed: update_detected_caps fan-out added in _on_audio_caps_detected immediately after _refresh_quality_badge"
  - "update_detected_caps placed before update_quality_map in fan-out ordering (detected panel rows before global quality map)"
metrics:
  duration: "~88s"
  completed: "2026-06-27"
  tasks_completed: 1
  files_changed: 1
---

# Phase 98 Plan 03: Signal Wiring — audio_format_detected Integration Summary

**One-liner:** QueuedConnection wiring of `Player.audio_format_detected` to a never-raise `MainWindow._on_audio_format_detected` slot + `update_detected_caps` fan-out in `_on_audio_caps_detected`, completing the producer-to-consumer integration seam.

## What Was Built

### Task 1: Connect + Slot + Caps Fan-out

**`musicstreamer/ui_qt/main_window.py`** — three changes:

**1. New connection in `__init__` (~546-554):**
```python
self._player.audio_format_detected.connect(
    self._on_audio_format_detected, Qt.ConnectionType.QueuedConnection
)
```
QueuedConnection is mandatory per qt-glib-bus-threading.md Rule 2: the signal fires from the GStreamer bus-loop thread; the slot must run on the Qt main thread.

**2. New slot `_on_audio_format_detected`:**
- `try` block: `if hasattr(self.now_playing, "update_detected_format"): self.now_playing.update_detected_format(stream_id, codec_norm, bitrate_kbps)`
- `except Exception: _log.exception(...)` — never-raise invariant (tag-burst resilience, T-98-08)
- No `repo.update_stream` call — detected values are transient (D-03 / Finding 6)

**3. Fan-out in `_on_audio_caps_detected` Step 5:**
```python
if hasattr(self.now_playing, "update_detected_caps"):
    self.now_playing.update_detected_caps(stream_id, rate_hz, bit_depth)
```
Inserted after the existing `_refresh_quality_badge` fan-out, still inside the `try` block, preserving the DB-write-first ordering invariant.

## Verification Results

```
.venv/bin/python -m pytest tests/test_player_codec_tag.py tests/test_now_playing_stats.py \
  tests/test_fake_player_signal_parity.py tests/test_now_playing_panel.py \
  tests/test_player_tag.py tests/test_player_caps.py tests/test_main_window_integration.py \
  -x -q --deselect tests/test_main_window_integration.py::test_hamburger_menu_actions

269 passed, 1 deselected, 63 warnings in 4.21s
```

The deselected test (`test_hamburger_menu_actions`) is a known pre-existing failure unrelated to this plan — confirmed by running the same test against the unmodified codebase (same failure).

## Acceptance Criteria

| Criterion | Result |
|-----------|--------|
| `grep -c "audio_format_detected.connect" main_window.py` → 1 | PASS (1) |
| `audio_format_detected.connect` includes `QueuedConnection` | PASS |
| `grep -c "def _on_audio_format_detected" main_window.py` → 1 | PASS (1) |
| `grep -c "update_detected_caps" main_window.py` → 1 | PASS (3 — hasattr guard + call + docstring) |
| No `repo.update_stream` in `_on_audio_format_detected` | PASS |
| `test_main_window_integration` passes (exc. pre-existing) | PASS |

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 926bf6ac | feat | Wire audio_format_detected QueuedConnection + slot + caps fan-out |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Model Compliance

- **T-98-07 (Tampering — thread-safety):** Connection uses `Qt.ConnectionType.QueuedConnection`; slot runs on Qt main thread only. No Qt widget touched from bus-loop thread.
- **T-98-08 (DoS — exception in slot):** `_on_audio_format_detected` wrapped in `try/except _log.exception`; malformed payload cannot crash the UI thread.
- **T-98-09 (Tampering — data integrity):** No `repo.update_stream` call in slot; detected values stay transient; declared `Stream.codec`/`bitrate_kbps` remain the persistent source of truth.
- **T-98-SC:** No package installs.

## Known Stubs

None. All four detected-format rows are now fully wired end-to-end: producer (Plan 98-01) emits the signal, consumer (Plan 98-02) exposes the panel methods, and this plan connects them. Playback of a stream will populate Encoding, Bitrate, Sample rate, and Bit depth rows in Stats for Nerds.

## Self-Check: PASSED

- `musicstreamer/ui_qt/main_window.py` modified: FOUND
- Task commit 926bf6ac: verified in git log
- 269 tests pass (1 pre-existing failure deselected)
