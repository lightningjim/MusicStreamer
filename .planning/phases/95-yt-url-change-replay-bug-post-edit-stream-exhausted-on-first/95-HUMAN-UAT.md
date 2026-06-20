---
status: diagnosed
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
source: [95-VERIFICATION.md]
started: 2026-06-19
updated: 2026-06-20
---

## Current Test

[testing complete]

## Tests

### 1. YouTube URL edit → first-play audio, NO spurious toast (95-02 gap closure)
expected: Play a YouTube station, edit its URL to a different valid YouTube source, save. New audio starts immediately on the first play — and NO "Stream exhausted" toast appears at any point during the transition (this is the residual flash you reported, now fixed by the _recovery_seq guard). Control check: a station whose every stream genuinely fails should STILL show "Stream exhausted" exactly once — the fix must not over-suppress legitimate exhaustion.
why_human: End-to-end depends on real yt-dlp resolution, the GStreamer bus-thread timing of the old stream's EOS error, and live playbin3 audio output. The spurious-toast race is a QueuedConnection timing issue observable only with a real pipeline.
result: issue
reported: "The 'stream has ended' modal does pop up and I can edit it. When I save I get the first Stream Exhausted then it moves onto the working stream."
severity: minor
note: "Re-opened 2026-06-20 — user now has a station that had to relaunch its stream plus the original URL, so the URL-edit race is actively reproducible. The 95-02 _recovery_seq guard did NOT eliminate the spurious toast in the live scenario: 'Stream Exhausted' still flashes once on save before the working stream plays. Core failover/first-play works; the residual toast the guard targeted persists end-to-end."

## Summary

total: 1
passed: 0
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "No 'Stream exhausted' toast appears when a YouTube station's URL is edited and saved while playing (after the 95-02 _recovery_seq guard)"
  status: failed
  reason: "User reported (live repro, 2026-06-20): 'The stream has ended modal does pop up and I can edit it. When I save I get the first Stream Exhausted then it moves onto the working stream.' The 95-02 _recovery_seq generation guard did not suppress the spurious toast in the real pipeline — it still flashes once on save before the working stream plays."
  severity: minor
  test: 1
  root_cause: "CURRENT-generation false exhaustion during an in-flight async YouTube resolve — NOT a stale (pre-restart) recovery, so the 95-02 _recovery_seq generation guard structurally cannot suppress it. Sequence: old YT live stream already ended (queue drained, 'stream has ended' modal) → user edits URL + saves → invalidate_for_edit → play() runs synchronously: empties _streams_queue, bumps _recovery_seq to generation N, pops the new YT stream, and spawns an async yt-dlp resolve worker (seconds). During that synchronous window two set_state(NULL) teardowns of the still-loaded OLD/ended URI emit message::error on the bus thread; _on_gst_error stamps the recovery with the POST-time seq = N (current), so _handle_gst_error_recovery's guard (N != N = False) PASSES it by design → _try_next_stream() on the still-empty queue (new URL not yet resolved) → failover.emit(None) → show_toast('Stream exhausted'). Seconds later the resolve completes and the working URL plays. V12 even explicitly asserts current-seq pass-through on an empty queue, codifying the exact behavior that fires the toast. A generation guard cannot distinguish genuine all-streams-failed exhaustion from a transiently-empty queue mid-resolve (both carry the current seq)."
  artifacts:
    - path: "musicstreamer/player.py"
      line: 699
      issue: "play() empties _streams_queue and bumps _recovery_seq to generation N, then _try_next_stream() (L849) pops the new YT stream and _play_youtube spawns an async resolve worker — leaving the queue empty for the seconds-long resolve window"
    - path: "musicstreamer/player.py"
      line: 1498
      issue: "set_state(Gst.State.NULL) teardown of the still-loaded OLD/ended URI (also L1918) emits current-generation message::error during the synchronous restart window"
    - path: "musicstreamer/player.py"
      line: 1017
      issue: "_on_gst_error stamps the recovery with the POST-time _recovery_seq (now N, the current generation) — so the delivery is NOT stale and passes the 95-02 guard"
    - path: "musicstreamer/player.py"
      line: 1039
      issue: "_handle_gst_error_recovery 95-02 guard (recovery_seq != self._recovery_seq) passes current-generation deliveries by design; it cannot gate this case"
    - path: "musicstreamer/player.py"
      line: 1507
      issue: "_try_next_stream() empty-queue branch calls failover.emit(None) — the sole exhausted signal — while the new URL is still resolving"
    - path: "musicstreamer/player.py"
      line: 2042
      issue: "_on_youtube_resolution_failed calls _try_next_stream() with NO _recovery_seq / _youtube_resolve_seq guard — secondary unguarded route to a spurious failover(None)"
    - path: "musicstreamer/ui_qt/main_window.py"
      line: 914
      issue: "Sole 'Stream exhausted' toast emit site (on Player.failover(None))"
    - path: "tests/test_player_edit_invalidation.py"
      line: 390
      issue: "V12 explicitly asserts current-seq recovery on an empty queue STILL emits failover(None) — codifies the pass-through that produces the residual toast; no test models a post-bump error during an async resolve"
  missing:
    - "Add a YouTube-resolve-in-flight gate (a generation guard cannot fix this). Set a flag (e.g. _youtube_resolve_in_flight, or store the in-flight resolve generation) TRUE when the resolve worker is spawned in _play_youtube (~player.py:1927); clear it ONLY when the current generation's resolution settles, in BOTH _on_youtube_resolved (success) AND _on_youtube_resolution_failed (failure)."
    - "Before failover.emit(None) in _try_next_stream (player.py:1505-1508) — and before advancing in _handle_gst_error_recovery — do NOT declare exhaustion / emit the toast while a current-generation YouTube resolve is still pending."
    - "Stamp/guard the secondary _on_youtube_resolution_failed → _try_next_stream route (player.py:2042) so a stale OLD-URL resolution-failed delivery after the restart cannot emit a spurious failover(None)."
    - "Hard constraint (preserve V12 intent): when NO resolve is in flight and the queue is genuinely empty, 'Stream exhausted' must still fire exactly once — the gate must not over-suppress legitimate exhaustion."
  debug_session: ".planning/debug/95-residual-exhausted-toast-already-ended-path.md"
