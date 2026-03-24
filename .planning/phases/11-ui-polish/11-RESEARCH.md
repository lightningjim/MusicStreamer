# Phase 11: UI Polish - Research

**Researched:** 2026-03-24
**Domain:** GTK4/libadwaita CSS styling, PyGObject
**Confidence:** HIGH

## Summary

This phase is entirely CSS-driven: add a `Gtk.CssProvider` with three rules, add two CSS class names to existing widgets, and bump four margin values in Python. No structural widget changes, no new dependencies, no new widget types.

The CSS specification is fully codified in the approved UI-SPEC. Research confirms all proposed CSS features (`shade()`, `linear-gradient`, `border-radius`, `@card_bg_color`) are supported by the installed runtime (GTK 4.20, libadwaita 1.8.0). The fallback for `shade()` is documented but unlikely to be needed.

**Primary recommendation:** Load a single inline CSS string from `__main__.py` `do_activate` (after `win = MainWindow(...)`) via `Gtk.StyleContext.add_provider_for_display`. Keep the CSS as a Python string constant in `__main__.py` or a sibling `style.css` file loaded at startup.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Keep the panel as a flat `Gtk.Box` — no card border, no frame widget
- **D-02:** Increase internal whitespace/padding: more `margin_top/bottom` and `margin_start/end` on the panel box itself
- **D-03:** Rounded corners on the panel via CSS (not structural widget change)
- **D-04:** Apply Adwaita secondary surface color as panel background (`@card_bg_color`)
- **D-05:** Add a subtle `linear-gradient` on the panel background — not dramatic, just enough to break the flatness
- **D-06:** Implement both effects via `Gtk.CssProvider` loaded at app startup — no custom widget subclassing
- **D-07:** Subtle bump only — single increment of padding on `Adw.ActionRow` rows (4–6px additional vertical padding)

### Claude's Discretion
- Exact gradient direction and color stops (keep it subtle)
- Exact padding pixel values within the "subtle bump" intent
- Whether to apply CSS globally via app-level provider or per-widget via class names
- CSS class naming conventions

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Panels and cards use rounded corners | CSS `border-radius: 12px` on `.now-playing-panel` — matches Adwaita `.card` radius |
| UI-02 | Color palette softened with subtle gradients (less harsh contrast) | `linear-gradient` using `shade(@card_bg_color, ...)` stops; secondary surface via `@card_bg_color` token |
| UI-03 | Station list rows have increased vertical padding | CSS `padding-top/bottom: 4px` on `.station-list-row` class added to `Adw.ActionRow` instances |
| UI-04 | Now Playing panel has increased internal whitespace | Python margin properties bumped: `margin_top/bottom` 4→16px, `margin_start/end` 8→24px |
</phase_requirements>

---

## Standard Stack

### Core (already in project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GTK4 | 4.20 (installed) | Widget toolkit | System package |
| libadwaita | 1.8.0 (installed) | GNOME design system | System package |
| PyGObject | system | Python bindings | System package |

No new packages required. This phase adds zero dependencies.

**Installation:** nothing — all system packages already present.

---

## Architecture Patterns

### CSS Loading Pattern

The project has no existing `Gtk.CssProvider`. The correct pattern for GTK4/PyGObject:

```python
# Source: GTK4 docs — Gtk.StyleContext.add_provider_for_display
css_provider = Gtk.CssProvider()
css_provider.load_from_string(CSS_STRING)
Gtk.StyleContext.add_provider_for_display(
    display,
    css_provider,
    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
)
```

`STYLE_PROVIDER_PRIORITY_APPLICATION` (600) overrides Adwaita defaults (400) without interfering with user themes. `display` is obtained from `Gdk.Display.get_default()` or `win.get_display()`.

**Placement:** Call this in `App.do_activate` after `win = MainWindow(...)` and before `win.present()` — or inside `MainWindow.__init__` using `self.get_display()`. Either works; `do_activate` keeps CSS concerns out of the window class.

**Note:** In GTK4 PyGObject, `load_from_string` is the correct method (not `load_from_data`). `load_from_data` still accepts bytes but `load_from_string` is cleaner.

### CSS Rule Structure

All rules in a single provider string:

```css
.now-playing-panel {
    background: linear-gradient(
        to bottom,
        shade(@card_bg_color, 1.04),
        shade(@card_bg_color, 0.97)
    );
    border-radius: 12px;
}

.station-list-row {
    padding-top: 4px;
    padding-bottom: 4px;
}
```

### Widget Class Assignment Pattern

```python
# panel in MainWindow.__init__
panel.add_css_class("now-playing-panel")

# Adw.ActionRow in StationRow.__init__
row.add_css_class("station-list-row")

# Adw.ActionRow in _make_action_row
ar.add_css_class("station-list-row")
```

### Panel Margin Changes (Python, not CSS)

These are direct property changes on the existing `panel` box object — not CSS:

```python
panel.set_margin_top(16)
panel.set_margin_bottom(16)
panel.set_margin_start(24)
panel.set_margin_end(24)
```

### Anti-Patterns to Avoid

- **Don't use `load_from_data`** with a string — pass bytes or use `load_from_string`.
- **Don't subclass widgets** for visual changes — CSS class is sufficient per D-06.
- **Don't target `row` globally** without verifying no regression on ExpanderRow headers. Use `.station-list-row` class instead.
- **Don't hardcode hex colors** — use Adwaita semantic tokens (`@card_bg_color`) so dark mode works correctly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Semantic color tokens | Hardcoded hex values | `@card_bg_color`, `@window_bg_color` | Tokens resolve correctly for light/dark theme |
| Color lightening/darkening | Manual hex manipulation | `shade()` GTK CSS function | Built-in, theme-safe |
| CSS priority management | Widget-level inline styles | `STYLE_PROVIDER_PRIORITY_APPLICATION` | Correct override level without fighting user themes |

---

## Common Pitfalls

### Pitfall 1: `shade()` on GTK versions below 3.92
**What goes wrong:** `shade()` is a GTK CSS function — not standard W3C CSS. It is supported in GTK3.92+ (well within GTK 4.20).
**Why it happens:** Developers assume GTK CSS = browser CSS.
**How to avoid:** Use it as specified. The installed version (4.20) fully supports it.
**Warning signs:** CSS parse error logged to stderr at startup.

### Pitfall 2: CSS padding on Adw.ActionRow may be partially absorbed
**What goes wrong:** `Adw.ActionRow` has its own internal padding managed by libadwaita CSS. Adding `padding-top/bottom` on the row element may add to the existing internal padding or may be overridden.
**Why it happens:** libadwaita's CSS for `row` widgets already sets padding internally.
**How to avoid:** Use `min-height` as an alternative if direct padding doesn't render visually. Or target the inner `GtkLabel` container. The UI-SPEC prescribes `padding-top: 4px; padding-bottom: 4px` on `.station-list-row` — test visually and adjust if the delta doesn't appear.
**Warning signs:** Row height looks unchanged at runtime even after CSS loads.

### Pitfall 3: CSS provider not reaching already-constructed widgets
**What goes wrong:** If the CSS provider is added after widgets are shown, the style may not apply until the next layout pass.
**Why it happens:** GTK style invalidation timing.
**How to avoid:** Load the provider before `win.present()` — constructing widgets and assigning classes before presenting ensures the first render uses the correct styles.

### Pitfall 4: `border-radius` on Gtk.Box has no visible effect without explicit background
**What goes wrong:** `border-radius` only clips visible backgrounds. If the panel has no background color set via CSS, the radius has nothing to clip and the corners appear sharp.
**Why it happens:** GTK4 boxes are transparent by default; `border-radius` alone doesn't draw anything.
**How to avoid:** The `background: linear-gradient(...)` rule in the same `.now-playing-panel` block handles this — both rules must be present together. Do not split them.

---

## Code Examples

### Complete CSS provider setup
```python
# Source: GTK4 PyGObject docs pattern
import gi
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

CSS = """
.now-playing-panel {
    background: linear-gradient(
        to bottom,
        shade(@card_bg_color, 1.04),
        shade(@card_bg_color, 0.97)
    );
    border-radius: 12px;
}

.station-list-row {
    padding-top: 4px;
    padding-bottom: 4px;
}
"""

def _load_css():
    provider = Gtk.CssProvider()
    provider.load_from_string(CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
```

### Panel margin update (in MainWindow.__init__, existing panel box)
```python
# Change these 4 lines (currently at ~L40-43):
panel.set_margin_top(16)     # was 4
panel.set_margin_bottom(16)  # was 4
panel.set_margin_start(24)   # was 8
panel.set_margin_end(24)     # was 8
panel.add_css_class("now-playing-panel")
```

---

## Environment Availability

Step 2.6: SKIPPED — no external dependencies. All libraries are already installed system packages. No CLI tools, databases, or external services required.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (detected via `tests/` directory with collected tests) |
| Config file | `pyproject.toml` (no `[tool.pytest]` section — pytest autodiscovers) |
| Quick run command | `python3 -m pytest tests/ -x -q` |
| Full suite command | `python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | Rounded corners on panel | manual-only | N/A — visual rendering | N/A |
| UI-02 | Gradient background on panel | manual-only | N/A — visual rendering | N/A |
| UI-03 | Station rows have more vertical padding | manual-only | N/A — visual rendering | N/A |
| UI-04 | Now Playing panel has more whitespace | manual-only | N/A — visual rendering | N/A |

All four requirements are visual/CSS only — no logic to unit test. Validation is by visual inspection at runtime.

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/ -x -q` (existing suite must stay green — no regressions)
- **Per wave merge:** `python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green + visual inspection before `/gsd:verify-work`

### Wave 0 Gaps
None — no new test files needed. Existing test suite covers all non-visual logic. The CSS changes have no unit-testable behavior.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `load_from_data(bytes)` | `load_from_string(str)` | GTK 4.x | Use `load_from_string` in new code |
| `Gtk.StyleContext` per-widget provider | `add_provider_for_display` global | GTK4 | Single call covers all widgets |

---

## Open Questions

1. **Adw.ActionRow padding delta rendering**
   - What we know: libadwaita sets its own internal row padding; adding CSS `padding-top/bottom` on the row element may or may not produce the expected visual delta depending on how libadwaita's own CSS specificity interacts.
   - What's unclear: Whether targeting `.station-list-row` (specificity: class selector) overrides libadwaita's internal `row` styling (specificity: type selector). Class selector wins on specificity, so it likely works.
   - Recommendation: Implement as specified; test visually. If the 4px delta is invisible, try `min-height` increase or target the row's inner box via `.station-list-row > box`.

---

## Sources

### Primary (HIGH confidence)
- Installed runtime verified: GTK 4.20, libadwaita 1.8.0 — all CSS features (`shade()`, `linear-gradient`, `border-radius`, `@card_bg_color`) confirmed present
- `musicstreamer/ui/main_window.py` — panel construction, current margin values, `_make_action_row` location
- `musicstreamer/ui/station_row.py` — `Adw.ActionRow` construction, CSS class target
- `musicstreamer/__main__.py` — `App.do_activate` — CSS provider load point
- `11-UI-SPEC.md` — fully approved design contract with exact values

### Secondary (MEDIUM confidence)
- GTK4 PyGObject `add_provider_for_display` pattern — widely used in GNOME app ecosystem

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — system packages verified at runtime
- Architecture: HIGH — CSS provider pattern is standard GTK4, fully specified in UI-SPEC
- Pitfalls: MEDIUM — ActionRow padding interaction is a known uncertainty; all others HIGH

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (stable GTK/Adwaita API)
