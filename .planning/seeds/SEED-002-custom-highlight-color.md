---
id: SEED-002
status: shipped
planted: 2026-03-27
planted_during: v1.3 Discovery & Favorites (pre-planning)
trigger_when: any milestone focused on theming, appearance, or UI customization
scope: medium
shipped_date: 2026-04-05
shipped_by: v1.4 Phase 19 (ACCENT-01) — Custom Accent Color
---

> **✅ SHIPPED** — Delivered as v1.4 Phase 19. Exact match to the seed
> proposal: 8 preset swatches + hex entry field, persisted in SQLite
> settings, CSS injection via `Gtk.CssProvider` at `PRIORITY_USER` so
> it overrides theme tokens. Key code:
> `musicstreamer/ui/accent_dialog.py`, `musicstreamer/accent_utils.py`.
> See SEED-006 for the follow-up (visual color wheel picker — still
> dormant).

# SEED-002: Custom highlight/accent color with presets + hex input

## Why This Matters

The app currently uses GTK's `suggested-action` CSS class as the highlight color (blue, on
the Stop button and potentially other accents). Users may want to personalize this to match
their desktop theme or preference. A preset picker covers common cases quickly; a hex input
covers power users who want an exact color.

## When to Surface

**Trigger:** any milestone focused on theming, appearance, or UI customization

This seed should be presented during `/gsd:new-milestone` when the milestone
scope matches any of these conditions:
- Milestone includes a theming or visual customization phase
- Milestone adds a Preferences/Settings dialog
- Milestone is a UI polish or personalization milestone

## Scope Estimate

**Medium** — needs a UI for the picker (preset swatches + hex entry field), CSS injection to
override the accent color at runtime, and config persistence. The `settings` table in SQLite
already supports arbitrary key/value storage (`repo.py:203-213`), so persistence is free.
The main work is the color picker UI and generating/applying a dynamic CSS override.

## Implementation Notes

- **Presets:** a small horizontal row of color swatches (Gtk.ToggleButton with colored circles)
- **Custom hex:** a `Gtk.Entry` that validates 6-char hex, shows a live preview swatch
- **CSS injection:** `Gtk.CssProvider.load_from_string()` at runtime with a rule like
  `button.suggested-action { background: #RRGGBB; }` — applied via `Gtk.StyleContext`
- **Persistence:** `repo.set_setting("highlight_color", "#hex")` — load on startup and apply
- **Where to surface the picker:** a Preferences row in a future settings dialog, or as
  a small color dot in the header bar

## Breadcrumbs

- `musicstreamer/repo.py:203-213` — `get_setting` / `set_setting` on SQLite `settings` table (persistence is ready)
- `musicstreamer/ui/main_window.py:89-90` — `stop_btn` uses `suggested-action` CSS class (primary target for accent override)
- `musicstreamer/constants.py:5` — `DB_PATH` for the SQLite database location

## Notes

No CSS files exist yet — the app relies entirely on GTK CSS classes. A dynamic
`CssProvider` is the right approach for runtime color overrides without a static `.css` file.
