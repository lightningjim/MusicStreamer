---
phase: 41-platform-media-keys
plan: "03"
subsystem: media-keys
tags: [pyside6, mpris2, media-keys, main-window, signal-wiring, testing]

requires:
  - phase: 41-01
    provides: "MediaKeysBackend abstract class + NoOpMediaKeysBackend + create() factory"

provides:
  - "MainWindow constructs MediaKeysBackend via factory and wires all 4 request signals"
  - "Player.title_changed bridges to backend.publish_metadata on every ICY update (D-05)"
  - "Playback state transitions (play/pause/stop/failover/offline) call set_playback_state"
  - "closeEvent calls backend.shutdown() before super() (T-41-13 mitigation)"
  - "NowPlayingPanel.current_cover_pixmap() public accessor"
  - "8 integration tests using _SpyBackend pattern (no real D-Bus)"

affects:
  - "41-02 (LinuxMprisBackend must exist for live media-keys to function; wiring is complete)"
  - "43.1 (Windows SMTC will be wired via same MainWindow slots)"

tech-stack:
  added: []
  patterns:
    - "Belt-and-braces factory try/except in MainWindow wraps the D-06 factory guarantee"
    - "Bridge slot pattern: _on_media_key_play_pause delegates to now_playing._on_play_pause_clicked then mirrors state to backend"
    - "_SpyBackend subclass of NoOpMediaKeysBackend records calls for test assertions"

key-files:
  created:
    - tests/test_main_window_media_keys.py
  modified:
    - musicstreamer/ui_qt/main_window.py
    - musicstreamer/ui_qt/now_playing_panel.py

key-decisions:
  - "Bridge _on_media_key_play_pause delegates to now_playing._on_play_pause_clicked (reuses panel logic) then mirrors state to backend — avoids duplicating pause/resume logic"
  - "MainWindow wraps media_keys.create() in try/except despite D-06 guarantee — belt-and-braces for construction bugs in backend"
  - "pause state: mirrored in _on_media_key_play_pause by reading now_playing._is_playing after the toggle — no new signal needed"

patterns-established:
  - "MediaKeysBackend wired at end of MainWindow.__init__ so backend sees fully-constructed window"
  - "closeEvent override pattern: try shutdown(), log warning on failure, call super()"

requirements-completed: [MEDIA-04, MEDIA-05]

duration: 3 min
completed: 2026-04-15
---

# Phase 41 Plan 03: Wire MediaKeysBackend into MainWindow Summary

**MainWindow wired to MediaKeysBackend via factory: title_changed bridges to publish_metadata, 4 state transitions call set_playback_state, closeEvent calls shutdown — 8/8 spy-backend tests passing**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-15T15:41:49Z
- **Completed:** 2026-04-15T15:44:48Z
- **Tasks:** 1 complete, 1 pending (Task 2: manual UAT)
- **Files modified:** 3

## Accomplishments

- `MainWindow` constructs `MediaKeysBackend` via `media_keys.create()` with a belt-and-braces try/except fallback to `NoOpMediaKeysBackend` (factory guarantee + implementation guarantee)
- All 4 backend request signals wired to bridge slots: `play_pause_requested`, `stop_requested`, `next_requested` (no-op D-03), `previous_requested` (no-op D-03)
- `Player.title_changed` → `_on_title_changed_for_media_keys` → `publish_metadata(station, title, cover_pixmap)` on every ICY update
- Playback state transitions covered: station-activated → `"playing"`, failover(None) → `"stopped"`, offline → `"stopped"`, station-deleted → `"stopped"`, media-key play-pause → `"playing"` or `"paused"`
- `closeEvent` override calls `backend.shutdown()` before `super().closeEvent()` (T-41-13 mitigation)
- `NowPlayingPanel.current_cover_pixmap()` accessor added for use by the bridge slot

## Task Commits

1. **RED — failing tests** - `253407d` (test)
2. **Task 1: Wire MediaKeysBackend into MainWindow** - `da6eb5a` (feat)

## Files Created/Modified

- `tests/test_main_window_media_keys.py` — 8 integration tests using `_SpyBackend` monkeypatching `media_keys.create`
- `musicstreamer/ui_qt/main_window.py` — factory construction, signal wiring, bridge slots, closeEvent, state transitions
- `musicstreamer/ui_qt/now_playing_panel.py` — `current_cover_pixmap()` public accessor

## Decisions Made

- **Bridge pattern for play_pause:** `_on_media_key_play_pause` delegates to `now_playing._on_play_pause_clicked()` (reuses all existing panel logic), then reads `now_playing._is_playing` to mirror the resulting state to the backend. No new signal needed; no logic duplication.
- **No separate pause signal:** The pause state is mirrored immediately after the toggle in `_on_media_key_play_pause` — clean and predictable without adding new signals or observable state.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Pending: Task 2 — Manual UAT

Task 2 is a `checkpoint:human-verify` gate. It requires running the app on Linux and verifying end-to-end MPRIS2 behaviour via `playerctl`. **Task 2 cannot proceed until Plan 41-02 (`LinuxMprisBackend`) is executed** — without `mpris2.py`, `media_keys.create()` returns `NoOpMediaKeysBackend` and `playerctl` will not see the service.

### UAT Instructions (Task 2)

Run the app on Linux:
```
cd /home/kcreasey/OneDrive/Projects/MusicStreamer
uv run python -m musicstreamer
```

**Test 1 — service registration:**
```
playerctl --list-all
```
Expected: output includes `musicstreamer`.

**Test 2 — status + metadata (no playback):**
```
playerctl -p musicstreamer status
playerctl -p musicstreamer metadata
```
Expected: status is `Stopped`. Metadata shows just the NoTrack trackid (or is empty).

**Test 3 — playback metadata:**
Click a station with ICY support (e.g., SomaFM). Wait 5-10s for ICY title.
```
playerctl -p musicstreamer status
playerctl -p musicstreamer metadata
```
Expected: status `Playing`, `xesam:title` = ICY title, `xesam:artist` = station name, `mpris:artUrl` starts with `file://`.
Verify the PNG exists: `ls ~/.cache/musicstreamer/mpris-art/<id>.png`

**Test 4 — playerctl control:**
```
playerctl -p musicstreamer play-pause  # stream pauses
playerctl -p musicstreamer play-pause  # stream resumes
playerctl -p musicstreamer stop        # stream stops
```

**Test 5 — keyboard media keys:**
With a station playing, press the play/pause media key. Stream should toggle.

**Test 6 — GNOME overlay:**
Open system status menu. Media overlay should show MusicStreamer with station + ICY title + cover art.

**Test 7 — ICY update propagation:**
Let stream run until next ICY title (2-5 min). `playerctl -p musicstreamer metadata` should show updated title.

**Test 8 — clean shutdown:**
Close the app. `playerctl --list-all` should NOT show `musicstreamer`.

**Test 9 — no-D-Bus fallback (optional):**
```
DBUS_SESSION_BUS_ADDRESS=/dev/null uv run python -m musicstreamer
```
Expected: app starts, logs one warning `Media keys disabled...`, runs normally.

**Resume signal:** Type "approved" to mark Phase 41 complete, or describe any failures.

## Next Phase Readiness

- Task 1 complete: MainWindow wiring is in place and tested
- **Prerequisite before UAT:** Plan 41-02 (`LinuxMprisBackend`) must be executed to create `mpris2.py`
- After Plan 41-02 completes, run the app and execute UAT Tests 1-9 above
- Phase 41 will be complete once UAT is approved

---
*Phase: 41-platform-media-keys*
*Completed: 2026-04-15 (Task 1 only; Task 2 pending UAT after Plan 41-02)*
