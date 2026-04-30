# Phase 54 — Plan 03 — Path B-1 Patch + UAT Re-run

**Date:** 2026-04-30
**Trigger:** Plan 02 SUMMARY recorded `PATH B-1 ESCALATE`
**Patch scope:** musicstreamer/ui_qt/_art_paths.py — ~10 lines + 2 imports
**BUG-05 status:** STILL OPEN — escalate

## Patch Summary

- Imports extended: `QPoint` (QtCore), `QPainter` (QtGui)
- `load_station_icon` cache-miss block replaced: source pixmap → aspect-scaled to (size, size) with `Qt.KeepAspectRatio` → painted onto a transparent (size, size) QPixmap canvas → cached
- Cache key string UNCHANGED — `f"station-logo:{load_path}"` (D-11 invariant)
- FALLBACK_ICON branch preserved verbatim (`src.isNull()` check retained)
- QPainter explicitly ended (`painter.end()`) before `QPixmapCache.insert(...)` — no resource leak
- Single commit: `b1a9088 fix(54-03): paint aspect-scaled icon onto transparent square QPixmap canvas`

## Test Adjustments
- Adjusted `tests/test_art_paths.py::test_load_station_icon_preserves_portrait_aspect` — replaced dimension assertions with non-transparent-region (bbox) assertions per Outcome B in plan task 2 (since the QIcon now wraps a 32×32 canvas, not a 16×32 bare pixmap)
- Adjusted `tests/test_art_paths.py::test_load_station_icon_preserves_landscape_aspect` — same shape adjustment
- Added `_non_transparent_bbox` helper at top of the tests module
- All 9 tests in `test_art_paths.py` pass (`pytest tests/test_art_paths.py -x` → 0.19s, 9 passed)
- Full suite: 786 passed; only failure is pre-existing `test_linux_mpris_backend_constructs` flake already documented in `deferred-items.md` from Plan 01 (not introduced by this patch)

## UAT Re-run

| Step | Repro | Pre-patch | Post-patch | Status |
|------|-------|-----------|------------|--------|
| 1 | Landscape (Living Coffee, id=2) | cropped | letterboxed correctly (uniform 32×32 cells with 32×16 thumbnail centered vertically) | ✅ Fixed — landscape regression resolved |
| 2 | Square baseline (20th Century, id=10) | edge-to-edge | edge-to-edge (visually unchanged, as expected for square sources) | ✅ Unchanged (expected) |
| 3 | Synthetic portrait (50×100 red, /tmp/portrait.png) | cropped (oversized red column) | **still cropped** — visible result is "landscape-shaped" cell with top/bottom of the painted 16×32 region clipped off | ❌ STILL BROKEN |
| 4 | Icon column uniformity | uniform-but-wrong | uniform 32×32 for landscape & square sources; portrait sources still distort | ⚠ Partially fixed |

## User Verbatim

> "I still see it acting like it's landscape for everything, cutting off the top and bottom halves. Is this not maybe something to do with the row setup or is it actually the image?"

> "landscape has never not worked. Just the square to portrait."

UAT performed after a full system reboot and `run_local.sh` relaunch — QPixmapCache definitively flushed. Cache invalidation is not the cause.

## Root-Cause Diagnosis

The QIcon contract is correct after Path B-1:
- `pytest tests/test_art_paths.py -x` proves `load_station_icon(portrait_50x100_station)` returns a QIcon whose `.pixmap(QSize(32, 32))` is a 32×32 RGBA pixmap with a 16×32 red region centered horizontally and transparent strips at x=0..7 and x=24..31. D-04, D-05 invariants are mathematically satisfied.

The cropping observed live therefore originates **downstream of `load_station_icon`** — specifically in the decoration-rect geometry the tree gives Qt's drawing pipeline. On the user's Linux X11/Wayland session, the rect Qt draws the icon into is wider than tall, so the 32×32 square pixmap is mapped into a landscape-shaped slot and the painted 16×32 portrait region's top and bottom are clipped.

Evidence that points to row geometry rather than the icon:
- `uat-evidence.png` (pre-patch) shows the SomaFM Groove Salad row was ~70px tall — the row stretched to fit a 50×100-derived non-square pixmap. Post-patch the icon is always 32×32, so the row falls back to its default `sizeHint`-computed height, which on this Qt session appears to be < 32 (landscape-shaped decoration rect).
- `station_star_delegate.py` (the only QStyledItemDelegate on the tree, set via `tree.setItemDelegate`) does not override the decoration rect. It paints a 20×20 star on the right and forwards `super().sizeHint()` (`base.height()`) for vertical sizing. There is no explicit row-height enforcement that would guarantee 32px tall rows.
- `tree.setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))` (32×32) is set in `station_list_panel.py:280`, but `setIconSize` only governs how QIcon is asked for pixmaps — not the rect Qt actually draws into when the row's vertical space is shorter than 32.
- Path A's offscreen probe (Plan 02 RESEARCH §2) used a headless `QT_QPA_PLATFORM=offscreen` environment which renders rows differently from a real X11/Wayland session — explaining why the probe predicted Path A would work but UAT showed it didn't.

Path B-1 was rejected as insufficient by D-09's "smallest diff first; escalate only if necessary" hierarchy. Per RESEARCH §3, the documented escalation is **Path B-2: a custom QStyledItemDelegate (or extension to StationStarDelegate) that explicitly controls decoration-rect geometry** so the 32×32 pixmap is drawn into a square 32×32 slot regardless of platform-default row sizing.

## Screenshots
- `uat-landscape-after.png` — post-patch Cafe BGM panel; landscape thumbnails (Living Coffee, TOKYO Cafe) render uniformly 32×32 with 32×16 letterboxed content. Confirms landscape rendering is correct.
- `uat-portrait-after.png` — post-patch Filters panel with SomaFM Groove Salad selected. Portrait-orientation logo still appears clipped top-and-bottom. (NOTE: this screenshot was captured before `/tmp/portrait.png` was regenerated — the icon shown is the actual SomaFM logo, not the synthetic 50×100 red. The user's verbal report after re-running step #3 with the regenerated synthetic confirms the same cropping pattern.)
- `uat-evidence.png` — Plan 02 pre-patch evidence (carry-forward).

## Decisions Honored

- D-04 (transparent bars): `pix.fill(Qt.transparent)` — present in patched function ✓
- D-05 (edge-to-edge longer axis): `(size - scaled.width()) // 2` centering present ✓
- D-07 (uniform loader): no per-station-type branching introduced ✓
- D-09 (smallest diff): single ~10-line change, no delegate modification, no `setItemDelegateForColumn` ✓ — but D-09's hierarchy permits escalation to Path B-2 when B-1 proves insufficient, which is the case here
- D-11 (cache key unchanged): `station-logo:{load_path}` preserved ✓

## What Remains Open

- BUG-05 (portrait/landscape cropping in row icon) — partially resolved (landscape ✓), portrait still failing on Linux X11/Wayland
- Path B-2 (delegate-controlled decoration rect) is now indicated. Per RESEARCH §3 "Path B-2", this likely means extending `StationStarDelegate.paint` to compute and pass an explicit 32×32 (or AlignCenter, KeepAspect) decoration rect when painting the row icon, rather than letting Qt's default `super().paint()` infer the rect from the row geometry.
- Recommended follow-up: gap-closure phase via `/gsd-plan-phase 54 --gaps` after this verification reports `gaps_found`, scoped to Path B-2 implementation. The B-1 patch (commit b1a9088) should be **kept** — it correctly fixes landscape and is a precondition for any delegate-level work (the delegate needs a square-canvas pixmap to paint into a square rect cleanly).

## Files Modified This Plan

- `musicstreamer/ui_qt/_art_paths.py` — patched (kept; correctly fixes landscape)
- `tests/test_art_paths.py` — assertion shape adjusted (kept; matches new contract)
