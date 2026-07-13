# Phase 96: Manual Refresh of Live-Stream URLs from Channel - Pattern Map

**Mapped:** 2026-06-20
**Files analyzed:** 8 (6 modified, 1 new file, 1 new test file)
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/ui_qt/live_refresh_dialog.py` | dialog + worker | request-response (scan → review → apply) | `musicstreamer/ui_qt/import_dialog.py` | exact |
| `musicstreamer/ui_qt/live_refresh_dialog.py` (`_LiveRefreshScanWorker`) | worker (QThread) | request-response | `import_dialog.py:75-101` (`_YtScanWorker`) | exact |
| `musicstreamer/repo.py` — migrations | migration | CRUD | `repo.py:313-334` (Phase 89A/89.1 additive blocks) | exact |
| `musicstreamer/repo.py` — new setter methods | service | CRUD | `repo.py:951-976` (`update_channel_avatar_path`, `update_provider_avatar_path`) | exact |
| `musicstreamer/repo.py` — `list_flagged_stations_for_provider` | service | CRUD | `repo.py:792-825` (`list_recently_played`) | role-match |
| `musicstreamer/models.py` | model | — | `models.py:27-44` (`Station` dataclass, `Provider` dataclass) | exact |
| `musicstreamer/ui_qt/station_tree_model.py` | model | event-driven | `station_tree_model.py:29-36` (`_TreeNode`) + `_populate()` at 209-233 | exact |
| `musicstreamer/ui_qt/station_list_panel.py` | component | event-driven | `station_list_panel.py:682-694` (`_on_tree_context_menu`) | exact |
| `musicstreamer/ui_qt/edit_station_dialog.py` | component | request-response | `edit_station_dialog.py:1289-1295` (URL gate), `134-193` (`_AvatarFetchWorker`) | exact |
| `tests/test_repo.py` — new migration tests | test | — | `tests/test_repo.py:229-253` (`test_cover_art_source_migration_idempotent`) | exact |
| `tests/test_live_refresh_dialog.py` | test | — | `tests/test_station_tree_model.py:1-31` (model unit-test structure) | role-match |
| `tests/test_station_tree_model.py` — new `_TreeNode.provider_id` tests | test | — | `tests/test_station_tree_model.py:34-55` | exact |

---

## Pattern Assignments

---

### `musicstreamer/ui_qt/live_refresh_dialog.py` — `_LiveRefreshScanWorker` (worker, QThread)

**Analog:** `musicstreamer/ui_qt/import_dialog.py:75-101`

**Imports pattern** (import_dialog.py lines 21-48):
```python
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from musicstreamer import yt_import
from musicstreamer.runtime_check import NodeRuntime
from musicstreamer.yt_import import is_yt_playlist_url
from musicstreamer.repo import Repo, db_connect
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX
```

**QThread worker pattern** (import_dialog.py lines 75-101 — copy verbatim, rename class and URL param):
```python
class _LiveRefreshScanWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        url: str,
        toast_callback: Optional[Callable[[str], None]] = None,
        *,
        node_runtime: "NodeRuntime | None" = None,
        parent=None,
    ):
        super().__init__(parent)
        self._url = url
        self._toast = toast_callback
        self._node_runtime = node_runtime  # CRITICAL: thread through; see Pitfall 3

    def run(self):
        try:
            results = yt_import.scan_playlist(
                self._url,
                toast_callback=self._toast,
                node_runtime=self._node_runtime,
            )
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))
```

**Key difference from `_YtScanWorker`:** parameter name is `url` (channel scan URL, not playlist URL), and the docstring must note the node_runtime landmine. The `run()` body is otherwise identical.

---

### `musicstreamer/ui_qt/live_refresh_dialog.py` — `LiveRefreshDialog` (dialog, request-response)

**Analog:** `musicstreamer/ui_qt/import_dialog.py` — `ImportDialog` class + `_on_yt_scan_clicked` + `_on_yt_scan_complete` flow (lines 176-430)

**Dialog constructor pattern** (import_dialog.py lines 176-203):
```python
class ImportDialog(QDialog):
    import_complete = Signal()

    def __init__(self, toast_callback: Callable[[str], None], repo, parent=None, *,
                 node_runtime: "NodeRuntime | None" = None):
        super().__init__(parent)
        self._toast = toast_callback
        self._repo = repo
        self._node_runtime = node_runtime
        self.setWindowTitle("Import Stations")
        self.setMinimumSize(600, 440)
        self.setModal(True)

        self._yt_scan_worker: Optional[QThread] = None
        ...
        root = QVBoxLayout(self)
```

For `LiveRefreshDialog`, adapt to:
```python
class LiveRefreshDialog(QDialog):
    refresh_complete = Signal()  # emitted after successful Apply (not import_complete)

    def __init__(
        self,
        repo: Repo,
        provider_id: int,
        provider_name: str,
        channel_scan_url: str,
        *,
        node_runtime: "NodeRuntime | None" = None,
        toast_callback: Optional[Callable[[str], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._repo = repo
        self._provider_id = provider_id
        self._provider_name = provider_name
        self._channel_scan_url = channel_scan_url
        self._node_runtime = node_runtime
        self._toast = toast_callback
        self._scan_worker: Optional[_LiveRefreshScanWorker] = None
        self.setWindowTitle(f"Refresh Live Streams — {provider_name}")
        self.setMinimumSize(700, 500)
        self.setModal(True)
```

**Scan-kick-off pattern** (import_dialog.py lines 338-354):
```python
    def _on_yt_scan_clicked(self):
        ...
        self._set_yt_busy(True)
        self._yt_list.clear()
        self._yt_status.setText("Scanning playlist…")
        self._yt_progress.setRange(0, 0)  # indeterminate
        self._yt_progress.setVisible(True)

        self._yt_scan_worker = _YtScanWorker(
            url,
            toast_callback=self._toast,
            node_runtime=self._node_runtime,
            parent=self,
        )
        self._yt_scan_worker.finished.connect(self._on_yt_scan_complete, Qt.QueuedConnection)
        self._yt_scan_worker.error.connect(self._on_yt_scan_error, Qt.QueuedConnection)
        self._yt_scan_worker.start()
```

**Scan-complete population pattern** (import_dialog.py lines 356-381):
```python
    def _on_yt_scan_complete(self, results: list):
        self._yt_progress.setVisible(False)
        self._set_yt_busy(False)

        if not results:
            self._yt_status.setText("No live streams found in this playlist.")
            return

        # Populate list — block itemChanged during bulk insert
        self._yt_list.blockSignals(True)
        self._yt_list.clear()
        for entry in results:
            item = QListWidgetItem(entry.get("title", "Untitled"))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)         # NOTE: D-10 mandates Unchecked for drops/adds
            item.setData(Qt.UserRole, entry)
            self._yt_list.addItem(item)
        self._yt_list.blockSignals(False)
```

**Error-handling pattern** (import_dialog.py lines 383-388):
```python
    def _on_yt_scan_error(self, msg: str):
        self._yt_progress.setVisible(False)
        self._set_yt_busy(False)
        self._yt_status.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
        self._yt_status.setText(f"Scan failed: {msg}")
        self._yt_status.setVisible(True)
```

**Apply pattern** (import_dialog.py lines 397-416 — kick-off pattern; Phase 96 persistence is synchronous, so no second worker needed):
```python
    def _on_yt_import_clicked(self):
        entries = []
        for i in range(self._yt_list.count()):
            item = self._yt_list.item(i)
            if item.checkState() == Qt.Checked:
                data = item.data(Qt.UserRole)
                if data:
                    entries.append(data)
        if not entries:
            return
        # ... kick off worker or call _apply_refresh() directly on main thread
```

---

### `musicstreamer/repo.py` — Additive Column Migrations

**Analog:** `musicstreamer/repo.py:313-334` (Phase 89A/89.1 blocks)

**Migration try/except pattern** (repo.py lines 313-334 — the exact shape to copy three times):
```python
    # Phase 89A D-04/D-05 — channel avatar path; nullable TEXT no DEFAULT.
    # NULL means no avatar stored; existing rows backfill automatically.
    # MUST land AFTER the legacy URL-column rebuild block (Pitfall 2): the
    # rebuild's CREATE TABLE stations_new / INSERT SELECT does not carry
    # dynamically-added columns, so placing the ALTER here ensures the column
    # lands on the rebuilt (or fresh) table. Idempotent via the same
    # try/except sqlite3.OperationalError idiom as the Phase 73/82/83 blocks above.
    try:
        con.execute("ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent

    # Phase 89.1 D-11 — provider-level channel avatar; nullable TEXT no DEFAULT.
    # providers has NO legacy rebuild block (unlike stations — see Phase 73/82/83/89A
    # ordering comments). Confirmed by grep: zero hits for 'providers_new' in db_init.
    # Idempotent via the same try/except OperationalError idiom as above.
    try:
        con.execute("ALTER TABLE providers ADD COLUMN avatar_path TEXT")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent
```

**Phase 96 adds these three blocks immediately after line 334** (in this order):
```python
    # Phase 96 D-01 — per-station opt-in flag; INTEGER NOT NULL DEFAULT 0.
    # Existing rows default to 0 (OFF) automatically.
    # MUST land AFTER the legacy URL-column rebuild block (Pitfall 8).
    try:
        con.execute(
            "ALTER TABLE stations ADD COLUMN live_url_syncs_from_channel INTEGER NOT NULL DEFAULT 0"
        )
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent

    # Phase 96 D-03 — title anchor; nullable TEXT no DEFAULT.
    # NULL means flag is ON but anchor not yet captured.
    try:
        con.execute("ALTER TABLE stations ADD COLUMN live_url_title_anchor TEXT")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent

    # Phase 96 D-04 — per-provider channel scan URL; nullable TEXT no DEFAULT.
    # providers has NO legacy rebuild block — safe to add at any position.
    try:
        con.execute("ALTER TABLE providers ADD COLUMN channel_scan_url TEXT")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent
```

---

### `musicstreamer/repo.py` — New Single-Column Setter Methods

**Analog:** `musicstreamer/repo.py:951-976` (`update_channel_avatar_path` + `update_provider_avatar_path`)

**Setter pattern** (repo.py lines 951-976):
```python
    def update_channel_avatar_path(self, station_id: int, path: Optional[str]) -> None:
        """Phase 89 D-13: write channel_avatar_path for station.

        Not routed through update_station to avoid silent-reset of avatar on saves
        that don't touch the avatar column (RESEARCH.md Pitfall 5).
        """
        self.con.execute(
            "UPDATE stations SET channel_avatar_path = ? WHERE id = ?",
            (path, station_id),
        )
        self.con.commit()

    def update_provider_avatar_path(self, provider_id: int, path: Optional[str]) -> None:
        """Phase 89.1 D-09: write avatar_path for provider.

        Not routed through a broad provider update to avoid silent-reset of avatar
        on saves that don't touch the avatar column (same Pitfall 5 rationale as
        update_channel_avatar_path). Dedicated single-column UPDATE only.
        """
        self.con.execute(
            "UPDATE providers SET avatar_path = ? WHERE id = ?",
            (path, provider_id),
        )
        self.con.commit()
```

**Phase 96 adds three setters following this exact shape:**
```python
    def set_live_url_syncs_from_channel(self, station_id: int, value: bool) -> None:
        """Phase 96 D-01: set per-station live URL re-sync flag.

        Not routed through update_station — that method does not include this
        column (Pitfall 1). Dedicated single-column UPDATE only.
        """
        self.con.execute(
            "UPDATE stations SET live_url_syncs_from_channel = ? WHERE id = ?",
            (int(value), station_id),
        )
        self.con.commit()

    def set_live_url_title_anchor(self, station_id: int, title: Optional[str]) -> None:
        """Phase 96 D-03: write/clear the live URL title anchor."""
        self.con.execute(
            "UPDATE stations SET live_url_title_anchor = ? WHERE id = ?",
            (title, station_id),
        )
        self.con.commit()

    def set_provider_channel_scan_url(self, provider_id: int, url: Optional[str]) -> None:
        """Phase 96 D-04: write the channel scan URL for a provider."""
        self.con.execute(
            "UPDATE providers SET channel_scan_url = ? WHERE id = ?",
            (url, provider_id),
        )
        self.con.commit()
```

---

### `musicstreamer/repo.py` — `list_flagged_stations_for_provider`

**Analog:** `musicstreamer/repo.py:792-825` (`list_recently_played`) — same Station-building loop with an added WHERE clause

**Filtered-query + Station-building pattern** (repo.py lines 792-825):
```python
    def list_recently_played(self, n: int = 5) -> List[Station]:
        rows = self.con.execute(
            """
            SELECT s.*, p.name AS provider_name, p.avatar_path AS provider_avatar_path
            FROM stations s
            LEFT JOIN providers p ON p.id = s.provider_id
            WHERE s.last_played_at IS NOT NULL
            ORDER BY s.last_played_at DESC
            LIMIT ?
            """,
            (n,),
        ).fetchall()
        return [
            Station(
                id=r["id"],
                name=r["name"],
                provider_id=r["provider_id"],
                provider_name=r["provider_name"],
                tags=r["tags"] or "",
                station_art_path=r["station_art_path"],
                album_fallback_path=r["album_fallback_path"],
                icy_disabled=bool(r["icy_disabled"]),
                cover_art_source=r["cover_art_source"] or "auto",
                last_played_at=r["last_played_at"],
                is_favorite=bool(r["is_favorite"]),
                preferred_stream_id=r["preferred_stream_id"],
                streams=self.list_streams(r["id"]),
                prerolls=self.list_prerolls(r["id"]),
                prerolls_fetched_at=r["prerolls_fetched_at"],
                channel_avatar_path=r["channel_avatar_path"],
                provider_avatar_path=r["provider_avatar_path"],
            )
            for r in rows
        ]
```

**Phase 96 adaptation** — change the WHERE clause and add the two new Phase 96 fields to the Station constructor:
```python
    def list_flagged_stations_for_provider(self, provider_id: int) -> List[Station]:
        """Phase 96 D-04: stations for this provider where live_url_syncs_from_channel=1."""
        rows = self.con.execute(
            """
            SELECT s.*, p.name AS provider_name, p.avatar_path AS provider_avatar_path
            FROM stations s
            LEFT JOIN providers p ON p.id = s.provider_id
            WHERE s.provider_id = ?
              AND s.live_url_syncs_from_channel = 1
            ORDER BY s.name COLLATE NOCASE
            """,
            (provider_id,),
        ).fetchall()
        return [
            Station(
                ...,                                                         # all existing fields
                live_url_syncs_from_channel=bool(r["live_url_syncs_from_channel"]),  # Phase 96
                live_url_title_anchor=r["live_url_title_anchor"],                     # Phase 96
            )
            for r in rows
        ]
```

**Important:** All four existing Station-building queries (`list_stations` L641-673, `get_station` L682-712, `list_recently_played` L792-825, `list_favorite_stations` L911-942) must ALSO gain the two new Phase 96 fields in their Station constructors — see Pitfall 2 in RESEARCH.md.

---

### `musicstreamer/repo.py` — `update_stream` call for refresh update-in-place

**Analog:** `musicstreamer/ui_qt/edit_station_dialog.py:1783-1819` — full-row preserve pattern

**Full-row-preserve before update_stream** (edit_station_dialog.py lines 1783-1819):
```python
        existing_streams = {s.id: s for s in repo.list_streams(station.id)}
        ...
        if stream_id is not None:
            ex = existing_streams.get(stream_id)
            label = ex.label if ex else ""
            stream_type = ex.stream_type if ex else ""
            sample_rate_hz = ex.sample_rate_hz if ex else 0
            bit_depth = ex.bit_depth if ex else 0
            repo.update_stream(
                stream_id, url, label, quality, position, stream_type, codec,
                bitrate_kbps=bitrate_kbps,
                sample_rate_hz=sample_rate_hz,
                bit_depth=bit_depth,
            )
```

**`update_stream` signature** (repo.py lines 564-572):
```python
    def update_stream(self, stream_id: int, url: str, label: str,
                      quality: str, position: int, stream_type: str, codec: str,
                      bitrate_kbps: int = 0,
                      sample_rate_hz: int = 0, bit_depth: int = 0):
        self.con.execute(
            "UPDATE station_streams SET url=?,label=?,quality=?,position=?,stream_type=?,codec=?,bitrate_kbps=?,sample_rate_hz=?,bit_depth=? WHERE id=?",
            (url, label, quality, position, stream_type, codec, bitrate_kbps,
             sample_rate_hz, bit_depth, stream_id))
        self.con.commit()
```

**`list_streams` + `insert_station` signatures** (repo.py lines 490-498, 886-896):
```python
    def list_streams(self, station_id: int) -> List[StationStream]:
        rows = self.con.execute(
            "SELECT * FROM station_streams WHERE station_id=? ORDER BY position", (station_id,)
        ).fetchall()
        return [StationStream(id=r["id"], station_id=r["station_id"], url=r["url"],
                label=r["label"], quality=r["quality"], position=r["position"],
                stream_type=r["stream_type"], codec=r["codec"],
                bitrate_kbps=r["bitrate_kbps"],
                sample_rate_hz=r["sample_rate_hz"], bit_depth=r["bit_depth"]) for r in rows]

    def insert_station(self, name: str, url: str, provider_name: str, tags: str) -> int:
        provider_id = self.ensure_provider(provider_name) if provider_name else None
        cur = self.con.execute(
            "INSERT INTO stations(name, provider_id, tags) VALUES (?, ?, ?)",
            (name, provider_id, tags or ""),
        )
        self.con.commit()
        station_id = int(cur.lastrowid)
        if url:
            self.insert_stream(station_id, url)
        return station_id

    def delete_station(self, station_id: int):
        self.con.execute("DELETE FROM stations WHERE id = ?", (station_id,))
        self.con.commit()
```

---

### `musicstreamer/models.py` — New `Station` and `Provider` Fields

**Analog:** `musicstreamer/models.py:27-44` (existing `Station` dataclass optional fields)

**Existing dataclass tail pattern** (models.py lines 27-44):
```python
@dataclass
class Station:
    id: int
    name: str
    provider_id: Optional[int]
    provider_name: Optional[str]
    tags: str
    station_art_path: Optional[str]
    album_fallback_path: Optional[str]
    icy_disabled: bool = False
    cover_art_source: Literal["auto", "itunes_only", "mb_only"] = "auto"
    streams: List[StationStream] = field(default_factory=list)
    last_played_at: Optional[str] = None
    is_favorite: bool = False
    preferred_stream_id: Optional[int] = None
    prerolls: List[str] = field(default_factory=list)
    prerolls_fetched_at: Optional[int] = None
    channel_avatar_path: Optional[str] = None
    provider_avatar_path: Optional[str] = None
```

**Provider dataclass** (models.py lines 5-8):
```python
@dataclass
class Provider:
    id: int
    name: str
```

**Phase 96 additions** — append to each dataclass (fields with defaults must stay after all non-default fields):
```python
# Append to Station (after provider_avatar_path line 44):
    live_url_syncs_from_channel: bool = False   # Phase 96 D-01
    live_url_title_anchor: Optional[str] = None  # Phase 96 D-03

# Append to Provider (after name line 8):
    channel_scan_url: Optional[str] = None      # Phase 96 D-04
```

Note: `Provider` today has only `id` (no default) and `name` (no default). Adding `channel_scan_url: Optional[str] = None` is safe — all new callers must pass the field if they construct `Provider` manually.

---

### `musicstreamer/ui_qt/station_tree_model.py` — `_TreeNode.provider_id` and `_populate()`

**Analog:** `musicstreamer/ui_qt/station_tree_model.py:29-36` (`_TreeNode` dataclass) + lines 209-233 (`_populate`)

**Existing `_TreeNode`** (station_tree_model.py lines 29-36):
```python
@dataclass
class _TreeNode:
    kind: str  # "root" | "provider" | "station"
    label: str
    parent: Optional["_TreeNode"] = None
    children: list["_TreeNode"] = field(default_factory=list)
    station: Optional[Station] = None
    provider_name: Optional[str] = None  # raw, never gets the " (N)" label suffix (Phase 55 / BUG-06)
```

**Phase 96 addition** — append one field after `provider_name`:
```python
    provider_id: Optional[int] = None  # Phase 96 D-04: for provider context-menu
```

**Existing `_populate` provider-node creation** (station_tree_model.py lines 209-222):
```python
    def _populate(self, stations: list[Station]) -> None:
        groups: dict[str, _TreeNode] = {}
        for st in stations:
            pname = st.provider_name or "Ungrouped"
            grp = groups.get(pname)
            if grp is None:
                grp = _TreeNode(
                    kind="provider",
                    label=pname,
                    parent=self._root,
                    provider_name=pname,  # Phase 55 / BUG-06: round-tripable key for capture/restore
                )
                self._root.children.append(grp)
                groups[pname] = grp
```

**Phase 96 addition** — add `provider_id=st.provider_id` to the `_TreeNode(...)` call:
```python
                grp = _TreeNode(
                    kind="provider",
                    label=pname,
                    parent=self._root,
                    provider_name=pname,
                    provider_id=st.provider_id,  # Phase 96: first station of group sets the id
                )
```

**`station_for_index` pattern for provider detection** (station_tree_model.py lines 81-87):
```python
    def station_for_index(self, index: QModelIndex) -> Optional[Station]:
        if not index.isValid():
            return None
        node: _TreeNode = index.internalPointer()
        if node is None:
            return None
        return node.station if node.kind == "station" else None
```

The same `index.internalPointer()` pattern is used in `_on_tree_context_menu` to detect provider rows.

---

### `musicstreamer/ui_qt/station_list_panel.py` — Provider Context Menu Branch

**Analog:** `musicstreamer/ui_qt/station_list_panel.py:682-694` (`_on_tree_context_menu`)

**Existing station-only context menu** (station_list_panel.py lines 682-694):
```python
    def _on_tree_context_menu(self, pos) -> None:
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        source_idx = self._proxy.mapToSource(index)
        station = self.model.station_for_index(source_idx)
        if station is None:
            return
        menu = QMenu(self)
        edit_action = menu.addAction("Edit Station")
        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action is edit_action:
            self.edit_requested.emit(station)
```

**Phase 96 modification** — insert a provider branch BEFORE the station early-return. The `if station is None: return` becomes the station guard, not a blanket guard:
```python
    def _on_tree_context_menu(self, pos) -> None:
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        source_idx = self._proxy.mapToSource(index)

        # Phase 96 D-04: detect provider row via internalPointer().kind
        node = source_idx.internalPointer()
        if node is not None and node.kind == "provider" and node.provider_id is not None:
            menu = QMenu(self)
            refresh_action = menu.addAction("Refresh live streams…")
            action = menu.exec(self.tree.viewport().mapToGlobal(pos))
            if action is refresh_action:
                self.provider_refresh_requested.emit(
                    node.provider_id,
                    node.provider_name or "",
                )
            return

        station = self.model.station_for_index(source_idx)
        if station is None:
            return
        menu = QMenu(self)
        edit_action = menu.addAction("Edit Station")
        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action is edit_action:
            self.edit_requested.emit(station)
```

**New signal to add to `StationListPanel`** (following the pattern of line 87-90 signal declarations):
```python
    station_activated = Signal(Station)
    station_favorited = Signal(Station, bool)
    edit_requested = Signal(Station)
    new_station_requested = Signal()
    provider_refresh_requested = Signal(int, str)  # Phase 96: provider_id, provider_name
```

**Constructor signature change** (station_list_panel.py line 92):
```python
    # Current:
    def __init__(self, repo, parent: QWidget | None = None) -> None:
    # Phase 96: add node_runtime parameter
    def __init__(self, repo, parent: QWidget | None = None, *, node_runtime: "NodeRuntime | None" = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._node_runtime = node_runtime  # Phase 96: passed to LiveRefreshDialog
```

---

### `musicstreamer/ui_qt/edit_station_dialog.py` — Flag Checkbox and YouTube URL Gate

**Analog:** `musicstreamer/ui_qt/edit_station_dialog.py:1289-1295` (`_on_url_text_changed` YouTube gate) + `134-193` (`_AvatarFetchWorker` for async pattern reference)

**Existing URL gate pattern** (edit_station_dialog.py lines 1289-1295):
```python
    def _on_url_text_changed(self) -> None:
        self._url_timer.start()
        self._logo_status_clear_timer.stop()
        self._logo_status.clear()
        # Phase 89-05 / D-10: gate Refresh button on YouTube URL detection.
        # Phase 89b / D-08: extend gate to include twitch.tv URLs (Pitfall 2).
        url = self.url_edit.text().strip()
        lower = url.lower()
        is_yt = "youtube.com" in lower or "youtu.be" in lower
        is_twitch = "twitch.tv" in lower
        self._refresh_avatar_btn.setEnabled(is_yt or is_twitch)
```

**Phase 96 addition** — append to `_on_url_text_changed()` after the avatar gate line 1295:
```python
        # Phase 96 D-02: live-resync flag checkbox enabled ONLY for YouTube URLs (not Twitch).
        self._live_resync_checkbox.setEnabled(is_yt)
        if not is_yt:
            self._live_resync_checkbox.setChecked(False)
        # Companion channel-URL field visible only when checkbox is enabled and checked
        self._live_resync_channel_url_edit.setVisible(
            is_yt and self._live_resync_checkbox.isChecked()
        )
```

**New checkbox widget construction** (follow the pattern of existing `QCheckBox` widgets in the dialog's form layout):
```python
        self._live_resync_checkbox = QCheckBox("Re-sync live URL from channel")
        self._live_resync_checkbox.setEnabled(False)  # gated on YouTube URL (D-02)
        self._live_resync_checkbox.toggled.connect(self._on_live_resync_toggled)

        self._live_resync_channel_url_edit = QLineEdit()
        self._live_resync_channel_url_edit.setPlaceholderText(
            "https://youtube.com/@Channel/streams"
        )
        self._live_resync_channel_url_edit.setVisible(False)
```

**On-save persistence** — calls dedicated setters, NOT `update_station()`:
```python
        # Phase 96 D-01/D-03/D-04: save flag + anchor + channel URL via dedicated setters.
        # Do NOT add these to update_station() (Pitfall 1).
        flag = self._live_resync_checkbox.isChecked()
        repo.set_live_url_syncs_from_channel(station.id, flag)
        if flag:
            # D-03: anchor = existing stream label or station name
            streams = repo.list_streams(station.id)
            anchor = (streams[0].label if streams else "") or station.name
            repo.set_live_url_title_anchor(station.id, anchor)
            channel_url = self._live_resync_channel_url_edit.text().strip()
            if channel_url and station.provider_id is not None:
                from musicstreamer.yt_import import is_yt_playlist_url
                if is_yt_playlist_url(channel_url):
                    repo.set_provider_channel_scan_url(station.provider_id, channel_url)
```

---

## Shared Patterns

### QThread Worker Shape
**Source:** `musicstreamer/ui_qt/import_dialog.py:75-101` (`_YtScanWorker`)
**Apply to:** `_LiveRefreshScanWorker` in `live_refresh_dialog.py`

Rules (from the threading discipline docstring at import_dialog.py:10-19):
- All blocking I/O runs on daemon QThread workers
- `run()` MUST NOT touch any widget
- `run()` MUST NOT call `QTimer.singleShot`
- Results marshalled to main thread exclusively via queued Signal connections
- Worker stores `node_runtime` in `__init__`; passes it to `scan_playlist`

### Single-Column Setter Pattern (avoid update_station bypass)
**Source:** `musicstreamer/repo.py:951-976`
**Apply to:** All three new Phase 96 setter methods (`set_live_url_syncs_from_channel`, `set_live_url_title_anchor`, `set_provider_channel_scan_url`)

Rule: never route new-column writes through `update_station()` — its SET clause is fixed and will silently ignore new columns.

### Signal Connection Convention
**Source:** `musicstreamer/ui_qt/import_dialog.py:352-353`
**Apply to:** All worker signal connections in `LiveRefreshDialog`

```python
self._scan_worker.finished.connect(self._on_scan_complete, Qt.QueuedConnection)
self._scan_worker.error.connect(self._on_scan_error, Qt.QueuedConnection)
```

Always use `Qt.QueuedConnection` for cross-thread signals.

### Error Color
**Source:** `musicstreamer/ui_qt/_theme.py` (imported as `ERROR_COLOR_HEX`)
**Apply to:** `LiveRefreshDialog` status label styling on scan error

```python
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX
self._status_label.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
```

### Indeterminate Progress Bar
**Source:** `musicstreamer/ui_qt/import_dialog.py:343-344`
**Apply to:** `LiveRefreshDialog` scan-in-progress state

```python
self._progress.setRange(0, 0)   # indeterminate spinner
self._progress.setVisible(True)
```

### Qt.UserRole for entry data
**Source:** `musicstreamer/ui_qt/import_dialog.py:376`
**Apply to:** Any `QListWidgetItem` or table row in `LiveRefreshDialog` that carries a scan entry dict

```python
item.setData(Qt.UserRole, entry)   # attach dict; retrieve with item.data(Qt.UserRole)
```

### Conservative unchecked-by-default (D-10)
**Source:** `import_dialog.py:375` sets `Qt.Checked` for import (opt-in checked). Phase 96 INVERTS this for drop and add rows.

```python
# For REMAP rows: Qt.Checked (user is resolving an existing station)
item.setCheckState(Qt.Checked)
# For DROP rows and ADD rows: Qt.Unchecked (D-10 conservative default)
item.setCheckState(Qt.Unchecked)
```

---

## Migration Test Pattern

### Test fixture and idempotency check
**Source:** `tests/test_repo.py:229-253` (`test_cover_art_source_migration_idempotent`)

**Pattern to copy for each of the three new Phase 96 columns:**
```python
def test_live_url_syncs_from_channel_migration_idempotent(repo):
    """Phase 96 D-01: db_init twice must not raise; column present with DEFAULT 0."""
    db_init(repo.con)
    db_init(repo.con)  # third call for paranoia; still idempotent

    cols = repo.con.execute("PRAGMA table_info('stations')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert "live_url_syncs_from_channel" in by_name
    col = by_name["live_url_syncs_from_channel"]
    # type idx=2, notnull idx=3, dflt_value idx=4
    assert col[2] == "INTEGER"
    assert col[3] == 1, "must be NOT NULL"
    assert col[4] == "0", f"DEFAULT 0 expected; got {col[4]!r}"
```

**Test fixture** (test_repo.py lines 8-14):
```python
@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)
```

### Round-trip test for setter methods
```python
def test_live_url_syncs_from_channel_round_trip(repo):
    sid = repo.create_station()
    assert repo.get_station(sid).live_url_syncs_from_channel is False
    repo.set_live_url_syncs_from_channel(sid, True)
    assert repo.get_station(sid).live_url_syncs_from_channel is True
    repo.set_live_url_syncs_from_channel(sid, False)
    assert repo.get_station(sid).live_url_syncs_from_channel is False
```

---

## No Analog Found

All files have close analogs in the codebase. No files require falling back to RESEARCH.md patterns exclusively.

| File | Note |
|------|------|
| `tests/test_live_refresh_dialog.py` | No existing dialog-logic unit test file exists; structure mirrors `test_station_tree_model.py` for fixtures and `test_repo.py` for isolation pattern. Dialog-specific logic tests (D-05 no-auto-apply, D-10 conservative defaults) have no prior exact analog — implement from RESEARCH.md's test map. |

---

## Metadata

**Analog search scope:** `musicstreamer/`, `musicstreamer/ui_qt/`, `tests/`
**Files scanned:** 9 source files + 2 test files
**Pattern extraction date:** 2026-06-20

**Critical ordering constraint:** The three Phase 96 `ALTER TABLE` blocks in `db_init()` MUST be placed after line 334 (the last existing additive-column block). Placing them before line 208 (the URL-column rebuild block) will cause them to be silently dropped during the `CREATE TABLE stations_new` rebuild. This is the single highest-risk implementation mistake (Pitfall 8 in RESEARCH.md).
