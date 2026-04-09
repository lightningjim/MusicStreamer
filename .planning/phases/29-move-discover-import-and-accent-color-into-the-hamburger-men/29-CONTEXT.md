# Phase 29: Move Discover, Import, and Accent Color into the Hamburger Menu - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Move the Discover, Import, and Accent Color buttons from the header bar into the existing hamburger `Gio.Menu`. The header bar becomes search entry + hamburger button only. No new features — purely a UI reorganization.

</domain>

<decisions>
## Implementation Decisions

### Menu Item Ordering
- **D-01:** Feature-grouped layout with a section separator. Top section (station actions): "Discover Stations…", "Import Stations…". Bottom section (settings): "Accent Color…", "YouTube Cookies…". Use `Gio.Menu` section grouping for the separator.

### Labels & Icons
- **D-02:** Text-only menu items, no icons. Standard GNOME hamburger menu style.
- **D-03:** Labels with ellipsis to indicate dialogs: "Discover Stations…", "Import Stations…", "Accent Color…", "YouTube Cookies…".

### Header Bar Cleanup
- **D-04:** After moving the 3 buttons, the header bar contains only the search entry (title widget) and the hamburger `Gtk.MenuButton`. Remove the `discover_btn`, `import_btn`, and `accent_btn` button creation and `pack_end` calls entirely.

### Implementation Approach
- **D-05:** Each moved action becomes a `Gio.SimpleAction` on the app, connected to the existing `_open_discovery`, `_open_import`, and `_open_accent_dialog` methods. Same pattern already used for "YouTube Cookies…" (`app.open-cookies`).

### Claude's Discretion
- Action naming convention (e.g., `app.open-discovery`, `app.open-import`, `app.open-accent`)
- Whether to group action registration in a helper method or keep inline

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase - Header bar and menu
- `musicstreamer/ui/main_window.py` lines 29-69 — Header bar construction, existing hamburger menu with `Gio.Menu`, `Gio.SimpleAction` pattern for "YouTube Cookies…"
- `musicstreamer/ui/main_window.py` lines 46-58 — Discover, Import, Accent button creation and `pack_end` calls (to be removed)
- `musicstreamer/ui/main_window.py` lines 1066-1077 — `_open_accent_dialog`, `_open_discovery`, `_open_import` handler methods (to be reused as action callbacks)

### Codebase - Dialog classes
- `musicstreamer/ui/accent_dialog.py` — AccentDialog opened by accent action
- `musicstreamer/ui/discovery_dialog.py` — DiscoveryDialog opened by discover action
- `musicstreamer/ui/import_dialog.py` — ImportDialog opened by import action

### Prior context
- `.planning/phases/19-custom-accent-color/19-CONTEXT.md` — D-07: original accent button placement (being moved)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Gio.SimpleAction` + `Gio.Menu.append()` pattern already established for "YouTube Cookies…" action — exact same pattern for 3 new items
- Existing handler methods (`_open_discovery`, `_open_import`, `_open_accent_dialog`) need only minor signature adjustment for action callback `(action, param)` vs button callback `(*_)`

### Established Patterns
- Actions registered on `app` via `app.add_action()`, menu items reference `"app.action-name"`
- `Gio.Menu` sections created via `Gio.Menu()` subsections appended to a parent menu

### Integration Points
- `_build_station_list_panel()` in `main_window.py` — header bar construction (lines 29-69)
- `__main__.py` `do_activate()` — if any app-level action registration is needed

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 29-move-discover-import-and-accent-color-into-the-hamburger-men*
*Context gathered: 2026-04-09*
