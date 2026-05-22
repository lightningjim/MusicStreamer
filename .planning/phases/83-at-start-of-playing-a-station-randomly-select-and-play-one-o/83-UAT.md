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

[testing complete — 3 pass, 1 minor issue (D-07 partial gapless), 0 blocked]

## Tests

### 1. Beat Blender preroll → stream gapless handoff
expected: |
  Bind SomaFM Beat Blender. Click Play. Hear one of three station-ID voiceover clips
  (~5-8s), then deep-house stream begins gaplessly. Now Playing shows "Beat Blender"
  throughout (no preroll title flicker). Covers D-05 + D-07.
result: issue
reported: "It wasn't quite gaplessly but it definitely happened."
severity: minor
notes: |
  D-05 (preroll plays audibly) is CLOSED — user confirmed preroll → stream
  transition occurred. D-07 (gapless handoff) is partial — user heard a
  perceptible discontinuity at the preroll→stream boundary. Plan 83-04's
  `set_property("uri", ...)` on the still-PLAYING pipeline is the canonical
  playbin3 gapless idiom; an audible gap here suggests one of:
    (a) about-to-finish fires slightly late vs the preroll EOS, leaving
        a brief silence (playbin3's lookahead buffer for the new URI is
        not arriving in time),
    (b) the new URI's first audio packets are delayed (ICE-relay TCP
        connect latency for the SomaFM stream),
    (c) codec/sample-rate transition between the m4a preroll and the
        AAC/MP3 SomaFM stream forces a brief audiosink reconfigure.
  Treat as observation; not a regression vs the prior (broken) behavior.
history: |
  2026-05-22 (pre-83-04): result=issue (blocker). `_on_preroll_about_to_finish` called
  `_try_next_stream()` which set_state(NULL) — preroll torn down before reaching
  speakers. Closed by Plan 83-04: gapless URI handoff via `set_property("uri", ...)` on
  still-PLAYING pipeline (player.py:1124-1205). Commits: 6994b3d, 72a0ebf, fef340e.
  2026-05-22 (post-83-04): preroll plays audibly (D-05 ✓); transition not fully
  gapless (D-07 partial — minor).

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
passed: 3
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "D-07: SomaFM preroll transitions gaplessly into the station stream."
  status: failed
  reason: "User reported: It wasn't quite gaplessly but it definitely happened. D-05 audibility ✓, D-07 gapless quality partial."
  severity: minor
  test: 1
  artifacts:
    - musicstreamer/player.py:1124-1205 (_on_preroll_about_to_finish — gapless handoff implementation)
  missing:
    - "Investigate whether about-to-finish lookahead timing leaves a brief silence vs the canonical playbin3 gapless behavior (preroll EOS → stream first-sample latency)."
    - "Possibly: per-codec audiosink reconfigure cost between m4a preroll and AAC/MP3 stream (codec transition stall)."
    - "Possibly: ICE-relay TCP connect latency for the SomaFM stream URL — first audio packet may arrive after preroll EOS."
