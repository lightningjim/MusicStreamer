# Phase 19: Custom Accent Color - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

User can set a custom highlight/accent color from GNOME-style preset swatches or a hex input. Color is applied immediately at runtime via CSS injection and persisted in SQLite settings across sessions. No changes outside the accent color system (no theme switching, no per-station colors).

</domain>

<decisions>
## Implementation Decisions

### CSS Mechanism
- **D-01:** Inject `@define-color accent_bg_color #RRGGBB` via a dedicated `Gtk.CssProvider` at `STYLE_PROVIDER_PRIORITY_USER` priority. This is a *second* provider separate from the existing `_APP_CSS` provider in `__main__.py`. Full Libadwaita accent — affects suggested-action buttons, links, sliders, toggles, checkboxes, progress bars (same as system-wide accent).
- **D-02:** At app startup, load the persisted accent color from `repo.get_setting("accent_color", "#3584e4")` and inject immediately before `win.present()`. On color change, call `css_provider.load_from_string(...)` on the same provider instance — no need to remove/re-add it.

### Persistence
- **D-03:** Settings key: `"accent_color"`, stored as lowercase hex string (e.g., `"#3584e4"`). Default: `"#3584e4"` (Libadwaita standard blue). Uses existing `repo.get_setting()` / `repo.set_setting()` — no new persistence mechanism.

### Preset Palette
- **D-04:** 8 GNOME-style presets matching GNOME Settings display accent picker:
  - Blue: `#3584e4`
  - Teal: `#2190a4`
  - Green: `#3a944a`
  - Yellow: `#c88800`
  - Orange: `#ed5b00`
  - Red: `#e62d42`
  - Purple: `#9141ac`
  - Pink: `#c64d92`
- **D-05:** Hex input field allows custom color beyond presets. "Custom" is just the hex input — no separate swatch for it; the presets are swatches, the entry is how you go custom.

### Invalid Hex Handling
- **D-06:** Show inline error state on the hex entry (Adwaita `error` CSS class on the entry row) when the value is not a valid 3- or 6-digit hex. Previous color is preserved. No error dialog. Clear error indicator as soon as the user starts typing again.

### Entry Point
- **D-07:** A small palette/color icon button in the header bar (`header.pack_end()`), alongside existing Discover and Import buttons. Use icon `preferences-color-symbolic` or `color-select-symbolic` (whichever is available in the icon theme). Opens `AccentDialog` as a modal dialog.

### Claude's Discretion
- Whether to make the accent CSS provider a module-level singleton or instance variable on `App`
- Exact dialog layout (grid of swatches + separator + hex entry row)
- Whether hex entry uses `Adw.EntryRow` or plain `Gtk.Entry`
- Icon name for header button (resolve at implementation from available system icons)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase — CSS and settings
- `musicstreamer/__main__.py` — Existing `Gtk.CssProvider` pattern (`_APP_CSS`, `do_activate`) — second provider follows same `add_provider_for_display` call; lines 43–60
- `musicstreamer/repo.py` — `get_setting()` / `set_setting()` API (lines ~213–222); `settings` table schema (line ~68)
- `musicstreamer/constants.py` — Where to add `ACCENT_COLOR_DEFAULT = "#3584e4"` constant

### Codebase — header bar reference
- `musicstreamer/ui/main_window.py` — `_build_station_list_panel()` header bar construction (lines ~26–45); Discover/Import button pattern to follow

### Requirements
- `.planning/REQUIREMENTS.md` — ACCENT-01 (success criteria: presets, hex, immediate apply, persist, invalid hex rejected)
- `.planning/ROADMAP.md` — Phase 19 plan split (19-01: CSS backend; 19-02: dialog UI)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `repo.get_setting(key, default)` / `repo.set_setting(key, value)` — already used for `volume` and `recently_played_count`; same pattern applies to `accent_color`
- `Gtk.CssProvider` + `Gtk.StyleContext.add_provider_for_display` — already instantiated in `__main__.py do_activate()`; second provider follows identical setup

### Established Patterns
- Settings persistence: float/int/str values stored as text in `settings` table, retrieved with default fallback
- Header bar buttons: `Gtk.Button(label=...)` or icon button, `header.pack_end()`, connected to `self._open_*` method
- Modal dialogs: `EditDialog`, `DiscoveryDialog`, `ImportDialog` all follow `Adw.Dialog` or `Gtk.Dialog` subclass pattern in separate files under `musicstreamer/ui/`

### Integration Points
- `__main__.py` `do_activate()`: CSS provider must be injected here after `repo` is available and before `win.present()`
- `musicstreamer/ui/main_window.py` header bar: accent button packs alongside Discover/Import
- New file: `musicstreamer/ui/accent_dialog.py` — `AccentDialog` class

</code_context>

<specifics>
## Specific Ideas

- "The GNOME display presets with an additional custom selection (hex value for now)" — presets are the 8 GNOME colors; custom is via hex entry (not a preset swatch)

</specifics>

<deferred>
## Deferred Ideas

- ACCENT-F01: Per-station accent color override — explicitly out of scope (listed as future requirement)
- Swatch color names/labels in the dialog — not required, colors are self-evident

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 19-custom-accent-color*
*Context gathered: 2026-04-05*
