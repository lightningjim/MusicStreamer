# Phase 26: Fix broken Edit button next to Add Station - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove the broken standalone "Edit" button from the filter bar and add a pencil edit icon to the now-playing controls for editing the currently playing station.

</domain>

<decisions>
## Implementation Decisions

### Fix Strategy
- **D-01:** Remove the standalone "Edit" button from the filter bar entirely. It's broken (relies on `listbox.get_selected_row()` which doesn't find nested ExpanderRow children) and redundant with per-row edit icons.
- **D-02:** Add a pencil edit icon button to the now-playing controls_box (alongside star, pause, stop) that opens the station editor for the currently playing station.

### Now-Playing Edit Button
- **D-03:** The edit button should be visible/sensitive only when a station is currently playing or paused (same visibility logic as pause/stop buttons).
- **D-04:** Button uses `document-edit-symbolic` icon (same as per-row edit icons) and calls `_open_editor()` with the current station's ID.

### Filter Bar Layout
- **D-05:** Claude's Discretion — handle filter bar reflow after Edit button removal. The chip area already has `hexpand=True` so it should fill naturally.

### Cleanup
- **D-06:** Remove `_edit_selected()` method (line 969-972) since nothing will call it after the button is removed.

</decisions>

<canonical_refs>
## Canonical References

No external specs — requirements fully captured in decisions above.

- `.planning/phases/25-fix-filter-chip-overflow-in-station-filter-section/25-CONTEXT.md` — Current filter bar layout reference

</canonical_refs>

<code_context>
## Existing Code Insights

### Files to Modify
- `musicstreamer/ui/main_window.py:200-254` — Filter bar: remove `edit_btn` creation (line 203-204) and `filter_box.append(edit_btn)` (line 252)
- `musicstreamer/ui/main_window.py:126-151` — Now-playing controls_box: add edit button alongside star, pause, stop
- `musicstreamer/ui/main_window.py:969-972` — Remove `_edit_selected()` method

### Established Patterns
- Per-row edit buttons use `document-edit-symbolic` icon with `flat` CSS class (line 589-591)
- Controls_box uses `Gtk.Align.END` alignment, 6px spacing (line 126-127)
- `_current_station` tracks the playing station; `_paused_station` tracks paused station
- `_open_editor(station_id)` is the existing method to open the editor dialog

### Integration Points
- Edit button sensitivity should follow the same pattern as `pause_btn` and `stop_btn` — enabled when playing/paused, disabled otherwise
- `_current_station` and `_paused_station` provide the station ID for the editor

</code_context>

<specifics>
## Specific Ideas

User wants the edit icon in the now-playing section specifically to edit the currently playing station — a more useful location than a generic "edit selected" button in the filter bar.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 26-fix-broken-edit-button-next-to-add-station*
*Context gathered: 2026-04-08*
