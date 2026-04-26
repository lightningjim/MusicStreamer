---
phase: 38-filter-strip-favorites
plan: 01
subsystem: ui_qt/station_list_panel + repo + models
tags: [filter, proxy-model, flow-layout, station-favorites, chips]
dependency_graph:
  requires: [37-01]
  provides: [StationFilterProxyModel, FlowLayout, Station.is_favorite, filter strip UI]
  affects: [station_list_panel, repo, models, station_tree_model]
tech_stack:
  added: []
  patterns:
    - QSortFilterProxyModel subclass with recursive provider-group child check
    - FlowLayout (in-repo wrapping QLayout, from Qt canonical example)
    - QButtonGroup(exclusive=False) for multi-select chip rows
    - QSS dynamic property toggle (unpolish/polish cycle) for chip selected state
    - ALTER TABLE migration for is_favorite column (same pattern as icy_disabled)
key_files:
  created:
    - musicstreamer/ui_qt/station_filter_proxy.py
    - musicstreamer/ui_qt/flow_layout.py
    - musicstreamer/ui_qt/icons/starred-symbolic.svg
    - musicstreamer/ui_qt/icons/non-starred-symbolic.svg
    - musicstreamer/ui_qt/icons/user-trash-symbolic.svg
    - musicstreamer/ui_qt/icons/edit-clear-all-symbolic.svg
    - tests/test_station_filter_proxy.py
    - tests/test_flow_layout.py
  modified:
    - musicstreamer/models.py
    - musicstreamer/repo.py
    - musicstreamer/ui_qt/station_tree_model.py
    - musicstreamer/ui_qt/station_list_panel.py
    - musicstreamer/ui_qt/icons.qrc
    - musicstreamer/ui_qt/icons_rc.py
    - tests/test_favorites.py
    - tests/test_station_list_panel.py
decisions:
  - Use QSortFilterProxyModel.invalidate() not invalidateFilter/invalidateRowsFilter (both deprecated in PySide6 6.9.2)
  - is_favorite column on stations table (not separate join table) — simpler migration, avoids N+1
  - mapToSource required in _on_tree_activated — proxy indexes not valid for source model methods
metrics:
  duration: ~35 min
  completed: 2026-04-12
  tasks_completed: 2
  files_changed: 14
---

# Phase 38 Plan 01: Filter Strip + Favorites DB Infrastructure Summary

**One-liner:** StationFilterProxyModel with search/chip multi-select filtering, FlowLayout for wrapping chip rows, Station.is_favorite DB column, and filter strip UI wired into StationListPanel.

## What Was Built

### Task 1: DB migration + StationFilterProxyModel + FlowLayout + tests

- `Station.is_favorite: bool = False` field added to models.py
- `ALTER TABLE stations ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0` migration in `db_init()`
- `list_stations()`, `get_station()`, `list_recently_played()` updated to include `is_favorite=bool(r["is_favorite"])`
- `Repo.set_station_favorite(id, bool)`, `is_favorite_station(id)`, `list_favorite_stations()` added
- `StationTreeModel.data()` returns `node.station` for `Qt.UserRole` on station nodes
- `StationFilterProxyModel(QSortFilterProxyModel)` created with `set_search`, `set_providers`, `set_tags`, `clear_all`; `filterAcceptsRow` recurses into provider children and delegates to `matches_filter_multi()`
- `FlowLayout(QLayout)` created as in-repo wrapping layout with `h_spacing`/`v_spacing` params
- 25 new tests across test_station_filter_proxy.py, test_flow_layout.py, test_favorites.py

### Task 2: Filter strip UI in StationListPanel + icons

- 4 SVG icons copied from Adwaita: starred, non-starred, user-trash, edit-clear-all
- `icons.qrc` extended with 4 new entries; `icons_rc.py` regenerated
- `StationListPanel` restructured: search `QLineEdit`, provider/tag `FlowLayout` chip rows, "Clear all" `QPushButton`
- `_proxy = StationFilterProxyModel` set as tree model; `mapToSource` used in `_on_tree_activated` (Pitfall 1 fix)
- `_set_chip_state` helper applies unpolish/polish cycle for QSS re-evaluation
- `_on_provider_chip_clicked`, `_on_tag_chip_clicked`, `_clear_all_filters`, `_on_search_changed` as bound methods
- URL migration `executescript` updated to include `is_favorite` in `stations_new` DDL (bug fix — Rule 1)
- `test_station_list_panel.py` updated for proxy indexes; 2 new tests added

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed URL migration executescript missing is_favorite column**
- **Found during:** Task 2 full-suite run
- **Issue:** `test_migration_url_to_streams` failed — the legacy URL migration `executescript` recreates `stations` as `stations_new` without `is_favorite`, so `list_stations()` raised `IndexError: No item with that key`
- **Fix:** Added `is_favorite INTEGER NOT NULL DEFAULT 0` to `stations_new` DDL in the migration block
- **Files modified:** `musicstreamer/repo.py`
- **Commit:** 15f0b84

**2. [Rule 1 - Bug] Switched from deprecated invalidateFilter/invalidateRowsFilter to invalidate()**
- **Found during:** Task 1 test run
- **Issue:** Both `invalidateFilter()` and `invalidateRowsFilter()` show as deprecated in PySide6 6.9.2; `invalidate()` is the correct method
- **Fix:** Used `self.invalidate()` in all four proxy mutator methods
- **Files modified:** `musicstreamer/ui_qt/station_filter_proxy.py`
- **Commit:** c4f88d8

## Commits

| Hash | Message |
|------|---------|
| c4f88d8 | feat(38-01): DB migration + StationFilterProxyModel + FlowLayout + tests |
| 15f0b84 | feat(38-01): filter strip UI in StationListPanel + SVG icons |

## Known Stubs

None — all data wires through from the repo. Chip rows populate from `repo.list_stations()`. Proxy filters live data.

## Threat Flags

None — filter strip is in-memory string matching only; no new network endpoints or SQL injection surfaces introduced. `is_favorite` is local SQLite boolean, same trust level as `icy_disabled`.

## Self-Check: PASSED

All created files exist on disk. Both task commits confirmed in git log.
