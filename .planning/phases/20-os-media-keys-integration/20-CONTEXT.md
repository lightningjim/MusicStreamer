# Phase 20: Playback Controls & Media Keys - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a play/pause toggle button to the now-playing controls bar (between star and stop), and wire OS media keys via a MPRIS2 D-Bus interface. Pause stops the stream but keeps the station selected and now-playing panel visible. Stop retains existing behavior (clears selection and now-playing). MPRIS2 exposes PlayPause, Stop, and read-only metadata.

</domain>

<decisions>
## Implementation Decisions

### Pause Button

- **D-01:** Single toggle button — shows `media-playback-pause-symbolic` while playing, swaps to `media-playback-start-symbolic` while paused. Icon-only, matches stop button style (`suggested-action` CSS class).
- **D-02:** Button inserts between `star_btn` and `stop_btn` in `controls_box`.
- **D-03:** Now-playing panel stays visually identical when paused — no dimming, no "Paused" label. State is communicated solely by the button icon.

### Pause Implementation (Player)

- **D-04:** Pause = set GStreamer pipeline to `NULL` (kills the connection). Resume = call `play()` again on the same station. No `Gst.State.PAUSED` — radio servers drop HTTP connections after a short idle period, making PAUSED unreliable.
- **D-05:** `_current_station` is NOT cleared on pause. It is only cleared on stop (existing behavior).
- **D-06:** A `_paused_station` (or equivalent flag) tracks the paused station so resume can call `play()` with the right station without relying on external state.

### Stop Button

- **D-07:** Stop behavior unchanged — calls `player.stop()`, clears `_current_station`, hides now-playing panel. Pause state is implicitly reset when stop is called (no explicit cleanup needed; calling stop from paused is a no-op from the user's perspective).

### MPRIS2 Scope

- **D-08:** Implement MPRIS2 org.mpris.MediaPlayer2.Player interface on the session D-Bus with:
  - `PlayPause` — toggles pause/play
  - `Stop` — calls existing stop
  - Read-only metadata: station name (as `xesam:title`), current ICY track title (as `xesam:artist` or `xesam:album`), artwork URL if available
- **D-09:** `Next` and `Previous` raise `NotSupported` / do nothing — radio has no track navigation.
- **D-10:** `CanGoNext`, `CanGoPrevious` = False. `CanPlay`, `CanPause`, `CanControl` = True when a station is selected.

### Claude's Discretion

- D-Bus service name (e.g., `org.mpris.MediaPlayer2.MusicStreamer`)
- Exact MPRIS2 property stubs required vs optional (Shuffle, LoopStatus, Rate — all read-only False/1.0)
- Whether to use `dbus-python`, `pydbus`, or `gi.repository.Gio` for the D-Bus binding
- How to handle MPRIS2 metadata update when ICY title changes mid-stream

</decisions>

<specifics>
## Specific Ideas

No specific references — open to standard GTK4/GLib D-Bus approaches.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs — requirements are fully captured in decisions above.

### Requirements source
- `.planning/REQUIREMENTS.md` §CTRL-01, §CTRL-02 — acceptance criteria for pause button and MPRIS2 integration

### Key source files
- `musicstreamer/player.py` — `play()`, `stop()`, GStreamer pipeline; pause must extend this module
- `musicstreamer/ui/main_window.py` — `controls_box`, `star_btn`, `stop_btn`, `_current_station`, `_play_station()`, `_stop()`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `controls_box` (Gtk.Box, horizontal, spacing=6): existing container — new pause button appends here
- `stop_btn`: pattern to follow for pause button (icon-only, `suggested-action` CSS, `set_sensitive()`)
- `player.play(station, on_title)`: called on resume — passes station + title callback

### Established Patterns
- Player state is tracked via `_current_station` in `main_window.py` (not in `player.py`)
- Button sensitivity toggled with `stop_btn.set_sensitive(False/True)` — pause button follows same pattern
- Icon names follow GNOME symbolic icon spec (e.g., `media-playback-stop-symbolic`)

### Integration Points
- `_play_station(st)`: resume calls this with the paused station
- `_stop()`: must set `_paused = False` equivalent before returning (or just let existing logic handle it)
- MPRIS2 D-Bus object connects to main_window methods for PlayPause/Stop callbacks
- ICY title callback (`on_title`) feeds MPRIS2 metadata updates

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 20-os-media-keys-integration*
*Context gathered: 2026-04-05*
