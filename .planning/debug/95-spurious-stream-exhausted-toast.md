---
status: diagnosed
slug: 95-spurious-stream-exhausted-toast
trigger: "Phase 95 UAT Test 1 (minor) — after editing a playing YouTube station's stream URL, a 'Stream exhausted' toast still flashes briefly before the new URL resolves and plays fine. Core replay bug is fixed; only the spurious toast remains."
phase_ref: 95
created: 2026-06-19T00:00:00Z
updated: 2026-06-19T00:00:00Z
goal: find_root_cause_only
---

## Symptoms

DATA_START
- **Expected behavior:** Edit a currently-playing YouTube station's stream URL to a different valid source and save → the new stream plays on the first play with NO "Stream exhausted" toast.
- **Actual behavior:** The new stream DOES play on first play (core fix works), but a "Stream exhausted" toast flashes briefly on screen during the edit→restart transition, then the player switches to the new URL and plays fine. Verbatim: "Almost, I still see the stream exhausted then it goes to the new URL and plays just fine. Core issue is gone, just that minor issue with the toast"
- **Error messages:** "Stream exhausted" toast (cosmetic only; playback recovers).
- **Reproduction:** Play a YouTube station whose resolved HLS source is (or becomes) exhausted/at-EOS. Edit its stream URL to a different valid source, save. Observe the brief "Stream exhausted" toast before the new stream starts.
- **Started:** After Phase 95 (the D-01 `invalidate_for_edit` → `play(station)` restart path). The core URL-change replay bug is fixed; this residual toast is the leftover symptom.
DATA_END

## Current Focus

hypothesis: A queued `_error_recovery_requested` slot from the OLD (exhausted) YouTube stream survives the synchronous `play(station)` restart and runs AFTER `play()` has already drained `_streams_queue` for the new (async, not-yet-resolved) YouTube URL. `_handle_gst_error_recovery` → `_try_next_stream()` finds the queue empty → `failover.emit(None)` → `_on_failover(None)` → `show_toast("Stream exhausted")`. The `_recovery_in_flight` coalescing guard does NOT protect against this because `play()` RESETS it to False (player.py:687), and there is no edit/restart generation guard on the error-recovery path (unlike the `_youtube_resolve_seq` guard that protects the resolve path).
test: Code trace head-to-tail through player.py + main_window.py (cross-thread signal ordering).
expecting: The single `failover.emit(None)` site (player.py:1460) is reachable via a queued error-recovery from the old URI after play() has emptied the queue but before the new YouTube resolution returns.
next_action: Diagnose-only mode — report root cause, do not fix.
reasoning_checkpoint: done (see Resolution)

## Evidence

- timestamp: 2026-06-19T00:00:00Z
  source: musicstreamer/ui_qt/main_window.py:906-912 (read)
  finding: |
    The "Stream exhausted" toast has exactly ONE emit site:
      def _on_failover(self, next_stream):
          if next_stream is None:
              self.show_toast("Stream exhausted")   # L909
              ...
    `_on_failover` is wired to `Player.failover` (main_window.py:481). So the toast fires
    iff `Player.failover.emit(None)` is called.

- timestamp: 2026-06-19T00:00:01Z
  source: musicstreamer/player.py (grep failover.emit)
  finding: |
    `self.failover.emit(None)` has exactly ONE call site: player.py:1460, inside
    `_try_next_stream()` when `not self._streams_queue` (empty queue → "All streams exhausted").
    Therefore the spurious toast == a spurious `_try_next_stream()` call against an EMPTY queue.

- timestamp: 2026-06-19T00:00:02Z
  source: musicstreamer/player.py:2050-2055 (invalidate_for_edit D-01 path) + play() 682-828
  finding: |
    D-01 restart: `invalidate_for_edit(station, is_playing=True)` with a changed playing-stream URL
    calls `self.play(station)` SYNCHRONOUSLY on the main thread. play():
      - _cancel_timers()                     (L685 — stops the failover QTimer)
      - self._streams_queue = []             (L686)
      - self._recovery_in_flight = False     (L687)  <-- RESETS the coalescing guard
      - rebuilds _streams_queue from the NEW station (1 YT stream)
      - _try_next_stream()                   (L828)
        → pops the single new stream → _streams_queue is now EMPTY
        → url is youtube.com → _play_youtube(new_url)  (L1501-1502)
          → set_state(NULL) + spawns _youtube_resolve_worker on a DAEMON thread (L1880-1882)
    The new YouTube URL takes SECONDS to resolve (yt-dlp + Node EJS solver). During that window
    `_streams_queue` is EMPTY and `_recovery_in_flight` is False.

- timestamp: 2026-06-19T00:00:03Z
  source: musicstreamer/player.py:983-991 (_on_gst_error) + 523-525 (_error_recovery_requested wiring)
  finding: |
    The OLD exhausted YouTube HLS stream causes playbin3 to emit message::error on the bus.
    `_on_gst_error` runs on the GstBusLoopThread (daemon) and does:
        self.playback_error.emit(...)
        self._tracker.note_error_in_cycle()
        self._error_recovery_requested.emit()      # L991 — QUEUED signal to main thread
    `_error_recovery_requested` is connected with Qt.ConnectionType.QueuedConnection
    (L523-525) → `_handle_gst_error_recovery`. So the recovery does NOT run inline; it is
    POSTED to the main-thread event queue and runs on a later event-loop turn.

- timestamp: 2026-06-19T00:00:04Z
  source: musicstreamer/player.py:993-1035 (_handle_gst_error_recovery)
  finding: |
    `_handle_gst_error_recovery`:
      if self._recovery_in_flight: return       # coalescing guard ONLY
      self._recovery_in_flight = True
      self._cancel_timers()
      ... (preroll / twitch branches not taken for a plain YT stream) ...
      self._try_next_stream()                   # L1034 → empty queue → failover.emit(None)
      QTimer.singleShot(0, self._clear_recovery_guard)
    There is NO check that the errored URL is still the current stream, and NO edit/restart
    generation guard. The ONLY thing that would block it is `_recovery_in_flight == True` —
    which play() explicitly cleared at L687.

- timestamp: 2026-06-19T00:00:05Z
  source: cross-thread ordering analysis
  finding: |
    RACE / ORDERING (all on the main-thread event queue):
      T0  OLD YT stream exhausts → playbin3 message::error on bus thread
      T1  _on_gst_error (bus thread) → _error_recovery_requested.emit() → QUEUED slot R pending
      T2  user saves edit → _sync_now_playing_station → invalidate_for_edit → play(new_station)
          runs synchronously NOW (main thread), drains _streams_queue to EMPTY, resets
          _recovery_in_flight=False, spawns the async YT resolve worker, returns.
      T3  main event loop dispatches the still-pending queued slot R →
          _handle_gst_error_recovery → guard is False → _try_next_stream() →
          _streams_queue empty → failover.emit(None) → _on_failover(None) →
          show_toast("Stream exhausted")            <-- THE SPURIOUS TOAST
      T4  (seconds later) _youtube_resolve_worker finishes → youtube_resolved(seq) →
          _on_youtube_resolved → seq matches → _set_uri(new_url) → plays fine.
    Also note the teardown set_state(NULL) on the OLD URI in _play_youtube:1871 / _try_next_stream:1451
    can itself emit additional cascading errors for the old URI, producing MORE queued R slots —
    but only ONE needs to slip past the (reset) guard to fire the toast.
    This exactly reproduces "I still see the stream exhausted THEN it goes to the new URL and plays fine."

- timestamp: 2026-06-19T00:00:06Z
  source: musicstreamer/player.py:1718-1745 (_on_gst_eos_during_preroll) — ELIMINATION
  finding: |
    EOS is NOT the toast source. The only message::eos handler early-returns when
    `_preroll_in_flight` is False (L1738), so a streaming-path EOS never reaches _try_next_stream.
    The spurious toast therefore comes from the message::error → _error_recovery_requested path,
    not from EOS.

- timestamp: 2026-06-19T00:00:07Z
  source: .planning/debug/resolved/stream-exhausted-premature.md (read)
  finding: |
    The Phase 47 `_recovery_in_flight` guard was designed to coalesce CASCADING errors for a
    SINGLE failing URL within one play session. It is explicitly cleared by play()/play_stream()/
    stop()/pause() "so a new user action cannot inherit a stale guard." That deliberate reset is
    exactly what re-opens the door here: the edit-triggered play() clears the guard, so a queued
    recovery from the OUTGOING (pre-edit) URL is no longer coalesced and fires once against the
    freshly-emptied queue. The guard was never meant to span a station restart — but the
    edit→restart sequence needs precisely that protection.

## Eliminated

- "Toast comes from a leftover OLD failover QTimer firing _on_timeout."
  evidence: play() calls _cancel_timers() at L685 BEFORE rebuilding, which stops the failover
  QTimer. A stale single-shot timer from the old stream cannot fire after play() runs.
  timestamp: 2026-06-19T00:00:08Z

- "Toast comes from a streaming-path EOS on the old exhausted HLS stream."
  evidence: player.py:1738 — the sole message::eos handler returns immediately unless a preroll is
  in flight; the streaming path has no EOS→failover bridge. Toast is from message::error, not EOS.
  timestamp: 2026-06-19T00:00:09Z

- "Stale YouTube resolution of the OLD URL clobbers the new URL (the V5 race)."
  evidence: Already closed by the Phase 95 _youtube_resolve_seq guard (player.py:1985-1986).
  invalidate_for_edit bumps the seq (L2029) and play()→_play_youtube captures the new seq;
  a late OLD resolution no-ops. This guard protects the RESOLVE path but does NOT cover the
  ERROR-RECOVERY path — which is the actual gap.
  timestamp: 2026-06-19T00:00:10Z

## Resolution

root_cause: |
  The Phase 95 D-01 restart (`invalidate_for_edit` → `play(station)`) runs synchronously and
  immediately empties `_streams_queue` for the new YouTube URL (whose resolution is async and
  takes seconds), while ALSO resetting `_recovery_in_flight = False` (player.py:687). A
  `message::error` from the OLD (exhausted) YouTube stream — emitted before the edit and/or during
  the old-pipeline teardown — is delivered to `_handle_gst_error_recovery` via a QUEUED
  `_error_recovery_requested` signal that is still pending on the main-thread event loop. Because
  that slot runs AFTER `play()` has cleared the coalescing guard and emptied the queue, it sails
  past the only existing guard and calls `_try_next_stream()` on an empty queue →
  `failover.emit(None)` (player.py:1460) → `_on_failover(None)` → `show_toast("Stream exhausted")`
  (main_window.py:909). Moments later the new YouTube resolution returns and `_set_uri` plays the
  new URL fine. The Phase 95 `_youtube_resolve_seq` generation guard protects the RESOLVE path but
  there is no equivalent generation guard on the ERROR-RECOVERY path, so a stale error-recovery
  from the outgoing URL produces the spurious toast.

reasoning_checkpoint:
  hypothesis: "A queued error-recovery from the OLD exhausted YouTube stream runs after the
    synchronous edit→play() has emptied the queue and reset _recovery_in_flight, hitting
    _try_next_stream() with an empty queue and emitting failover(None) → the spurious toast."
  confirming_evidence:
    - "failover.emit(None) has a single call site (player.py:1460) reachable only with an empty queue."
    - "_error_recovery_requested is a QueuedConnection (player.py:523-525) → recovery is deferred to a later main-loop turn, AFTER the synchronous play() returns."
    - "play() resets _recovery_in_flight=False (L687) and drains _streams_queue, then _play_youtube spawns an async worker leaving the queue empty for seconds."
    - "_handle_gst_error_recovery has no generation/current-stream guard — only the _recovery_in_flight coalescing flag, which play() just cleared."
  falsification_test: "If the toast still fired with _streams_queue NON-empty at the moment recovery
    runs, or if EOS (not error) were the trigger, the hypothesis would be wrong. EOS is eliminated
    (1738 early-return); the queue is provably empty post-_play_youtube. Runtime confirmation:
    log every failover.emit(None) with a stack + the in-flight resolve seq; the spurious one will
    show a stack through _handle_gst_error_recovery and a _current_stream pointing at the OLD url."
  fix_rationale: "Guarding the error-recovery path against stale (pre-restart) deliveries — mirroring
    the existing _youtube_resolve_seq idiom — addresses the root cause (a stale async event acting on
    fresh state) rather than suppressing the toast globally, so a genuinely-exhausted queue still toasts."
  blind_spots: "Not verified at runtime that the OLD HLS exhaustion surfaces as message::error vs a
    silent EOS; if it is EOS-only in some YT-live cases, the recovery path wouldn't be the trigger
    (but the streaming EOS handler early-returns, so no toast there either — would need a different
    explanation). Also not measured: how many cascading old-URI errors land, though one suffices."

fix: |
  (DIAGNOSE-ONLY — not applied.) Add an edit/restart generation guard to the ERROR-RECOVERY path,
  mirroring the Phase 95 _youtube_resolve_seq guard that already protects the resolve path. Concrete
  options, smallest first:

  1. RECOMMENDED — restart-generation guard on recovery. Introduce a `_play_seq` (or reuse/extend the
     existing generation idea) that is bumped at the TOP of play() (and in invalidate_for_edit's
     restart). Capture it where _error_recovery_requested is emitted (stamp carried on the signal, or
     compared against a `_recovery_valid_after` marker), and early-return in _handle_gst_error_recovery
     when the recovery was scheduled for a superseded generation. This makes a pre-restart error-recovery
     no-op without touching the legitimate same-session cascade-coalescing behavior.

  2. ALTERNATIVE — current-stream identity check. In _handle_gst_error_recovery, before advancing,
     verify the recovery still corresponds to _current_stream (e.g. the error's URL/stream matches the
     stream currently loaded). A recovery whose target is no longer the current stream (because play()
     swapped it) no-ops. Requires threading the failing URL/stream identity from _on_gst_error to the
     handler.

  3. NARROWER — do not clear _recovery_in_flight in the EDIT-restart path. The general play() reset
     (L687) is intentional for fresh user actions, but the invalidate_for_edit→play restart could keep
     the guard armed across the swap (or re-arm it for one event-loop turn) so a queued old-URL recovery
     is coalesced away. Risk: more subtle / order-dependent than the explicit generation guard, and the
     guard semantics (per-URL coalescing) don't cleanly express "ignore pre-restart deliveries."

  Whichever path: the guard MUST NOT suppress the toast when the queue is GENUINELY exhausted in the
  current generation (real all-streams-failed case). Verify with: (a) edit a playing YT station's URL →
  no "Stream exhausted" toast, new URL plays; (b) a station whose every stream truly fails → toast still
  fires exactly once.

verification: |
  (Not performed — diagnose-only.) Suggested regression test in tests/test_player_edit_invalidation.py
  or tests/test_player_failover.py:
    - Arrange a playing YT station; simulate a pending/old-URL error recovery being queued.
    - Call invalidate_for_edit(updated_station, is_playing=True) (D-01 → play()).
    - Then invoke the (stale) _handle_gst_error_recovery; assert failover(None) is NOT emitted
      (no "Stream exhausted") and the new stream's resolve path proceeds.
    - Control test: a same-generation empty-queue recovery STILL emits failover(None).

files_changed: []
