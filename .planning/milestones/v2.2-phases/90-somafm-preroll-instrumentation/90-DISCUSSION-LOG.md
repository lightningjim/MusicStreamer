# Phase 90: SomaFM Preroll Instrumentation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-18
**Phase:** 90-somafm-preroll-instrumentation
**Areas discussed:** Phase scope (post-verification), Re-fetch design, Preroll selection behavior

---

## Pre-discussion verification (drove the reframe)

User flagged at invocation: *"This might have been fully fixed between me creating
this and now incidentally by other code changes, but still good to verify if it's
fully fixed."* Claude ran an empirical check before discussing:

- Live SomaFM API: Boot Liquor has 5 prerolls upstream.
- Local DB: Boot Liquor has all 5 stored (fetched 2026-05-24); gate logic plays one
  on bind. Zero permanently-stuck stations; 14 unfetched stations self-heal on play.

User correction during discussion: the prerolls existed upstream the **whole time**,
so the original failure mechanism AND the resolution mechanism are both UNKNOWN.
This reframed the phase from "harvest to discover an unknown cause" → "verify it's
actually resolved + add a recovery lever."

---

## Phase scope (post-verification)

| Option | Description | Selected |
|--------|-------------|----------|
| Verify & close | Convert to verification record; build no new code | |
| Harden stale-trap, then close | Verify + small re-fetch fix only | |
| Keep light instrumentation | preroll_log.py + menu entry; drop probe + harvest | ✓ |
| Full phase as scoped | Everything incl. probe + 1-2 day harvest | |

**User's choice:** Keep light instrumentation — then clarified to also fold the
re-fetch build into Phase 90 (90b reserved for "truly still broken").
**Notes:** Cause is NOT known; this is a "is this actually resolved?" check. Re-fetch
enabled here in 90. User will personally run through all stations to verify, partly
to confirm whether selection is random vs first-only (Claude confirmed from code:
`random.choice` — one at random per bind).

---

## Re-fetch design

| Option | Description | Selected |
|--------|-------------|----------|
| Manual menu action | "Re-fetch SomaFM prerolls" hamburger action, empties only | |
| Both manual + auto-staleness | Manual action + silent re-fetch on stale fetched_at + rows=0 | ✓ |
| Auto-staleness only | Silent re-fetch, no UI | |

**User's choice:** Both manual + auto-staleness.
**Notes:** Closes the latent "fetched-with-0 never re-fetches" trap permanently while
also giving an observable lever for the run-through.

---

## Preroll selection behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Keep random, log the choice | random.choice per bind; log chosen URL | ✓ |
| Change to deterministic | Play first / cycle sequentially | |

**User's choice:** Keep random, log the choice.
**Notes:** Authentic SomaFM rotation; the logged chosen-URL lets the run-through
confirm variety + reachability.

---

## Claude's Discretion

- Log rotation size/cap (mirror buffer_log), auto-refetch staleness threshold, event
  field schema, menu action placement/labels.

## Deferred Ideas

- 30s opt-in network probe + preroll-probe.log → conditional Phase 90b only.
- 1-2 day passive harvest → replaced by deliberate manual run-through.
- Net-new "Open buffer-events log" menu entry (none currently exists) → backlog polish.
- Phase 90b (conditional fix) → fires only if run-through reveals a truly-broken station.
- Possible SOMA-PRE-06 for the re-fetch lever (new capability) → roadmap concern.
