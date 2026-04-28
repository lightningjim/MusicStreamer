# Phase 52: EQ Toggle Dropout Fix - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 52-eq-toggle-dropout-fix
**Areas discussed:** Repro & characterization, Fix approach, Re-toggle behavior

---

## Repro & characterization — Symptom direction

| Option | Description | Selected |
|--------|-------------|----------|
| Brief click or pop (≈10–50ms artifact) | Short transient — vinyl-click-like. IIR coefficient discontinuity signature; fix is gain smoothing. | ✓ |
| Brief silence / gap (≥100ms) | Audio cuts to silence then resumes. Suggests pipeline state transition or buffer underrun. | |
| Stutter / glitch | Audio fragment repeats or skips. Streaming thread missed buffer deadline. | |
| Level jump | Sudden volume change without smoothing — perceptible even without click. | |

**User's choice:** Brief click or pop (≈10–50ms artifact)
**Notes:** Matches the IIR coefficient-discontinuity hypothesis exactly.

---

## Repro & characterization — Direction symmetry

| Option | Description | Selected |
|--------|-------------|----------|
| Both directions | Clicking on AND off both produce a click. Symmetric — confirms gain transition itself is the cause. | ✓ |
| Only toggle-off | EQ active → bypass clicks; toggle-on does not. | |
| Only toggle-on | Bypass → EQ active clicks; toggle-off does not. | |
| Inconsistent / not sure | Hard to characterize; treat as 'both'. | |

**User's choice:** Both directions
**Notes:** Fix must handle both directions symmetrically.

---

## Fix approach

| Option | Description | Selected |
|--------|-------------|----------|
| Smooth gain ramping | QTimer-driven interpolation: ramp band gains over 30–50ms in 5ms ticks. Filter coefficients change incrementally instead of jumping. No volume dip. | ✓ |
| Soft-mute envelope | Briefly attenuate volume around the gain switch (~10ms ramp down, switch, ~10ms ramp up). Simpler code; user perceives brief volume dip instead of click. | |
| Investigate first | Add instrumentation, log warnings, capture buffer timing. Fix once root cause is observable. | |

**User's choice:** Smooth gain ramping (Recommended)
**Notes:** 8 ticks × 5ms = 40ms. Lerp each band's gain from current to target. Final tick commits exact target.

---

## Re-toggle behavior (rapid double-click)

| Option | Description | Selected |
|--------|-------------|----------|
| Reverse from current point | Capture current in-progress gains as new start, set new target, ramp from there. Smooth reversal, no click. | ✓ |
| Snap-then-restart | Cancel running ramp, snap to its target instantly (clicks!), then start fresh ramp toward new target. | |
| Ignore re-toggle until ramp completes | Disable toggle button during ramp. Adds ~40ms unresponsive UX. | |

**User's choice:** Reverse from current point
**Notes:** Captures intermediate gain state as the new ramp start. Maintains the no-click guarantee even on rapid clicks.

---

## Claude's Discretion

- Acceptance bar interpretation: UAT pass = Kyle clicks 10× rapidly with no audible artifacts.
- SC #3 (toggle fires exactly once per click): wiring is already clean (only `clicked` is connected). Defensive test recommended; no behavior change needed.
- Ramp timer attribute name and constant naming/location.
- Whether to lerp gain in dB-linear (recommended for simplicity) or linear-amplitude.
- Whether to add a unit test asserting per-tick gain progression.
- Early-exit conditions for the ramp (e.g., when `_eq is None` or `_eq_profile is None`).

## Deferred Ideas

- Smoothing the profile-change path (`set_eq_profile` → `_rebuild_eq_element`) which does a `READY`-state pipeline transition.
- Smoothing the preamp-slider drag path.
- Replacing `equalizer-nbands` element entirely.
- Moving SQLite write off the GUI thread (confirmed not the cause of audio dropout).
- Disabling the toggle button during ramp (explicitly rejected in favor of reverse-from-current).
