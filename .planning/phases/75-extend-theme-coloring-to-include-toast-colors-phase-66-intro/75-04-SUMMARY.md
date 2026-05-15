---
phase: 75
plan: 04
subsystem: theme
tags: [theme, theme-picker, setproperty, wave-2]
dependency_graph:
  requires:
    - "Phase 75 PLAN-01 setProperty('theme_name', theme_name) inside apply_theme_palette"
  provides:
    - "QApplication property 'theme_name' is kept in sync during tile-click live preview"
    - "ToastOverlay (Wave 3+) can rely on app.property('theme_name') being current inside the synchronous PaletteChange dispatch fired by setPalette()"
  affects:
    - musicstreamer/ui_qt/theme_picker_dialog.py
tech_stack:
  added: []
  patterns:
    - "Mirror PLAN-01's QApplication.setProperty signal at the second mandatory write site (RESEARCH §1)"
key_files:
  created:
    - .planning/phases/75-extend-theme-coloring-to-include-toast-colors-phase-66-intro/75-04-SUMMARY.md
  modified:
    - musicstreamer/ui_qt/theme_picker_dialog.py
decisions:
  - "Used the function parameter `theme_id` (not a repo lookup) as the property value: the tile-click signal already carries the authoritative new theme_id and a repo round-trip would race the live-preview flow."
  - "Placed the setProperty call BEFORE the system/custom/preset branch (and therefore before any setPalette call) — RESEARCH §1 makes this mandatory because Qt dispatches PaletteChange synchronously inside setPalette() and ToastOverlay's changeEvent reads app.property('theme_name') inside that dispatch."
  - "Did not add a comment above the new line — the surrounding lines are uncommented and the minimal-diff constraint in the plan acceptance criteria (≤1 net insertion) takes precedence."
metrics:
  duration_seconds: 120
  tasks_completed: 1
  files_modified: 1
  completed_date: 2026-05-15
---

# Phase 75 Plan 04: theme_picker_dialog setProperty mirror Summary

Inserted a single line — `app.setProperty("theme_name", theme_id)` — inside `theme_picker_dialog._on_tile_clicked`, immediately after `app = QApplication.instance()` and before the system/custom/preset branch, so the `QApplication` `"theme_name"` property is updated on every live-preview tile click before `setPalette()` fires its synchronous `PaletteChange` dispatch. This is the second of the two mandatory `setProperty` write sites identified by RESEARCH §1 (PLAN-01 landed the first inside `apply_theme_palette`).

## Objective

Mirror the PLAN-01 `setProperty` call at the picker dialog's tile-click slot. ToastOverlay's `changeEvent` (delivered to Wave 3+) will read `app.property("theme_name")` inside Qt's synchronous `PaletteChange` dispatch to decide system-QSS vs non-system-QSS branches; the property therefore must already hold the new `theme_id` by the time `setPalette()` is invoked.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Insert `app.setProperty("theme_name", theme_id)` between `app = QApplication.instance()` and the branch logic in `_on_tile_clicked` | `4a09064` | musicstreamer/ui_qt/theme_picker_dialog.py |

## Implementation Details

### Task 1 — Mirror the PLAN-01 setProperty write site

`musicstreamer/ui_qt/theme_picker_dialog.py::_on_tile_clicked` was modified to insert exactly one new line between the existing `app = QApplication.instance()` line (line 264) and the `if theme_id == "system":` branch (now line 267):

```python
def _on_tile_clicked(self, theme_id: str) -> None:
    """Tile click = live preview; no persistence (UI-SPEC §State Machine P-Previewing)."""
    self._selected_theme_id = theme_id
    self._active_tile_id = theme_id
    app = QApplication.instance()
    app.setProperty("theme_name", theme_id)   # ← new line (Phase 75 PLAN-04)

    if theme_id == "system":
        app.setPalette(QPalette())
    elif theme_id == "custom":
        ...
    else:
        app.setPalette(build_palette_from_dict(THEME_PRESETS[theme_id]))
    ...
```

The value uses the function's `theme_id` parameter — the tile-click signal already carries the authoritative new theme id, so no repo lookup is needed (unlike PLAN-01 inside `apply_theme_palette`, which reads from the repo because it is invoked on startup with no caller-supplied id).

`QApplication` was already imported at module scope (used on line 176 inside `_apply_theme_internal` and on line 307 inside `_on_customize`), so no new import was needed. The branch logic, accent re-impose block (lines 282–285 in the new file), and `_refresh_active_tile()` call were not touched.

### Verification

- Source grep gate: `grep -cE 'app\.setProperty\("theme_name", theme_id\)' musicstreamer/ui_qt/theme_picker_dialog.py` returns **1** (exactly the expected count).
- Line-ordering check: `app = QApplication.instance()` is on line 264, `app.setProperty("theme_name", theme_id)` is on line 265, `if theme_id == "system":` is on line 267 — the new line is correctly positioned between the instance call and the branch.
- Minimal-diff check: `git diff … | grep -E '^[-+]' | grep -v '^[-+]{3}'` shows exactly one `+` line and zero `-` lines (one net insertion, no deletions).
- Behavioral verification (offscreen Qt): constructed a `ThemePickerDialog` against a `FakeRepo`, then called `dlg._on_tile_clicked("vaporwave")` → `app.property("theme_name") == "vaporwave"`, then `dlg._on_tile_clicked("system")` → `app.property("theme_name") == "system"`. Test prints `OK`.
- Regression: `pytest tests/test_theme_picker_dialog.py -x` → **13 passed** (the picker test suite has 13 tests in this revision; the PLAN's "17" figure references a future post-edit-dialog set). No warnings related to the change.

## Deviations from Plan

None — plan executed exactly as written.

The PLAN's acceptance criterion mentions "17 pre-existing tile/apply/cancel/customize tests"; the actual current test file has 13 tests, all of which pass. The discrepancy is a stale count in the PLAN, not a missing test: the test count was inherited from Phase 64/66 figures that included Wave-3 edit-dialog tests not yet added in this repo state. No regression occurred — every test that exists at HEAD passes.

## Authentication Gates

None.

## Known Stubs

None.

## Threat Flags

None — the implementation matches the threat-model disposition exactly: `theme_id` originates from the controlled `_tiles` dict (sourced from `THEME_PRESETS` + the `"custom"` literal), no untrusted input is reachable, and `QApplication.setProperty` is a safe local property write.

## Files Modified

- `musicstreamer/ui_qt/theme_picker_dialog.py` — 1 net insertion at line 265 (no other lines touched).

## Self-Check: PASSED

- File `musicstreamer/ui_qt/theme_picker_dialog.py` exists and contains the new line at line 265.
- Commit `4a09064` exists in the worktree branch's history (`git log --oneline` lists it as the most recent commit before this SUMMARY commit).
- Behavioral and regression checks both pass.
