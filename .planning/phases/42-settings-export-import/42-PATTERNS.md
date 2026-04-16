# Phase 42: Settings Export/Import - Pattern Map

**Mapped:** 2026-04-16
**Files analyzed:** 4 new/modified files
**Analogs found:** 4 / 4

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/settings_export.py` | service | file-I/O + CRUD | `musicstreamer/yt_import.py` (pure logic module, no Qt) | role-match |
| `musicstreamer/ui_qt/settings_import_dialog.py` | component | request-response | `musicstreamer/ui_qt/import_dialog.py` | exact |
| `musicstreamer/ui_qt/main_window.py` (modify) | controller | request-response | `musicstreamer/ui_qt/main_window.py` itself (existing menu wiring) | exact |
| `tests/test_settings_export.py` | test | — | `tests/test_repo.py` | role-match |

---

## Pattern Assignments

### `musicstreamer/settings_export.py` (service, file-I/O + CRUD)

**Analog:** `musicstreamer/repo.py` (DB access patterns) + stdlib zipfile (RESEARCH.md)

**Imports pattern** — copy from `musicstreamer/repo.py` lines 1-5 and extend:
```python
from __future__ import annotations

import datetime
import json
import os
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from typing import List

from musicstreamer import paths
from musicstreamer.repo import Repo
```

**Core export pattern** — `build_zip(repo, dest_path)`:
- Call `repo.list_stations()`, `repo.list_favorites()`, direct `con.execute` for settings rows
- Exclude `audioaddict_listen_key` by key blocklist (D-05)
- Write `settings.json` via `zf.writestr()`
- For each station with `station_art_path`, resolve via `paths.data_dir()` (not `paths.assets_dir()`) — `station_art_path` is relative to data root
- Logo ZIP entry: `logos/{_sanitize(station.name)}{ext}`

**Logo sanitization pattern** (RESEARCH.md Pattern 2, verified):
```python
def _sanitize(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s.-]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return (name[:80] or "station")
```

**ZIP validation pattern** — `preview_import(zip_path, repo)`:
```python
# Raise ValueError on any invalid input — caller (worker thread) catches and emits error signal
try:
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Security: path traversal guard
        for member in zf.infolist():
            if member.filename.startswith('/') or '..' in member.filename:
                raise ValueError(f"Unsafe path in archive: {member.filename}")
        if "settings.json" not in zf.namelist():
            raise ValueError("Missing settings.json")
        payload = json.loads(zf.read("settings.json"))
        if payload.get("version") != 1:
            raise ValueError(f"Unsupported version: {payload.get('version')}")
except zipfile.BadZipFile:
    raise ValueError("Not a valid ZIP archive")
```

**All-or-nothing commit pattern** — `commit_import(preview, repo, mode)`:
```python
# Use repo.con as context manager — implicit BEGIN/COMMIT or ROLLBACK
# Copy from repo.py pattern: repo.con.execute() for direct SQL
with repo.con:
    if mode == "replace_all":
        repo.con.execute("DELETE FROM station_streams")
        repo.con.execute("DELETE FROM stations")
        repo.con.execute("DELETE FROM favorites")
        repo.con.execute("DELETE FROM providers")
    for item in preview.detail_rows:
        if item.action in ("add", "replace"):
            _apply_station(repo, item, mode)
    for fav in preview.track_favorites:
        repo.add_favorite(...)  # INSERT OR IGNORE — from repo.py line 353
```

**Art path convention on import** (Pitfall 1 — critical):
After `repo.insert_station()` returns `station_id`, write logo to:
`assets/{station_id}/station_art{ext}` and call `repo.update_station_art(station_id, f"assets/{station_id}/station_art{ext}")`.
`repo.update_station_art` exists at `musicstreamer/repo.py` line 449.

**Merge replace — stale streams** (Pitfall 2 — critical):
Before re-inserting streams on URL match: `repo.con.execute("DELETE FROM station_streams WHERE station_id=?", (station_id,))`.

---

### `musicstreamer/ui_qt/settings_import_dialog.py` (component, request-response)

**Analog:** `musicstreamer/ui_qt/import_dialog.py`

**Imports pattern** (import_dialog.py lines 21-46):
```python
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QMessageBox,
    QRadioButton,
    QButtonGroup,
    QVBoxLayout,
    QWidget,
)

from musicstreamer.repo import Repo, db_connect
```

**QThread worker pattern** (import_dialog.py lines 72-85 — exact template):
```python
class _ImportPreviewWorker(QThread):
    finished = Signal(object)   # emits ImportPreview dataclass
    error = Signal(str)

    def __init__(self, zip_path: str, parent=None):
        super().__init__(parent)
        self._zip_path = zip_path

    def run(self):
        try:
            from musicstreamer.repo import db_connect, Repo
            repo = Repo(db_connect())   # thread-local connection — NEVER pass from main thread
            result = settings_export.preview_import(self._zip_path, repo)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))
```

**Worker reference retention** (import_dialog.py lines 172-175 — Pitfall 4):
```python
# Store on self to prevent GC before finished signal fires
self._preview_worker: Optional[QThread] = None
self._commit_worker: Optional[QThread] = None
```

**Worker start pattern** (import_dialog.py lines 304-307):
```python
self._preview_worker = _ImportPreviewWorker(zip_path, parent=self)
self._preview_worker.finished.connect(self._on_preview_complete, Qt.QueuedConnection)
self._preview_worker.error.connect(self._on_preview_error, Qt.QueuedConnection)
self._preview_worker.start()
```

**Dialog constructor pattern** (import_dialog.py lines 160-179):
```python
class SettingsImportDialog(QDialog):
    import_complete = Signal()

    def __init__(self, preview, toast_callback: Callable[[str], None], parent=None):
        super().__init__(parent)
        self._toast = toast_callback
        self.setWindowTitle("Import Settings")
        self.setMinimumSize(480, 320)
        self.setModal(True)
        # Store worker refs on self (Pitfall 4)
        self._commit_worker: Optional[QThread] = None
```

**Error display / toast pattern** (import_dialog.py lines 336-340, 377-378):
```python
# Error: show inline label + toast
self._toast(f"Invalid settings file")

# Success: toast + emit signal for station list refresh
self._toast(msg)
self.import_complete.emit()
```

**QListWidget item population** (import_dialog.py lines 323-331 — block signals during bulk insert):
```python
self._detail_list.blockSignals(True)
self._detail_list.clear()
for row in preview.detail_rows:
    item = QListWidgetItem(f"{row.icon} {row.action.title()}: {row.name}")
    self._detail_list.addItem(item)
self._detail_list.blockSignals(False)
```

**Replace All confirmation** (Claude's Discretion — use QMessageBox.warning pattern from cookie_import_dialog.py line 278):
```python
if self._mode_group.checkedId() == REPLACE_ALL:
    reply = QMessageBox.warning(
        self, "Replace All",
        "This will erase your entire station library and replace it with the import. Continue?",
        QMessageBox.Yes | QMessageBox.Cancel,
        QMessageBox.Cancel,
    )
    if reply != QMessageBox.Yes:
        return
```

---

### `musicstreamer/ui_qt/main_window.py` (modify — menu wiring + handlers + workers)

**Analog:** Same file — existing menu action pattern (lines 79-107) and dialog opener pattern (lines 350-369).

**Enable placeholders pattern** (lines 100-107 → replace disabled blocks):
```python
# BEFORE (lines 100-107):
act_export = self._menu.addAction("Export Settings")
act_export.setEnabled(False)
act_import_settings = self._menu.addAction("Import Settings")
act_import_settings.setEnabled(False)

# AFTER: enable + connect (copy pattern from lines 80-84):
act_export = self._menu.addAction("Export Settings")
act_export.triggered.connect(self._on_export_settings)
act_import_settings = self._menu.addAction("Import Settings")
act_import_settings.triggered.connect(self._on_import_settings)
```

**File dialog pattern** (cookie_import_dialog.py lines 212-218 — QFileDialog.getOpenFileName):
```python
from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QFileDialog
import datetime, os

def _on_export_settings(self) -> None:
    docs = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    default = os.path.join(docs, f"musicstreamer-export-{datetime.date.today().isoformat()}.zip")
    path, _ = QFileDialog.getSaveFileName(
        self, "Export Settings", default, "ZIP Archive (*.zip)"
    )
    if not path:
        return
    self._export_worker = _ExportWorker(path, self._repo, parent=self)
    self._export_worker.finished.connect(self._on_export_done, Qt.QueuedConnection)
    self._export_worker.error.connect(self._on_export_error, Qt.QueuedConnection)
    self._export_worker.start()
```

**Dialog opener pattern** (main_window.py lines 350-354):
```python
def _on_import_settings(self) -> None:
    path, _ = QFileDialog.getOpenFileName(
        self, "Import Settings", docs, "ZIP Archive (*.zip)"
    )
    if not path:
        return
    # Launch preview worker; on success show SettingsImportDialog
    self._import_preview_worker = _ImportPreviewWorker(path, parent=self)
    self._import_preview_worker.finished.connect(self._on_import_preview_ready, Qt.QueuedConnection)
    self._import_preview_worker.error.connect(self._on_import_preview_error, Qt.QueuedConnection)
    self._import_preview_worker.start()

def _on_import_preview_ready(self, preview) -> None:
    from musicstreamer.ui_qt.settings_import_dialog import SettingsImportDialog
    dlg = SettingsImportDialog(preview, self.show_toast, parent=self)
    dlg.import_complete.connect(self._refresh_station_list)
    dlg.exec()
```

**New imports to add at top of main_window.py** (follow existing import block lines 44-53):
```python
from musicstreamer.ui_qt.settings_import_dialog import SettingsImportDialog
# (QThread, Signal, QFileDialog, QStandardPaths — add to existing PySide6 imports)
```

**Worker reference retention in MainWindow** (import_dialog.py lines 172-175 pattern):
```python
self._export_worker: Optional[QThread] = None
self._import_preview_worker: Optional[QThread] = None
```

---

### `tests/test_settings_export.py` (test, pure logic — no Qt)

**Analog:** `tests/test_repo.py`

**Fixture pattern** (test_repo.py lines 7-13 — in-memory DB with db_init):
```python
import sqlite3
import pytest
from musicstreamer.repo import Repo, db_init

@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)
```

**paths monkeypatch pattern** (test_paths.py / test_art_paths.py convention):
```python
import musicstreamer.paths as paths_mod

@pytest.fixture(autouse=True)
def isolated_paths(tmp_path):
    paths_mod._root_override = str(tmp_path)
    yield
    paths_mod._root_override = None
```

**Test structure** — one test per SYNC requirement (see RESEARCH.md Validation Architecture):
- `test_build_zip_structure` — assert ZIP contains `settings.json` and `logos/`
- `test_export_content_completeness` — assert all stations/streams/favorites in JSON
- `test_credentials_excluded` — assert `audioaddict_listen_key` absent
- `test_preview_merge` — assert correct add/replace/skip counts
- `test_commit_merge` — assert DB state after merge commit
- `test_commit_replace_all` — assert DB wiped and restored
- `test_cancel_no_change` — assert DB unchanged when commit not called

---

## Shared Patterns

### Toast error display
**Source:** `musicstreamer/ui_qt/main_window.py` line 204, `import_dialog.py` lines 377-384
**Apply to:** All error paths in main_window.py handlers and SettingsImportDialog
```python
self.show_toast("Invalid settings file")   # main_window handler
self._toast("Invalid settings file")        # inside dialog
```

### QThread + Signal worker (threading discipline)
**Source:** `musicstreamer/ui_qt/import_dialog.py` lines 72-153
**Apply to:** All three workers — `_ExportWorker`, `_ImportPreviewWorker`, `_ImportCommitWorker`
- Always open thread-local `Repo(db_connect())` inside `run()` — never pass `self._repo` across thread boundary
- Always store worker as `self._xxx_worker` on the parent widget to prevent GC
- Always connect signals with `Qt.QueuedConnection`

### Repo transaction pattern
**Source:** `musicstreamer/repo.py` lines 353-358 (`add_favorite` — INSERT OR IGNORE) and `con.commit()` after each write
**Apply to:** `commit_import()` in `settings_export.py`
- Use `with repo.con:` for the entire import transaction (atomic)
- Favor direct `repo.con.execute()` for bulk operations not covered by Repo methods

### station_art_path convention
**Source:** `musicstreamer/repo.py` line 449 (`update_station_art`) and `musicstreamer/paths.py` line 34 (`data_dir`)
**Apply to:** Logo extraction in `commit_import()`
- Art paths stored as `assets/{station_id}/station_art{ext}` (relative to `data_dir()`)
- Use `repo.update_station_art(station_id, relative_path)` after writing file

---

## No Analog Found

All files have close analogs. No entries.

---

## Metadata

**Analog search scope:** `musicstreamer/`, `musicstreamer/ui_qt/`, `tests/`
**Files scanned:** `import_dialog.py`, `cookie_import_dialog.py`, `main_window.py`, `repo.py`, `paths.py`, `models.py`, `test_repo.py`, `test_import_dialog.py`
**Pattern extraction date:** 2026-04-16
