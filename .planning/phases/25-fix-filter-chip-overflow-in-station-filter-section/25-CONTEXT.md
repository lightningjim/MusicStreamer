# Phase 25: Fix filter chip overflow in station filter section - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the provider and tag filter chips in the main window filter bar that overflow horizontally via ScrolledWindow when many providers/tags exist. Replace with FlowBox wrapping to prevent overflow past adjacent buttons (Add Station, Edit, Clear).

</domain>

<decisions>
## Implementation Decisions

### Overflow Approach
- **D-01:** Use FlowBox wrapping (same pattern as phase 24 edit dialog fix). Replace both `ScrolledWindow` + horizontal `Gtk.Box` containers with `Gtk.FlowBox`. No max height constraint — chips wrap freely.

### Layout / Grouping
- **D-02:** Keep provider chips and tag chips in separate FlowBoxes. Maintains the current two-row visual grouping but with wrapping instead of horizontal scroll.

### Visual Appearance
- **D-03:** Claude's Discretion — match the existing chip style (ToggleButtons) and spacing. Follow the phase 24 FlowBox configuration (8px column spacing, 4px row spacing, hexpand=False).

</decisions>

<canonical_refs>
## Canonical References

No external specs — requirements fully captured in decisions above. Phase 24 CONTEXT.md and SUMMARY.md document the FlowBox pattern to follow.

- `.planning/phases/24-fix-tag-chip-scroll-overlapping-buttons-in-edit-dialog/24-01-SUMMARY.md` — FlowBox implementation reference from edit dialog

</canonical_refs>

<code_context>
## Existing Code Insights

### Files to Modify
- `musicstreamer/ui/main_window.py:210-230` — Provider and tag chip containers: two `Gtk.ScrolledWindow` with horizontal `Gtk.Box` children, inside a vertical `chip_container`

### Established Patterns
- Phase 24 established FlowBox wrapping for chips: `Gtk.FlowBox` with `SelectionMode.NONE`, 8px column spacing, 4px row spacing, `hexpand=False`
- Filter bar uses `filter_box` (horizontal) containing: Add Station, Edit, chip_container (vertical), Clear
- `_rebuild_provider_chips` and `_rebuild_tag_chips` methods iterate get_first_child/remove/append to rebuild chips
- `_rebuilding` flag prevents spurious filter updates during bulk chip mutations

### Integration Points
- `_on_provider_chip_toggled` and `_on_tag_chip_toggled` handlers on each ToggleButton
- `_rebuild_provider_chips` at line 385 and `_rebuild_tag_chips` at line 401
- `_provider_scroll` and `_tag_scroll` referenced in build and rebuild methods

</code_context>

<specifics>
## Specific Ideas

No specific requirements — follow the phase 24 FlowBox pattern.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 25-fix-filter-chip-overflow-in-station-filter-section*
*Context gathered: 2026-04-08*
