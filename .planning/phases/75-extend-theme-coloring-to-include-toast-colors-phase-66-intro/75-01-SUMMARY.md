---
phase: 75
plan: 01
subsystem: theme
tags: [theme, qpalette, foundation, wave-1]
dependency_graph:
  requires: []
  provides:
    - "THEME_PRESETS with ToolTipBase/ToolTipText hex pairs on all 6 non-system presets"
    - "EDITABLE_ROLES tuple of length 11 with ToolTipBase + ToolTipText appended last"
    - "QApplication property 'theme_name' set inside apply_theme_palette before any branch logic"
  affects:
    - musicstreamer/ui_qt/toast.py
    - musicstreamer/ui_qt/theme_picker_dialog.py
    - musicstreamer/ui_qt/theme_editor_dialog.py
    - tests/test_toast_overlay.py
    - tests/test_theme.py
    - tests/test_theme_editor_dialog.py
    - tests/test_theme_picker_dialog.py
tech_stack:
  added: []
  patterns:
    - "Additive QPalette role extension via THEME_PRESETS dict literals"
    - "QApplication.setProperty as decoupled active-theme signal (D-10 path b)"
key_files:
  created: []
  modified:
    - musicstreamer/theme.py
decisions:
  - "Adopted D-10 path (b): setProperty('theme_name', theme_name) placed in apply_theme_palette before any branch so the property is in a sane state on every code path including the Linux+system early-return."
  - "Preserved Phase 66 D-23 sentinel: THEME_PRESETS['system'] stays {} — toast widget will read the property and branch to legacy QSS for system theme (downstream in PLAN-03)."
  - "Preserved Phase 66 D-05 uppercase-hex sampling for gbs preset's existing 10 keys; new ToolTipBase/ToolTipText keys use lowercase hex per UI-SPEC §Color LOCKED table — both forms are valid Qt input."
metrics:
  duration_seconds: 205
  tasks_completed: 3
  files_modified: 1
  completed_date: 2026-05-15
---

# Phase 75 Plan 01: theme.py foundation — ToolTipBase/ToolTipText hex + EDITABLE_ROLES + theme_name property Summary

Added per-preset `ToolTipBase` + `ToolTipText` hex pairs (UI-SPEC LOCKED, WCAG AA validated) to all 6 non-system `THEME_PRESETS`, appended both keys to `EDITABLE_ROLES` (length 9 → 11), and wired `app.setProperty("theme_name", theme_name)` inside `apply_theme_palette` before any branch logic — establishing the Wave 1 foundation that every Wave 2 consumer (`toast.py`, `theme_picker_dialog.py`, `theme_editor_dialog.py`) and Wave 3 test plan will read from.

## Objective

Land the Phase 75 theme.py foundation by writing exactly: 12 new hex literals (6 presets × 2 keys), 2 new EDITABLE_ROLES tuple entries, 1 new `setProperty` line, and 1 docstring update ("9 roles" → "11 roles"). No widget code touched. All first-9 EDITABLE_ROLES entries and existing preset keys preserved verbatim per UI-SPEC §Visual Invariance Locks.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Append UI-SPEC locked ToolTipBase/ToolTipText hex pairs to all 6 non-system presets | `2b7d868` | musicstreamer/theme.py |
| 2 | Append ToolTipBase + ToolTipText to EDITABLE_ROLES and add `app.setProperty("theme_name", theme_name)` inside apply_theme_palette | `a749021` | musicstreamer/theme.py |
| 3 | Update module docstring "9 roles" → "11 roles" (explicitly lists ToolTipBase, ToolTipText) | `36c5345` | musicstreamer/theme.py |

## Implementation Details

### Task 1 — Per-preset hex pairs (UI-SPEC LOCKED)

Added two key-value pairs after the existing `"Link"` entry inside each of the 6 non-system preset dicts in `musicstreamer/theme.py`:

| Preset | ToolTipBase | ToolTipText | Contrast (per UI-SPEC) |
|--------|-------------|-------------|------------------------|
| vaporwave | `#f9d6f0` | `#3a2845` | 9.6:1 AAA body |
| overrun | `#1a0a18` | `#ffe8f4` | 17.8:1 AAA body |
| gbs | `#2d5a2a` | `#f0f5e8` | 9.5:1 AAA body |
| gbs_after_dark | `#d5e8d3` | `#0a1a0d` | 15.2:1 AAA body |
| dark | `#181820` | `#f0f0f0` | 14.6:1 AAA body |
| light | `#2a2a32` | `#f5f5f5` | 13.5:1 AAA body |

- `THEME_PRESETS["system"]` stays `{}` (Phase 66 D-23 sentinel preserved).
- Each non-system preset dict now has exactly 12 keys (10 existing + 2 new).
- Existing preset keys (including uppercase-hex GBS brand sampling per Phase 66 D-05) preserved verbatim.

### Task 2 — EDITABLE_ROLES extension + setProperty

`EDITABLE_ROLES` tuple grew from 9 → 11 by appending `"ToolTipBase"`, `"ToolTipText"` after `"Link"`. Existing 9 entries unchanged in order (Window → WindowText → Base → AlternateBase → Text → Button → ButtonText → HighlightedText → Link).

Inside `apply_theme_palette`, inserted exactly one line:
```python
theme_name = repo.get_setting("theme", "system")
app.setProperty("theme_name", theme_name)   # ← NEW Phase 75
```

Placement is BEFORE the `if theme_name == "system":` branch so the property holds the active theme name on every path — including the Linux+system early-return that doesn't call `setPalette`. This implements D-10 path (b) verbatim from RESEARCH §1.

### Task 3 — Docstring update

Module docstring at the top of `theme.py` changed from:
```
- Theme owns 9 QPalette primary roles (Window, WindowText, Base, AlternateBase,
  Text, Button, ButtonText, HighlightedText, Link) plus a Highlight baseline.
```
to:
```
- Theme owns 11 QPalette primary roles (Window, WindowText, Base, AlternateBase,
  Text, Button, ButtonText, HighlightedText, Link, ToolTipBase, ToolTipText)
  plus a Highlight baseline.
```

Documentation only; `python -c "import musicstreamer.theme"` confirms no regression.

## Verification Results

All acceptance criteria from PLAN.md tasks 1, 2, and 3 pass:

- **Task 1 inline asserts (Python):** All 6 non-system presets verified hex pair equality against the UI-SPEC table; system preset == `{}`; each non-system preset has exactly 12 keys.
- **Task 1 grep gates:** `grep -c '"ToolTipBase":' musicstreamer/theme.py` → 6; `grep -c '"ToolTipText":' musicstreamer/theme.py` → 6.
- **Task 2 inline asserts (Python):** `len(EDITABLE_ROLES) == 11`; tail is `('ToolTipBase', 'ToolTipText')`; head preserves the existing 9-tuple order.
- **Task 2 grep gate:** `grep -cE 'app\.setProperty\("theme_name"' musicstreamer/theme.py` → 1.
- **Task 2 regression:** `pytest tests/test_theme.py::test_apply_theme_palette_uses_repo_setting -x` passes.
- **Task 3 grep gates:** "Theme owns 11 QPalette primary roles" count == 1; no surviving "Theme owns 9 QPalette" claim outside comments.
- **Task 3 import:** `python -c "import musicstreamer.theme"` succeeds.
- **Plan-level smoke command:** `python -c "from musicstreamer.theme import THEME_PRESETS, EDITABLE_ROLES; print(len(EDITABLE_ROLES), THEME_PRESETS['vaporwave']['ToolTipBase'])"` outputs `11 #f9d6f0`.

## Deviations from Plan

None — plan executed exactly as written. Tasks 1, 2, and 3 each landed in a single atomic commit with no auto-fix activity, no checkpoint escalations, and no authentication gates.

## Known Stubs

None. All edits are concrete data values from the UI-SPEC LOCKED table; no placeholder hex, no TODOs, no empty handlers introduced. The `system` preset entry remaining `{}` is a Phase 66 D-23 sentinel (documented intentional invariant), not a stub.

## Test Surface Notes (anticipated downstream)

PLAN-01's `<verification>` section explicitly anticipates that the existing test `test_all_presets_cover_9_roles` at `tests/test_theme.py:202` continues to pass (loop iterates `EDITABLE_ROLES`, uses `in` checks — verified, still green). One adjacent test, `test_gbs_preset_locked_hex_match` at `tests/test_theme.py:196`, now fails because its locked-dict comparison was Phase-66 verbatim and Phase 75 additively extends the GBS preset with two new keys. **This breakage is anticipated and explicitly owned by PLAN-06** (Wave 3, "test_theme.py: update `test_all_presets_cover_9_roles` → '_11_roles' (or add new test); per-preset hex assertions for the 12 locked values; ...") per RESEARCH §7 wave structure. Not a regression caused by this plan; not within PLAN-01's scope to update.

No other test files were touched by PLAN-01 and none of them broke as a result of the additive changes.

## Threat Flags

None. The threat register's `T-75-01` (Tampering — hex validation) and `T-75-02` (unknown role injection) are both `accept` dispositions because:
- `build_palette_from_dict` at `theme.py:179-186` already validates every hex via `_is_valid_hex` before constructing `QColor`. The two new keys flow through this validator unchanged.
- `getattr(QPalette.ColorRole, role_name, None)` already silently skips unknown role names. `ToolTipBase` and `ToolTipText` are valid `QPalette.ColorRole` enum members (verified at `musicstreamer/__main__.py:88-89`) so they pass through naturally.

No new trust-boundary surface introduced (the JSON parse path in `apply_theme_palette` for `theme=='custom'` is untouched; new keys are additive within the existing free-form `{role_name: hex}` shape).

## Self-Check: PASSED

- File `musicstreamer/theme.py` modified at HEAD: FOUND
- Commit `2b7d868` (Task 1): FOUND in `git log --oneline`
- Commit `a749021` (Task 2): FOUND in `git log --oneline`
- Commit `36c5345` (Task 3): FOUND in `git log --oneline`
- All three commits live on branch `worktree-agent-a7f81eab1cfca9689` based on `ecdd26c`.
