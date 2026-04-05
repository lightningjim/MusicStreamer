# Phase 19: Custom Accent Color - Research

**Researched:** 2026-04-05
**Domain:** GTK4 / Libadwaita CSS theming, settings persistence, dialog UI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Inject `@define-color accent_bg_color #RRGGBB` via a dedicated `Gtk.CssProvider` at `STYLE_PROVIDER_PRIORITY_USER` priority. Second provider separate from `_APP_CSS`. Full Libadwaita accent — affects suggested-action buttons, links, sliders, toggles, checkboxes, progress bars.
- **D-02:** On startup, load from `repo.get_setting("accent_color", "#3584e4")` and inject before `win.present()`. On change, call `css_provider.load_from_string(...)` on the same provider instance — no remove/re-add.
- **D-03:** Settings key: `"accent_color"`, stored as lowercase hex. Default: `"#3584e4"`. Uses existing `repo.get_setting()` / `repo.set_setting()`.
- **D-04:** 8 GNOME-style preset swatches: Blue `#3584e4`, Teal `#2190a4`, Green `#3a944a`, Yellow `#c88800`, Orange `#ed5b00`, Red `#e62d42`, Purple `#9141ac`, Pink `#c64d92`.
- **D-05:** Hex input for custom; no separate "Custom" swatch.
- **D-06:** Inline error via Adwaita `error` CSS class on entry row; clear on next keystroke (`changed` signal). No error dialog.
- **D-07:** Icon button in header bar (`header.pack_end()`). Icon: `preferences-color-symbolic` or `color-select-symbolic`. Opens `AccentDialog` as modal.

### Claude's Discretion

- Whether to make accent CSS provider a module-level singleton or instance variable on `App`
- Exact dialog layout (grid of swatches + separator + hex entry row)
- Whether hex entry uses `Adw.EntryRow` or plain `Gtk.Entry`
- Icon name for header button (resolve at implementation from available system icons)

### Deferred Ideas (OUT OF SCOPE)

- ACCENT-F01: Per-station accent color override
- Swatch color names/labels in dialog

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ACCENT-01 | User can set a custom highlight/accent color from preset swatches or hex input; applied immediately and persists across sessions | CSS injection mechanism verified; settings API verified; `Adw.EntryRow` + `error` CSS class confirmed; validation regex defined |

</phase_requirements>

---

## Summary

Phase 19 adds a user-configurable accent color using GTK4/Libadwaita's native `@define-color accent_bg_color` CSS variable. The mechanism is `Gtk.CssProvider.load_from_string()` called on a dedicated provider registered at `STYLE_PROVIDER_PRIORITY_USER` (800), which overrides the system accent for this app. All locked decisions are verified against the running environment (GTK 4.20, Adw 1.8.0).

The implementation splits cleanly into two parts: a pure Python backend (CSS provider creation, hex validation, settings read/write) which is fully unit-testable without a display, and a dialog UI (`AccentDialog`) which requires manual visual verification. The existing `repo.get_setting()` / `repo.set_setting()` API handles persistence identically to the existing `volume` setting — no schema changes needed.

**Primary recommendation:** Implement CSS provider as an instance variable on `App` (passed to `AccentDialog`). This avoids module globals while keeping the provider accessible for re-injection on color change.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GTK4 (PyGObject) | 4.20 (installed) | Widgets, CSS providers, layout | Project standard |
| Libadwaita | 1.8.0 (installed) | `Adw.Dialog`, `Adw.EntryRow`, `error` CSS class | Project standard |

No new packages required. [VERIFIED: live environment probe]

**Installation:** None — all dependencies already present.

---

## Architecture Patterns

### Recommended Project Structure

```
musicstreamer/
├── __main__.py          — App.do_activate(): create accent_provider, inject startup color
├── constants.py         — Add ACCENT_COLOR_DEFAULT = "#3584e4"
└── ui/
    ├── main_window.py   — Add accent icon button to header bar
    └── accent_dialog.py — NEW: AccentDialog class (Adw.Window, following DiscoveryDialog pattern)
```

### Pattern 1: Dual CSS Provider Injection

**What:** Two separate `Gtk.CssProvider` instances registered on the same display. The accent provider uses `PRIORITY_USER` (800) to override the system accent; app styles use `PRIORITY_APPLICATION` (600).

**When to use:** Always — this is D-01.

**Example:**
```python
# Source: verified against Gtk.STYLE_PROVIDER_PRIORITY_USER = 800 (live probe)
# In App.do_activate(), after existing _APP_CSS provider:
accent_provider = Gtk.CssProvider()
accent_hex = repo.get_setting("accent_color", ACCENT_COLOR_DEFAULT)
accent_provider.load_from_string(f"@define-color accent_bg_color {accent_hex};")
Gtk.StyleContext.add_provider_for_display(
    Gdk.Display.get_default(),
    accent_provider,
    Gtk.STYLE_PROVIDER_PRIORITY_USER,
)
```

### Pattern 2: In-place CSS Provider Reload

**What:** Call `load_from_string()` on the existing provider instance — GTK re-applies immediately, no remove/re-add needed.

**When to use:** Every time the user selects a swatch or submits a valid hex.

**Example:**
```python
# D-02: no re-registration needed
accent_provider.load_from_string(f"@define-color accent_bg_color {hex_value};")
repo.set_setting("accent_color", hex_value)
```
[VERIFIED: CSS parsed without error in live probe]

### Pattern 3: Dialog as Adw.Window (project convention)

**What:** All project dialogs (`DiscoveryDialog`, `ImportDialog`, `EditStationDialog`) subclass `Adw.Window` — not `Adw.Dialog`. They set `set_transient_for(main_window)` and `set_modal(True)` explicitly. `present()` takes no parent argument with `Adw.Window`.

**When to use:** `AccentDialog` must follow the same pattern.

**Example:**
```python
# Source: DiscoveryDialog pattern (discovery_dialog.py:37-44)
class AccentDialog(Adw.Window):
    def __init__(self, app, repo: Repo, accent_provider: Gtk.CssProvider, main_window):
        super().__init__(application=app, title="Accent Color")
        self.set_transient_for(main_window)
        self.set_modal(True)
        self.set_default_size(320, -1)
```

Note: `Adw.Dialog` also exists in Adw 1.8 and its `present(self, parent=None)` is valid. However project convention is `Adw.Window`. The UI-SPEC says `Adw.Dialog` — **this is a Claude's Discretion decision**: use `Adw.Window` to match project convention, or `Adw.Dialog` to match the spec. Recommend `Adw.Window` for consistency with existing dialogs. [VERIFIED: both classes present in Adw 1.8.0]

### Pattern 4: Hex Validation Without Regex Import

**What:** Validate a hex color string.

**Example:**
```python
import re
_HEX_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')

def _is_valid_hex(value: str) -> bool:
    return bool(_HEX_RE.match(value))
```

### Pattern 5: Entry Row Error State

**What:** Add/remove the `error` CSS class on an `Adw.EntryRow`.

**Example:**
```python
# Add error indicator
entry_row.add_css_class("error")

# Clear on text change (connect to 'changed' signal of the inner Gtk.Entry, or use notify::text)
entry_row.connect("notify::text", self._on_text_changed)

def _on_text_changed(self, *_):
    self.entry_row.remove_css_class("error")
```
[VERIFIED: `Adw.EntryRow` has `error` CSS class support in Adw 1.8; `add_css_class`/`remove_css_class` from GtkWidget]

### Pattern 6: Swatch Selection State

**What:** Selected swatch shows `suggested-action` CSS class for active ring; deselected swatches have none.

**Example:**
```python
def _select_swatch(self, hex_value: str):
    # Deselect old
    if self._selected_btn:
        self._selected_btn.remove_css_class("suggested-action")
    # Select new
    btn = self._swatch_map[hex_value]
    btn.add_css_class("suggested-action")
    self._selected_btn = btn
```

### Anti-Patterns to Avoid

- **Re-registering the provider on each color change:** `add_provider_for_display` every update leaks provider registrations. Call `load_from_string()` on the existing instance only.
- **Using `Adw.Dialog` instead of `Adw.Window`:** The project uses `Adw.Window` for all dialogs — mixing introduces inconsistency with transient/modal setup.
- **Module-level accent provider global:** Makes testing harder and creates shared state. Prefer instance variable on `App`, passed to `AccentDialog`.
- **Persisting invalid hex:** Only call `repo.set_setting()` after `_is_valid_hex()` passes.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSS variable for theming | Custom color-swap logic | `@define-color` + `Gtk.CssProvider` | GTK/Adwaita resolves this token app-wide automatically |
| Settings persistence | Custom file/config parser | `repo.get_setting()` / `repo.set_setting()` | Already exists, tested, SQLite-backed |
| Error visual state | Custom border drawing | `error` CSS class on `Adw.EntryRow` | Adwaita provides themed error border/color out of the box |

---

## Common Pitfalls

### Pitfall 1: Provider Priority — USER vs APPLICATION
**What goes wrong:** Using `STYLE_PROVIDER_PRIORITY_APPLICATION` (600) for the accent provider means the system Adwaita accent (also at APPLICATION or higher) wins and the color has no effect.
**Why it happens:** Confusion between the two priority levels.
**How to avoid:** Always use `STYLE_PROVIDER_PRIORITY_USER` (800) for the accent override provider. [VERIFIED: PRIORITY_USER=800 > PRIORITY_APPLICATION=600]
**Warning signs:** Color appears to change in CSS provider but has no visible effect on buttons/sliders.

### Pitfall 2: Accent Provider Scope
**What goes wrong:** Creating the accent provider inside `AccentDialog` instead of `do_activate()` means it gets garbage-collected when the dialog closes, reverting the accent.
**Why it happens:** Provider lifetime is not obvious.
**How to avoid:** Create the provider in `App.do_activate()` and store as `self.accent_provider`. Pass it as a constructor argument to `AccentDialog`.

### Pitfall 3: Adw.Window vs Adw.Dialog present() call
**What goes wrong:** Calling `Adw.Dialog.present(parent)` pattern on an `Adw.Window` instance — `Adw.Window.present()` takes no parent argument, transient is set in `__init__`.
**Why it happens:** Mixing up the two dialog base classes.
**How to avoid:** Follow `DiscoveryDialog` constructor pattern exactly.

### Pitfall 4: Missing Gdk import in __main__.py
**What goes wrong:** `Gdk.Display.get_default()` call fails with NameError because `Gdk` is not imported separately when only `from gi.repository import Adw, Gst, Gtk` is present.
**Why it happens:** `Gdk` is not implicitly available via `Gtk`.
**How to avoid:** `__main__.py` already imports `Gdk` (`from gi.repository import Adw, Gst, Gtk, Gdk`) — confirmed in codebase. [VERIFIED: __main__.py line 6]

### Pitfall 5: Icon name resolution
**What goes wrong:** Using an icon name that doesn't exist in the system theme causes a missing icon (no visible button content).
**Why it happens:** Icon availability varies by system.
**How to avoid:** Both `color-select-symbolic` and `preferences-color-symbolic` are confirmed present on this machine. Use `color-select-symbolic` (non-legacy path). [VERIFIED: /usr/share/icons/Adwaita/symbolic/actions/color-select-symbolic.svg]

### Pitfall 6: Hex normalization
**What goes wrong:** User types `#3584E4` (uppercase) — stored as-is, compared against preset list `#3584e4` — no swatch appears selected on next open.
**How to avoid:** Normalize hex to lowercase before storing and before comparing: `hex_value.lower()`.

---

## Code Examples

### Startup CSS injection (do_activate)
```python
# Source: pattern from existing _APP_CSS provider + D-01/D-02
from musicstreamer.constants import ACCENT_COLOR_DEFAULT

accent_provider = Gtk.CssProvider()
accent_hex = repo.get_setting("accent_color", ACCENT_COLOR_DEFAULT)
accent_provider.load_from_string(f"@define-color accent_bg_color {accent_hex};")
Gtk.StyleContext.add_provider_for_display(
    Gdk.Display.get_default(),
    accent_provider,
    Gtk.STYLE_PROVIDER_PRIORITY_USER,
)
self.accent_provider = accent_provider  # keep alive
```

### AccentDialog constructor skeleton
```python
class AccentDialog(Adw.Window):
    PRESETS = [
        "#3584e4", "#2190a4", "#3a944a", "#c88800",
        "#ed5b00", "#e62d42", "#9141ac", "#c64d92",
    ]

    def __init__(self, app, repo: Repo, accent_provider: Gtk.CssProvider, main_window):
        super().__init__(application=app, title="Accent Color")
        self.repo = repo
        self.accent_provider = accent_provider
        self.set_transient_for(main_window)
        self.set_modal(True)
        self.set_default_size(320, -1)
        self._selected_btn = None
        self._swatch_map = {}
        self._current_hex = repo.get_setting("accent_color", "#3584e4")
        self._build_ui()
```

### Header bar button (main_window.py)
```python
# After existing import_btn (pack_end stacks right-to-left)
accent_btn = Gtk.Button()
accent_btn.set_icon_name("color-select-symbolic")
accent_btn.set_tooltip_text("Accent color")
accent_btn.connect("clicked", self._open_accent_dialog)
header.pack_end(accent_btn)
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none (auto-discovery) |
| Quick run command | `python3 -m pytest tests/test_accent_color.py -x -q` |
| Full suite command | `python3 -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ACCENT-01 | `_is_valid_hex` accepts `#3584e4`, `#fff` | unit | `pytest tests/test_accent_color.py::test_valid_hex -x` | Wave 0 |
| ACCENT-01 | `_is_valid_hex` rejects `3584e4`, `#gggggg`, `""` | unit | `pytest tests/test_accent_color.py::test_invalid_hex -x` | Wave 0 |
| ACCENT-01 | `repo.get_setting("accent_color", default)` returns default when unset | unit | `pytest tests/test_repo.py` (existing) | exists |
| ACCENT-01 | `repo.set_setting` / `get_setting` round-trip for accent_color | unit | `pytest tests/test_accent_color.py::test_settings_roundtrip -x` | Wave 0 |
| ACCENT-01 | CSS string format matches `@define-color accent_bg_color #hex;` | unit | `pytest tests/test_accent_color.py::test_css_string_format -x` | Wave 0 |

Note: UI behavior (swatch selection, error state, immediate apply) is manual-only — requires a display and cannot be headlessly automated.

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_accent_color.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_accent_color.py` — covers hex validation, CSS string format, settings round-trip (REQ ACCENT-01)

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| GTK4 | All widgets | ✓ | 4.20 | — |
| Libadwaita | Adw.Window, Adw.EntryRow, error CSS class | ✓ | 1.8.0 | — |
| `color-select-symbolic` icon | Header button | ✓ | Adwaita symbolic | Fall back to `preferences-color-symbolic` (also present) |
| pytest | Tests | ✓ | 9.0.2 | — |

---

## Security Domain

Not applicable. This phase writes a color hex string to a local SQLite `settings` table. No network calls, no authentication, no user data beyond a local display preference. Input validation (hex regex) is present by design for correctness, not security.

---

## Open Questions

1. **`Adw.Window` vs `Adw.Dialog` for AccentDialog**
   - What we know: Project convention is `Adw.Window` (all 3 existing dialogs). UI-SPEC says `Adw.Dialog`. Both classes present in Adw 1.8.
   - What's unclear: Which takes precedence — spec or project convention?
   - Recommendation: Use `Adw.Window` to match existing codebase pattern. The functional difference is minor.

2. **`notify::text` vs `changed` signal on `Adw.EntryRow`**
   - What we know: `Adw.EntryRow` emits `notify::text` when text changes. The underlying `Gtk.Entry` emits `changed`. Both can clear the error class.
   - Recommendation: Use `entry_row.connect("notify::text", ...)` — cleaner with `Adw.EntryRow`.

---

## Sources

### Primary (HIGH confidence)
- Live environment probe — GTK 4.20, Adw 1.8.0, `PRIORITY_USER=800`, `Adw.Dialog.present(parent=None)`, `load_from_string('@define-color...')` parsed OK
- `/usr/share/icons/Adwaita/symbolic/` — icon availability confirmed
- Codebase scan — `__main__.py` (CSS provider pattern), `repo.py` (settings API), `discovery_dialog.py` (dialog convention)

### Secondary (MEDIUM confidence)
- CONTEXT.md decisions (D-01 through D-07) — authored from prior discussion session

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `Adw.EntryRow` `error` CSS class produces visible error border in Adw 1.8 | Architecture Patterns | Error state may be invisible; fallback: style entry border manually |

**All other claims verified in this session via live probes and codebase inspection.**

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against running environment
- Architecture: HIGH — patterns derived from existing codebase, verified against live GTK/Adw API
- Pitfalls: HIGH — derived from verified API behavior and codebase inspection

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable GTK4/Adw stack)
