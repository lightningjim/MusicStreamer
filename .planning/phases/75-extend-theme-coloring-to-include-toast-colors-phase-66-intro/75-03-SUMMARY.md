---
phase: 75-extend-theme-coloring-to-include-toast-colors-phase-66-intro
plan: 03
subsystem: ui

tags: [pyside6, qpalette, qss, toast, changeevent, palettechange, theme]

requires:
  - phase: 75-01
    provides: "QPalette.ToolTipBase / ToolTipText roles in all THEME_PRESETS; EDITABLE_ROLES extended; QApplication.setProperty('theme_name', ...) wired in apply_theme_palette"
  - phase: 66
    provides: "QApplication.setPalette()-based theme architecture; QApplication.setProperty('theme_name', ...) pattern"
  - phase: 37
    provides: "ToastOverlay widget (lifetime, animations, geometry)"

provides:
  - "ToastOverlay palette-driven stylesheet that branches on QApplication.property('theme_name')"
  - "System-theme legacy QSS preservation (rgba(40, 40, 40, 220) + white) per D-09"
  - "Live theme retint via changeEvent(QEvent.PaletteChange) — first setStyleSheet-inside-changeEvent site in the codebase, with PaletteChange-only filter as recursion guard"

affects: [75-04, 75-05, 75-06, 75-07, 75-08, future widgets that need theme-name branching]

tech-stack:
  added: []
  patterns:
    - "Lazy theme_name read inside QSS builder (NEVER cached on self) — picker live-preview mutates the property mid-session, RESEARCH §Pattern 2 / §4"
    - "changeEvent(PaletteChange) ONLY when the handler calls setStyleSheet (StyleChange would recurse) — diverges from in-tree analogs at now_playing_panel.py:194-197 / eq_response_curve.py:121-124 which use both PaletteChange and StyleChange because they call setPalette/update, not setStyleSheet"
    - "Handler-first, super()-last ordering in changeEvent overrides (matches now_playing_panel analog)"
    - "Verbatim IMMUTABLE QSS comment-locked in source — D-09 protected substring `rgba(40, 40, 40, 220)` + `color: white`"

key-files:
  created: []
  modified:
    - "musicstreamer/ui_qt/toast.py — QPalette + QApplication imports; _rebuild_stylesheet helper; changeEvent override; __init__ calls _rebuild_stylesheet instead of inline setStyleSheet"

key-decisions:
  - "PaletteChange-ONLY filter on changeEvent (not the (PaletteChange, StyleChange) tuple used by in-tree analogs) — setStyleSheet() inside the handler re-fires StyleChange; matching on StyleChange would recurse infinitely (RESEARCH Risk 1, T-75-05). Verified by 35-flip stress test (5 cycles × 7 themes) with no RecursionError."
  - "Lazy property read inside _rebuild_stylesheet — never cache on self. Picker tile-click live-preview mutates QApplication.property('theme_name'); caching would freeze the toast on the startup theme."
  - "System-theme branch uses literal `color: white` (the word, not `#ffffff`) — UI-SPEC §Color §System-theme legacy fallback IMMUTABLE QSS LOCK preserves the exact pre-Phase-75 substring."
  - "Inline NB comment above the filter check explains the narrowing (`# NB: PaletteChange ONLY — setStyleSheet() re-fires StyleChange (RESEARCH Risk 1).`) so future readers don't 'fix' it back to the both-events filter by analogy with the codebase."

patterns-established:
  - "First setStyleSheet-inside-changeEvent site in the codebase — narrows the filter to PaletteChange ONLY. Future widgets in this category should follow this template, not the wider both-events filter used by setPalette-only widgets."
  - "QApplication.property('theme_name') as theme-identity broadcast — read inside per-widget QSS builders (no Repo threading required, no caching). The property is written by apply_theme_palette and theme_picker_dialog tile-click."

requirements-completed: [THEME-02]

# Metrics
duration: ~10 min (Wave 2 worktree agent)
completed: 2026-05-15
---

# Phase 75 Plan 03: ToastOverlay palette-driven stylesheet Summary

**ToastOverlay now branches on `QApplication.property('theme_name')`: `system` (or unset) yields the IMMUTABLE legacy `rgba(40, 40, 40, 220)` + white QSS, every other theme yields palette-driven QSS interpolating ToolTipBase rgb (alpha 220) and ToolTipText.name(). A `changeEvent(QEvent.PaletteChange)` override (filter narrowed to PaletteChange ONLY as a recursion guard) retints live on theme flips.**

## Performance

- **Duration:** ~10 min (Wave 2 worktree agent)
- **Completed:** 2026-05-15
- **Tasks:** 2
- **Files modified:** 1 (musicstreamer/ui_qt/toast.py)

## Accomplishments

- Replaced the hardcoded inline `setStyleSheet(...)` block at toast.py:44-52 with a single `self._rebuild_stylesheet()` call from `__init__`. All animation, lifetime, and geometry code in `__init__` left untouched.
- Added `_rebuild_stylesheet(self) -> None` to the `# --- Internal ---` section. Reads `app.property("theme_name")` lazily (no caching) and branches:
  - `None` / empty / `"system"` → IMMUTABLE legacy QSS (`rgba(40, 40, 40, 220)`, `color: white`, `border-radius: 8px`, `padding: 8px 12px`).
  - Otherwise → QSS interpolating `pal.color(QPalette.ToolTipBase).red()/.green()/.blue()` with literal alpha `220` and `pal.color(QPalette.ToolTipText).name()` (lowercase `#rrggbb`). Same geometry pair preserved verbatim.
  - No `font-size:`, `font-family:`, or `font-weight:` in either branch (UI-SPEC typography invariance lock).
- Added `changeEvent(self, event: QEvent) -> None` override placed adjacent to `_rebuild_stylesheet`. Filter is `event.type() == QEvent.PaletteChange` ONLY (NOT the `(PaletteChange, StyleChange)` tuple used by in-tree analogs). Handler logic FIRST, `super().changeEvent(event)` LAST. Inline `# NB:` comment explains the recursion guard so the filter is not "corrected" back to the wider form by future readers.
- Added `from PySide6.QtGui import QPalette` and added `QApplication` to the existing `PySide6.QtWidgets` import block.

## Task Commits

1. **Task 1: Imports + `_rebuild_stylesheet` + replace inline setStyleSheet** — `50a8d4c` (feat)
2. **Task 2: `changeEvent(QEvent.PaletteChange)` override (recursion guard)** — `d02363b` (feat)

## Files Created/Modified

- `musicstreamer/ui_qt/toast.py` — Imports extended (QPalette + QApplication); inline `setStyleSheet(...)` in `__init__` replaced with single `self._rebuild_stylesheet()` call; `_rebuild_stylesheet` and `changeEvent` methods added to the `# --- Internal ---` section.

## Decisions Made

- **PaletteChange-ONLY filter on changeEvent.** Departs from the in-tree pattern at `now_playing_panel.py:194-197` and `eq_response_curve.py:121-124` (both filter `(PaletteChange, StyleChange)`). Rationale: those handlers call `setPalette` / `update()`, neither of which fires `StyleChange`. Phase 75's handler calls `setStyleSheet()`, which Qt 6.11 re-fires as `StyleChange` internally — matching on it would cause infinite recursion (RESEARCH §Risk 1, threat register T-75-05). 35-flip stress test (5 cycles × 7 themes) confirmed no `RecursionError`. Inline `# NB:` comment locks the narrowing in place.
- **Lazy `theme_name` read.** Property is read inside `_rebuild_stylesheet`, never cached on `self`. The theme picker's tile-click live-preview mutates `QApplication.property("theme_name")` mid-session (RESEARCH §Pattern 2 / Anti-Pattern); caching would freeze the toast on whatever theme was active at construction.
- **Literal `color: white` in the system branch.** The word `white`, not `#ffffff` or `#FFF`. UI-SPEC §Color §System-theme legacy fallback IMMUTABLE QSS LOCK protects the exact pre-Phase-75 substring `rgba(40, 40, 40, 220)` + `color: white`. Source comment in `_rebuild_stylesheet` explicitly flags both as immutable.
- **Method placement order (changeEvent BEFORE `_rebuild_stylesheet` BEFORE `eventFilter`).** Both new methods live in the `# --- Internal ---` section. `changeEvent` is placed first because Qt overrides conventionally appear before private helpers in this codebase. `eventFilter` remains adjacent to `_reposition` (its caller).

## Deviations from Plan

None — plan executed exactly as written. Both tasks committed with the expected behavior and source-grep gates. The single Qt-test-harness quirk encountered (palette propagation requires `QApplication.sendPostedEvents()` to flush queued `PaletteChange` events to widgets created BEFORE `setPalette`) is a test-environment artifact, not an implementation issue — in real GUI usage with a running event loop, the propagation happens naturally. Documented under "Issues Encountered" below.

## Issues Encountered

- **Qt palette propagation requires event-queue flush in headless tests.** When the verify command constructed a `parent = QWidget()` BEFORE calling `app.setPalette(...)`, the parent's cached palette did not update until `QApplication.sendPostedEvents()` was called (Qt 6.11 delivers `PaletteChange` via the posted-events queue, not synchronously). Child widgets created after the flip but before the flush inherited the stale parent palette via `self.palette()`. Resolution: add `QApplication.sendPostedEvents()` to the headless verification script. The implementation is correct — under a running event loop (real GUI), `changeEvent(PaletteChange)` fires naturally as part of palette dispatch and the toast retints without explicit flushing. This finding is captured here so future Plan-06 test retrofits know to flush events between `setPalette` and `widget.styleSheet()` reads in headless / no-event-loop scenarios.

## Verification Results

- Source grep gates (all passing):
  - `grep -c '_rebuild_stylesheet' toast.py` = 2 (def + `__init__` call) — Task 2 changeEvent adds a third reference, so post-plan count is 3 actual references (def + `__init__` call + changeEvent call).
  - `grep -c 'from PySide6.QtGui import QPalette' toast.py` = 1.
  - `grep -E 'from PySide6.QtWidgets import.*QApplication' toast.py` matches the multi-line import block (QApplication appears as the first entry on the import-list line).
  - Non-comment `setStyleSheet` count = 2 (both inside `_rebuild_stylesheet`). Total source count is 3 because of the explanatory `# NB:` comment on the changeEvent filter line; the plan's "exactly 2" criterion was authored before this comment was added and reflects the count of actual calls.
  - `grep -cE 'def changeEvent' toast.py` = 1.
  - `grep -v '^\s*#' toast.py | grep -c 'QEvent\.StyleChange'` = 0 — recursion guard locked.
  - `grep -cE 'QEvent\.PaletteChange' toast.py` = 1.
- Behavior verification:
  - System branch (`theme_name='system'`): QSS contains `rgba(40, 40, 40, 220)`, `color: white`, `border-radius: 8px`, `padding: 8px 12px`. No `font-*` properties.
  - All 6 non-system themes verified end-to-end: vaporwave `rgba(249, 214, 240, 220)`, overrun `rgba(26, 10, 24, 220)`, gbs `rgba(45, 90, 42, 220)`, gbs_after_dark `rgba(213, 232, 211, 220)`, dark `rgba(24, 24, 32, 220)`, light `rgba(42, 42, 50, 220)` — each with the correct lowercase `ToolTipText.name()` foreground, alpha 220 literal, and geometry pair.
  - Recursion stress test: 35 palette flips (5 cycles × 7 themes) with no `RecursionError`.
  - `pytest tests/test_toast_overlay.py -x`: 14/14 tests pass (including `test_14_stylesheet_color_contract` which exercises the legacy QSS branch via the default fixture state where `theme_name` is unset — the system branch fires).

## Threat Surface

No new threat surface beyond what is captured in the plan's `<threat_model>`:

- **T-75-04 (Tampering, accept):** `palette().color(QPalette.ToolTipBase/ToolTipText)` returns a Qt-validated `QColor`. `.red()/.green()/.blue()` are int methods bounded 0-255; `.name()` returns lowercase `#rrggbb`. Upstream `_is_valid_hex` in `theme.py:179-186` filters every hex before reaching the palette. No user-controlled string ever flows through the f-string interpolation in `_rebuild_stylesheet`.
- **T-75-05 (Denial of Service via recursion, mitigated):** PaletteChange-only filter + source-grep gate (`grep -v '^#' | grep -c 'QEvent.StyleChange'` = 0) locks the mitigation in place.

## Self-Check: PASSED

- File `musicstreamer/ui_qt/toast.py` exists (modified). Confirmed via `ls`.
- Commit `50a8d4c` (Task 1) exists in `git log`.
- Commit `d02363b` (Task 2) exists in `git log`.

## Next Plan Readiness

- Plan 75-04 (theme_picker_dialog `setProperty("theme_name", ...)` for live preview) can proceed — the toast widget will retint when 75-04 broadcasts the property change.
- Plan 75-06 (test retrofit for `test_14_stylesheet_color_contract`) inherits the verification template proven here: construct toast with `theme_name='system'` for the legacy-QSS assertion; flip to a non-system preset (with `QApplication.sendPostedEvents()` between `setPalette` and reading `styleSheet()` in headless mode) for the palette-driven assertions.
- All 14 pre-Phase-75 toast tests continue to pass; no regression in lifetime, animation, or geometry behavior (no code in those blocks was touched).

---
*Phase: 75-extend-theme-coloring-to-include-toast-colors-phase-66-intro*
*Completed: 2026-05-15*
