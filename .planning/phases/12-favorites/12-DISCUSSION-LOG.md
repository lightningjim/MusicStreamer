# Phase 12: Favorites - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 12-favorites
**Areas discussed:** Toggle UI, Star button, Row content, Duplicates

---

## Toggle UI

| Option | Description | Selected |
|--------|-------------|----------|
| Button above list | Adw.ToggleGroup row above station list area | ✓ |
| Chip in filter bar | Add Favorites chip to existing filter bar | |
| Header button | Star icon in window header bar | |

**Widget choice:**

| Option | Description | Selected |
|--------|-------------|----------|
| Adw.ToggleGroup | Native Adwaita segmented control | ✓ |
| Two Gtk.ToggleButton | Linked toggle buttons, simpler | |

**User's choice:** Button above list, using Adw.ToggleGroup (segmented control)
**Notes:** User also clarified that the star button icon should behave like standard app favorites — silhouette/outline when not yet starred, filled when already favorited. (This note came in during the Toggle UI discussion but applies to the star button.)

---

## Star button

| Option | Description | Selected |
|--------|-------------|----------|
| Inline with title label | Star on same row as title, center column | |
| Below title, above Stop | Star on own row between title and Stop | |
| Left of Stop button | Star to the left of Stop in center column | ✓ |

**Visibility when no actionable title:**

| Option | Description | Selected |
|--------|-------------|----------|
| Hidden | Not visible when no ICY title | ✓ |
| Disabled | Always visible but greyed out | |

**User's choice:** Left of Stop button; hidden (not disabled) when no actionable title
**Notes:** User specified placement directly as free text: "left of the stop button"

---

## Favorites row content

| Option | Description | Selected |
|--------|-------------|----------|
| Title + Station | Title primary, Station · Provider secondary | ✓ |
| Title + Station + Date | Add date stamp | |

**Delete mechanism:**

| Option | Description | Selected |
|--------|-------------|----------|
| Trash icon button on row | Always-visible icon on right side | ✓ |
| Swipe to delete | Swipe gesture | |
| Confirm dialog on tap | Tap opens dialog | |

**User's choice:** Title + Station · Provider layout; trash icon button on row (no confirmation)

---

## Duplicate handling

| Option | Description | Selected |
|--------|-------------|----------|
| Silently skip | Same (station_name, track_title) → do nothing | ✓ |
| Update timestamp | Replace created_at | |
| Allow duplicates | Insert regardless | |

**User's choice:** Silently skip
**Notes:** Star button remains filled if the track is already in favorites.

---

## Claude's Discretion

- Widget hierarchy for toggle row
- Filter bar visibility vs. sensitivity in Favorites view
- DB migration approach for favorites table
- Favorites list ordering
- iTunes genre caching strategy (use `_last_cover_icy` pattern vs. second API call)

## Deferred Ideas

None.
