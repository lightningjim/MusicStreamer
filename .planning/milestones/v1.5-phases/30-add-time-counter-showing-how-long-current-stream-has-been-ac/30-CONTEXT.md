# Phase 30: Add time counter showing how long current stream has been actively playing - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Display an elapsed time counter in the now-playing panel showing how long the current stream has been actively playing. Pause-aware, resets on station change, hidden when nothing is playing. No new features beyond the timer display.

</domain>

<decisions>
## Implementation Decisions

### Counter Placement
- **D-01:** New label row between `station_name_label` and `controls_box` in the center column of the now-playing panel. Contains a small timer icon on the left and the elapsed time text to its right.
- **D-02:** Use a horizontal `Gtk.Box` with a `Gtk.Image` (icon) and `Gtk.Label` (time text) to compose the timer row. Icon: `timer-symbolic` or `hourglass-symbolic` (whichever is available in the icon theme).

### Timer Behavior
- **D-03:** Timer pauses when stream is paused (`_toggle_pause`), resumes on unpause. Uses accumulated elapsed seconds, not wall-clock difference.
- **D-04:** Timer resets to 0:00 on station change (`_play_station` with a new station). Stream failover (same station, different stream) does NOT reset — counter continues.
- **D-05:** Timer is hidden (`set_visible(False)`) when nothing is playing (stopped state). Shows `0:00` immediately when a new station starts, then ticks up.
- **D-06:** Use `GLib.timeout_add_seconds(1, callback)` to tick every second. Callback returns `True` while playing (keeps ticking) or `False` when stopped (removes source). Re-added on play.

### Display Format
- **D-07:** Adaptive format: `M:SS` for 0–59:59, `H:MM:SS` for 1:00:00+. No leading zero on hours or first minutes digit.
- **D-08:** Uses `dim-label` CSS class on both the icon and the time label — matches the station name label styling. Subtle, not distracting.

### Claude's Discretion
- Whether to store elapsed seconds as an int on `MainWindow` or create a small helper
- Exact icon name resolution (try `timer-symbolic` first, fall back to `hourglass-symbolic`)
- Whether to use `Gtk.Image.new_from_icon_name` or set via `set_from_icon_name`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase — now-playing panel
- `musicstreamer/ui/main_window.py` lines 81-212 — Now-playing panel construction, center column layout (title_label, station_name_label, controls_box, volume_slider)
- `musicstreamer/ui/main_window.py` lines 119-130 — title_label and station_name_label pattern (Gtk.Label with dim-label, ellipsize, xalign)

### Codebase — play/pause/stop state management
- `musicstreamer/ui/main_window.py` `_play_station()` — sets `_current_station`, starts playback
- `musicstreamer/ui/main_window.py` `_toggle_pause()` — pause/unpause logic, `_paused` flag
- `musicstreamer/ui/main_window.py` `_stop()` — clears `_current_station`, resets UI

### Codebase — GLib timer pattern
- `GLib.timeout_add_seconds(interval, callback)` — standard GTK periodic callback pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `dim-label` CSS class already used on `title_label` and `station_name_label` — same class for timer
- Center column `Gtk.Box(orientation=VERTICAL, spacing=4)` — timer row inserts between station_name_label and controls_box
- `_paused` boolean flag already tracks pause state — timer callback checks this

### Established Patterns
- Labels: `Gtk.Label()` with `add_css_class("dim-label")`, `set_xalign(0)`, `set_visible(False)` initial state
- State tracking: boolean flags on `self` (`_paused`, `_current_station`)
- Periodic updates: no existing `GLib.timeout_add_seconds` pattern in the codebase — this will be the first

### Integration Points
- Center column in now-playing panel (line ~172): insert timer row before `controls_box`
- `_play_station()`: start/reset timer
- `_toggle_pause()`: pause/resume timer
- `_stop()`: stop and hide timer

</code_context>

<specifics>
## Specific Ideas

- Small timer icon to the left of the elapsed time text (user request)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 30-add-time-counter-showing-how-long-current-stream-has-been-ac*
*Context gathered: 2026-04-09*
