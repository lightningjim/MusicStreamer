---
phase: 20-os-media-keys-integration
verified: 2026-04-05T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
human_verification:
  - test: "Click pause while a station is playing. Observe that audio stops, the now-playing panel (station name, title label, cover art) remains visible, and the pause button icon changes to play (media-playback-start-symbolic)."
    expected: "Audio stops. Station name label and title label remain visible. Pause button shows start/play icon. Stop button remains sensitive."
    why_human: "UI widget state (sensitivity, icon names, label visibility) after GStreamer pipeline NULL cannot be verified without a running GTK session."
  - test: "Click the play/resume button (now showing start icon) while paused. Verify the same station resumes playback."
    expected: "Same stream restarts. Pause button reverts to pause icon. Now-playing panel shows correct station info."
    why_human: "Requires live GStreamer pipeline and audio output to confirm stream restarts correctly."
  - test: "Click stop while paused. Verify now-playing panel clears and station is deselected."
    expected: "Title resets to 'Nothing playing'. Station name label hidden. Stop and pause buttons become insensitive. Cover art reverts to fallback."
    why_human: "UI state reset requires a running GTK session."
  - test: "With the app running, press the OS media play/pause key (or run: playerctl play-pause). Verify behavior matches the in-app pause button."
    expected: "Playback toggles pause/resume. GNOME media overlay shows 'MusicStreamer' with current station name."
    why_human: "Requires a live D-Bus session bus and MPRIS2 registration to verify."
  - test: "With the app running, run: playerctl stop. Verify stop behavior is triggered."
    expected: "Now-playing panel clears, identical to clicking the in-app stop button."
    why_human: "Requires live D-Bus session to test Stop dispatch."
  - test: "With the app running, run: playerctl metadata. Verify output shows station name and ICY track title."
    expected: "xesam:title = station name, xesam:artist = current ICY track title."
    why_human: "Requires live D-Bus and an active stream with ICY metadata."
---

# Phase 20: Playback Controls & Media Keys Verification Report

**Phase Goal:** Add play/pause button that pauses without deselecting the station, and wire OS media keys via MPRIS2
**Verified:** 2026-04-05
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Pause button (between star and stop) stops stream but keeps station selected and now-playing panel visible | VERIFIED (code) | `_toggle_pause()` calls `player.pause()` and sets `_paused=True` without clearing `_current_station` or touching title/name labels. `pause_btn` appended between `star_btn` and `stop_btn` in `controls_box` (main_window.py:115-135). |
| 2 | Pressing play on a paused station resumes the same stream | VERIFIED (code) | `_toggle_pause()` resume branch: `self._play_station(self._current_station)` with `_paused_station` guard (main_window.py:684-690). |
| 3 | Stop retains existing behavior — clears now-playing, deselects station | VERIFIED (code) | `_stop()` clears `_current_station=None`, resets `_paused=False`, disables both `stop_btn` and `pause_btn`, resets title label (main_window.py:712-735). |
| 4 | OS play/pause media key toggles pause/resume with same behavior as in-app button | VERIFIED (code) | `MprisService.PlayPause()` calls `GLib.idle_add(self._window._toggle_pause)` — same code path as the button click (mpris.py:52-54). Test `test_playpause_dispatches` passes. |
| 5 | OS stop key triggers the existing stop behavior | VERIFIED (code) | `MprisService.Stop()` calls `GLib.idle_add(self._window._stop)` (mpris.py:70-72). Test `test_stop_dispatches` passes. |

**Score:** 5/5 truths verified (code-level)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/player.py` | `pause()` method setting pipeline to NULL | VERIFIED | `def pause(self):` at line 66; sets `_on_title=None`, calls `_stop_yt_proc()`, sets `Gst.State.NULL`. |
| `musicstreamer/ui/main_window.py` | `pause_btn`, `_toggle_pause()`, `_paused` state | VERIFIED | All present and substantive. `pause_btn` wired to `_toggle_pause`. `_paused`/`_paused_station` state managed in `_toggle_pause`, `_play_station`, `_stop`. |
| `musicstreamer/mpris.py` | `MprisService` D-Bus service | VERIFIED | 171-line module. `class MprisService(dbus.service.Object)` with all MPRIS2 Player and root interface methods, `_build_metadata`, `emit_properties_changed`, `GetAll/Get/PropertiesChanged`. |
| `tests/test_player_pause.py` | Unit tests for player pause/stop | VERIFIED | 5 tests: `test_pause_sets_pipeline_null`, `test_pause_clears_on_title`, `test_pause_kills_yt_proc`, `test_stop_after_pause`, `test_pause_does_not_error_when_stopped`. All pass. |
| `tests/test_mpris.py` | Unit tests for MPRIS2 service | VERIFIED | 10 tests covering PlayPause/Stop dispatch, Next/Previous no-op, GetAll player/root, metadata with/without station, Raise. All pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `musicstreamer/ui/main_window.py` | `musicstreamer/player.py` | `self.player.pause()` | WIRED | `_toggle_pause()` calls `self.player.pause()` on pause branch (line 695). |
| `musicstreamer/mpris.py` | `musicstreamer/ui/main_window.py` | `GLib.idle_add(self._window._toggle_pause)` | WIRED | `PlayPause()` dispatches via `GLib.idle_add` (mpris.py:54). Pattern `idle_add.*_toggle_pause` confirmed. |
| `musicstreamer/ui/main_window.py` | `musicstreamer/mpris.py` | `self.mpris = MprisService(self)` | WIRED | Import at line 18, instantiation at line 35 in try/except with `None` fallback (line 37). |
| `musicstreamer/ui/main_window.py` | `musicstreamer/mpris.py` | `emit_properties_changed` on state changes | WIRED | Called in `_on_cover_art` (line 635), `_toggle_pause` (line 701), `_stop` (line 732), `_play_station` (line 833) — 4 locations confirmed. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `mpris.py _get_all_player` | `PlaybackStatus` | `self._window._playback_status()` — reads live `_paused` / `_current_station` state | Yes — live state, not hardcoded | FLOWING |
| `mpris.py _build_metadata` | `xesam:title` | `self._window._current_station.name` — live station object | Yes — real station name | FLOWING |
| `mpris.py _build_metadata` | `xesam:artist` | `self._window._last_cover_icy` — updated by ICY TAG callback | Yes — real ICY title or empty string | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| player pause() sets NULL state | `uv run --with pytest python -m pytest tests/test_player_pause.py -v` | 5 passed | PASS |
| MPRIS PlayPause dispatches to _toggle_pause | `uv run --with pytest python -m pytest tests/test_mpris.py -v` | 10 passed | PASS |
| Full test suite regression | `uv run --with pytest python -m pytest tests/ -q` | 184 passed | PASS |
| D-Bus live registration + playerctl | Requires running app + D-Bus session | — | SKIP (needs live session) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CTRL-01 | 20-01 | Play/pause button between star and stop; pause keeps station selected | SATISFIED | `pause_btn` inserted between `star_btn` and `stop_btn`; `_toggle_pause()` silences audio without clearing `_current_station`; 5 passing unit tests. |
| CTRL-02 | 20-02 | OS media keys control playback via MPRIS2 D-Bus | SATISFIED (code) | `MprisService` registered as `org.mpris.MediaPlayer2.MusicStreamer`; `PlayPause`→`_toggle_pause`, `Stop`→`_stop` dispatch via `GLib.idle_add`; 10 passing unit tests. Live D-Bus behavior requires human verification. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

No TODO/FIXME/placeholder comments, no empty return values in production paths, no hardcoded empty data flowing to rendering. `return null` / `return {}` only appear in `Quit()` and `Next()`/`Previous()` no-op stubs which are intentional MPRIS2 no-ops (CanQuit=False, CanGoNext=False).

### Human Verification Required

#### 1. Pause button UI behavior

**Test:** Click a playing station's pause button. Observe the now-playing panel.
**Expected:** Audio stops. Station name, title, and cover art remain visible. Pause button shows `media-playback-start-symbolic` icon. Stop button stays sensitive.
**Why human:** GTK widget state after GStreamer NULL cannot be confirmed without a running session.

#### 2. Resume from pause

**Test:** After pausing, click the button again (now showing play icon).
**Expected:** Same station stream restarts. Pause button reverts to `media-playback-pause-symbolic`.
**Why human:** Requires live GStreamer pipeline to confirm stream reconnection.

#### 3. Stop while paused

**Test:** While paused, click the stop button.
**Expected:** Now-playing panel clears. Title resets to "Nothing playing". Both stop and pause buttons become insensitive.
**Why human:** Requires running GTK session.

#### 4. OS media play/pause key

**Test:** With the app running and a station playing, press the OS media play/pause key (or run `playerctl play-pause`).
**Expected:** Playback toggles pause/resume identically to the in-app button. GNOME media overlay shows "MusicStreamer".
**Why human:** Requires a live session D-Bus and MPRIS2 registration.

#### 5. OS media stop key

**Test:** While playing, run `playerctl stop`.
**Expected:** Now-playing panel clears, identical to the in-app stop button.
**Why human:** Requires live D-Bus session.

#### 6. playerctl metadata

**Test:** While a station is playing with an active ICY title, run `playerctl metadata`.
**Expected:** Output includes `xesam:title` = station name and `xesam:artist` = current ICY track title.
**Why human:** Requires live stream with ICY metadata.

### Gaps Summary

No implementation gaps found. All 5 roadmap success criteria are satisfied at the code level:

- `Player.pause()` is fully implemented and tested (5 passing tests)
- Pause button sits between star and stop, wired to `_toggle_pause()`
- `_toggle_pause()` correctly manages `_paused`/`_paused_station` state without clearing station context
- `_stop()` resets all pause state and clears the now-playing panel
- `MprisService` implements full MPRIS2 Player interface with all required methods
- All D-Bus handlers dispatch via `GLib.idle_add()` for thread safety
- `MprisService` instantiation is wrapped in try/except — app degrades gracefully when D-Bus unavailable
- `emit_properties_changed` called at all 4 state-change sites
- 184 total tests pass, no regressions

Status is `human_needed` because live OS media key and D-Bus behavior cannot be verified programmatically.

---

_Verified: 2026-04-05_
_Verifier: Claude (gsd-verifier)_
