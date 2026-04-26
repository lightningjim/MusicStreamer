---
phase: 37
plan: 01
subsystem: ui_qt
tags: [qt, widget, station-list, model, mvc]
requires:
  - musicstreamer.models.Station
  - musicstreamer.repo.Repo.list_stations
  - musicstreamer.repo.Repo.list_recently_played
provides:
  - musicstreamer.ui_qt.station_tree_model.StationTreeModel
  - musicstreamer.ui_qt.station_list_panel.StationListPanel
  - musicstreamer.ui_qt.station_list_panel._load_station_icon
  - ":/icons/audio-x-generic-symbolic.svg"
affects:
  - musicstreamer/ui_qt/icons.qrc
  - musicstreamer/ui_qt/icons_rc.py
tech-stack:
  added: []
  patterns:
    - QAbstractItemModel two-level tree with _TreeNode dataclass
    - QPixmapCache keyed on station art path
    - QStandardItemModel for RecentlyPlayed QListView
    - bound-method signal slots (no self-capturing lambdas)
key-files:
  created:
    - musicstreamer/ui_qt/station_tree_model.py
    - musicstreamer/ui_qt/station_list_panel.py
    - musicstreamer/ui_qt/icons/audio-x-generic-symbolic.svg
    - musicstreamer/ui_qt/icons/NOTICE.md
    - tests/test_station_tree_model.py
    - tests/test_station_list_panel.py
  modified:
    - musicstreamer/ui_qt/icons.qrc
    - musicstreamer/ui_qt/icons_rc.py
decisions:
  - "Shared _load_station_icon helper at module level in station_list_panel.py — avoids coupling RecentlyPlayedView to StationTreeModel internals while reusing the QPixmapCache key scheme."
  - "RecentlyPlayed uses QListView + QStandardItemModel (D-02 option b) — simpler than a second QAbstractItemModel and Qt-native for selection/keyboard nav."
  - "Recent stations carried on Qt.UserRole payload of QStandardItem — click handler retrieves the Station via index.data(Qt.UserRole) without maintaining a parallel list."
metrics:
  completed: 2026-04-11
  duration: ~18min
  tasks: 3
  files_created: 6
  files_modified: 2
  tests_added: 18
  tests_total: 284
---

# Phase 37 Plan 01: Station List Panel Summary

Built the Phase 37 left panel foundation: a `QAbstractItemModel`-backed provider-grouped station tree (`StationTreeModel`) plus a `QWidget` host (`StationListPanel`) that also renders a Recently Played section. Ships the `audio-x-generic-symbolic.svg` Adwaita fallback icon via `icons.qrc` and emits the `station_activated(Station)` signal that Plan 37-04 will wire to `Player.play`.

## What Shipped

### StationTreeModel (`musicstreamer/ui_qt/station_tree_model.py`)
Two-level tree: invisible root → provider group nodes → station rows. Key behaviors:
- Provider labels include `(N)` count suffix (D-04): `"SomaFM (2)"`.
- Provider rows return `Qt.ItemIsEnabled` only — **not** `Qt.ItemIsSelectable` (D-03).
- Station rows return `Qt.ItemIsEnabled | Qt.ItemIsSelectable`.
- `parent()` of a top-level provider node returns an invalid `QModelIndex()` (Pitfall §4 — prevents `expandAll()` infinite recursion).
- `columnCount() == 1` (Pitfall §7).
- `DecorationRole` returns a 32×32 `QIcon` via `QPixmapCache`, falling back to `:/icons/audio-x-generic-symbolic.svg` when `station.station_art_path` is None or the file is missing.
- `FontRole` for provider rows returns a bold 13pt `QFont` (UI-SPEC Heading role).
- `station_for_index(idx)` returns the underlying `Station` for a station row, `None` for providers/invalid.
- `refresh(stations)` uses `beginResetModel`/`endResetModel` for safe rebuilds.

### StationListPanel (`musicstreamer/ui_qt/station_list_panel.py`)
`QWidget` host with `QVBoxLayout` containing:
1. `"Recently Played"` QLabel (9pt Normal).
2. `recent_view: QListView` backed by `QStandardItemModel`, populated from `repo.list_recently_played(3)`. Each item carries its `Station` on `Qt.UserRole`. Max height 160px, icon size 32×32.
3. `QFrame.HLine` separator (sunken).
4. `tree: QTreeView` backed by `StationTreeModel(repo.list_stations())`. Configured per UI-SPEC: `setHeaderHidden(True)`, `setRootIsDecorated(False)`, `setIndentation(16)`, `setUniformRowHeights(True)`, `setIconSize(QSize(32, 32))`, `SingleSelection`, `expandAll()`.

Click-to-play surface:
- `station_activated = Signal(Station)` — public.
- `tree.clicked` / `tree.doubleClicked` → `_on_tree_activated` (bound method). Provider-row clicks resolve to `None` via `station_for_index` and are silently dropped.
- `recent_view.clicked` → `_on_recent_clicked` — pulls `Station` from `index.data(Qt.UserRole)` and emits.

Zero self-capturing lambdas (`grep 'lambda.*self'` → no match). QA-05 lifetime safety holds.

### Assets
- `musicstreamer/ui_qt/icons/audio-x-generic-symbolic.svg` — verbatim from `/usr/share/icons/Adwaita/symbolic/mimetypes/audio-x-generic-symbolic.svg` (CC-BY-SA 3.0).
- `musicstreamer/ui_qt/icons/NOTICE.md` — attribution table for all bundled icons, extensible for Plan 37-02's three media control icons.
- `musicstreamer/ui_qt/icons.qrc` — entry added.
- `musicstreamer/ui_qt/icons_rc.py` — regenerated via `pyside6-rcc`.

### Tests
- `tests/test_station_tree_model.py` — 9 tests:
  - `test_empty_stations_zero_rowcount`
  - `test_provider_grouping_row_counts`
  - `test_provider_label_includes_count_suffix`
  - `test_top_level_parent_is_invalid` (Pitfall §4)
  - `test_flags_provider_not_selectable_station_selectable`
  - `test_station_data_decoration_and_display`
  - `test_station_for_index_lookup`
  - `test_column_count_is_one`
  - `test_decoration_fallback_when_art_path_none`
- `tests/test_station_list_panel.py` — 9 tests:
  - `test_panel_min_width_and_structure`
  - `test_panel_exposes_station_activated_signal`
  - `test_tree_configuration`
  - `test_all_provider_groups_expanded_after_construction`
  - `test_tree_click_on_station_emits_station_activated` (`qtbot.waitSignal`)
  - `test_tree_click_on_provider_does_not_emit`
  - `test_recently_played_populated`
  - `test_recently_played_click_emits_station_activated`
  - `test_recent_view_max_height_and_icon_size`

Full suite: **284 passed** in 1.66s (266 baseline + 18 new).

## Commits

| Task | Message | Commit |
|------|---------|--------|
| 1 | feat(37-01): add audio-x-generic-symbolic.svg for station fallback | `4340792` |
| 2 | feat(37-01): add StationTreeModel with provider grouping | `4dcdddd` |
| 3 | feat(37-01): add StationListPanel with Recently Played + tree | `76ecfac` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test assertion `findChild(QFrame)` returned first QLabel**
- **Found during:** Task 3 verification.
- **Issue:** `QLabel` inherits from `QFrame`, so `panel.findChild(QFrame)` in `test_panel_min_width_and_structure` returned the "Recently Played" label (which has `Shape.NoFrame`), not the separator line.
- **Fix:** Changed the test to filter with `findChildren(QFrame)` and assert at least one child has `frameShape() == QFrame.HLine`. Covered in the same Task 3 commit (`76ecfac`).
- **Impact:** None — test-only correction.

No auth gates, no scope changes, no skipped tasks. Plan-provided acceptance criteria all held up end-to-end; the `grep 'audio_x_generic_symbolic' icons_rc.py` line in T1's criteria does not match because the rcc output is binary data (same pattern as Phase 36's existing icons — the **functional** verify `QIcon(':/icons/…').isNull() is False` was the true gate and it passed).

## Deferred Issues

None.

## Threat Flags

None — this plan adds only a read-only model/view over already-validated `Station` records; no new network surface, file access, or trust boundary.

## Known Stubs

None.

## Integration Notes for Downstream Plans

- **Plan 37-02 (NowPlayingPanel):** Consume `station_activated` signal from `StationListPanel`. Import the shared `_load_station_icon` helper from `station_list_panel.py` for its 180×180 station-logo fallback path (or duplicate the QPixmapCache idiom — helper is deliberately module-level, not class-bound).
- **Plan 37-02 (media icons):** `icons/NOTICE.md` is ready to append `media-playback-start-symbolic.svg`, `media-playback-pause-symbolic.svg`, `media-playback-stop-symbolic.svg` rows.
- **Plan 37-04 (MainWindow integration):** Owns the wiring `StationListPanel(repo).station_activated → MainWindow._on_station_activated → Player.play`. This plan did **not** touch `main_window.py`.
- **Future favorites/search (Phase 38):** `StationTreeModel.refresh(stations)` is ready for a `QSortFilterProxyModel` layering.

## Self-Check: PASSED

Verified:
- `musicstreamer/ui_qt/station_tree_model.py` exists
- `musicstreamer/ui_qt/station_list_panel.py` exists
- `musicstreamer/ui_qt/icons/audio-x-generic-symbolic.svg` exists
- `musicstreamer/ui_qt/icons/NOTICE.md` exists
- `tests/test_station_tree_model.py` exists
- `tests/test_station_list_panel.py` exists
- `musicstreamer/ui_qt/icons.qrc` contains `audio-x-generic-symbolic.svg`
- Commit `4340792` exists (Task 1)
- Commit `4dcdddd` exists (Task 2)
- Commit `76ecfac` exists (Task 3)
- `musicstreamer/ui_qt/main_window.py` untouched
- Full test suite: 284 passed (266 baseline + 18 new)
