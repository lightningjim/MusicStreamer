# Phase 50: Recently Played Live Update — Pattern Map

**Mapped:** 2026-04-27
**Files analyzed:** 4 (2 source modifications, 2 test additions)
**Analogs found:** 4 / 4

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/ui_qt/station_list_panel.py` | component | request-response | `StationListPanel.refresh_model()` (same file, line 314) | exact |
| `musicstreamer/ui_qt/main_window.py` | coordinator/slot | request-response | `_on_station_activated` body (same file, line 320) | exact — new call inserted into existing slot |
| `tests/test_station_list_panel.py` | test | — | existing tests in same file (lines 73–80 and beyond) | exact |
| `tests/test_main_window_integration.py` | test | — | `test_station_activated_updates_last_played` (line 279) | exact |

---

## Pattern Assignments

### `musicstreamer/ui_qt/station_list_panel.py` — add `refresh_recent()`

**Analog:** `StationListPanel.refresh_model()` (same file, lines 314–319)

**Core public-method pattern** (lines 314–319):
```python
def refresh_model(self) -> None:
    """Reload station tree and recently played after external changes (edit/delete/import)."""
    self.model.refresh(self._repo.list_stations())
    self._sync_tree_expansion()
    self._populate_recent()
    self._build_chip_rows()
```

**Private method being wrapped** (lines 357–365):
```python
def _populate_recent(self) -> None:
    self._recent_model.clear()
    stations = self._repo.list_recently_played(3)
    for station in stations:
        item = QStandardItem(station.name)
        item.setIcon(load_station_icon(station))
        item.setEditable(False)
        item.setData(station, Qt.UserRole)
        self._recent_model.appendRow(item)
```

**New method to add** — mirrors `refresh_model()` naming, wraps only the recent path:
```python
def refresh_recent(self) -> None:
    """Refresh the Recently Played list from the DB. Call after update_last_played."""
    self._populate_recent()
```

**Placement:** Insert immediately after `refresh_model()` (after line 319), before `_sync_tree_expansion()` — keeping all public refresh methods grouped together under the `# Public refresh API` comment block at line 311.

**Critical constraint:** Do NOT call `self.model.refresh(...)` or `self._sync_tree_expansion()` — those rebuild the provider tree and collapse groups (SC #3 violation). The new method calls `_populate_recent()` only.

---

### `musicstreamer/ui_qt/main_window.py` — update `_on_station_activated()`

**Analog:** The existing `_on_station_activated` body (lines 320–329)

**Current slot** (lines 320–329):
```python
def _on_station_activated(self, station: Station) -> None:
    """Called when the user selects a station in StationListPanel."""
    self.now_playing.bind_station(station)
    self._player.play(station)
    self._repo.update_last_played(station.id)
    self.now_playing.on_playing_state_changed(True)
    self.show_toast("Connecting…")
    self._media_keys.publish_metadata(station, "", self.now_playing.current_cover_pixmap())
    self._media_keys.set_playback_state("playing")
```

**After edit** — one line inserted at line 325, after `update_last_played`:
```python
def _on_station_activated(self, station: Station) -> None:
    """Called when the user selects a station in StationListPanel."""
    self.now_playing.bind_station(station)
    self._player.play(station)
    self._repo.update_last_played(station.id)
    self.station_panel.refresh_recent()          # NEW — D-04
    self.now_playing.on_playing_state_changed(True)
    self.show_toast("Connecting…")
    self._media_keys.publish_metadata(station, "", self.now_playing.current_cover_pixmap())
    self._media_keys.set_playback_state("playing")
```

**No new imports needed.** `self.station_panel` is already the attribute at `main_window.py:204`.

**Order constraint:** `refresh_recent()` must come AFTER `update_last_played()`. The DB write must precede the UI rebuild or the query returns the old order.

---

### `tests/test_station_list_panel.py` — add `test_refresh_recent_*`

**Analog:** existing test structure (lines 1–80)

**Imports pattern** (lines 6–14):
```python
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QAbstractItemView, QFrame, QListView, QTreeView

from musicstreamer.ui_qt import icons_rc  # noqa: F401
from musicstreamer.ui_qt.station_list_panel import StationListPanel
from musicstreamer.models import Station
```

**`FakeRepo` pattern** (lines 34–70) — `list_recently_played` returns a mutable slice of `self._recent`:
```python
class FakeRepo:
    def __init__(self, stations: list[Station], recent: list[Station]) -> None:
        self._stations = stations
        self._recent = recent

    def list_recently_played(self, n: int = 3) -> list[Station]:
        return list(self._recent[:n])
```

**`make_station` helper** (lines 17–31) — used to construct test stations:
```python
def make_station(sid: int, name: str, provider: str | None, art: str | None = None) -> Station:
    return Station(id=sid, name=name, provider_id=None, provider_name=provider,
                   tags="", station_art_path=art, album_fallback_path=None,
                   icy_disabled=False, streams=[], last_played_at=None)
```

**`_sample_repo()` helper** (lines 59–70) — reused across all panel tests:
```python
def _sample_repo() -> FakeRepo:
    stations = [make_station(1, "Groove Salad", "SomaFM"), ...]
    recent   = [make_station(1, "Groove Salad", "SomaFM"), ...]
    return FakeRepo(stations, recent)
```

**Existing test shape** (lines 73–79) — pattern to follow:
```python
def test_panel_min_width_and_structure(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)
    assert panel.minimumWidth() == 280
```

**New tests to add** — two cases, both following the shape above:

*Test 1 — `refresh_recent()` rebuilds the model with updated data:*
```python
def test_refresh_recent_updates_list(qtbot):
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    new_top = make_station(99, "New Top Station", "TestFM")
    repo._recent = [new_top] + repo._recent          # simulate DB update

    panel.refresh_recent()

    assert panel.recent_view.model().rowCount() == 3
    top_station = panel.recent_view.model().index(0, 0).data(Qt.UserRole)
    assert isinstance(top_station, Station)
    assert top_station.id == 99
```

*Test 2 — `refresh_recent()` does not touch the provider tree (SC #3):*
```python
def test_refresh_recent_does_not_touch_tree(qtbot):
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    panel.tree.expandAll()
    row_count_before = panel.tree.model().rowCount()

    panel.refresh_recent()

    # Tree row count unchanged — provider groups not rebuilt
    assert panel.tree.model().rowCount() == row_count_before
```

**Pitfall to avoid (RESEARCH.md Pitfall #3):** Mutate `repo._recent` before calling `refresh_recent()`, not after. `list_recently_played()` is a snapshot of `_recent` at call time. A test that does not mutate `_recent` first will see the same list before and after and pass vacuously.

---

### `tests/test_main_window_integration.py` — add `test_station_activated_refreshes_recent_list`

**Analog:** `test_station_activated_updates_last_played` (lines 279–282)

**`FakeRepo` in this file** — note `update_last_played` records ids but does NOT mutate `_recent` (lines 97–99):
```python
def update_last_played(self, station_id: int) -> None:
    self._last_played_ids: list = getattr(self, "_last_played_ids", [])
    self._last_played_ids.append(station_id)
```

**`window` fixture** (lines 196–200) — used by all activation tests:
```python
@pytest.fixture
def window(qtbot, fake_player, fake_repo):
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    return w
```

**`fake_repo` fixture** (lines 192–193):
```python
@pytest.fixture
def fake_repo():
    return FakeRepo(stations=[_make_station()])
```

**Closest existing test** (lines 279–282):
```python
def test_station_activated_updates_last_played(qtbot, window, fake_repo):
    station = _make_station()
    window.station_panel.station_activated.emit(station)
    assert fake_repo._last_played_ids == [station.id]
```

**New test to add** — pre-populate `_recent` so `list_recently_played` returns something after activation, then verify the QListView row count:
```python
def test_station_activated_refreshes_recent_list(qtbot, fake_player, fake_repo):
    station = _make_station()
    fake_repo._recent = [station]                    # seed _recent before window creation
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    w.station_panel.station_activated.emit(station)

    assert w.station_panel.recent_view.model().rowCount() >= 1
```

**Pitfall to avoid (RESEARCH.md Pitfall #4):** `FakeRepo._recent` must be populated before or during construction. If `_recent` is empty and `update_last_played` does not prepend to it, `list_recently_played` returns `[]` and the row count stays 0. The test above seeds `_recent` before `MainWindow(...)` is called, so the panel constructs with one recent item and `refresh_recent()` after activation re-queries the same list.

---

## Shared Patterns

### Public "refresh a subset" method shape

**Source:** `StationListPanel.refresh_model()`, `station_list_panel.py:314–319`
**Apply to:** The new `refresh_recent()` method only

The established naming convention is `refresh_<noun>()` where `<noun>` is the scope. The body is a direct delegation to the appropriate private populate method. No arguments. No return value. Docstring names the DB precondition.

### Slot edit pattern: insert one call in sequence

**Source:** `MainWindow._on_station_activated()`, `main_window.py:320–329`
**Apply to:** The one-line insertion in `_on_station_activated`

All side effects in this slot are plain method calls in sequence. The new call follows the same style: no lambda, no signal emit, no error handling wrapper. The call order is load-bearing (DB write before UI rebuild).

### Test: emit signal to trigger slot

**Source:** `test_station_activated_updates_last_played`, `test_main_window_integration.py:279`
**Apply to:** The new integration test

All `_on_station_activated` integration tests fire the slot via `window.station_panel.station_activated.emit(station)` rather than calling `window._on_station_activated(station)` directly. This exercises the real signal connection.

---

## No Analog Found

None. All four files have direct analogs in the existing codebase.

---

## Metadata

**Analog search scope:** `musicstreamer/ui_qt/`, `tests/`
**Files read:** `station_list_panel.py` (lines 308–372), `main_window.py` (lines 318–330), `test_station_list_panel.py` (lines 1–80), `test_main_window_integration.py` (lines 1–299)
**Pattern extraction date:** 2026-04-27
