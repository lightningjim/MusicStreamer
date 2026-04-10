# Phase 30: Add time counter showing how long current stream has been actively playing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 30-add-time-counter-showing-how-long-current-stream-has-been-ac
**Areas discussed:** Counter placement, Timer behavior, Display format

---

## Counter Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Below station name | New label between station_name_label and controls_box. Naturally groups with track info. | ✓ |
| Inside controls row | Inline with pause/stop buttons as a label. Compact but may crowd the controls. | |
| Below volume slider | At the bottom of the center column. Separated from track info but out of the way. | |

**User's choice:** Below station name (Recommended)
**Notes:** User also requested a small timer icon to the left of the elapsed time text.

---

## Timer Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Pause-aware, reset on station change | Timer pauses when paused, resumes on unpause. Resets on new station. Failover continues. Hidden when stopped. | ✓ |
| Wall-clock style | Always counts from play start, never pauses. Resets only on station change. | |
| Strict reset | Resets on station change AND stream failover. | |

**User's choice:** Pause-aware, reset on station change (Recommended)
**Notes:** None

---

## Display Format

| Option | Description | Selected |
|--------|-------------|----------|
| Adaptive MM:SS / H:MM:SS, dim | Shows 0:00 initially, MM:SS until 59:59, then H:MM:SS. dim-label class. Subtle. | ✓ |
| Always H:MM:SS | Fixed format 0:00:00. More consistent but takes more space. | |
| Prominent with icon | Timer icon + MM:SS in regular weight. More visible. | |

**User's choice:** Adaptive MM:SS / H:MM:SS, dim (Recommended)
**Notes:** None

---

## Claude's Discretion

- Elapsed seconds storage approach
- Icon name resolution
- Gtk.Image construction method

## Deferred Ideas

None
