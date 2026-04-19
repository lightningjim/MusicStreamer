---
created: 2026-04-19T18:09:28.334Z
title: EQ toggle causes brief audio dropout
area: audio
files:
  - musicstreamer/player.py — _apply_eq_state bypass branch
  - musicstreamer/ui_qt/now_playing_panel.py:245 — eq_toggle_btn
  - .planning/phases/47.2-autoeq-parametric-eq-import/47.2-CONTEXT.md (D-05)
---

## Problem

Clicking the EQ on/off toggle button in the now-playing panel produces a brief but audible audio dropout. Per Phase 47.2 CONTEXT D-05, the toggle is supposed to bypass the EQ by zeroing all band gains on the existing `equalizer-nbands` element — no pipeline state transition, no element rebuild, and therefore no dropout. Observed behavior contradicts the design contract.

Surfaced during Phase 47.2 UAT on 2026-04-19.

## Solution

TBD — investigation needed. Starting points:

1. Read `_apply_eq_state` in `musicstreamer/player.py` (added in Plan 47.2-02) and confirm the bypass branch only mutates band gain properties; nothing else (no `set_state`, no `audio-filter` reassignment, no element recreation).
2. Check whether `band.set_property("gain", 0.0)` on `equalizer-nbands` triggers caps renegotiation inside GStreamer — may need to set gains in a specific order, or set them under a `GstStructure` batch update if one exists.
3. Verify `set_eq_enabled` is being called only once per click (no double-toggle from the checkable button's `toggled` signal + a manually-connected `clicked` handler).
4. Consider adding a small hysteresis: only zero-out gains once and cache the zeroed state, so repeated toggles don't re-write properties that are already zero.

Severity: low. Feature works; cosmetic audio artifact only.

## Notes

- Profile-swap dropouts WHERE band count changes are expected (D-04 rebuilds the element) — those are out of scope for this todo.
- Same-band-count profile swaps should also be dropout-free; user has not yet confirmed whether those drop out.
