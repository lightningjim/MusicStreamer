---
phase: 59-visual-accent-color-picker
plan: 03
subsystem: ui
tags: [accent, color-picker, qcolordialog, uat, manual-verify]
requires:
  - phase: 59
    provides: 59-01 RED test contract + 59-02 QColorDialog wrapper implementation
provides:
  - Manual UAT attestations on Linux X11 (DPR=1.0 / GNOME) covering ROADMAP §Phase 59 SC #1..4 + Eyedropper + Reset + Cancel/Esc/X + Idempotent reseed
  - Runtime confirmation of D-11 throttle decision (no flicker → keep no-throttle ship; no follow-up Plan 04 needed)
  - Discovery + fix of an X11-only render bug missed by the offscreen pytest-qt suite (commit `0f46a77`)
affects: [phase 66 — color themes layer on top of accent_color override; this phase's contract holds]
tech-stack:
  added: []
  patterns:
    - X11 child-widget render gotcha: QColorDialog (which is a QDialog) embedded via addWidget needs setWindowFlags(Qt.Widget) to render its content on real X11 — offscreen Qt does not surface the bug.
key-files:
  created:
    - .planning/phases/59-visual-accent-color-picker/59-03-UAT-LOG.md
  modified:
    - musicstreamer/ui_qt/accent_color_dialog.py (during UAT — X11 render fix on top of Plan 02's ship)
---

# Phase 59-03 — Plan Summary

## Outcome

Manual UAT on Linux X11 (DPR=1.0, GNOME compositor) validated all 4 ROADMAP §Phase 59 success criteria + 4 additional attestations (Eyedropper, Reset, Cancel/Esc/X, Idempotent reseed). All scenarios PASS.

**Resume signal:** `approved`

## Findings

### UAT-blocker discovered + fixed mid-run

Initial launch of the new dialog showed only the Apply / Reset / Cancel button row — the inner `QColorDialog` was suppressed by Qt's default `Qt.Dialog` window flag on real X11 (offscreen Qt rendered fine, which is why pytest-qt did not catch it during Plan 02 verification). Fix: `self._inner.setWindowFlags(Qt.Widget)` on the inner widget before `addWidget`, plus `setSizeGripEnabled(False)`. Committed as `0f46a77` and verified via offscreen test re-run (27/27 pass) before resuming UAT.

This is a pattern worth remembering: **embedding a QColorDialog as a child widget on X11 requires stripping the Qt.Dialog window flag.** The offscreen platform plugin handles this differently than the real X11 server. Captured in this summary's `tech-stack.patterns`.

### Decisions confirmed at runtime

- **D-11 throttle (Claude's Discretion):** ship without `QTimer.singleShot(50, ...)`. UAT confirmed no flicker on Linux X11 / GNOME / DPR=1.0 during drag through the hue picker and sat/val square. **No follow-up Plan 04 needed.**
- **Pitfall 4 X11 mouse-grab caveat:** not observed on the GNOME compositor. Eyedropper grabs cross-app screen pixels cleanly.
- **D-03 idempotent reseed:** verified at runtime — overwriting slot 0 of Custom Colors and reopening the dialog confirms the seed loop runs in `__init__` and overwrites any in-session edits to slots 0..7.
- **D-15 + D-15.6 Reset semantics:** Reset clears the saved `accent_color` setting, restores the snapshot palette, returns the picker to default blue, dialog stays open. The empty-string write to `paths.accent_css_path()` (D-15.6 path chosen by Plan 02) is verified to leave a clean startup state — the next launch boots with the theme/system default, not a stale accent.

## Verification

### ROADMAP §Phase 59 Success Criteria

| SC | Behavior | Status |
|----|----------|--------|
| #1 | Visual color picker present alongside swatches and hex field | PASS |
| #2 | Live preview during drag (no flicker) | PASS |
| #3 | Hex entry still works; picker reflects hex | PASS |
| #4 | Persistence across app restart | PASS |

### Additional attestations

| Behavior | Status |
|----------|--------|
| Eyedropper / Pick Screen Color | PASS |
| Reset (clear setting + restore snapshot + dialog stays open) | PASS |
| Cancel / Esc / window-manager X (snapshot restore, no save) | PASS |
| Idempotent reseed of slots 0..7 across dialog opens | PASS |

### Plan 03 acceptance criteria

| Predicate | Result |
|-----------|--------|
| `test -f 59-03-UAT-LOG.md && grep -q 'SC #1..4'` | OK: SC #1..4 each attested |
| `grep -c "## ROADMAP §Phase 59"` | 1 |
| `grep -cE '(Eyedropper\|Reset\|Cancel\|Idempotent reseed)'` | 8 (>= 4 required) |

## Phase 59 Closure

- All 3 plans complete (59-01 RED, 59-02 GREEN, 59-03 UAT).
- All 4 ROADMAP SCs PASS.
- ACCENT-02 requirement satisfied.
- No outstanding follow-up plans needed.
- Phase 66 forward-compat preserved: accent_color setting + Highlight palette role override semantics unchanged; theme layering will work as designed.
