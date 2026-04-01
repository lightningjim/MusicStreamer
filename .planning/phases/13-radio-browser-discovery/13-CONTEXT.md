# Phase 13: Radio-Browser Discovery - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a discovery dialog for browsing Radio-Browser.info stations. Users can search by name with live debounce, filter by tag or country via dropdowns, preview a station (temporarily replacing current playback), and save stations to their library using the station's network/homepage as provider name. Duplicate URLs are blocked with an error message.

</domain>

<decisions>
## Implementation Decisions

### Discovery Dialog Layout
- **D-01:** Discovery UI is a modal dialog (separate `Adw.Window`), consistent with the existing `EditStationDialog` pattern
- **D-02:** Results displayed as simple `Adw.ActionRow` list rows — station name as title, subtitle with country/tags/bitrate

### Search & Filter Behavior
- **D-03:** Live search with debounce (~500ms) — results update as user types, no submit button needed
- **D-04:** Tag and country filters are `Adw.ComboRow` dropdowns, pre-populated from the Radio-Browser API
- **D-05:** Search text and dropdown filters compose together when querying the API

### Preview Playback
- **D-06:** Preview temporarily replaces current playback. Closing the dialog auto-resumes the previously playing station.
- **D-07:** Each result row has a small play button icon to trigger preview (not row-click activation)

### Save-to-Library Flow
- **D-08:** Provider name is auto-assigned from the station's homepage/network metadata in the Radio-Browser response (not hardcoded "Radio-Browser")
- **D-09:** If a station with the same URL already exists in the library, block the save with an error message (not a silent skip)
- **D-10:** Save button per row (or save action) adds the station directly to the library — no intermediate edit dialog

### Claude's Discretion
- Exact Radio-Browser API endpoints and query parameter mapping (researcher should investigate)
- How to populate tag/country dropdowns (separate API calls vs extracted from results)
- ActionRow subtitle format (e.g., "US | Jazz, Blues | 128kbps" vs "Jazz · United States")
- Dialog size, spacing, and widget hierarchy
- How to handle Radio-Browser API errors or empty results (inline status page, toast, etc.)
- Whether the play-preview button shows a stop icon when that row is actively previewing
- How to extract provider/network name from Radio-Browser metadata (homepage domain, network field, etc.)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs — requirements fully captured in decisions above and REQUIREMENTS.md (DISC-01 through DISC-04).

### Codebase
- `musicstreamer/ui/edit_dialog.py` — Existing modal dialog pattern (Adw.Window subclass)
- `musicstreamer/ui/main_window.py` — Main window, playback integration, station list rendering
- `musicstreamer/player.py` — GStreamer playback engine (preview must use same engine)
- `musicstreamer/repo.py` — `create_station()` for saving to library, station URL uniqueness
- `musicstreamer/models.py` — Station and Provider dataclasses

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EditStationDialog` (Adw.Window): Modal dialog pattern — discovery dialog should follow same structure
- `player.py`: GStreamer playback — preview plays through same engine, need to save/restore state for resume
- `repo.create_station()`: Existing method to persist a new station to SQLite
- `Adw.ComboRow`: Already used in edit dialog for provider picker — reuse for tag/country dropdowns

### Established Patterns
- Modal dialogs are `Adw.Window` subclasses with `set_transient_for(main_window)`
- Station list uses `Adw.ExpanderRow` grouped by provider — saved Radio-Browser stations will appear in their provider group
- Playback state tracked via `_current_station` and `_last_cover_icy` on MainWindow

### Integration Points
- Discovery dialog opened from main window (toolbar button or menu item)
- Save action calls `repo.create_station()` then triggers `reload_list()` on main window
- Preview playback uses `player.play()` / `player.stop()` — main window needs to track "was playing before dialog" for auto-resume

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for Radio-Browser API integration.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 13-radio-browser-discovery*
*Context gathered: 2026-03-31*
