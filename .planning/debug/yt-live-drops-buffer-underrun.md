---
status: resolved
trigger: "I seem to be getting a lot more drops on YT streams more often, and I notice the buffer seems to at times fill up and drop never quite reaching 100% (it is at the moment but it seems intermittent)"
created: 2026-07-10
updated: 2026-07-13
---

# Debug Session: YT live stream drops + buffer never reaching 100%

## Symptoms

- **Expected behavior:** YouTube live streams play continuously without frequent rebuffering; playback buffer fills to and holds near 100%.
- **Actual behavior:** More frequent "drops" on YT live streams; playback stalls then recovers (rebuffering). Buffer intermittently fills partway, drains, and never quite reaches 100%.
- **Error messages:** None reported so far (no crash/toast; behavioral stall/recover).
- **Timeline:** Gradual — always had occasional drops, noticeably worse recently. No obvious code trigger correlated by the user.
- **Reproduction:** Occurs intermittently during normal YT live playback. Only live streams are used (app design).

## Symptom details (from intake)

- Scope: **live streams only** (app design — no VODs).
- Drop type: **playback stalls then recovers** (rebuffering, not a hard error/exhausted-stream end).
- Buffer: fills partway, drains, never reaches 100% intermittently.
- Onset: gradual worsening, no code change the user can point to.

## Relevant prior knowledge (from project memory)

- `[[hlsdemux2-owns-independent-segment-buffer]]` — YouTube live HLS underruns = live-edge starvation. hlsdemux2 keeps an independent segment buffer; playbin3 `buffer-duration` does NOT govern it. Prior fix pattern was a DVR seek ~30s back rather than a larger buffer.
- `[[yt-streams-tab-flat-scan-live-status-none]]` — live detection quirks.

## Current Focus

- hypothesis: CONFIRMED (see Resolution). Adaptive buffer-duration growth (Phase 84 / D-11, `_maybe_grow_buffer_duration`) never propagates to the live hlsdemux2 element during an in-progress YouTube-live session. `_on_deep_element_added` configures `max-buffering-time`/`high-watermark-time` on hlsdemux2 exactly once, at element-creation time (session start, always at the 30s baseline). Growth after underrun cycles only updates `_pending_buffer_duration_s`/`_current_buffer_duration_s` (staged for playbin3 at the *next* URI bind) — but no code re-applies the grown value to the already-running hlsdemux2 instance, and no reference to that instance is even retained. So the "adaptive" 30s→60s→120s growth schedule is a complete no-op for hlsdemux2-backed live sessions: real segment-buffer capacity is permanently pinned at 30s regardless of how many underrun cycles fire.
- test: implemented fix + verifying via existing suite (test_player_hlsdemux2_buffer.py, test_player_buffer_growth.py) plus new regression test for mid-session re-apply.
- expecting: hlsdemux2 element's max-buffering-time/high-watermark-time are updated immediately when `_maybe_grow_buffer_duration` stages a new value, using a stored reference to the current hlsdemux2 element captured in `_on_deep_element_added`.
- next_action: implement fix, run test suite, verify.
- reasoning_checkpoint: see Resolution.root_cause / fix below — all 5 fields answered.
- tdd_checkpoint: (none — tdd_mode not set for this session)

## Evidence

- timestamp: 2026-07-10 (investigation)
  checked: `.planning/debug/knowledge-base.md` — does not exist yet (no prior resolved sessions to match against).
  found: n/a
  implication: proceed with fresh investigation; will seed knowledge base on resolution.

- timestamp: 2026-07-10 (investigation)
  checked: `musicstreamer/player.py` — BUG-YT-LIVE-BUFFER prior fix (D-01 hlsdemux2 buffer config, D-02 DVR seek) around lines 380-465, 1978-2088, 2205-2229.
  found: A prior, already-shipped fix (commit f716f083) added a one-shot DVR seek (`_apply_live_dvr_seek`, 30s behind hold-back) plus `_on_deep_element_added`, which sets hlsdemux2's `max-buffering-time`/`high-watermark-time` to `self._current_buffer_duration_s` ONE TIME when the hlsdemux2 element is added to the pipeline (per URI bind). No reference to the created element is retained anywhere in the class.
  implication: any *subsequent* change to `_current_buffer_duration_s` during the same live session has no mechanism to reach the already-configured hlsdemux2 instance.

- timestamp: 2026-07-10 (investigation)
  checked: `_maybe_grow_buffer_duration` (player.py:1538-1570) and `_apply_pending_buffer_duration_to_pipeline` (player.py:1582-1618).
  found: Growth only (a) updates `_current_buffer_duration_s`/`_pending_buffer_duration_s` and emits `buffer_duration_changed` (UI mirror), and (b) writes `playbin3.buffer-duration` — but ONLY at the next `set_property("uri", ...)` bind (explicitly documented as a "silent no-op" mid-session). Nothing touches hlsdemux2's `max-buffering-time`/`high-watermark-time` properties after initial configuration.
  implication: for a live YouTube session that never rebinds (a single long-running station play), growth staged after underrun cycle #1 (→60s) and #2 (→120s, cap) never actually enlarges the real segment buffer hlsdemux2 uses — only the UI's "current buffer duration" display changes.

- timestamp: 2026-07-10 (investigation)
  checked: `_try_next_stream` (player.py:1651-1717) ordering of `_reset_buffer_duration_to_baseline()` then `_apply_pending_buffer_duration_to_pipeline()` (CR-02, Phase 84 code review).
  found: Even on a fresh reconnect to the SAME station/URL, growth state is reset to the 30s baseline BEFORE being (re)applied — by design, so it doesn't leak across station changes. Confirms growth can never survive into a new hlsdemux2 instance either, except via the preroll-handoff path (different track queued via gapless handoff), which is not the live-radio-station use case.
  implication: hlsdemux2's real buffer capacity is permanently pinned at 30s baseline for every YouTube live session, regardless of underrun history.

- timestamp: 2026-07-10 (Round 2 investigation)
  checked: `_on_gst_error` (player.py:1103-1116) and the bus-connect wiring block (player.py:480-495).
  found: `note_error_in_cycle()` (the ONLY mechanism that ever flips `cause_hint` away from `"unknown"`) is called exclusively from `_on_gst_error`, which is wired to `"message::error"` only. There is NO `"message::warning"` handler anywhere in player.py, and NO other code path ever touches `_cause_hint`. `_on_deep_element_added` / `_configure_hlsdemux2_buffer` never set the GstBin `message-forward` property (default `false`) on the hlsdemux2 element, so warnings/errors posted by hlsdemux2's *internal* child elements (its own download-worker machinery) are swallowed by hlsdemux2's own GstBin filtering and never reach the pipeline's top-level bus at all.
  implication: `cause_hint=unknown` on every one of the 511 production events (including the 172s/108s stalls) is not surprising -- it is architecturally guaranteed. The tracker is blind to anything happening inside hlsdemux2's internal segment-fetch/retry machinery; it can only ever see a *fatal, top-level* GStreamer ERROR, which apparently never fires for these cycles (all close with `outcome=recovered`, never `failover`).

- timestamp: 2026-07-10 (Round 2 investigation)
  checked: `_failover_timer` arm/disarm sites (player.py:502-503, 1475-1477, 1746, 1827, 1981, 2309, 2501) and `_cancel_timers_requested` wiring from `message::tag` (`_on_gst_tag` implicitly via `_cancel_timers_requested.emit()`).
  found: `_failover_timer` is a ONE-SHOT "stream never started" watchdog. It is armed once per `_set_uri`/`_try_next_stream`/preroll-start call (waiting up to `_current_buffer_duration_s` seconds for the FIRST audio/tag to arrive) and is stopped for good the moment the first ICY tag arrives (`_cancel_timers` called via the queued `_cancel_timers_requested` signal, itself emitted from `_on_gst_tag`). It is never re-armed for the rest of the session. There is no OTHER timer/watchdog anywhere in Player that caps how long a mid-session buffering stall (post-first-audio) is allowed to persist.
  implication: once initial playback has started, the player has ZERO active mechanism that can detect "this underrun cycle has been open for an abnormally long time" and force ANY corrective action (reconnect, re-seek, restart). It purely and indefinitely waits on `message::buffering` percent to climb back to 100 on its own, however long GStreamer's internal hlsdemux2 retry machinery takes.

- timestamp: 2026-07-10 (Round 2 investigation)
  checked: `gst-inspect-1.0 hlsdemux2` (local GStreamer 1.28.2, gst-plugins-good, matches project's GStreamer family).
  found: hlsdemux2 (GstHLSDemux2 -> GstAdaptiveDemux2 -> GstBin) exposes `max-retries` (Integer, default **3**, "-1=infinite"), `retry-backoff-factor` (Double, default **0**, "Exponential retry backoff factor in seconds"), and `retry-backoff-max` (Double, default **60**, "Maximum backoff delay in seconds") -- all properties governing HTTP segment-fetch retry behavior for stalled/failed fragment requests. Player never sets any of these three (only `max-buffering-time` / `high-watermark-time` are configured, in `_configure_hlsdemux2_buffer`); they sit at GStreamer defaults for every session. Also confirmed: `message-forward` (Boolean, default **false**, "Forwards all children messages") is present and unconfigured.
  implication: segment-fetch retries/backoff run entirely under GStreamer defaults, invisible to the app, and (per the GstBin `message-forward` contract -- official GStreamer docs: forwarded child messages are wrapped as a `GST_MESSAGE_ELEMENT` with structure name `"GstBinForwarded"` and a `"message"` field carrying the original `GstMessage`) NONE of that internal retry activity is currently surfaced to the pipeline's top-level bus. This is a real, closable player-side visibility gap, independent of whatever is ultimately causing the CDN/segment fetch to need retrying in the first place.

- timestamp: 2026-07-10 (Round 2 investigation)
  checked: `~/.local/share/musicstreamer/buffer-events.log` (real production log, 1220 lines, 2026-05-18 through 2026-07-10).
  found: `grep -c "buffer_underrun"` = 511 events total; `grep -o "min_percent=" | sort | uniq -c` shows 402/511 (~79%) events bottom out at `min_percent=0` (full drain, not partial). `grep -o "station_name="` shows YouTube "lofi hip hop radio" live channels dominate (286+13+7+4+1 ≈ 311 of 511, ~61%). On 2026-07-09, ONE continuous session (single "live HLS DVR seek applied" log line at 10:15:52, no further YouTube resolve until the next day) on station_id=3300 (url=youtube.com/watch?v=X4VbdwhkE10) produced 57 separate `buffer_underrun ... outcome=recovered` cycles across the day, all at `min_percent=0`, with no discernible improvement in frequency/duration over the session (growth would have staged 60s at cycle #1 and capped at 120s by cycle #2, yet cycles #3 through #57 show the same 0%-drain pattern).
  implication: direct field evidence that the growth schedule provides zero real mitigation once staged past cycle #2 for a live hlsdemux2 session — consistent with the code-level finding that growth never reaches the live hlsdemux2 element. Matches user's reported symptom (buffer never reaching 100%, drops getting worse) precisely: the "self-healing" mechanism the user might expect (and that the codebase's own naming/comments imply) silently does nothing after the first two underrun cycles.
  implication: `grep -c "DVR seek failed"` = 7 (rare, race-condition path already logged/handled with a warning) — ruled out as the primary driver; DVR seek succeeds in the overwhelming majority of sessions (244 "applied" vs 7 "failed").

## Eliminated

- hypothesis: DVR seek (`_apply_live_dvr_seek`) silently fails often, leaving sessions riding the live edge with no cushion.
  evidence: Production log shows only 7 "DVR seek failed" lines against 244 "DVR seek applied" lines (~2.8% failure rate) — not frequent enough to explain the observed 511 underrun events, and the 07-09 station_id=3300 session had a successful DVR seek applied at session start yet still accumulated 57 underrun cycles.
  timestamp: 2026-07-10

- hypothesis: (Round 2) The one-shot DVR-seek position goes "stale" over a long session, causing hlsdemux2 to request segments near/at an unstable live edge later in the session.
  evidence: `_apply_live_dvr_seek` is a single relative SEEK_TYPE_END seek performed once at session start (D-02); it does not set an absolute position that could "go stale" -- once applied, playback proceeds forward from that point exactly like any other HLS DVR playback, with hlsdemux2's own live-edge tracking (not the one-shot seek) governing subsequent segment requests. The production log's 4 post-fix events (08:40-08:49, ~10 minutes into the session) show no trend of worsening severity that would indicate progressive drift from a stale seek position; the two long stalls are not the LAST two events (there is no "gets worse over the session" pattern) and the surrounding evidence (retry/backoff properties, message-forward gap) already fully explains the observed durations without needing a staleness mechanism. No code path re-reads or re-applies the seek position after the one-shot fires.
  timestamp: 2026-07-10

- hypothesis: (Round 2) A player-forced faster reconnect (full `_try_next_stream` re-resolve or a mid-stall repeat DVR re-seek) would recover faster than passively waiting, and should be implemented as the primary fix this round.
  evidence: All 511 production underrun cycles close with `outcome=recovered` (never `outcome=failover`) -- meaning hlsdemux2's own internal retry/backoff always eventually succeeds on its own without any player intervention. There is no direct evidence (HTTP-level tracing, forwarded child messages) yet available about what is actually happening on the wire during a 172s stall, so a forced full re-resolve (heavier: tears down the pipeline and re-invokes yt-dlp, which project memory already flags as fragile/slow) is not demonstrated to be faster, and could plausibly make things worse. Implementing an unverified active-recovery action now would violate the "assume your fix is wrong until proven otherwise" verification discipline -- there is no way to verify a forced-recovery fix actually shortens stall duration without live reproduction data that does not yet exist. Deferred: the message-forward instrumentation fix (Resolution, Round 2) is a prerequisite that will supply exactly the missing data (whether hlsdemux2's own children ever report an ERROR/WARNING during a stall) needed to justify and target a forced-recovery mitigation in a future round, if warranted.
  timestamp: 2026-07-10

## Resolution

root_cause: >
  The Phase 84 adaptive buffer-duration growth mechanism (`_maybe_grow_buffer_duration`,
  30s -> 60s -> 120s after each "recovered" underrun cycle) never reaches the live
  hlsdemux2 element for an in-progress YouTube live session. `_on_deep_element_added`
  configures hlsdemux2's `max-buffering-time` / `high-watermark-time` properties exactly
  once, at element-creation time, using whatever `_current_buffer_duration_s` was at that
  instant (always the 30s baseline, since reset-before-apply wipes any prior growth
  before a new bind). No reference to the created hlsdemux2 element is retained, and no
  code path re-applies the grown value to it later. Result: hlsdemux2's real segment
  buffer capacity is permanently pinned at 30s for the life of a live session, no matter
  how many underrun cycles close as "recovered" and stage growth — the growth only moves
  a UI-facing counter (`_current_buffer_duration_s` / `buffer_duration_changed` Signal)
  and (uselessly, since the session never rebinds) `_pending_buffer_duration_s` for
  playbin3's downstream queue2, which does not govern hlsdemux2's independent segment
  buffer per the existing `hlsdemux2-owns-independent-segment-buffer` project-memory
  finding. Confirmed against production `buffer-events.log`: a single continuous
  2026-07-09 live session accumulated 57 "recovered" underrun cycles with no reduction in
  frequency/duration after growth should have capped at 120s by cycle #2.
fix: >
  Store a reference to the live hlsdemux2 element when `_on_deep_element_added` first
  configures it. Add a helper that re-applies `max-buffering-time` / `high-watermark-time`
  to that stored element immediately whenever `_maybe_grow_buffer_duration` stages a new
  value, so growth takes effect on the CURRENTLY RUNNING hlsdemux2 instance mid-session
  (not just at a future URI bind that mostly never happens for a live radio station).
  Clear the stored reference on pipeline teardown (`_try_next_stream` / `_set_uri`, both
  of which call `set_state(Gst.State.NULL)`) so a stale/disposed element is never targeted
  by a subsequent growth event from a new session.
verification: >
  Added 7 new regression tests to tests/test_player_buffer_growth.py covering:
  _live_hlsdemux2_element defaults to None; _on_deep_element_added captures the
  reference; a first cycle_close re-applies 60s to the LIVE element
  immediately; a second cycle_close re-applies the 120s cap to the same live
  element; growth is a safe no-op (no exception, UI-mirror still updates) when
  no hlsdemux2 element is live; _try_next_stream and _set_uri both clear the
  stale reference on pipeline teardown. RED-checked: stashed player.py changes
  only (kept new tests) — all 7 new tests failed against the pre-fix code
  (AttributeError / assertion failures), confirming they exercise the actual
  bug. Applied the fix back — all 7 pass. Full existing suite still green:
  63/63 in test_player_hlsdemux2_buffer.py + test_player_buffer_growth.py +
  test_player_buffer.py + test_player_underrun*.py combined before adding new
  tests; 40/40 in the two directly-touched files after adding new tests.
  Broader `pytest tests/ -k player` (241 tests, 1 skip) shows only one
  pre-existing unrelated failure (test_fake_player_no_inline.py — an inline
  FakePlayer hygiene violation in test_now_playing_stats.py, confirmed present
  on a clean stash of player.py/tests changes too — not caused by this fix).
  Self-verification confirms the code-level mechanism is fixed; end-to-end
  confirmation that live YouTube session drops/buffer-fill improve requires
  the user's real-world listening session (see CHECKPOINT).
files_changed:
  - musicstreamer/player.py
  - tests/test_player_buffer_growth.py

## Verification Feedback (Round 1) — PARTIAL FIX, reopened

User restarted the app on the fixed build and reproduced. Outcome: **improved but not resolved**.

- Buffer now DOES reach 100% at times (it never did pre-fix) → the growth-propagation fix is landing and helping. Confirms the original root cause was real and the fix works.
- Residual symptom: buffer still SUDDENLY drops from ~100% to 0% intermittently.
- Network during stalls: not checked by user.

### New evidence — post-fix live session 2026-07-10 08:39–08:49 (station_id=3300, X4VbdwhkE10)

```
08:39:58  live HLS DVR seek applied: 30 s behind hold-back position
08:40:54  buffer_underrun duration_ms=2935    min_percent=0  outcome=recovered  cause_hint=unknown
08:42:04  buffer_underrun duration_ms=12950   min_percent=0  outcome=recovered  cause_hint=unknown
08:46:43  buffer_underrun duration_ms=172493  min_percent=0  outcome=recovered  cause_hint=unknown   ← ~2m52s
08:49:33  buffer_underrun duration_ms=108802  min_percent=0  outcome=recovered  cause_hint=unknown   ← ~1m49s
```

Key observation: recovery durations of **172s and 108s** cannot be explained by buffer capacity — no reasonable buffer covers a ~3-minute upstream gap. When min_percent pins at 0 for minutes, the segment SOURCE (YouTube CDN / hlsdemux2 fetch) stopped supplying data, not the buffer being too small. This is a **segment-supply-stall** class of problem, distinct from the (now-fixed) buffer-capacity problem. `cause_hint=unknown` on every event — the underrun classifier is not attributing a cause.

## Current Focus (Round 2 — residual)

- hypothesis: CONFIRMED (see Resolution — Round 2). Hypothesis (d) is confirmed as the actionable, closable root cause this round: `cause_hint=unknown` on every underrun (including the 108s/172s stalls) is architecturally guaranteed, not a data artifact — the tracker's ONLY cause-attribution signal (`note_error_in_cycle`) is wired exclusively to top-level `message::error`, and hlsdemux2's segment-fetch retry/backoff machinery (`max-retries`=3, `retry-backoff-factor`=0, `retry-backoff-max`=60s — all left at GStreamer defaults, confirmed via `gst-inspect-1.0 hlsdemux2`) runs entirely inside hlsdemux2's own GstBin and is swallowed by GstBin's default message filtering (`message-forward`=false, also unconfigured by the player) — it never escalates to a fatal bus error for cycles that eventually recover (which is 100% of the 511 production events: none ever close as `outcome=failover`). Compounding this, the ONLY watchdog capable of forcing corrective action (`_failover_timer`) is a one-shot "stream never started" guard, permanently disarmed after the first audio tag — nothing in the player caps or even observes how long a mid-session stall persists once initial playback has begun. Hypotheses (a) genuine YT-CDN-side throttling as the ultimate trigger and (c) hlsdemux2 HTTP retry/backoff as the stall-duration mechanism remain the most likely explanation for WHY a fetch needs retrying at all — that portion is honestly assessed as primarily env/YT-side and not something this fix can eliminate. Hypothesis (b) DVR-seek staleness is eliminated (see Eliminated). Hypothesis re: forced-faster-reconnect-as-primary-fix is deferred, not eliminated (see Eliminated) — insufficient evidence yet to justify or target it; this round's fix is the prerequisite instrumentation that will supply that evidence for a future round if still needed.
- test: implemented fix (message-forward=True on hlsdemux2 + message::element bus handler unwrapping GstBinForwarded + new `_BufferUnderrunTracker.note_segment_retry_in_cycle()` cause_hint value) + new regression tests; verified via existing suite (test_player_hlsdemux2_buffer.py, test_player_underrun_tracker.py, test_player_underrun.py) plus new tests for the forwarding wiring and cause_hint classification.
- expecting: (a) the buffer-events.log will start showing `cause_hint=segment_retry` (or `error`-level `hls_segment_fetch_issue` log lines) on future long stalls IF hlsdemux2's internal children do post warnings/errors during them — giving definitive future evidence on whether this is CDN-side vs. something else; (b) if a future stall STILL shows `cause_hint=unknown` even with forwarding enabled, that itself is new evidence (e.g. a true silent TCP-level stall with no GStreamer-level warning at all, or nested-bin forwarding not reaching this depth) worth a Round 3 investigation.
- next_action: DONE this round — fix implemented, tests written and passing. Recommend to user: monitor `~/.local/share/musicstreamer/buffer-events.log` for `hls_segment_fetch_issue` lines and `cause_hint=segment_retry` on the next long stall; if stalls are consistently accompanied by forwarded WARNING/ERROR text mentioning connection/timeout issues, that confirms CDN/network-side triggering and the recommended next step is a bounded stall-duration watchdog (e.g. re-issue `_apply_live_dvr_seek` if a cycle stays open beyond ~90s) — NOT implemented this round due to insufficient evidence to verify it would help (see Eliminated).
- reasoning_checkpoint:
    hypothesis: "cause_hint=unknown on every underrun (including 108s/172s stalls) is caused by the tracker's cause-attribution being wired ONLY to top-level message::error, while hlsdemux2's internal segment-fetch retry/backoff runs inside its own GstBin with message-forward=false (default), so retry activity that recovers before becoming fatal is invisible to the app; separately, no watchdog caps mid-session stall duration once playback has started."
    confirming_evidence:
      - "Direct code read: note_error_in_cycle (the only cause_hint writer) is called only from _on_gst_error, which is wired only to message::error; grep confirms zero message::warning handlers anywhere in player.py."
      - "gst-inspect-1.0 hlsdemux2 (local GStreamer 1.28.2) directly confirms max-retries/retry-backoff-factor/retry-backoff-max exist and are never set by the player, and message-forward exists, defaults to false, and is never set by the player."
      - "Production log: 511/511 underrun cycles close with outcome=recovered (never failover) AND cause_hint=unknown (never network) -- consistent with retries succeeding internally before any fatal top-level error, which per the code read is the only way cause_hint could ever become anything but unknown."
      - "_failover_timer arm/disarm sites (grep, 6 call sites) confirm it is a one-shot pre-first-audio watchdog, stopped for good by the first message::tag and never re-armed mid-session."
    falsification_test: "If, after enabling message-forward and wiring the message::element handler, a live YouTube session's long stall (>60s) STILL shows cause_hint=unknown with zero hls_segment_fetch_issue log lines, the hypothesis that hlsdemux2's own children post observable warnings/errors during these stalls would be falsified (though the broader 'tracker was architecturally blind before this fix' claim would still stand as historically true)."
    fix_rationale: "The fix does not (and cannot, from this seat) address the ultimate CDN/network-side trigger of a segment-fetch stall -- that is honestly out of player-fixable scope this round. It DOES close the two concrete, root-caused, player-side gaps confirmed by direct evidence: (1) zero observability into hlsdemux2's internal retry activity (message-forward + bus handler fixes this at the standard GStreamer level), and (2) the tracker's cause_hint being permanently unable to represent 'hlsdemux2 was retrying' as anything other than unknown (new segment_retry value fixes this). This is the root cause of the requested symptom ('cause_hint=unknown on every event') and a prerequisite for evidence-based decisions about further mitigation."
    blind_spots: "Have NOT verified in a live YouTube session that hlsdemux2's internal children actually DO post forwarded WARNING/ERROR messages during a real stall (no reproduction available outside production) -- it is possible message-forward on hlsdemux2 does not reach deeply-nested internal elements (e.g. if the download workers are managed via non-Bin GStreamer objects, forwarding would not apply and cause_hint could remain unknown even after this fix). Have NOT verified whether a forced re-seek/reconnect would actually shorten recovery time -- deliberately not implemented this round for that reason (see Eliminated). Have NOT confirmed the exact numeric relationship between retry-backoff-max=60s / max-retries=3 and the observed 108s/172s durations without GStreamer source access -- treated as a plausible order-of-magnitude explanation, not a proven arithmetic derivation."
- tdd_checkpoint: (none — tdd_mode not set for this session)

## Resolution (Round 2)

root_cause: >
  The residual full-drain (`min_percent=0`) underrun cycles taking up to 172s
  to recover are a distinct problem class from the (already-fixed, Round 1)
  buffer-capacity bug: they are segment-supply stalls inside hlsdemux2's own
  internal HTTP fetch/retry machinery, not a buffer that is too small.
  `hlsdemux2` exposes configurable retry/backoff properties (`max-retries`=3,
  `retry-backoff-factor`=0, `retry-backoff-max`=60s — confirmed via
  `gst-inspect-1.0 hlsdemux2` against the project's GStreamer 1.28.2), none of
  which the player configures; they run at GStreamer defaults, entirely
  inside hlsdemux2's own GstBin. Two compounding, confirmed player-side gaps
  made this invisible and unmanaged:
  (1) `_BufferUnderrunTracker.note_error_in_cycle` — the ONLY mechanism that
  ever sets `cause_hint` away from `"unknown"` — is wired exclusively to the
  pipeline's TOP-LEVEL `message::error`. hlsdemux2's internal retry activity
  never escalates to a fatal top-level error for cycles that eventually
  recover (100% of the 511 production events close `outcome=recovered`,
  never `failover`), and is additionally swallowed outright by GstBin's
  default `message-forward=false` filtering (also never configured by the
  player) — so the tracker was architecturally guaranteed to see
  `cause_hint=unknown` for this entire class of event, regardless of how long
  the stall or how much internal retry activity occurred.
  (2) `_failover_timer`, the only watchdog capable of forcing corrective
  action, is a one-shot "stream never started" guard armed once per
  `_set_uri`/`_try_next_stream` and permanently disarmed the moment the first
  audio tag arrives (`_cancel_timers` via `message::tag`) — it is never
  re-armed mid-session, so nothing in the player caps or even measures how
  long a post-first-audio stall is allowed to persist. The player purely and
  indefinitely waits for `message::buffering` to climb back to 100%.
  Honest scope assessment: the ULTIMATE trigger for why a given segment fetch
  needed retrying at all (YouTube CDN hiccup / throttle on this stream) is
  primarily environment/YouTube-side and outside this fix's ability to
  eliminate. What IS root-caused and closable from the player side is the
  complete absence of visibility into that retry activity and the complete
  absence of any duration cap or corrective escalation once a stall begins.
fix: >
  (1) `_on_deep_element_added` now also calls new helper
  `_enable_hlsdemux2_message_forwarding(element)`, which sets
  `message-forward=True` on the live hlsdemux2 element (mirrors
  `_configure_hlsdemux2_buffer`'s defensive try/except for older/unusual
  GStreamer builds). This is the standard GstBin mechanism
  (gstreamer.freedesktop.org/documentation/gstreamer/gstbin.html) that
  re-posts otherwise-swallowed child ERROR/WARNING messages on the pipeline's
  top-level bus, wrapped as a `GST_MESSAGE_ELEMENT` with structure name
  `"GstBinForwarded"` and a `"message"` field carrying the original
  `GstMessage`.
  (2) New bus wiring: `bus.connect("message::element", self._on_gst_element_message)`.
  (3) New handler `_on_gst_element_message` unwraps `GstBinForwarded`
  envelopes, and for an inner ERROR or WARNING logs a new structured line
  (`hls_segment_fetch_issue level=... src=... err=... debug=...`) and calls
  new tracker method `note_segment_retry_in_cycle()`.
  (4) New `_BufferUnderrunTracker.note_segment_retry_in_cycle()` sets
  `cause_hint="segment_retry"` if a cycle is open and `cause_hint` is still
  `"unknown"` — a new, non-fatal cause value distinct from the existing
  `"network"` (reserved for a genuine top-level bus error, which also drives
  failover). `"network"` always wins over `"segment_retry"` if both fire in
  the same cycle (order-independent — verified by test).
  Deliberately NOT implemented this round (insufficient evidence to justify
  or verify — see Eliminated): a forced faster-recovery action (repeat
  DVR re-seek / full reconnect) triggered by a stall-duration watchdog. This
  is recommended as the natural next step IF the new instrumentation
  confirms (via `cause_hint=segment_retry` / `hls_segment_fetch_issue` log
  lines) that these stalls are consistently accompanied by observable
  internal retry activity.
verification: >
  RED-checked: stashed player.py changes only (kept new tests in
  tests/test_player_hlsdemux2_buffer.py and tests/test_player_underrun_tracker.py)
  — all 12 new Round-2 tests failed against the pre-fix code
  (AttributeError on `note_segment_retry_in_cycle`, or assertions on
  `message-forward` / `message::element` wiring that don't yet exist),
  confirming they exercise the actual gap. Applied the fix back — all 12
  pass, plus the full existing suite: 68/68 across
  test_player_hlsdemux2_buffer.py + test_player_underrun_tracker.py +
  test_player_underrun.py + test_player_buffer_growth.py combined.
  Broader `pytest tests/ -k player` (254 tests, 1 skip): 253 pass, 1
  pre-existing unrelated failure (`test_fake_player_no_inline.py` —
  inline FakePlayer hygiene violation in test_now_playing_stats.py,
  already documented as pre-existing and unrelated in the Round 1
  verification note; unaffected by this change).
  Self-verification confirms the instrumentation mechanism (message
  forwarding + cause_hint classification) is correctly wired and unit-tested.
  End-to-end confirmation that this genuinely closes the visibility gap in a
  REAL YouTube live session (i.e. that hlsdemux2's internal children do post
  observable forwarded messages during a real stall) requires the user's
  next real-world long-stall occurrence and a look at
  `~/.local/share/musicstreamer/buffer-events.log` for
  `cause_hint=segment_retry` / `hls_segment_fetch_issue` lines — see
  CHECKPOINT.
files_changed:
  - musicstreamer/player.py
  - tests/test_player_hlsdemux2_buffer.py
  - tests/test_player_underrun_tracker.py

## Resolution (2026-07-13)

Real-world verification via `~/.local/share/musicstreamer/buffer-events.log`. Fix
commits landed **2026-07-10 10:10:50** (R1, `9b49182e`) and **10:11:33** (R2,
`3a5f3b41`). Mapping underruns against that line:

- All ~14 underruns on station 3300 — including both long stalls (**103 s** at
  09:48, **89 s** at 09:58) — occurred **09:27–10:03, i.e. BEFORE the fix landed**.
  Pre-fix baseline, not evidence against the fix.
- Post-fix (after 10:10 on 07-10): a single `duration_ms=60 min_percent=1` blip on
  station 3305 at 22:21 — a 60 ms dip that never fully drained.
- 07-11 and 07-13: only clean session starts (`youtube resolve` →
  `live HLS DVR seek applied`), **zero underruns**.

User report: "Don't think I've had any issues in a while." — consistent with the log.

**Round 3 gate outcome:** neither branch fired. No long stall has recurred since the
fix, so there was nothing for the R2 instrumentation to classify and no
`cause_hint=segment_retry` / `hls_segment_fetch_issue` to act on. The stall-duration
watchdog (deliberately deferred pending evidence) is **not needed** — the residual
problem it targeted has not reproduced. R1's buffer-growth fix resolved the observed
symptom; R2 instrumentation remains in place as a safety net if it ever recurs.
