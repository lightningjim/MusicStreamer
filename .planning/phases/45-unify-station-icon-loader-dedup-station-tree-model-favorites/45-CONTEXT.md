---
phase: 45
phase_slug: unify-station-icon-loader-dedup-station-tree-model-favorites
status: context_gathered
created: 2026-04-14
source: interactive_discuss_chain
---

# Phase 45 Context — Unify station-icon loader

## Scope

Deduplicate three parallel station-icon loaders into a single shared helper in `musicstreamer/ui_qt/_art_paths.py`. Fixes the live bug where `StationTreeModel._icon_for_station` and `FavoritesView._load_station_icon` pass raw relative `station_art_path` directly to `QPixmap(path)` without calling `abs_art_path()`, so `QPixmap` loads null and the row falls back to the generic audio-x-symbolic icon even when the station has a valid logo file.

## Problem statement (from user observation during Phase 40.1 UAT)

> "What is supposed to be to the left of the stations in the station list? I see the note replacement icon."

Logo renders correctly in the now-playing panel (uses `abs_art_path` resolution) but NOT in the main station list or favorites list because those two call sites inline a different path resolution that skips `abs_art_path()`.

## Current state (three parallel implementations)

| File | Function | Uses `abs_art_path()`? | Notes |
|------|----------|------------------------|-------|
| `musicstreamer/ui_qt/station_list_panel.py:70` | `_load_station_icon(station)` | ✅ Yes | Correct; used by `RecentlyPlayedView` |
| `musicstreamer/ui_qt/station_tree_model.py:89` | `_icon_for_station(self, station)` | ❌ No — broken | Used for main tree `DecorationRole` |
| `musicstreamer/ui_qt/favorites_view.py:40` | `_load_station_icon(station)` | ❌ No — broken | Used for favorites list items |

All three define their own `FALLBACK_ICON = ":/icons/audio-x-generic-symbolic.svg"` constant.
All three cache into `QPixmapCache` with `f"station-logo:{path}"` — but with inconsistent key inputs (rel vs abs), so the cache is polluted and inconsistent.

## Decisions (locked)

- **D-01 — Helper location:** Extend `musicstreamer/ui_qt/_art_paths.py`. Already the home of `abs_art_path()` and already imported by the currently-correct `station_list_panel` loader. No new module.

- **D-02 — Shared API:** `load_station_icon(station, size: int = 32) -> QIcon` — single function that encapsulates path resolution, QPixmapCache lookup, scaling, and fallback. Also export a `FALLBACK_ICON` constant from the same module.

- **D-03 — Cache key:** Always `f"station-logo:{abs_path or FALLBACK_ICON}"` using the resolved absolute path (or the resource path if fallback). This matches what the currently-correct `station_list_panel` loader does and prevents relative/absolute variants of the same logo from producing distinct cache entries.

- **D-04 — Delete duplicates:** Remove `StationTreeModel._icon_for_station`, `favorites_view._load_station_icon`, and `station_list_panel._load_station_icon`. Remove each file's local `FALLBACK_ICON` constant. Replace all call sites with the shared helper. No backwards-compat shims — all callers are in-tree.

- **D-05 — Test strategy:** Add `tests/test_art_paths.py` with unit tests covering:
  - Relative `station_art_path` resolves via `abs_art_path` and loads the correct pixmap
  - Missing file falls back to `FALLBACK_ICON` and does not raise
  - Absolute path passes through unchanged
  - `size` parameter honored (e.g. 32px and 64px produce correctly-sized pixmaps)
  - Cache key dedup: calling the helper twice with the same station returns cached pixmap (no re-load)

## Files to modify

- `musicstreamer/ui_qt/_art_paths.py` — add `FALLBACK_ICON`, `load_station_icon(station, size=32)`
- `musicstreamer/ui_qt/station_tree_model.py` — delete `_icon_for_station` + local `FALLBACK_ICON`, call shared helper
- `musicstreamer/ui_qt/favorites_view.py` — delete `_load_station_icon` + local `_FALLBACK_ICON`, call shared helper
- `musicstreamer/ui_qt/station_list_panel.py` — delete local `_load_station_icon` + `_FALLBACK_ICON`, call shared helper
- `tests/test_art_paths.py` — new file, regression tests per D-05

## Success criteria

- Station list rows show the station's logo (not the generic fallback) when `station_art_path` points to a valid file
- Favorites list rows show the same
- No duplicate code across the three UI files — single source of truth in `_art_paths.py`
- All existing tests still green
- New `tests/test_art_paths.py` passes

## Out of scope / deferred

- Icon size variants beyond 32px (e.g. 16px for search, 64px for import dialog) — the `size` parameter enables this but no existing caller needs it yet
- Theme-aware fallback icons (light/dark mode swap) — not in any requirement
- Async logo loading for slow/remote filesystems — not observed as a problem
