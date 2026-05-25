# Phase 62: Audio Buffer Underrun Resilience - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Make intermittent audio dropouts/stutters **observable** (structured per-event log lines with timestamps, duration, min fill, station/URL context, terminating outcome) and **recoverable from the user's perspective** (a single non-spammy `Buffering…` toast on cycles long enough to be audible). Surface lives in `musicstreamer/player.py` (event accounting + bus handler instrumentation) and `musicstreamer/ui_qt/main_window.py` (toast wiring). The Phase 16 buffer constants in `musicstreamer/constants.py` (10s / 10MB) MUST NOT regress this phase — see D-09.

**In scope:**
- Buffer underrun event tracker in Player: cycle open/close state machine driven by `Player.buffer_percent` (already emitted by `_on_gst_buffering`, Phase 47.1) + terminator hooks on `_try_next_stream` / `stop` / `pause` / NULL transition / shutdown.
- Structured log line per recovery cycle (one line, written at close) using stdlib `logging.getLogger(__name__)` — first logger in `player.py`.
- Toast wiring: a new Player-level Signal that fires only when an open cycle exceeds the 1.5s dwell threshold; MainWindow shows `Buffering…` on the existing `show_toast` channel with a 10s cooldown.

**Out of scope (deferred):**
- Behavior fix (buffer-duration / buffer-size tuning, reconnect logic, low-watermark threshold) — Spec criterion #3 lets us ship instrumentation now and the fix once root cause is observable from collected logs.
- Cause attribution beyond outcome tag + duration + min-percent (no CPU sampling, no clock-skew heuristics this phase).
- File-based log sink, in-app log viewer, log download — stderr via the existing `logging.basicConfig` is sufficient for diagnosis.
- Auto-showing the Phase 47.1 stats-for-nerds bar during a cycle — user opted for toast-only.
- Recovery / "back-to-normal" affirmative toast.

</domain>

<decisions>
## Implementation Decisions

### Underrun Trigger Definition

- **D-01:** An underrun event is any `GST_MESSAGE_BUFFERING` with `percent < 100` while the URL's tracker is **armed** (D-04). The existing `_on_gst_buffering` handler at `player.py:448` is the single observation site; no new bus subscriptions.
- **D-02:** Coalesce to **one event per recovery cycle**. The cycle opens on the first `percent < 100` post-arming and closes on the first `percent == 100` thereafter (or on a terminator, D-03). Exactly one structured log line is written at close, carrying `{start_ts, end_ts, duration_ms, min_percent, station_id, station_name, url, outcome, cause_hint}`. The cycle's `min_percent` is updated on every BUFFERING message during the open window; the rest of the fields are captured at open and finalized at close.
- **D-03:** **Force-close on terminator events** with `outcome` tag. Hooks: `_try_next_stream` (→ `failover`), `stop()` (→ `stop`), `pause()` (→ `pause`), explicit `set_state(NULL)` paths inside `_try_next_stream` (→ `failover`, dedup with above), and process shutdown / `closeEvent` (→ `shutdown`). Natural close at `percent == 100` uses outcome `recovered`. No watchdog timeout in this phase.
- **D-04:** **Arm on first `percent == 100` per URL.** New per-URL state `_underrun_armed: bool = False`, reset to `False` inside `_try_next_stream` at the same site that already resets `_last_buffer_percent = -1` (Phase 47.1 D-14). Inside `_on_gst_buffering`, the first `percent == 100` flips arm to `True`. While unarmed, `percent < 100` is the initial fill — observed but not opened as a cycle. Lifecycle mirrors Phase 47.1's sentinel reset exactly.

### Recovery Indicator UX

- **D-05:** **Toast-only indicator.** No new always-visible chrome. The Phase 47.1 stats-for-nerds buffer bar continues to honor its existing hamburger-menu toggle and is **not** auto-shown during a cycle (rejected during discussion).
- **D-06:** **Toast text: `Buffering…`** (U+2026 ellipsis, matching existing `Connecting…`, `Stream failed, trying next…`). Exactly one toast per cycle. No recovery / "back-to-normal" toast — the audio resuming is itself the recovery signal.
- **D-07:** **Dwell threshold = 1500 ms.** Cycle open starts a `QTimer.singleShot(1500, …)` on the main thread (cross-thread marshalling required: bus handler runs on GstBusLoopThread per Pitfall 2 — emit a queued Signal first, then arm the QTimer in the main-thread slot). If the cycle closes (any outcome) before the timer fires, cancel the timer — no toast, still log.
- **D-08:** **Toast cooldown = 10 000 ms.** After a `Buffering…` toast fires, suppress further toasts for 10 s. Subsequent cycles within the cooldown window still log normally — only the user-facing toast is debounced. Cooldown clock is wall-clock-based and persists across station changes (no special-case reset).

### Phase 16 Invariant (Carried Forward)

- **D-09:** `BUFFER_DURATION_S = 10` and `BUFFER_SIZE_BYTES = 10 * 1024 * 1024` in `musicstreamer/constants.py` (Phase 16 / STREAM-01) **MUST NOT** be modified in this phase. ROADMAP success criterion #4 binds: any change requires an explicit decision logged here. None is taken — instrumentation is the deliverable. The behavior fix that may eventually adjust these constants is a follow-up phase (deferred).

### Claude's Discretion

- **Cause attribution depth.** D-02 specifies a `cause_hint` field, but the heuristic for filling it is intentionally minimal this phase: default `unknown`, with `network` only when `_on_gst_error` has already fired for the same URL within the same cycle. CPU sampling, clock-skew measurement, and decoder-stall detection are NOT added — they would be premature without observed root cause. Planner may keep `cause_hint` populated as `unknown` end-to-end if simpler.
- **Log sink.** Use `_log = logging.getLogger(__name__)` (first logger in `player.py`) emitted at `INFO` level for cycle close. The existing `logging.basicConfig(level=logging.WARNING)` in `__main__.py:222` suppresses INFO by default — the planner should bump that to `INFO` for `musicstreamer.player` (or unconditionally) so events surface during diagnosis. File sink, ring buffer, and in-app log viewer are deferred.
- **Test repro for criterion #3.** Since instrumentation-only ships this phase, criterion #3 (demonstrably-reduced dropout count) is **deferred to a follow-up phase**, gated on observed log data. Test coverage this phase: unit tests for the cycle state machine (open/close/force-close/arm-gate) + a smoke test that the dwell-threshold path emits the Signal exactly once. No live-stream repro required.
- **Per-cycle structured log format.** Single-line key=value or JSON — Claude picks based on what looks cleanest in the existing log output. Suggested fields are non-negotiable (D-02); format is.
- **Counter for diagnostics convenience.** A tiny `_underrun_event_count: int` on Player can be incremented at every cycle close and exposed via the existing stats-for-nerds extensible `QFormLayout` (Phase 47.1 D-09) as "Underruns: {N}". Optional — Claude can defer if it adds churn to UI tests.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Player / GStreamer bus
- `musicstreamer/player.py` — class-level `Signal` pattern around line 80; `_on_gst_buffering` at line 448 (single observation site for percent); `_on_gst_state_changed` at line 463 (PLAYING-state filter, useful if D-04 needs an alternate arm path); `_try_next_stream` at line 529 (existing `_last_buffer_percent = -1` reset site at line 545 — same lifecycle hook for arm-state reset)
- `musicstreamer/constants.py` lines 54-56 — Phase 16 buffer constants (`BUFFER_DURATION_S`, `BUFFER_SIZE_BYTES`); D-09 invariant binds.

### UI / toast wiring
- `musicstreamer/ui_qt/main_window.py:344` — `show_toast(text, duration_ms=3000)` API; existing wiring site for Player Signals around line 274 (`buffer_percent.connect(...)`, `cookies_cleared.connect(self.show_toast)` are the patterns to follow for the new dwell-threshold Signal).
- `musicstreamer/ui_qt/now_playing_panel.py` — `set_buffer_percent` at line 640; `_build_stats_widget` at line 1377 (only relevant if Claude exposes the optional underrun counter from Discretion notes).

### Prior-phase context (reuse / non-regression)
- `.planning/milestones/v2.0-phases/47.1-stats-for-nerds-buffer-indicator/47.1-CONTEXT.md` — `Player.buffer_percent = Signal(int)` contract; D-14 sentinel-reset-per-URL pattern that D-04 mirrors; stats-for-nerds extensibility (`QFormLayout`).
- `.planning/milestones/v1.4-ROADMAP.md` — Phase 16 STREAM-01 rationale (10s / 10MB baseline).

### Threading / bus-handler pitfalls (MANDATORY for cross-thread work)
- `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` — Pitfall 1 (`parse_buffering` flatten), Pitfall 2 (bus-loop thread has no Qt event loop — must use queued Signals), Pitfall 3 (per-URL sentinel reset). All three apply directly to the cycle state machine and dwell-timer arming.

### Logging convention
- `musicstreamer/aa_import.py:20`, `musicstreamer/media_keys/mpris2.py:53`, `musicstreamer/url_helpers.py:16`, `musicstreamer/single_instance.py:27`, `musicstreamer/runtime_check.py:22` — established `_log = logging.getLogger(__name__)` pattern.
- `musicstreamer/__main__.py:222` — `logging.basicConfig(level=logging.WARNING)` site; planner adjusts to surface INFO for `musicstreamer.player` (Discretion).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`Player.buffer_percent = Signal(int)`** (Phase 47.1): the single source of buffer-fill truth. De-dup-on-unchanged is already built in (`_last_buffer_percent`). The cycle tracker subscribes via the same value the UI bar already consumes — no new bus wiring required.
- **`_on_gst_buffering`** (player.py:448): runs on `GstBusLoopThread`. The cycle state machine lives here. All cross-thread work (toast, dwell timer arming) MUST go through queued Signals (Pitfall 2).
- **`_try_next_stream`** (player.py:529): already resets per-URL state at line 545. Adding `_underrun_armed = False` and an open-cycle force-close (`outcome = failover`) at the same site is a single-block edit.
- **`MainWindow.show_toast`** (main_window.py:344): the existing channel for non-modal user notifications; 8+ producers already wire to it. No new UI infrastructure.
- **`logging.getLogger(__name__)`**: established convention in 10+ modules. `player.py` currently has zero logging — this phase introduces the first logger in that file.
- **`QTimer` main-thread parented to self**: dwell timer construction follows the existing pattern at player.py:148-180 (Pitfall 2: parented to `self`, main-thread).

### Established Patterns
- Bound-method `Signal.connect(...)` (QA-05) — no self-capturing lambdas. The new `underrun_recovery_started` (or equivalently named) Signal connects to a `MainWindow._on_underrun_recovery_started` slot that calls `show_toast`.
- Per-URL state reset inside `_try_next_stream` mirrors Phase 47.1 D-14 sentinel pattern. Add `_underrun_armed = False` in the same block.
- Queued Signals for cross-thread marshalling (Pitfall 2). Bus-loop handler may only emit Signals — never set timers, touch widgets, or call Qt directly.
- Force-close on terminating user actions: `_cancel_timers` already encodes the convention of stopping pending state on `pause` / failover / etc. — the cycle force-close attaches to the same call sites.

### Integration Points
- `Player.__init__` constructs the dwell timer (`self._underrun_dwell_timer: QTimer`, single-shot, parented to self, interval 1500 ms) and the cooldown bookkeeping (`self._last_underrun_toast_ts: float | None = None`). New module-level `_log = logging.getLogger(__name__)`.
- `_on_gst_buffering` extends with: arm gate; cycle open (record start_ts, station context, schedule dwell timer via main-thread queued Signal); update `min_percent` on each subsequent message; cycle close on `percent == 100` (outcome=`recovered`, write log line, cancel timer).
- `_try_next_stream` / `stop` / `pause` extends with: if cycle is open, force-close with appropriate outcome and write log line. The existing `_cancel_timers` is the analog hook for the dwell timer cancellation.
- App shutdown / `MainWindow.closeEvent` (or `Player.shutdown` if one exists) extends with: force-close any open cycle as `outcome=shutdown`.
- `MainWindow` adds one queued connection from the new `underrun_recovery_started` Signal to a slot that checks the 10s cooldown gate, emits `show_toast("Buffering…")`, and updates the cooldown timestamp.

</code_context>

<specifics>
## Specific Ideas

- Toast text **`Buffering…`** with U+2026 ellipsis — matches the existing copywriting style of `Connecting…` and `Stream failed, trying next…` (per UI-SPEC convention seen in main_window.py:367, 393).
- Dwell threshold **1500 ms** — common audio-app convention (sub-1.5s glitches are typically inaudible or imperceptible).
- Toast cooldown **10 000 ms** — uniform across station changes; no special-case reset.
- Structured log fields (D-02): `start_ts, end_ts, duration_ms, min_percent, station_id, station_name, url, outcome, cause_hint`. Outcomes: `recovered | failover | stop | pause | shutdown`.

</specifics>

<deferred>
## Deferred Ideas

- **Behavior fix (success criterion #3)** — buffer-duration / buffer-size adjustment, reconnect logic, low-watermark threshold, smarter underrun recovery. This phase ships instrumentation; the fix is a follow-up phase scheduled once log data identifies a root cause. Phase 16 baseline (10s / 10MB) held verbatim per D-09.
- **Cause attribution beyond outcome + duration + min_percent** — CPU sampling, wall-clock-vs-pipeline-clock skew detection, decoder-vs-network discrimination. Premature without data; revisit once instrumentation produces enough samples.
- **File-based log sink** — dedicated `~/.local/share/musicstreamer/buffer-events.log` ringfile with rotation. stderr via stdlib logging is sufficient for now; revisit if Kyle wants a portable diagnostic file to share.
- **In-app log viewer / hamburger menu "Show buffer events…"** — not requested; adds UI surface area without proven need.
- **Auto-show stats-for-nerds buffer bar during a cycle** — explicitly rejected during discussion (toast-only chosen).
- **Recovery / "back-to-normal" affirmative toast** — explicitly rejected (silent recovery).
- **Watchdog cycle timeout** — explicitly rejected; force-close on terminator events is sufficient given current call-site coverage.
- **30 s cooldown variant** — considered, rejected in favor of 10 s.
- **Underrun counter in stats-for-nerds row** — optional in Discretion notes; Claude defers if it adds churn to UI tests.
- **Throttled-network repro fixture** — not required this phase since the fix is deferred. May be needed for the follow-up behavior-fix phase.

</deferred>

---

*Phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt*
*Context gathered: 2026-05-07*
