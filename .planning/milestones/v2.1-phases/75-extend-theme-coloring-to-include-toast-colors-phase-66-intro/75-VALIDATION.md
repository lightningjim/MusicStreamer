---
phase: 75
slug: extend-theme-coloring-to-include-toast-colors-phase-66-intro
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-05-15
---

# Phase 75 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Sourced from `75-RESEARCH.md §Validation Architecture` (lines 617-660).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-qt (offscreen platform) |
| **Config file** | `tests/conftest.py` (sets `QT_QPA_PLATFORM=offscreen` at line 13) |
| **Quick run command** | `pytest tests/test_toast_overlay.py tests/test_theme.py -x` |
| **Full suite command** | `pytest tests/test_toast_overlay.py tests/test_theme.py tests/test_theme_editor_dialog.py tests/test_theme_picker_dialog.py -x` |
| **Estimated runtime** | ~5-8 seconds (full 4-file suite, offscreen platform) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_toast_overlay.py tests/test_theme.py -x` (~2-3s)
- **After every plan wave:** Run the full 4-file command
- **Before `/gsd-verify-work`:** Full 4-file suite must be green
- **Max feedback latency:** 8 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 75-01-01 | 01 | 1 | THEME-02 | — | N/A | unit | `pytest tests/test_theme.py -x -k preset` | ✅ | ⬜ pending |
| 75-01-02 | 01 | 1 | THEME-02 | — | N/A | unit | `pytest tests/test_theme.py -x -k locked_hex` | ✅ | ⬜ pending |
| 75-01-03 | 01 | 1 | THEME-02 | — | N/A | unit | `pytest tests/test_theme.py -x -k system_empty` | ✅ | ⬜ pending |
| 75-01-04 | 01 | 1 | THEME-02 | — | N/A | unit | `pytest tests/test_theme.py -x -k editable_roles` | ✅ | ⬜ pending |
| 75-01-05 | 01 | 1 | THEME-02 | — | N/A | unit | `pytest tests/test_theme.py -x -k property` | ✅ | ⬜ pending |
| 75-02-01 | 02 | 1 | THEME-02 | — | N/A | docs | (REQUIREMENTS.md grep `THEME-02`) | ✅ | ⬜ pending |
| 75-03-01 | 03 | 2 | THEME-02 | T-V5 | hex validation via `_is_valid_hex` upstream | unit | `pytest tests/test_toast_overlay.py -x -k system` | ✅ | ⬜ pending |
| 75-03-02 | 03 | 2 | THEME-02 | — | N/A | unit | `pytest tests/test_toast_overlay.py -x -k preset` | ✅ | ⬜ pending |
| 75-03-03 | 03 | 2 | THEME-02 | — | N/A | unit | `pytest tests/test_toast_overlay.py -x -k changeEvent` | ✅ | ⬜ pending |
| 75-03-04 | 03 | 2 | THEME-02 | — | N/A | unit | `pytest tests/test_toast_overlay.py -x -k geometry` | ✅ | ⬜ pending |
| 75-03-05 | 03 | 2 | THEME-02 | — | N/A | unit | `pytest tests/test_toast_overlay.py -x -k typography` | ✅ | ⬜ pending |
| 75-04-01 | 04 | 2 | THEME-02 | — | N/A | integration | `pytest tests/test_theme_picker_dialog.py -x -k property` | ✅ | ⬜ pending |
| 75-04-02 | 04 | 2 | THEME-02 | — | N/A | integration | `pytest tests/test_theme_picker_dialog.py -x -k retint` | ✅ | ⬜ pending |
| 75-05-01 | 05 | 2 | THEME-02 | — | N/A | unit | `pytest tests/test_theme_editor_dialog.py -x -k 11_color` | ✅ | ⬜ pending |
| 75-05-02 | 05 | 2 | THEME-02 | — | N/A | unit | `pytest tests/test_theme_editor_dialog.py -x -k label` | ✅ | ⬜ pending |
| 75-05-03 | 05 | 2 | THEME-02 | — | N/A | unit | `pytest tests/test_theme_editor_dialog.py -x -k save` | ✅ | ⬜ pending |
| 75-05-04 | 05 | 2 | THEME-02 | — | N/A | unit | `pytest tests/test_theme_editor_dialog.py -x -k reset` | ✅ | ⬜ pending |
| 75-05-05 | 05 | 2 | THEME-02 | — | N/A | unit | `pytest tests/test_theme_editor_dialog.py -x -k cancel` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Note: exact task IDs and plan splits will be finalized by `gsd-planner`. The structure above reflects the 6-8 plan / 3-wave proposal from RESEARCH.md §7; planner may merge test plans into their parent feature plans.*

---

## Wave 0 Requirements

All 4 test files already exist:

- ✅ `tests/test_toast_overlay.py` — existing 14 tests + line 143 retrofit + new palette-driven assertions
- ✅ `tests/test_theme.py` — existing per-preset assertions to extend with ToolTipBase/ToolTipText
- ✅ `tests/test_theme_editor_dialog.py` — existing Save/Reset/Cancel tests to extend from 9→11 rows
- ✅ `tests/test_theme_picker_dialog.py` — existing tile-click tests to extend with property + retint assertions
- ✅ `tests/conftest.py` — offscreen platform already set (line 13)
- ✅ pytest-qt already installed (per RESEARCH §Test Infrastructure)

*Phase 75 extends existing infrastructure rather than creating new — no Wave 0 install/scaffold work required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Wayland live theme flip: pick a non-system theme via the picker → currently-visible toast retints instantly to the new ToolTipBase/ToolTipText pair | THEME-02 | Visual repaint timing on real Wayland compositor (GNOME Shell) — offscreen platform doesn't render | Launch app on Linux Wayland (`musicstreamer`), trigger a toast (`Ctrl+G` and tab a few times to fire a status toast), open Theme picker, click each of the 6 preset tiles — toast should retint without restart. Confirm dark→light alpha stays at 80% (`220/255`). |
| Wayland live theme flip with theme=system: toast stays dark grey + white | THEME-02 (legacy preservation D-09) | Same — visual confirmation on real compositor | After live-flip test, pick "System" tile → next toast (and any visible one) should snap to `rgba(40,40,40,220)` + white, pixel-identical to today |
| Editor 11-row layout: rows fit without scroll bar | UI-SPEC §Spacing | Visual size assertion — offscreen reports geometry but doesn't render scrollbar visibility | Open Customize… editor; verify 11 swatch rows are visible without a scrollbar on a 1080p Wayland DPR=1.0 display |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (Wave 0 N/A — extends existing)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (no MISSING refs — all test files exist)
- [ ] No watch-mode flags (`-x` used, not `--watch`)
- [ ] Feedback latency < 8s (measured: ~5-8s full suite)
- [ ] `nyquist_compliant: true` set in frontmatter (flip on planner sign-off)

**Approval:** pending

---

*Sources: `75-RESEARCH.md §Validation Architecture` (lines 617-660), `75-UI-SPEC.md §Color`, `75-CONTEXT.md D-13/D-14/D-15`.*
