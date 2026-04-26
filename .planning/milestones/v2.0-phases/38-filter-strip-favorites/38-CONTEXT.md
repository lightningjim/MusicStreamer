# Phase 38: Filter Strip + Favorites - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Add search/filter functionality and a favorites system to the station panel. A user can type in a search box to filter stations in real time, select provider/tag chips to narrow results, toggle between Stations and Favorites views, star tracks from the now-playing panel, and star stations from the station list. All work builds on Phase 37's `StationListPanel` and `NowPlayingPanel`.

Out of scope for Phase 38 (explicit cut-lines — DO NOT PULL FORWARD):
- EditStationDialog and edit icon on now-playing → Phase 39 (UI-05)
- Stream picker dropdown → Phase 39 (UI-13)
- DiscoveryDialog, ImportDialog → Phase 39 (UI-06, UI-07)
- AccountsDialog, cookie import, accent color, hamburger menu → Phase 40 (UI-08..UI-11)

</domain>

<decisions>
## Implementation Decisions

### Search + Filter Interaction
- **D-01:** Search text and chip filters compose with **AND logic**. Typing "drone" with "SomaFM" chip active shows only SomaFM stations matching "drone". Matches v1.5 behavior.
- **D-02:** Provider and tag chips **auto-populate from station DB data**. Distinct `provider_name` values generate provider chips; distinct values from `Station.tags` (comma-separated) generate tag chips. No manual chip management.
- **D-03:** Multi-select logic: **OR within dimension, AND between dimensions**. Selecting "SomaFM" + "DI.fm" in the provider row shows both providers. Adding a "chill" tag chip further narrows to only chill stations from those two providers. Matches ROADMAP success criterion #2.
- **D-04:** Filter implementation uses `QSortFilterProxyModel` layered on top of the existing `StationTreeModel` (Phase 37 D-01 designed for this). Search text applies to station name; chip selections apply to provider/tags columns.

### Stations/Favorites Toggle
- **D-05:** A **segmented control** (`[Stations | Favorites]`) sits at the top of the station panel. Clicking toggles the list content inline below.
- **D-06:** The Favorites view has **two sections**: (a) **Favorite Stations** at the top — stations the user has starred, shown as a flat list; (b) **Favorite Tracks** below — flat chronological list (newest first) showing "Track Title — Station Name" per row with a trash icon to remove. Both sections are separate from the main station tree.
- **D-07:** Favorite stations are stored via a new mechanism — either a boolean `is_favorite` column on the stations table or a separate `favorite_stations` table. Planner picks the simpler approach. Starring a station in the tree adds it to the Favorite Stations section; unstarring removes it.

### Star Button Behavior
- **D-08:** **Track star button** on the now-playing panel (at the `# Plan 38: insert star button here` comment marker). Saves current ICY title + station name + provider name + genre (from last iTunes lookup) using the existing `repo.add_favorite()` API. Star icon toggles: filled = favorited, outline = not. Check via `repo.is_favorited(station_name, track_title)` on each title change.
- **D-09:** **Station star button** on each station row in the tree view (or as a hover/context action). Stars/unstars the station itself (separate from track favorites). Same icon idiom — filled star = favorited station.
- **D-10:** Visual feedback: icon toggles immediately + brief toast ("Saved to favorites" / "Removed from favorites") via the existing toast system.
- **D-11:** Star button is disabled (or hidden) when no station is playing / no ICY title is available (for track star). Station star is always available on station rows.

### Filter Strip Layout
- **D-12:** Filter strip sits **above the tree view, below the segmented control**. Layout order top-to-bottom: Segmented control → Search box → Provider chip row → Tag chip row → Tree view (or Favorites view).
- **D-13:** Chip rows use a **FlowLayout** (wrapping layout) so chips wrap to new lines on narrow windows. Matches ROADMAP success criterion #2. Qt doesn't ship a FlowLayout natively — use the Qt example FlowLayout or implement a simple one.
- **D-14:** A "Clear all" action (small X button or link) resets search text and deselects all chips. Individual chips toggle on click.
- **D-15:** Filter strip is **visible in Stations mode only**. When toggled to Favorites, the filter strip hides (favorites have their own simpler view).

### Claude's Discretion
- Exact chip styling (rounded rectangle, selected state color, etc.) — UI-SPEC will pin this down
- Whether search box has a clear (X) button inside it or relies on backspace
- Chip ordering within rows (alphabetical, by station count, etc.)
- Whether the segmented control uses `QButtonGroup` + styled `QPushButton`s or a custom widget
- Empty state text for favorites when no tracks/stations are starred

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + Requirements
- `.planning/ROADMAP.md` § "Phase 38: Filter Strip + Favorites" — goal, success criteria
- `.planning/REQUIREMENTS.md` § UI-03 (filter strip), UI-04 (favorites view)

### Phase 37 output to build on
- `musicstreamer/ui_qt/station_list_panel.py` — `StationListPanel` with tree + recently played; filter strip inserts here
- `musicstreamer/ui_qt/station_tree_model.py` — `StationTreeModel(QAbstractItemModel)` ready for `QSortFilterProxyModel` layering
- `musicstreamer/ui_qt/now_playing_panel.py` — has `# Plan 38: insert star button here` at line 173
- `musicstreamer/ui_qt/main_window.py` — signal wiring patterns established
- `musicstreamer/ui_qt/toast.py` — `ToastOverlay` for star feedback toasts

### Data layer (stable from v1.5)
- `musicstreamer/repo.py` — `add_favorite()`, `remove_favorite()`, `list_favorites()`, `is_favorited()` — track favorites API ready
- `musicstreamer/models.py` — `Station.tags` (comma-separated string), `Station.provider_name`, `Favorite` dataclass
- `musicstreamer/repo.py` — `list_stations()`, `list_providers()` — for auto-populating chips

### External specs (researcher should consult)
- PySide6 `QSortFilterProxyModel` — for filtering the station tree
- Qt FlowLayout example — for wrapping chip rows
- PySide6 `QButtonGroup` — for segmented control implementation

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`StationTreeModel`** — custom `QAbstractItemModel` with `refresh(stations)` and `station_for_index(idx)`. `QSortFilterProxyModel` layers on top without modifying the model.
- **`repo.list_favorites()`** — returns `List[Favorite]` with `station_name`, `provider_name`, `track_title`, `genre`, `created_at`.
- **`repo.is_favorited(station_name, track_title)`** — boolean check for star toggle state.
- **`repo.list_providers()`** — returns `List[Provider]` for populating provider chips.
- **`Station.tags`** — comma-separated string; split on `,` to get distinct tag values across all stations.
- **Toast system** — `MainWindow.show_toast(text)` ready for star feedback.

### Established Patterns
- Bound-method signal slots (QA-05) — no self-capturing lambdas
- `QIcon.fromTheme("name", QIcon(":/icons/name.svg"))` fallback pattern
- `icons.qrc` + `icons_rc.py` regeneration for new SVGs

### Integration Points
- `StationListPanel` — insert segmented control, search box, and chip rows above the tree
- `NowPlayingPanel` — insert star button at the marked location (line 173)
- `MainWindow` — wire star button signals, favorites view toggle

</code_context>

<specifics>
## Specific Ideas

- User wants **station favorites** in addition to track favorites — starred stations appear at top of station list under "Favorites" heading. Same star icon idiom as track favorites.
- User selected all recommended options — signals continued "port faithfully, keep it simple" philosophy from Phase 37.
- FlowLayout for chips is the one non-trivial widget addition — everything else layers on existing patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 38-filter-strip-favorites*
*Context gathered: 2026-04-12*
