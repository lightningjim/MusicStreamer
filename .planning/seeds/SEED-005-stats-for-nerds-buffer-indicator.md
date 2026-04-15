---
id: SEED-005
status: harvested
harvested_into: Phase 47
harvested_date: 2026-04-14
planted: 2026-04-03
planted_during: v1.4 Phase 16 (GStreamer Buffer Tuning)
trigger_when: when a debug/advanced settings or developer panel phase is planned
scope: small
---

# SEED-005: Stats for nerds — live GStreamer buffer fill indicator

## Why This Matters

After tuning buffer-duration to 5s, there's no visibility into whether the buffer is
actually filling/depleting during playback. A live indicator (percent bar or label) would
help diagnose future drop-out reports and let curious users see the stream health at a glance.

## When to Surface

**Trigger:** When a debug/advanced settings phase is planned, or when a "stream diagnostics" milestone is scoped.

This seed should be presented during `/gsd:new-milestone` when the milestone scope matches:
- A "developer tools" or "debug overlay" feature
- An advanced/settings panel phase
- Any work touching the now-playing panel that would make a debug row easy to add

## Scope Estimate

**Small** — GStreamer already emits `message::buffering` on the pipeline bus with a `percent` field (0–100). Wiring it is ~10 lines in `player.py`. The UI is a progress bar or `{N}%` label in the now-playing panel, behind a toggle or collapsible row.

## Breadcrumbs

- `musicstreamer/player.py` — pipeline bus is already set up with `add_signal_watch()`; add `bus.connect("message::buffering", self._on_gst_buffering)` alongside existing handlers
- `musicstreamer/constants.py:8` — `BUFFER_DURATION_S` / `BUFFER_SIZE_BYTES` defined here (Phase 16)
- `musicstreamer/ui/main_window.py` — now-playing panel is where the indicator would live

## Notes

Came up immediately after Phase 16 landed. User asked "is there a possibility to have a
stats for nerds thing that shows the size of the buffer as it fills up/depletes?" —
GStreamer's `BUFFERING` message with `parse_buffering()` percent is the exact hook needed.
