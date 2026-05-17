# Phase 78: Phase 62 follow-up — Buffer underrun behavior fix - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning (two-stage; see <domain>)

<domain>
## Phase Boundary

Phase 62 shipped the **instrumentation half** of BUG-09 (structured `buffer_underrun` log lines + cooldown-gated `Buffering…` toast). Phase 78 ships the **behavior fix half** and closes SC #3 ("a demonstrable reduction in dropout count under repro conditions"). Phase 16's baseline (`BUFFER_DURATION_S=10`, `BUFFER_SIZE_BYTES=10MB`) is unlocked here per Phase 62 D-09 — any change in this phase must be logged as a decision below.

**Two-stage phase** (locked, D-01):

1. **Commit A — harvest infra (ship immediately).** Add a `RotatingFileHandler` to the `musicstreamer.player` logger so `buffer_underrun` lines also land at `~/.local/share/musicstreamer/buffer-events.log` regardless of launch context (terminal vs `.desktop`). Also promote Phase 62 D-Discretion #5 — expose `_underrun_event_count` in the stats-for-nerds row so cycle counts are observable live without grepping the file. Stop after this commit. User runs the app under daily-use conditions for **~1 week** to accumulate samples.

2. **Commit B — behavior fix (after harvest week).** Reopen `78-CONTEXT.md`, append a `<data-summary>` block (baseline N, duration distribution, outcome breakdown, station/codec patterns), then plan + ship the actual buffer-tuning fix per the directional preferences captured below.

The two commits ship in two distinct planning passes. Commit A's plans are written now; Commit B's plans are written **after** the harvest week.

**In scope (Commit A — ship now):**

- **File sink** — Add `RotatingFileHandler(buffer-events.log, maxBytes=1MB, backupCount=3)` to the `musicstreamer.player` logger only. Existing `logging.basicConfig(level=WARNING)` in `__main__.py:222` stays exactly as-is (Pitfall 5 invariant from Phase 62). Other modules' stderr behavior unchanged. Format is the same Phase 62 D-02 line — file gets the structured `buffer_underrun start_ts=… end_ts=… duration_ms=… min_percent=… station_id=… station_name=… url=… outcome=… cause_hint=…` line and nothing else.
- **Path** — `~/.local/share/musicstreamer/buffer-events.log` via `musicstreamer.paths` (mirror the existing `cookies_path()` pattern). Parent dir already exists (DATA_DIR creation site).
- **`_underrun_event_count` row in stats-for-nerds** — Promote the Phase 62 D-Discretion deferred item. Increment counter inside `_on_underrun_cycle_closed` slot; expose `Underruns: {N}` row via `form.addRow(...)` at `now_playing_panel.py:2478` (after the existing `Buffer` progressbar row). Hidden by default, hamburger-toggle as today.
- **Tests** — Unit test asserts the RotatingFileHandler is attached to `musicstreamer.player`, points at the expected path, and uses the same format spec as the existing stderr formatter (i.e. one full `buffer_underrun` line per event reaches the file). Unit test asserts `_underrun_event_count` increments by 1 per `cycle_closed` slot call across all outcomes (`recovered`/`failover`/`stop`/`pause`/`shutdown`). UI test asserts the new stats-for-nerds row appears when the toggle is on and shows the current count.

**In scope (Commit B — ship after harvest, planned later):**

- **Buffer-duration bump (primary lever, D-04).** Apply chosen post-harvest value (likely 20–60s based on observed pattern) to `BUFFER_DURATION_S` in `constants.py`. Phase 16 D-09 invariant explicitly waived for this phase; rationale logged here with data citation.
- **Adaptive growth (D-05, directional).** First in-session underrun → bump live to 2×. Second → 4×. Cap at 120s. Resets on station-change (existing `_try_next_stream` per-URL state reset is the natural hook). **Research dependency:** verify playbin3 honors mid-session `buffer-duration` property writes; if not, degrade to "new value applies at next URL bind in `_try_next_stream`" (still adaptive, session-boundary granularity).
- **`Buffer config: Xs (adapted)` row in stats-for-nerds.** Only shown when the live value differs from the static default. Same `form.addRow` site.
- **Validation gate (D-06).** Compare `cycle_close` counts from harvest-week log against post-fix-week log. Split on `start_ts` against the fix-ship timestamp. Closure gate = M < N AND median `duration_ms` lower. Numbers committed to `78-VERIFICATION.md`.

**Out of scope (deferred):**

- **Reconnect-on-stall logic** — explicitly deferred (D-04 picked buffer-bump as the cheapest first lever). If post-fix data shows long-cycle `recovered` events (>10s with low `min_percent`) still happening, reconnect lands in a follow-up phase.
- **Low-percent / high-percent queue2 watermark tweaks** — explicitly deferred (same reason). Cheap to revisit if buffer-bump alone isn't sufficient.
- **Per-station configurable buffer override** — rejected (D-05). Adds UI/data-model surface for a polish phase; the adaptive growth covers the realistic asymmetry across stations.
- **Synthetic throttled-network repro fixture** — Phase 62 deferred section flagged this as "may be needed for the follow-up behavior-fix phase". User picked real-world A/B over synthetic, so the fixture stays deferred. Revisit only if real-world A/B is inconclusive.
- **Distinct `Reconnecting…` toast** — rejected (D-07). Phase 62's silent-recovery philosophy holds; adaptive growth happens invisibly with only the existing `Buffering…` toast as user-visible signal.
- **Wider `musicstreamer.*` capture in the file sink** — rejected (D-02). Sink scoped to `musicstreamer.player` only; grep noise from `yt_import` / `soma_import` / etc. would dilute the diagnostic signal.
- **In-app log viewer / hamburger "Show buffer events…"** — Phase 62 deferred; not promoted here. File sink is enough.
- **TimedRotatingFileHandler (daily files)** — rejected (D-02). Size-based rotation (1MB × 3) keeps disk footprint predictable; date-splitting for analysis works off `start_ts` in each line.

</domain>

<decisions>
## Implementation Decisions

### Phase shape

- **D-01:** **Two-stage phase, single CONTEXT.md.** Commit A ships harvest infra (file sink + cycle counter) now; Commit B ships the actual buffer fix after a ~1-week harvest. Both commits live under Phase 78; we do NOT split into Phase 78 + 78.1. Why: keeps BUG-09 SC #3 closure inside one ROADMAP entry, and the harvest infra has zero standalone value — it only exists to inform the fix. Update CONTEXT.md with a `<data-summary>` block before Commit B planning starts.

### File sink (Commit A)

- **D-02:** **Rotating file, dedicated logger, stderr untouched.** `RotatingFileHandler(maxBytes=1_048_576, backupCount=3)` attached to the `musicstreamer.player` logger (NOT `musicstreamer.*`). Existing `logging.basicConfig(level=WARNING)` preserved verbatim per Phase 62 Pitfall 5. Format = the same `_log.info("buffer_underrun start_ts=%.3f …")` line Phase 62 already emits — file handler installs the same `logging.Formatter` to keep grep parity. Rejected: TimedRotatingFileHandler (predictable disk cap is more useful than predictable filenames); wider `musicstreamer.*` capture (would dilute signal with yt_import / soma_import lines).
- **D-03:** **Path = `~/.local/share/musicstreamer/buffer-events.log`** via `musicstreamer.paths` (new helper `buffer_events_log_path()` mirroring `cookies_path()` at `paths.py`). Parent dir is the existing DATA_DIR; no new mkdir needed. Permissions: default (no 0o600 wrap — this is diagnostic data, not credentials, and we want easy `cat` / `grep` from a terminal).

### Behavior fix levers (Commit B, directional)

- **D-04:** **Bump BUFFER_DURATION_S / BUFFER_SIZE_BYTES first.** Cheapest lever — single change in `constants.py`. Picked over reconnect logic and watermark tweaks because (a) data-pending, (b) low code-churn risk, (c) preserves Phase 16's single-knob philosophy. If post-fix data shows it's insufficient, reconnect / watermark tweaks land in a follow-up phase. **Exact bump value picked from harvest data**, not preset here — likely 20–60s range. Phase 16 D-09 invariant waived for this phase; rationale documented in Commit B's CONTEXT.md update.
- **D-05:** **Adaptive growth on repeated underruns (preferred).** First in-session `cycle_close` → bump live to 2× (e.g. 10→20s). Second → 4× (40s). Cap at 120s. Resets to baseline on `_try_next_stream` (URL bind site — mirrors Phase 47.1 D-14 sentinel-reset pattern and Phase 62 D-04 arm-state reset). **Research dependency for the planner:** verify playbin3 actually honors mid-session writes to `buffer-duration` and `buffer-size`. If not, degrade gracefully — new value applies at next URL bind in `_try_next_stream`, NOT mid-stream. Still adaptive, just at session/station-boundary granularity. Rejected: static aggressive bump (no diagnostic signal when default-is-fine cases exist); per-station configurable (too much UI surface for a polish phase).
- **D-06:** **Validation via real-world A/B from log counts.** Baseline N = cycle_close events in harvest-week log; post-fix M = same in the week after Commit B ships. Closure gate = `M < N` AND median `duration_ms` lower in post-fix window. Split on `start_ts` against the fix-ship wall-clock timestamp; both weeks may live in the same rotating file. Numbers committed to `78-VERIFICATION.md`. No synthetic fixture, no CI gate beyond the unit tests in D-08.

### Recovery UX (Commit A + B)

- **D-07:** **Toast-only stays.** Phase 62's `Buffering…` toast (1.5s dwell + 10s cooldown) remains the only user-visible signal during recovery. Adaptive growth is silent. Rejected: distinct `Reconnecting…` toast (noisier UX for marginal benefit; would also imply reconnect logic which is out-of-scope).
- **D-08:** **Stats-for-nerds rows.** Add to `_build_stats_widget` at `now_playing_panel.py:2478` (after the existing `Buffer` progressbar row, before `wrapper.setVisible(False)`):
  - **Commit A:** `Underruns: {N}` — driven by a new Player `Signal(int)` (or extend an existing one) emitted from `_on_underrun_cycle_closed`. The counter increments on every `cycle_close` regardless of outcome (mirrors the file-sink semantics).
  - **Commit B:** `Buffer config: Xs (adapted)` — only visible when the live `_current_buffer_duration_s` differs from `BUFFER_DURATION_S`. Hidden when equal so the row doesn't shout "I'm always there".
  Both rows use the existing `_MutedLabel` pattern (Phase 47.1 D-10) and inherit the hamburger-toggle visibility from the `_stats_widget` parent.

### Claude's Discretion

- **Counter signal vs. expose on existing one.** D-08 says "new `Signal(int)` or extend existing". Planner picks — bias toward adding a new typed Signal (`underrun_count_changed = Signal(int)`) for clarity. The deferred Phase 62 D-Discretion mention permits either.
- **Adaptive growth schedule exact numbers.** D-05 sketches 2× → 4× → cap-at-120s. The actual schedule (linear vs exponential, step count, cap value) gets fine-tuned from harvest data in Commit B's CONTEXT.md update. Don't lock numbers here.
- **File log retention beyond 3 backups.** D-02 picks 3. If harvest week shows you blow past 3MB total, planner may bump `backupCount` — note in Commit B CONTEXT update if so.
- **Pre-existing file at first launch with sink.** No migration concern — the handler creates the file on first emit. No need to `touch` it at install time.
- **Stats row ordering.** D-08 says "after the existing `Buffer` progressbar row". Planner is free to reorder if a different visual layout looks better.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 62 (this is the follow-up; carry-forward is mandatory)
- `.planning/phases/62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt/62-CONTEXT.md` — D-01..D-09 (instrumentation surface), D-09 Phase 16 invariant (UNLOCKED for Phase 78 — must log rationale), `<deferred>` section item #1 (behavior fix) and #3 (file-based log sink — promoted to scope here).
- `.planning/phases/62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt/62-VERIFICATION.md` — Phase 62 closure record. SC #1, #2, #4 verified; SC #3 explicitly deferred. Phase 78 closes SC #3.
- `.planning/phases/62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt/62-RESEARCH.md` — GStreamer queue2 / playbin3 buffering background. Re-read by planner for Commit B research on mid-session property writes.

### Player / GStreamer surface
- `musicstreamer/player.py` — `_BufferUnderrunTracker` class (line 111), `_CycleClose` dataclass (line 92), `_log = logging.getLogger(__name__)` (line 77), `_on_gst_buffering` (line 703), `_on_underrun_cycle_opened/_closed/_dwell_elapsed` slots (lines 909, 918, 936), `_try_next_stream` per-URL reset site (line 962), `BUFFER_DURATION_S` / `BUFFER_SIZE_BYTES` apply sites (lines 298–299). The pipeline construction sets `flags | 0x100` to enable `GST_PLAY_FLAG_BUFFERING` so the buffer constants are actually honored (line 305 + the 4-line comment block above it — DO NOT regress).
- `musicstreamer/constants.py` lines 54–56 — `BUFFER_DURATION_S = 10` and `BUFFER_SIZE_BYTES = 10 * 1024 * 1024`. Phase 16 / STREAM-01 baseline. Phase 78 D-04 unlocks these; Commit B's CONTEXT.md update logs the exact new values.
- `musicstreamer/__main__.py:222–226` — `logging.basicConfig(level=logging.WARNING)` (line 222) MUST remain verbatim. `logging.getLogger("musicstreamer.player").setLevel(logging.INFO)` (line 226) — already escalates the player logger to INFO so the file sink will receive events. Phase 78 Commit A adds the file handler at this same wiring site (or a near sibling).

### Paths / data dir
- `musicstreamer/paths.py` — `data_dir()`, `cookies_path()`, `db_path()` pattern for adding `buffer_events_log_path()`. Returns `Path(data_dir()) / "buffer-events.log"`.
- `musicstreamer/constants.py` PEP 562 `__getattr__` shim — if any code wants `BUFFER_EVENTS_LOG_PATH` via the constants module, add a delegating branch here (mirrors `DATA_DIR`, `DB_PATH`). Skip if not needed.

### Stats-for-nerds row (D-08)
- `musicstreamer/ui_qt/now_playing_panel.py` — `_build_stats_widget` at line 2451; `form.addRow(_MutedLabel("Buffer", …), value_row)` at line 2478 is the row-add anchor. `_MutedLabel` (Phase 47.1 D-10) handles theme-flip readability.
- `musicstreamer/ui_qt/main_window.py:294–295` — queued `underrun_recovery_started.connect(...)` pattern is the template for the new `underrun_count_changed` Signal (D-08 + Claude Discretion).

### Threading / bus-handler pitfalls (Phase 62 mandatory carry-forward)
- `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` — Pitfall 2 (bus-loop thread has no Qt event loop — must use queued Signals) still binds for the new count-changed Signal and any mid-session property write into playbin3.
- Phase 62 D-Discretion / Pitfall 5 — `__main__.py` MUST keep `basicConfig(WARNING)` global; only per-logger escalations are allowed. File handler installation must NOT change root-logger level.

### Phase 16 (Phase 78 D-04 unlocks this baseline)
- `.planning/milestones/v1.4-ROADMAP.md` — Phase 16 STREAM-01 rationale (10s / 10MB baseline). Phase 78 Commit B's CONTEXT.md update will cite this with the post-harvest decision.

### Phase 47.1 (UI patterns we extend)
- `.planning/milestones/v2.0-phases/47.1-stats-for-nerds-buffer-indicator/47.1-CONTEXT.md` — `_stats_widget` extensibility pattern (QFormLayout `addRow`), `_MutedLabel` theme-responsive label, hamburger toggle wiring (D-05 default-hidden).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`_log = logging.getLogger("musicstreamer.player")`** (player.py:77) — Phase 62 already wired the logger; file handler attaches to the same logger object. Zero new logging plumbing.
- **`_on_underrun_cycle_closed` slot** (player.py:918) — already runs on the main thread, already receives the immutable `_CycleClose` record. Counter increment + new `Signal(int).emit(self._underrun_event_count)` lands here, one line each.
- **`_build_stats_widget` + `form.addRow(...)`** (now_playing_panel.py:2451 / 2478) — Phase 47.1 designed the form to be extensible. Two new rows = two new `form.addRow` calls inside the same builder, before the trailing `wrapper.setVisible(False)`.
- **`_MutedLabel`** — Theme-responsive label that re-applies its muted color on palette flips. New rows use it directly.
- **Phase 62 D-Discretion `_underrun_event_count` notion** — Phase 62 mentioned the field as optional; Phase 78 makes it real. No conflict with prior decision.
- **`musicstreamer.paths.data_dir()`** — DATA_DIR resolver. `buffer_events_log_path()` is one helper mirroring `cookies_path()` shape.

### Established Patterns

- **Per-logger level escalation, root-logger preserved at WARNING** — Phase 62 / Pitfall 5. The file handler attaches via `_log.addHandler(...)`; root logger's level is irrelevant for the per-logger-INFO path. NO `basicConfig` mutation.
- **Bound-method Signal.connect (QA-05)** — no lambdas. Any new `underrun_count_changed.connect(self._on_underrun_count_changed)` follows this.
- **Queued Signals for cross-thread marshalling** — Phase 62 Pitfall 2. The new count-changed Signal emits on the main thread (from the existing `_on_underrun_cycle_closed` slot), so `DirectConnection` is acceptable — but document it explicitly to dispel ambiguity.
- **Per-URL state reset inside `_try_next_stream`** — Phase 47.1 D-14, Phase 62 D-04. Commit B's adaptive-growth reset attaches at the same site (line 962-ish, alongside `_last_buffer_percent = -1` and `_underrun_armed = False`).

### Integration Points

- **Commit A:**
  - `musicstreamer/__main__.py:222–226` (near the existing `setLevel(INFO)` call) — attach the `RotatingFileHandler` to the `musicstreamer.player` logger. Single block of ~6 lines: handler construction, formatter, `addHandler`.
  - `musicstreamer/paths.py` — add `buffer_events_log_path()` helper. ~3 lines.
  - `musicstreamer/player.py` — instance field `self._underrun_event_count: int = 0` in `__init__`; new `Signal(int)` declaration near the existing `underrun_recovery_started`; increment + emit in `_on_underrun_cycle_closed`. ~4 net lines.
  - `musicstreamer/ui_qt/now_playing_panel.py` — new `_MutedLabel("Underruns")` row in `_build_stats_widget`; `set_underrun_count(int)` setter slot; connection wiring lives in `MainWindow` per the existing `buffer_percent` pattern.
  - `musicstreamer/ui_qt/main_window.py` — one new `.connect(...)` call alongside the existing `buffer_percent` and `underrun_recovery_started` wirings (~line 294).

- **Commit B (planned later):**
  - `musicstreamer/constants.py:54–56` — chosen post-harvest values.
  - `musicstreamer/player.py` — `self._current_buffer_duration_s: int = BUFFER_DURATION_S` + `_grow_buffer_on_underrun()` method called from `_on_underrun_cycle_closed`; pipeline property writes via `self._pipeline.set_property("buffer-duration", self._current_buffer_duration_s * Gst.SECOND)`; reset hook inside `_try_next_stream`. **Research dependency** D-05 controls whether the write is mid-stream or at next URL bind.
  - `musicstreamer/ui_qt/now_playing_panel.py` — second new row (`Buffer config: Xs (adapted)`).

</code_context>

<specifics>
## Specific Ideas

- **Harvest week duration:** ~1 week of daily use. Not a hard gate — if the user accumulates enough samples in 3 days they can reopen earlier; if a week is light, extend. The CONTEXT update before Commit B is the trigger, not a calendar date.
- **File-sink format string:** byte-for-byte the same as the existing stderr line. Reuse the same `logging.Formatter` instance if convenient, or instantiate a separate one with the matching `fmt=` string. Grep parity with stderr captures is the goal.
- **Counter semantics:** every `cycle_close` increments — including `failover`, `stop`, `pause`, `shutdown`, not just `recovered`. Same semantics as the file sink (one line per cycle_close). The stats row displays whatever cumulative number the session has reached; resets at app launch (no persistence).
- **Adaptive growth sketch (directional only):** 10s → 20s → 40s → 80s → 120s (cap). Or 10s → 30s → 90s → 120s. Or 10s → 60s → 120s. Real schedule picked in Commit B with harvest data in hand.
- **`Buffer config:` row visibility:** invisible when `_current_buffer_duration_s == BUFFER_DURATION_S`. Shown only after the first growth step in a session. Matches the "I'm doing something different" affordance the user wants.

</specifics>

<deferred>
## Deferred Ideas

- **Reconnect-on-stall logic** — D-04 picked buffer-bump as the first lever. If Commit B's post-fix logs show long-cycle `recovered` events (>10s, low `min_percent`) persisting, reconnect lands in a new phase. Sketch: when a cycle exceeds N seconds, force same-URL `set_state(NULL)` → `set_state(PLAYING)` instead of waiting for natural recovery.
- **`low-percent` / `high-percent` queue2 watermark tuning** — D-04 deferred. Cheap follow-up if buffer-bump alone underperforms. Default 1% / 99% → tightening to e.g. 5% / 50% means earlier rebuffer trigger + earlier resume.
- **Per-station configurable buffer override** — rejected during discussion. EditStationDialog field + `stations.buffer_seconds` column. Revisit only if the dropout pattern is per-station asymmetric to a degree the adaptive growth can't smooth out.
- **Synthetic throttled-network repro fixture** — Phase 62 deferred; D-06 keeps it deferred. `tc qdisc netem rate=… loss=…` against a local nginx serving a known stream. Bring forward only if the real-world A/B validation comes back inconclusive.
- **Distinct `Reconnecting…` toast** — rejected (D-07). Silent recovery philosophy from Phase 62 holds; reconnect logic itself is out-of-scope, so the toast question is moot.
- **In-app log viewer / hamburger "Show buffer events…"** — Phase 62 deferred; not promoted. File sink + `cat ~/.local/share/musicstreamer/buffer-events.log` is sufficient.
- **Wider `musicstreamer.*` capture in the file sink** — rejected (D-02). Sink intentionally scoped to `musicstreamer.player` only.
- **TimedRotatingFileHandler (daily files)** — rejected (D-02). Size rotation gives a predictable disk cap; per-event `start_ts` already supports date-based analysis.
- **Persistent cycle counter across app launches** — counter resets per launch (D-Discretion); persistence would need a SQLite column or settings entry for marginal benefit. File sink is the persistent record.
- **Watchdog cycle timeout that auto-forces failover** — Phase 62 explicitly rejected; Phase 78 holds the line. Reconnect-on-stall (deferred above) is the better path if needed.

</deferred>

---

*Phase: 78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug*
*Context gathered: 2026-05-17*
*Two-stage phase: Commit A (harvest infra) plans now; Commit B (behavior fix) CONTEXT.md update + plans after ~1 week of accumulated samples.*
