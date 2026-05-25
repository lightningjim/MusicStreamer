# Plan 54-02 — UAT Decision Gate Summary

**Phase:** 54 — Station Logo Aspect Ratio Fix
**Plan:** 54-02 (UAT decision gate)
**Decision:** PATH B-1 ESCALATE
**Completed:** 2026-04-29

## Decision Token

**PATH B-1 ESCALATE**

UAT confirmed that the user's running build does NOT match the offscreen Linux/Qt 6.11.0 probe environment. The provider-tree row icon is being rendered at native source dimensions (or larger than the 32×32 iconSize hint), causing both visible cropping artifacts on certain logos AND row-height variation across stations. Plan 54-03 will apply the canvas-paint patch in `musicstreamer/ui_qt/_art_paths.py` per RESEARCH.md §3 Path B-1.

## UAT Outcomes

| # | Step | Repro | Expected | Observed | Verdict |
|---|------|-------|----------|----------|---------|
| 1 | Landscape | Cafe BGM → "Living Coffee: Smooth Jazz Radio" (id=2, 1280×720) | 32w × 16h letterboxed | Renders correctly in Recently Played; landscape thumbnail fits without obvious distortion | PASS |
| 2 | Square baseline | ClassicalRadio → "20th Century" (id=10, 1000×1000) | 32×32 fills cell edge-to-edge | User reports cropping observed | FAIL |
| 3 | Portrait (synthetic) | Test station with `/tmp/portrait.png` (50×100) installed via EditStationDialog | 16w × 32h pillarboxed in 32×32 cell with transparent strips left+right | Red rectangle renders at full source size; row HEIGHT grew to accommodate the unscaled image. Visible in both Recently Played AND in SomaFM section between Drone Zone and Vaporwaves — that station's row is visibly taller than its siblings. | FAIL |
| 4 | Column uniformity (SC #4) | Scroll provider tree | Icon column uniformly 32px wide; row height stable | SC #4 violated — synthetic-portrait row is taller than adjacent rows | FAIL |

## Evidence

- `.planning/phases/54-station-logo-aspect-ratio-fix/uat-evidence.png` — screenshot showing:
  - Recently Played: "SomaFM Groove Salad (128k MP3)" displays a large RED bar (the synthetic portrait, oversized)
  - Provider tree → SomaFM section: Drone Zone (normal row height) → SomaFM Groove Salad (visibly taller row, large red bar) → Vaporwaves (normal row height)
  - Now-playing 180×180 viewport (right): synthetic portrait renders correctly pillarboxed (out of scope per D-01, but confirms the now-playing render path is fine)

## Environment

- **OS / Qt platform:** Linux (per project environment metadata)
- **PySide6 / Qt:** matches RESEARCH.md probe (PySide6 6.11.0 / Qt 6.11.0)
- **Discrepancy with research probe:** the research used `QT_QPA_PLATFORM=offscreen` which does NOT match the user's actual native Qt platform (X11 or Wayland). This validates RESEARCH.md §1 explanation #2: "Platform-specific style. The probe ran on Linux/offscreen. It's conceivable that on a different QStyle … the default item-view decoration alignment differs and could produce visible artifacts. **Researcher could not test this from a Linux box; this is a known gap.**" — confirmed.

## Asset metadata

- `/tmp/portrait.png` — 50×100 red PNG fixture (Task 1 output, verified)
- `~/.local/share/musicstreamer/assets/2/station_art.jpg` — 1280×720 (Living Coffee)
- `~/.local/share/musicstreamer/assets/10/station_art.png` — 1000×1000 (20th Century)
  - *(Minor: RESEARCH.md §5 listed this as `.jpg`; actual extension is `.png`. DB row points correctly; loads via QPixmap fine.)*

## Cleanup

- User must restore the test station's original `station_art_path` after UAT (T-54-04 mitigation in PLAN). If the test station was the synthetic-installed one ("SomaFM Groove Salad"), revert via EditStationDialog → Choose File → original asset, OR Clear if originally logo-less.

## Next

- **Plan 54-03 EXECUTES** — apply ~10-line canvas-paint patch to `musicstreamer/ui_qt/_art_paths.py::load_station_icon` per RESEARCH.md §3 Path B-1. Re-run UAT against the same three repros to confirm the fix.
- **Test-assertion adjustment:** Plan 54-03 Task 2 may need to update the two regression tests added in Plan 54-01 because the QIcon will now wrap a 32×32 canvas rather than a 16×32 / 32×16 raw scaled pixmap. The PATTERNS.md `_non_transparent_bbox` helper described in Plan 54-03 handles this contingency.
