# Phase 87b: GBS Zero-Token Single-Song Add - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-18
**Phase:** 87B-gbs-zero-token-single-song-add
**Areas discussed:** Endpoint discovery, Affordance UI, Queue-empty rule, Add + feedback flow

---

## Endpoint discovery — mechanism knowledge

| Option | Description | Selected |
|--------|-------------|----------|
| Separate free-add flow | Distinct affordance/endpoint at tokens==0 | |
| Same /add, server-gated | Existing /add/<songid> allows one at tokens==0 | |
| Not sure — need to look | Don't remember; would need to log in at tokens==0 | ✓ |
| It's in the search dialog already | Existing submit IS the free-song path | |

**User's choice:** "Not sure, and not sure when I'll have token at 0 as I currently still have 48 tokens"
**Notes:** Hard constraint — user is at 48 tokens with no known/scheduled path to 0. The real tokens==0 POST behavior cannot be observed on demand. Drove the whole discovery strategy.

## Endpoint discovery — strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Provisional + capture-on-use | Assume /add reuse, build now, fixture-lock observable shape, capture real tokens==0 response on first live use, follow-up todo | ✓ |
| Investigate first, then decide | Research pass at 48 tokens (inspect homepage/Settings DOM) before committing; research flag YES | |
| Burn down to 0 first | Spend tokens to capture real POST, then plan — blocks phase indefinitely | |

**User's choice:** Provisional + capture-on-use
**Notes:** Mirrors Phase 87 D-04 "structure now, data accretes." Relaxes GBS-TOKEN-05 to provisional fixture + capture-on-first-use. Capture hook must be no-PII (Phase 87 D-18). Confirmed in CONTEXT D-01/D-02/D-03.

---

## Affordance UI — placement & form

| Option | Description | Selected |
|--------|-------------|----------|
| Button by playlist widget | QPushButton inline with GBS active-playlist widget; same data source as gating | ✓ (base) |
| Banner-style row | Full-width affordance like the Phase 87 announcement banner | |
| Button in controls area | Compact button near play/volume controls | |

**User's choice:** Option 1 (button by playlist widget) — with a reframe: "since this also applies to those with tokens, it would make sense to have the same"
**Notes:** User pivoted the phase — the affordance should serve token-holders too, not just tokens==0. Triggered the follow-up visibility question below.

## Affordance UI — visibility (scope reframe)

| Option | Description | Selected |
|--------|-------------|----------|
| Always visible when GBS bound | Persistent button any token count; amends GBS-TOKEN-01/SC#1 | ✓ |
| Visible, enabled-state varies | Always present but disabled/greyed at tokens==0 with a queued song | |
| Keep strictly zero-token gated | Honor GBS-TOKEN-01 literally; token-holders keep hamburger menu | |

**User's choice:** Always visible when GBS bound
**Notes:** Flagged as a requirements change (contradicts ROADMAP SC#1 "hidden in all other states"). User accepted the amendment. Simplifies tokens>0 to a second launch point for the existing dialog. CONTEXT D-04/D-05/D-06.

---

## Queue-empty rule / constraint handling

| Option | Description | Selected |
|--------|-------------|----------|
| Server is truth | No local pre-gating; /add hits server; messages-cookie text surfaced verbatim; capture hook records | ✓ |
| Local pre-check + server fallback | Disable button at tokens==0 + queued, but still trust server | |
| Local pre-check only | Gate purely on locally-polled state | |

**User's choice:** Server is truth
**Notes:** Consistent with Phase 60 Pitfall 8. Avoids reimplementing zero-token server rules we're guessing at under the provisional contract. Makes GBS-TOKEN-04 obsolete (button persists). CONTEXT D-07/D-08.

---

## Add + feedback flow

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm, close, re-poll | Inline success → dialog closes → playlist widget re-polls | ✓ |
| Confirm inline, stay open | Success inline, dialog stays for multi-add | |
| Close immediately, toast only | Dialog closes on success; main-window toast | |

**User's choice:** Confirm, close, re-poll
**Notes:** Existing GBSSearchDialog reused as-is (GBS-TOKEN-03). CONTEXT D-09/D-10.

---

## Claude's Discretion
- `add_song_zero_token()` factoring (thin wrapper over /add preferred).
- Capture-hook mechanics + scrubbing + "first live use" trigger (must follow Phase 87 D-18 no-PII discipline).
- Auth-expiry surfacing via Phase 87.1 `gbs_relogin_handler`.
- Worker-thread vs inline submit; re-poll plumbing; in-flight button debounce.

## Deferred Ideas
- Capture-and-confirm the true tokens==0 endpoint (auto via capture hook + follow-up todo).
- Local pre-gating / disabled-button tooltip (rejected for server-is-truth).
- Multi-add "stay open" dialog session.
- Token-cost surfacing in the affordance (out of scope per GBS-TOKEN-02).
- 6 unrelated keyword-matched todos (test failures, PLS fallback, docker probe) — reviewed, not folded.
