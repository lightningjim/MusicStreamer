---
id: SEED-001
status: shipped
planted: 2026-03-27
planted_during: v1.3 Discovery & Favorites (pre-planning)
trigger_when: any milestone with UI layout or player controls phases
scope: small
shipped_date: 2026-04-10
shipped_by: v1.4 Phase 20 (CTRL-01) + v1.5 Phase 26 (FIX-06) — controls_box layout rework
---

> **✅ SHIPPED** — `musicstreamer/ui/main_window.py:149` sets
> `controls_box.set_halign(Gtk.Align.END)`, right-aligning the whole
> controls cluster (star, edit, pause, stop, stream) to the panel's
> right edge. Delivered incidentally as part of the v1.4/v1.5 now-playing
> controls rework, not as a dedicated fix.

# SEED-001: Right-align the Stop button in the now-playing panel

## Why This Matters

The now-playing panel has left-aligned text info (title + station name) and the Stop button
sitting in the same center column, also left-aligned. Moving the Stop button to the right
edge creates visual balance (info left, control right) and makes the separation between
informational content and interactive controls more obvious at a glance.

## When to Surface

**Trigger:** any milestone that includes UI layout, player controls, or visual polish phases
 
This seed should be presented during `/gsd:new-milestone` when the milestone
scope matches any of these conditions:
- Milestone includes a UI polish or layout phase
- Milestone touches the now-playing panel or player controls
- Milestone is explicitly a v1.3 UI-focused milestone

## Scope Estimate

**Small** — single widget layout change in `main_window.py`. The Stop button currently lives
in the `center` Gtk.Box (vertical, hexpand). Right-aligning it likely means either setting
`set_halign(Gtk.Align.END)` on the button, or restructuring the panel's horizontal layout
to have an explicit right slot for the button.

## Breadcrumbs

- `musicstreamer/ui/main_window.py:89-94` — `self.stop_btn` created, added to `center` column with `set_halign(Gtk.Align.START)`
- `musicstreamer/ui/main_window.py:70-94` — center column layout (title, station name, stop button all in one Gtk.Box)
- `musicstreamer/ui/main_window.py:68` — `panel` is a horizontal Gtk.Box; left slot = logo, center = info+button

## Notes

The panel layout is: `[logo] [center: title / station / stop_btn]`. To right-align the stop
button, the simplest approach is restructuring center into two sub-boxes or adding a
right-slot box to the panel. The button currently uses `suggested-action` CSS class (blue).
