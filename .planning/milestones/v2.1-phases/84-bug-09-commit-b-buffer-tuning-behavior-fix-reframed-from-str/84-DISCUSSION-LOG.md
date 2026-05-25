# Phase 84: BUG-09 Commit B — buffer-tuning behavior fix (reframed) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 84-bug-09-commit-b-buffer-tuning-behavior-fix-reframed-from-str
**Areas discussed:** Roadmap framing correction, Bump value & scope, Adaptive growth ship-or-defer, Stats row + closure gate

---

## Area selection (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| Roadmap framing correction first | Log has 12 events / 5 long (2 YT + 3 SomaFM, not 3:1 YT). Correct framing before locking decisions. | ✓ |
| Bump value & scope | How much to bump BUFFER_DURATION_S; whether to touch BUFFER_SIZE_BYTES. | ✓ |
| Adaptive growth: ship or defer | D-05 adaptive 2x/4x growth with playbin3 mid-session-write dependency — ship or defer? | ✓ |
| Stats row + closure gate | D-08 row visibility post-adaptive choice; closure artifact for SC #3 behavior side. | ✓ |

**User's choice:** All four areas.

---

## Area 1 — Roadmap framing correction

| Option | Description | Selected |
|--------|-------------|----------|
| Reframe: both clusters | CONTEXT.md frames target as "both clusters" (YT worse magnitude, SomaFM higher count). | ✓ |
| Keep YouTube focus, note SomaFM | Roadmap framing stays; CONTEXT.md notes corrected split but tunes for YT magnitudes. | |
| Edit roadmap entry too | Same as "both clusters" AND amend ROADMAP.md Phase 84 entry's data summary. | |

**User's choice:** Reframe: both clusters (CONTEXT.md only; ROADMAP entry stays as-written).
**Notes:** Locked as D-09. The roadmap entry's "target the YouTube cluster" framing is superseded by this CONTEXT.md's `<data-summary>`. ROADMAP amendment deferred as a "if onboarding audit complains later" item.

---

## Area 2 — Bump value & scope

| Option | Description | Selected |
|--------|-------------|----------|
| 30s duration only | BUFFER_DURATION_S 10→30; leave size at 10MB. | |
| 20s duration only | BUFFER_DURATION_S 10→20; leave size at 10MB. Minimal bump. | |
| 30s duration + 20MB size | BUFFER_DURATION_S 10→30 AND BUFFER_SIZE_BYTES 10MB→20MB. Coordinated. | ✓ |
| 60s duration only | BUFFER_DURATION_S 10→60. Aggressive; ~3–6s startup latency. | |

**User's choice:** 30s duration + 20MB size.
**Notes:** Locked as D-10. 20MB size chosen so byte cap doesn't constrain duration target at high-bitrate FLAC sources (GBS.FM ≈ 1.4Mbps would hit 10MB before 30s). Player.py legacy comment about "HTTP audio sources silently ignored" flagged as misleading — drive-by freshen allowed.

---

## Area 3 — Adaptive growth: ship or defer

| Option | Description | Selected |
|--------|-------------|----------|
| Defer adaptive to follow-up | Static bump only this phase; adaptive becomes a Deferred Idea. | |
| Ship adaptive at session-bind only | New value at next `_try_next_stream` URL bind. Skips playbin3 mid-session research. | |
| Ship full adaptive (mid-session) | Full D-05 plan: 2x→4x via mid-session `set_property` writes. Research dependency stays. | ✓ |

**User's choice:** Ship full adaptive (mid-session).
**Notes:** Locked as D-11. Schedule clarified in follow-up question. Playbin3 mid-session-write research dependency is now a Phase 84 RESEARCH.md responsibility; fallback to URL-bind application if research shows mid-session writes don't take.

### Follow-up: Adaptive growth schedule

| Option | Description | Selected |
|--------|-------------|----------|
| 30 → 60 → 120 (cap) | 2× then 2× to cap. Three states total. | ✓ |
| 30 → 90 → 120 (cap) | Bigger first step (3×), fewer growth steps to ceiling. | |
| 30 → 60 only (no cap step) | Single growth step. Simpler logic. | |

**User's choice:** 30 → 60 → 120 (cap).
**Notes:** Two growth steps; resets to 30s on URL bind.

---

## Area 4 — Stats row + closure gate (asked as two questions)

### 4a — Stats row visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Adapted-only (D-08 as-spec'd) | Row hidden when at baseline; shown only after growth fires. | |
| Always show baseline + adapted state | Always-visible `Buffer: 30s` / `Buffer: 60s (adapted)` / `Buffer: 120s (adapted)`. | ✓ |
| Skip the row entirely | No row. Live state inferred from Underruns count + cooldown. | |

**User's choice:** Always show baseline + adapted state.
**Notes:** Locked as D-12. Phase 78 D-08 default ("adapted-only") explicitly overridden because the 30s baseline itself is a meaningful change from the long-standing 10s and worth surfacing up-front.

### 4b — Closure gate for BUG-09 SC #3

| Option | Description | Selected |
|--------|-------------|----------|
| VERIFICATION.md with waived gate + monitor plan | Full 78-style VERIFICATION.md; explicit gate-waiver + 2-week monitor plan + follow-up triggers. | ✓ |
| Lighter VERIFICATION + open follow-up criteria | Short VERIFICATION.md listing what to watch for next 2 weeks. | |
| Just commit + ROADMAP checkbox | No VERIFICATION.md; ship commit + roadmap checkbox closes SC #3. | |

**User's choice:** VERIFICATION.md with waived gate + monitor plan.
**Notes:** Locked as D-13. SC #3 (behavior side) closes on the Phase 84 ship commit; the 2-week monitor window is forward-looking guidance, not a closure prerequisite. Follow-up trigger thresholds defined in D-13.

---

## Claude's Discretion

Captured under `<decisions>` in CONTEXT.md:
- Counter Signal naming (`buffer_duration_changed` suggested, planner may alter).
- Growth-step counter location (`Player` vs `_BufferUnderrunTracker`).
- Player.py legacy comment freshening (drive-by allowed).
- Stats row exact label string (collision concerns with existing `Buffer` progressbar label).
- Reset granularity if research forces next-bind fallback (semantics of "second underrun → 120s" need adjustment if mid-session writes don't work).

## Deferred Ideas

Captured under `<deferred>` in CONTEXT.md. Carry-forward from Phase 78 plus:
- ROADMAP.md entry harvest-summary amendment (user chose CONTEXT.md-only correction).
- Reconnect-on-stall logic (D-13 monitor thresholds are the bring-forward trigger).
- Watermark tuning, per-station overrides, synthetic repro fixture, reconnect toast, in-app log viewer, TimedRotatingFileHandler, persistent counter, watchdog-cycle failover — all hold their Phase 62 / 78 deferred status.
