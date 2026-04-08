# Phase 25: Fix filter chip overflow in station filter section - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-08
**Phase:** 25-fix-filter-chip-overflow-in-station-filter-section
**Areas discussed:** Overflow approach, Layout impact, Chip grouping

---

## Overflow Approach

| Option | Description | Selected |
|--------|-------------|----------|
| FlowBox wrap (Recommended) | Same approach as phase 24. Chips wrap to multiple lines. Consistent pattern across the app. | ✓ |
| FlowBox + max height | Wrap chips but cap at ~3 rows with vertical scroll if exceeded. | |
| Keep horizontal scroll | Keep current ScrolledWindow but constrain max width. | |

**User's choice:** FlowBox wrap
**Notes:** Consistent with phase 24 pattern.

---

## Layout Impact + Chip Grouping (combined)

| Option | Description | Selected |
|--------|-------------|----------|
| Separate FlowBoxes (Recommended) | Keep provider and tag chips in their own FlowBox. Maintains visual grouping. | ✓ |
| Single merged FlowBox | Combine all chips into one FlowBox. Simpler but mixes provider/tag chips. | |

**User's choice:** Separate FlowBoxes
**Notes:** Maintains current two-row visual grouping with wrapping.

---

## Claude's Discretion

- Visual appearance: match existing chip style and spacing, follow phase 24 FlowBox config

## Deferred Ideas

None.
