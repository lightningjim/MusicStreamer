# Phase 96: Manual Refresh of Live-Stream URLs from Channel - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 96-manual-refresh-of-yellow-brick-cinema-provider-with-what-is-
**Areas discussed:** Scope reframe, Stream matching key, Diff handling scope, Apply flow & naming & defaults

---

## Scope reframe (user-initiated)

Original phase framing was YBC-specific ("refresh the Yellow Brick Cinema provider"). User clarified mid-discussion:

- YBC is not the only channel with restart-churn; **Cafe BGM** has the same problem, and likely others.
- Therefore the feature should be a **generic per-station opt-in flag, default-disabled** — mark a station as "live URL drifts, re-sync from channel."
- Likely no use outside YouTube currently. Twitch *might* qualify, but there's no HTTP-stream visibility without a plugin process for custom-site awareness — deferred to v3.

**Outcome:** Phase generalized from YBC-specific to a generic YouTube-scoped per-station flag.

---

## Stream matching key

| Option | Description | Selected |
|--------|-------------|----------|
| Exact title anchor | Store original YT title at flag-time; auto-update only exact-title matches; rest to review dialog | |
| Fuzzy title anchor | Normalize (lowercase, strip emoji/punct/'24-7'/'LIVE') before comparing; auto-resolve more; wrong-sibling risk | |
| Always manual map | No auto-matching; dialog always lists currently-live streams beside flagged stations; user maps/drops/adds every time | ✓ |

**User's choice:** Always manual map.
**Notes:** Title anchor is retained but used only to pre-order/hint suggestions, never to auto-apply. Driven by the reality that an old stream can vanish and be replaced by an unrelated new one (no title connection).

---

## Diff handling scope

User expanded this area before answering: a refresh must support not just URL updates but **dropping gone streams and adding/replacing with new unconnected streams**.

| Option | Description | Selected |
|--------|-------------|----------|
| Narrow: update URL only | Only re-point flagged station's URL; ignore new/offline | |
| URL + warn if offline | Update on match; warn (no delete) if gone | |
| Broad: also offer new streams + drop/replace | Update matched, drop gone, add new, manually map replacements | ✓ (per user clarification) |

**User's choice:** Broad — full resolution action set (update / map-replacement / drop / add), surfaced in a review/resolve dialog.
**Notes:** "There are situations where the old stream is gone and a new stream has replaced it that is not connected otherwise, so it should also be an option to delete/drop streams and add new ones with selecting a replacement."

---

## Naming (on add/replace)

| Option | Description | Selected |
|--------|-------------|----------|
| Keep custom / new uses YT title | Replacement keeps existing name; new add takes YT title | |
| Always adopt YT title | Both overwrite with current YT title | |
| Editable per row | Each row has an editable name field, pre-filled | ✓ |

**User's choice:** Editable per row.

---

## Apply flow & defaults

| Option | Description | Selected |
|--------|-------------|----------|
| Silent + summary toast | Apply immediately, toast summary | |
| Preview/confirm dialog | Show diff, confirm before commit | ✓ (implied by manual-map model) |
| Silent single / preview bulk | Mixed | |

**Defaults sub-question:**

| Option | Description | Selected |
|--------|-------------|----------|
| Conservative | URL updates pre-applied; drops & adds opt-in; unresolved untouched | ✓ |
| Aggressive | All pre-checked | |
| Nothing pre-checked | All unchecked | |

**User's choice:** Review-and-confirm dialog, Conservative defaults.
**Notes:** Reconciled with "Always manual map" — since there is no auto-applied bucket, Conservative governs unresolved-row behavior: unresolved flagged stations are left untouched (never auto-deleted); drops and new-stream adds are opt-in; deletions require an explicit tick.

---

## Claude's Discretion

- Entry point & trigger mechanics (user skipped this area): chose provider-row sidebar context menu → "Refresh live streams" review dialog over all flagged stations; flag checkbox in EditStationDialog, YouTube-gated, default off; hidden title anchor stored at flag-time.
- Exact review-dialog layout, migration column naming, anchor-based suggestion ordering, optional per-station "Refresh now" affordance.

## Deferred Ideas

- **Pluggable, custom-site-aware live-URL resolver** (Twitch + arbitrary sites), config-driven and updatable without hardcoding — scoped to **v3 milestone** by user.
- Auto/scheduled refresh on app launch — out of scope; refresh stays manual.
- Top-level-URL ↔ first-StationStream-URL duplication — that is Phase 97.
