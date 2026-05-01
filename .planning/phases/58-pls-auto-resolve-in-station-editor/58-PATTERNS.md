# Phase 58: PLS Auto-Resolve in Station Editor — Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 5 (2 new, 3 modified)
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/playlist_parser.py` | utility | transform | `musicstreamer/url_helpers.py` | role-match (pure helper, no Qt) |
| `tests/test_playlist_parser.py` | test | transform | `tests/test_aa_import.py` (`test_resolve_pls*`) | role-match (pure-helper test, `patch`-based) |
| `musicstreamer/ui_qt/edit_station_dialog.py` | component | request-response | itself — `_LogoFetchWorker` + `_on_logo_fetched` | exact (copy shape within same file) |
| `musicstreamer/aa_import.py` | service | request-response | itself — `_resolve_pls` body | exact (thin-wrapper refactor) |
| `tests/test_edit_station_dialog.py` | test | request-response | itself — Phase 46/47/51 test blocks | exact (extend existing file) |

---

## Pattern Assignments

### `musicstreamer/playlist_parser.py` (utility, transform)

**Analog:** `musicstreamer/url_helpers.py` — pure string/regex module, zero Qt, zero I/O, imported by both `aa_import.py` and `edit_station_dialog.py`.

**Imports pattern** (`url_helpers.py` lines 1-14):
```python
"""Pure URL classification helpers for stream sources.
...
"""
from __future__ import annotations

import html
import urllib.parse

from musicstreamer.aa_import import NETWORKS
```

For `playlist_parser.py` the analogous shape is:
```python
"""Pure playlist parser for PLS, M3U/M3U8, and XSPF formats.

parse_playlist(body, content_type, url_hint) -> list[dict]
Each dict: {url: str, title: str, bitrate_kbps: int, codec: str}
No Qt dependency. No I/O — caller provides the body string.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
```

**Core dispatch pattern** — modeled on the existing `_resolve_pls` regex loop in `aa_import.py` lines 23-46:
```python
def _resolve_pls(pls_url: str) -> list[str]:
    try:
        with urllib.request.urlopen(pls_url, timeout=10) as resp:
            body = resp.read().decode()
        entries = []
        for line in body.splitlines():
            m = re.match(r"^File(\d+)=(.+)$", line.strip())
            if m:
                entries.append((int(m.group(1)), m.group(2).strip()))
        if not entries:
            return [pls_url]
        entries.sort(key=lambda t: t[0])
        return [url for _, url in entries]
    except Exception:
        pass
    return [pls_url]
```

`_parse_pls` in the new module promotes this to return `list[dict]` with `{url, title, bitrate_kbps, codec}`. The file-order sort (`entries.sort(key=lambda t: t[0])`) is preserved verbatim (gap-06 invariant).

**Public entry-point shape** (D-09 contract):
```python
def parse_playlist(
    body: str,
    content_type: str = "",
    url_hint: str = "",
) -> list[dict]:
    """Dispatch to the correct sub-parser by URL extension then Content-Type.

    Returns list of {url, title, bitrate_kbps, codec} dicts in playlist
    file order. Returns [] when format is unrecognized or body is malformed.
    """
    hint = url_hint.lower().split("?")[0]  # strip query string for ext check
    if hint.endswith(".pls"):
        return _parse_pls(body)
    if hint.endswith(".m3u") or hint.endswith(".m3u8"):
        return _parse_m3u(body)
    if hint.endswith(".xspf"):
        return _parse_xspf(body)
    ct = content_type.lower()
    if "scpls" in ct:
        return _parse_pls(body)
    if "mpegurl" in ct or "apple.mpegurl" in ct:
        return _parse_m3u(body)
    if "xspf" in ct:
        return _parse_xspf(body)
    return []
```

**Bitrate/codec extraction pattern** (D-11 — applies equally to PLS, M3U, XSPF title strings):
```python
_BITRATE_RE = re.compile(r"(\d+)\s*k(?:b(?:ps)?)?\b", re.IGNORECASE)
_CODEC_TOKENS = ["HE-AAC", "AAC+", "AAC", "OGG", "FLAC", "OPUS", "MP3", "WMA"]

def _extract_bitrate(title: str) -> int:
    m = _BITRATE_RE.search(title)
    return int(m.group(1)) if m else 0

def _extract_codec(title: str) -> str:
    upper = title.upper()
    for token in _CODEC_TOKENS:
        if token in upper:
            return token
    return ""
```

---

### `tests/test_playlist_parser.py` (test, transform)

**Analog:** `tests/test_aa_import.py` lines 104-128 — test of the existing `_resolve_pls` pure function using `patch` for network I/O. Since `playlist_parser.py` is pure (no I/O), no patching is needed — fixture strings are passed directly.

**File structure pattern** (`test_aa_import.py` lines 1-10):
```python
import json
import urllib.error
from unittest.mock import MagicMock, patch, call

import pytest

from musicstreamer.aa_import import _resolve_pls, fetch_channels, import_stations
```

For `test_playlist_parser.py` the analogous imports:
```python
import pytest

from musicstreamer.playlist_parser import parse_playlist
```

**Fixture-string test pattern** (`test_aa_import.py` lines 104-128):
```python
def test_resolve_pls():
    """_resolve_pls fetches a PLS URL and returns ALL File= stream URLs (gap-06)."""
    pls_content = b"[playlist]\nNumberOfEntries=2\nFile1=http://prem1.di.fm:80/ambient_hi?key\nFile2=http://prem4.di.fm:80/ambient_hi?key\n"

    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(pls_content)):
        result = _resolve_pls("https://listen.di.fm/premium_high/ambient.pls?listen_key=key")

    assert result == [
        "http://prem1.di.fm:80/ambient_hi?key",
        "http://prem4.di.fm:80/ambient_hi?key",
    ]
```

Since `parse_playlist` takes a pre-fetched body string, tests pass body literals directly — no `patch` required:
```python
_PLS_BODY = """\
[playlist]
NumberOfEntries=2
File1=http://prem1.di.fm:80/ambient_hi?key
Title1=Ambient 320k AAC+
File2=http://prem4.di.fm:80/ambient_hi?key
Title2=Ambient 320k AAC+ (fallback)
Length1=-1
Length2=-1
Version=2
"""

def test_parse_pls_basic():
    entries = parse_playlist(_PLS_BODY, url_hint="station.pls")
    assert len(entries) == 2
    assert entries[0]["url"] == "http://prem1.di.fm:80/ambient_hi?key"
    assert entries[0]["title"] == "Ambient 320k AAC+"
    assert entries[0]["bitrate_kbps"] == 320
    assert entries[0]["codec"] == "AAC+"
```

**Error/empty result pattern** (mirrors `test_resolve_pls_fallback_on_error` at line 119):
```python
def test_parse_playlist_unknown_format_returns_empty():
    result = parse_playlist("something", url_hint="file.txt", content_type="text/plain")
    assert result == []
```

---

### `musicstreamer/ui_qt/edit_station_dialog.py` — `_PlaylistFetchWorker` (component, request-response)

**Analog:** `_LogoFetchWorker` at lines 54-122 in the same file. Copy the class shape exactly; replace the body of `run()`.

**Worker class shape** (`edit_station_dialog.py` lines 54-122):
```python
class _LogoFetchWorker(QThread):
    finished = Signal(str, int, str)

    def __init__(self, url: str, token: int, parent=None):
        super().__init__(parent)
        self.setObjectName("logo-fetch-worker")
        self._url = url
        self._token = token

    def run(self):
        token = self._token
        try:
            # ... domain-specific work ...
            self.finished.emit(result, token, classification)
            return
        except Exception:
            self.finished.emit("", token, "")
```

For `_PlaylistFetchWorker`, the analogous shape:
```python
class _PlaylistFetchWorker(QThread):
    # entries: list[dict], error_message: str, token: int
    finished = Signal(list, str, int)

    def __init__(self, url: str, token: int, parent=None):
        super().__init__(parent)
        self.setObjectName("pls-fetch-worker")
        self._url = url
        self._token = token

    def run(self):
        token = self._token
        try:
            import urllib.request
            import socket
            with urllib.request.urlopen(self._url, timeout=10) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read()
            body = raw.decode("utf-8", errors="replace")
            from musicstreamer.playlist_parser import parse_playlist
            entries = parse_playlist(body, content_type=content_type, url_hint=self._url)
            if not entries:
                self.finished.emit([], "No entries found.", token)
                return
            self.finished.emit(entries, "", token)
        except urllib.error.HTTPError as exc:
            self.finished.emit([], f"HTTP {exc.code}: {exc.reason}", token)
        except (urllib.error.URLError, socket.timeout) as exc:
            self.finished.emit([], f"Could not connect: {exc}", token)
        except Exception as exc:
            self.finished.emit([], str(exc) or "Unknown error", token)
```

**Token initialization** — placed alongside `_logo_fetch_token` at `edit_station_dialog.py` lines 246-249:
```python
self._logo_fetch_worker: Optional[_LogoFetchWorker] = None
self._logo_fetch_token: int = 0
# Phase 58: PLS fetch worker and monotonic token (mirrors logo worker above)
self._pls_fetch_worker: Optional[_PlaylistFetchWorker] = None
self._pls_fetch_token: int = 0
```

**Worker start pattern** (`edit_station_dialog.py` lines 682-692) — copy exactly for `_on_add_pls`:
```python
def _on_url_timer_timeout(self) -> None:
    url = self.url_edit.text().strip()
    if not url:
        return
    self._logo_fetch_token += 1
    token = self._logo_fetch_token
    self._logo_status.setText("Fetching…")
    self._fetch_logo_btn.setEnabled(False)
    self._logo_fetch_worker = _LogoFetchWorker(url, token, self)
    self._logo_fetch_worker.finished.connect(self._on_logo_fetched)
    # D-10: wait cursor during fetch. Restored exactly once at the top of
    # _on_logo_fetched (covers success, failure, unsupported, aa_no_key,
    # and stale-token branches — see RESEARCH Pitfall P-1).
    QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
    self._logo_fetch_worker.start()
```

For `_on_add_pls` substitute `_logo_fetch_token` → `_pls_fetch_token`, `_fetch_logo_btn` → `add_pls_btn`, `_LogoFetchWorker` → `_PlaylistFetchWorker`, `_logo_fetch_worker` → `_pls_fetch_worker`, `_on_logo_fetched` → `_on_pls_fetched`.

**Cursor-restore-first-unconditionally pattern** (`edit_station_dialog.py` lines 739-760) — the single most critical pattern to copy:
```python
def _on_logo_fetched(
    self,
    tmp_path: str,
    token: int = 0,
    classification: str = "",
) -> None:
    # D-10/D-11 + P-1: restore cursor BEFORE the stale-token check so that
    # every setOverrideCursor call has exactly one matching restore,
    # regardless of token freshness.
    QApplication.restoreOverrideCursor()

    # Stale response: a newer fetch has been started.
    if token and token != self._logo_fetch_token:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return

    self._fetch_logo_btn.setEnabled(True)
    # ... success/failure branching after ...
```

For `_on_pls_fetched` the analogous shape with button re-enable moved before stale-token check (D-03 specifies restoring button unconditionally alongside cursor):
```python
def _on_pls_fetched(self, entries: list, error_message: str, token: int) -> None:
    # Restore cursor and re-enable button BEFORE stale-token check — every
    # setOverrideCursor must have exactly one matching restore (D-03/D-10).
    QApplication.restoreOverrideCursor()
    self.add_pls_btn.setEnabled(True)

    if token != self._pls_fetch_token:
        return  # stale emission; cursor already restored

    # Branch on outcome ...
```

**`_shutdown_logo_fetch_worker` pattern** (`edit_station_dialog.py` lines 814-829) — copy verbatim, change worker attribute name:
```python
def _shutdown_logo_fetch_worker(self) -> None:
    """Bound-wait for the logo fetch worker so tmp files are cleaned up.

    Capped at 2s to keep UI close snappy. If the worker completes during
    the wait, its queued emission will not be delivered (the dialog is
    tearing down); we rely on stale-token branch logic in the next fetch
    to avoid leaks when the dialog is reused. See WR-02.
    """
    worker = self._logo_fetch_worker
    if worker is None or not worker.isRunning():
        return
    try:
        worker.finished.disconnect()
    except Exception:
        pass
    worker.wait(2000)
```

And the three call sites at `accept()`, `closeEvent()`, `reject()` (`edit_station_dialog.py` lines 831-858):
```python
def accept(self) -> None:
    self._shutdown_logo_fetch_worker()
    super().accept()

def closeEvent(self, event):
    if self._is_new:
        self._repo.delete_station(self._station.id)
        self._is_new = False
    self._shutdown_logo_fetch_worker()
    super().closeEvent(event)

def reject(self) -> None:
    if self._is_new:
        self._repo.delete_station(self._station.id)
        self._is_new = False
    self._shutdown_logo_fetch_worker()
    super().reject()
```

`_shutdown_pls_fetch_worker` is added alongside, and all three call sites call both shutdown methods.

**`_add_stream_row` signature** (`edit_station_dialog.py` lines 603-626) — called by `_apply_pls_entries`:
```python
def _add_stream_row(self, url: str = "", quality: str = "",
                    codec: str = "", bitrate_kbps: int = 0,
                    position: int = 1,
                    stream_id: Optional[int] = None) -> int:
    """Insert a new row in the stream table.

    stream_id stored in URL item's Qt.UserRole — survives row swaps.
    bitrate_kbps=0 renders as empty string (D-12/G-5).
    """
    row = self.streams_table.rowCount()
    self.streams_table.insertRow(row)
    url_item = QTableWidgetItem(url)
    url_item.setData(Qt.UserRole, stream_id)  # None for new rows
    self.streams_table.setItem(row, _COL_URL, url_item)
    self.streams_table.setItem(row, _COL_QUALITY, QTableWidgetItem(quality))
    self.streams_table.setItem(row, _COL_CODEC, QTableWidgetItem(codec))
    self.streams_table.setItem(
        row, _COL_BITRATE,
        QTableWidgetItem(str(bitrate_kbps) if bitrate_kbps else ""),
    )
    self.streams_table.setItem(row, _COL_POSITION, QTableWidgetItem(str(position)))
    return row
```

`_apply_pls_entries` calls this with `stream_id=None` for every resolved entry.

**Button row construction pattern** (`edit_station_dialog.py` lines 362-379) — location for the 5th button:
```python
btn_row = QHBoxLayout()
btn_row.setContentsMargins(0, 0, 0, 0)
btn_row.setSpacing(4)
self.add_stream_btn = QPushButton("Add")
self.remove_stream_btn = QPushButton("Remove")
self.move_up_btn = QPushButton("Move Up")
self.move_down_btn = QPushButton("Move Down")
for btn in (self.add_stream_btn, self.remove_stream_btn,
            self.move_up_btn, self.move_down_btn):
    btn_row.addWidget(btn)
btn_row.addStretch()
# ...
self.add_stream_btn.clicked.connect(self._on_add_stream)
self.remove_stream_btn.clicked.connect(self._on_remove_stream)
self.move_up_btn.clicked.connect(self._on_move_up)
self.move_down_btn.clicked.connect(self._on_move_down)
```

Insert `self.add_pls_btn` into the `for btn in (...)` tuple before `btn_row.addStretch()`, and add its connection after the four existing connections.

**`_snapshot_form_state` / `_is_dirty` pattern** (`edit_station_dialog.py` lines 469-526) — no code changes needed. The streams table snapshot at line 490-497 captures every row's five cell texts into `tuple(streams_snapshot)`. Adding rows via `_add_stream_row` changes `rowCount()`, which changes the snapshot, which makes `_is_dirty()` return `True`. No new code is required to trip dirty.

---

### `musicstreamer/aa_import.py` — `_resolve_pls` thin wrapper (service, request-response)

**Analog:** itself — the current `_resolve_pls` body at lines 23-46 is replaced by a thin delegation.

**Current body** (`aa_import.py` lines 23-46):
```python
def _resolve_pls(pls_url: str) -> list[str]:
    try:
        with urllib.request.urlopen(pls_url, timeout=10) as resp:
            body = resp.read().decode()
        entries = []
        for line in body.splitlines():
            m = re.match(r"^File(\d+)=(.+)$", line.strip())
            if m:
                entries.append((int(m.group(1)), m.group(2).strip()))
        if not entries:
            return [pls_url]
        entries.sort(key=lambda t: t[0])
        return [url for _, url in entries]
    except Exception:
        pass
    return [pls_url]
```

**Replacement pattern** (D-10 contract — preserve `list[str]` signature and `[pls_url]` fallback):
```python
def _resolve_pls(pls_url: str) -> list[str]:
    """Thin wrapper around playlist_parser.parse_playlist (Phase 58 D-10).

    Preserves list[str] contract and [pls_url] fallback for callers at
    aa_import.py:135 and aa_import.py:177. File-order invariant (gap-06)
    is preserved by parse_playlist's file-order traversal.
    """
    try:
        with urllib.request.urlopen(pls_url, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", errors="replace")
        from musicstreamer.playlist_parser import parse_playlist
        entries = parse_playlist(body, content_type=content_type, url_hint=pls_url)
        if entries:
            return [e["url"] for e in entries]
    except Exception:
        pass
    return [pls_url]
```

Both call sites (`aa_import.py:135` and `aa_import.py:177`) continue to work unchanged because the return type `list[str]` is preserved.

---

### `tests/test_edit_station_dialog.py` — new test block (test, request-response)

**Analog:** the existing Phase 46-02 test block at lines 329-466 in the same file — worker-mock pattern for `_LogoFetchWorker`.

**Worker mock pattern** (`test_edit_station_dialog.py` lines 329-347):
```python
def test_auto_fetch_worker_starts_on_url_change(qtbot, monkeypatch, dialog):
    from unittest.mock import MagicMock
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    fake_worker_instance = MagicMock()
    fake_worker_instance.isRunning.return_value = False
    fake_worker_cls = MagicMock(return_value=fake_worker_instance)
    monkeypatch.setattr(esd_mod, "_LogoFetchWorker", fake_worker_cls)

    dialog.url_edit.setText("https://www.youtube.com/watch?v=abc")
    dialog._on_url_timer_timeout()

    fake_worker_cls.assert_called_once()
    assert "youtube.com" in fake_worker_cls.call_args[0][0]
    fake_worker_instance.start.assert_called_once()
```

Apply the same shape to test `_PlaylistFetchWorker` is instantiated and started when `_on_add_pls` is called, monkeypatching `QInputDialog.getText` to return a URL and `_PlaylistFetchWorker` to a mock.

**`QMessageBox.warning` mock pattern** (`test_edit_station_dialog.py` lines 648-665):
```python
def test_new_mode_empty_name_blocks_save(qtbot, station, player, repo, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warning_calls: list = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda *a, **kw: warning_calls.append((a, kw)) or QMessageBox.Ok),
    )

    d = EditStationDialog(station, player, repo, is_new=True)
    qtbot.addWidget(d)
    d.name_edit.setText("")
    d._on_save()

    assert repo.update_station.call_count == 0
    assert len(warning_calls) == 1
```

Apply this pattern to test the failure branch of `_on_pls_fetched`.

**`_on_logo_fetched` direct-call pattern** (`test_edit_station_dialog.py` lines 365-372):
```python
def test_auto_fetch_completion_copies_via_assets(qtbot, tmp_path, monkeypatch, dialog, station):
    # ...
    assert hasattr(dialog, "_on_logo_fetched")
    dialog._on_logo_fetched(str(fetched))

    mock_copy.assert_called_once()
```

Apply this shape to directly call `dialog._on_pls_fetched(entries, "", token)` in tests that check Replace/Append/Cancel branching without needing a real QThread.

**Dirty-state interaction test pattern** (`test_edit_station_dialog.py` lines 754-769):
```python
def test_is_dirty_after_stream_row_added(dialog):
    initial_rows = dialog.streams_table.rowCount()
    dialog._add_stream_row()
    assert dialog.streams_table.rowCount() == initial_rows + 1
    assert dialog._is_dirty() is True
```

After calling `dialog._apply_pls_entries(entries, mode="append")`, assert `dialog._is_dirty() is True`.

---

## Shared Patterns

### Monotonic-token stale-discard
**Source:** `musicstreamer/ui_qt/edit_station_dialog.py` lines 682-692 (write) and 739-760 (check)
**Apply to:** `_on_add_pls`, `_on_pls_fetched`

```python
# Write side (_on_add_pls):
self._pls_fetch_token += 1
token = self._pls_fetch_token

# Check side (_on_pls_fetched), after unconditional cursor restore:
if token != self._pls_fetch_token:
    return  # discard stale emission
```

### Wait-cursor + button-disable lifecycle
**Source:** `musicstreamer/ui_qt/edit_station_dialog.py` lines 685-692 (set) and 749-762 (restore)
**Apply to:** `_on_add_pls` (set), `_on_pls_fetched` (restore — first two lines, before any conditional)

```python
# Set (_on_add_pls, after incrementing token):
self.add_pls_btn.setEnabled(False)
QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
self._pls_fetch_worker.start()

# Restore (_on_pls_fetched, FIRST lines, unconditionally):
QApplication.restoreOverrideCursor()
self.add_pls_btn.setEnabled(True)
```

### Worker shutdown in accept/closeEvent/reject
**Source:** `musicstreamer/ui_qt/edit_station_dialog.py` lines 831-858
**Apply to:** All three teardown methods — add `self._shutdown_pls_fetch_worker()` alongside the existing `self._shutdown_logo_fetch_worker()` call in each method.

```python
def accept(self) -> None:
    self._shutdown_logo_fetch_worker()
    self._shutdown_pls_fetch_worker()   # NEW
    super().accept()

def closeEvent(self, event):
    if self._is_new:
        self._repo.delete_station(self._station.id)
        self._is_new = False
    self._shutdown_logo_fetch_worker()
    self._shutdown_pls_fetch_worker()   # NEW
    super().closeEvent(event)

def reject(self) -> None:
    if self._is_new:
        self._repo.delete_station(self._station.id)
        self._is_new = False
    self._shutdown_logo_fetch_worker()
    self._shutdown_pls_fetch_worker()   # NEW
    super().reject()
```

### `QMessageBox.question` 3-button custom pattern
**Source:** Phase 51 `_on_sibling_link_activated` — same `addButton` + `clickedButton()` idiom

```python
msg_box = QMessageBox(self)
msg_box.setWindowTitle("...")
msg_box.setText("...")
replace_btn = msg_box.addButton("Replace", QMessageBox.DestructiveRole)
append_btn  = msg_box.addButton("Append",  QMessageBox.AcceptRole)
cancel_btn  = msg_box.addButton("Cancel",  QMessageBox.RejectRole)
msg_box.setDefaultButton(append_btn)
msg_box.exec()
clicked = msg_box.clickedButton()
if clicked is replace_btn:
    ...
elif clicked is append_btn:
    ...
# else: Cancel — no-op
```

---

## No Analog Found

All files have close analogs. No entries in this section.

---

## Metadata

**Analog search scope:** `musicstreamer/`, `tests/`
**Files scanned:** 7 source files read in full or in targeted sections
**Pattern extraction date:** 2026-05-01
