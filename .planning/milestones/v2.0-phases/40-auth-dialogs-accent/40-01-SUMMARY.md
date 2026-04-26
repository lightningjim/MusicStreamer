---
phase: 40-auth-dialogs-accent
plan: "01"
subsystem: accent-color
tags: [accent, qss, palette, dialog, ui]
dependency_graph:
  requires: []
  provides: [build_accent_qss, apply_accent_palette, reset_accent_palette, AccentColorDialog]
  affects: [musicstreamer/ui_qt/accent_color_dialog.py, musicstreamer/accent_utils.py]
tech_stack:
  added: []
  patterns: [QPalette.Highlight override for per-widget QSS palette(highlight) resolution, functools.partial for swatch click safety]
key_files:
  created:
    - musicstreamer/ui_qt/accent_color_dialog.py
    - tests/test_accent_color_dialog.py
  modified:
    - musicstreamer/accent_utils.py
    - tests/test_accent_provider.py
decisions:
  - QPalette.Highlight override chosen over global QSS for chip/seg selectors because per-widget setStyleSheet() has higher specificity than QApplication.setStyleSheet()
  - build_accent_qss targets only QSlider::sub-page:horizontal in global QSS; all other accent uses resolve via palette(highlight)
  - functools.partial used for swatch clicked connections to avoid lambda GC/closure issues (QA-05)
metrics:
  duration: 18min
  completed: 2026-04-13
  tasks: 2
  files_changed: 4
---

# Phase 40 Plan 01: Accent Color Dialog Summary

One-liner: AccentColorDialog with 8 preset swatches, live QPalette.Highlight preview, hex entry validation, and SQLite persistence via apply/reset_accent_palette helpers.

## What Was Built

**Task 1 — build_accent_qss + palette helpers** (957171f)

Added three functions to `musicstreamer/accent_utils.py`:

- `build_accent_qss(hex_value)` — QSS string for `QSlider::sub-page:horizontal`. Validates hex via `_is_valid_hex` before interpolation (T-40-01 mitigated). Returns empty string for invalid input.
- `apply_accent_palette(app, hex_value)` — sets `QPalette.ColorRole.Highlight` to `QColor(hex_value)`, `HighlightedText` to white, and applies slider QSS via `app.setStyleSheet()`.
- `reset_accent_palette(app, original_palette)` — restores palette and clears QSS.

4 new tests added to `tests/test_accent_provider.py`; all 18 tests pass.

**Task 2 — AccentColorDialog** (0717da1)

Created `musicstreamer/ui_qt/accent_color_dialog.py`:

- `AccentColorDialog(repo, parent=None)` — modal QDialog, min width 360px
- 4×2 swatch grid (8 `QPushButton` instances, 32×32px, stored in `self._swatches`)
- Hex entry (`QLineEdit`, maxLength=7) with live validation — invalid input shows red border, no QSS applied (T-40-02 mitigated)
- `QDialogButtonBox` with Apply/Reset/Cancel
- `_preview()` calls `apply_accent_palette()` on valid swatch click or hex change
- Apply: `repo.set_setting("accent_color", hex)` + writes `accent_css_path()` + `accept()`
- Reset: `repo.set_setting("accent_color", "")` + `reset_accent_palette()` + deselect swatches
- Cancel: restores `_original_palette` + `_original_qss` via `reject()` override
- Pre-loads saved accent on open: populates hex entry, selects matching swatch

8 tests in `tests/test_accent_color_dialog.py`; all pass.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Mitigations Applied

| Threat | Mitigation |
|--------|-----------|
| T-40-01: hex injection into build_accent_qss | `_is_valid_hex()` guards interpolation; returns "" on invalid |
| T-40-02: hex QLineEdit in dialog | `_on_hex_changed` calls `_is_valid_hex()` before `_preview()`; red border shown, no QSS applied |

## Known Stubs

None — all data wired to FakeRepo/real Repo.

## Threat Flags

None — no new network endpoints or trust boundaries introduced.

## Self-Check: PASSED

- musicstreamer/accent_utils.py: FOUND (def build_accent_qss, def apply_accent_palette, def reset_accent_palette)
- musicstreamer/ui_qt/accent_color_dialog.py: FOUND (class AccentColorDialog)
- tests/test_accent_color_dialog.py: FOUND (test_apply_saves_setting, test_dialog_has_8_swatches)
- Commits: 957171f (task 1), 0717da1 (task 2) — both present in git log
