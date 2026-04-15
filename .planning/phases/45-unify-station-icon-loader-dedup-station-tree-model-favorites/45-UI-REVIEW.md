# Phase 45 — UI Review

**Audited:** 2026-04-14
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md; refactor phase)
**Screenshots:** Not captured (PySide6/Qt desktop app — no web dev server; Playwright-MCP not applicable to Qt widgets)
**Audit mode:** Code-only

---

## Scope note

Phase 45 is a pure dedup/bugfix refactor. Three duplicate icon-loaders (`StationTreeModel._icon_for_station`, `FavoritesView._load_station_icon`, `station_list_panel._load_station_icon`) were consolidated into a single `load_station_icon()` in `_art_paths.py`. The visible change is that station-tree rows and favorites-list rows now correctly render per-station 32px logos instead of the generic `audio-x-generic-symbolic.svg` fallback. No layout, spacing, typography, or color changes were introduced. Scoring reflects the quality of the change itself, not the surrounding UI.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | No strings touched this phase; surrounding labels remain solid (`Favorite Stations`, `No favorites yet`, `Star a station or track to save it here.`). |
| 2. Visuals | 4/4 | Fix restores primary visual affordance (station branding). Icon slots (32px) were already reserved, now correctly populated. |
| 3. Color | 4/4 | No color changes. Fallback is theme-neutral symbolic SVG. |
| 4. Typography | 4/4 | Not touched. |
| 5. Spacing | 4/4 | Icon size (32px) is consistent across all three surfaces (`setIconSize(QSize(32, 32))` in tree, recent, favorites). |
| 6. Experience Design | 4/4 | Null/missing paths fall back cleanly, no raise; QPixmapCache keyed on absolute path eliminates duplicate cache entries across surfaces. |

**Overall: 23/24**

---

## Top 3 Priority Fixes

1. **Verify UAT Task 3 is actually completed** — `45-01-SUMMARY.md` states Task 3 is "awaiting user" and the phase-wide git log shows Phase 40.1 was paused with a known `EditStationDialog` auto-fetch regression. Confirm the user has visually verified logos render in (a) station tree, (b) favorites list, (c) recently played, and (d) missing-logo fallback case. Without that confirmation the bugfix remains unverified.
2. **Consider unifying `now_playing_panel` fallback constant** — `grep` (per plan verification note) shows `now_playing_panel.py` still defines its own `_FALLBACK_ICON`. This is explicitly out of scope for P45 (different use — cover art slot, not station-list row), but the comment "single source of truth" from D-04 is only half-true at the module level. Low priority; document the intentional duality or fold it into a future sweep.
3. **Icon size is hardcoded at three call sites** — `setIconSize(QSize(32, 32))` is repeated in `station_tree_model` parent view config, `favorites_view:97`, and `station_list_panel:151,257`. The `size=32` default in `load_station_icon` matches, but a shared `STATION_ICON_SIZE = 32` constant in `_art_paths.py` (exported alongside `FALLBACK_ICON`) would prevent future drift if the project ever bumps to 40px or 48px.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

No copy was modified this phase. Surrounding strings in touched files are specific and user-appropriate:
- `favorites_view.py:60` — `"No favorites yet"` (specific empty-state heading, not generic "No data")
- `favorites_view.py:68` — `"Star a station or track to save it here."` (actionable body)
- `favorites_view.py:191` — `"Remove from favorites"` tooltip (clear intent)
- `station_list_panel.py:168,185` — `"▶ Filters"`, `"Search stations…"` (action-oriented, uses ellipsis char U+2026)

No generic `Submit`/`OK`/`Cancel` strings detected in the four audited files. One deduction only because phase scope didn't exercise copywriting.

### Pillar 2: Visuals (4/4)

The entire point of this phase is restoring a broken visual affordance. Before: generic music-note icon on every tree/favorites row regardless of station branding. After: per-station logos render at 32px with cached pixmaps. Visual hierarchy of the station-list rows (icon + label) was already correct; this phase fixes the silently-null icon load.

Fallback handling is graceful: `pix.isNull()` triggers a second load against the resource-registered SVG at `:/icons/audio-x-generic-symbolic.svg` (see `_art_paths.py:75-76`). No broken-image placeholder can surface.

### Pillar 3: Color (4/4)

No color tokens, no hardcoded hex, no palette overrides added. Existing QSS in `station_list_panel.py:51-79` uses `palette(base|mid|highlight|highlighted-text|button-text)` tokens (theme-aware) and was not touched.

### Pillar 4: Typography (4/4)

No font changes. Existing typography in touched files (`QFont` 9pt Normal for section labels, 13pt Bold for provider group headers via `station_tree_model.py:149-151`, 16pt DemiBold for empty-state heading) is internally consistent.

### Pillar 5: Spacing (4/4)

Icon dimension (32×32) is consistent across all three station-list surfaces. Margins in `favorites_view.py` (`setContentsMargins(8, 8, 0, 0)` for headers; `setContentsMargins(8, 0, 4, 0)` for track rows) follow a coherent 4/8 grid. `station_list_panel.py` uses 16px outer padding consistently (lines 103, 141, 189, 201, 215, 230).

No arbitrary spacing values introduced. See fix #3 above regarding DRY-ing the 32px icon size.

### Pillar 6: Experience Design (4/4)

State coverage for icon loading is complete in the unified helper:

- **Missing file (empty/None `station_art_path`):** `abs_art_path` returns `None` → `load_path = FALLBACK_ICON` → fallback rendered (`_art_paths.py:67-69`).
- **Broken file on disk:** `QPixmap(load_path)` returns null → `pix.isNull()` check → second `QPixmap(FALLBACK_ICON)` load (`_art_paths.py:74-76`).
- **Cache hit:** Absolute-path key ensures rel/abs variants share cache (`_art_paths.py:70-73`).
- **Cache miss:** Scaled with `Qt.KeepAspectRatio | Qt.SmoothTransformation` — correct for non-square logos.

Test coverage in `tests/test_art_paths.py` per summary: 7 cases, all pass, including explicit regression guards for the bug this phase fixes (relative path resolution) and for cache-key dedup.

Import hygiene is clean: `station_tree_model.py`, `favorites_view.py`, `station_list_panel.py` all dropped their now-unused `QPixmap`/`QPixmapCache` imports and each local `FALLBACK_ICON` constant. Single source of truth achieved (modulo `now_playing_panel.py` intentional exception noted above).

---

## Files Audited

- `musicstreamer/ui_qt/_art_paths.py` (79 lines)
- `musicstreamer/ui_qt/station_tree_model.py` (156 lines)
- `musicstreamer/ui_qt/favorites_view.py` (221 lines)
- `musicstreamer/ui_qt/station_list_panel.py` (481 lines)
- `.planning/phases/45-.../45-CONTEXT.md`
- `.planning/phases/45-.../45-01-PLAN.md`
- `.planning/phases/45-.../45-01-SUMMARY.md`

No registry audit: not a shadcn/web project.
