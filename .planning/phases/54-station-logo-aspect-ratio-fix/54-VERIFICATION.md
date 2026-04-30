---
status: pass
phase: 54-station-logo-aspect-ratio-fix
must_haves_total: 4
must_haves_verified: 4
must_haves_failed: 0
generated: 2026-04-30
updated: 2026-04-30
---

# Phase 54 Verification — Station Logo Aspect Ratio Fix

## Goal

Station logos in the radio logo view display fully regardless of their natural aspect ratio — square logos are not cropped, and rectangular logos are letterboxed/pillarboxed rather than cut off.

## Verdict: pass

Phase 54 closed in two stages. Plan 03's Path B-1 canvas-paint patch in `_art_paths.py` (commit `b1a9088`) shipped a square 32×32 transparent QPixmap canvas through `load_station_icon`, fixing landscape rendering and locking the QIcon contract behind 9 regression-lock tests. UAT then revealed a second-order failure: on Linux X11/Wayland, the row's default decoration rect was wider than tall, so Qt squeezed the square pixmap into a landscape-shaped slot and clipped the top + bottom of the painted portrait region. Plan 04's Path B-2 delegate patch (commit `af63397`) overrides `StationStarDelegate.paint()` to force `option.decorationSize = QSize(32, 32)` and `option.decorationAlignment = Qt.AlignVCenter | Qt.AlignLeft` before delegating to `super().paint()`, and floors `sizeHint().height()` at 32 for both station and provider rows so `setUniformRowHeights(True)` propagates the right height view-wide. UAT re-run confirmed portrait, landscape, and square sources all render correctly; favorite-toggle star unaffected. BUG-05 closed.

## Must-Have Coverage

| # | Must-Have | Evidence | Status |
|---|-----------|----------|--------|
| 1 | Square logos display edge-to-edge with no cropping | UAT step #4 (20th Century, id=10) — visually unchanged pre/post patch | ✅ Verified |
| 2 | Landscape logos display 32×16 letterboxed and centered vertically in 32×32 row icon cells | UAT step #1 (Living Coffee + TOKYO Cafe in Cafe BGM panel) — `uat-landscape-after.png` shows uniform 32×32 cells with 32×16 thumbnails letterboxed | ✅ Verified |
| 3 | Icon column is uniform 32×32 across all stations regardless of source aspect | Plan 04 UAT — landscape, square, AND portrait sources now uniform on Linux X11/Wayland; user signed off `approved` | ✅ Verified |
| 4 | Portrait logos display 16×32 pillarboxed and centered horizontally in 32×32 row icon cells | Plan 04 UAT step #1 (synthetic 50×100 red `/tmp/portrait.png` installed via EditStationDialog) — pillarboxed correctly after Path B-2 delegate patch (commit `af63397`); user signed off `approved` | ✅ Verified |

**Score:** 4/4 must-haves verified.

## Gaps

### Gap 1 (CLOSED — Plan 04, Path B-2) — Portrait sources still vertically cropped on Linux X11/Wayland

**Resolution:** Plan 04's delegate patch (commit `af63397`) closes this gap by forcing a square 32×32 decoration rect via `option.decorationSize` mutation and `sizeHint().height()` floor on both row branches. UAT re-run confirmed portrait sources now render 16w × 32h pillarboxed with no top/bottom clipping. See `54-04-SUMMARY.md`.

**Original diagnosis (preserved for audit trail):**


**Symptom:** After applying the Path B-1 canvas-paint patch (commit `b1a9088`), a portrait-oriented source (50×100 red synthetic via `/tmp/portrait.png`) still renders with the top and bottom of the painted region clipped on the user's live Qt session. The visual outcome looks like the row's icon cell is shorter than it is wide ("acting like landscape for everything").

**Why the regression-lock tests pass:** The 9 tests in `tests/test_art_paths.py` assert on `icon.pixmap(QSize(32, 32))` — i.e. they exercise the QIcon contract directly with a square 32×32 request size. Under that contract the patched function returns a 32×32 RGBA pixmap with a centered 16×32 painted region surrounded by transparent pillarbox strips. The tests are correct and continue to be the regression lock for the QIcon contract.

**Why the live UAT fails:** The cropping happens **downstream of `load_station_icon`**, in Qt's tree paint pipeline. The decoration rect Qt's `super().paint()` draws the icon into on Linux X11/Wayland is wider than tall (landscape-shaped), so a square 32×32 pixmap with a 16×32 painted region in its center gets vertically squeezed → top and bottom of the painted region clip out.

**Evidence pointing to row geometry rather than the icon:**
- Pre-patch `uat-evidence.png` shows the SomaFM row stretched to ~70px tall to fit a 50×100-derived non-square pixmap. Post-patch the icon is always 32×32, so the row falls back to its default `sizeHint`-computed height — apparently shorter than 32 on this Qt session.
- `station_star_delegate.py` (the only delegate on the tree, set via `tree.setItemDelegate`) does not override decoration rect or row height. It paints a 20×20 star on the right and forwards `super().sizeHint()`'s `base.height()`. There is no explicit row-height enforcement that would guarantee a 32×32 square decoration rect.
- `tree.setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))` in `station_list_panel.py:280` is set to 32×32, but `setIconSize` only governs how QIcon is asked for pixmaps — not the rect Qt actually draws into when row vertical space is shorter.
- Path A's offscreen probe in Plan 02 RESEARCH §2 (`QT_QPA_PLATFORM=offscreen`) renders rows differently from a real X11/Wayland session — explaining why the probe predicted Path A would work but UAT showed it didn't, and now also why Path B-1 passes the offscreen probe (and our tests) but fails live.

**Required:** Path B-2 — a delegate-level fix that explicitly controls the icon decoration rect (likely an override of `paint` in `StationStarDelegate` or a new icon-cell delegate) so the 32×32 canvas is drawn into a square 32×32 (or AlignCenter, KeepAspect) slot regardless of platform-default row sizing. Per RESEARCH §3 ("Path B-2"), this is the documented escalation path. D-09's "smallest diff" hierarchy permits B-2 once B-1 has been proven insufficient — which is now the case.

**Affected requirement:** `BUG-05` — "Rectangular brand logos display fully in the radio logo view (no square-only crop that cuts off content)".

## Recommended Next Step

Run `/gsd-plan-phase 54 --gaps` to scope a Path B-2 plan. The B-1 patch (commit `b1a9088`) and adjusted regression-lock tests should both be **kept** — B-1 is a precondition for B-2 (the delegate needs the QIcon to store a square 32×32 pixmap so the painted region's geometry is unambiguous when computed against a square decoration rect).

## Files

**Production:**
- `musicstreamer/ui_qt/_art_paths.py` — patched in commit `b1a9088` (kept)

**Tests:**
- `tests/test_art_paths.py` — 9 tests passing; portrait/landscape assertions adjusted to non-transparent-region bbox shape (kept)

**Plans:**
- `54-01-PLAN.md` / `54-01-SUMMARY.md` — regression-lock tests (complete)
- `54-02-PLAN.md` / `54-02-SUMMARY.md` — UAT decision gate; recorded `PATH B-1 ESCALATE` (complete)
- `54-03-PLAN.md` / `54-03-SUMMARY.md` — Path B-1 patch + UAT re-run; recorded `BUG-05 STILL OPEN — escalate` (complete-but-goal-unmet)

**Evidence:**
- `uat-evidence.png` — Plan 02 pre-patch baseline
- `uat-landscape-after.png` — Path B-1 post-patch landscape (PASS)
- `uat-portrait-after.png` — Path B-1 post-patch portrait (FAIL — note caveats in 54-03-SUMMARY about asset state during capture)
