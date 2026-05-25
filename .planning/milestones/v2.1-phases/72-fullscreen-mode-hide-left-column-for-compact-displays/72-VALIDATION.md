---
phase: 72
slug: fullscreen-mode-hide-left-column-for-compact-displays
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
---

# Phase 72 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) + pytest-qt (verify Wave 0 if not installed) |
| **Config file** | `pyproject.toml` (pytest section) |
| **Quick run command** | `pytest tests/test_main_window.py tests/test_now_playing_panel.py -x` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~60s (quick), ~3-5min (full) |

---

## Sampling Rate

- **After every task commit:** Run quick command (relevant test file only)
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60s

---

## Per-Task Verification Map

> Plans not yet generated — table populated by planner. Initial template lists expected dimensions sourced from RESEARCH.md `## Validation Architecture` section.

| Dimension | Coverage | Test Type | Notes |
|-----------|----------|-----------|-------|
| QShortcut Ctrl+B activation | toggle slot fires | pytest-qt integration | QTest.keyClick or activated.emit() |
| QToolButton checked state | sync with shortcut | pytest-qt integration | button.setChecked persists across both surfaces |
| Splitter sizes snapshot/restore | round-trip | unit (no Qt event loop) | sizes captured BEFORE hide() per Pitfall 1 |
| station_panel.hide()/show() | visibility flips | pytest-qt | isVisible() / isHidden() assertions |
| Splitter handle auto-hide (A1) | Wave 0 spike | pytest-qt | regression-catch for Qt 6.10+ behavior |
| station_panel reparenting (A2) | Wave 0 spike | pytest-qt | confirm no parent-assumption breakage |
| Hover-dwell timer (~250-300ms) | fires after dwell, cancels on exit | pytest-qt with qWait | event filter on centralWidget |
| Peek overlay visibility | shown on dwell, hidden on mouse-leave | pytest-qt | mouse-leave-overlay-only dismiss |
| Peek overlay interactivity | click-to-play works inside overlay | pytest-qt integration | station_activated signal fires |
| Session-only persistence (negative) | repo.set_setting NOT called for compact_mode | unit/mock | MagicMock spy on repo, assertNotCalled |
| Icon flip per state | two distinct icons swap | pytest-qt | button.icon() differs in checked vs unchecked |
| Restored splitter sizes (D-10) | exit compact restores last-live sizes | pytest-qt | snapshot=[400,800], hide, show, sizes==[400,800] |
| Modal dialog shortcut blocking | Ctrl+B inert when dialog open | pytest-qt | EditStationDialog opened → Ctrl+B no-op |
| No X11 codepaths | source-level grep | grep | confirm no xprop/xwininfo references introduced |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] **Spike A1:** `tests/test_phase72_splitter_handle_autohide.py` — verify Qt 6.10+ auto-hides splitter handle when child is hidden (regression-catch)
- [ ] **Spike A2:** `tests/test_phase72_reparent_station_panel.py` — verify `station_panel.setParent(...)` round-trip preserves filter/search/scroll state (no parent-assumption breakage)
- [ ] Verify `pytest-qt` is installed (likely already present given Phase 47.1/67 Qt test patterns); if not, add to dev dependencies in Wave 0
- [ ] Confirm `QTest.keyClick` for shortcut testing works in this project's Qt setup (may need a small fixture)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Icon flip visual correctness | D-05 | Visual judgment — does each glyph clearly communicate next-action | Open app, toggle Ctrl+B, confirm icon visibly changes between sidebar-open and sidebar-closed states |
| Hover-peek feel/timing | D-13 | Subjective UX — is 280ms dwell + 4-6px zone natural? | Move cursor across window, intentionally to the edge, confirm peek opens after a perceptible-but-not-laggy dwell; confirm accidental drags do not trigger |
| Overlay z-order vs ToastOverlay | D-12 + Open Question | Visual — does the peek panel obscure or get obscured by toasts? | Trigger a toast (e.g., star a track) while peeked; confirm visual stacking is acceptable |
| Bottom-bar overlap fix verified | Phase goal (root cause) | Real-device — repro requires the actual small/secondary display | Resize window to ~560-700px width on small display; toggle compact ON; confirm bottom-bar controls no longer overlap and are fully clickable |
| Wayland on GNOME Shell behavior | Deployment target | Wayland-specific shell behavior cannot be unit-tested | Run on actual Wayland session; confirm no X11-property dependencies surface |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers Spike A1 (splitter handle auto-hide) + Spike A2 (reparenting feasibility)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s for quick command
- [ ] Negative-persistence assertion (no `repo.set_setting` for compact mode) exists
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending — planner fills per-task rows in step 8.
