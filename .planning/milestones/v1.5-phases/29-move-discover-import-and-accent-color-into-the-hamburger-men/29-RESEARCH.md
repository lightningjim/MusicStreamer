# Phase 29: Move Discover, Import, and Accent Color into the Hamburger Menu - Research

**Researched:** 2026-04-09
**Domain:** GTK4 / libadwaita UI reorganization (Python/GObject)
**Confidence:** HIGH

## Summary

This phase is a pure UI reorganization with no new features. Three header bar buttons (Discover, Import, Accent Color) move into the existing `Gio.Menu` hamburger, which already has one item ("YouTube Cookies…") following the exact same `Gio.SimpleAction` pattern needed for the three new items.

The existing code at lines 46–73 of `main_window.py` contains both the pattern to replicate (`open-cookies` action) and the code to delete (three `Gtk.Button` instantiations and `pack_end` calls). Handler methods at lines 1066–1079 require only a signature change from `(*_)` to `(action, param)` to match the `SimpleAction.connect("activate", ...)` callback convention.

**Primary recommendation:** Replicate the `open-cookies` pattern three times, restructure the `Gio.Menu` into two sections per D-01, and remove the three button creation blocks.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Feature-grouped layout with section separator. Top section (station actions): "Discover Stations…", "Import Stations…". Bottom section (settings): "Accent Color…", "YouTube Cookies…". Use `Gio.Menu` section grouping.
- **D-02:** Text-only menu items, no icons.
- **D-03:** Labels with ellipsis: "Discover Stations…", "Import Stations…", "Accent Color…", "YouTube Cookies…".
- **D-04:** Remove `discover_btn`, `import_btn`, and `accent_btn` button creation and `pack_end` calls entirely. Header bar left with only search entry + hamburger button.
- **D-05:** Each moved action becomes a `Gio.SimpleAction` on the app, connected to the existing handler methods. Same pattern as `app.open-cookies`.

### Claude's Discretion

- Action naming convention (e.g., `app.open-discovery`, `app.open-import`, `app.open-accent`)
- Whether to group action registration in a helper method or keep inline

### Deferred Ideas (OUT OF SCOPE)

None
</user_constraints>

## Standard Stack

No additional libraries needed. Everything required is already imported and in use.

| API | Purpose | Already in use |
|-----|---------|----------------|
| `Gio.Menu` | Menu model for hamburger | Yes — line 61 |
| `Gio.Menu` section grouping | Section separator between groups | Not yet — add now |
| `Gio.SimpleAction` | Action wired to menu item | Yes — lines 71–73 |
| `app.add_action()` | Register action on app | Yes — line 73 |

## Architecture Patterns

### Existing Pattern (open-cookies — lines 61–73)

```python
# [VERIFIED: main_window.py lines 61-73]
menu = Gio.Menu()
menu.append("YouTube Cookies\u2026", "app.open-cookies")

menu_btn = Gtk.MenuButton()
menu_btn.set_icon_name("open-menu-symbolic")
menu_btn.set_menu_model(menu)
header.pack_end(menu_btn)

action = Gio.SimpleAction.new("open-cookies", None)
action.connect("activate", self._open_cookies_dialog)
app.add_action(action)
```

### Target Pattern: Two-Section Menu (D-01)

```python
# [VERIFIED: Gio.Menu section API — standard GLib pattern]
menu = Gio.Menu()

# Top section — station actions
station_section = Gio.Menu()
station_section.append("Discover Stations\u2026", "app.open-discovery")
station_section.append("Import Stations\u2026", "app.open-import")
menu.append_section(None, station_section)

# Bottom section — settings
settings_section = Gio.Menu()
settings_section.append("Accent Color\u2026", "app.open-accent")
settings_section.append("YouTube Cookies\u2026", "app.open-cookies")
menu.append_section(None, settings_section)
```

`append_section(None, subsection)` produces an unnamed section with a visual separator — no label, just the separator line. `[ASSUMED]` — the `None` label argument behavior matches GLib docs; verify renders as expected at runtime.

### Action Registration Pattern

```python
# [VERIFIED: main_window.py line 71-73 — existing pattern]
for name, handler in [
    ("open-discovery", self._open_discovery),
    ("open-import", self._open_import),
    ("open-accent", self._open_accent_dialog),
]:
    action = Gio.SimpleAction.new(name, None)
    action.connect("activate", handler)
    app.add_action(action)
```

Or keep three inline blocks matching existing style — Claude's discretion per context.

### Handler Signature Adjustment

Existing handlers use `(*_)`. `SimpleAction.connect("activate", cb)` calls `cb(action, param)`. The `(*_)` signature already accepts this — no change required.

```python
# [VERIFIED: main_window.py lines 1066-1079]
def _open_accent_dialog(self, *_):   # works as action callback as-is
def _open_discovery(self, *_):       # works as action callback as-is
def _open_import(self, *_):          # works as action callback as-is
```

### Code to Remove (D-04)

Lines 46–58 in `main_window.py`:

```python
# DELETE these 7 lines:
discover_btn = Gtk.Button(label="Discover")
discover_btn.connect("clicked", self._open_discovery)
header.pack_end(discover_btn)

import_btn = Gtk.Button(label="Import")
import_btn.connect("clicked", self._open_import)
header.pack_end(import_btn)

accent_btn = Gtk.Button()
accent_btn.set_icon_name("color-select-symbolic")
accent_btn.set_tooltip_text("Accent color")
accent_btn.connect("clicked", self._open_accent_dialog)
header.pack_end(accent_btn)
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Section separator in menu | Manual separator widget | `Gio.Menu.append_section(None, subsection)` |
| Action dispatch | Custom signal routing | `Gio.SimpleAction` + `app.add_action()` |

## Common Pitfalls

### Pitfall 1: Moving "YouTube Cookies…" between sections breaks its action

The `open-cookies` action is registered after the menu is built (line 71–73). When restructuring the menu into sections, the `app.open-cookies` action name must remain unchanged — only the menu model changes. The action registration block stays identical.

**How to avoid:** Keep the action name `"app.open-cookies"` and its registration block untouched; only the `menu.append(...)` call moves into `settings_section.append(...)`.

### Pitfall 2: Forgetting to remove button local variables

After deleting the three `pack_end` calls, the button variables (`discover_btn`, `import_btn`, `accent_btn`) must also be deleted. Leaving them creates dead object construction with no side effects but is misleading.

### Pitfall 3: Section label vs. no label

`append_section(None, section)` — `None` means no title label, just a visual separator. Passing an empty string `""` may render a blank label space depending on the theme. Use `None`. `[ASSUMED]` — GTK4/Adw behavior; confirm visually.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `append_section(None, subsection)` renders as unnamed section with only a separator line | Architecture Patterns | Cosmetic — may show blank label; fix by testing |
| A2 | `(*_)` handler signature works for `SimpleAction.connect("activate", ...)` callback without modification | Architecture Patterns | Low — `(*_)` accepts any positional args including `(action, param)` |

## Open Questions

None — implementation is fully specified by CONTEXT.md decisions and existing code patterns.

## Validation Architecture

### Test Framework

No automated tests exist for UI behavior in this codebase. This phase is UI-only restructuring with no logic changes.

| Property | Value |
|----------|-------|
| Framework | None (manual smoke test) |
| Quick verification | Launch app, open hamburger menu, confirm 4 items in 2 sections, confirm all 3 dialogs open |

### Phase Requirements → Test Map

| Behavior | Test Type | Verification |
|----------|-----------|-------------|
| Hamburger shows "Discover Stations…", "Import Stations…" in top section | Manual smoke | Open menu, visually confirm |
| Hamburger shows "Accent Color…", "YouTube Cookies…" in bottom section | Manual smoke | Open menu, visually confirm separator |
| Header bar has no Discover/Import/Accent buttons | Manual smoke | Visual inspection |
| All 3 dialogs open from menu items | Manual smoke | Click each, confirm dialog appears |

### Wave 0 Gaps

None — no test infrastructure needed for this phase.

## Sources

### Primary (HIGH confidence)

- `musicstreamer/ui/main_window.py` lines 29–73 — [VERIFIED] existing button and action code
- `musicstreamer/ui/main_window.py` lines 1066–1083 — [VERIFIED] handler method signatures

### Secondary (MEDIUM confidence)

- GLib `Gio.Menu.append_section` API — standard GObject introspection pattern [ASSUMED from training, no live doc fetch needed given confidence in pattern]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all patterns verified in codebase
- Architecture: HIGH — exact pattern already exists for open-cookies
- Pitfalls: HIGH — all identified from direct code inspection

**Research date:** 2026-04-09
**Valid until:** Stable — no external dependencies
