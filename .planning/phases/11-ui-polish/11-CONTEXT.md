# Phase 11: UI Polish - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Visual refinement of the existing interface: rounded corners, subtle gradients, and improved spacing throughout. No new capabilities — purely aesthetic improvements to existing widgets.

Requirements: UI-01, UI-02, UI-03, UI-04

</domain>

<decisions>
## Implementation Decisions

### Now-playing panel (UI-01, UI-04)
- **D-01:** Keep the panel as a flat `Gtk.Box` — no card border, no frame widget
- **D-02:** Increase internal whitespace/padding: more `margin_top/bottom` and `margin_start/end` on the panel box itself
- **D-03:** Rounded corners on the panel via CSS (not structural widget change)

### Color treatment (UI-02)
- **D-04:** Apply Adwaita secondary surface color as panel background (less harsh than default window background)
- **D-05:** Add a subtle `linear-gradient` on the panel background to reduce flat/plain appearance — not dramatic, just enough to break the flatness
- **D-06:** Implement both effects via `Gtk.CssProvider` loaded at app startup — no custom widget subclassing

### Station list row padding (UI-03)
- **D-07:** Subtle bump only — single increment of padding on `Adw.ActionRow` rows (4–6px additional vertical padding), not a dramatic height increase

### Claude's Discretion
- Exact gradient direction and color stops (keep it subtle — user wants "less flat" not decorative)
- Exact padding pixel values within the "subtle bump" intent
- Whether to apply CSS globally via app-level provider or per-widget via class names
- CSS class naming conventions

</decisions>

<specifics>
## Specific Ideas

- "A mix — literal gradient to make it less flat AND softer secondary surface" — the two effects are complementary, both should be applied to the now-playing panel
- Row padding: "a single bump sounds good" — minimal, not a dramatic change

</specifics>

<canonical_refs>
## Canonical References

No external specs — requirements are fully captured in decisions above.

### Relevant source files
- `musicstreamer/ui/main_window.py` — Now-playing panel construction (lines 38–128), filter strip, `Adw.ToolbarView` shell layout
- `musicstreamer/ui/station_row.py` — `Adw.ActionRow` row construction with 48px art prefix
- `.planning/REQUIREMENTS.md` — UI-01 through UI-04 acceptance criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Gtk.CssProvider` — not yet instantiated anywhere; clean slate for custom CSS
- `Adw.ActionRow` in `StationRow` — target for padding increase (UI-03)
- `panel` (`Gtk.Box`) in `MainWindow.__init__` — target for gradient + whitespace (UI-02, UI-04)

### Established Patterns
- No CSS provider pattern exists yet — new code needed in `__main__.py` or `MainWindow.__init__` to load provider via `Gtk.StyleContext.add_provider_for_display`
- Adwaita utility classes (`.card`, `.dim-label`) are already used — CSS class approach is consistent with existing style

### Integration Points
- CSS loaded at `Adw.Application` startup so it applies globally
- Panel box needs a CSS class name added so the custom gradient/surface rule targets it specifically
- `StationRow` `Adw.ActionRow` needs a CSS class or the rule targets all `actionrow` widgets (acceptable if consistent)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 11-ui-polish*
*Context gathered: 2026-03-24*
