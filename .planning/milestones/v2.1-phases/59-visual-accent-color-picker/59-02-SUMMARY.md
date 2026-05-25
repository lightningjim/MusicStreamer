---
phase: 59-visual-accent-color-picker
plan: 02
subsystem: ui
tags:
  - ui
  - dialog
  - qcolordialog
  - accent-color
  - rewrite
  - green-state
  - wave-1
  - pyside6

requires:
  - phase: 59-01
    provides: 9-test TDD-RED contract in tests/test_accent_color_dialog.py targeting self._inner / self._current_hex; FakeRepo + qtbot fixtures
  - phase: 19
    provides: Accent palette helpers (build_accent_qss, apply_accent_palette, reset_accent_palette, _is_valid_hex) in accent_utils.py — reused as-is (D-19)
  - phase: 40
    provides: Snapshot/restore palette pattern + bound-method connect convention; AccentColorDialog public API surface (D-08)

provides:
  - Visual color picker via Qt's stock QColorDialog (HSV wheel + sat/val square + numeric R/G/B/H/S/V + hex field + screen-color eyedropper)
  - 8 ACCENT_PRESETS seeded into Custom Colors slots 0..7 on every dialog open (D-03 idempotent reseed)
  - Live preview via currentColorChanged → apply_accent_palette (no throttle)
  - Phase 19/40 snapshot/restore invariant preserved (cancel/X/Esc all restore the snapshot palette + QSS)
  - Apply | Reset | Cancel button row with Apply as default (Enter→Apply)
  - Public API (AccentColorDialog(repo, parent=None)) preserved verbatim — main_window.py:53 + 680-682 untouched
  - All 9 Plan-01 RED tests turn GREEN; 18 accent_provider tests continue to pass unchanged

affects:
  - Phase 66 (color themes — Highlight layering): Reset semantics (clear accent_color setting + restore snapshot) is exactly the layering contract documented in 66-DISCUSS-CHECKPOINT.json — Phase 66's theme Highlight will be the snapshot when Phase 59 ships before Phase 66
  - Plan 59-03 (UAT): visual color picker, eyedropper-on-Linux-X11, drag-flicker observation, cross-restart persistence — all gated to Plan 03's manual UAT

tech-stack:
  added: [PySide6.QtWidgets.QColorDialog (first use in this codebase)]
  patterns:
    - "Wrapper QDialog hosting a complex Qt widget via NoButtons + DontUseNativeDialog (Pattern (b) from D-07; recommended path in CONTEXT.md)"
    - "Static-method process-static seeding (QColorDialog.setCustomColor) called BEFORE inner construction (Pitfall 1 ordering)"
    - "Pitfall 6 wire-order workaround: set _current_hex manually in __init__ to maintain post-init invariant when setCurrentColor predates the connect"
    - "Pitfall 3 color-flash guard: _is_valid_hex defensive check before passing saved hex to QColor(...) — fall back to ACCENT_COLOR_DEFAULT for corrupt repo state"
    - "blockSignals around setCurrentColor in Reset to prevent the slot from re-clobbering _current_hex = '' after the visual reset"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/accent_color_dialog.py — rewritten (235 LOC → 156 LOC)

key-decisions:
  - "D-07 wrapper QDialog (Pattern b) over QColorDialog subclass (Pattern a): wrapper avoids reaching into QColorDialog's private layout to inject a Reset button — brittle across Qt minor versions"
  - "D-15.6 chosen variant: write empty string to paths.accent_css_path() on Reset (over os.remove or leave-alone). Predictable, idempotent, prevents stale QSS on next startup before re-Apply"
  - "D-11 Claude's Discretion: ship with no QTimer throttle on currentColorChanged. apply_accent_palette is cheap (palette swap + 1-line setStyleSheet). Promote to QTimer.singleShot(50, ...) only if Plan 03 UAT reports flicker on Linux X11 DPR=1.0"

patterns-established:
  - "Wrapper-around-stock-Qt-widget shape: QDialog hosts QColorDialog (NoButtons | DontUseNativeDialog) with own QDialogButtonBox; pattern reusable for future Qt-stdlib-dialog wrappers (e.g., custom QFontDialog wrapper)"
  - "Custom Colors slot seeding: idempotent reseed of process-static state in every __init__ rather than at app startup — testable, predictable, resilient to user edits within session"
  - "Pitfall 6 invariant pattern: when an init-time emission predates the slot connect, set the tracking field manually so post-init invariants hold"

requirements-completed:
  - ACCENT-02

duration: 9 min
completed: 2026-05-04
---

# Phase 59 Plan 02: Visual Accent Color Picker (TDD-GREEN) Summary

**Rewrote AccentColorDialog as a wrapper QDialog hosting an embedded QColorDialog (NoButtons | DontUseNativeDialog) — full HSV wheel + sat/val square + R/G/B/H/S/V fields + hex field + screen-color eyedropper — with 8 ACCENT_PRESETS seeded into Custom Colors slots 0..7. Phase 19/40 snapshot/restore invariant preserved verbatim; public API unchanged so main_window.py is untouched.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-05-04T00:55:31Z
- **Completed:** 2026-05-04T01:04:31Z
- **Tasks:** 1 (single rewrite task)
- **Files modified:** 1 (musicstreamer/ui_qt/accent_color_dialog.py: 235 LOC → 156 LOC, -159/+80)

## Accomplishments

- All 9 Plan-01 RED tests turn GREEN (TDD-RED → TDD-GREEN transition)
- 18 accent_provider tests continue to pass unchanged (D-19 invariant verified — accent_utils.py untouched)
- 235 LOC → 156 LOC (-79 LOC); legacy swatch grid + hex QLineEdit + `_select_swatch`/`_deselect_all_swatches`/`_on_swatch_clicked`/`_on_hex_changed` deleted
- Eyedropper "Pick Screen Color" now available (free under DontUseNativeDialog) — was impossible with the legacy 8-preset + hex dialog
- Public API surface (`from musicstreamer.ui_qt.accent_color_dialog import AccentColorDialog` at main_window.py:53; `AccentColorDialog(repo, parent=self).exec()` at main_window.py:680-682) unchanged
- All 14 UI-SPEC audit-hook grep predicates pass (see Self-Check below)

## Task Commits

1. **Task 1: Rewrite musicstreamer/ui_qt/accent_color_dialog.py per Pattern 1** — `4b1d74e` (feat)

## Files Created/Modified

- `musicstreamer/ui_qt/accent_color_dialog.py` — Rewritten as wrapper QDialog (235 LOC → 156 LOC). Hosts `self._inner = QColorDialog(self)` with NoButtons | DontUseNativeDialog | ShowAlphaChannel=False. Seeds ACCENT_PRESETS into Custom Colors slots 0..7 BEFORE inner construction. Bound-method connect on currentColorChanged → `_on_color_changed`. Apply | Reset | Cancel button row; Apply has setDefault(True). Phase 19/40 snapshot/restore invariant preserved verbatim in `__init__` + `reject()`. Reset uses `blockSignals(True)` around `setCurrentColor(QColor(ACCENT_COLOR_DEFAULT))` then sets `self._current_hex = ""` and writes empty string to paths.accent_css_path() (D-15.6 chosen variant). All 14 UI-SPEC audit predicates verified.

## Decisions Made

- **D-07 wrapper-vs-subclass:** shipped Pattern (b) wrapper QDialog (recommended path in CONTEXT.md). Subclass (Pattern a) would require reaching into QColorDialog's private layout to inject the Reset button — brittle across Qt minor versions.
- **D-15.6 QSS-file cleanup:** chose "write empty string to paths.accent_css_path()" over `os.remove(...)` (less predictable across OSes — Windows file locks, etc.) and over leave-alone (would leave a stale QSS file on disk that main_window.py:189-192 would re-apply on next startup if accent_color setting were somehow re-set externally). Empty string is idempotent and explicit.
- **D-11 throttle alternative:** shipped with NO throttle. `apply_accent_palette` is cheap (palette swap + 1-line `setStyleSheet`); Qt batches repaints; QColorDialog only emits during user interaction. **If Plan 03 UAT observes visible flicker on Linux X11 DPR=1.0**, promote `_on_color_changed` body to `QTimer.singleShot(50, lambda: apply_accent_palette(QApplication.instance(), self._current_hex))`. Until UAT signals flicker, no QTimer is added.

## Deviations from Plan

None — plan executed exactly as written. The locked code skeleton from RESEARCH.md §"Construct + embed + wire (the locked Phase 59 shape)" + the pattern recipes in PATTERNS.md §AccentColorDialog REWRITE were both copied verbatim. The only minor adjustment was trimming verbose comments to bring LOC into the 80-160 target range (final 156 LOC fits comfortably, accommodating the chosen D-15.6 file-write variant).

## Issues Encountered

- **Audit predicate #2 false positive on first attempt:** initial commentary line included the literal string "do NOT call setMinimumWidth(360)" which matched `grep -cE 'setMinimumWidth'`. Rephrased to "do NOT set a minimum width" to satisfy the predicate without losing the Pitfall 7 context. **Resolution:** trivial wording edit; predicate now returns 0.
- **3 mpris2 test failures appear in full-suite run order** (`test_linux_mpris_backend_publish_metadata`, `test_linux_mpris_backend_publish_metadata_none`, `test_linux_mpris_backend_set_playback_state`). Verified pre-existing test-isolation bug — running `pytest tests/test_main_window_integration.py::test_accent_loaded_on_startup tests/test_media_keys_mpris2.py` reproduces the same 7-failure pattern on the BASELINE (Plan 01) commit, so this is unrelated to Phase 59. mpris2 tests pass cleanly in isolation. Logged as out-of-scope (test-suite global polution; not introduced by Plan 02).

## Test Results

**Plan 01 RED contract turned GREEN:**

```
tests/test_accent_color_dialog.py::test_dialog_seeds_custom_colors_from_presets PASSED
tests/test_accent_color_dialog.py::test_setting_color_emits_signal_and_applies_palette PASSED
tests/test_accent_color_dialog.py::test_apply_persists_to_repo_and_writes_qss PASSED
tests/test_accent_color_dialog.py::test_cancel_restores_palette_and_does_not_save PASSED
tests/test_accent_color_dialog.py::test_reset_clears_setting_and_keeps_dialog_open PASSED
tests/test_accent_color_dialog.py::test_window_close_behaves_like_cancel PASSED
tests/test_accent_color_dialog.py::test_load_saved_accent_pre_selects_in_picker PASSED
tests/test_accent_color_dialog.py::test_corrupt_saved_hex_falls_back_to_default PASSED
tests/test_accent_color_dialog.py::test_currentColorChanged_drives_live_preview_via_bound_method PASSED
========================= 9 passed, 1 warning in 0.19s =========================
```

**D-19 verification (accent_utils.py untouched):**

```
tests/test_accent_provider.py::test_valid_hex_6digit PASSED  ... (18 tests)
======================== 18 passed, 1 warning in 0.10s =========================
```

`git diff --stat HEAD~1 musicstreamer/accent_utils.py musicstreamer/constants.py musicstreamer/paths.py` returns no output — D-19 invariant verified.

**Full suite delta:** baseline (Plan 01 commit) had 13 failures (9 RED + 4 pre-existing). Current state has 7 failures (0 RED + 7 pre-existing test-ordering issues — same root cause as baseline's `test_linux_mpris_backend_constructs` polluted-by-earlier-test pattern). **No new failures introduced by Plan 02.**

## UI-SPEC Audit-Hook Grep Predicates Verified

| # | Predicate | Expected | Actual | Pass |
|---|-----------|----------|--------|------|
| 1 | `setContentsMargins\(8, 8, 8, 8\)` | 1 | 1 | ✓ |
| 2 | `setMinimumWidth` | 0 | 0 | ✓ |
| 3 | `setOption\(.*NoButtons, True\)` | 1 | 1 | ✓ |
| 4 | `setOption\(.*DontUseNativeDialog, True\)` | 1 | 1 | ✓ |
| 5 | `setOption\(.*ShowAlphaChannel, False\)` | 1 | 1 | ✓ |
| 6 | `connect\(lambda` | 0 | 0 | ✓ |
| 7 | `currentColorChanged\.connect\(self\._on_color_changed\)` | 1 | 1 | ✓ |
| 8 | `QFont\|setPointSize\|setWeight` | 0 | 0 | ✓ |
| 9 | `"#rrggbb"` (legacy placeholder) | 0 | 0 | ✓ |
| 10 | `setWindowTitle\("Accent Color"\)` | 1 | 1 | ✓ |
| 11 | `setDefault\(True\)` | 1 | 1 | ✓ |
| 12 | `class AccentColorDialog\(QDialog\)` | 1 | 1 | ✓ |
| 13 | `def __init__\(self, repo, parent=None\)` | 1 | 1 | ✓ |
| 14 | `enumerate\(ACCENT_PRESETS\)` | 1 | 1 | ✓ |
| 15 | `self\._inner\.blockSignals\(True\)` | 1 | 1 | ✓ |
| 16 | `if not self\._current_hex or not _is_valid_hex\(self\._current_hex\)` | 1 | 1 | ✓ |
| 17 | `def reject\(self\)` | 1 | 1 | ✓ |
| 18 | `app\.setPalette\(self\._original_palette\)` | 1 | 1 | ✓ |
| 19 | `reset_accent_palette\(QApplication\.instance\(\), self\._original_palette\)` | 1 | 1 | ✓ |
| 20 | `paths\.accent_css_path\(\)` | ≥1 | 2 | ✓ |
| 21 | `addButton\("(Apply\|Reset\|Cancel)"` | 3 | 3 | ✓ |
| 22 | `_swatches\|_hex_edit\|_on_swatch_clicked\|_on_hex_changed\|_select_swatch\|_deselect_all_swatches` | 0 | 0 | ✓ |
| 23 | Pitfall 1 ordering (`setCustomColor` line < `QColorDialog(self)` line) | True | True | ✓ |
| 24 | LOC | 80–160 | 156 | ✓ |
| 25 | Import smoke test (`AccentColorDialog.__init__.__qualname__`) | OK | OK | ✓ |

All 25 audit predicates pass.

## User Setup Required

None — no external service configuration. The rewrite is a pure code change touching one file; no schema migration, no env vars, no auth flow.

## Next Phase Readiness

- **Plan 03 (UAT) ready to execute.** All 9 unit tests are GREEN, public API preserved, audit predicates green. Plan 03 will perform manual visual UAT covering: (a) eyedropper grabs cross-app pixel correctly on Linux X11; (b) drag through hue ring shows smooth live preview without flicker; (c) Reset visually returns picker + app accent to default blue within 1 frame; (d) cross-restart persistence via accent_color SQLite key + paths.accent_css_path() on-disk QSS file; (e) the 8 Custom Colors slots show ACCENT_PRESETS verbatim.
- **D-11 throttle alternative documented** for Plan 03 to revisit only if real-world flicker is observed.
- **D-15.6 QSS-file cleanup choice (write empty)** documented for Plan 03 to validate (Reset → close app → restart → verify accent restored to system theme's default highlight; if a stale colored highlight appears, the empty-file write is failing).
- **Phase 66 forward-compat preserved.** Reset semantics (clear `accent_color` setting only — never write a non-empty default) is the exact contract Phase 66 expects per 66-DISCUSS-CHECKPOINT.json. No regression risk for the upcoming theme-system layering.

## Self-Check: PASSED

- File `musicstreamer/ui_qt/accent_color_dialog.py` exists (verified via wc -l = 156 lines).
- Commit `4b1d74e` exists in git log (verified via `git rev-parse --short HEAD`).
- All 9 dialog tests pass (verified above).
- All 18 accent_provider tests pass (verified above; D-19 invariant).
- All 25 UI-SPEC audit predicates pass (verified above).

---
*Phase: 59-visual-accent-color-picker*
*Completed: 2026-05-04*
