---
phase: 54-station-logo-aspect-ratio-fix
fixed_at: 2026-04-30T15:25:04-05:00
review_path: .planning/phases/54-station-logo-aspect-ratio-fix/54-REVIEW.md
iteration: 1
fix_scope: critical_warning
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 54: Code Review Fix Report

**Fixed at:** 2026-04-30T15:25:04-05:00
**Source review:** `.planning/phases/54-station-logo-aspect-ratio-fix/54-REVIEW.md`
**Iteration:** 1
**Scope:** critical_warning (CR-* + WR-*; IN-* deferred)

## Summary

- Findings in scope: 8 (1 Critical + 7 Warning)
- Fixed: 8
- Skipped: 0
- Test status after all fixes: **14 passed** (`tests/test_art_paths.py` 9/9 + `tests/test_station_star_delegate.py` 5/5)
  - Suite count dropped by 1 (was 6, now 5) due to WR-07 deleting a tautological test by design.

All in-scope findings were fixed in atomic commits, each with its own targeted test re-run. The fixes were applied per the `<config>` instructions on the foreground prompt — no fixes required adaptation away from the proposed approach. WR-04 (and WR-07's deletion) materially improved test integrity; WR-01 and WR-02 hardened the `paint` and `sizeHint` contracts.

## Fixed Issues

### CR-01: HiDPI device-pixel-ratio dropped on canvas

**Files modified:** `musicstreamer/ui_qt/_art_paths.py`
**Commit:** `c3ee6ce`
**Applied fix:** Added one-line `pix.setDevicePixelRatio(scaled.devicePixelRatio())` between the `QPixmap(size, size)` allocation and `pix.fill(Qt.transparent)`. Carries the source pixmap's DPR onto the canvas so QIcon does not nearest-neighbor up-scale on HiDPI displays. Smallest-diff variant per finding's "Fix (smallest diff)" path; preserves existing centering math (no coordinate-space change). Inline comment cites WR-01 source rationale and Phase 54 review.
**Verification:** `pytest tests/test_art_paths.py -x` → 9/9 green.

### WR-01: Redundant `initStyleOption` re-call in delegate paint

**Files modified:** `musicstreamer/ui_qt/station_star_delegate.py`
**Commit:** `846c859`
**Applied fix:** Removed `self.initStyleOption(option, index)` from the `paint()` station-row branch. Rephrased the inline comment to explain that Qt has already populated `option` (selected/hover/focus state) before `paint()` is invoked, so direct mutation of `option.decorationSize` and `option.decorationAlignment` is sufficient — the previous re-call would have clobbered view-supplied state.
**Verification:** `pytest tests/test_station_star_delegate.py -x` → 6/6 green at the time of this commit.

### WR-02: Provider-row floor coupled to STATION_ICON_SIZE

**Files modified:** `musicstreamer/ui_qt/station_star_delegate.py`, `tests/test_station_star_delegate.py`
**Commit:** `06bde21`
**Applied fix:** Introduced module-private `_PROVIDER_TREE_MIN_ROW_HEIGHT = 32` constant near `_STAR_SIZE` / `_STAR_MARGIN`, with a multi-line comment documenting the `setUniformRowHeights(True)` dependency. `sizeHint` now branches: station rows continue to floor at `STATION_ICON_SIZE`; provider rows floor at `_PROVIDER_TREE_MIN_ROW_HEIGHT`. Updated `tests/test_station_star_delegate.py` to import the new constant and assert the provider-row floor against it (instead of `STATION_ICON_SIZE`), de-coupling the test contract too. The asserted floor value remains 32 (per fixer instructions).
**Verification:** `pytest tests/test_station_star_delegate.py -x` → 6/6 green at the time of this commit.

### WR-03: Stale docstring overstating cache-key dedup

**Files modified:** `musicstreamer/ui_qt/_art_paths.py`
**Commit:** `3ef6715`
**Applied fix:** Weakened the docstring claim in `load_station_icon`. Removed the absolute statement that "the same logo referenced as relative vs. absolute hits the same cache entry"; replaced with a more accurate statement noting that paths are joined via `os.path.join` but **not canonicalized** (no `normpath`/`realpath`), so callers passing a non-canonical relative form may not hit a previously-cached canonical entry. Code behavior unchanged (per scope: docstring-only fix).
**Verification:** `pytest tests/test_art_paths.py -x` → 9/9 green.

### WR-04: Brittle QImage equality test

**Files modified:** `tests/test_art_paths.py`
**Commit:** `e07b998`
**Applied fix:** Replaced the `loaded_pix.toImage() != fallback_pix.scaled(...).toImage()` assertions in two tests (`test_relative_station_art_path_resolves_via_abs_art_path` and `test_absolute_path_passes_through_unchanged`) with center-pixel red-color checks. The fixture's `_write_logo` paints `Qt.red` onto the saved PNG, so a center pixel with `red() > 200`, `green() < 50`, and `blue() < 50` confirms the real fixture loaded (not the fallback icon, which has different colors). This positively asserts what the equality check was trying (and post-Plan-04 failing) to prove. The previous-style `FALLBACK_ICON` import is left in place; pruning unused imports is an info-tier cleanup outside this commit's scope.
**Verification:** `pytest tests/test_art_paths.py -x` → 9/9 green.

### WR-05: O(n²) scan + null guard in `_non_transparent_bbox`

**Files modified:** `tests/test_art_paths.py`
**Commit:** `53d90d0`
**Applied fix:** Added two assertions at the top of `_non_transparent_bbox`: `assert not pix.isNull(), "_non_transparent_bbox requires a non-null pixmap"` and `assert pix.width() <= 64 and pix.height() <= 64, "_non_transparent_bbox is O(n^2); not for large pixmaps"`. Expanded the docstring to explicitly call out the O(n²) cost and the rationale for the guards. No behavioral change for the existing 32×32-pixmap call sites.
**Verification:** `pytest tests/test_art_paths.py -x` → 9/9 green.

### WR-06: Fragile `__bases__[0]()` instantiation

**Files modified:** `tests/test_station_star_delegate.py`
**Commit:** `4e94911`
**Applied fix:** Imported `QStyledItemDelegate` from `PySide6.QtWidgets` (alongside the existing `QStyleOptionViewItem` import). Replaced `StationStarDelegate.__bases__[0]().sizeHint(option, provider_idx)` with the unbound-method form `QStyledItemDelegate.sizeHint(delegate, option, provider_idx)`. No fresh QObject is allocated, no leaked QObject lifetime, and the test no longer depends on `StationStarDelegate`'s inheritance order.
**Verification:** `pytest tests/test_station_star_delegate.py -x` → 6/6 green at the time of this commit.

### WR-07: Tautological `test_paint_provider_row_does_not_force_decoration_size`

**Files modified:** `tests/test_station_star_delegate.py`
**Commit:** `c1d68e7`
**Applied fix:** Deleted the tautological test. Replaced its body with a multi-line comment explaining the rationale for removal: `super().paint()` internally re-runs `initStyleOption`, which re-derives `decorationSize` from the model — so a snapshot-and-compare would always equal regardless of whether the delegate touched the option. The structural `if isinstance(station, Station)` guard in source enforces the negative case at compile time, and `test_paint_forces_square_decoration_rect` covers the positive station-row case. Test count for this file dropped from 6 to 5 by design.
**Verification:** `pytest tests/test_station_star_delegate.py -x` → 5/5 green.

## Final Suite Run

After all 8 commits:

```
$ pytest tests/test_art_paths.py tests/test_station_star_delegate.py -x
collected 14 items

tests/test_art_paths.py .........                  [ 64%]
tests/test_station_star_delegate.py .....          [100%]

======================== 14 passed, 1 warning in 0.12s =========================
```

The single warning is a pre-existing `gi.overrides` `PyGIDeprecationWarning` unrelated to this work.

## Out of Scope This Run

The following findings were intentionally NOT addressed (Info-tier; deferred per `fix_scope: critical_warning`):

- **IN-01:** Unused `QStyle` import in `station_star_delegate.py`
- **IN-02:** Centralize `_STAR_SIZE` / `_STAR_MARGIN` to `_theme.py`
- **IN-03:** Promote duplicated fixtures to `tests/conftest.py`
- **IN-04:** Inline-document the "D-03" decision tag
- **IN-05:** Reconcile divergent `_make_station` helpers across the two test files

Suggest bundling these into a single follow-up cleanup commit when convenient.

## Notes for Verifier

- **CR-01 logic note:** The DPR fix is the smallest-diff variant; on the project's current Linux X11 deployment with `devicePixelRatio == 1.0` the behavior is unchanged (which is why no test was added — `test_art_paths.py` runs under the offscreen Qt platform plugin at DPR 1.0, and verifying DPR > 1.0 requires HiDPI test rig hardware). The reviewer's "Better long-term" suggestion (allocate at device size) was deliberately skipped — it would force coordinate-space changes to the centering math at lines ~95-96 and is properly a future-phase item.
- **WR-02 design call:** Chose option (a) from the reviewer's two suggestions (introduce a separate constant) over option (b) (just document the coupling). The constant pattern makes the decoupling discoverable in code rather than only in comments and gives future HiDPI work a clean place to live.
- **WR-04 unused import:** `FALLBACK_ICON` is still imported in `tests/test_art_paths.py` after the equality-check removal (it's only referenced in a docstring/comment). Left in place to keep this commit narrowly scoped.

---

_Fixed: 2026-04-30T15:25:04-05:00_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
