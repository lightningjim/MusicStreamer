# Phase 50: Recently Played Live Update — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 50-recently-played-live-update
**Areas discussed:** Bump timing, Failed-stream behavior, Visual treatment

---

## Bump timing

| Option | Description | Selected |
|--------|-------------|----------|
| On click (Recommended) | Update the recent list at the same point `update_last_played` already fires (in `_on_station_activated`). Feels instant — matches the moment the user committed to play. | ✓ |
| On playback start | Wait until Player confirms audio is actually playing (e.g., a `player.playing_started` signal). Slight delay (1–5s for streams, up to 15s for YouTube) but the list reflects only stations that actually played. | |
| You decide | Claude picks based on simplest implementation and best UX fit. | |

**User's choice:** On click (Recommended)
**Notes:** Lines up with the existing `update_last_played` call site, no Player signal plumbing needed. Implies failed plays will appear at the top of Recently Played (resolved in next area).

---

## Failed-stream behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — stay (Recommended) | Failed plays appear at top. Matches user mental model ("I just tried that station"), keeps DB and UI consistent (`update_last_played` already fires on click), and means you can re-attempt it from Recently Played without rummaging through the tree. | ✓ |
| No — roll back on failure | If Player emits `playback_error` / failover-exhausted / YouTube-stream-ended, revert `update_last_played` to its prior value and re-render Recently Played. Adds rollback bookkeeping in MainWindow. | |
| You decide | Claude picks based on simplest implementation. | |

**User's choice:** Yes — stay (Recommended)
**Notes:** Recovery affordance — failed station stays one click away in Recently Played for retry.

---

## Visual treatment

| Option | Description | Selected |
|--------|-------------|----------|
| Instant swap (Recommended) | Re-populate the QListView — the new station appears at row 0 with no animation. Matches existing app behavior (`refresh_model` already does instant updates); zero new code beyond the trigger wiring. | |
| Brief highlight on new top row | After the swap, briefly tint or pulse row 0 (e.g., 600ms QPropertyAnimation on background color) to draw the eye. Adds an animation timer + style. | |
| Slide animation | Animate the list reordering (items slide up; new entry slides in from top). Most polished, most code; QAbstractItemView has limited animation support — likely needs a custom delegate or QListView replacement. | |
| You decide | Claude picks based on simplest implementation and parity with the rest of the app. | ✓ |

**User's choice:** You decide → Claude resolved as **Instant swap**.
**Notes:** Bug-fix phase, minimal-diff principle, parity with the existing `_populate_recent` behavior. Polish (highlight, slide) deferred as a future phase if requested.

---

## Claude's Discretion

- **Refresh mechanism (D-04):** direct method call from `MainWindow._on_station_activated` to a new public entry point on `StationListPanel` (likely `refresh_recent()`). No new player/main-window signal — `MainWindow` already owns both repo and panel, signal indirection adds nothing.
- **Visual treatment (D-03):** Instant swap, no animation.
- **Refresh strategy:** full `_populate_recent()` rebuild (3 items) rather than surgical move-to-top.
- **Same-station re-activation:** no special case (idempotent rebuild).

## Deferred Ideas

- **Visual polish (highlight pulse / slide animation):** future phase if requested.
- **Distinguishing "tried" from "successfully played":** would require Player signal plumbing + rollback bookkeeping; explicitly rejected for v2.1 per D-02.
- **`n > 3` for Recently Played size:** not raised; constant stays.
