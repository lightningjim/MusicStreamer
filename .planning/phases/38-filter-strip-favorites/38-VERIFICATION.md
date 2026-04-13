---
phase: 38-filter-strip-favorites
verified: 2026-04-12T21:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Launch the app and expand the filter strip (click the 'Filters' toggle). Type in the search box."
    expected: "Station list filters in real time as you type."
    why_human: "Filter strip starts collapsed (post-fix change). Automated checks confirm the search box connects to the proxy, but visual real-time behavior requires manual inspection."
  - test: "Click provider chips and tag chips in the expanded filter strip."
    expected: "Provider chips apply OR logic within providers; combining with tag chips applies AND between dimensions. Chip rows wrap to new lines on narrow windows."
    why_human: "FlowLayout geometry tests fail due to missing pytest-qt in this environment; wrapping behavior and chip QSS rendering require visual confirmation."
  - test: "Click 'Favorites' in the segmented control."
    expected: "Filter strip disappears, FavoritesView appears. Star a station in tree, switch to Favorites — station appears under 'Favorite Stations'. Click trash on a track — removed."
    why_human: "QStackedWidget page toggle and FavoritesView content require visual confirmation."
  - test: "Play a station, wait for ICY title, click star button on now-playing panel."
    expected: "Toast 'Saved to favorites' appears. Star icon fills. Track appears in Favorites view."
    why_human: "Track star button toggling ICY favorites requires live playback."
  - test: "Stop playback. Inspect star button on now-playing panel."
    expected: "Star button is disabled/dimmed."
    why_human: "Disabled state requires visual inspection."
---

# Phase 38: Filter Strip + Favorites Verification Report

**Phase Goal:** A user can filter stations by search/provider/tag chips and toggle to their favorites list
**Verified:** 2026-04-12
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Typing in the search box filters the station list in real time | VERIFIED | `StationFilterProxyModel` imported and set as tree model in `station_list_panel.py:268-270`; `_on_search_changed` → `self._proxy.set_search(text)` at line 362; `filterAcceptsRow` delegates to `matches_filter_multi` at line 72 of `station_filter_proxy.py` |
| 2 | Provider and tag chip rows wrap on narrow windows; multi-select composes with AND-between / OR-within logic | VERIFIED | `FlowLayout` used for both chip rows (`station_list_panel.py:216,230`); `matches_filter_multi` from `filter_utils.py` handles OR-within/AND-between logic (`station_filter_proxy.py:19,72`) |
| 3 | Toggling the Stations/Favorites control switches to the favorites list inline; trash button removes entries | VERIFIED | `QStackedWidget` at `station_list_panel.py:148`; `FavoritesView` on page 1 (`line 293`); trash `QToolButton` per row calls `repo.remove_favorite` in `favorites_view.py`; `_stack.setCurrentIndex(1)` on Favorites btn click (`line 432`) |
| 4 | Star button on now-playing panel saves an ICY track title to favorites | VERIFIED | `star_btn` inserted at `now_playing_panel.py:178-187`; `_on_star_clicked` calls `repo.add_favorite`/`remove_favorite`; `track_starred` signal emitted and connected to `MainWindow._on_track_starred` → `show_toast` (`main_window.py:107,150-152`) |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/ui_qt/station_filter_proxy.py` | StationFilterProxyModel with set_search, set_providers, set_tags | VERIFIED | Class exists, all methods present, delegates to `matches_filter_multi` |
| `musicstreamer/ui_qt/flow_layout.py` | FlowLayout QLayout subclass | VERIFIED | `class FlowLayout(QLayout)` with `hasHeightForWidth`, `heightForWidth`, `setGeometry` |
| `musicstreamer/repo.py` | is_favorite migration + CRUD methods | VERIFIED | `ALTER TABLE stations ADD COLUMN is_favorite` at line 79; `set_station_favorite`, `is_favorite_station`, `list_favorite_stations` at lines 409-443 |
| `musicstreamer/models.py` | Station.is_favorite field | VERIFIED | `is_favorite: bool = False` at line 35 |
| `musicstreamer/ui_qt/favorites_view.py` | FavoritesView widget | VERIFIED | `class FavoritesView(QWidget)` with `station_activated`, `favorites_changed` signals, `refresh()`, empty state "No favorites yet" |
| `musicstreamer/ui_qt/station_star_delegate.py` | QStyledItemDelegate painting star icons | VERIFIED | `class StationStarDelegate(QStyledItemDelegate)` with `star_toggled` signal, `paint()`, `editorEvent()` |
| `musicstreamer/ui_qt/now_playing_panel.py` | Track star QToolButton | VERIFIED | `self.star_btn` at line 178, `track_starred` signal at line 79, `_update_star_enabled` helper |
| `musicstreamer/ui_qt/icons/starred-symbolic.svg` | SVG icon file | VERIFIED | File exists |
| `musicstreamer/ui_qt/icons/non-starred-symbolic.svg` | SVG icon file | VERIFIED | File exists |
| `musicstreamer/ui_qt/icons/user-trash-symbolic.svg` | SVG icon file | VERIFIED | File exists |
| `musicstreamer/ui_qt/icons/edit-clear-all-symbolic.svg` | SVG icon file | VERIFIED | File exists |
| `tests/test_station_filter_proxy.py` | Unit tests for proxy filter | VERIFIED | File exists, 179 lines of tests |
| `tests/test_flow_layout.py` | Unit tests for FlowLayout geometry | VERIFIED | File exists, tests present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `station_filter_proxy.py` | `filter_utils.py` | `matches_filter_multi()` in `filterAcceptsRow` | WIRED | `from musicstreamer.filter_utils import matches_filter_multi` at line 19; called at line 72 |
| `station_list_panel.py` | `station_filter_proxy.py` | proxy model set as tree view model | WIRED | `self._proxy = StationFilterProxyModel(parent=self)` → `self.tree.setModel(self._proxy)` at lines 268-270 |
| `station_list_panel.py` | `station_filter_proxy.py` | `mapToSource` before `station_for_index` | WIRED | `source_idx = self._proxy.mapToSource(index)` at lines 399, 451 |
| `station_list_panel.py` | `favorites_view.py` | QStackedWidget page 1 | WIRED | `FavoritesView(self._repo, parent=self._stack)` at line 293; `self._stack.setCurrentIndex(1)` at line 432 |
| `now_playing_panel.py` | `repo.py` | `add_favorite`/`remove_favorite` on star click | WIRED | `self._repo.add_favorite(...)` and `self._repo.remove_favorite(...)` in `_on_star_clicked` |
| `station_star_delegate.py` | `repo.py` | `is_favorite_station` check in paint | WIRED | `self._repo.is_favorite_station(station.id)` at line 52 |
| `main_window.py` | `now_playing_panel.py` | `track_starred` signal → `show_toast` | WIRED | `self.now_playing.track_starred.connect(self._on_track_starred)` at line 107; `show_toast(...)` at line 152 |
| `favorites_view.py` | `station_list_panel.py` | `FavoritesView.station_activated` re-emitted | WIRED | `self._favorites_view.station_activated.connect(self.station_activated.emit)` at line 294 |

### Behavioral Spot-Checks

Test suite cannot run against all phase 38 tests in this environment due to missing `pytest-qt` package (`qtbot` fixture not found). This is a **pre-existing environment issue** — `qtbot` is missing from all test files including those from earlier phases (e.g., `test_station_tree_model.py`, `test_player_volume.py`). Not introduced by phase 38.

Non-qtbot tests in `test_favorites.py` (11 tests covering repo methods) all pass.

| Behavior | Result | Status |
|----------|--------|--------|
| Non-qtbot favorites repo tests (11 tests) | 11 passed, 0 failed | PASS |
| Phase 38 qtbot tests (filter proxy, flow layout, panel, now playing) | Cannot run — pytest-qt not installed | SKIP (pre-existing env issue) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| UI-03 | 38-01-PLAN, 38-02-PLAN | Filter strip — provider and tag chip rows with FlowLayout, OR-within, AND-between | SATISFIED | StationFilterProxyModel, FlowLayout, filter strip UI wired in StationListPanel |
| UI-04 | 38-02-PLAN | Favorites view — segmented Stations/Favorites toggle, trash button to remove | SATISFIED | FavoritesView, StationStarDelegate, QStackedWidget toggle, track star button |

Both requirements explicitly mapped to Phase 38 in REQUIREMENTS.md (lines 126-127). No orphaned requirements for this phase.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `musicstreamer/ui_qt/now_playing_panel.py` | 259-276 | `is_fav` defined inside `if self._station and title:` block but second `if` block at line 269 runs unconditionally — latent NameError risk if blocks are ever merged or `is_fav` referenced in second block | Warning | No current crash (second block doesn't reference `is_fav`); flagged in 38-REVIEW.md as CR-01; fix not applied in post-review commit `f354427` |

The filter strip starts **collapsed** (hidden by default behind a toggle button "Filters") — this is a post-SUMMARY fix in commit `f354427`. The ROADMAP SC "Typing in the search box filters the station list in real time" is still satisfiable (the search box exists and works when the strip is expanded), but the visible-by-default behavior from the UI-SPEC was changed. Not a blocker, but worth noting during visual verification.

### Human Verification Required

#### 1. Real-time search filtering (filter strip collapsed by default)

**Test:** Launch the app. Click the "Filters" toggle to expand the filter strip. Type in the search box.
**Expected:** Station list filters in real time as you type.
**Why human:** Filter strip starts collapsed per post-summary fix commit. Automated check confirms proxy wiring; visual real-time filtering requires manual inspection.

#### 2. Chip row wrapping and multi-select logic

**Test:** Expand the filter strip. Click multiple provider chips and tag chips. Narrow the window.
**Expected:** Provider chips apply OR logic (shows stations from any selected provider). Combining with tag chips applies AND between dimensions. Chip rows wrap to new lines, not clip, on narrow windows.
**Why human:** FlowLayout geometry tests require pytest-qt (not installed). Wrapping behavior and chip QSS visual state (selected/unselected highlight) require visual confirmation.

#### 3. Segmented control Stations/Favorites toggle and favorites workflow

**Test:** Click "Favorites" button. Star a station row in Stations mode (click star icon in tree row). Switch to Favorites. Click trash on a favorite track.
**Expected:** Filter strip disappears when Favorites active. Starred station appears under "Favorite Stations." Trash removes the track row immediately. Empty state ("No favorites yet") shows when all removed.
**Why human:** QStackedWidget page-switch visual behavior and FavoritesView content population require live app interaction.

#### 4. Track star button on now-playing panel

**Test:** Play a station. Wait for ICY title. Click the star button. Click again to unstar.
**Expected:** Toast "Saved to favorites" on star, "Removed from favorites" on unstar. Star icon toggles filled/unfilled. Track appears/disappears from Favorites view.
**Why human:** Requires live playback and ICY metadata.

#### 5. Star button disabled state

**Test:** Stop playback. Observe star button on now-playing panel.
**Expected:** Star button is visually disabled/dimmed.
**Why human:** Disabled visual state requires manual inspection.

---

## Gaps Summary

No blocking gaps. All ROADMAP Success Criteria have implementation evidence. Requirements UI-03 and UI-04 are satisfied by code present in the codebase.

One latent code quality issue (CR-01 from 38-REVIEW.md) remains unfixed in `now_playing_panel.py:259-276` but does not cause a current runtime failure.

Five visual/behavioral items require human verification — the automated pass rate (4/4 truths, 8/8 key links wired) is high.

---

_Verified: 2026-04-12_
_Verifier: Claude (gsd-verifier)_
