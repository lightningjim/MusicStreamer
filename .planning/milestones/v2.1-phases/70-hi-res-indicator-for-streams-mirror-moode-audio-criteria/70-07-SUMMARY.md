---
phase: 70
plan: "07"
subsystem: ui_qt/station_star_delegate
tags: [tree-row, delegate, paint, qpainter, sizehint, tdd-green, hres-01]
dependency_graph:
  requires:
    - "70-01 (best_tier_for_station + TIER_LABEL_BADGE in musicstreamer/hi_res.py)"
    - "70-02 (StationStream.sample_rate_hz + bit_depth fields in musicstreamer/models.py)"
  provides:
    - "station_star_delegate.paint() renders quality-tier pill before star icon"
    - "station_star_delegate.sizeHint() reserves worst-case pill width on station rows"
  affects:
    - "musicstreamer/ui_qt/station_star_delegate.py"
tech_stack:
  added: []
  patterns:
    - "QPainter primitive pill: drawRoundedRect + drawText, no QSS"
    - "Selection-state color swap via QPalette.Highlight / HighlightedText"
    - "Geometry helper _pill_rect() right-anchored left of star column"
    - "sizeHint worst-case constant reservation (_PILL_WIDTH_WORST_CASE=80)"
key_files:
  created: []
  modified:
    - "musicstreamer/ui_qt/station_star_delegate.py"
decisions:
  - "sizeHint uses constant 80 px reservation (not QFontMetrics) — deterministic across platforms, mirrors _STAR_SIZE idiom"
  - "All station rows grow sizeHint width (not only stations with a tier) — avoids dynamic width shifts when tier changes"
  - "Pre-existing consumer test failures (test_station_list_panel, test_now_playing_panel) are RED stubs for plans 70-03..70-06; not caused by this plan"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-12"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase 70 Plan 07: Quality-Tier Pill in Station-Tree Delegate Summary

Wave 3 GREEN: extended `StationStarDelegate.paint()` to render a `QPainter`-drawn rounded-rect pill with `HI-RES` / `LOSSLESS` text before the star icon for station rows, with selection-state color swap and deterministic `sizeHint` width reservation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend paint() + sizeHint() for quality-tier pill | 1b40ab3 | musicstreamer/ui_qt/station_star_delegate.py |

## What Was Built

`musicstreamer/ui_qt/station_star_delegate.py` extended with:

- **4 new geometry constants**: `_PILL_PADDING_X=6`, `_PILL_PADDING_Y=4`, `_PILL_TO_STAR_GAP=8`, `_PILL_RADIUS=8` (UI-SPEC §Spacing Scale lock, match Phase 68 LIVE badge).
- **`_PILL_WIDTH_WORST_CASE=80`**: constant for deterministic `sizeHint` reservation ("LOSSLESS" at 9pt bold ≈ 78 px).
- **`_pill_rect(row_rect, pill_width, pill_height)`**: right-anchored helper, pill right edge is `_PILL_TO_STAR_GAP` px left of the star left edge, vertically centered.
- **`paint()` extension**: calls `best_tier_for_station(station)` and, when non-empty, renders the TIER_LABEL_BADGE label via `QPainter` primitives — `drawRoundedRect` + `drawText` with `QPainter.Antialiasing`. UI-SPEC OD-3 selection-state swap: under `QStyle.State_Selected` the pill fill becomes `QPalette.HighlightedText` and text becomes `QPalette.Highlight` (inverted from unselected), keeping the pill visible against the row's selected-highlight background.
- **`sizeHint()` extension**: station rows now return `base.width() + _STAR_SIZE + _STAR_MARGIN + _PILL_WIDTH_WORST_CASE + _PILL_TO_STAR_GAP`. Provider rows unchanged.

## Test Results

All 10 tests in `tests/test_station_star_delegate.py` GREEN:

| Test | Status |
|------|--------|
| test_paint_forces_square_decoration_rect | PASS (pre-existing) |
| test_paint_forces_left_aligned_decoration | PASS (pre-existing) |
| test_sizehint_enforces_min_row_height_32_for_station_rows | PASS (pre-existing) |
| test_sizehint_floors_height_at_32_for_provider_rows | PASS (pre-existing) |
| test_uniform_row_height_applies_floor_with_provider_first_row | PASS (pre-existing) |
| test_paints_hires_pill_for_hires_station | PASS (Phase 70 RED → GREEN) |
| test_paints_lossless_pill_for_cd_flac_station | PASS (Phase 70 RED → GREEN) |
| test_no_pill_for_lossy_station | PASS (Phase 70 RED → GREEN) |
| test_no_pill_for_provider_row | PASS (Phase 70 RED → GREEN) |
| test_sizehint_grows_for_pill | PASS (Phase 70 RED → GREEN) |

## Grep Gate Results

| Gate | Result |
|------|--------|
| `setStyleSheet` count == 0 | PASS (0) |
| `QStyle.State_Selected` count >= 1 | PASS (1) |
| `QPainter.Antialiasing` count >= 1 | PASS (1) |
| `from musicstreamer.hi_res import` count == 1 | PASS (1) |
| pill constants defined at module scope (4) | PASS (4) |

## Consumer Test Status

Pre-existing failures in `test_station_list_panel.py` and `test_now_playing_panel.py` are Phase 70 Wave 3 RED stubs for plans 70-03 through 70-06 (hi_res_chip, quality_badge, picker tier suffix) — none caused by this plan. Failure count identical on base commit vs. post-plan commit.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — the pill is fully wired: `best_tier_for_station(station)` reads live `station.streams` data (added in plan 70-02); the pill text comes from `TIER_LABEL_BADGE` (added in plan 70-01). No hardcoded empty values or placeholder text in the delegate path.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The only new surface is `QPainter.drawText(r, Qt.AlignCenter, label)` where `label` comes from the closed-enum `TIER_LABEL_BADGE` dict — plain-text by Qt design; no markup interpretation.

## Self-Check: PASSED

- File exists: `musicstreamer/ui_qt/station_star_delegate.py` — FOUND
- Commit `1b40ab3` exists in git log — FOUND
- All 10 tests pass — VERIFIED
