# Phase 57: Windows Audio Glitch + Test Fix - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 57-windows-audio-glitch-test-fix
**Areas discussed:** Volume on Windows, WIN-03 verification scope

---

## Gray-Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Pause/resume idiom | Stay with NULL→PLAYING rebuild + smoothing vs switch to Gst.State.READY soft pause | |
| Volume on Windows | Re-apply volume after NULL transition vs explicit `volume` element in playbin3.audio-filter | ✓ |
| WIN-03 verification scope | VM UAT only vs VM UAT + Linux CI guard vs VM UAT + diagnostic log doc | ✓ |
| WIN-04 fix scope | Minimal AsyncMock patch on store_async vs harden all of _build_winrt_stubs | |

**User's selection:** Volume on Windows + WIN-03 verification scope. Other two areas routed to Claude's discretion (default: NULL stays, minimal AsyncMock patch).

---

## Volume on Windows

| Option | Description | Selected |
|--------|-------------|----------|
| Diagnose first on VM | Phase 56 pattern — readback session before picking A or B | ✓ |
| Try A first (re-apply after NULL) | One-line fix at end of _set_uri | |
| Go straight to B (volume element) | Explicit `volume` element in playbin3.audio-filter | |
| You decide | Claude picks | |

**User's choice:** Diagnose first on VM.
**Notes:** User wants evidence-driven fix selection, mirroring Phase 56's diagnostic-first cadence. Captured in CONTEXT.md as D-01 / D-04 / D-06.

### Diagnostic Evidence Set

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal evidence set | 3 readbacks: sink identity, playbin3.volume across NULL→PLAYING, slider effect mid-stream | ✓ |
| Above + sink-internal volume | Adds 4th readback on the sink's internal volume property | |
| You decide | Claude picks | |

**User's choice:** Minimal evidence set.
**Notes:** Three readbacks are enough to disambiguate Option A (re-apply) from Option B (`volume` element). Captured as D-04.

---

## WIN-03 Verification Scope

| Option | Description | Selected |
|--------|-------------|----------|
| VM UAT only | Mirror Phase 56 D-11; perceptual + slider both verified on Win11 VM | |
| VM UAT + Linux CI guard | Adds a Linux pytest asserting volume survives a NULL→PLAYING rebuild | ✓ |
| VM UAT + diagnostic log doc | VM UAT plus 57-DIAGNOSTIC-LOG.md; no new pytest | |
| You decide | Claude picks | |

**User's choice:** VM UAT + Linux CI guard.
**Notes:** Catches future regressions (contributor adds another `set_state(NULL)` site and forgets to re-apply volume) without needing a Windows CI runner. Captured as D-07. Diagnostic log artifact is also kept (D-05) — the choice was about adding a CI guard, not removing the log.

---

## Claude's Discretion

- **Pause/resume audible-glitch fix mechanism.** User did not select this gray area; planner picks the smoothing approach (sink-volume mute window, `playbin3.volume`-side fade, or `volume`-element ramp) after the diagnostic identifies the actual sink + after WIN-03 volume picks Option A or B. Captured as a "Claude's Discretion" entry in CONTEXT.md.
- **WIN-04 fix scope.** User did not select; default is minimal — replace MagicMock with AsyncMock for `DataWriter().store_async` only, no audit of `_build_winrt_stubs`. Captured as D-08 / D-09 / D-10.
- **Diagnostic log location** — `57-DIAGNOSTIC-LOG.md` next to CONTEXT.md proposed; planner can adjust per-plan if better.
- **AsyncMock import location** — top-of-file or inline; planner picks per existing conventions.

## Deferred Ideas

- **Refactor `pause()` to use `Gst.State.READY`** — out of scope; lighter teardown might avoid the glitch but changes Linux behavior. Re-visit only if smoothing wrapper proves insufficient.
- **Audit all of `_build_winrt_stubs`** for awaitable winrt methods — out of scope per D-09. Future async methods get AsyncMock as they're added.
- **Switch Windows audio sink** — out of scope per Phase 43; diagnostic only reads current sink.
- **Windows CI runner** — would catch the bug natively, but no CI matrix planned for this personal project.
