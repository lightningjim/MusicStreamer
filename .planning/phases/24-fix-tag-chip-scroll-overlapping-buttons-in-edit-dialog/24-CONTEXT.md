# Phase 24: Fix tag chip scroll overlapping buttons in edit dialog - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the tag chip horizontal scroll in the edit dialog that overflows and overlaps adjacent buttons/controls. The ScrolledWindow has no max width constraint and can extend beyond the dialog form column.

</domain>

<decisions>
## Implementation Decisions

### Overflow Behavior
- **D-01:** Claude's Discretion — choose the best overflow approach for the existing dialog layout. Options considered: constrain to dialog width with horizontal scroll, or wrap to multiple lines with FlowBox.

### Visual Appearance
- **D-02:** Claude's Discretion — choose what fits the existing Adwaita dialog style. Options considered: fix overflow only (keep ToggleButtons), or restyle with pill-shape chips.

</decisions>

<canonical_refs>
## Canonical References

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Files to Modify
- `musicstreamer/ui/edit_dialog.py:226-258` — Tag chip panel: `Gtk.Box` (horizontal) inside `Gtk.ScrolledWindow` with `AUTOMATIC/NEVER` scroll policy, no max width set

### Established Patterns
- Edit dialog uses `Gtk.Grid` for form layout (column 0 = labels, column 1 = inputs)
- Tags box is at grid row 3, column 1
- `chip_scroll` has margins (8px start/end, 4px top/bottom) and min content height 36px
- Chips are `Gtk.ToggleButton` in a horizontal `Gtk.Box` with 8px spacing

### Integration Points
- `_on_tag_chip_toggled` handler on each ToggleButton
- `_rebuild_chips` method reconstructs the chip box on tag changes
- `new_tag_entry` sits below the chip scroll in a vertical `tags_box`

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 24-fix-tag-chip-scroll-overlapping-buttons-in-edit-dialog*
*Context gathered: 2026-04-07*
