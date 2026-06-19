---
status: diagnosed
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
source: [95-01-SUMMARY.md]
started: 2026-06-18
updated: 2026-06-19
---

## Current Test

[testing complete]

## Tests

### 1. YouTube URL edit → first-play audio (the bug under fix)
expected: Play a YouTube station, edit its stream URL to a different valid YouTube source, save. New audio starts immediately on the FIRST play — no "stream exhausted" toast, no second play needed.
result: issue
reported: "Almost, I still see the stream exhausted then it goes to the new URL and plays just fine. Core issue is gone, just that minor issue with the toast"
severity: minor

### 2. Metadata-only edit does NOT interrupt (D-02)
expected: While a YouTube station is playing, edit only its label/quality/codec (leave the URL unchanged) and save. Audio continues uninterrupted — no restart, no gap.
result: pass

## Summary

total: 2
passed: 1
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "No 'stream exhausted' toast appears when a YouTube station's URL is edited and saved while playing"
  status: failed
  reason: "User reported: Almost, I still see the stream exhausted then it goes to the new URL and plays just fine. Core issue is gone, just that minor issue with the toast"
  severity: minor
  test: 1
  root_cause: "A QUEUED error-recovery from the OLD exhausted YouTube stream (posted via QueuedConnection from the GST bus thread) runs deferred on the main loop AFTER the synchronous edit→play() restart has emptied _streams_queue for the new (still-resolving) URL and reset _recovery_in_flight=False. With the coalescing guard cleared and the queue empty, _handle_gst_error_recovery calls _try_next_stream() → failover.emit(None) → show_toast('Stream exhausted'). The error-recovery path has no edit/restart generation guard (unlike the _youtube_resolve_seq guard that protects the resolve path)."
  artifacts:
    - path: "musicstreamer/ui_qt/main_window.py"
      line: 909
      issue: "Sole 'Stream exhausted' toast emit site — fires on Player.failover(None)"
    - path: "musicstreamer/player.py"
      line: 1460
      issue: "Sole failover.emit(None) call site — reached only when _streams_queue is empty inside _try_next_stream()"
    - path: "musicstreamer/player.py"
      line: 991
      issue: "_on_gst_error posts _error_recovery_requested as a QueuedConnection — recovery runs deferred on the main loop after edit→play() returns"
    - path: "musicstreamer/player.py"
      line: 687
      issue: "play() resets _recovery_in_flight=False, disarming the only guard that would coalesce away the stale old-URL recovery"
    - path: "musicstreamer/player.py"
      line: 993
      issue: "_handle_gst_error_recovery has NO restart-generation / current-stream guard; a pre-restart recovery advances the freshly-emptied queue"
    - path: "musicstreamer/player.py"
      line: 2050
      issue: "invalidate_for_edit D-01 calls play(station) synchronously, creating the empty-queue + cleared-guard window the stale recovery exploits"
  missing:
    - "Add an edit/restart generation guard to the ERROR-RECOVERY path, mirroring the existing _youtube_resolve_seq idiom: bump a play/restart sequence at the top of play() (and in invalidate_for_edit's restart), stamp it where _error_recovery_requested is emitted, early-return in _handle_gst_error_recovery when the recovery belongs to a superseded generation"
    - "Constraint: must NOT suppress the toast when the queue is genuinely exhausted in the current generation"
  debug_session: ".planning/debug/95-spurious-stream-exhausted-toast.md"
