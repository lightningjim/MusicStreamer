# Phase 71: Sister Station Expansion - Pattern Map

**Mapped:** 2026-05-12
**Files analyzed:** 11 (3 new, 8 modified)
**Analogs found:** 11 / 11

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `musicstreamer/ui_qt/add_sibling_dialog.py` | dialog (new) | request-response | `musicstreamer/ui_qt/discovery_dialog.py` (modal structure); `musicstreamer/ui_qt/edit_station_dialog.py` (chip QSS, QComboBox) | role-match |
| `tests/test_station_siblings.py` | test (new) | N/A | `tests/test_aa_siblings.py` (_mk factory, one-assert-per-test) + `tests/test_repo.py` (repo fixture with PRAGMA) | exact |
| `tests/test_add_sibling_dialog.py` | test (new) | N/A | `tests/test_discovery_dialog.py` (QDialog test structure, FakeRepo, FakePlayer, qtbot) + `tests/test_edit_station_dialog.py` (dialog fixture, MagicMock repo) | role-match |
| `musicstreamer/repo.py` | model/storage (modified) | CRUD | self — `list_streams`/`insert_stream`/`delete_stream` shapes at lines 190-231; `db_init` executescript at lines 15-67 | exact |
| `musicstreamer/url_helpers.py` | utility/pure function (modified) | transform | self — `find_aa_siblings` at lines 171-234 (tuple shape, self-exclusion, sort) | exact |
| `musicstreamer/ui_qt/edit_station_dialog.py` | dialog (modified) | request-response | self — `navigate_to_sibling Signal(int)` at line 255; `_CHIP_QSS`/`_make_chip` at lines 189-203, 657-666; `_refresh_siblings` at lines 617-651; `_on_sibling_link_activated` at lines 1241-1288 | exact |
| `musicstreamer/ui_qt/now_playing_panel.py` | panel (modified) | request-response | self — `_refresh_siblings` at lines 1182-1224 (call-site swap only) | exact |
| `musicstreamer/settings_export.py` | export/import (modified) | batch/transform | self — `_station_to_dict` at lines 108-132; `_insert_station` at lines 390-425; `commit_import` at lines 275-375 | exact |
| `musicstreamer/ui_qt/main_window.py` | controller (modified) | event-driven | self — `navigate_to_sibling` wiring at lines 788-803; `show_toast` at line 434 | exact |
| `tests/test_settings_export.py` | test (modified) | N/A | self — `repo` fixture at lines 29-35; `seeded_repo` pattern at lines 38-68 | exact |
| `tests/test_edit_station_dialog.py` | test (modified) | N/A | self — `dialog` fixture at lines 60-64; chip toggle test at lines 96-108 | exact |

---

## Pattern Assignments

### `musicstreamer/ui_qt/add_sibling_dialog.py` (dialog, request-response)

**Analog:** `musicstreamer/ui_qt/discovery_dialog.py` (modal QDialog structure + QComboBox + QLineEdit filter) and `musicstreamer/ui_qt/edit_station_dialog.py` (`_CHIP_QSS`, `QComboBox` population pattern).

**Imports pattern** — copy from `discovery_dialog.py` lines 1-30 (DiscoveryDialog heads); prune network/thread imports since AddSiblingDialog is synchronous. Minimum set:

```python
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)
from musicstreamer.repo import Repo
```

**Modal QDialog constructor pattern** (`discovery_dialog.py` lines 158-184):

```python
class DiscoveryDialog(QDialog):
    def __init__(self, player, repo, toast_callback, parent=None):
        super().__init__(parent)
        self._player = player
        self._repo = repo
        self._toast_callback = toast_callback
        ...
        self.setWindowTitle("Discover Stations")
        self.setMinimumSize(720, 520)
        self.setModal(False)
        self._build_ui()
```

For `AddSiblingDialog` adapt to:

```python
class AddSiblingDialog(QDialog):
    def __init__(self, station, repo: Repo, parent=None):
        super().__init__(parent)
        self._current_station = station
        self._current_station_id = station.id
        self._repo = repo
        self._linked_station_name: str = ""   # read by caller after exec()
        ...
        self.setWindowTitle("Add Sibling Station")
        self.setMinimumSize(480, 360)
        self.setModal(True)
        self._build_ui()
```

**VBox root layout pattern** (`discovery_dialog.py` lines 190-193):

```python
def _build_ui(self) -> None:
    root = QVBoxLayout(self)
    root.setContentsMargins(16, 16, 16, 16)
    root.setSpacing(8)
```

**QComboBox population pattern** (`edit_station_dialog.py:_populate` lines 511-513):

```python
for p in self._repo.list_providers():
    self.provider_combo.addItem(p.name)
self.provider_combo.setCurrentText(station.provider_name or "")
```

For `AddSiblingDialog`, adapt to store provider objects for id→name lookup and default-select editing station's provider.

**QDialogButtonBox with overridden labels** (canonical pattern — compose from `edit_station_dialog.py` `button_box` near line 457):

```python
self._button_box = QDialogButtonBox(
    QDialogButtonBox.Ok | QDialogButtonBox.Cancel
)
self._button_box.button(QDialogButtonBox.Ok).setText("Link Station")
self._button_box.button(QDialogButtonBox.Cancel).setText("Don't Link")
self._button_box.button(QDialogButtonBox.Ok).setEnabled(False)
self._button_box.accepted.connect(self._on_accept)
self._button_box.rejected.connect(self.reject)
```

**QListWidget item with UserRole data** (UI-SPEC line 260 — no direct analog but compose from `QListWidgetItem` stdlib pattern):

```python
for st in filtered_stations:
    item = QListWidgetItem(st.name)
    item.setData(Qt.UserRole, st.id)
    self._station_list.addItem(item)
```

**Empty-state non-selectable item** (UI-SPEC lines 275-279):

```python
item = QListWidgetItem("All stations in this provider are already linked.")
item.setFlags(Qt.NoItemFlags)
self._station_list.addItem(item)
```

**`_on_accept` slot**:

```python
def _on_accept(self) -> None:
    item = self._station_list.currentItem()
    if item is None:
        return
    station_id = item.data(Qt.UserRole)
    self._repo.add_sibling_link(self._current_station_id, station_id)
    self._linked_station_name = item.text()
    self.accept()
```

---

### `tests/test_station_siblings.py` (test, new)

**Analog:** `tests/test_aa_siblings.py` (pure helper tests) + `tests/test_repo.py` (repo fixture).

**`_mk` factory pattern** (`test_aa_siblings.py` lines 12-23):

```python
def _mk(id_, name, url):
    """Factory: a minimal Station with one StationStream at `url`."""
    return Station(
        id=id_,
        name=name,
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=[StationStream(id=id_ * 10, station_id=id_, url=url, position=1)],
    )
```

For `test_station_siblings.py`, extend `_mk` to accept `provider_name` (needed to test `find_manual_siblings` tuple's first element):

```python
def _mk(id_, name, provider_name=None, url="http://example.com/stream"):
    return Station(
        id=id_, name=name, provider_id=None, provider_name=provider_name,
        tags="", station_art_path=None, album_fallback_path=None,
        streams=[StationStream(id=id_*10, station_id=id_, url=url, position=1)],
    )
```

**Repo fixture with PRAGMA foreign_keys** (`test_repo.py` lines 7-13):

```python
@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)
```

Copy this fixture verbatim — PRAGMA foreign_keys = ON is mandatory for CASCADE tests (RESEARCH Pitfall 3).

**One-assertion-per-test shape** (`test_aa_siblings.py` lines 26-45):

```python
def test_finds_zenradio_sibling_for_difm_ambient():
    di = _mk(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?...")
    zr = _mk(2, "Ambient", "http://prem4.zenradio.com/zrambient?...")
    siblings = find_aa_siblings([di, zr], current_station_id=1, ...)
    assert siblings == [("zenradio", 2, "Ambient")]

def test_excludes_self_by_id():
    di = _mk(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?...")
    siblings = find_aa_siblings([di], current_station_id=1, ...)
    assert siblings == []
```

Mirror this shape for `find_manual_siblings` and `merge_siblings` tests.

---

### `tests/test_add_sibling_dialog.py` (test, new)

**Analog:** `tests/test_discovery_dialog.py` (QDialog + FakeRepo pattern, `qtbot.addWidget`) + `tests/test_edit_station_dialog.py` (MagicMock repo, `dialog` fixture).

**FakeRepo for picker tests** — derive from `test_discovery_dialog.py` FakeRepo (lines 54-80) + extend with `list_providers`, `list_stations`, `list_sibling_links`, `add_sibling_link`:

```python
class FakeRepo:
    def __init__(self) -> None:
        self.add_sibling_link_calls = []
        self._providers = []
        self._stations = []
        self._sibling_links = []

    def list_providers(self):
        return self._providers

    def list_stations(self):
        return self._stations

    def list_sibling_links(self, station_id):
        return self._sibling_links

    def add_sibling_link(self, a_id, b_id):
        self.add_sibling_link_calls.append((a_id, b_id))
```

**Dialog fixture with qtbot** (mirrors `test_edit_station_dialog.py` lines 60-64):

```python
@pytest.fixture()
def dialog(qtbot, station, repo):
    d = AddSiblingDialog(station, repo, parent=None)
    qtbot.addWidget(d)
    return d
```

---

### `musicstreamer/repo.py` — `station_siblings` table + CRUD (modified, CRUD)

**Analog:** self — existing `db_init` executescript (lines 15-66) and `insert_stream`/`delete_stream`/`list_streams` (lines 190-231).

**Schema addition — placement inside executescript body** (after `station_streams` table, `repo.py` lines 51-65):

```python
        CREATE TABLE IF NOT EXISTS station_streams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id INTEGER NOT NULL,
            ...
            FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
        );
```

Add `station_siblings` in the same block, after `station_streams`, before the closing `"""`:

```python
        CREATE TABLE IF NOT EXISTS station_siblings (
          a_id INTEGER NOT NULL,
          b_id INTEGER NOT NULL,
          FOREIGN KEY(a_id) REFERENCES stations(id) ON DELETE CASCADE,
          FOREIGN KEY(b_id) REFERENCES stations(id) ON DELETE CASCADE,
          UNIQUE(a_id, b_id),
          CHECK(a_id < b_id)
        );
```

**CRUD method shape** — copy from `delete_stream`/`insert_stream` pattern (lines 200-224):

```python
def insert_stream(self, station_id: int, url: str, ...) -> int:
    cur = self.con.execute(
        "INSERT INTO station_streams(...) VALUES(?,?,?...)",
        (station_id, url, ...))
    self.con.commit()
    return int(cur.lastrowid)

def delete_stream(self, stream_id: int):
    self.con.execute("DELETE FROM station_streams WHERE id=?", (stream_id,))
    self.con.commit()
```

New methods follow same shape — `con.execute` + `con.commit`, no return value for add/remove:

```python
def add_sibling_link(self, a_id: int, b_id: int) -> None:
    lo, hi = min(a_id, b_id), max(a_id, b_id)
    self.con.execute(
        "INSERT OR IGNORE INTO station_siblings(a_id, b_id) VALUES (?, ?)",
        (lo, hi),
    )
    self.con.commit()

def remove_sibling_link(self, a_id: int, b_id: int) -> None:
    lo, hi = min(a_id, b_id), max(a_id, b_id)
    self.con.execute(
        "DELETE FROM station_siblings WHERE a_id = ? AND b_id = ?",
        (lo, hi),
    )
    self.con.commit()

def list_sibling_links(self, station_id: int) -> list[int]:
    rows = self.con.execute(
        "SELECT b_id AS sid FROM station_siblings WHERE a_id = ? "
        "UNION "
        "SELECT a_id AS sid FROM station_siblings WHERE b_id = ?",
        (station_id, station_id),
    ).fetchall()
    return [r["sid"] for r in rows]
```

---

### `musicstreamer/url_helpers.py` — `find_manual_siblings` + `merge_siblings` (modified, transform)

**Analog:** self — `find_aa_siblings` (lines 171-234) and `render_sibling_html` (lines 237-266).

**Insertion point:** immediately after `find_aa_siblings` at line 234 (before `render_sibling_html` at line 237). Both new helpers are pure functions with the same module convention: no Qt, no DB access, no logging.

**Existing signature to match tuple shape** (`url_helpers.py` lines 171-175):

```python
def find_aa_siblings(
    stations: list,
    current_station_id: int,
    current_first_url: str,
) -> list[tuple[str, int, str]]:
```

**Self-exclusion + sort pattern from `find_aa_siblings`** (lines 208-233):

```python
    for st in stations:
        if st.id == current_station_id:
            continue
        if not st.streams:
            continue
        ...
    siblings.sort(key=lambda t: t[0])
    return [(slug, sid, sname) for _, slug, sid, sname in siblings]
```

**New `find_manual_siblings`** mirrors this pattern:

```python
def find_manual_siblings(
    stations: list,
    current_station_id: int,
    link_ids: list[int],
) -> list[tuple[str, int, str]]:
    """Return (provider_name_or_empty, station_id, station_name) triples.

    link_ids: from Repo.list_sibling_links(current_station_id).
    Excludes current_station_id even if present in link_ids (defensive).
    Sort order: alphabetical by station_name (casefold).
    Pure function — no Qt, no DB access, no logging.
    """
    link_set = set(link_ids)
    result: list[tuple[str, int, str]] = []
    for st in stations:
        if st.id == current_station_id:
            continue
        if st.id not in link_set:
            continue
        result.append((st.provider_name or "", st.id, st.name))
    result.sort(key=lambda t: t[2].casefold())
    return result
```

**New `merge_siblings`** (place immediately after `find_manual_siblings`):

```python
def merge_siblings(
    aa_siblings: list[tuple[str, int, str]],
    manual_siblings: list[tuple[str, int, str]],
) -> list[tuple[str, int, str]]:
    """Deduplicate by station_id; AA entries take precedence.
    Returns aa_siblings + non-duplicate manual_siblings.
    Pure function — no Qt, no DB access.
    """
    seen: set[int] = {sid for _, sid, _ in aa_siblings}
    merged = list(aa_siblings)
    for entry in manual_siblings:
        if entry[1] not in seen:
            merged.append(entry)
            seen.add(entry[1])
    return merged
```

**`render_sibling_html` signature must remain unchanged** (lines 237-240):

```python
def render_sibling_html(
    siblings: list[tuple[str, int, str]],
    current_name: str,
) -> str:
```

The fallback `name_for_slug.get(slug, slug)` at line 259 handles manual entries' `provider_name` string transparently — no change needed to this function.

---

### `musicstreamer/ui_qt/edit_station_dialog.py` — chip row + signals (modified, request-response)

**Analog:** self — lines 185-203 (`_CHIP_QSS`), 255 (`navigate_to_sibling`), 372-374 (FlowLayout chip row for tags), 657-666 (`_make_chip`), 617-651 (`_refresh_siblings`), 1241-1288 (`_on_sibling_link_activated`).

**New Signal declaration** — add adjacent to `navigate_to_sibling = Signal(int)` at line 255:

```python
    navigate_to_sibling = Signal(int)
    # Phase 71: emitted after a manual sibling link is added or removed.
    # MainWindow connects to show_toast. Pattern mirrors NowPlayingPanel
    # gbs_vote_error_toast = Signal(str) (now_playing_panel.py:141).
    sibling_toast = Signal(str)
```

**FlowLayout chip row construction** — copy from tag chip row at lines 372-374:

```python
        self._chips_widget = QWidget()
        self._chips_layout = FlowLayout(self._chips_widget, h_spacing=4, v_spacing=4)
        self._chips_widget.setStyleSheet(_CHIP_QSS)
```

For sibling chip row:

```python
        self._sibling_row_widget = QWidget()
        self._sibling_row_layout = FlowLayout(
            self._sibling_row_widget, h_spacing=4, v_spacing=4
        )
        self._sibling_row_widget.setStyleSheet(_CHIP_QSS)
        self._sibling_row_widget.setContentsMargins(0, 0, 0, 0)
        # Always visible (D-11: authoring surface; + Add sibling must be discoverable)
        outer.addWidget(self._sibling_row_widget)
```

Note: **Remove** the existing `self._sibling_label` block at lines 486-492 (the `QLabel` with `Qt.RichText`). The `_sibling_row_widget` replaces it. The T-40-04 RichText baseline goes down by one (`EditStationDialog` loses its RichText QLabel).

**Existing `_sibling_label` block to REMOVE** (`edit_station_dialog.py` lines 486-492):

```python
        self._sibling_label = QLabel("", self)
        self._sibling_label.setTextFormat(Qt.RichText)
        self._sibling_label.setOpenExternalLinks(False)
        self._sibling_label.setVisible(False)
        self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)
        outer.addWidget(self._sibling_label)
```

**FlowLayout clear pattern** — copy from tag chip helpers in `_on_clear_tags` / `_on_add_tag`. Use `takeAt` + `deleteLater` (RESEARCH Pitfall 5):

```python
        while self._sibling_row_layout.count():
            item = self._sibling_row_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
```

**Manual chip compound widget construction** (UI-SPEC lines 171-200):

```python
        chip_container = QWidget()
        chip_container.setObjectName(f"sibling_chip_{sibling_id}")
        chip_hl = QHBoxLayout(chip_container)
        chip_hl.setContentsMargins(0, 0, 0, 0)
        chip_hl.setSpacing(0)

        name_btn = QPushButton(station_name)
        name_btn.setProperty("chipState", "unselected")
        name_btn.setAccessibleName(station_name)
        name_btn.clicked.connect(
            lambda checked=False, sid=sibling_id: self._on_sibling_link_activated(
                f"sibling://{sid}"
            )
        )
        chip_hl.addWidget(name_btn)

        unlink_btn = QPushButton("×")   # U+00D7 MULTIPLICATION SIGN
        unlink_btn.setProperty("chipState", "unselected")
        unlink_btn.setAccessibleName(f"Unlink {station_name}")
        unlink_btn.setMaximumWidth(24)
        unlink_btn.clicked.connect(
            lambda checked=False, sid=sibling_id, sname=station_name:
                self._on_unlink_sibling(sid, sname)
        )
        chip_hl.addWidget(unlink_btn)

        self._sibling_row_layout.addWidget(chip_container)
```

**AA chip (single QPushButton, no `×`)** (UI-SPEC lines 202-213):

```python
        aa_btn = QPushButton(station_name)
        aa_btn.setProperty("chipState", "unselected")
        aa_btn.setAccessibleName(station_name)
        aa_btn.setToolTip("Auto-detected from AudioAddict URL")
        aa_btn.clicked.connect(
            lambda checked=False, sid=sibling_id: self._on_sibling_link_activated(
                f"sibling://{sid}"
            )
        )
        self._sibling_row_layout.addWidget(aa_btn)
```

**`+ Add sibling` button at end of row**:

```python
        add_btn = QPushButton("+ Add sibling")
        add_btn.setProperty("chipState", "unselected")
        add_btn.clicked.connect(self._on_add_sibling_clicked)
        self._sibling_row_layout.addWidget(add_btn)
```

**`_refresh_siblings` rewrite** — preserve the `url_edit.text().strip()` read (RESEARCH Pitfall 2). Existing structure to extend from (`edit_station_dialog.py` lines 617-651):

```python
    def _refresh_siblings(self) -> None:
        current_url = self.url_edit.text().strip()    # KEEP: reads live URL field
        if not current_url:
            self._sibling_label.setVisible(False)
            return
        all_stations = self._repo.list_stations()
        siblings = find_aa_siblings(
            stations=all_stations,
            current_station_id=self._station.id,
            current_first_url=current_url,
        )
        ...
```

New version replaces from line 638 onward:

```python
    def _refresh_siblings(self) -> None:
        current_url = self.url_edit.text().strip()    # KEEP: reads live URL field

        # Clear chip row
        while self._sibling_row_layout.count():
            item = self._sibling_row_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        all_stations = self._repo.list_stations()
        link_ids = self._repo.list_sibling_links(self._station.id)

        aa_list = find_aa_siblings(
            stations=all_stations,
            current_station_id=self._station.id,
            current_first_url=current_url,
        )
        manual_list = find_manual_siblings(
            stations=all_stations,
            current_station_id=self._station.id,
            link_ids=link_ids,
        )

        aa_ids = {sid for _, sid, _ in aa_list}

        # Render AA chips
        for slug, sibling_id, station_name in aa_list:
            ...  # single QPushButton, no ×

        # Render manual chips (skip if already shown as AA)
        for provider_name, sibling_id, station_name in manual_list:
            if sibling_id in aa_ids:
                continue
            ...  # compound widget with ×

        # + Add sibling button always last
        add_btn = QPushButton("+ Add sibling")
        ...
        self._sibling_row_layout.addWidget(add_btn)
```

**`_on_unlink_sibling` slot** (new, parallel to `_on_sibling_link_activated`):

```python
    def _on_unlink_sibling(self, sibling_id: int, station_name: str) -> None:
        self._repo.remove_sibling_link(self._station.id, sibling_id)
        self._refresh_siblings()
        display_name = station_name[:37] + "…" if len(station_name) > 40 else station_name
        self.sibling_toast.emit(f"Unlinked from {display_name}")
```

**`_on_sibling_link_activated`** at line 1241 — this slot is reused verbatim by both AA and manual name-chip clicks via `f"sibling://{sid}"` href. No change needed to the method body.

---

### `musicstreamer/ui_qt/now_playing_panel.py` — `_refresh_siblings` call-site swap (modified, request-response)

**Analog:** self — `_refresh_siblings` at lines 1182-1224.

**Exact block to modify** (`now_playing_panel.py` lines 1206-1224):

```python
        try:
            all_stations = self._repo.list_stations()
        except Exception:
            self._sibling_label.setVisible(False)
            self._sibling_label.setText("")
            return
        siblings = find_aa_siblings(
            stations=all_stations,
            current_station_id=self._station.id,
            current_first_url=current_url,
        )
        if not siblings:
            self._sibling_label.setVisible(False)
            self._sibling_label.setText("")
            return
        self._sibling_label.setText(
            render_sibling_html(siblings, self._station.name)
        )
        self._sibling_label.setVisible(True)
```

Replace `find_aa_siblings(...)` call with merge helper call. The try/except wrapper and hidden-when-empty contract are **unchanged**:

```python
        try:
            all_stations = self._repo.list_stations()
            link_ids = self._repo.list_sibling_links(self._station.id)
        except Exception:
            self._sibling_label.setVisible(False)
            self._sibling_label.setText("")
            return
        aa_list = find_aa_siblings(
            stations=all_stations,
            current_station_id=self._station.id,
            current_first_url=current_url,
        )
        manual_list = find_manual_siblings(
            stations=all_stations,
            current_station_id=self._station.id,
            link_ids=link_ids,
        )
        siblings = merge_siblings(aa_list, manual_list)
        if not siblings:
            self._sibling_label.setVisible(False)
            self._sibling_label.setText("")
            return
        self._sibling_label.setText(
            render_sibling_html(siblings, self._station.name)
        )
        self._sibling_label.setVisible(True)
```

Also add `find_manual_siblings, merge_siblings` to the `from musicstreamer.url_helpers import ...` line at the top of `now_playing_panel.py`.

---

### `musicstreamer/settings_export.py` — `siblings` field (modified, batch/transform)

**Analog:** self — `_station_to_dict` at lines 108-132; `_insert_station` at lines 390-425; `commit_import` at lines 275-375.

**`_station_to_dict` — add `siblings` key** (after `streams` key at line 131):

```python
def _station_to_dict(station: Station) -> dict:
    return {
        "name": station.name,
        "provider": station.provider_name or "",
        ...
        "streams": [...],
        "siblings": [],    # Phase 71: populated by build_zip second pass
    }
```

The sibling names list is populated in `build_zip` after station serialization, via a second pass that reads `Repo.list_sibling_links(station.id)` and resolves IDs to names.

**Forward-compat read pattern** — copy from Phase 70 idiom at `_insert_station` lines 420-422:

```python
int(stream.get("bitrate_kbps", 0) or 0),   # Phase 70 forward-compat
int(stream.get("sample_rate_hz", 0) or 0), # Phase 70 forward-compat
int(stream.get("bit_depth", 0) or 0),      # Phase 70 forward-compat
```

Apply same pattern for siblings:

```python
sibling_names = list(data.get("siblings") or [])   # old ZIPs missing key → []
```

**Two-pass import in `commit_import`** — must happen INSIDE `with repo.con:` but AFTER all station rows are inserted (RESEARCH Pitfall 1). The existing loop structure (`commit_import` lines 292-330):

```python
    with repo.con:
        if mode == "replace_all":
            ...
        with zipfile.ZipFile(preview.zip_path, "r") as zf:
            ...
            for station_data, detail_row in zip(preview.stations_data, preview.detail_rows):
                action = detail_row.action
                if action == "add" ...:
                    station_id = _insert_station(repo, station_data)
                elif action == "replace":
                    station_id = _replace_station(repo, station_data)
                ...
```

Add second pass AFTER the for-loop, still inside `with repo.con:` and `with zipfile.ZipFile(...) as zf:`:

```python
            # Phase 71: second pass — resolve sibling names to IDs and write links
            name_to_id = {
                r["name"]: r["id"]
                for r in repo.con.execute("SELECT id, name FROM stations").fetchall()
            }
            for station_data, detail_row in zip(preview.stations_data, preview.detail_rows):
                if detail_row.action not in ("add", "replace"):
                    continue
                station_name = station_data.get("name", "")
                station_id = name_to_id.get(station_name)
                if station_id is None:
                    continue
                for sibling_name in list(data.get("siblings") or []):
                    sibling_id = name_to_id.get(sibling_name)
                    if sibling_id is None:
                        continue   # silently drop unresolved names (D-07)
                    lo, hi = min(station_id, sibling_id), max(station_id, sibling_id)
                    repo.con.execute(
                        "INSERT OR IGNORE INTO station_siblings(a_id, b_id) VALUES (?, ?)",
                        (lo, hi),
                    )
```

Note: use `station_data` (not `data`) in the actual implementation; the snippet above is illustrative.

---

### `musicstreamer/ui_qt/main_window.py` — `sibling_toast` wiring (modified, event-driven)

**Analog:** self — `navigate_to_sibling` wiring at lines 788-803.

**Existing `navigate_to_sibling` wiring** (lines 787-802):

```python
        # _on_add_station, lines ~787-789:
        dlg.navigate_to_sibling.connect(self._on_navigate_to_sibling)
        dlg.exec()

        # _on_edit_requested, lines ~801-803:
        dlg.navigate_to_sibling.connect(self._on_navigate_to_sibling)
        dlg.exec()
```

**Add `sibling_toast` wiring in the same two places** — immediately after each `navigate_to_sibling` connect line:

```python
        dlg.navigate_to_sibling.connect(self._on_navigate_to_sibling)
        dlg.sibling_toast.connect(self.show_toast)    # Phase 71: bound-method, QA-05
        dlg.exec()
```

`show_toast` signature (`main_window.py` line 434):

```python
    def show_toast(self, text: str, duration_ms: int = 3000) -> None:
        """Show a toast notification on the centralWidget bottom-centre."""
        self._toast.show_toast(text, duration_ms)
```

No signature change needed — `Signal(str)` passes `text`; `duration_ms` defaults to 3000.

---

### `tests/test_settings_export.py` — siblings round-trip tests (modified)

**Analog:** self — `repo` fixture (lines 29-35), `seeded_repo` fixture (lines 38-68), existing `test_build_zip_*` / `test_commit_import_*` tests.

**`repo` fixture** (lines 29-35) — copy verbatim, it already has `PRAGMA foreign_keys = ON`:

```python
@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)
```

**Pattern for forward-compat test** — model on existing `test_commit_import_merge_adds_new_stations` style (no Phase 70 specific to quote here, but the strategy is: build a minimal ZIP dict without the `siblings` key and assert `commit_import` succeeds without raising):

```python
def test_siblings_missing_key_defaults_empty(repo, tmp_path):
    """Old ZIP without 'siblings' key imports without error."""
    station_data = {"name": "Jazz FM", "provider": "", "tags": "", ...}
    # Note: no "siblings" key
    ...  # build_zip / commit_import
    # assert no exception; assert station_siblings table empty
    rows = repo.con.execute("SELECT * FROM station_siblings").fetchall()
    assert rows == []
```

---

### `tests/test_edit_station_dialog.py` — chip row + sibling_toast tests (modified)

**Analog:** self — `dialog` fixture (lines 60-64), `repo` MagicMock fixture (lines 34-50), tag chip test (lines 96-108).

**MagicMock repo for sibling tests** — extend existing `repo` fixture to add new method mocks:

```python
@pytest.fixture()
def repo():
    r = MagicMock()
    r.list_stations.return_value = []
    r.list_providers.return_value = [Provider(1, "TestProvider"), Provider(2, "Other")]
    r.list_streams.return_value = [...]
    r.ensure_provider.return_value = 1
    # Phase 71: new sibling methods
    r.list_sibling_links.return_value = []     # default: no manual links
    r.add_sibling_link.return_value = None
    r.remove_sibling_link.return_value = None
    return r
```

**Signal capture pattern** — for testing `sibling_toast`, use `qtbot.waitSignal` or manually collect:

```python
def test_x_click_fires_sibling_toast(dialog, repo, qtbot):
    emitted = []
    dialog.sibling_toast.connect(emitted.append)
    # configure repo to return one manual sibling
    ...
    dialog._refresh_siblings()
    # find the × button and click it
    chip = dialog.findChild(QWidget, "sibling_chip_42")
    unlink_btn = chip.findChildren(QPushButton)[1]
    unlink_btn.click()
    assert len(emitted) == 1
    assert "Unlinked from" in emitted[0]
```

---

### `tests/test_now_playing_panel.py` — merged display test (modified)

**Analog:** self — `FakeRepo` class (lines 65-112), `_station` factory (lines 115-118).

**Extend `FakeRepo` with `list_sibling_links`** (add to the existing FakeRepo class at lines 65-112):

```python
    def list_sibling_links(self, station_id: int) -> list:
        return []   # default; override per-test
```

**New test shape** — mirrors existing sibling tests in `test_now_playing_panel.py`:

```python
def test_now_playing_shows_merged_siblings(qtbot, ...):
    """bind_station with manual + AA siblings → both appear in _sibling_label."""
    # Build a station with AA URL
    st = Station(id=1, name="Ambient", ...,
                 streams=[StationStream(url="http://prem1.di.fm:80/ambient_hi?k=x")])
    # Manual sibling
    manual_st = Station(id=99, name="Manual Station", provider_name="SomaFM", ...)
    repo = FakeRepo(stations=[st, manual_st])
    repo._sibling_links = [99]   # list_sibling_links returns [99] for station 1
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(st)
    assert panel._sibling_label.isVisible()
    assert "Manual Station" in panel._sibling_label.text()
```

---

### `tests/test_constants_drift.py` — T-40-04 RichText baseline (modified)

**Analog:** self — `test_no_org_example_literal_remains_in_python_sources` pattern (lines 37-49).

**Existing grep-gate pattern** (lines 37-49):

```python
def test_no_org_example_literal_remains_in_python_sources():
    pkg_root = Path(__file__).parent.parent / "musicstreamer"
    needle = "org.example.MusicStreamer"
    hits = []
    for py in pkg_root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if needle in text:
            hits.append(str(py.relative_to(pkg_root.parent)))
    assert not hits, f"Phase 61 left placeholder behind in: {hits}"
```

**New T-40-04 RichText baseline test** — same file scan, count `setTextFormat(Qt.RichText)` occurrences. After Phase 71, `EditStationDialog` loses its `setTextFormat(Qt.RichText)` call (the `_sibling_label` QLabel is removed), so the count decreases by 1. The UI-SPEC records the current baseline as 9 occurrences across `now_playing_panel.py` (lines 339, 344, 355, 369, 388, 400, 607, 617, 625, 633). Confirm net count after implementation:

```python
def test_richtext_baseline_unchanged_by_phase_71():
    """T-40-04: count of setTextFormat(Qt.RichText) must stay at baseline.

    Phase 71 removes the QLabel in EditStationDialog (_sibling_label) and
    adds NO new RichText labels, so the count should be baseline - 1.
    Update this test's expected value after Phase 71 lands.
    """
    pkg_root = Path(__file__).parent.parent / "musicstreamer"
    needle = "setTextFormat(Qt.RichText)"
    count = 0
    for py in pkg_root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        count += text.count(needle)
    # Planner: set expected to (pre-phase count - 1) after confirming baseline
    assert count == EXPECTED_RICHTEXT_COUNT, (
        f"T-40-04: expected {EXPECTED_RICHTEXT_COUNT} RichText labels, found {count}. "
        "Phase 71 must not add new setTextFormat(Qt.RichText) calls."
    )
```

Planner runs the baseline grep before implementing to establish `EXPECTED_RICHTEXT_COUNT`.

---

## Shared Patterns

### Pattern 1: FlowLayout chip row (used in both `EditStationDialog` and `add_sibling_dialog.py`)

**Source:** `musicstreamer/ui_qt/edit_station_dialog.py` lines 372-374 (tag chip row), 657-666 (`_make_chip`).

```python
# Chip row container + FlowLayout
self._chips_widget = QWidget()
self._chips_layout = FlowLayout(self._chips_widget, h_spacing=4, v_spacing=4)
self._chips_widget.setStyleSheet(_CHIP_QSS)

# Chip factory
def _make_chip(self, tag: str, selected: bool = True) -> QPushButton:
    chip = QPushButton(tag)
    state = "selected" if selected else "unselected"
    chip.setProperty("chipState", state)
    chip.setStyleSheet(_CHIP_QSS)
    chip.style().polish(chip)
    ...
    return chip
```

Apply `_CHIP_QSS` verbatim — no new QSS needed for sibling chips.

### Pattern 2: `Signal(int)` / `Signal(str)` for cross-widget communication

**Source:** `musicstreamer/ui_qt/edit_station_dialog.py` line 255 (`navigate_to_sibling`); `musicstreamer/ui_qt/now_playing_panel.py` line 141 (`gbs_vote_error_toast Signal(str)`).

```python
# EditStationDialog class body:
navigate_to_sibling = Signal(int)       # existing Phase 51
sibling_toast = Signal(str)             # new Phase 71 — parallel pattern
```

Wired in `MainWindow` via bound-method (QA-05):

```python
dlg.navigate_to_sibling.connect(self._on_navigate_to_sibling)
dlg.sibling_toast.connect(self.show_toast)
```

### Pattern 3: Idempotent `CREATE TABLE IF NOT EXISTS` schema migration

**Source:** `musicstreamer/repo.py` lines 15-66 (executescript block).

```python
def db_init(con: sqlite3.Connection):
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS station_streams (
            ...
            FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
        );
        """
    )
    con.commit()
```

New table goes inside the same executescript block. No try/except needed for `CREATE TABLE IF NOT EXISTS` — the `IF NOT EXISTS` clause is the idempotency guarantee.

### Pattern 4: Forward-compat `(data.get("key") or default)` for ZIP import

**Source:** `musicstreamer/settings_export.py` lines 420-422.

```python
int(stream.get("bitrate_kbps", 0) or 0),   # Phase 70 forward-compat
int(stream.get("sample_rate_hz", 0) or 0),
int(stream.get("bit_depth", 0) or 0),
```

For the `siblings` key:

```python
sibling_names = list(data.get("siblings") or [])   # old ZIPs missing key → []
```

### Pattern 5: `sibling://` href scheme + ValueError guard

**Source:** `musicstreamer/ui_qt/edit_station_dialog.py` lines 1257-1263.

```python
        prefix = "sibling://"
        if not href.startswith(prefix):
            return
        try:
            sibling_id = int(href[len(prefix):])
        except ValueError:
            return
```

Chip name buttons connect to `_on_sibling_link_activated(f"sibling://{sid}")` — reusing this guard unchanged.

### Pattern 6: `PRAGMA foreign_keys = ON` in test fixtures

**Source:** `tests/test_repo.py` lines 9-12; `tests/test_settings_export.py` lines 32-33.

```python
con = sqlite3.connect(str(tmp_path / "test.db"))
con.row_factory = sqlite3.Row
con.execute("PRAGMA foreign_keys = ON;")
db_init(con)
```

Every new test fixture (`test_station_siblings.py`, `test_settings_export.py` additions) must include this — required for ON DELETE CASCADE tests (RESEARCH Pitfall 3).

---

## No Analog Found

No files in Phase 71 lack a codebase analog. All patterns have direct precedent.

---

## Metadata

**Analog search scope:** `musicstreamer/` (all `.py`), `tests/` (all `.py`), `.planning/phases/71-*/`
**Files scanned:** ~20 source files + 3 phase documents
**Pattern extraction date:** 2026-05-12
