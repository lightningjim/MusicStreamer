# Phase 7: Station List Restructuring - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the flat station list with a provider-grouped collapsible list, and add a "Recently Played" section above all provider groups showing the last N played stations (default 3, configurable). Filtering and playback behavior are adjusted to work correctly with the new structure. The filter bar dropdowns and multi-select are NOT changed here — that is Phase 8.

</domain>

<decisions>
## Implementation Decisions

### Group header widget
- **D-01:** Use `Adw.ExpanderRow` for provider group headers — native Libadwaita collapsible row, consistent with the existing Adwaita HIG patterns in the app
- **D-02:** All provider groups collapsed by default on every launch (no state persistence for expand/collapse)
- **D-03:** Stations within each group are `Adw.ActionRow` entries (or equivalent styled row) preserving the existing logo + name display

### Stations with no provider
- **D-04:** Stations with `provider_id = NULL` appear in an "Uncategorized" group at the bottom of the list
- **D-05:** "Uncategorized" group is collapsed by default, same as all other groups

### Recently Played
- **D-06:** Recently Played section appears above all provider groups, always visible (not collapsible)
- **D-07:** Shows last N played stations, most recent first; default N = 3
- **D-08:** N is configurable — store in a config/settings location (existing `config.json` in `.planning/` is dev-only; use a user-facing config, e.g., a `settings` table in SQLite or a key in a JSON settings file in DATA_DIR)
- **D-09:** Recently Played persists across app restarts — add a `last_played_at` TEXT column to the `stations` table (ISO datetime, NULL = never played); on play, update it; query top-N by `last_played_at DESC WHERE last_played_at IS NOT NULL`
- **D-10:** Recently Played updates immediately after a station starts playing (not on stop)
- **D-11:** A station in Recently Played is fully playable from that row (same as a row in the grouped list)

### Filter bar interaction
- **D-12:** Provider filter active → switch to a flat (ungrouped) list showing only stations from the selected provider; grouping is suppressed because the user is already scoped to one provider
- **D-13:** Search text active, no provider filter → grouped view is preserved; non-matching rows are hidden within their groups (empty groups are hidden)
- **D-14:** Both provider filter AND search text active → flat list (provider filter always triggers flat mode regardless of search)
- **D-15:** Recently Played section is hidden when any filter is active (flat or grouped filtered view — the section is a browse affordance, not a search result)

### Claude's Discretion
- Exact widget type for station rows inside ExpanderRow (Adw.ActionRow vs custom StationRow subclass)
- Whether empty groups (all stations filtered out) are hidden or shown collapsed
- Settings storage mechanism for Recently Played count (SQLite `settings` table recommended for consistency with existing DB)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Station list and filtering
- `musicstreamer/ui/main_window.py` — `MainWindow`; `reload_list`, `_filter_func`, `_on_filter_changed`, `_rebuild_filter_state`; all require significant rework for grouped view
- `musicstreamer/ui/station_row.py` — existing `StationRow`; reuse or adapt for rows inside ExpanderRow

### Data model and repo
- `musicstreamer/repo.py` — `Repo.list_stations()` (ordered by provider then name); needs `update_last_played(station_id)` and `list_recently_played(n)` methods; schema migration for `last_played_at` column
- `musicstreamer/models.py` — `Station` dataclass; needs `last_played_at: Optional[str]` field

### Playback hook
- `musicstreamer/ui/main_window.py` — `_play_station`; must call `repo.update_last_played()` and refresh Recently Played section on play

### Settings storage (for configurable N)
- `musicstreamer/repo.py` — add `get_setting(key, default)` / `set_setting(key, value)` backed by a `settings` table, or use a simple JSON file in DATA_DIR; Claude's discretion on mechanism

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `StationRow` in `musicstreamer/ui/station_row.py` — existing row widget with logo + name; may be embeddable inside `Adw.ExpanderRow` as child rows
- `_rebuild_filter_state()` — already queries all providers from stations; can drive ExpanderRow group creation
- `repo.list_stations()` — already returns stations ordered by `COALESCE(p.name,''), s.name`; grouping in UI is straightforward iteration

### Established Patterns
- `Gtk.Stack` — used for logo/art fallback; same pattern applies to Recently Played section visibility (show/hide based on filter state)
- `GLib.idle_add` — mandatory for cross-thread UI updates; not directly needed here but keep in mind for any async refresh
- `self._rebuilding` flag — guards dropdown model rebuilds from triggering filter callbacks; analogous guard needed when rebuilding grouped list

### Integration Points
- `reload_list()` — currently clears and rebuilds all rows; must be restructured to build ExpanderRows per provider + Recently Played section
- `_on_filter_changed()` — must detect provider filter state and toggle between flat and grouped render modes
- `_play_station()` — add `repo.update_last_played(st.id)` call and trigger Recently Played section refresh
- `listbox.set_filter_func()` — may need to be replaced or supplemented; `Adw.ExpanderRow` children may not participate in ListBox filter func in the same way as top-level rows

</code_context>

<specifics>
## Specific Ideas

- Recently Played is a browse affordance — hide it entirely when filters are active so it doesn't clutter filtered results
- "Uncategorized" group behaves identically to named provider groups — collapsed by default, same visual treatment

</specifics>

<deferred>
## Deferred Ideas

- Configurable Recently Played count UI (settings dialog) — the default of 3 can be changed via config but no settings UI is in scope for this phase
- Recently Played section collapsibility — currently decided as always-visible; could be made collapsible in a later polish pass
- Phase 8: multi-select provider/tag filter chips replace the current dropdowns

</deferred>

---

*Phase: 07-station-list-restructuring*
*Context gathered: 2026-03-21*
