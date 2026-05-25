---
status: complete
phase: 83-at-start-of-playing-a-station-randomly-select-and-play-one-o
source:
  - 83-01-SUMMARY.md
  - 83-02-SUMMARY.md
  - 83-03-SUMMARY.md
  - 83-04-SUMMARY.md
started: 2026-05-22
updated: 2026-05-22
---

## Current Test

[testing complete — 4 pass, 0 issues, 0 blocked]

## Tests

### 1. Beat Blender preroll → stream gapless handoff
expected: |
  Bind SomaFM Beat Blender. Click Play. Hear one of three station-ID voiceover clips
  (~5-8s), then deep-house stream begins gaplessly. Now Playing shows "Beat Blender"
  throughout (no preroll title flicker). Covers D-05 + D-07.
result: pass
notes: |
  Initial reading was "wasn't quite gaplessly but it definitely happened" — diagnosed
  as content, not code. User cross-checked with other SomaFM stations: those preroll
  m4a files transition immediately, while Beat Blender's specific preroll has a
  longer trailing silence in the audio file itself. playbin3's gapless handoff is
  working correctly (set_property on still-PLAYING pipeline). D-05 + D-07 ✓.
history: |
  2026-05-22 (pre-83-04): result=issue (blocker). `_on_preroll_about_to_finish` called
  `_try_next_stream()` which set_state(NULL) — preroll torn down before reaching
  speakers. Closed by Plan 83-04: gapless URI handoff via `set_property("uri", ...)` on
  still-PLAYING pipeline (player.py:1124-1205). Commits: 6994b3d, 72a0ebf, fef340e.
  2026-05-22 (post-83-04, pass 1): user reported "not quite gaplessly" — initially
  logged as minor D-07 issue.
  2026-05-22 (post-83-04, pass 2): user cross-checked other stations — discontinuity
  is content-level silence in Beat Blender's preroll audio file, not a code-level
  gapless failure. Reclassified to pass.

### 2. Seven Inch Soul (no preroll) — straight to stream
expected: |
  Bind SomaFM Seven Inch Soul. Click Play. Vintage soul track begins immediately with
  no preroll preamble (Seven Inch Soul has an empty preroll[] array on the API side, so
  the player gate skips preroll for this station). The first play may briefly trigger
  the background backfill fetch — that runs invisibly and does NOT delay playback.
  Covers D-04 + D-11.
result: pass

### 3. Throttle within 10 minutes — replay suppresses preroll
expected: |
  Immediately after test 1 (Beat Blender preroll played), Stop, then re-bind Beat Blender
  (or just click Play again on the same station). The stream should start IMMEDIATELY
  with NO preroll — the in-memory throttle gate (10 min window via
  Player._last_preroll_played_at) suppresses the second preroll. Covers D-12 window
  suppression.
result: pass
history: |
  2026-05-22 (pre-83-04): result=blocked (prior-phase) on test 1's blocker.
  Unblocked by Plan 83-04. 2026-05-22 (post-83-04): pass.

### 4. Throttle after 10 minutes — preroll plays again
expected: |
  Wait at least 10 minutes after the throttle-suppressed replay (test 3). Click Play on
  Beat Blender again. Preroll plays this time — confirms the throttle gate clears after
  the 10-min window elapses. Covers D-12 window expiry.

  (If you don't want to wait, you can simulate by restarting the app — the throttle
  state lives in memory only, so a fresh launch always plays the preroll on first
  SomaFM station.)
result: pass
verified_via: restart-as-simulation (app relaunch clears _last_preroll_played_at)
history: |
  2026-05-22 (pre-83-04): result=blocked (prior-phase) on test 1's blocker.
  Unblocked by Plan 83-04. 2026-05-22 (post-83-04): pass via restart simulation.

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none — Test 1 initial "not gapless" reading reclassified to content-level
silence in Beat Blender's preroll audio file (other stations transition cleanly).
playbin3 gapless handoff verified working.]
