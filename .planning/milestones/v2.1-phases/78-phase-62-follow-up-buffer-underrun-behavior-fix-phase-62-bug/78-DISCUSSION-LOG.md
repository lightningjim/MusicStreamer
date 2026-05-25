# Phase 78: Phase 62 follow-up — Buffer underrun behavior fix - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug
**Areas discussed:** Root-cause evidence, Fix scope (which levers), Validation for SC #3, Recovery UX surface

---

## Root-cause evidence

### Q1 — Log data available?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — I have stderr captures | Real `buffer_underrun` lines from terminal runs | |
| No, but I've observed patterns informally | Empirical hunches without log data | |
| No — I haven't been running from terminal | Daily-use via `.desktop`; no log data exists | ✓ |
| Skip — build a synthetic repro instead | Throttled-network fixture, real-world later | |

**User's choice:** No log data. Daily-use is `.desktop`-launched; Phase 62's stderr instrumentation never landed anywhere captureable.

### Q2 — Harvest plan

| Option | Description | Selected |
|--------|-------------|----------|
| Add a file sink, run a week, then plan fix | Two-commit phase: harvest infra first, behavior fix second | ✓ |
| Synthetic repro fixture only — ship now | Build the deferred `tc netem` fixture, skip waiting | |
| Split into two phases | 78 = harvest only; new 78.1 = fix | |
| Run from terminal, no code change, then plan | Manual stderr capture for a week, no new code | |

**User's choice:** Two-stage Phase 78 with file sink shipped first.
**Notes:** Phase 62 deferred the file-based log sink. This phase promotes it as the harvest mechanism, then resumes for the actual fix once samples accumulate.

---

## Fix scope (which levers)

### Q1 — File-sink mechanics (Commit A immediate-ship)

| Option | Description | Selected |
|--------|-------------|----------|
| Rotating file, dedicated logger, stderr untouched | RotatingFileHandler on `musicstreamer.player` only; basicConfig stays WARNING | ✓ |
| Rotating file, all `musicstreamer.*` loggers | Wider capture, noisier file | |
| Daily file, no rotation by size | TimedRotatingFileHandler, keep 7 days | |

**User's choice:** Rotating file, dedicated logger, stderr untouched.
**Notes:** Phase 62 Pitfall 5 invariant preserved — root logger's WARNING level is not changed. File sink scoped narrowly to keep diagnostic signal clean.

### Q2 — Fix lever (Commit B, directional)

| Option | Description | Selected |
|--------|-------------|----------|
| Bump buffer-duration / buffer-size first | Cheapest single-knob lever | ✓ |
| Low-watermark threshold first | queue2 low-percent / high-percent tweaks | |
| Reconnect-on-stall logic | Force same-URL reconnect after N seconds | |
| Wait for data, no preconception | No directional commitment | |

**User's choice:** Bump buffer-duration / buffer-size first.
**Notes:** Reconnect logic and watermark tweaks stay deferred; revisit if buffer-bump alone underperforms.

### Q3 — Bump style

| Option | Description | Selected |
|--------|-------------|----------|
| Static, modest bump (10s → 20s) | Single hardcoded value, 1.5–2× | |
| Static, aggressive (10s → 60s) | Big single bump, trade startup latency for resilience | |
| Adaptive: start at 10s, grow on repeated underruns | 2× → 4×, cap at 120s, reset per station | ✓ |
| Per-station configurable | EditStationDialog field + stations.buffer_seconds column | |

**User's choice:** Adaptive growth.
**Notes:** Research dependency flagged — playbin3 may not honor mid-session `buffer-duration` writes. If not, degrade gracefully to "new value applies at next URL bind" (still adaptive, session-boundary granularity).

---

## Validation for SC #3

### Q1 — Validation strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Real-world A/B using harvested log counts | Baseline week vs post-fix week from file sink | ✓ |
| Synthetic repro fixture as hard gate | `tc netem` + nginx, CI-stable | |
| Unit-test the lever, real-world for the SC | Two-tier: cheap unit gate + live-data SC | |
| Skip CI validation, trust live UAT only | No automated SC test | |

**User's choice:** Real-world A/B using harvested log counts.
**Notes:** Phase 62's `start_ts` field timestamps each event, so the post-fix and harvest weeks can live in the same rotating file and be split on wall-clock time for analysis. No synthetic fixture needed; the deferred-from-Phase-62 fixture stays deferred.

---

## Recovery UX surface

### Q1 — Adaptive UX

| Option | Description | Selected |
|--------|-------------|----------|
| Nothing — stay toast-only with `Buffering…` | Adaptive growth happens silently | |
| Expose adaptive state in stats-for-nerds | New `Underruns: N` + `Buffer: 20s (adapted)` rows | ✓ |
| Distinct toast on adaptive bump | New `Increasing buffer…` toast | |
| Just the counter, no buffer-value row | `Underruns: N` only | |

**User's choice:** Expose adaptive state in stats-for-nerds.
**Notes:** Two rows added to the existing `_build_stats_widget` QFormLayout (Phase 47.1 extensibility pattern). Counter row ships in Commit A (live during harvest week); buffer-value row ships in Commit B with the adaptive logic. Counter visible whenever stats-for-nerds is toggled on; buffer-value row only when live value differs from default.

---

## Claude's Discretion

- Counter signal name (`underrun_count_changed` vs extending an existing Signal) — planner picks; bias toward new typed Signal for clarity.
- Adaptive growth schedule exact numbers (linear vs exponential, step count, cap value) — chosen in Commit B with harvest data in hand. Sketch in `<specifics>` is directional only.
- `RotatingFileHandler` `backupCount` (currently 3) — planner may revise if harvest week shows the cap is too tight.
- File first-launch creation (handler creates on first emit, no `touch` at install).
- Stats row layout order (planner may reorder if a different visual layout looks cleaner).

## Deferred Ideas

- **Reconnect-on-stall logic** — buffer-bump (D-04) is the first lever; reconnect lands in a follow-up if buffer-bump underperforms.
- **`low-percent` / `high-percent` queue2 watermark tuning** — same; cheap follow-up if needed.
- **Per-station configurable buffer override** — rejected as overkill for a polish phase.
- **Synthetic throttled-network repro fixture** — Phase 62 deferred; D-06 keeps it deferred. Revisit only if real-world A/B is inconclusive.
- **Distinct `Reconnecting…` toast** — rejected; reconnect is out-of-scope and the toast question is moot.
- **In-app log viewer** — Phase 62 deferred; file sink + `cat`/`grep` is sufficient.
- **Wider `musicstreamer.*` capture** — rejected; signal dilution.
- **TimedRotatingFileHandler (daily files)** — rejected in favor of size-based rotation.
- **Persistent cycle counter across launches** — counter resets per session; file sink is the persistent record.
- **Watchdog cycle timeout auto-failover** — Phase 62 explicit reject; Phase 78 holds the line.
