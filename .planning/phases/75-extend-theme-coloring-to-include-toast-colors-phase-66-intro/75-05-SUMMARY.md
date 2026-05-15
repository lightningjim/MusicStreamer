---
phase: 75
plan: 05
subsystem: theme
tags: [theme, editor, qpalette, wave-2]
dependency_graph:
  requires:
    - "75-01: EDITABLE_ROLES extended to 11 (ToolTipBase, ToolTipText appended)"
  provides:
    - "ROLE_LABELS has 11 entries; new keys map to 'Toast background' / 'Toast text' (UI-SPEC LOCKED)"
    - "ThemeEditorDialog auto-renders 11 _ColorRow instances (no KeyError on the new roles)"
    - "_on_role_color_changed flips app.setProperty('theme_name', 'custom') on first role edit"
  affects:
    - tests/test_theme_editor_dialog.py
    - tests/test_theme_picker_dialog.py
tech_stack:
  added: []
  patterns:
    - "Additive ROLE_LABELS dict extension (UI-SPEC §Copywriting Contract LOCKED)"
    - "QApplication.setProperty('theme_name', 'custom') mirror inside editor slot (RESEARCH §Risk 8 mitigation)"
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/theme_editor_dialog.py
decisions:
  - "Consolidated the existing app = QApplication.instance() lookup to the top of _on_role_color_changed (single call site) instead of leaving a duplicate further down. PLAN.md explicitly allows either form (minimal-diff or hoist); chose hoist for cleanliness — net effect is one fewer QApplication.instance() call per slot invocation."
  - "Placed app.setProperty('theme_name', 'custom') BEFORE the _is_valid_hex defense return so the property flips even on malformed-hex edits — defensive: a user who somehow triggers the slot with bad input still has their editor session correctly tagged as 'custom' in the running QApplication property. No behavioral conflict: the rest of the slot still early-returns on invalid hex."
metrics:
  duration_seconds: 165
  tasks_completed: 2
  files_modified: 1
  completed_date: 2026-05-15
---

# Phase 75 Plan 05: theme_editor_dialog.py row labels — Wave 2 Summary

Added the two locked UI-SPEC labels (`ToolTipBase` → `Toast background`, `ToolTipText` → `Toast text`) to `ROLE_LABELS` so the editor's existing `EDITABLE_ROLES` iteration auto-grows from 9 to 11 `_ColorRow` instances without a `KeyError`, and wired `app.setProperty("theme_name", "custom")` into `_on_role_color_changed` to mitigate RESEARCH §Risk 8 (toast retints correctly when the user enters the editor from `theme='system'`).

## Objective

Two minimal additive edits to `musicstreamer/ui_qt/theme_editor_dialog.py`:
1. Append two key-value pairs to `ROLE_LABELS` so the editor's row-layout loop at lines 161-167 (which iterates `EDITABLE_ROLES` and looks up labels via `ROLE_LABELS[role_name]`) finds the new keys.
2. Set `app.setProperty("theme_name", "custom")` at the top of `_on_role_color_changed` so the toast widget's QSS branch retints to the in-progress palette when editing starts from `theme='system'`.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Append `"ToolTipBase": "Toast background"` and `"ToolTipText": "Toast text"` to ROLE_LABELS | `0617422` | musicstreamer/ui_qt/theme_editor_dialog.py |
| 2 | Set `app.setProperty("theme_name", "custom")` in `_on_role_color_changed` (RESEARCH §Risk 8) | `c34a752` | musicstreamer/ui_qt/theme_editor_dialog.py |

## Implementation Details

### Task 1 — ROLE_LABELS extension (UI-SPEC LOCKED)

Appended two key-value pairs after the existing `"Link": "Hyperlink"` entry inside the `ROLE_LABELS` dict (lines 37-49):

```python
"ToolTipBase": "Toast background",
"ToolTipText": "Toast text",
```

- Existing 9 entries preserved verbatim ("Window background", "Window text", ..., "Hyperlink").
- Labels use the app's term **Toast** over Qt's role-name term **ToolTip**, per UI-SPEC §Copywriting Contract (lines 215-223).
- Labels exactly `Toast background` and `Toast text` (single-word "Toast", lowercase second word, NO ellipsis, NO trailing colon — the swatch tooltip and dialog title are auto-derived elsewhere via `f"Edit {role_label}…"` at `_ColorRow.__init__` and `f"Choose {self._role_label} color"` at `_on_swatch_clicked`).
- Dict now has exactly 11 entries.
- Layout code at lines 161-167 unchanged — the loop iterates `EDITABLE_ROLES` (which PLAN-01 already grew to 11) and the new label entries fill the lookup that previously would have raised `KeyError`.

### Task 2 — _on_role_color_changed property mirror (RESEARCH §Risk 8)

Inserted two lines at the top of `_on_role_color_changed` (before any defense-in-depth return or palette mutation):

```python
app = QApplication.instance()
app.setProperty("theme_name", "custom")
```

The pre-existing `app = QApplication.instance()` line was moved up from inside the slot body to consolidate to a single retrieval (PLAN.md explicitly permitted either form). The `app.setProperty` call is now the first effect of the slot — it fires on every role edit, including the very first one when the user has entered the editor from `theme='system'`.

Rationale (RESEARCH §Risk 8): a user who picks `theme='system'`, then opens Customize…, then edits a row, would otherwise leave `app.property("theme_name") == "system"`. The `ToastOverlay` widget (PLAN-03) reads that property to branch its QSS — `"system"` → legacy dark-grey, anything else → palette-driven. Without this property flip, the toast preview lies about what the user is editing. With it, the next-fired (and currently-visible) toast retints to the in-progress palette as soon as the user makes their first role edit.

I deliberately placed `setProperty` BEFORE the `_is_valid_hex(new_hex)` defense return, so the property is updated even if the slot somehow receives malformed hex — a no-op for the palette but a correct state for the QApplication property. The rest of the slot (signature, `_role_hex_dict` update, `app.setPalette()`, accent re-impose) is unchanged.

## Verification Results

All acceptance criteria from PLAN.md tasks 1 and 2 pass:

- **Task 1 inline asserts (Python):** `ROLE_LABELS["ToolTipBase"] == "Toast background"`, `ROLE_LABELS["ToolTipText"] == "Toast text"`, `ROLE_LABELS["Window"] == "Window background"` (unchanged), `ROLE_LABELS["Link"] == "Hyperlink"` (unchanged), `len(ROLE_LABELS) == 11`.
- **Task 1 grep gates:** `grep -c '"Toast background"' musicstreamer/ui_qt/theme_editor_dialog.py` → 1; `grep -c '"Toast text"' musicstreamer/ui_qt/theme_editor_dialog.py` → 1.
- **Task 1 import smoke:** `python -c "from musicstreamer.ui_qt.theme_editor_dialog import ThemeEditorDialog"` succeeds (no `KeyError`).
- **Task 2 grep gate:** `grep -cE 'app\.setProperty\("theme_name", "custom"\)' musicstreamer/ui_qt/theme_editor_dialog.py` → 1.
- **Task 2 behavior test (headless, QT_QPA_PLATFORM=offscreen):** starting from `app.setProperty('theme_name', 'system')`, instantiating the editor with `source_preset='vaporwave'` and calling `dlg._on_role_color_changed('Window', '#abcdef')` results in `app.property('theme_name') == 'custom'`. Passed.
- **Regression — editor tests:** `pytest tests/test_theme_editor_dialog.py -x -k "not 9_color"` → 13 passed, 1 deselected (the 9-row test is owned by PLAN-07 retrofit, per RESEARCH §7 wave structure).
- **Regression — wider theme suite:** `pytest tests/test_theme.py tests/test_theme_editor_dialog.py -x -k "not 9_color and not test_gbs_preset_locked_hex_match and not test_all_presets_cover_9_roles"` → 32 passed, 3 deselected (all three deselected tests are explicitly anticipated by PLAN-01 SUMMARY and owned by PLAN-06's "_11_roles" retrofit).

## Deviations from Plan

None — both tasks landed in single atomic commits with no auto-fix activity, no checkpoint escalations, no authentication gates, and no architectural changes.

The only judgment call permitted by PLAN.md was Task 2's "duplicate `QApplication.instance()` is acceptable; alternatively, hoist the existing retrieval to the top — minimal-diff preferred." I chose to hoist (consolidate to a single call) because the slot is small enough that having two `app = QApplication.instance()` reads within ~15 lines reads worse than a single one. Net diff is +10/-2 lines on the slot body, well within minimal-diff territory.

## Known Stubs

None. Both edits are concrete data values (string literals from the UI-SPEC LOCKED copywriting contract; one literal `"custom"` for the property setter). No placeholders, no TODOs, no empty handlers introduced.

## Threat Flags

None. The threat register entry `T-75-07` (Tampering — V5 N/A) covers both edits: ROLE_LABELS values are dialog-local string literals (no user input flows into the dict); the setProperty value is the literal `"custom"` (no external input). RESEARCH §Security Domain confirms V5 only applies at the `theme_custom` JSON consumption boundary in `theme.py` (covered by PLAN-01's threat model), not at the editor's UI labels or property mirror.

## Self-Check: PASSED

- File `musicstreamer/ui_qt/theme_editor_dialog.py` modified at HEAD: FOUND
- Commit `0617422` (Task 1): FOUND in `git log --oneline` (`feat(75-05): append ToolTipBase/ToolTipText to ROLE_LABELS`)
- Commit `c34a752` (Task 2): FOUND in `git log --oneline` (`feat(75-05): flip theme_name to 'custom' in _on_role_color_changed`)
- Both commits live on branch `worktree-agent-acc6fc70a0d6603b3` based on `28fcbc1` (Wave 1 merge).
- ROLE_LABELS verified to contain 11 entries via runtime import: PASSED.
- setProperty grep gate (exactly 1 occurrence): PASSED.
- Editor dialog imports without KeyError: PASSED.
- Behavior test (system → custom flip): PASSED.
- Regression test suite (editor dialog, non-deselected): 13/13 PASSED.
