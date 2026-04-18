---
status: resolved
trigger: "Phase 47 UAT gap 5 — failover reports 'stream exhausted' before trying all streams"
slug: stream-exhausted-premature
created: 2026-04-18T18:45:00Z
updated: 2026-04-18T22:00:00Z
phase_ref: 47
uat_ref: .planning/phases/47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame/47-UAT.md
resolved_by: 47-05
---

## Symptoms

DATA_START
- **Expected behavior:** When a station has multiple streams, the failover queue (ordered by `order_streams`: codec_rank desc, bitrate_kbps desc, position asc with unknowns last) should attempt each stream in order and succeed on the first one that works. "Stream exhausted" should only be reported after EVERY candidate has been attempted and failed.
- **Actual behavior:** On an AudioAddict station where the higher-quality streams are broken but the low-quality stream is functional, the app reports "stream exhausted" and does not play. The user confirmed the low-quality stream works fine when selected directly (i.e., it plays as the primary when nothing precedes it).
- **Error messages:** "stream exhausted" (exact phrasing as observed in-app).
- **Timeline:** Surfaced immediately after Phase 47 shipped (commit range `598214c..d636c6f`, 2026-04-17 → 2026-04-18). Phase 47 replaced the prior position-only failover ordering with `order_streams(...)` in `player.py:166` (single-line swap per 47-02 SUMMARY).
- **Reproduction:** (a) Take an AA station with hi/med/low streams. (b) Break the URLs on hi and med so they cannot connect (e.g., point to `http://broken.local/`). Leave low working. (c) Click play. Observe: app reports "stream exhausted" rather than falling through to low.
- **Related gap:** UAT gap 4 — no visible indication of failover events (may share root cause in the player state machine / emit path).
DATA_END

## Current Focus

hypothesis: ORIGINAL (preferred_quality filter) was FALSIFIED on reading `player.py:166-181`. REVISED: Multiple GStreamer bus-error messages per broken URL each schedule an independent `QTimer.singleShot(0, self._handle_gst_error_recovery)` at `player.py:253`. With no in-flight dedupe, each queued callback pops a fresh stream from `_streams_queue` and re-arms playback — so a single broken URL that emits N errors during connect/teardown drains N queue entries. For a 3-stream station where the first URL fails with 2+ cascading errors, streams 2 and 3 get "consumed" without real playback attempts, and the queue empties → `failover.emit(None)` → toast "Stream exhausted".
test: VERIFIED via code trace, not yet verified at runtime. Next verification: write a regression test that calls `_on_gst_error` N times in quick succession on a 3-stream queue and asserts that only 1 pop occurs (i.e., recovery is idempotent per failed URL). See `tdd_checkpoint`.
expecting: (a) `_on_gst_error` at `player.py:248-253` has no dedupe — any N bus error messages schedule N recoveries. (b) `_handle_gst_error_recovery` at `player.py:255-262` unconditionally calls `_try_next_stream()` — does not check whether the current stream was the one that errored, or whether another recovery has already advanced the queue. (c) `_try_next_stream` at `player.py:297-330` pops from `_streams_queue` without a guard against "recovery already in flight for current URL". All confirmed by reading player.py head-to-tail.
next_action: Apply fix below. Write regression test `test_multiple_gst_errors_advance_queue_once`.
reasoning_checkpoint: done
tdd_checkpoint: pending — regression test is part of fix plan.

## Evidence

- timestamp: 2026-04-18T19:00:00Z
  source: musicstreamer/player.py:166-181 (read)
  finding: |
    `preferred_quality` short-circuit does NOT filter the queue. Lines 166-178:
      streams_by_position = order_streams(station.streams)
      preferred = next((s for s in streams_by_position if s.quality == preferred_quality), None) if preferred_quality else None
      if preferred: queue = [preferred] + [s for s in streams_by_position if s is not preferred]
      else:         queue = list(streams_by_position)
    The `else` branch is what runs in practice because `main_window.py:270` calls `self._player.play(station)` with no `preferred_quality` argument. So the queue always contains ALL streams.
  falsifies: "preferred_quality filters the failover queue" (the original hypothesis in the debug file).

- timestamp: 2026-04-18T19:01:00Z
  source: musicstreamer/ui_qt/main_window.py:270, 278-286 (read)
  finding: |
    `_on_station_activated` calls `self._player.play(station)` with no `preferred_quality`. `_on_failover(None)` displays "Stream exhausted"; `_on_failover(<stream>)` displays "Stream failed, trying next…". So UAT gap 4 ("failover is invisible") is PARTIALLY wrong — the toast DOES fire per failover event. However, the toast duration is 3s default and may be dismissed before the user notices during rapid cascading errors (this bug's root cause). Fixing this bug should eliminate the "invisible" symptom as a side effect because failover will actually take its full BUFFER_DURATION_S window per stream instead of draining instantly.

- timestamp: 2026-04-18T19:02:00Z
  source: musicstreamer/player.py:248-262 (read)
  finding: |
    `_on_gst_error` at L248-253 unconditionally calls `QTimer.singleShot(0, self._handle_gst_error_recovery)`. No guard, no dedupe, no check for pending recovery. `_handle_gst_error_recovery` at L255-262 unconditionally calls `_try_next_stream()`. Therefore: N bus errors for a single failing URL schedule N recoveries; each pops a separate queue entry.
    Thread note: `_on_gst_error` runs on the bus-loop daemon thread (per class docstring). Any guard state touched here must be either atomic or marshalled to the main thread.
  corroborates: revised hypothesis.

- timestamp: 2026-04-18T19:02:30Z
  source: musicstreamer/player.py:297-330 (read)
  finding: |
    `_try_next_stream` pops `_streams_queue[0]`, calls `_set_uri`, and arms `_failover_timer` for `BUFFER_DURATION_S * 1000` ms — but the NEXT error from the NEW URL (or a still-queued error from the OLD one) immediately pops again. There is no "in-flight URL attempt" state that would let a later recovery be coalesced into "I've already advanced past the URL that errored."

- timestamp: 2026-04-18T19:03:00Z
  source: musicstreamer/gst_bus_bridge.py (read full)
  finding: |
    The bus bridge dispatches every `message::error` on the GLib main loop; nothing there dedupes errors. It's purely a plumbing layer.

- timestamp: 2026-04-18T19:03:30Z
  source: tests/test_player_failover.py (read full)
  finding: |
    Coverage gap: `test_gst_error_triggers_failover` calls `_handle_gst_error_recovery()` exactly ONCE. No test covers the "N errors → advance only once" contract. So the Wave-2 test suite cannot catch this regression. Wave-2 tests use a mocked pipeline, so they never observe multi-error cascades that happen on a real GStreamer playbin3.

- timestamp: 2026-04-18T19:04:00Z
  source: git show fb1e3ca (Phase 47-02 diff)
  finding: |
    Phase 47-02 was a pure minimal-diff replacement of `sorted(streams, key=position)` with `order_streams(streams)` at player.py:166. Zero behavior change to the failover iteration, error handling, or `_try_next_stream`. So this bug is NOT introduced by Phase 47 — it's a latent pre-47 bug in the error-recovery path that Phase 47 makes more reachable: the ordered queue (by codec/bitrate desc) is more likely to put a broken premium-tier URL first, which is the exact scenario that triggers cascading errors. Pre-47, position order happened to put the same stream first for AA (hi at position 1), so the scenario was technically reproducible pre-47 but the user may not have encountered it or may have attributed it to "broken station" rather than "failover bug."

- timestamp: 2026-04-18T19:04:30Z
  source: musicstreamer/aa_import.py:93-94, 169-175 (read)
  finding: |
    Side-finding (UAT gap 3): AA codec/bitrate map is wrong. Currently: hi→AAC/320, med→MP3/128, low→MP3/64. Ground truth (per UAT gap 3): hi→MP3/320, med→AAC/128, low→AAC/64. This is NOT the root cause of gap 5 — the queue still contains all streams regardless of codec labels — but it's relevant context: the ordering badges in the UI will be misleading until this is corrected. Separate fix.

## Eliminated

- "preferred_quality filters the failover queue" — falsified by code read at player.py:166-181. The short-circuit only PINS a preferred stream to the front; it does not filter. In practice `main_window.py` calls `play()` without `preferred_quality`, so even the pin path is inert.
- "order_streams orders wrong, leaving low unreachable" — falsified. `order_streams` returns a complete list with all streams; unknown bitrates sort LAST, not dropped. Queue construction preserves all items.
- "Phase 47 broke the failover iteration" — falsified by reading the Phase 47-02 diff. Only queue CONSTRUCTION changed; iteration and error handling are pre-47 code.
- "Tag-arrival wrongly cancels failover for a still-broken stream" — considered and dismissed. `_on_gst_tag` at L264-274 only fires when `message::tag` is received, which requires the pipeline to have actually started streaming. A broken URL that never connects won't emit a tag.

## Resolution

root_cause: |
  `player.py:248-262` treats every GStreamer `message::error` as an independent "advance the failover queue" trigger, with no dedupe. When playbin3 emits multiple bus errors for a single failing URL (common on DNS failures, connection refusals, or HTTP errors where source + demuxer + decoder each report an error during pipeline teardown), each error schedules a fresh `QTimer.singleShot(0, _handle_gst_error_recovery)` which pops the next stream from `_streams_queue`. A single broken URL can therefore drain multiple queue entries, effectively skipping unattempted streams and producing a spurious "Stream exhausted" toast. Phase 47 did not introduce this bug — the failover-iteration and error-recovery code are unchanged since Phase 28 (commit b3dec88). Phase 47 made the scenario more reachable because the new codec/bitrate-descending order puts premium (often-broken) URLs ahead of the free low-quality URL more reliably than the old position order.

fix: |
  Add a per-attempt in-flight guard so only ONE recovery runs per failing URL. Because `_on_gst_error` runs on the bus-loop daemon thread while `_handle_gst_error_recovery` and `_try_next_stream` run on the Qt main thread, the guard must be written/read consistently across threads. Preferred implementation: marshal the guard check to the main thread by moving ALL guard logic into `_handle_gst_error_recovery` (main-thread only) and leaving `_on_gst_error` to schedule unconditionally. The guard then only needs main-thread atomicity, not cross-thread synchronization.

  Concrete change in `musicstreamer/player.py`:

    # in __init__ (main thread):
    self._recovery_in_flight: bool = False

    # _on_gst_error stays dumb — just schedules (bus-loop thread, no guard):
    def _on_gst_error(self, bus, msg) -> None:
        err, debug = msg.parse_error()
        self.playback_error.emit(f"{err} | {debug}")
        # Schedule recovery on the main thread. Coalescing happens THERE.
        QTimer.singleShot(0, self._handle_gst_error_recovery)

    # _handle_gst_error_recovery coalesces on the main thread:
    def _handle_gst_error_recovery(self) -> None:
        # If a recovery is already in flight for the URL that just failed, drop
        # this duplicate. Cleared at the end so the NEXT failing URL can trigger.
        if self._recovery_in_flight:
            return
        self._recovery_in_flight = True
        try:
            self._cancel_timers()
            if self._current_stream and "twitch.tv" in self._current_stream.url:
                if self._twitch_resolve_attempts < 1:
                    self._twitch_resolve_attempts += 1
                    self._play_twitch(self._current_stream.url)
                    return
            self._try_next_stream()
        finally:
            # Clear AFTER the next attempt is armed, so any still-queued errors
            # from the PREVIOUS URL that are dispatched before we return here
            # will see _recovery_in_flight == True and no-op. Errors from the
            # NEW URL (which won't start emitting until after set_state(PLAYING))
            # will see False and trigger a fresh recovery.
            self._recovery_in_flight = False

  Also clear `_recovery_in_flight = False` in `play()`, `play_stream()`, `stop()`, and `pause()` (alongside the existing `_streams_queue = []` reset) so a new user action cannot inherit a stale guard from a previous session.

  Note: `_on_timeout` (watchdog) does NOT need the guard because QTimer is single-shot and main-thread-owned; it can only fire once per arming. But if we want symmetry, wrap `_on_timeout` to also respect the guard.

  Why this placement is safe:
  - `_recovery_in_flight` is only touched on the main thread (inside `_handle_gst_error_recovery` + the `play/play_stream/stop/pause` reset sites, all main-thread). No cross-thread write.
  - The window where the guard is True spans from "start of recovery" through "new attempt armed." Any late bus errors from the OLD URL delivered during that window either (a) run their singleShot recovery after we return and see the guard CLEARED — BUT by then the queue has advanced; or (b) run before we return and are queued behind us on the main thread's event queue.
  - Case (a) IS the residual race. To close it, defer the clear by ONE event-loop turn: `QTimer.singleShot(0, lambda: setattr(self, '_recovery_in_flight', False))`. This ensures any already-queued recovery callbacks drain FIRST (and see True), and only then the guard clears for future URL failures. RECOMMENDED.

  Updated recovery body with deferred clear:

    def _handle_gst_error_recovery(self) -> None:
        if self._recovery_in_flight:
            return
        self._recovery_in_flight = True
        self._cancel_timers()
        if self._current_stream and "twitch.tv" in self._current_stream.url:
            if self._twitch_resolve_attempts < 1:
                self._twitch_resolve_attempts += 1
                self._play_twitch(self._current_stream.url)
                QTimer.singleShot(0, self._clear_recovery_guard)
                return
        self._try_next_stream()
        QTimer.singleShot(0, self._clear_recovery_guard)

    def _clear_recovery_guard(self) -> None:
        self._recovery_in_flight = False

  Regression test (`tests/test_player_failover.py`):

    def test_multiple_gst_errors_advance_queue_once(qtbot):
        """Multiple bus errors for a single failing URL must advance the failover
        queue exactly once (regression for gsd-debug:stream-exhausted-premature)."""
        p = make_player(qtbot)
        streams = [make_stream(i, i, f"q{i}") for i in (1, 2, 3)]
        station = make_station_with_streams(streams)
        with patch.object(p, "_set_uri"):
            p.play(station)
        # Currently on stream 1; queue has [2, 3].
        assert p._current_stream.id == 1
        assert [s.id for s in p._streams_queue] == [2, 3]
        # Simulate playbin3 emitting three errors for the same failing URL.
        # Invoke _handle_gst_error_recovery directly to avoid the 0-ms
        # singleShot event-loop race in a non-running test loop.
        mock_msg = MagicMock()
        mock_msg.parse_error.return_value = (Exception("e"), "d")
        with patch.object(p, "_set_uri"):
            p._handle_gst_error_recovery()
            p._handle_gst_error_recovery()
            p._handle_gst_error_recovery()
        # After three recovery calls, the queue should have advanced ONE step.
        # The subsequent two calls hit the _recovery_in_flight guard and no-op.
        # (Note: the guard-clear singleShot hasn't fired yet — qtbot.wait(50)
        # would clear it; intentionally we don't wait so we test the coalescing.)
        assert p._current_stream.id == 2
        assert [s.id for s in p._streams_queue] == [3]

    def test_recovery_guard_resets_between_distinct_url_failures(qtbot):
        """After the guard-clear singleShot fires, a subsequent error on the
        NEW URL advances the queue again (the guard doesn't stick)."""
        p = make_player(qtbot)
        streams = [make_stream(i, i, f"q{i}") for i in (1, 2, 3)]
        station = make_station_with_streams(streams)
        with patch.object(p, "_set_uri"):
            p.play(station)
        mock_msg = MagicMock()
        mock_msg.parse_error.return_value = (Exception("e"), "d")
        with patch.object(p, "_set_uri"):
            p._handle_gst_error_recovery()   # advance to stream 2
            qtbot.wait(20)                   # let guard-clear singleShot fire
            p._handle_gst_error_recovery()   # advance to stream 3
            qtbot.wait(20)
        assert p._current_stream.id == 3

verification: |
  1. Both regression tests above pass (red before fix, green after).
  2. Manual smoke: set two of three AA streams to `http://broken.local/`, leave low-quality working, click play. Observe (a) "Stream failed, trying next…" toast appears exactly ONCE per failing URL (not for each cascading error), (b) playback lands on the working stream, (c) no "Stream exhausted" toast.
  3. Existing `test_player_failover.py` suite still passes — the guard is a superset of current behavior when exactly one error fires per URL.

files_changed:
  - musicstreamer/player.py (add _recovery_in_flight guard + _clear_recovery_guard; reset in play/play_stream/stop/pause)
  - tests/test_player_failover.py (add test_multiple_gst_errors_advance_queue_once + test_recovery_guard_resets_between_distinct_url_failures)

## Specialist Review

[pending — python-expert-best-practices-code-review. Key questions for the reviewer:
 1. Is the "guard cleared via singleShot(0)" pattern idiomatic for coalescing async Qt callbacks in PySide6, or is there a cleaner Qt primitive (e.g., a QEventLoopLocker, or setting a flag via QMetaObject.invokeMethod with Qt.QueuedConnection) I should use instead?
 2. Should `_recovery_in_flight` be stored as a simple attribute or a property guarded by the Qt thread-affinity check?
 3. Is there a risk of the guard-clear singleShot being lost if the Player object is destroyed between "schedule" and "dispatch"? (Should be fine because the QTimer is parented to self, but worth confirmation.)
 4. The proposed test calls `_handle_gst_error_recovery` synchronously rather than going through `_on_gst_error` → singleShot. That's consistent with existing tests (test_gst_error_triggers_failover does the same), but it means the test does NOT exercise the cross-thread scheduling path. Is an integration-style test (qtbot.waitSignal on a synthetic bus event) worth adding, or is it enough to trust the existing bus-bridge coverage?]
