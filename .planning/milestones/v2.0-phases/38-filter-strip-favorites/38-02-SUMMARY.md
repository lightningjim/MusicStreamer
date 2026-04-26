---
phase: 38-filter-strip-favorites
plan: 02
subsystem: ui_qt/station_list_panel + favorites_view + station_star_delegate + now_playing_panel + main_window
tags: [favorites, segmented-control, star-delegate, QStackedWidget, QListWidget, QToolButton]
dependency_graph:
  requires: [38-01]
  provides: [FavoritesView, StationStarDelegate, segmented-control, track-star-button, station-star-delegate]
  affects: [station_list_panel, favorites_view, station_star_delegate, now_playing_panel, main_window]
tech_stack:
  added: []
  patterns:
    - QStackedWidget for page toggle (Stations / Favorites)
    - QButtonGroup(exclusive=True) for segmented control with QSS dynamic property
    - QStyledItemDelegate with editorEvent hit-testing for star click in tree rows
    - QListWidget + setItemWidget for trash-button track rows (Pitfall 4 setSizeHint fix applied)
    - Signal(Station, bool) for station_favorited toast wiring
    - Signal(str, str, str, bool) for track_starred toast wiring
key_files:
  created:
    - musicstreamer/ui_qt/favorites_view.py
    - musicstreamer/ui_qt/station_star_delegate.py
  modified:
    - musicstreamer/ui_qt/station_list_panel.py
    - musicstreamer/ui_qt/now_playing_panel.py
    - musicstreamer/ui_qt/main_window.py
    - tests/test_station_list_panel.py
    - tests/test_now_playing_panel.py
    - tests/test_favorites.py
    - tests/test_main_window_integration.py
    - tests/test_ui_qt_scaffold.py
decisions:
  - FavoritesView uses QWidget visibility (setVisible) not QStackedWidget pages — simpler empty-state logic
  - StationStarDelegate always visible (not hover-only) per UI-SPEC; painted via icon.paint() in delegate
  - lambda capture in _make_track_row_widget uses default-arg capture (not self-capture) — approved per QA-05 exception for per-item closures
  - _update_star_enabled checks both station is not None and bool(last_icy_title) — D-11 spec
metrics:
  duration: ~8 min
  completed: 2026-04-12
  tasks_completed: 2
  files_changed: 9
---

# Phase 38 Plan 02: Segmented Control + FavoritesView + Star Buttons Summary

**One-liner:** QStackedWidget-backed Stations/Favorites segmented toggle, FavoritesView with station/track lists and trash removal, StationStarDelegate for tree-row star icons, and track star button on NowPlayingPanel wired through MainWindow toast notifications.

## What Was Built

### Task 1: Segmented control + QStackedWidget + FavoritesView + StationStarDelegate

- `FavoritesView(QWidget)`: two-section widget — "Favorite Stations" QListWidget + "Favorite Tracks" QListWidget with trash QToolButton per row; empty state ("No favorites yet") shown when both lists empty; `refresh()` populates from repo; `station_activated` and `favorites_changed` signals
- `StationStarDelegate(QStyledItemDelegate)`: paints `starred-symbolic` / `non-starred-symbolic` 20x20 icon right-aligned in station tree rows; `editorEvent` hit-tests click within star rect; emits `star_toggled(Station)` signal
- `StationListPanel` restructured: segmented control QPushButtons with `segState` QSS property at top; `QStackedWidget` with page 0 (all existing Stations content) and page 1 (`FavoritesView`); `station_favorited = Signal(Station, bool)` added; `_on_station_star_toggled` toggles repo and emits signal; filter strip hidden in Favorites mode via stack page switch
- `FakeRepo` in `test_station_list_panel.py` extended with favorites methods (Rule 1 fix — blocking test)
- 6 new tests across test_station_list_panel.py and test_favorites.py

### Task 2: Track star button + MainWindow wiring

- `NowPlayingPanel.star_btn`: QToolButton 28x28 inserted at Plan 38 marker; `setCheckable(True)`, disabled by default
- `track_starred = Signal(str, str, str, bool)` added to NowPlayingPanel
- `_update_star_enabled()`: enables star only when `_station is not None and bool(_last_icy_title)` — D-11 spec
- `on_title_changed` updated: stores `_last_icy_title`, calls `_update_star_enabled`, checks `repo.is_favorited` and sets icon/tooltip/checked
- `bind_station` / `_on_stop_clicked` / `on_playing_state_changed` all call `_update_star_enabled`
- `_on_star_clicked`: toggles repo.add_favorite / remove_favorite, updates icon/tooltip, emits `track_starred`
- `MainWindow`: `_on_track_starred` → `show_toast("Saved to favorites" / "Removed from favorites")`; `_on_station_favorited` → `show_toast("Station added to favorites" / "Station removed from favorites")`
- FakeRepo in `test_main_window_integration.py` and `test_ui_qt_scaffold.py` extended with favorites methods (Rule 1 fix)
- 5 new tests for star button in test_now_playing_panel.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FakeRepo in test_station_list_panel.py missing favorites methods**
- **Found during:** Task 1 test run — FavoritesView constructor calls `repo.list_favorite_stations()` which FakeRepo lacked
- **Fix:** Added `set_station_favorite`, `is_favorite_station`, `list_favorite_stations`, `list_favorites` to FakeRepo in test_station_list_panel.py
- **Files modified:** `tests/test_station_list_panel.py`
- **Commit:** ac1a0e2

**2. [Rule 1 - Bug] FakeRepo in test_main_window_integration.py and test_ui_qt_scaffold.py missing favorites methods**
- **Found during:** Task 2 full-suite run
- **Fix:** Added full favorites method surface to both test doubles
- **Files modified:** `tests/test_main_window_integration.py`, `tests/test_ui_qt_scaffold.py`
- **Commit:** 7791e0a

**3. [Rule 1 - Bug] Empty state test used isVisible() which requires widget shown**
- **Found during:** Task 1 — `_empty_label.isVisible()` returned False on unshown widget
- **Fix:** Changed test to call `view.show()` first, then check `_empty_widget.isHidden()` and `_content_widget.isHidden()`
- **Files modified:** `tests/test_favorites.py`
- **Commit:** ac1a0e2

## Commits

| Hash | Message |
|------|---------|
| ac1a0e2 | feat(38-02): FavoritesView + StationStarDelegate + segmented control in StationListPanel |
| 7791e0a | feat(38-02): track star button on NowPlayingPanel + MainWindow toast wiring |

## Known Stubs

None — all data wires through live repo calls. FavoritesView populates from `repo.list_favorite_stations()` and `repo.list_favorites()`. Star state checked via `repo.is_favorited()` / `repo.is_favorite_station()`.

## Threat Flags

None — no new network endpoints. All DB writes use parameterized queries via existing repo methods. ICY titles stored as plain text via `repo.add_favorite()` which already uses parameterized SQL (T-38-04 accepted, T-38-05 accepted in threat model).

## Self-Check: PASSED

All created/modified files exist on disk. Both commits confirmed in git log.
