# Phase 62: Audio Buffer Underrun Resilience - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt
**Areas discussed:** Underrun trigger definition, Recovery indicator UX

---

## Underrun Trigger Definition

### Q1 — Canonical "this is an underrun" trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Percent<100 mid-playback | Any GST_MESSAGE_BUFFERING with percent<100 AFTER first PLAYING is an underrun. Simple, low false-negative; relies on Phase 47.1's existing buffer_percent flow. | ✓ |
| BUFFERING + state drop | Only count when GStreamer drops to PAUSED AND a BUFFERING message arrives. Stricter — catches genuine interruptions, ignores brief wobble. | |
| Hybrid: low-watermark + dwell | Underrun = dwell below low-watermark for >= N seconds OR state drop. Decouples log-worthy event from raw bus chatter. | |

**Notes:** Initial-fill phase (before first PLAYING) is excluded so "connecting" isn't counted (handled separately via Q4 — arm gate).

---

### Q2 — Coalesce multiple BUFFERING messages per recovery

| Option | Description | Selected |
|--------|-------------|----------|
| One event per recovery cycle | Cycle opens at first percent<100, closes at percent==100. Single structured log line at close: {start_ts, end_ts, duration_ms, min_percent, station, url, codec_if_known}. | ✓ |
| Edge-only (open + close) | Two log lines per cycle (open + close). No min-percent aggregation. Slightly chattier but lets you correlate raw transitions. | |
| Every BUFFERING message | Log every distinct percent value (after Phase 47.1 de-dup). Maximum signal for tuning, but logs noisy and harder to count "how many dropouts last hour". | |

**Notes:** Cleanest for diagnostics; matches how a human perceives a "glitch" as one event.

---

### Q3 — Closing an open cycle that never reaches 100

| Option | Description | Selected |
|--------|-------------|----------|
| Force-close on terminating events | Close + log on `_try_next_stream`, `stop()`, `pause()`, NULL state, app shutdown. Tag with `outcome: failover|stop|pause|shutdown`. | ✓ |
| Watchdog timeout | If cycle stays open > N seconds without reaching 100%, close with `outcome: stalled` regardless of pipeline state. Single mechanism. | |
| Both | Terminator events close fast; watchdog catches residual case (process kill, pipeline hang). | |

**Notes:** Terminator hooks already exist on the relevant call sites — minimal additional wiring.

---

### Q4 — Initial-fill suppression

| Option | Description | Selected |
|--------|-------------|----------|
| Arm on first 100% per URL | `_underrun_armed = False` per URL; first BUFFERING percent==100 since `_try_next_stream` arms it. Cycles only open while armed. Reset on URL change. Mirrors Phase 47.1's `_last_buffer_percent` reset pattern. | ✓ |
| Arm on first PLAYING state | Use existing `_on_gst_state_changed` filter to PLAYING. Arm on first PLAYING-after-NULL per URL. Slightly later than first 100%. | |
| Hybrid: arm on whichever fires first | Arm when EITHER first 100% OR first PLAYING fires. Belt-and-suspenders against ordering quirks. | |

**Notes:** Direct mirror of Phase 47.1 D-14 lifecycle — single source of truth for per-URL state reset.

---

## Recovery Indicator UX

### Q1 — Indicator surface

| Option | Description | Selected |
|--------|-------------|----------|
| Toast on dwell threshold | Toast `Buffering…` only when an underrun cycle stays open longer than N seconds. Brief auto-recoveries silent. One toast per cycle. | ✓ |
| Auto-show stats bar during recovery | Un-hide existing Phase 47.1 buffer-fill bar for the duration of an open cycle. The bar IS the indicator. | |
| New dedicated inline indicator | Always-present buffer/connection icon near now-playing that animates only during a cycle. | |
| Toast + stats-bar auto-show | Combine: toast on dwell + auto-show bar. Two channels, one cycle. | |

**Notes:** Fits existing `MainWindow.show_toast` pattern; matches the "non-spammy" spec language.

---

### Q2 — Dwell threshold value

| Option | Description | Selected |
|--------|-------------|----------|
| 1.5 seconds | Most sub-second recovers stay silent, but anything you'd actually hear (≈1-2s of dropout) toasts. Default in audio apps. | ✓ |
| 1.0 second | More aggressive — toast on most audible glitches including shorter ones. Slightly more frequent. | |
| 3.0 seconds | Conservative — only sustained recovery cycles toast. Less interruption, but misses some 1-2s glitches in indicator. | |
| You decide | Claude picks — default 1.5s based on common convention. | |

**Notes:** Reviewable post-implementation if the toast feels too eager / too quiet.

---

### Q3 — Toast copy and recovery confirmation

| Option | Description | Selected |
|--------|-------------|----------|
| Once per cycle: 'Buffering…' | Single toast at dwell threshold. Audio resuming IS the recovery signal. Simplest. | ✓ |
| Open + close: 'Buffering…' / 'Recovered' | Two toasts per cycle. Affirmative close, but is double-toast on every glitch. | |
| Once per cycle: 'Reconnecting…' | Same shape as option 1 but network-flavored copy. | |

**Notes:** U+2026 ellipsis matching existing `Connecting…`, `Stream failed, trying next…`.

---

### Q4 — Cooldown / anti-spam

| Option | Description | Selected |
|--------|-------------|----------|
| Cooldown: 10s between toasts | After toast, suppress further toasts for 10s. Subsequent cycles within window log normally — only toast suppressed. Recommended. | ✓ |
| Cooldown: 30s between toasts | Longer cooldown — fewer toasts on flaky network. | |
| No cooldown | Every cycle that crosses dwell threshold toasts. Bad-network night could see toast every 10–20s. | |
| Cooldown only across station | Reset cooldown on station change so a new station's first underrun always toasts. Otherwise 10s. | |

**Notes:** Uniform cooldown across station changes — no special-case reset.

---

### Q5 — Dwell timer mechanics on early close

| Option | Description | Selected |
|--------|-------------|----------|
| Cancel timer; no toast; still log | Sub-1.5s recoveries are below audible threshold. Cancel timer on close, never show toast, but DO write structured log line. | ✓ |
| Always log AND toast on close ≥ dwell threshold | Same as above, but also retroactively toast at close if duration_ms ≥ 1500. Catches edge case where timer scheduling slips. | |

**Notes:** Matches "silent below threshold" framing.

---

## Claude's Discretion

The following gray areas were NOT selected for discussion — Claude exercises discretion within the constraints captured in CONTEXT.md `<decisions>` and per-area Discretion notes:

- **Cause attribution depth** — minimal `cause_hint` field defaulting to `unknown`, with `network` only when `_on_gst_error` already fired for the same URL within the cycle. No CPU/clock-skew/decoder heuristics this phase.
- **Log sink** — stdlib `logging.getLogger(__name__)` at INFO level; planner may need to bump `__main__.py:222`'s `logging.basicConfig` level so INFO surfaces during diagnosis. No file sink, no in-app viewer.
- **Fix scope** — instrumentation-only this phase; behavior fix deferred to a follow-up phase, gated on observed root cause from collected logs. Phase 16 invariant (10s / 10MB) held verbatim (D-09).
- **Test repro for criterion #3** — deferred along with the fix. Test coverage this phase: state-machine unit tests + dwell-threshold smoke test.
- **Per-cycle log format** — JSON vs key=value left to Claude; field set is fixed.
- **Optional underrun counter in stats-for-nerds row** — defer if it adds UI test churn.

## Deferred Ideas

See CONTEXT.md `<deferred>` for the full list. Highlights:
- Behavior fix (criterion #3) — follow-up phase once log data identifies root cause.
- File log sink, in-app log viewer.
- Watchdog cycle timeout (rejected in favor of terminator-event close).
- Auto-show stats-for-nerds bar / recovery toast (both rejected).
- Throttled-network repro fixture for the follow-up phase.
