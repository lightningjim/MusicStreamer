# Phase 54 — Plan 04 — Path B-2 Delegate Geometry Fix + UAT Re-run

**Date:** 2026-04-30
**Trigger:** Phase 54 VERIFICATION.md status `gaps_found` — Gap 1 (portrait still cropped on Linux X11/Wayland after Plan 03's Path B-1 patch)
**Patch scope:** `musicstreamer/ui_qt/station_star_delegate.py` — `paint()` and `sizeHint()` overrides extended; +1 import
**BUG-05 status:** **BUG-05 CLOSED**

## Patch Summary

- Imports extended: `STATION_ICON_SIZE` from `musicstreamer.ui_qt._theme`.
- `StationStarDelegate.paint` modified: for station rows (where `index.data(Qt.UserRole)` is a `Station`), calls `self.initStyleOption(option, index)` then forces `option.decorationSize = QSize(STATION_ICON_SIZE, STATION_ICON_SIZE)` (32×32) and `option.decorationAlignment = Qt.AlignVCenter | Qt.AlignLeft` BEFORE delegating to `super().paint()`. Provider rows take the super-class default decoration path (no mutation).
- `StationStarDelegate.sizeHint` modified: floors row height at `STATION_ICON_SIZE` (32) for **ALL** rows. Station rows return `QSize(base.width() + _STAR_SIZE + _STAR_MARGIN, max(base.height(), STATION_ICON_SIZE))`; provider rows return `QSize(base.width(), max(base.height(), STATION_ICON_SIZE))`. Both branches floor because `tree.setUniformRowHeights(True)` (set in `station_list_panel.py:279`) probes the FIRST row (a provider) for the whole view's row height — a station-only floor is silently bypassed (BLOCKER #1 fix from plan-checker iteration 1). Provider-row width does NOT include the star reservation, preserving the D-01 invariant at the star-logic level.
- Star-painting tail preserved verbatim — favorite-toggle on the right-edge 20×20 star still works.
- `_art_paths.py` UNCHANGED — D-11 cache-key invariant preserved (cache key string `f"station-logo:{load_path}"` unchanged).
- Plan 03's canvas-paint patch (commit `b1a9088`) UNCHANGED — Path B-2 builds on it, does not replace it. Plan 03's transparent square 32×32 canvas is exactly what the Path B-2 delegate now reliably draws into a 32×32 decoration rect.
- Commits: `0112a9b test(54-04): add failing tests for StationStarDelegate paint+sizeHint geometry`, `af63397 fix(54-04): force square 32x32 decoration rect in StationStarDelegate`.

## New Tests

`tests/test_station_star_delegate.py` (NEW) — 6 behavioral tests covering delegate paint+sizeHint geometry:

- `test_paint_forces_square_decoration_rect` — paint() sets `option.decorationSize == QSize(32, 32)` for station rows.
- `test_paint_forces_left_aligned_decoration` — paint() sets `AlignLeft + AlignVCenter` bits in `option.decorationAlignment` (PySide6 6.11 flag-safe bitwise check).
- `test_sizehint_enforces_min_row_height_32_for_station_rows` — station-row `sizeHint().height() >= 32`.
- `test_sizehint_floors_height_at_32_for_provider_rows` — provider-row `sizeHint().height() >= 32` (BLOCKER #1 fix: `setUniformRowHeights(True)` probes the first row), AND width does NOT include star reservation (D-01 invariant).
- `test_paint_provider_row_does_not_force_decoration_size` — provider rows preserve super-class decorationSize.
- `test_uniform_row_height_applies_floor_with_provider_first_row` — integration test: real `QTreeView` + `StationTreeModel` + `StationStarDelegate` with `setUniformRowHeights(True)` and provider-first model; asserts `tree.visualRect(station_idx).height() >= 32`.

## Test Results

- `pytest tests/test_station_star_delegate.py -x` → **6 / 6 GREEN** (transitioned from 5 RED + 1 negative-pass at Task 1 to 6 / 6 after Task 2 patch).
- `pytest tests/test_art_paths.py -x` → **9 / 9 GREEN** (Plan 01 regression-lock preserved — D-11 invariant honored, Plan 03 canvas contract honored).
- `pytest` (full suite) → **846 passed, 11 failed**. All 11 failures are pre-existing and out-of-scope per `deferred-items.md`. Verified pre-existing by reverting the delegate to `HEAD~1` and re-running affected tests — same failures with the un-patched delegate. **No new regressions introduced by Plan 04.**

## UAT Re-run

| Step | Repro | Pre-B-2 (Plan 03) | Post-B-2 (Plan 04) | Status |
|------|-------|-------------------|--------------------|--------|
| 1 | Synthetic portrait (50×100 red, /tmp/portrait.png) | top + bottom clipped — "acting like landscape for everything" | 16w × 32h pillarboxed, full height visible | ✅ FIXED |
| 2 | Landscape (Living Coffee, id=2 — 1280×720 YouTube thumbnail) | letterboxed correctly | letterboxed correctly (unchanged) | ✅ Preserved |
| 3 | Square baseline (20th Century, id=10 — 1000×1000 AudioAddict) | edge-to-edge | edge-to-edge (unchanged) | ✅ Preserved |
| 4 | Star icon click-toggle | working | working | ✅ Preserved |

## User Verbatim

> approved

UAT performed after a fresh app launch — QPixmapCache flushed by process exit.

## Decisions Honored

- **D-01 (provider-tree scope):** paint+sizeHint overrides only fire on station rows where `index.data(Qt.UserRole)` is a `Station`. Recently Played `QListView`, now-playing 180×180 viewport, and EditStationDialog 64×64 preview NOT touched. ✓
- **D-04 (transparent bars):** No solid-color or theme-derived fill introduced; Plan 03's transparent 32×32 canvas continues to provide the bars. ✓
- **D-05 (edge-to-edge longer axis):** Preserved by Plan 03's canvas centering math (`(size - scaled.width()) // 2`); the delegate now reliably paints the 32×32 canvas into a 32×32 decoration rect with no inset. ✓
- **D-07 (uniform loader):** `_art_paths.py` UNCHANGED — no per-station-type branching introduced. ✓
- **D-09 (smallest-diff escalation):** Modified the EXISTING `StationStarDelegate` via `paint+sizeHint` overrides. NO `setItemDelegateForColumn` introduced; NO second delegate. The escalation from B-1 to B-2 is justified by Plan 03's UAT failure on Linux X11/Wayland — D-09's hierarchy permits B-2 once B-1 is proven insufficient. ✓
- **D-11 (cache key unchanged):** `_art_paths.py` NOT touched. `test_cache_hit_on_second_call` continues to pass. ✓

## Files Modified This Plan

- `musicstreamer/ui_qt/station_star_delegate.py` — `paint()` and `sizeHint()` overrides extended; +1 import (`STATION_ICON_SIZE`).
- `tests/test_station_star_delegate.py` — NEW file with 6 behavioral tests covering delegate paint+sizeHint geometry.

## Evidence

- (kept) `uat-portrait-after.png` — pre-B-2 evidence from Plan 03 (still cropped).
- (kept) `uat-landscape-after.png` — landscape regression baseline, still valid.
- (kept) `uat-evidence.png` — Plan 02 pre-fix baseline.
- `uat-portrait-after-b2.png` — NOT captured. User verified visually and signed off with `approved`; the resume-signal is the primary evidence. Recommend capturing the screenshot at convenience for the visual archive, but not blocking phase closure on it.

## What Closes

- BUG-05 (portrait/landscape cropping in row icon) — **CLOSED**. Both axes verified end-to-end (regression-lock unit tests + delegate geometry tests + live UAT on Linux X11/Wayland).
- Phase 54 Gap 1 — **CLOSED**.

## Phase 54 Status

Phase 54 ready to be marked **COMPLETE**. `54-VERIFICATION.md` updated to `status: pass`. ROADMAP.md Phase 54 entry and REQUIREMENTS.md BUG-05 entry should drop the partial-closure caveat introduced after Plan 03 verification.
