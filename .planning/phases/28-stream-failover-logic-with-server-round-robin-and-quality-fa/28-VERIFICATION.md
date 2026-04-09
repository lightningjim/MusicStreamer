---
phase: 28-stream-failover-logic-with-server-round-robin-and-quality-fa
verified: 2026-04-09T00:00:00Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Play a station with 2+ streams and verify stream picker button appears next to stop button"
    expected: "network-wireless-symbolic button visible in controls_box"
    why_human: "GTK widget visibility cannot be verified without rendering the UI"
  - test: "Click the stream picker button and verify popover shows streams with quality badges and active-stream checkmark"
    expected: "Popover opens with all streams listed, quality uppercase badge, emblem-ok on current stream"
    why_human: "Popover content and visual rendering requires running application"
  - test: "Click a different stream in the picker and verify playback switches immediately"
    expected: "Audio source changes, picker refreshes to show new checkmark"
    why_human: "Audio playback switch requires live execution"
  - test: "Play a station with 1 stream and verify the stream picker button is hidden"
    expected: "stream_btn.set_visible(False) — button not shown"
    why_human: "Widget visibility state in running app"
  - test: "Trigger a stream failure (invalid URL) and verify toast 'Stream failed — trying [label]...' appears"
    expected: "Adw.Toast notification auto-dismisses after 3s"
    why_human: "Toast notification display requires live GTK main loop"
  - test: "Exhaust all streams (all invalid) and verify 'All streams failed' toast appears"
    expected: "Adw.Toast with 5s timeout displayed"
    why_human: "End-to-end failover path requires live GStreamer pipeline errors"
---

# Phase 28: Stream Failover Logic Verification Report

**Phase Goal:** Player automatically tries next stream on error or timeout, using preferred quality first then position order; toast notifications for failover events; manual stream picker in now-playing controls
**Verified:** 2026-04-09
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GStreamer error or 10s timeout triggers failover to next stream | VERIFIED | `_on_gst_error` calls `_cancel_failover_timer()` + `_try_next_stream()`; `_on_timeout_cb()` calls `_try_next_stream()` + returns False; tests `test_gst_error_triggers_failover` and `test_timeout_triggers_failover` both pass |
| 2 | Preferred quality stream is tried first; remaining in position order | VERIFIED | `play()` builds queue: `preferred + [s for s in streams_by_position if s is not preferred]`; `test_preferred_stream_first` and `test_no_preferred_quality_uses_position_order` pass |
| 3 | Each stream tried exactly once; all-exhausted stops playback with error toast | VERIFIED | `_try_next_stream()` pops queue (no re-enqueue); empty queue calls `GLib.idle_add(self._on_failover, None)`; `test_all_streams_exhausted` passes; `_on_player_failover(None)` shows "All streams failed" toast |
| 4 | Toast notifications on each failover attempt and on exhaustion | VERIFIED | `_on_player_failover` in main_window.py: `stream is None` -> "All streams failed" (5s), else "Stream failed — trying {label}..." (3s); `_show_toast()` calls `toast_overlay.add_toast()` |
| 5 | Stream picker button in now-playing controls shows all streams for manual switching | VERIFIED | `self.stream_btn = Gtk.MenuButton()` in controls_box; `_update_stream_picker()` builds Popover with sorted streams, quality badges, active-stream checkmark; `set_visible(len(streams) > 1)`; hidden in `_stop()` at line 772 |
| 6 | Manual stream selection plays immediately without affecting configured order | VERIFIED | `_on_stream_picker_row_activated` calls `player.play_stream(stream, ...)` which clears queue and plays only that stream; `test_play_stream_bypasses_queue` passes |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/player.py` | Failover-aware Player with `_streams_queue`, `_try_next_stream`, timeout | VERIFIED | All 9 required symbols present; 251 lines; substantive implementation |
| `tests/test_player_failover.py` | Unit tests for failover logic, >= 80 lines | VERIFIED | 378 lines, 13 test functions — exceeds minimum |
| `musicstreamer/ui/main_window.py` | ToastOverlay, stream picker MenuButton, failover callback wiring | VERIFIED | `toast_overlay` present; `stream_btn` MenuButton present; all key methods implemented |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `player.py` | `_on_gst_error` | calls `_try_next_stream` on error | WIRED | Line 65: `_cancel_failover_timer()` + `_try_next_stream()` |
| `player.py` | `GLib.timeout_add` | arms 10s failover timer | WIRED | Line 115: `GLib.timeout_add(BUFFER_DURATION_S * 1000, self._on_timeout_cb)` |
| `main_window.py` | `player.py` | `on_failover` callback passed to `player.play()` | WIRED | Line 893: `on_failover=self._on_player_failover` |
| `main_window.py` | `Adw.ToastOverlay` | `toast_overlay` wraps scroller | WIRED | Lines 325-327: created, set_child(scroller), shell.set_content(toast_overlay) |
| `main_window.py` | `player.play_stream` | stream picker row click calls `play_stream` | WIRED | Line 958: `self.player.play_stream(stream, ...)` in `_on_stream_picker_row_activated` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `_update_stream_picker` | `station.streams` | `station` arg from `_play_station` → DB-loaded Station | Yes — Station loaded via `repo.get_station()` with streams joined | FLOWING |
| `_on_player_failover` | `stream` | passed from `player._try_next_stream` via `GLib.idle_add` | Yes — `StationStream` popped from real queue | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 13 failover tests pass | `uv run pytest tests/test_player_failover.py -q` | `13 passed in 0.05s` | PASS |
| Full suite no regressions | `uv run pytest tests/ -q` | `244 passed in 1.86s` | PASS |
| `_try_next_stream` present | `grep -c "_try_next_stream" player.py` | 4 references | PASS |
| `_streams_queue` present | grep check | present in __init__, play(), stop(), pause(), play_stream() | PASS |
| `toast_overlay` wired | grep check | 7 occurrences (creation + all child swaps + add_toast) | PASS |
| `stream_btn` wired | grep check | 5 occurrences (creation + show/hide + popover set) | PASS |
| Empty-state swaps use toast_overlay | grep check | `toast_overlay.set_child(...)` at lines 556, 558, 569, 571, 1010, 1012 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| D-01 | 28-01 | GStreamer error triggers failover | SATISFIED | `_on_gst_error` calls `_try_next_stream` |
| D-02 | 28-01 | Silence detection out of scope | SATISFIED | Not implemented (by design) |
| D-03 | 28-01 | Each stream tried exactly once; no retry | SATISFIED | Queue pops without re-enqueue; `test_all_streams_exhausted` |
| D-04 | 28-01 | Preferred quality stream tried first | SATISFIED | Queue construction with preferred at index 0 |
| D-05 | 28-01 | Remaining streams in position order | SATISFIED | `sorted(streams, key=lambda s: s.position)` |
| D-06 | 28-02 | Adw.Toast notifications for failover | SATISFIED | `_on_player_failover` + `_show_toast` |
| D-07 | 28-02 | Stream picker button in now-playing controls | SATISFIED | `self.stream_btn` MenuButton in controls_box |
| D-08 | 28-01/02 | Manual stream selection via picker | SATISFIED | `play_stream()` + `_on_stream_picker_row_activated` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

No stubs, placeholders, or hardcoded empty returns found in phase-modified files. The `time.sleep(2)` in `_play_youtube` is pre-existing behavior (cookie retry path), not a stub.

### Human Verification Required

#### 1. Stream Picker Visibility

**Test:** Play a station that has 2+ streams configured. Check that the network-wireless-symbolic button appears in the controls row next to the stop button.
**Expected:** Button visible, tooltip "Switch stream"
**Why human:** GTK widget visibility requires running app with populated station data

#### 2. Stream Picker Popover Content

**Test:** Click the stream picker button on a multi-stream station.
**Expected:** Popover opens showing each stream's label (or truncated URL), quality badge (uppercase), and a checkmark on the currently-playing stream.
**Why human:** Popover rendering and content layout requires live GTK execution

#### 3. Manual Stream Switch

**Test:** With a multi-stream station playing, click the stream picker and select a different stream.
**Expected:** Playback switches immediately to the selected stream; popover closes; checkmark moves to new stream on next open.
**Why human:** Audio playback switch and picker state update require live execution

#### 4. Single-Stream Station

**Test:** Play a station that has only 1 stream configured.
**Expected:** The stream picker button is not visible in the controls row.
**Why human:** Widget visibility in running app

#### 5. Failover Toast (per-attempt)

**Test:** Configure a station with an invalid stream URL as the first stream and a valid one as the second. Play the station.
**Expected:** Toast "Stream failed — trying [label]..." appears briefly, then playback continues on the valid stream.
**Why human:** Requires GStreamer pipeline error to fire, which needs live network operation

#### 6. Exhaustion Toast

**Test:** Configure a station where all streams have invalid URLs. Play it.
**Expected:** After trying all streams, toast "All streams failed" appears (5s timeout).
**Why human:** Full end-to-end failover path requires live GStreamer and GLib main loop

### Gaps Summary

No gaps. All 6 roadmap success criteria are implemented and wired correctly. 13 failover-specific tests pass, full suite of 244 tests passes with no regressions. The 6 human verification items are visual/behavioral checks that cannot be validated programmatically — they do not indicate any missing implementation.

---

_Verified: 2026-04-09_
_Verifier: Claude (gsd-verifier)_
