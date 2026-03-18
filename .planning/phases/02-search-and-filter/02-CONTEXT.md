# Phase 2: Search and Filter - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Add live name search and provider/tag dropdown filters to the station list. All three controls compose with AND logic — multiple active filters narrow the list simultaneously. A clear-all control resets to the full list. Playback, station editing, and all other features are untouched.

</domain>

<decisions>
## Implementation Decisions

### Search bar placement
- Always-visible `Gtk.SearchEntry` centered in the HeaderBar (not a toggling Adw.SearchBar)
- Full-width center position — like GNOME Software / Files, prominent and immediately usable
- No Ctrl+F toggle required — always there

### Filter controls layout
- Provider dropdown and tag dropdown live in a thin toolbar strip **below** the HeaderBar
- Both dropdowns side-by-side in the strip — always visible, keeps the header clean
- A **"Clear" button** appears in the filter strip when any filter is active (search text, provider selection, or tag selection)
- Clicking Clear resets all three controls simultaneously

### Zero-result state
- When the filtered list is empty: show a message ("No stations match your filters") with an inline "Clear filters" link/button
- Use `Adw.StatusPage` or a simple label — either is acceptable
- The empty state replaces the listbox content (not shown alongside it)

### Tag normalization
- Split tag strings on comma (`,`) and bullet (`•`), strip surrounding whitespace from each token
- Deduplicate case-insensitively (e.g. "Lofi" and "lofi" become one entry)
- Dropdown populated from all distinct normalized tags across all stations

### Claude's Discretion
- GTK4 filter mechanism (`Gtk.ListBox.set_filter_func` vs `Gtk.FilterListModel`) — use whichever is cleaner with the existing `Gtk.ListBox`
- Dropdown widget choice (`Gtk.DropDown` vs `Adw.ComboRow` in a list context)
- Exact styling of the toolbar strip (margin, spacing, padding)
- Sort order of dropdown entries (alphabetical is fine)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — FILT-01 through FILT-05 acceptance criteria
- `.planning/ROADMAP.md` — Phase 2 success criteria (5 specific test scenarios)

### Existing code (read before modifying)
- `musicstreamer/ui/main_window.py` — where search/filter controls will be added; current HeaderBar and ListBox setup
- `musicstreamer/ui/station_row.py` — `self.station` already set for filter_func use
- `musicstreamer/models.py` — `Station.tags`, `Station.provider_name` fields used by filter logic
- `musicstreamer/repo.py` — `list_stations()` is the data source; provider list derived from stations

No external ADRs or design docs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `StationRow.station` (full `Station` object) — already wired in Phase 1 specifically for filter_func use; no changes needed to StationRow
- `Repo.list_stations()` — returns all stations; provider list and tag vocabulary derived from this set
- `MainWindow.reload_list()` — existing list population; filter logic hooks in here or replaces it

### Established Patterns
- GTK signal-based wiring: `widget.connect("signal", handler)` — stay consistent
- `Adw.ToolbarView` with `add_top_bar()` for header layers — filter strip fits naturally as a second top bar or as content above the ScrolledWindow
- `Adw.ActionRow` used in StationRow — Adw widget style is established

### Integration Points
- `MainWindow.__init__`: add SearchEntry to HeaderBar center, add filter strip below
- `MainWindow.reload_list()` or a new `_apply_filter()` method: drives filter_func updates when any control changes
- Filter strip "Clear" button: connected to a method that resets SearchEntry text, both dropdowns to "All", then re-triggers filter

</code_context>

<specifics>
## Specific Ideas

- The "find a station in seconds" core value drove the always-visible search decision — no toggle friction
- Clear button only appears when a filter is active (not always visible)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-search-and-filter*
*Context gathered: 2026-03-18*
