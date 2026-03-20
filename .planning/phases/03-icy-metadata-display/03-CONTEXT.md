# Phase 3: ICY Metadata Display - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the GStreamer TAG bus to a redesigned now-playing panel that shows the current track title and station logo. The window is split into two zones: a compact player panel at the top and the station list below. Cover art (Phase 4) lives in the right slot of the same panel but is out of scope here — only the station logo (left slot) and track title (center) are delivered in this phase.

</domain>

<decisions>
## Implementation Decisions

### Window layout
- Two-zone layout: now-playing panel (~120px fixed height) on top, station list + filter controls below
- Inspired by the Winamp model: compact player panel above, playlist below
- `Adw.ToolbarView` top bars: HeaderBar → now-playing panel → filter strip → station list (content)

### Now-playing panel structure
- Three columns: `[96px station logo] | [center: track title + station name + Stop button] | [96px cover art placeholder]`
- Panel is always visible at full height, even when nothing is playing (idle state shows placeholder icons and "Nothing playing" text)
- Stop button moves from the HeaderBar into the center column of this panel

### HeaderBar
- SearchEntry only (centered, as established in Phase 2)
- Add Station and Edit buttons move to the filter strip (left side of the existing filter bar)
- HeaderBar loses the Stop button pack_end — Stop is now in the now-playing panel

### Filter strip changes
- Add Station button and Edit button added to the left of the filter strip
- Existing layout: `[Add] [Edit] [Provider ▼] [Tag ▼] [spacer] [Clear]`

### Station logo
- Displayed in the left slot of the now-playing panel when a station is playing
- Source: `station.station_art_path` (already on the Station model)
- Loaded as a `Gtk.Picture` or `Gtk.Image` sized to 96×96px, 1:1 aspect ratio
- Fallback when `station_art_path` is None or file missing: `audio-x-generic-symbolic` icon at the same size
- Cleared/reset to fallback icon when playback stops

### Cover art placeholder (right slot)
- A 96×96px placeholder (`audio-x-generic-symbolic`) for the slot Phase 4 will fill
- No functionality in this phase — just the structural widget so Phase 4 can swap it

### GStreamer TAG handling
- Add `message::tag` to the Player bus watch alongside the existing `message::error`
- Read `Gst.TAG_TITLE` from the TagList; ignore all other tags
- Call the existing `on_title(title)` callback with the extracted title
- If `Gst.TAG_TITLE` is not present in a TAG message, ignore that message (don't clear the current title)

### on_title callback
- Reuse the existing `on_title` callback pattern — no new callback needed
- `MainWindow._play_station` already passes `on_title=lambda t: self.now_label.set_text(...)` — update this lambda to update the new panel's title label instead

### YouTube / no-ICY fallback
- `_play_youtube` already calls `on_title(station.name)` — no change needed
- Station name as title fully satisfies NOW-03

### Claude's Discretion
- Exact GTK widget types for the panel (Gtk.Box, Adw.Bin, or a custom composite)
- Precise margin/spacing/padding values for the 120px panel
- Whether to use Gtk.Picture or Gtk.Image for the logo slot
- Animation or transition when track title updates (or none — simple set_text is fine)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — NOW-01 through NOW-04 acceptance criteria
- `.planning/ROADMAP.md` — Phase 3 success criteria (4 specific scenarios)

### Existing code (read before modifying)
- `musicstreamer/player.py` — current Player class; `_set_uri`, `_play_youtube`, `on_title` callback pattern; bus only has `message::error` — need to add `message::tag`
- `musicstreamer/ui/main_window.py` — current window layout; `self.now_label`, `_play_station`, `_stop`, `add_btn`, `edit_btn`, `stop_btn` all need relocation
- `musicstreamer/models.py` — `Station.station_art_path` and `Station.album_fallback_path` fields
- `musicstreamer/assets.py` — `copy_asset_for_station()` and path helpers used when station art is present

No external ADRs or design docs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Player.on_title` callback — already threaded through `play()`, `_set_uri()`, `_play_youtube()`; adding TAG support means calling it from the bus handler with the same signature
- `Station.station_art_path` — already on the model and stored in SQLite; no schema changes needed
- `MainWindow.shell` (Adw.ToolbarView) — `add_top_bar()` used for HeaderBar and filter strip; now-playing panel fits as another top bar

### Established Patterns
- GStreamer bus signal watch: `bus.add_signal_watch()` + `bus.connect("message::tag", handler)` — mirrors existing `message::error` pattern
- GTK signal-based wiring: `widget.connect(...)` — consistent throughout
- `_stop()` and `_play_station()` are the two call sites that need updating for the new panel

### Integration Points
- `Player.__init__`: add `bus.connect("message::tag", self._on_gst_tag)` alongside existing error handler
- `Player.play()`: `on_title` signature unchanged — just add TAG bus handler that calls it
- `MainWindow.__init__`: new now-playing panel inserted as second `add_top_bar()` call; existing `now_label` replaced by panel's title label; `stop_btn`, `add_btn`, `edit_btn` positions change
- `MainWindow._play_station()`: update `on_title` lambda to set panel title label + load station logo
- `MainWindow._stop()`: clear panel title to "Nothing playing", reset logo to fallback icon

</code_context>

<specifics>
## Specific Ideas

- "Winamp layout" — compact player panel on top, station list (playlist) below. The panel should feel like a focused playback widget, not just a status bar.
- The cover art placeholder (right slot) should be structurally identical to the logo slot so Phase 4 can swap in real art with minimal changes.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-icy-metadata-display*
*Context gathered: 2026-03-19*
