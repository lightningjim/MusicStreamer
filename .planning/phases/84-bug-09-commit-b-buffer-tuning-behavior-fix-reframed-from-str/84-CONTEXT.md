# Phase 84: BUG-09 Commit B — buffer-tuning behavior fix (reframed) - Context

**Gathered:** 2026-05-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the buffer-tuning behavior fix that Phase 78 deferred as Commit B. Phase 78 Commit A shipped harvest infrastructure on 2026-05-17 (`RotatingFileHandler` at `~/.local/share/musicstreamer/buffer-events.log`, live `Underruns: {N}` row in stats-for-nerds). Seven days of real-world harvest yielded 12 `buffer_underrun` events — enough for directional signal, NOT enough for the originally-specified statistical `M < N + median improvement` closure gate. Phase 84 is the reframed delivery: pick a meaningful static bump, layer adaptive growth on top, and ship under a "ship + monitor" closure rather than rigorous A/B.

Phase 16's `STREAM-01` baseline (`BUFFER_DURATION_S=10`, `BUFFER_SIZE_BYTES=10MB`) was unlocked in Phase 78 D-09 for this work. Both values change here; the rationale (D-10 below) cites the harvest data.

**In scope:**

- **Static bump:** `BUFFER_DURATION_S` 10 → **30** seconds and `BUFFER_SIZE_BYTES` 10MB → **20MB** in `musicstreamer/constants.py`. Both knobs in one coordinated change so the byte cap isn't the limiter at high-bitrate sources (e.g. GBS.FM FLAC ≈ 1.4Mbps would saturate 10MB before 30s).
- **Full adaptive growth (D-11) with mid-session property writes:** First in-session underrun bumps live `buffer-duration` 30 → 60s. Second underrun → 120s (cap). Resets to 30s baseline on station change at the `_try_next_stream` URL-bind site. Implementation writes the new value via `self._pipeline.set_property("buffer-duration", new_value * Gst.SECOND)` mid-session. Carries a research dependency the planner must resolve (D-11 fallback).
- **Stats-for-nerds row:** Always-visible `Buffer: 30s` (or `60s (adapted)` / `120s (adapted)`) row added in `_build_stats_widget` at `now_playing_panel.py:2478` (after the existing `Buffer` progressbar row and the Phase 78 `Underruns: {N}` row). Communicates the new baseline up-front since 30s is a meaningful change from the 10s users may remember.
- **VERIFICATION.md with waived gate + monitor plan:** Phase 84 writes `84-VERIFICATION.md` documenting that the Phase 78 D-06 `M < N AND median lower` gate is explicitly **waived** under the harvest-week reframe. Closure is "ship + monitor 2 weeks; revisit if dropouts persist". BUG-09 SC #3 (behavior side) closes on the Phase 84 ship commit; the monitor plan defines what triggers a follow-up phase.
- **Tests:** Unit tests for the new constants values, the adaptive growth state machine (counter increment, schedule application, reset on URL bind, cap clamp), and the stats row label updates. Mid-session property-write contract verified via mocked pipeline call assertions (per the GStreamer mock-blind-spot memory: also a source-level grep gate proving the call uses `buffer-duration` not legacy 1.x names).

**Out of scope (deferred):**

- **Reconnect-on-stall logic** — Phase 78 deferred; remains deferred. Bring forward only if post-Phase-84 monitoring shows long-cycle `recovered` events persist.
- **`low-percent` / `high-percent` queue2 watermark tuning** — Phase 78 deferred; remains deferred.
- **Per-station configurable buffer override** — Phase 78 rejected; not reopened.
- **Synthetic throttled-network repro fixture** — Phase 78 deferred; not needed under the "ship + monitor" reframe.
- **Distinct `Reconnecting…` toast** — Phase 78 rejected; Phase 62 silent-recovery philosophy holds.
- **ROADMAP.md entry amendment** — User chose to capture the corrected harvest split (12 events, 5 long with 2 YT / 3 SomaFM) in this CONTEXT.md only. ROADMAP entry stays as-written (historical record of the reframe decision; this CONTEXT.md is the corrected data source going forward).

</domain>

<data-summary>
## Harvest-week data (Commit A → 2026-05-24)

Source: `~/.local/share/musicstreamer/buffer-events.log` (lines containing `buffer_underrun`). Window: 2026-05-19 09:09 → 2026-05-24 15:07 (~5.25 days of recorded events, 7 days since Commit A ship).

**Totals:** 12 `buffer_underrun` events (roadmap entry says 11; +1 event landed during 2026-05-24 between roadmap write and this CONTEXT capture).

**Long events (>1s) — 5 total:**

| When | Duration | Station | URL kind | min_percent | outcome | cause_hint |
|---|---|---|---|---|---|---|
| 2026-05-19 09:09 | 6683ms | lofi hip hop | YouTube | 0 | recovered | unknown |
| 2026-05-19 12:03 | 1356ms | Groove Salad | SomaFM mp3 | 0 | recovered | unknown |
| 2026-05-24 10:22 | 5474ms | Drone Zone | SomaFM mp3 | 1 | recovered | **network** |
| 2026-05-24 11:23 | 7389ms | medieval lofi | YouTube | 0 | recovered | unknown |
| 2026-05-24 15:07 | 2446ms | Drone Zone | SomaFM mp3 | 0 | recovered | unknown |

**Brief events (<200ms) — 7 total:** 6 SomaFM micro-recoveries + 1 GBS.FM. All `outcome=recovered` (or `preroll` for the one 2026-05-23 20:13 Drone Zone event, which is a Phase 83 startup-handoff artifact, not a true underrun).

**Cluster split (corrected from roadmap entry):**
- Long events: **2 YouTube / 3 SomaFM** (roadmap entry said "3 of 4 YouTube" — incorrect; the 2026-05-24 events shifted the count and split).
- YouTube worst-case magnitude: 7389ms.
- SomaFM worst-case magnitude: 5474ms (the one event with `cause_hint=network`).
- Both clusters are worth targeting — YouTube has worse magnitude per event, SomaFM has more long events.

**Per Phase 78 D-09 invariant:** Phase 16 baseline (10s / 10MB) is explicitly unlocked here. New baseline (30s / 20MB, D-10) chosen to cover the 7.4s worst case with substantial headroom while keeping startup latency modest. Adaptive growth (D-11) handles the rare case where 30s isn't enough.

</data-summary>

<decisions>
## Implementation Decisions

### Framing

- **D-09:** **Reframe target as "both clusters", not "YouTube only".** Harvest data corrected: 5 long events split 2 YT / 3 SomaFM (not 3:1 as the roadmap entry stated). Decisions tune for whichever cluster has worse magnitude OR higher count, not just the YouTube cluster. The roadmap entry's "target the LONG-event YouTube cluster" framing is superseded by this CONTEXT.md's `<data-summary>` section. ROADMAP.md entry is NOT amended (user choice — historical record of reframe stands; this CONTEXT.md is the corrected forward-going source).

### Static bump (Phase 16 baseline change)

- **D-10:** **`BUFFER_DURATION_S` 10 → 30; `BUFFER_SIZE_BYTES` 10MB → 20MB.** Both knobs change in `musicstreamer/constants.py:55–56`, in a single coordinated edit. 3× duration headroom comfortably absorbs the observed 7.4s worst case with room for growth. 20MB byte cap ensures the byte limit doesn't constrain the duration target at high-bitrate sources (FLAC stations like GBS.FM ≈ 1.4Mbps would hit a 10MB cap before 30s elapses; 20MB gives ~110s worst-case headroom). Rejected: 20s-only (covers worst case with zero margin); 60s-only (~3–6s perceptible startup latency, overkill for observed magnitudes). The player.py comment block above lines 318–319 about "HTTP audio sources buffer-duration/buffer-size are silently ignored" is misleading legacy text — the `flags | 0x100` (`GST_PLAY_FLAG_BUFFERING`) added in Phase 16 makes both knobs honored. Planner may freshen the comment block as a drive-by.

### Adaptive growth (full mid-session)

- **D-11:** **Ship full adaptive growth with mid-session `set_property` writes.** Schedule: 30 → 60 → 120s (cap). First in-session `cycle_close` triggers the 60s write; second triggers the 120s write; subsequent underruns stay at 120s. Reset to 30s on `_try_next_stream` URL-bind (mirrors Phase 47.1 D-14 sentinel-reset pattern and Phase 62 D-04 `_underrun_armed` reset). Counter is a new instance field `_current_buffer_duration_s: int = BUFFER_DURATION_S` plus a per-session growth-step counter; both reset at URL bind, NOT at app launch.
  - **Research dependency:** Verify playbin3 honors mid-session writes to the `buffer-duration` property (Phase 78 D-05 originally flagged this). Planner MUST resolve this before locking the implementation; expected via `gsd-phase-researcher` reading `.planning/phases/62-*-RESEARCH.md` + the playbin3 documentation + the spike-findings-musicstreamer skill.
  - **Fallback if mid-session writes don't work:** Apply new `buffer-duration` only at next URL bind in `_try_next_stream` (still adaptive, just at station-boundary granularity rather than mid-stream). Functionally degraded but doesn't block ship. Choice between mid-session and next-bind must be documented in `84-RESEARCH.md` with playbin3 evidence.

### UI / observability

- **D-12:** **Always-visible `Buffer: Xs` row in stats-for-nerds.** Format: `Buffer: 30s` when at baseline; `Buffer: 60s (adapted)` or `Buffer: 120s (adapted)` after growth fires. Row lives in `_build_stats_widget` at `now_playing_panel.py:2478`, immediately after the Phase 78 `Underruns: {N}` row (which is itself after the existing `Buffer` progressbar row). Uses `_MutedLabel` (Phase 47.1 D-10) and inherits hamburger-toggle visibility. Always-shown rather than adapted-only (Phase 78 D-08 default) because the 30s baseline itself is a meaningful change from the long-standing 10s and worth surfacing. Driven by a new `Player` Signal — bias toward `buffer_duration_changed = Signal(int)` (seconds), emitted on every change to `_current_buffer_duration_s` (initial set, growth steps, and URL-bind reset).

### Closure / verification

- **D-13:** **VERIFICATION.md with waived gate + monitor plan.** Write `84-VERIFICATION.md` that:
  1. Explicitly states the Phase 78 D-06 `M < N AND median lower` gate is **waived** for this phase, with the reframe rationale (only 12 events / 7 days = insufficient sample for marginal-effect detection).
  2. Documents the "ship + monitor" closure: 2-week post-ship monitoring window, comparing `buffer_underrun` event count and long-event magnitudes in `~/.local/share/musicstreamer/buffer-events.log` against the harvest-week baseline.
  3. Defines the **follow-up trigger**: if 2-week post-ship window shows ≥3 long events (>1s) with `min_percent=0`, OR any `recovered` event >10s, OR ≥1 `cause_hint=network` event, open a follow-up phase to evaluate reconnect-on-stall logic (Phase 78 deferred item, still parked).
  4. BUG-09 SC #3 (behavior side) **closes on the Phase 84 ship commit** — not pending the monitor window. The monitor window is forward-looking guidance, not a closure prerequisite. SC #3 logging side already closed by Phase 78 Commit A.

### Claude's Discretion

- **Counter Signal naming.** D-12 suggests `buffer_duration_changed = Signal(int)`. Planner may pick a different name if it conflicts with an existing Signal or breaks naming parity with `underrun_count_changed` from Phase 78.
- **Growth-step counter location.** Could live on `Player` directly or on the `_BufferUnderrunTracker` class. Planner picks based on whichever has cleaner access to the per-URL reset hook.
- **Player.py legacy comment freshening.** D-10 mentions the misleading "HTTP audio sources silently ignored" comment above lines 318–319. Planner may rewrite it inline as a drive-by, or leave a TODO note for a future cleanup phase. Either is fine.
- **Stats row exact label string.** D-12 sketches `Buffer: 30s` and `Buffer: 60s (adapted)`. Planner may use `Buffer duration: 30s` or other phrasing if it reads better alongside the existing `Buffer` progressbar row (which would create label collision).
- **Reset granularity if research forces next-bind fallback.** If mid-session writes don't work and we fall back to URL-bind application, the "second underrun → 120s" semantics need reconsideration (you can't grow twice in one URL session if growth requires a URL bind). Planner must address this in RESEARCH.md and may simplify to a single-step "second URL underruns → next bind gets cap value".

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 78 (this phase is Commit B of the Phase 78 two-stage plan)
- `.planning/phases/78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug/78-CONTEXT.md` — D-01 (two-stage shape), D-04/D-05/D-06 (directional `[informational]` decisions that this phase locks), D-08 (stats-for-nerds row pattern, modified here by D-12), D-09 (Phase 16 baseline unlocked).
- `.planning/phases/78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug/78-RESEARCH.md` — playbin3 / queue2 background; re-read for D-11 mid-session-write research dependency.
- `.planning/phases/78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug/78-VERIFICATION.md` — Phase 78 Commit A closure record; Commit B (this phase) appends or links a separate `84-VERIFICATION.md`.

### Phase 62 (carry-forward is mandatory — Phase 84 extends the instrumentation surface)
- `.planning/phases/62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt/62-CONTEXT.md` — D-01..D-09; D-09 baseline-unlock predicate, Pitfall 5 (`basicConfig(WARNING)` invariant — DO NOT regress), silent-recovery philosophy.
- `.planning/phases/62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt/62-RESEARCH.md` — GStreamer queue2 / playbin3 buffering reference; mid-session property-write semantics needed for D-11.
- `.planning/phases/62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt/62-VERIFICATION.md` — Phase 62 closure record; SC #3 explicitly deferred to Phase 78 → Phase 84.

### Phase 16 (baseline this phase changes)
- `.planning/milestones/v1.4-ROADMAP.md` — Phase 16 STREAM-01 rationale (10s / 10MB baseline). Phase 78 D-09 unlocked it; Phase 84 D-10 changes it to 30s / 20MB with the `<data-summary>` block above as evidence.

### Phase 47.1 (stats-for-nerds row pattern Phase 84 extends)
- `.planning/milestones/v2.0-phases/47.1-stats-for-nerds-buffer-indicator/47.1-CONTEXT.md` — `_stats_widget` extensibility, `_MutedLabel` pattern, hamburger-toggle visibility, sentinel-reset pattern (D-14) reused for D-11 per-URL reset semantics.

### Threading / GStreamer pitfalls (mandatory before any Player or pipeline edit)
- `./.claude/skills/spike-findings-musicstreamer/SKILL.md` — full skill index.
- `./.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` — Pitfall 2 (bus-loop thread has no Qt event loop — queued Signals required for cross-thread marshalling). The new `buffer_duration_changed` Signal emits from `_on_underrun_cycle_closed` (already on the main thread per Phase 62 wiring), so `DirectConnection` is acceptable; document explicitly.
- Phase 62 Pitfall 5 (carried via 62-CONTEXT.md) — `__main__.py` `basicConfig(WARNING)` is byte-identical; no edit lands there.

### Player / GStreamer surface (edit sites)
- `musicstreamer/constants.py:54–56` — `BUFFER_DURATION_S = 10` and `BUFFER_SIZE_BYTES = 10 * 1024 * 1024`. D-10 changes both. The misleading inline comment on `BUFFER_SIZE_BYTES` ("5 MB") is wrong even pre-change (it's 10MB); fix as a drive-by.
- `musicstreamer/player.py:318–319` — `set_property("buffer-duration", ...)` and `set_property("buffer-size", ...)` apply sites. D-11 mid-session writes hit the same property names.
- `musicstreamer/player.py:325` — `flags | 0x100` (`GST_PLAY_FLAG_BUFFERING`) — DO NOT regress. This is what makes the buffer-duration / buffer-size properties actually honored on HTTP sources.
- `musicstreamer/player.py:918` — `_on_underrun_cycle_closed` slot. D-11 growth-step increment + new `buffer_duration_changed.emit(...)` lands here. Already main-thread.
- `musicstreamer/player.py` `_try_next_stream` (search for `set_property("uri"`) — D-11 URL-bind reset site for `_current_buffer_duration_s` and the per-session growth-step counter.

### UI surface (edit sites)
- `musicstreamer/ui_qt/now_playing_panel.py:2451` — `_build_stats_widget`. D-12 row lands here.
- `musicstreamer/ui_qt/now_playing_panel.py:2478` — `form.addRow(_MutedLabel("Buffer", …), value_row)` is the anchor; new `Buffer: Xs` row goes after the Phase 78 `Underruns: {N}` row (which itself was added after this anchor in Phase 78 Commit A).
- `musicstreamer/ui_qt/main_window.py:294` — `underrun_recovery_started.connect(...)` and the Phase 78 `underrun_count_changed.connect(...)` are the wiring siblings for the new `buffer_duration_changed.connect(...)`.

### Mock-blind-spot guardrail (carry-forward from memory)
- See `MEMORY.md` → `feedback_gstreamer_mock_blind_spot.md`. Tests for D-11 mid-session writes MUST include a source-level grep gate that bans legacy playbin 1.x property names (e.g. `playbin2`-era spellings) on the playbin3 code paths. Mock-only assertion is insufficient.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 78 `_underrun_event_count` + `underrun_count_changed` Signal pattern** — Already wired through `Player → MainWindow → NowPlayingPanel`. The new `buffer_duration_changed = Signal(int)` follows the same shape, same wiring path, same `_MutedLabel`-based stats row pattern. Adding D-12's row is structurally a copy-edit of the Phase 78 Underruns row.
- **`musicstreamer/paths.py` `buffer_events_log_path()`** — Already exists (Phase 78 Commit A). VERIFICATION.md monitoring window reads from this path; no new path helper needed.
- **`_MutedLabel`** — Theme-responsive label from Phase 47.1; the new D-12 row uses it directly.
- **`_try_next_stream` per-URL reset block** — Already houses `_last_buffer_percent = -1` and `_underrun_armed = False` resets (Phase 62 D-04). D-11 adds two more lines: `_current_buffer_duration_s = BUFFER_DURATION_S` and `_growth_step = 0` (or equivalent).

### Established Patterns
- **Per-logger level escalation, root `basicConfig(WARNING)` preserved** — Phase 62 Pitfall 5. Phase 84 does NOT touch logging; this is here to enforce the no-regression invariant.
- **Bound-method `Signal.connect`** — QA-05 carry-forward. New `buffer_duration_changed.connect(self._on_buffer_duration_changed)` follows this — no lambdas.
- **Cross-thread Signals are queued; same-thread Signals may be Direct (document the choice)** — Phase 62 Pitfall 2.
- **Per-URL state reset in `_try_next_stream`** — Phase 47.1 D-14, Phase 62 D-04, Phase 78 D-Discretion. D-11 extends.
- **Stats-for-nerds rows added via `form.addRow(_MutedLabel(...), value_row)` before the trailing `wrapper.setVisible(False)`** — Phase 47.1 D-05 + Phase 78 D-08.

### Integration Points
- **`musicstreamer/constants.py:54–56`** — Static bump (D-10). Single coordinated edit.
- **`musicstreamer/player.py`** — `__init__` instance fields (`_current_buffer_duration_s`, `_growth_step`); new `Signal(int)` declaration alongside Phase 78's `underrun_count_changed`; growth logic in `_on_underrun_cycle_closed`; reset hooks in `_try_next_stream`; pipeline `set_property("buffer-duration", ...)` mid-session write call (D-11, gated on RESEARCH.md verification).
- **`musicstreamer/ui_qt/now_playing_panel.py:2478+`** — One new `form.addRow` for the D-12 `Buffer: Xs` row; one new setter slot (`set_buffer_duration(int)` or equivalent).
- **`musicstreamer/ui_qt/main_window.py:~294`** — One new `.connect(...)` for the new Signal.

### Files NOT to touch
- `musicstreamer/__main__.py` — Phase 62 Pitfall 5 + Phase 78 Commit A drift-guard. `basicConfig(WARNING)` and the player-logger escalation are byte-identical invariants.
- INFRA-01 FakePlayer (`tests/conftest.py` or wherever the Player-parity protocol lives) — must mirror any new public Signal added to `Player`. Phase 78 Commit A established the drift-guard; D-11 adds `buffer_duration_changed`, so the FakePlayer needs the same Signal (parity edit lands in the same wave as the Player addition).

</code_context>

<specifics>
## Specific Ideas

- **Static bump magnitudes:** 30s / 20MB chosen specifically to cover the 7389ms YouTube worst case with ~3× headroom while keeping startup latency modest (single-step ~1–2s perceived delay before audio at first play). 60s rejected as overkill.
- **Adaptive schedule shape:** 30 → 60 → 120 (cap). Doubling each step, two growth steps total. Matches Phase 78 D-05's "2× then 4×" sketch mapped onto the new 30s baseline.
- **Adaptive reset:** Per-URL bind only. No app-launch persistence (Phase 78 D-Discretion holds).
- **Stats row visibility:** Always-visible (D-12), NOT adapted-only (Phase 78 D-08 default overridden). Reason: 30s baseline is itself a meaningful change worth surfacing.
- **Closure artifact:** `84-VERIFICATION.md` with explicit waived-gate language + 2-week monitor plan + follow-up trigger thresholds. NOT a silent commit + checkbox.
- **Monitor trigger thresholds for follow-up phase:** ≥3 long events (>1s) with `min_percent=0` in 2-week post-ship window, OR any `recovered` event >10s, OR ≥1 `cause_hint=network` event. Hitting any one opens a follow-up phase for reconnect-on-stall evaluation.

</specifics>

<deferred>
## Deferred Ideas

- **Reconnect-on-stall logic** — Phase 78 deferred; still deferred. Trigger to bring forward: D-13 monitor thresholds above. Sketch: when a cycle exceeds N seconds, force same-URL `set_state(NULL)` → `set_state(PLAYING)` instead of waiting for natural recovery.
- **`low-percent` / `high-percent` queue2 watermark tuning** — Phase 78 deferred; still deferred. Cheap follow-up if buffer-bump + adaptive isn't enough.
- **Per-station configurable buffer override** — Phase 78 rejected; not reopened. EditStationDialog field + `stations.buffer_seconds` column would add UI/data-model surface for a polish phase.
- **Synthetic throttled-network repro fixture** — Phase 62 / 78 deferred. Bring forward only if "ship + monitor" comes back inconclusive AND we need to reproduce specific conditions in CI.
- **Distinct `Reconnecting…` toast** — Phase 78 rejected; silent-recovery philosophy from Phase 62 holds.
- **In-app log viewer / hamburger "Show buffer events…"** — Phase 62 / 78 deferred. `cat ~/.local/share/musicstreamer/buffer-events.log` is sufficient.
- **TimedRotatingFileHandler (daily files)** — Phase 78 rejected; size rotation is more predictable.
- **Persistent cycle counter across app launches** — Phase 78 D-Discretion; file sink IS the persistent record.
- **ROADMAP.md entry harvest-summary amendment** — User chose to keep ROADMAP entry as-written and put corrections in this CONTEXT.md (`<data-summary>`). If a future onboarding audit complains, amend then.
- **Player.py legacy comment block freshening** ("HTTP audio sources silently ignored") — D-10 Claude Discretion item. Drive-by during this phase OR a future docs cleanup phase. Not load-bearing.
- **Watchdog cycle timeout that auto-forces failover** — Phase 62 rejected; Phase 78 / 84 hold the line. Reconnect-on-stall (deferred above) is the better path if needed.

</deferred>

---

*Phase: 84-bug-09-commit-b-buffer-tuning-behavior-fix-reframed-from-str*
*Context gathered: 2026-05-24*
*Phase 84 is Commit B of the Phase 78 two-stage plan; ships the buffer-tuning behavior fix under a "ship + monitor" reframe.*
