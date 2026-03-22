# Phase 8: Filter Bar Multi-Select - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the two `Gtk.DropDown` widgets (provider + tag) in the filter strip with multi-select chip controls. Users can select multiple providers and/or genres simultaneously; provider AND genre filters compose with AND logic. Clearing all selections returns the full grouped station list. The grouped list structure and Recently Played section from Phase 7 are not changed.

</domain>

<decisions>
## Implementation Decisions

### Filter widget
- **D-01:** Replace both `Gtk.DropDown` widgets with horizontally-arranged `Gtk.ToggleButton` chips — one chip per provider, one chip per tag
- **D-02:** Chips are always visible in the filter strip (no popover); strip scrolls horizontally if chip count overflows
- **D-03:** Each chip has a per-chip × suffix button; clicking × deselects that chip without requiring a toggle click
- **D-04:** The existing "Clear" button is retained for bulk reset (deselects all chips, clears search)

### Multi-provider list mode
- **D-05:** Provider filter active (any chip selected) → flat mode, same as Phase 7 D-12; no grouped-by-provider view when filtering
- **D-06:** Multiple providers selected → still flat; all matching stations from all selected providers in one flat list
- **D-07:** Tag filter applies in both flat and grouped modes (same as current behavior)

### Filter logic
- **D-08:** Provider chips compose with OR within providers (station matches if it belongs to any selected provider)
- **D-09:** Tag chips compose with OR within tags (station matches if it has any selected tag)
- **D-10:** Provider selection AND tag selection compose with AND (station must match at least one selected provider AND at least one selected tag)
- **D-11:** Clearing all chip selections returns to the full grouped view (same as Phase 7 no-filter state)

### Phase 7 compatibility
- **D-12:** Recently Played section hidden when any chip or search filter is active (Phase 7 D-15 still holds)
- **D-13:** `_any_filter_active()` updated to check chip selection state instead of dropdown index

### Claude's Discretion
- Exact widget for chip row (Gtk.ScrolledWindow + Gtk.Box vs Gtk.FlowBox)
- Spacing and visual styling of chips (keep consistent with existing filter strip margins)
- Whether provider and tag chips share one row or occupy separate rows

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Filter strip and list rendering
- `musicstreamer/ui/main_window.py` — `_rebuild_filter_state()`, `_render_list()`, `_rebuild_flat()`, `_rebuild_grouped()`, `_any_filter_active()`, `_on_filter_changed()`, `_on_clear()` — all require modification to replace DropDown with chip state
- `musicstreamer/ui/main_window.py` — `provider_dropdown` and `tag_dropdown` fields — these are replaced; all references must be removed or updated

### Filter utilities
- `musicstreamer/filter_utils.py` — `matches_filter()`, `normalize_tags()` — used by `_render_list()` for tag matching; may need adjustment for multi-select sets

### Data model (read-only reference)
- `musicstreamer/models.py` — `Station` dataclass; `provider_name`, `tags` fields used in filtering

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_rebuild_filter_state()` — already enumerates all providers and tags from the station list; same logic drives chip creation
- `_any_filter_active()` — boolean check; replace dropdown index checks with "any chip selected" checks
- `_on_clear()` — already resets dropdowns and calls `_on_filter_changed()`; extend to deselect all chips
- `matches_filter(s, search_text, provider, tag)` — currently single-value; may need a variant accepting sets

### Established Patterns
- `self._rebuilding` flag — guards filter state rebuilds from triggering callbacks; same pattern needed when building chip rows
- `Gtk.ToggleButton` — already available; no new widget types required

### Integration Points
- `filter_box` (Gtk.Box in `__init__`) — current container for dropdowns; chips replace the DropDown widgets in this box
- `_render_list()` — reads `provider_dropdown.get_selected()` and `tag_dropdown.get_selected()`; replace with chip selection state (e.g., sets of selected provider/tag strings)
- `_on_filter_changed()` — already the single callback for all filter changes; wire chip toggle signals here

</code_context>

<specifics>
## Specific Ideas

- Chips should be toggle buttons — clicking toggles selection; each chip also has a per-chip × to dismiss without re-clicking
- "All Providers" and "All Tags" header items are removed — chips represent individual values only; no selection = all shown

</specifics>

<deferred>
## Deferred Ideas

- Tag chip overflow handling / search within tags — if tag count becomes large in future, a popover may be warranted; defer
- Chip color coding by provider — visual enhancement only; Phase 11 if desired

</deferred>

---

*Phase: 08-filter-bar-multi-select*
*Context gathered: 2026-03-22*
