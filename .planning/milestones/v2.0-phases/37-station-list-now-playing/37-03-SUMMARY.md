---
phase: 37-station-list-now-playing
plan: "03"
subsystem: ui_qt
tags: [toast, overlay, animation, ui-12, qa-05]
dependency_graph:
  requires: [37-01]
  provides: [ToastOverlay widget, UI-12 surface]
  affects: [37-04]
tech_stack:
  added: []
  patterns: [QPropertyAnimation windowOpacity fade, eventFilter parent resize, parent-owned animations]
key_files:
  created:
    - musicstreamer/ui_qt/toast.py
  modified:
    - tests/test_toast_overlay.py  # pre-existing TDD-red; no changes needed — all 14 tests passed
decisions:
  - "Use QPropertyAnimation on windowOpacity for cross-platform fade (no QGraphicsOpacityEffect needed)"
  - "Parent-owned animations (self as parent arg) prevents GC freeze mid-flight (Pitfall 6)"
  - "No WA_DeleteOnClose — same ToastOverlay instance reused for every toast (QA-05)"
  - "Bound-method slots (not lambdas) for hold_timer.timeout and fade_out.finished — avoids self-capture lifetime issues"
metrics:
  duration_min: 5
  completed_date: "2026-04-12"
  tasks_completed: 1
  files_changed: 1
requirements: [UI-12]
---

# Phase 37 Plan 03: ToastOverlay Widget Summary

**One-liner:** Frameless QWidget toast overlay with QPropertyAnimation windowOpacity fade-in/hold/fade-out, parent-owned lifetime, and resize re-anchoring — all 14 lifecycle + QA-05 lifetime tests pass.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | ToastOverlay widget + animation lifecycle + tests | 83aa2e6 | musicstreamer/ui_qt/toast.py |

## What Was Built

`musicstreamer/ui_qt/toast.py` — `ToastOverlay(QWidget)` with:
- `show_toast(text, duration_ms=3000)` — public API, reusable
- Fade-in 150ms (`QPropertyAnimation` on `windowOpacity`, 0.0→1.0)
- Configurable hold via `QTimer.singleShot`
- Fade-out 300ms (1.0→0.0), hides on `finished`
- Re-show during fade-out: stops fade-out cleanly, no flicker (QA-05)
- `eventFilter` on parent for `QEvent.Resize` → `_reposition()`
- Width clamped: min 240px, max min(parent.width()-64, 480)
- Positioned: bottom-center, 32px above parent bottom edge
- `WA_TransparentForMouseEvents` — click-through
- `WA_ShowWithoutActivating` — no focus steal
- No `WA_DeleteOnClose` — parent-owned lifetime
- Inner `QLabel` objectName `"ToastLabel"` — QSS hook
- QSS: `rgba(40, 40, 40, 220)` background, `border-radius: 8px`

The TDD-red test file at `tests/test_toast_overlay.py` (committed at 63b2de3 pre-plan) covered all 14 required behaviors. No test additions were needed — the existing 14 tests passed immediately against the implementation.

**Test result:** 317 passed (303 baseline + 14 new), 0 failures.

## Deviations from Plan

None — plan executed exactly as written. The `toast.py` implementation matches the plan's verbatim code block. Test file was pre-existing (TDD-red); no modifications required.

## Self-Check: PASSED

- `musicstreamer/ui_qt/toast.py` — FOUND
- commit `83aa2e6` — FOUND
- All 14 tests pass
- No `WA_DeleteOnClose` attribute set (comment-only references)
- No `lambda.*self` in toast.py
