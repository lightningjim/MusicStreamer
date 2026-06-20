---
status: diagnosed
slug: 95-residual-exhausted-toast-already-ended-path
trigger: "Phase 95 UAT Test 1 re-opened (live, 2026-06-20): editing a YouTube station whose old stream had ALREADY ended (a 'stream has ended' modal was showing) → on save, a single 'Stream exhausted' toast flashes, THEN the new working stream plays. The 95-02 _recovery_seq guard did NOT eliminate the toast in this real path."
phase_ref: 95
created: 2026-06-20T00:00:00Z
updated: 2026-06-20T00:00:00Z
goal: find_root_cause_only
---

## Symptoms

DATA_START
- **Expected behavior:** Edit a YouTube station whose live stream has ended (the "stream has ended" modal is showing), choose Update URL, save the new (working) URL → the new stream plays on the first play with NO "Stream exhausted" toast.
- **Actual behavior:** Verbatim — "The 'stream has ended' modal does pop up and I can edit it. When I save I get the first Stream Exhausted then it moves onto the working stream." A single "Stream exhausted" toast flashes on save, then the new working YouTube URL plays. Core first-play fix works; the residual toast persists.
- **Error messages:** "Stream exhausted" toast (cosmetic). Underlying old-stream error is yt-dlp "This live stream recording is not available." (drives the modal).
- **Reproduction:** Play a YouTube live station whose broadcaster has ended the live stream. The yt-dlp resolution fails with "live stream recording is not available" → "YouTube live stream ended" modal. Click Update URL…, change to a working URL, save. Observe one "Stream exhausted" toast before the new stream plays.
- **Started:** After Phase 95-02. The 95-02 _recovery_seq guard closed the EARLIER flash (old stream errored on the bus before the edit, recovery POSTED pre-restart). This residual toast survives in the "already-ended-before-edit" path.
DATA_END

## Current Focus

hypothesis: The residual toast is NOT a stale (pre-restart) recovery — the 95-02 guard correctly kills those. It is a CURRENT-generation false exhaustion produced when the edit→restart `play()` empties `_streams_queue` for the new YouTube URL whose resolution is ASYNC. An error POSTED to the bus AFTER `play()` bumped `_recovery_seq` (during the resolve window, e.g. the old-URI teardown's `set_state(NULL)` in `_play_youtube`/`_try_next_stream` emitting message::error) carries the NEW (current) `_recovery_seq`, so it PASSES the generation guard, reaches `_handle_gst_error_recovery` → `_try_next_stream()` on the still-empty queue → `failover.emit(None)` → "Stream exhausted". A generation guard fundamentally cannot catch this because the stamp is current. The fix needs a "YouTube resolve in flight for the current generation" gate on the exhausted-toast path.
test: Head-to-tail code trace through player.py + main_window.py, cross-referencing the V11/V12/V13 unit-test timing vs the real already-ended pipeline timing.
expecting: A bus message::error timestamped AFTER the play() bump (current _recovery_seq) reaches _handle_gst_error_recovery and hits an empty queue while the new YT resolve worker is still running.
next_action: Diagnose-only — report root cause, do not fix.
reasoning_checkpoint: done (see Resolution)

## Evidence

- timestamp: 2026-06-20T00:00:00Z
  source: musicstreamer/ui_qt/main_window.py:911-919, 928-937, 952-982 (read)
  finding: |
    The "stream has ended" MODAL is NOT the EOS handler — it is `_on_playback_error`
    matching the substring "live stream recording is not available" (L935) →
    `_show_youtube_stream_ended_dialog()` (L952). That error string originates from
    yt-dlp on the OLD live stream and arrives via `youtube_resolution_failed` →
    `_on_youtube_resolution_failed` → `playback_error.emit(...)`. The "Update URL…"
    button (L971/981) routes to `_on_edit_requested(station)` → EditStationDialog →
    on save → `_sync_now_playing_station` (L1346 connect) → `invalidate_for_edit`.
    The "Stream exhausted" TOAST has exactly ONE emit site: `_on_failover(None)` →
    `show_toast("Stream exhausted")` (main_window.py:914), wired to `Player.failover`
    (L486). So the toast == `Player.failover.emit(None)`.

- timestamp: 2026-06-20T00:00:01Z
  source: musicstreamer/player.py:1495-1508 (_try_next_stream) + 2038-2042 (_on_youtube_resolution_failed)
  finding: |
    `failover.emit(None)` has ONE call site: player.py:1507, inside `_try_next_stream()`
    when `not self._streams_queue`. CRITICAL: `_on_youtube_resolution_failed` (L2042)
    calls `self._try_next_stream()` DIRECTLY with NO seq guard of any kind. This is the
    OLD-stream failure path that produced the modal: the single YT stream was already
    popped, the queue is EMPTY, resolution failed → _try_next_stream() → failover(None).
    (At THIS point the user has the modal open; the first failover(None) here is the
    pre-edit one — not the toast the user reports on SAVE.)

- timestamp: 2026-06-20T00:00:02Z
  source: musicstreamer/player.py:695-708 (play() entry) + 1918-1929 (_play_youtube) + 1495-1549 (_try_next_stream)
  finding: |
    The D-01 restart on SAVE runs synchronously on the main thread:
      play(new_station):
        L698 _cancel_timers()
        L699 _streams_queue = []
        L700 _recovery_in_flight = False
        L708 _recovery_seq += 1          <-- NEW generation N
        ... rebuilds _streams_queue = [new_yt_stream]
        L849 _try_next_stream()
          L1498 _pipeline.set_state(Gst.State.NULL)   <-- TEARS DOWN OLD URI
          L1504 _pipeline.get_state(CLOCK_TIME_NONE)
          L1509 stream = _streams_queue.pop(0)        <-- queue now EMPTY again
          L1548 "youtube.com" in url → _play_youtube(new_url)
            L1918 _pipeline.set_state(Gst.State.NULL)  <-- second NULL on the pipeline
            L1919 _pipeline.get_state(CLOCK_TIME_NONE)
            L1926 seq = _youtube_resolve_seq
            L1927-1929 spawn _youtube_resolve_worker DAEMON thread → returns immediately
    After play() returns, `_streams_queue` is EMPTY, `_recovery_in_flight` is False,
    and the NEW YouTube URL is still resolving on a daemon thread (yt-dlp + Node EJS:
    SECONDS). `_recovery_seq` is now N (the CURRENT generation).

- timestamp: 2026-06-20T00:00:03Z
  source: musicstreamer/player.py:1004-1017 (_on_gst_error) + 445 (bus message::error wiring) + 513-525 (queued connections)
  finding: |
    `_on_gst_error` runs on the GstBusLoopThread (daemon, no Qt loop). It reads
    `self._recovery_seq` AT POST TIME and emits `_error_recovery_requested.emit(self._recovery_seq)`
    (L1017), a QueuedConnection (L523-525) → `_handle_gst_error_recovery` on a later
    main-loop turn. KEY: the stamp is whatever `_recovery_seq` is WHEN THE ERROR IS
    POSTED. The two `set_state(Gst.State.NULL)` calls inside the synchronous restart
    (L1498 in _try_next_stream and L1918 in _play_youtube) tear down the OLD pipeline
    while it still holds the OLD (ended/HLS) URI. Such teardown routinely emits
    message::error (source/demuxer/decoder errors on an already-dead live HLS source).
    Because these errors are posted AFTER L708 ran, they carry the NEW `_recovery_seq`
    = N. They are CURRENT-generation, not stale.

- timestamp: 2026-06-20T00:00:04Z
  source: musicstreamer/player.py:1019-1082 (_handle_gst_error_recovery) + 1039 (the 95-02 guard)
  finding: |
    The 95-02 guard is: `if recovery_seq != -1 and recovery_seq != self._recovery_seq: return`
    (L1039). For a current-generation error (stamp == N == self._recovery_seq) the guard
    PASSES (N != N is False). Then `_recovery_in_flight` is False (play() cleared it at
    L700, and `_clear_recovery_guard` resets it after each advance), so the coalescing
    check (L1047) also passes. The handler falls through to `_try_next_stream()` (L1081).
    The new YT stream was already popped during the restart and resolution has NOT yet
    returned, so `_streams_queue` is EMPTY → `failover.emit(None)` (L1507) →
    `_on_failover(None)` → `show_toast("Stream exhausted")`. THE RESIDUAL TOAST.

- timestamp: 2026-06-20T00:00:05Z
  source: musicstreamer/player.py:2016-2036 (_on_youtube_resolved) + 2032 (resolve-seq guard)
  finding: |
    Moments later the NEW resolve worker finishes → `youtube_resolved.emit(url, is_live, seq)`
    → `_on_youtube_resolved`. The `_youtube_resolve_seq` guard (L2032) PASSES (seq captured
    at this restart's _play_youtube matches current) → `_set_uri(new_url)` (L2035) → the
    new stream plays. This exactly matches "I get the first Stream Exhausted then it moves
    onto the working stream." Ordering on the main-loop event queue:
      T0  modal showing (old resolution already failed; user editing)
      T1  user saves → _sync_now_playing_station → invalidate_for_edit → play(new) runs
          SYNCHRONOUSLY: bumps _recovery_seq to N, empties queue, set_state(NULL)×2 on the
          OLD URI, spawns new resolve worker, returns.
      T2  OLD-URI teardown errors (posted DURING T1, stamp == N) drain on the main loop →
          _handle_gst_error_recovery → guard PASSES (current gen) → _try_next_stream() →
          empty queue → failover.emit(None) → "Stream exhausted" TOAST.
      T3  (seconds later) new resolve completes → _on_youtube_resolved → _set_uri(new) → plays.

- timestamp: 2026-06-20T00:00:06Z
  source: tests/test_player_edit_invalidation.py:326-360 (V11) — WHY THE UNIT TEST MISSES THIS
  finding: |
    V11 models a STALE recovery: it captures `stale_recovery_seq = p._recovery_seq` BEFORE
    the bump (L346), THEN does `p._recovery_seq += 1` (L351), THEN delivers
    `_handle_gst_error_recovery(stale_recovery_seq)` with the OLD stamp. So V11 only proves
    the guard rejects a PRE-restart stamp. It never models an error POSTED AFTER the bump
    (current stamp == post-restart _recovery_seq) during the async-resolve empty-queue window.
    V12 even ASSERTS the opposite of what the live bug needs: it confirms a CURRENT-seq
    recovery on an empty queue STILL emits failover(None) (L390-397) — i.e. V12 codifies the
    very pass-through that produces the toast. The guard's whole design ("suppress only stale
    pre-restart deliveries; let current-generation exhaustions toast") cannot distinguish a
    real all-streams-failed exhaustion from a transient empty queue during an in-flight YT
    resolve, because both carry the current `_recovery_seq`.

- timestamp: 2026-06-20T00:00:07Z
  source: musicstreamer/player.py:1765-1789 (_on_gst_eos_during_preroll) — ELIMINATION
  finding: |
    EOS is NOT the toast source. The only message::eos handler early-returns when
    `_preroll_in_flight` is False (L1785). The toast comes from message::error on the
    OLD-URI teardown (current-generation recovery), not EOS — consistent with the prior
    diagnosis (.planning/debug/95-spurious-stream-exhausted-toast.md).

- timestamp: 2026-06-20T00:00:08Z
  source: musicstreamer/player.py:2038-2042 (_on_youtube_resolution_failed) — SECONDARY UNGUARDED PATH
  finding: |
    Independently of the recovery path, `_on_youtube_resolution_failed` itself calls
    `_try_next_stream()` (L2042) with NO _recovery_seq AND NO _youtube_resolve_seq guard. If
    the NEW URL's resolution ALSO fails (or a late OLD-URL resolution-failed delivery lands
    after the restart), this path emits failover(None) on an empty queue too. The live repro
    is most simply explained by the message::error→recovery path (current-gen), but this
    unguarded resolution-failed→_try_next_stream path is a second route to the same toast and
    must be considered by the fix.

## Eliminated

- "The residual toast is a STALE (pre-restart) recovery the 95-02 guard should have caught but didn't (a guard bug)."
  evidence: The 95-02 guard at player.py:1039 is correct and V11 proves it rejects pre-restart
  stamps. The live toast comes from an error POSTED AFTER play() bumped _recovery_seq (during the
  synchronous old-URI set_state(NULL) teardown at L1498/L1918), so it carries the CURRENT stamp
  and is DESIGNED to pass the guard (V12 codifies exactly this pass-through). It is therefore NOT
  a stale recovery — the guard is working as specified; the specification doesn't cover this case.
  timestamp: 2026-06-20T00:00:09Z

- "The toast is the same earlier flash the 95-02 guard targeted."
  evidence: The earlier flash (prior diagnosis) was a recovery POSTED before the edit. 95-02 closed
  that. The current repro reaches the edit THROUGH the 'stream has ended' modal, meaning the old
  resolution had ALREADY failed (queue already drained) before the edit; the toast now arises from
  the NEW restart's own synchronous old-URI teardown emitting a CURRENT-generation error.
  timestamp: 2026-06-20T00:00:10Z

- "EOS on the old HLS stream emits failover(None)."
  evidence: player.py:1785 — the sole message::eos handler returns immediately unless a preroll is
  in flight. No EOS→failover bridge on the streaming path.
  timestamp: 2026-06-20T00:00:11Z

## Resolution

root_cause: |
  The residual "Stream exhausted" toast is a CURRENT-generation false exhaustion, NOT a stale
  (pre-restart) recovery — so the Phase 95-02 `_recovery_seq` generation guard fundamentally
  cannot suppress it.

  Sequence (already-ended-before-edit path):
  1. The old YouTube live stream had already ended; yt-dlp returned "live stream recording is not
     available" → the "stream has ended" modal (main_window.py:935 → :952). The old single YT
     stream was already popped and the queue is empty.
  2. User clicks Update URL…, edits, saves → `_sync_now_playing_station` (main_window.py:1451) →
     `invalidate_for_edit(new_station, is_playing=True)` → D-01 `self.play(station)` (player.py:2102).
  3. `play()` runs SYNCHRONOUSLY: empties `_streams_queue` (L699), clears `_recovery_in_flight`
     (L700), BUMPS `_recovery_seq` to a new generation N (L708), rebuilds the queue with the new
     YT stream, then `_try_next_stream()` (L849) pops it (queue empty again) and calls
     `_play_youtube(new_url)`, which spawns an ASYNC daemon resolve worker (yt-dlp + Node EJS,
     seconds long) and returns. The two `set_state(Gst.State.NULL)` teardowns of the still-loaded
     OLD/ended URI (player.py:1498 and :1918) run during this synchronous window.
  4. Those teardowns emit `message::error` on the bus thread. `_on_gst_error` (player.py:1004)
     reads `self._recovery_seq` AT POST TIME — which is now N — and emits
     `_error_recovery_requested.emit(N)` (L1017), QueuedConnection to the main loop.
  5. On a later main-loop turn `_handle_gst_error_recovery(N)` runs. The 95-02 guard
     `recovery_seq != self._recovery_seq` is `N != N` = False → PASSES (correctly, by design,
     because N is the current generation). `_recovery_in_flight` is False → coalescing passes too.
     It falls through to `_try_next_stream()` (L1081) on the STILL-EMPTY queue (the new URL has not
     finished resolving) → `failover.emit(None)` (L1507) → `_on_failover(None)` →
     `show_toast("Stream exhausted")` (main_window.py:914). THE RESIDUAL TOAST.
  6. Seconds later the new resolve worker finishes → `_on_youtube_resolved` → `_set_uri(new_url)`
     (L2035) → the working stream plays. Hence "first Stream Exhausted then it moves onto the
     working stream."

  The generation guard distinguishes pre-restart vs post-restart deliveries; it CANNOT distinguish
  a genuine all-streams-failed exhaustion from a TRANSIENTLY-EMPTY queue while a current-generation
  YouTube resolution is still in flight — both carry the current `_recovery_seq`. There is NO flag
  recording that a YouTube resolution for the current generation is pending, and neither
  `_try_next_stream()` (failover.emit(None) at L1507) nor `_on_youtube_resolution_failed`
  (unguarded `_try_next_stream()` at L2042) consults such a flag before declaring exhaustion.

reasoning_checkpoint:
  hypothesis: "The toast is a CURRENT-generation transient-empty-queue exhaustion: an old-URI
    teardown message::error POSTED after play() bumped _recovery_seq carries the current stamp,
    passes the 95-02 guard, and hits _try_next_stream() on the empty queue while the new YouTube
    URL is still resolving asynchronously."
  confirming_evidence:
    - "failover.emit(None) has a single source (player.py:1507) reachable only with an empty queue."
    - "play() empties the queue and pops the new YT stream synchronously, leaving the queue empty for the seconds-long async resolve window (player.py:699, 849, 1509, 1918-1929)."
    - "_on_gst_error reads _recovery_seq at POST time (player.py:1017); errors from the synchronous old-URI set_state(NULL) teardown (L1498/L1918) are posted AFTER the L708 bump → carry the current stamp."
    - "The 95-02 guard (L1039) passes current-generation stamps by design; V12 (test_player_edit_invalidation.py:390-397) explicitly asserts a current-seq recovery on an empty queue STILL emits failover(None)."
    - "_on_youtube_resolved's resolve-seq guard passes for the new URL and plays it afterward (player.py:2032-2035), matching 'then it moves onto the working stream.'"
  falsification_test: "If, at the moment the spurious recovery runs, _streams_queue were NON-empty
    OR no YouTube resolution were in flight for the current generation, the hypothesis would be
    wrong. Runtime confirmation: log every failover.emit(None) with a stack + the in-flight resolve
    state + the recovery stamp vs current _recovery_seq; the spurious one will show stamp ==
    current _recovery_seq (NOT stale), an empty queue, AND a live resolve worker, with the new URL
    playing immediately after."
  fix_rationale: "Because the stamp is current, a generation guard cannot help. The correct fix is a
    'resolve-in-flight' gate: do NOT declare exhaustion (failover.emit(None) / show toast) while a
    YouTube resolution for the CURRENT generation is still pending. This addresses the root cause
    (premature exhaustion verdict during an unfinished async resolve) rather than suppressing the
    toast globally, so a genuine all-streams-failed case still toasts once."
  blind_spots: "Not verified at runtime that the OLD-URI set_state(NULL) teardown reliably emits a
    message::error for an already-ended HLS source (vs sometimes emitting nothing). If in some
    cases NO bus error is posted post-restart, the toast would instead come from the secondary
    unguarded path (_on_youtube_resolution_failed → _try_next_stream at L2042) if a late OLD-URL
    resolution-failed delivery lands after the restart; the fix should cover BOTH the recovery path
    and the resolution-failed path. Also not measured: exact count of teardown errors (one suffices)."

fix: |
  (DIAGNOSE-ONLY — not applied.) The toast is a CURRENT-generation exhaustion during an in-flight
  async YouTube resolve. A generation guard cannot fix it. Add a "YouTube resolve in flight"
  gate so exhaustion is never declared while the current generation's resolution is pending.

  RECOMMENDED — resolve-in-flight gate on the exhausted-toast path:
  1. Add a flag (e.g. `_youtube_resolve_in_flight: bool`, or store the in-flight resolve seq) set
     TRUE in `_play_youtube` at spawn time (player.py:~1927) and cleared in BOTH `_on_youtube_resolved`
     (L2034-2035, success) and `_on_youtube_resolution_failed` (L2038-2042, failure) — i.e. cleared
     only when the current generation's resolution actually completes (match on _youtube_resolve_seq
     so a stale completion does not clear a fresh in-flight flag).
  2. In `_try_next_stream`, before `failover.emit(None)` on the empty-queue branch (player.py:1505-
     1508): if a current-generation YouTube resolve is in flight, DO NOT emit failover(None) — the
     pending resolution will either play (`_set_uri`) or fail (`_on_youtube_resolution_failed`,
     which then legitimately advances/exhausts). This suppresses the transient false exhaustion
     without touching genuine exhaustion (no resolve pending → toast still fires).
  3. Equivalently/additionally, have `_handle_gst_error_recovery` early-return (no advance) when a
     current-generation YouTube resolve is in flight, since a recovery is pointless while the new
     URI is still being resolved.

  Hard constraint (mirror V12 intent): when NO resolve is in flight and the queue is genuinely
  empty (all streams truly failed), failover.emit(None) MUST still fire exactly once. The
  resolution-failed path (`_on_youtube_resolution_failed` → `_try_next_stream`, L2042) is the
  legitimate route to that toast and must remain reachable once the in-flight flag is cleared.

  Also audit the secondary unguarded path: `_on_youtube_resolution_failed` (L2042) calls
  `_try_next_stream()` with neither a `_recovery_seq` nor a `_youtube_resolve_seq` guard. Ensure a
  stale OLD-URL resolution-failed delivery arriving after the restart cannot itself emit a spurious
  failover(None) (it would carry no seq today). Consider stamping resolution-failed deliveries with
  the resolve seq and ignoring stale ones, the same way `youtube_resolved` is stamped.

verification: |
  (Not performed — diagnose-only.) Suggested regression coverage in
  tests/test_player_edit_invalidation.py:
    - V14 (the real bug): simulate post-restart state with `_youtube_resolve_in_flight = True`
      (current generation) + empty `_streams_queue`; deliver `_handle_gst_error_recovery(current_seq)`
      AND/OR call `_try_next_stream()`; assert failover(None) is NOT emitted (no "Stream exhausted").
    - V15 (hard constraint preserved): no resolve in flight + empty queue + current-seq recovery →
      failover(None) STILL emitted exactly once (genuine exhaustion).
    - V16: the in-flight flag is cleared by BOTH _on_youtube_resolved (success) and
      _on_youtube_resolution_failed (failure) for the matching generation, and a stale completion
      does NOT clear a fresh flag.
  End-to-end (HUMAN-UAT): (a) play a YT live station that has ended → modal → Update URL → save →
  new stream plays with NO "Stream exhausted" toast; (b) a station whose every stream genuinely
  fails → toast still fires exactly once.

files_changed: []
