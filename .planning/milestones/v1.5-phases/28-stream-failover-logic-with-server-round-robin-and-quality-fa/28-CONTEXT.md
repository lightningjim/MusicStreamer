# Phase 28: Stream Failover Logic with Server Round-Robin and Quality Fallback - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

When a stream fails or the user has a quality preference, the player automatically tries the next stream in the station's list. This phase adds failover logic to the player, integrates the existing `get_preferred_stream_url()` for quality-based selection, adds toast notifications for failover events, and provides a manual stream picker in the now-playing controls.

</domain>

<decisions>
## Implementation Decisions

### Failover Trigger
- **D-01:** Failover triggers on GStreamer pipeline ERROR bus message (connection refused, 404, decode failure) OR timeout — if no audio data arrives within 10 seconds of play start, treat as failure and try next stream.
- **D-02:** Silence detection is out of scope — only error and timeout trigger failover.

### Retry Strategy
- **D-03:** Try every stream in the station's list exactly once. If all fail, stop playback and show error. No cycling/retrying.

### Stream Selection Order
- **D-04:** First stream selected via `get_preferred_stream_url()` — if user has a global preferred quality (hi/med/low), start with a matching stream. Fall back to position order if no preference set or no quality match.
- **D-05:** After the preferred/first stream fails, try remaining streams in position order (as configured in Manage Streams dialog). Predictable and user-controlled.

### User Feedback
- **D-06:** Show `Adw.Toast` notifications: "Stream failed — trying next..." on each failover attempt, and "All streams failed" when exhausted. Non-intrusive, auto-dismisses.

### Manual Stream Switching
- **D-07:** Stream picker menu button in the now-playing controls row (next to Edit/Star/Pause/Stop). Uses an antenna/signal-style icon. Opens a popover listing all streams by label + quality badge.
- **D-08:** Selecting a stream from the picker immediately switches playback to that stream. Does not affect the configured position order.

### Claude's Discretion
- Icon choice for stream picker button (antenna, signal, radio tower — whatever fits Adwaita icon set)
- Toast message wording and duration
- Timeout implementation mechanism (GLib.timeout_add vs GStreamer clock)
- Whether to show stream picker button only when station has 2+ streams (sensible default)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Player
- `musicstreamer/player.py` — Current `play()` hardcodes `streams[0].url`; `_on_gst_error` handles errors; `_play_youtube` for YT streams
- `musicstreamer/repo.py:196-206` — `get_preferred_stream_url()` already implemented but unused by player

### Data Model (from Phase 27)
- `musicstreamer/models.py` — `Station.streams: list[StationStream]` with position, quality, stream_type fields
- `musicstreamer/repo.py` — `list_streams()`, stream CRUD methods

### UI
- `musicstreamer/ui/main_window.py` — Now-playing panel layout, controls_box with Edit/Star/Pause/Stop buttons
- `musicstreamer/constants.py` — `QUALITY_PRESETS`, `QUALITY_SETTING_KEY`

### Phase 27 Context
- `.planning/phases/27-add-multiple-streams-per-station-for-backup-round-robin-and-/27-CONTEXT.md` — D-06 defined global preferred quality setting

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_preferred_stream_url(station_id, preferred_quality)` in repo.py — already queries by quality then falls back to position order; player just needs to call it
- `Adw.Toast` — used elsewhere in the app for notifications; established pattern
- GStreamer bus message handling — `_on_gst_error` already catches pipeline errors; extend for failover
- `settings` table — `get_setting("preferred_quality")` can store user's global quality preference

### Established Patterns
- `GLib.idle_add` for cross-thread UI updates (player runs GStreamer on bus callbacks)
- `GLib.timeout_add` for deferred actions (used in other GTK apps for timeouts)
- Controls box layout — horizontal Gtk.Box with icon buttons (edit, star, pause, stop)

### Integration Points
- `Player.play(station)` — main entry point; currently picks `streams[0].url`, needs failover-aware stream resolution
- `main_window._on_play()` — calls `player.play(station)`; needs to pass toast overlay reference or callback for failover notifications
- `main_window.controls_box` — where stream picker button gets added

</code_context>

<specifics>
## Specific Ideas

- The 10-second timeout matches the existing GStreamer buffer-duration constant (10s) — consistent tuning
- YouTube streams via mpv subprocess need different failover detection (process exit code instead of GStreamer bus)
- Stream picker popover should show the currently-playing stream highlighted/checked
- Hide stream picker button for stations with only 1 stream (no value in showing it)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 28-stream-failover-logic-with-server-round-robin-and-quality-fa*
*Context gathered: 2026-04-09*
