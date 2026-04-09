# Phase 26: Fix broken Edit button next to Add Station - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-08
**Phase:** 26-fix-broken-edit-button-next-to-add-station
**Areas discussed:** Fix strategy, Layout adjustment

---

## Fix Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Remove the Edit button | Redundant with per-row edit icons, broken due to ExpanderRow grouping | |
| Fix it to work with grouped rows | Track last-clicked station and wire button to that | |
| Something else | User's own idea | ✓ |

**User's choice:** Remove from filter bar, add pencil edit icon to the now-playing section for editing the currently playing station.
**Notes:** User sees more value in editing the station you're listening to than a generic "edit selected" button. Per-row icons already cover the general case.

---

## Layout Adjustment

| Option | Description | Selected |
|--------|-------------|----------|
| Let it reflow naturally | Chip area has hexpand=True, should fill gap | |
| Specific layout tweaks | Manual spacing adjustments | |
| You decide | Claude's discretion | ✓ |

**User's choice:** Claude's discretion on filter bar reflow.
**Notes:** None.

---

## Claude's Discretion

- Filter bar layout reflow after Edit button removal

## Deferred Ideas

None — discussion stayed within phase scope.
