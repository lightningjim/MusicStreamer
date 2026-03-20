# Phase 4: Cover Art - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Fetch track/album art from the ICY track title via the iTunes Search API and display it in the right slot (160×160) of the now-playing panel. The slot widget (`self.cover_placeholder`) already exists from Phase 3 — Phase 4 replaces it with a `Gtk.Stack` (same pattern as the logo slot) and populates it with real art. Cover art is not embedded in streams — it is fetched from iTunes based on ICY metadata. MusicBrainz fallback and persistent caching are v2 concerns.

</domain>

<decisions>
## Implementation Decisions

### ICY title parsing and search
- Always attempt a title-only iTunes search when the ICY string cannot be split into "Artist - Title" (i.e., no " - " separator found)
- When a clean "Artist - Title" split exists, search iTunes with both artist and title for better precision
- Skip the API call entirely for obvious junk titles: empty string, whitespace-only, "Advertisement", "Advert", "Commercial", "Commercial Break" (case-insensitive match)
- Show placeholder for skipped/junk titles without making an API call

### Art update behavior
- While a new iTunes request is in-flight, keep displaying the previous track's art (silent swap — no placeholder flash between tracks)
- When playback stops (user hits Stop), revert the right slot to the placeholder — consistent with how the logo slot behaves on stop

### Session-level dedup
- Track the last successfully fetched ICY string in memory (a simple `self._last_cover_icy` string)
- If a new TAG message arrives with the exact same ICY string as the last fetch, skip the API call
- Clear `_last_cover_icy` when playback stops (Stop button) so switching stations always fetches fresh art

### Claude's Discretion
- Exact iTunes Search API query parameters (`term`, `media=music`, `limit=1`, etc.)
- Whether to use `urllib` or `requests` for the HTTP call (prefer stdlib `urllib.request` to avoid adding a dependency)
- Thread/async strategy for the HTTP fetch (GLib.idle_add to update UI from background thread, consistent with Phase 3 TAG bus pattern)
- Image scaling approach (GdkPixbuf pre-scale to 160×160 before display, consistent with Phase 3 logo handling)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — NOW-05 and NOW-06 acceptance criteria (v1); NOW-V2-01 through NOW-V2-04 (v2, out of scope for this phase)
- `.planning/ROADMAP.md` — Phase 4 success criteria (3 specific scenarios)

### Existing code (read before modifying)
- `musicstreamer/ui/main_window.py` — `self.cover_placeholder` (right slot widget, lines ~93–97); `self.logo_stack` (the `Gtk.Stack` pattern to replicate for right slot); `_stop()` and `_play_station()` (call sites for reset and update)
- `musicstreamer/player.py` — `_on_gst_tag` handler and `GLib.idle_add` pattern for marshalling GStreamer bus signals to GTK main thread; `on_title` callback pattern
- `musicstreamer/models.py` — `Station.album_fallback_path` field (available as a fallback if iTunes returns no result — Claude's discretion whether to use it)
- `musicstreamer/assets.py` — `copy_asset_for_station()` and asset path helpers (for reference, not modification)

No external ADRs or design docs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `self.logo_stack` (Gtk.Stack with "fallback" and "logo" children) — identical pattern for the right slot; Phase 4 should replace `self.cover_placeholder` with `self.cover_stack` using the same structure
- `GLib.idle_add` in `_on_gst_tag` (player.py) — established pattern for updating GTK widgets from GStreamer's non-GTK thread; cover art HTTP fetch and image update must use same approach
- `GdkPixbuf` pre-scaling to 160×160 before `Gtk.Image.set_from_pixbuf` — already used for logo; reuse for cover art to avoid rendering artifacts

### Established Patterns
- `Gtk.Stack` with named children ("fallback", "logo") swapped via `set_visible_child_name()` — apply to right slot ("fallback", "art")
- `_stop()` resets logo stack to "fallback" — Phase 4 extends `_stop()` to also reset cover stack to "fallback" and clear `_last_cover_icy`
- `_play_station()` loads station logo — Phase 4 does NOT pre-load art here (art comes via TAG bus, not from station data)

### Integration Points
- `MainWindow.__init__`: replace `self.cover_placeholder` (single Gtk.Image) with `self.cover_stack` (Gtk.Stack with fallback + art children)
- `MainWindow._on_title` or a new `_on_cover_art(icy_string)` callback wired from the TAG bus handler: check dedup → skip junk → fetch iTunes → GLib.idle_add to update cover_stack
- `MainWindow._stop()`: reset `self.cover_stack` to "fallback", clear `self._last_cover_icy`
- `Player._on_gst_tag`: already fires on TAG messages — Phase 4 may read `Gst.TAG_ARTIST` alongside `Gst.TAG_TITLE` to assemble the search string

</code_context>

<specifics>
## Specific Ideas

- The right slot must structurally mirror the left slot — same `Gtk.Stack` pattern, same 160×160 size — so Phase 3's structural placeholder is simply upgraded in place.
- "Keep old art" during in-flight requests means users experience smooth art transitions on fast-rotating stations rather than a jarring placeholder flash.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-cover-art*
*Context gathered: 2026-03-20*
