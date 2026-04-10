# Phase 24: Fix tag chip scroll overlapping buttons in edit dialog - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-07
**Phase:** 24-fix-tag-chip-scroll-overlapping-buttons-in-edit-dialog
**Areas discussed:** Overflow behavior, Visual appearance

---

## Overflow Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Constrain to dialog width | Keep horizontal scroll but set max width to match the form column width | |
| Wrap to multiple lines | Replace horizontal scroll with FlowBox that wraps chips to new lines | |
| You decide | Claude picks the best approach for existing dialog layout | ✓ |

**User's choice:** You decide
**Notes:** None

---

## Visual Appearance

| Option | Description | Selected |
|--------|-------------|----------|
| Fix overflow only | Keep existing chip style (ToggleButtons in a row). Just fix the sizing/overlap | |
| Use pill-style chips | Restyle chips with rounded pill shape and smaller text for a more compact look | |
| You decide | Claude picks what fits existing Adwaita dialog style | ✓ |

**User's choice:** You decide
**Notes:** None

## Claude's Discretion

- Overflow behavior: approach selection (constrain vs wrap)
- Visual appearance: style selection (keep vs restyle)

## Deferred Ideas

None
