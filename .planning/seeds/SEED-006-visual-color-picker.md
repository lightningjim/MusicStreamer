---
id: SEED-006
status: completed
planted: 2026-04-05
planted_during: v1.4 Media & Art Polish / Phase 19
trigger_when: UI polish milestone is being planned
scope: Medium
completed: 2026-05-04
completed_by: Phase 59 (ACCENT-02 — HSV/wheel color picker shipped alongside presets + hex entry); Phase 66 (theme picker extends accent picker with preset palettes + custom slot)
---

# SEED-006: Add visual color picker to the accent dialog

## Why This Matters

Two problems with the current hex-only approach:

1. **Friction**: Most users don't know hex color codes. Typing `#9141ac` is unintuitive compared to clicking a color wheel.
2. **Discoverability**: The hex entry row doesn't communicate that arbitrary colors are possible — many users will assume the 8 presets are the only options.

A visual picker (via `Gtk.ColorDialog`, GTK4's async color chooser) solves both: clicking a button next to the hex entry opens a native color chooser, the picked color flows back into `_apply_color`, and users who do know hex can still type directly.

## When to Surface

**Trigger:** When a UI polish or settings/preferences milestone is being planned.

This seed should be presented during `/gsd-new-milestone` when the milestone scope matches any of these conditions:
- Milestone involves UI polish, visual refinement, or settings UX improvements
- Milestone name contains "polish", "preferences", "settings", or "UX"
- A phase touching `accent_dialog.py` or the header bar is being added

## Scope Estimate

**Medium** — A phase or two. `Gtk.ColorDialog` (GTK 4.10+) is async; the integration needs:
1. A picker icon button next to the hex entry in `AccentDialog`
2. `Gtk.ColorDialog.choose_rgba()` call wired to `_apply_color`
3. RGBA→hex conversion utility (extend `accent_utils.py`)
4. Fallback to `Gtk.ColorChooserDialog` if GTK < 4.10

No backend changes needed — persistence and CSS injection already handle arbitrary hex via Plan 19.

## Breadcrumbs

- `musicstreamer/ui/accent_dialog.py` — `AccentDialog._build_ui()`: hex entry row is at line ~75; picker button would slot in alongside it
- `musicstreamer/accent_utils.py` — `_is_valid_hex`, `build_accent_css`: RGBA→hex conversion belongs here
- `musicstreamer/ui/main_window.py:864` — `_open_accent_dialog`: entry point, no changes needed
- `.planning/phases/19-custom-accent-color/19-UI-SPEC.md` — original design decisions, D-07 covers button ordering

## Notes

Decision D-05 from Phase 19 CONTEXT.md chose hex-only to keep scope small. This seed is the natural next step once Phase 19 ships.
