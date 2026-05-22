---
status: partial
phase: 83-at-start-of-playing-a-station-randomly-select-and-play-one-o
source:
  - 83-01-SUMMARY.md
  - 83-02-SUMMARY.md
  - 83-03-SUMMARY.md
started: 2026-05-22
updated: 2026-05-22
---

## Current Test

[testing complete — 1 pass, 1 issue (blocker), 2 blocked-by-prior]

## Tests

### 1. Beat Blender preroll → stream gapless handoff
expected: |
  Bind SomaFM Beat Blender. Click Play. Hear one of three station-ID voiceover clips
  (~5-8s), then deep-house stream begins gaplessly. Now Playing shows "Beat Blender"
  throughout (no preroll title flicker). Covers D-05 + D-07.
result: issue
reported: "Going straight to the stream — no preroll voiceover at all. DB has the 4 preroll URLs for Beat Blender stored correctly; provider_name is 'SomaFM'; eager-load returns 4 URLs in the Station object. The preroll gate fires, but the pipeline never plays the preroll audibly."
severity: blocker
root_cause: |
  `_on_preroll_about_to_finish` (musicstreamer/player.py:1124-1135) calls
  `_try_next_stream()` which immediately does `set_state(NULL)` →
  `set_property("uri", stream_url)` → `set_state(PLAYING)` (player.py:1043,1091-1094).
  That tears down the preroll mid-playback and restarts the pipeline on the stream
  URL from scratch.

  The playbin3 `about-to-finish` signal is the *gapless* handoff mechanism: the
  next URI must be set on the still-PLAYING pipeline via a plain
  `pipeline.set_property("uri", next_url)` — playbin3 then plays the current
  track to EOS and transitions seamlessly. Setting `set_state(NULL)` defeats
  this entirely; the live spike confirmed `about-to-finish` fires very early
  (before PLAYING is even reached), so the pipeline is torn down before any
  preroll audio reaches the speakers.

  The 83-RESEARCH §Open Questions Q1 spike measured a `+7.849s STREAM_START`
  for the stream URI, which matched the preroll's 7.99s duration — but that
  was with a SINGLE pipeline using gapless URI handoff (`set_property` only,
  no state change). The shipped code does state cycling instead, so the
  preroll never reaches audible playback.
artifacts:
  - musicstreamer/player.py:1124-1135 (_on_preroll_about_to_finish — wrong: calls _try_next_stream)
  - musicstreamer/player.py:1040-1087 (_try_next_stream — sets state NULL)
  - musicstreamer/player.py:1089-1094 (_set_uri — sets state NULL then PLAYING)
missing:
  - "Gapless URI handoff: in the about-to-finish path, set pipeline `uri` property directly on the still-PLAYING pipeline — do NOT cycle through NULL."
  - "Streaming-thread-safe set_property: `pipeline.set_property('uri', next_url)` is a pure GObject call, safe from the about-to-finish callback (the qt-glib threading rule applies to Qt operations and pipeline state changes, not to plain property sets)."
  - "Phase 83 scope: only direct HTTP(S) stream URLs reach the gapless handoff (SomaFM provider gate; SomaFM streams are direct ICE relays). YouTube/Twitch async-resolution paths are not in the SomaFM preroll codepath, so the simple set_property pattern suffices for this phase."
  - "Main-thread bookkeeping: pop _streams_queue, update _current_stream, bind tracker — but do NOT set pipeline state. The pipeline keeps playing through the gapless transition."

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
result: blocked
blocked_by: prior-phase
reason: "Depends on Test 1 (preroll playback) which is blocked by the gapless-handoff bug. Cannot verify throttle suppression of a feature that doesn't audibly play."

### 4. Throttle after 10 minutes — preroll plays again
expected: |
  Wait at least 10 minutes after the throttle-suppressed replay (test 3). Click Play on
  Beat Blender again. Preroll plays this time — confirms the throttle gate clears after
  the 10-min window elapses. Covers D-12 window expiry.

  (If you don't want to wait, you can simulate by restarting the app — the throttle
  state lives in memory only, so a fresh launch always plays the preroll on first
  SomaFM station.)
result: blocked
blocked_by: prior-phase
reason: "Depends on Test 1 (preroll playback) which is blocked by the gapless-handoff bug."

## Summary

total: 4
passed: 1
issues: 1
pending: 0
skipped: 0
blocked: 2

## Gaps

- truth: "D-05: Phase 83's user-observable goal — SomaFM preroll plays audibly for ~5-8s, then transitions gaplessly into the station stream."
  status: failed
  reason: "User reported: Going straight to the stream — no preroll voiceover at all. DB-layer data is correct (4 prerolls stored for Beat Blender, provider_name='SomaFM', eager-load returns them in the Station object). The preroll gate in Player.play fires, but the pipeline never plays the preroll audibly."
  severity: blocker
  test: 1
  artifacts:
    - musicstreamer/player.py:1124-1135 (_on_preroll_about_to_finish — wrong: calls _try_next_stream)
    - musicstreamer/player.py:1040-1087 (_try_next_stream — sets state NULL)
    - musicstreamer/player.py:1089-1094 (_set_uri — sets state NULL then PLAYING)
  missing:
    - "Gapless URI handoff: in the about-to-finish path, set pipeline `uri` property directly on the still-PLAYING pipeline — do NOT cycle through NULL."
    - "Main-thread bookkeeping pops _streams_queue + updates _current_stream + binds tracker but does NOT touch pipeline state. The pipeline keeps playing through the gapless transition."
    - "Phase 83 scope guarantee: only direct HTTP(S) stream URLs reach the gapless handoff (SomaFM provider gate; SomaFM streams are direct ICE relays). YouTube/Twitch async-resolution paths are not in the SomaFM preroll codepath, so the simple set_property pattern suffices for this phase."
