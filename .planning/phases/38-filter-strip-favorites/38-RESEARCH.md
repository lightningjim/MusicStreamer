# Phase 38: Filter Strip + Favorites — Research

**Researched:** 2026-04-12
**Domain:** PySide6 QSortFilterProxyModel, FlowLayout, QButtonGroup, SQLite schema extension
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Search + chip filters compose with AND logic.
- **D-02:** Provider and tag chips auto-populate from station DB data. No manual management.
- **D-03:** OR within dimension, AND between dimensions for multi-select chips.
- **D-04:** `QSortFilterProxyModel` layered on top of existing `StationTreeModel`.
- **D-05:** Segmented control `[Stations | Favorites]` at top of station panel.
- **D-06:** Favorites view: two sections — Favorite Stations (flat list, top) and Favorite Tracks (flat chronological, newest first, bottom).
- **D-07:** Favorite stations stored via new mechanism — boolean `is_favorite` column or separate table. Planner picks simpler approach.
- **D-08:** Track star button on now-playing panel at the `# Plan 38: insert star button here` marker (line 173 of `now_playing_panel.py`). Uses existing `repo.add_favorite()` / `repo.remove_favorite()` / `repo.is_favorited()`.
- **D-09:** Station star button on each station tree row (always visible, right-aligned). Stars/unstars the station itself.
- **D-10:** Visual feedback: immediate icon toggle + brief toast via `MainWindow.show_toast()`.
- **D-11:** Track star button disabled when no station playing or no ICY title. Station star always available.
- **D-12:** Filter strip order top-to-bottom: Segmented control → Search box → Provider chip row → Tag chip row → Tree view.
- **D-13:** Chip rows use FlowLayout (wrapping). Qt has no built-in FlowLayout — implement in-repo from Qt examples pattern.
- **D-14:** "Clear all" action resets search text and deselects all chips. Individual chips toggle on click.
- **D-15:** Filter strip visible in Stations mode only. Hidden (via QStackedWidget page) when Favorites mode active.

### Claude's Discretion
- Exact chip styling (rounded rect, selected state color) — pinned in UI-SPEC.
- Whether search box has a clear (X) button inside — UI-SPEC says `setClearButtonEnabled(True)` (Qt built-in).
- Chip ordering within rows — UI-SPEC says alphabetical.
- Whether segmented control uses `QButtonGroup` + styled `QPushButton`s — UI-SPEC confirms this.
- Empty state text for favorites — pinned in UI-SPEC copywriting.

### Deferred Ideas (OUT OF SCOPE)
- EditStationDialog, edit icon on now-playing → Phase 39 (UI-05)
- Stream picker dropdown → Phase 39 (UI-13)
- DiscoveryDialog, ImportDialog → Phase 39 (UI-06, UI-07)
- AccountsDialog, cookie import, accent color, hamburger menu → Phase 40 (UI-08..UI-11)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-03 | Filter strip — provider and tag chip rows using wrapping FlowLayout, OR-within-dimension AND-between-dimension multi-select | `filter_utils.matches_filter_multi()` already implements the logic; `StationFilterProxyModel(QSortFilterProxyModel)` wraps it for Qt; FlowLayout authored in-repo |
| UI-04 | Favorites view — segmented Stations/Favorites toggle replacing the station list inline, trash button to remove | QStackedWidget toggle pattern; new `favorite_stations` DB table or `is_favorite` column; existing `repo.list_favorites()` for track favorites |
</phase_requirements>

---

## Summary

Phase 38 is an incremental UI-only build on top of the Phase 37 `StationListPanel` and `NowPlayingPanel`. No new backend concepts are introduced. The filter logic is already implemented in `musicstreamer/filter_utils.py` (`matches_filter_multi`) and tested. The primary new Qt work is three widgets: `StationFilterProxyModel` (subclasses `QSortFilterProxyModel`), a `FlowLayout` (in-repo implementation), and the `FavoritesView` panel (two `QListWidget`s under a `QStackedWidget`).

The only DB change required is adding station favorites support. The simplest approach is an `is_favorite` boolean column on the `stations` table via `ALTER TABLE` migration in `db_init()` — matching the existing pattern used for `icy_disabled` and `last_played_at`. A separate `favorite_stations` table is also viable but unnecessary given the station model is already loaded in full by `repo.list_stations()`.

The station star button in the tree requires a custom `QStyledItemDelegate` to paint the star icon right-aligned in each station row. This is the most technically complex piece — the delegate must handle click hit-testing (via `editorEvent`) and emit a signal back to `StationListPanel` to trigger the star toggle.

**Primary recommendation:** Implement in three plans: (1) DB migration + `StationFilterProxyModel` + filter strip UI, (2) favorites view + station star delegate, (3) now-playing track star button + wiring + tests.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.9.2 [VERIFIED: installed] | All Qt widgets | Project standard throughout v2.0 |
| sqlite3 | stdlib | DB migration for `is_favorite` column | Already used via `repo.py` |

### Key Qt Classes (This Phase)
| Class | Module | Purpose |
|-------|--------|---------|
| `QSortFilterProxyModel` | `PySide6.QtCore` | Filter proxy over `StationTreeModel` [VERIFIED: import confirmed] |
| `QStyledItemDelegate` | `PySide6.QtWidgets` | Custom paint + hit-test for station star in tree rows |
| `QButtonGroup` | `PySide6.QtWidgets` | Segmented control (exclusive) and chip groups (non-exclusive) |
| `QStackedWidget` | `PySide6.QtWidgets` | Toggle between Stations page and Favorites page |
| `QListWidget` | `PySide6.QtWidgets` | Flat lists for favorite stations and favorite tracks |
| `QListWidgetItem` | `PySide6.QtWidgets` | Rows in the favorites lists |

### No External Dependencies
All required capabilities are in PySide6 stdlib or already in the project. No new packages to install.

---

## Architecture Patterns

### Recommended Project Structure (new files)
```
musicstreamer/
├── ui_qt/
│   ├── flow_layout.py           # FlowLayout (wrapping layout) — authored in-repo
│   ├── station_filter_proxy.py  # StationFilterProxyModel subclass
│   ├── station_star_delegate.py # QStyledItemDelegate for tree row star button
│   └── favorites_view.py        # FavoritesView widget (QWidget wrapping two QListWidgets)
```

Existing files modified:
- `musicstreamer/ui_qt/station_list_panel.py` — inserts segmented control, filter strip, QStackedWidget
- `musicstreamer/ui_qt/now_playing_panel.py` — inserts track star QToolButton at marker line 173
- `musicstreamer/ui_qt/main_window.py` — wires star signals to toast handler
- `musicstreamer/repo.py` — adds `db_init` migration + `add_favorite_station()`, `remove_favorite_station()`, `list_favorite_stations()`, `is_favorite_station()` methods
- `musicstreamer/ui_qt/icons.qrc` + `icons_rc.py` — adds 4 new SVG icons

### Pattern 1: StationFilterProxyModel
**What:** `QSortFilterProxyModel` subclass that overrides `filterAcceptsRow()` to call `filter_utils.matches_filter_multi()`.
**When to use:** Filtering a `QAbstractItemModel` tree without mutating the model.

```python
# Source: PySide6 QSortFilterProxyModel docs (ASSUMED pattern — standard Qt usage)
from PySide6.QtCore import QModelIndex, QSortFilterProxyModel
from musicstreamer.filter_utils import matches_filter_multi

class StationFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, source_model, parent=None):
        super().__init__(parent)
        self.setSourceModel(source_model)
        self._search_text: str = ""
        self._provider_set: set[str] = set()
        self._tag_set: set[str] = set()

    def set_search(self, text: str) -> None:
        self._search_text = text
        self.invalidateFilter()

    def set_providers(self, providers: set[str]) -> None:
        self._provider_set = providers
        self.invalidateFilter()

    def set_tags(self, tags: set[str]) -> None:
        self._tag_set = tags
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        source = self.sourceModel()
        idx = source.index(source_row, 0, source_parent)
        node = idx.internalPointer()
        if node is None:
            return True
        if node.kind == "provider":
            # Show provider group if any child station passes
            for i in range(source.rowCount(idx)):
                if self.filterAcceptsRow(i, idx):
                    return True
            return False
        if node.kind == "station":
            return matches_filter_multi(
                node.station, self._search_text,
                self._provider_set, self._tag_set
            )
        return True
```

**Critical pitfall:** Provider group rows must recurse into their children. If the proxy rejects a provider row because `filterAcceptsRow` returns `False`, all its children are hidden regardless of the child check. The recursion shown above is the correct approach. [ASSUMED — standard Qt pattern]

### Pattern 2: FlowLayout (in-repo)
**What:** A custom `QLayout` subclass that wraps widgets to new rows when the container width is exceeded.
**When to use:** Chip rows where count varies and window can be narrow.

```python
# Source: Qt FlowLayout example (canonical C++ → Python translation) [ASSUMED — standard pattern]
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy, QWidgetItem

class FlowLayout(QLayout):
    def __init__(self, parent=None, h_spacing: int = 4, v_spacing: int = 8):
        super().__init__(parent)
        self._items: list[QWidgetItem] = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for item in self._items:
            s = s.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return QSize(
            s.width() + margins.left() + margins.right(),
            s.height() + margins.top() + margins.bottom(),
        )

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def _do_layout(self, rect, test_only=False):
        margins = self.contentsMargins()
        x = rect.x() + margins.left()
        y = rect.y() + margins.top()
        row_height = 0
        for item in self._items:
            w = item.widget()
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h_spacing
            if next_x - self._h_spacing > rect.right() - margins.right() and row_height > 0:
                x = rect.x() + margins.left()
                y += row_height + self._v_spacing
                next_x = x + hint.width() + self._h_spacing
                row_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y() + margins.bottom()
```

### Pattern 3: Station Star Delegate
**What:** `QStyledItemDelegate` subclass painting a star icon right-aligned in each station row; `editorEvent` handles mouse press hit-testing.
**When to use:** Adding interactive icons inside tree/list view rows without creating per-row widgets.

```python
# Source: PySide6 QStyledItemDelegate docs [ASSUMED — standard pattern]
from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

class StationStarDelegate(QStyledItemDelegate):
    star_toggled = Signal(object)  # emits Station

    STAR_SIZE = 20
    MARGIN = 4

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        station = index.data(Qt.UserRole)  # requires StationTreeModel to expose via UserRole
        if station is None:
            return
        rect = self._star_rect(option.rect)
        is_fav = self._repo.is_favorite_station(station.id)
        icon_name = "starred-symbolic" if is_fav else "non-starred-symbolic"
        icon = QIcon.fromTheme(icon_name, QIcon(f":/icons/{icon_name}.svg"))
        icon.paint(painter, rect)

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonRelease:
            if self._star_rect(option.rect).contains(event.pos()):
                station = index.data(Qt.UserRole)
                if station is not None:
                    self.star_toggled.emit(station)
                    return True
        return super().editorEvent(event, model, option, index)

    def _star_rect(self, row_rect: QRect) -> QRect:
        x = row_rect.right() - self.STAR_SIZE - self.MARGIN
        y = row_rect.top() + (row_rect.height() - self.STAR_SIZE) // 2
        return QRect(x, y, self.STAR_SIZE, self.STAR_SIZE)
```

**Critical:** `StationTreeModel.data()` must expose `station` via `Qt.UserRole` for station-kind nodes. Currently it does NOT — this must be added in the plan.

### Pattern 4: QSS Property Toggle for Chips
**What:** Setting a custom property triggers QSS re-evaluation.
**When to use:** Chip selected/unselected state, segmented control active/inactive.

```python
# Source: UI-SPEC (VERIFIED: from 38-UI-SPEC.md)
def _set_chip_state(btn, selected: bool) -> None:
    btn.setProperty("chipState", "selected" if selected else "unselected")
    btn.style().unpolish(btn)
    btn.style().polish(btn)
    btn.update()
```

### Pattern 5: DB Migration for is_favorite
**What:** `ALTER TABLE stations ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0` in `db_init()`, inside a try/except `OperationalError` block — identical to existing `icy_disabled` and `last_played_at` migrations.
**When to use:** Adding nullable or defaulted columns to existing SQLite tables.

```python
# Source: repo.py existing migration pattern [VERIFIED: from repo.py lines 67-84]
try:
    con.execute("ALTER TABLE stations ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists
```

### Anti-Patterns to Avoid
- **Lambda slots in QButtonGroup.buttonClicked:** Use bound methods. `QButtonGroup.buttonClicked` passes the clicked `QAbstractButton` — define `_on_provider_chip_clicked(self, btn)` as a bound method.
- **Calling `model.station_for_index()` on proxy indexes:** Proxy indexes must be mapped back to source via `proxy.mapToSource(proxy_idx)` before calling `model.station_for_index()`. Failing to map results in `None` from the model.
- **Setting delegate on the view before setting the proxy model:** Set proxy model first, then `setItemDelegate()`. The delegate uses the proxy's index — wrong order causes stale index issues.
- **Storing filter state only in the proxy:** Clear-all must reset both the proxy's internal state and the UI widget states (QLineEdit, QButtonGroup). Keep them in sync explicitly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Proxy index → source index mapping | Manual row lookup | `QSortFilterProxyModel.mapToSource()` | Qt handles the mapping; custom lookup breaks with sorted/filtered rows |
| Star icon toggle | Separate icon QLabel widget per row | `QStyledItemDelegate.paint()` + `editorEvent()` | Delegates are the Qt pattern; per-row widgets destroy at scroll |
| Chip wrapping layout | `QHBoxLayout` with `setWordWrap` hack | `FlowLayout` (in-repo) | `QHBoxLayout` does not wrap — chips will be clipped on narrow windows |
| Duplicate favorite prevention | Manual list scan before insert | `repo.add_favorite()` already uses `INSERT OR IGNORE` | DB constraint handles it |

---

## Key Discovery: filter_utils Already Exists

`musicstreamer/filter_utils.py` is already implemented and fully tested (26 tests in `test_filter_utils.py`). It provides:
- `normalize_tags(raw: str) -> list[str]` — splits comma/bullet, strips, deduplicates
- `matches_filter(station, search_text, provider_filter, tag_filter)` — single-select logic
- `matches_filter_multi(station, search_text, provider_set, tag_set)` — **the exact multi-select AND/OR logic needed for Phase 38**

[VERIFIED: read from `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/filter_utils.py`]

`StationFilterProxyModel.filterAcceptsRow()` should delegate entirely to `matches_filter_multi()` — no new filter logic needed.

---

## Key Discovery: StationTreeModel Missing Qt.UserRole

`StationTreeModel.data()` currently returns `None` for `Qt.UserRole` on station nodes. [VERIFIED: read from `station_tree_model.py` lines 154-170]

The station star delegate needs `Qt.UserRole` to retrieve the `Station` object. The plan must add this to `StationTreeModel.data()`:

```python
if role == Qt.UserRole and node.kind == "station":
    return node.station
```

This is a one-line addition with no behavior change for existing consumers (the tree panel ignores UserRole currently).

---

## Key Discovery: Four SVG Icons Are Present on the System

All four required icons exist in the Adwaita theme and can be copied directly:
[VERIFIED: `find /usr -name ...` commands above]

| Icon | System Path |
|------|------------|
| `starred-symbolic.svg` | `/usr/share/icons/Adwaita/symbolic/status/starred-symbolic.svg` |
| `non-starred-symbolic.svg` | `/usr/share/icons/Adwaita/symbolic/status/non-starred-symbolic.svg` |
| `user-trash-symbolic.svg` | `/usr/share/icons/Adwaita/symbolic/places/user-trash-symbolic.svg` |
| `edit-clear-all-symbolic.svg` | `/usr/share/icons/Adwaita/symbolic/actions/edit-clear-all-symbolic.svg` |

Plan tasks should copy these to `musicstreamer/ui_qt/icons/`, add entries to `icons.qrc`, and rerun `pyside6-rcc`.

---

## Key Discovery: Existing Test Files for Phase 38

Tests relevant to this phase already exist or need extension:
- `tests/test_filter_utils.py` — 26 tests fully covering `matches_filter_multi`; no changes needed [VERIFIED]
- `tests/test_favorites.py` — covers track favorites repo layer; needs extension for station favorites
- `tests/test_station_list_panel.py` — covers Phase 37 panel; needs new tests for filter strip and proxy
- `tests/test_now_playing_panel.py` — covers Phase 37 panel; needs star button tests

No test files yet exist for: `StationFilterProxyModel`, `FlowLayout`, `StationStarDelegate`, `FavoritesView`. These are Wave 0 gaps.

---

## Common Pitfalls

### Pitfall 1: Proxy Index Not Mapped to Source for station_for_index
**What goes wrong:** `StationListPanel._on_tree_activated(index)` calls `self.model.station_for_index(index)`, where `index` comes from the view. After adding the proxy, the view's indexes are proxy indexes — passing them directly to the source model returns `None`.
**Why it happens:** The view always emits proxy model indexes, not source indexes.
**How to avoid:** Add `source_idx = self._proxy.mapToSource(index)` then `self.model.station_for_index(source_idx)`.
**Warning signs:** Station clicks emit no signal or activate wrong station.

### Pitfall 2: Provider Group Rows Disappear When All Children Filtered Out
**What goes wrong:** `filterAcceptsRow` for provider rows returns `False` without checking children. All provider groups vanish when any filter is active.
**Why it happens:** The proxy calls `filterAcceptsRow` for every row including group rows. The parent check must recurse.
**How to avoid:** Implement the recursive child check shown in Pattern 1 above.
**Warning signs:** Empty tree view when search text is present even if matching stations exist.

### Pitfall 3: QSS Properties Not Re-evaluated After setProperty
**What goes wrong:** Chip stays visually unselected after `setProperty("chipState", "selected")`.
**Why it happens:** Qt does not automatically re-apply QSS when a dynamic property changes. Must call `unpolish()` + `polish()`.
**How to avoid:** Use the helper from Pattern 4: `btn.style().unpolish(btn)` + `btn.style().polish(btn)` + `btn.update()`.
**Warning signs:** Chips toggle their `isChecked()` state but visual appearance doesn't change.

### Pitfall 4: QListWidget Item Widget Height vs Row Height
**What goes wrong:** Trash button rows in the favorite tracks list have inconsistent heights.
**Why it happens:** When `setItemWidget()` is used, the row height follows the item size hint, not the widget size. Must call `item.setSizeHint(QSize(0, 40))` to match the UI-SPEC 40px row height.
**How to avoid:** Set `item.setSizeHint(QSize(0, 40))` for every row that uses `setItemWidget()`.
**Warning signs:** Trash button rows are too short, clipping the widget.

### Pitfall 5: Star Button Disabled State on ICY Title Change
**What goes wrong:** Star button stays enabled after stop, or stays disabled after ICY title arrives.
**Why it happens:** The star button enabled state depends on two conditions: station playing AND ICY title present. These come from separate signal paths (`on_playing_state_changed` and `on_title_changed`).
**How to avoid:** Introduce `_update_star_enabled()` helper called from both slots; checks `self._station is not None and bool(self._last_icy_title)`.
**Warning signs:** Star button can be clicked with no station playing, raising `AttributeError` on `self._station.name`.

---

## DB Schema: Station Favorites

The simpler approach (D-07: planner's choice) is `is_favorite INTEGER NOT NULL DEFAULT 0` on the `stations` table. Analysis:

**`is_favorite` column on stations table (recommended):**
- Migration: one `ALTER TABLE` in `db_init()`, same pattern as `icy_disabled` [VERIFIED: lines 67-72 of repo.py]
- Repo methods needed: `set_station_favorite(station_id, is_favorite)`, `is_favorite_station(station_id)`, `list_favorite_stations()` — all simple single-table queries
- `repo.list_stations()` already returns all station fields; can include `is_favorite` in the `Station` model by adding `is_favorite: bool = False` field
- Avoids a JOIN when loading the favorites view

**Separate `favorite_stations` table (alternative):**
- More normalized but requires a JOIN or two-step query
- Adds complexity without benefit given the station count is small
- Inconsistent with how `is_favorite` booleans are handled elsewhere (e.g. `icy_disabled`)

**Decision to encode in plan:** Use `is_favorite` column on `stations` table.

---

## Layout: QStackedWidget Page Structure

The UI-SPEC Layout Contract (verified from 38-UI-SPEC.md) specifies:

```
StationListPanel outer QVBoxLayout
├── Segmented control row (always visible)
├── QStackedWidget
│   ├── Page 0: Stations mode (search + chips + "Clear all" + recently-played + separator + tree)
│   └── Page 1: Favorites mode (FavoritesView widget)
```

The `StationListPanel.__init__` currently does not have a `QStackedWidget`. Phase 38 inserts one. The segmented control sits outside the stacked widget so it's always visible.

The recently-played section stays on Page 0 (Stations mode). This matches the UI-SPEC layout contract.

---

## Validation Architecture

`workflow.nyquist_validation` is `true` in config.json.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` testpaths=["tests"] |
| Quick run command | `pytest tests/test_station_filter_proxy.py tests/test_flow_layout.py tests/test_favorites.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-03 | `StationFilterProxyModel.filterAcceptsRow` name match | unit | `pytest tests/test_station_filter_proxy.py::test_filter_by_search_text -x` | ❌ Wave 0 |
| UI-03 | `StationFilterProxyModel.filterAcceptsRow` provider OR | unit | `pytest tests/test_station_filter_proxy.py::test_filter_by_provider_set -x` | ❌ Wave 0 |
| UI-03 | `StationFilterProxyModel.filterAcceptsRow` tag OR | unit | `pytest tests/test_station_filter_proxy.py::test_filter_by_tag_set -x` | ❌ Wave 0 |
| UI-03 | Provider group visible when child matches | unit | `pytest tests/test_station_filter_proxy.py::test_provider_group_visible_when_child_matches -x` | ❌ Wave 0 |
| UI-03 | Provider group hidden when no children match | unit | `pytest tests/test_station_filter_proxy.py::test_provider_group_hidden_when_no_children_match -x` | ❌ Wave 0 |
| UI-03 | FlowLayout wraps chips when container narrow | unit | `pytest tests/test_flow_layout.py::test_flow_layout_wraps -x` | ❌ Wave 0 |
| UI-03 | `StationListPanel` emits `station_activated` via proxy index | widget | `pytest tests/test_station_list_panel.py::test_tree_click_via_proxy_emits_station_activated -x` | ❌ Wave 0 |
| UI-04 | `repo.is_favorite_station()` returns True after `set_station_favorite()` | unit | `pytest tests/test_favorites.py::test_station_favorite_add_remove -x` | ❌ Wave 0 |
| UI-04 | `repo.list_favorite_stations()` returns favorited stations | unit | `pytest tests/test_favorites.py::test_list_favorite_stations -x` | ❌ Wave 0 |
| UI-04 | Track star button disabled when no ICY title | widget | `pytest tests/test_now_playing_panel.py::test_star_btn_disabled_without_icy -x` | ❌ Wave 0 |
| UI-04 | Track star button toggles on click + calls repo | widget | `pytest tests/test_now_playing_panel.py::test_star_btn_toggle -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_station_filter_proxy.py tests/test_flow_layout.py tests/test_favorites.py -x -q`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_station_filter_proxy.py` — covers UI-03 proxy filter behavior
- [ ] `tests/test_flow_layout.py` — covers UI-03 FlowLayout geometry
- [ ] Extension of `tests/test_station_list_panel.py` — proxy index mapping tests
- [ ] Extension of `tests/test_favorites.py` — station favorite repo methods
- [ ] Extension of `tests/test_now_playing_panel.py` — star button widget tests

---

## Environment Availability

Step 2.6: No new external dependencies. All work uses PySide6 (already installed, 6.9.2) and stdlib. Adwaita SVG icons located on-system at `/usr/share/icons/Adwaita/symbolic/`. pyside6-rcc is available as part of the PySide6 install.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PySide6 | All UI | ✓ | 6.9.2 | — |
| pyside6-rcc | Icon resource compilation | ✓ | bundled with 6.9.2 | — |
| Adwaita SVG icons | starred, non-starred, trash, clear-all | ✓ | system install | Copy from NOTICE.md Adwaita — all 4 found at `/usr/share/icons/Adwaita/symbolic/` |

---

## Security Domain

No security-relevant changes. Phase is UI filtering and favorites CRUD — no auth, no network, no credential handling, no untrusted input beyond the existing ICY label (already locked down with `Qt.PlainText` in `NowPlayingPanel`).

ASVS V5 (Input Validation): The star button saves the current ICY label text to the DB. ICY text is already rendered with `Qt.PlainText` — the same string going to SQLite via parameterized query in `repo.add_favorite()` is safe. No additional sanitization needed.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `filterAcceptsRow` recursive child check is needed for provider group visibility | Architecture Patterns — Pattern 1 | Low — easily tested; if wrong, provider groups always show (partial correctness) |
| A2 | `QStyledItemDelegate.editorEvent` MouseButtonRelease fires reliably for hit-testing the star rect in tree rows | Architecture Patterns — Pattern 3 | Medium — if `editorEvent` intercept doesn't fire, station star can't be clicked; fallback is context menu or hover button |
| A3 | `is_favorite` column on stations table is simpler than a separate join table | DB Schema section | Low — both approaches work; wrong choice adds a migration task but doesn't break behavior |

---

## Open Questions

1. **Station model `is_favorite` field**
   - What we know: `Station` dataclass is in `models.py`; adding `is_favorite: bool = False` is safe (dataclass default).
   - What's unclear: Whether `repo.list_stations()` should eager-load this or defer to `is_favorite_station(id)` per row.
   - Recommendation: Add `is_favorite` field to `Station`, populate in `repo.list_stations()` query — avoids N+1 queries when building chip data.

2. **StationStarDelegate: editorEvent vs mouseReleaseEvent**
   - What we know: PySide6 docs describe `editorEvent` for handling events in delegates. [ASSUMED]
   - What's unclear: Whether the tree view consumes the click before the delegate sees it.
   - Recommendation: Implement with `editorEvent` first; if tree selection interferes, switch to overriding `mousePressEvent` on the view with manual hit-testing.

---

## Sources

### Primary (HIGH confidence)
- `musicstreamer/filter_utils.py` — filter logic already implemented, verified by reading file
- `musicstreamer/repo.py` — full DB layer, migration patterns, favorites API verified by reading file
- `musicstreamer/ui_qt/station_list_panel.py` — Phase 37 panel structure verified
- `musicstreamer/ui_qt/station_tree_model.py` — tree model internals verified (missing UserRole confirmed)
- `musicstreamer/ui_qt/now_playing_panel.py` — marker comment at line 173 verified
- `.planning/phases/38-filter-strip-favorites/38-UI-SPEC.md` — QSS strings, layout contracts, copywriting verified
- `.planning/phases/38-filter-strip-favorites/38-CONTEXT.md` — all decisions verified

### Secondary (MEDIUM confidence)
- System Adwaita icon paths — verified via `find /usr` commands; paths confirmed on this machine

### Tertiary (LOW confidence / ASSUMED)
- `QSortFilterProxyModel.filterAcceptsRow` recursive parent group pattern — standard Qt pattern, not verified via Context7 in this session
- `QStyledItemDelegate.editorEvent` for mouse hit-testing — standard Qt pattern, not verified via Context7 in this session

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PySide6 version confirmed, all APIs are core Qt
- Architecture: HIGH — all patterns derived directly from existing codebase or verified DB layer; two delegate patterns ASSUMED but standard
- Pitfalls: HIGH — proxy index mapping pitfall is a concrete code observation (station_for_index takes source index, view emits proxy index)

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable PySide6 — no fast-moving APIs in scope)
