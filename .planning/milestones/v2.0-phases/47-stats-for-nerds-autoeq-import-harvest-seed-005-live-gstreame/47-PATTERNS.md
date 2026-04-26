# Phase 47: Stream bitrate quality ordering — Pattern Map

**Mapped:** 2026-04-17
**Files analyzed:** 11 (2 new + 9 modified)
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| NEW `musicstreamer/stream_ordering.py` | utility (pure) | transform | `musicstreamer/url_helpers.py` | exact (top-level pure util module) |
| NEW `tests/test_stream_ordering.py` | test (pure unit) | transform | `tests/test_aa_import.py` (`test_quality_tier_mapping`) | role-match (table-driven pure-fn tests) |
| MOD `musicstreamer/models.py` | model (dataclass) | CRUD | existing `StationStream` (add sibling field) | exact (in-file) |
| MOD `musicstreamer/repo.py` | service (data access) | CRUD | existing CREATE TABLE + ALTER patterns in same file | exact (in-file idiom repeat) |
| MOD `musicstreamer/player.py` | controller (failover) | event-driven | existing `sorted(station.streams, ...)` at line 166 | exact (single-line swap) |
| MOD `musicstreamer/aa_import.py` | service (ingest) | transform | existing `fetch_channels_multi` stream-dict build (line 149) | exact (in-file) |
| MOD `musicstreamer/ui_qt/discovery_dialog.py::_on_save_row` | controller (ingest) | request-response | `aa_import.import_stations_multi` (insert → list_streams → update_stream) | role-match (post-insert fix-up pattern) |
| MOD `musicstreamer/settings_export.py::_station_to_dict` | service (serialize) | transform | existing stream dict literal at line 111 | exact (in-file) |
| MOD `musicstreamer/settings_export.py::_insert_station`/`_replace_station` | service (persist) | CRUD | existing 7-col SQL at lines 371-386 / 426-440 | exact (in-file 7→8 col extension) |
| MOD `musicstreamer/ui_qt/edit_station_dialog.py` | component (QWidget) | request-response | existing 4-col `streams_table` at line 275 | exact (in-file column addition) |
| MOD `tests/test_aa_import.py`, `tests/test_settings_export.py`, `tests/test_edit_station_dialog.py` | test | transform | existing table-driven tests in each file | exact (in-file extension) |

---

## Pattern Assignments

### NEW `musicstreamer/stream_ordering.py` (utility, pure transform)

**Analog:** `musicstreamer/url_helpers.py` (pure top-level util module, zero UI coupling)

**Module header pattern** (url_helpers.py:1-12):
```python
"""Pure URL classification helpers for stream sources.

Extracted from musicstreamer/ui/edit_dialog.py during the Phase 36 GTK cutover
so that non-UI tests (test_aa_url_detection, test_yt_thumbnail) survive the
deletion of the ui/ tree. These helpers have zero GTK/Qt coupling — they are
pure string and regex manipulation over URL literals.
"""
from __future__ import annotations

import urllib.parse

from musicstreamer.aa_import import NETWORKS
```

**Apply for Phase 47:**
```python
"""Pure stream ordering for failover (Phase 47).

Sorts a station's streams by (codec_rank desc, bitrate_kbps desc, position asc)
per D-04/D-05. Unknown bitrates (bitrate_kbps == 0) sort LAST per D-07.
Pure functions — no DB access, no mutation (D-09).
"""
from __future__ import annotations

from typing import List

from musicstreamer.models import StationStream

# D-05: FLAC=3 > AAC=2 > MP3=1 > other=0.
_CODEC_RANK = {"FLAC": 3, "AAC": 2, "MP3": 1}


def codec_rank(codec: str) -> int:
    return _CODEC_RANK.get((codec or "").strip().upper(), 0)


def order_streams(streams: List[StationStream]) -> List[StationStream]:
    # D-07: unknowns last; partition then sort each bucket separately.
    known = [s for s in streams if s.bitrate_kbps > 0]
    unknown = [s for s in streams if s.bitrate_kbps <= 0]
    known_sorted = sorted(
        known,
        key=lambda s: (-codec_rank(s.codec), -s.bitrate_kbps, s.position),
    )
    unknown_sorted = sorted(unknown, key=lambda s: s.position)
    return known_sorted + unknown_sorted
```

**Purity guard (P-3 / G-6):** use `sorted(...)`, never `list.sort(...)`.

---

### NEW `tests/test_stream_ordering.py` (test, pure)

**Analog:** `tests/test_aa_import.py` (`test_quality_tier_mapping`, line 91 — table-driven pure-function test)

**Table-driven pattern** (test_aa_import.py:91-101):
```python
def test_quality_tier_mapping():
    """Quality hi->premium_high, med->premium, low->premium_medium in URLs."""
    channel_data = _mock_channel_json("Jazz", "jazz")

    for quality, expected_tier in [("hi", "premium_high"), ("med", "premium"), ("low", "premium_medium")]:
        with patch(...):
            result = fetch_channels("testkey123", quality)
        for item in result:
            assert expected_tier in item["url"], ...
```

**Apply for Phase 47 (skeleton):**
```python
"""Tests for musicstreamer/stream_ordering.py — Phase 47 failover ordering."""
from __future__ import annotations

import pytest

from musicstreamer.models import StationStream
from musicstreamer.stream_ordering import codec_rank, order_streams


def _s(codec: str = "", bitrate_kbps: int = 0, position: int = 1, url: str = "u") -> StationStream:
    return StationStream(id=0, station_id=0, url=url, codec=codec,
                         bitrate_kbps=bitrate_kbps, position=position)


@pytest.mark.parametrize("codec,expected", [
    ("FLAC", 3), ("flac", 3), ("  FLAC  ", 3),
    ("AAC", 2), ("MP3", 1), ("OPUS", 0), ("", 0), (None, 0),
])
def test_codec_rank(codec, expected):
    assert codec_rank(codec) == expected


def test_same_codec_bitrate_sort():
    # 320 > 128 > 64 for MP3
    result = order_streams([_s("MP3", 64, 1), _s("MP3", 320, 2), _s("MP3", 128, 3)])
    assert [s.bitrate_kbps for s in result] == [320, 128, 64]


# PB-04, PB-05, PB-06, PB-07, PB-08, PB-09, PB-11 — see RESEARCH.md table
```

---

### MOD `musicstreamer/models.py` (dataclass)

**Analog:** self — add sibling field to existing `StationStream`.

**Current state** (models.py:11-20):
```python
@dataclass
class StationStream:
    id: int
    station_id: int
    url: str
    label: str = ""
    quality: str = ""        # "hi" | "med" | "low" | custom string
    position: int = 1
    stream_type: str = ""    # "shoutcast" | "youtube" | "hls" | ""
    codec: str = ""          # "MP3" | "AAC" | "OPUS" | "FLAC" | ""
```

**Edit:** add `bitrate_kbps: int = 0` after `codec`. Matches the existing style (default-valued scalar with inline comment explaining sentinel).

---

### MOD `musicstreamer/repo.py` (service, CRUD)

**Analog:** self — three existing in-file idioms to replicate.

**Pattern 1: CREATE TABLE** (repo.py:51-61 — current state):
```python
CREATE TABLE IF NOT EXISTS station_streams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    label TEXT NOT NULL DEFAULT '',
    quality TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 1,
    stream_type TEXT NOT NULL DEFAULT '',
    codec TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
);
```
Add `bitrate_kbps INTEGER NOT NULL DEFAULT 0,` between `codec` and `FOREIGN KEY`.

**Pattern 2: additive ALTER TABLE** (repo.py:66-82 — verbatim idiom, three existing instances):
```python
try:
    con.execute("ALTER TABLE stations ADD COLUMN icy_disabled INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists
```
Copy as the 4th block, targeting `station_streams`:
```python
try:
    con.execute("ALTER TABLE station_streams ADD COLUMN bitrate_kbps INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists
```

**Pattern 3: list_streams hydration** (repo.py:169-175):
```python
def list_streams(self, station_id: int) -> List[StationStream]:
    rows = self.con.execute(
        "SELECT * FROM station_streams WHERE station_id=? ORDER BY position", (station_id,)
    ).fetchall()
    return [StationStream(id=r["id"], station_id=r["station_id"], url=r["url"],
            label=r["label"], quality=r["quality"], position=r["position"],
            stream_type=r["stream_type"], codec=r["codec"]) for r in rows]
```
Append `bitrate_kbps=r["bitrate_kbps"]` to the `StationStream(...)` constructor.

**Pattern 4: insert_stream / update_stream** (repo.py:177-191):
```python
def insert_stream(self, station_id: int, url: str, label: str = "",
                  quality: str = "", position: int = 1,
                  stream_type: str = "", codec: str = "") -> int:
    cur = self.con.execute(
        "INSERT INTO station_streams(station_id,url,label,quality,position,stream_type,codec) VALUES(?,?,?,?,?,?,?)",
        (station_id, url, label, quality, position, stream_type, codec))
    self.con.commit()
    return int(cur.lastrowid)

def update_stream(self, stream_id: int, url: str, label: str,
                  quality: str, position: int, stream_type: str, codec: str):
    self.con.execute(
        "UPDATE station_streams SET url=?,label=?,quality=?,position=?,stream_type=?,codec=? WHERE id=?",
        (url, label, quality, position, stream_type, codec, stream_id))
    self.con.commit()
```
Extend both: new trailing kwarg `bitrate_kbps: int = 0`, extra column in the SQL, extra `?` placeholder, extra tuple slot.

---

### MOD `musicstreamer/player.py:166` (controller, failover)

**Analog:** self — single-line swap inside existing `play()` method.

**Current** (player.py:165-166):
```python
# Build ordered stream queue: preferred quality first, then rest in position order
streams_by_position = sorted(station.streams, key=lambda s: s.position)
```

**Edit:** replace line 166 with:
```python
from musicstreamer.stream_ordering import order_streams
streams_by_position = order_streams(station.streams)
```
(Import at module top, not inside method.) Variable name kept for minimal diff. Preferred-quality short-circuit logic on lines 167-177 remains intact — G-7 confirms ordering contract preserved.

---

### MOD `musicstreamer/aa_import.py` (service, ingest transform)

**Analog:** self — existing `position_map` + stream-dict build in `fetch_channels_multi`.

**Current** (aa_import.py:136-154):
```python
position_map = {"hi": 1, "med": 2, "low": 3}
for ch in data:
    key = (net["slug"], ch["key"])
    ...
    channels_by_net_key[key]["streams"].append({
        "url": stream_url,
        "quality": quality,
        "position": position_map[quality],
        "codec": "AAC" if tier == "premium_high" else "MP3",
    })
```

**Edits:**
1. Add inline map alongside `position_map` (line 136):
   ```python
   bitrate_map = {"hi": 320, "med": 128, "low": 64}  # D-10
   ```
2. Add key to the stream dict (line 149-154):
   ```python
   channels_by_net_key[key]["streams"].append({
       "url": stream_url,
       "quality": quality,
       "position": position_map[quality],
       "codec": "AAC" if tier == "premium_high" else "MP3",
       "bitrate_kbps": bitrate_map[quality],
   })
   ```
3. Thread through `import_stations_multi` (line 192-202) — extend both `update_stream` and `insert_stream` calls with `bitrate_kbps=s.get("bitrate_kbps", 0)`:
   ```python
   repo.update_stream(
       streams[0].id, s["url"], s.get("label", ""),
       s["quality"], s["position"],
       "shoutcast", s.get("codec", ""),
       bitrate_kbps=s.get("bitrate_kbps", 0),
   )
   ```

---

### MOD `musicstreamer/ui_qt/discovery_dialog.py::_on_save_row` (controller, post-insert fix-up)

**Analog:** `aa_import.import_stations_multi` (aa_import.py:188-196) — the existing "call insert_station, then list_streams, then update_stream" pattern.

**Pattern from `import_stations_multi`** (aa_import.py:186-196):
```python
# insert_station already created a stream for first_url at position=1
# Update the auto-created stream with quality/codec metadata, then insert remaining
for s in ch["streams"]:
    if s["url"] == first_url:
        streams = repo.list_streams(station_id)
        if streams:
            repo.update_stream(
                streams[0].id, s["url"], s.get("label", ""),
                s["quality"], s["position"],
                "shoutcast", s.get("codec", "")
            )
```

**Current `_on_save_row`** (discovery_dialog.py:414-430):
```python
def _on_save_row(self, row_index: int) -> None:
    if row_index >= len(self._results):
        return
    result = self._results[row_index]
    stream_url = result.get("url_resolved") or result.get("url", "")
    if not stream_url:
        return
    self._repo.insert_station(
        name=result.get("name", "Unknown"),
        url=stream_url,
        provider_name="Radio-Browser",
        tags=result.get("tags", ""),
    )
    self._toast_callback(f"Saved '{result.get('name', 'station')}' to library")
    if row_index < len(self._save_buttons):
        self._save_buttons[row_index].setEnabled(False)
    self.station_saved.emit()
```

**Note:** `insert_station` returns the new `station_id` (repo.py:407 — `return station_id`); current code discards the return value. The fix-up needs it.

**Edit (D-11 + G-2 Option 1):**
```python
bitrate_val = int(result.get("bitrate", 0) or 0)  # RadioBrowser API field
station_id = self._repo.insert_station(
    name=result.get("name", "Unknown"),
    url=stream_url,
    provider_name="Radio-Browser",
    tags=result.get("tags", ""),
)
# insert_station auto-created a stream at position=1 — fix it up with bitrate.
if bitrate_val:
    streams = self._repo.list_streams(station_id)
    if streams:
        s = streams[0]
        self._repo.update_stream(
            s.id, s.url, s.label, s.quality, s.position,
            s.stream_type, s.codec, bitrate_kbps=bitrate_val,
        )
```

**Context — result dict shape** (discovery_dialog.py:349 — `bitrate` key already populated from API):
```python
bitrate_val = result.get("bitrate", 0)
```
This exact pattern is already in the UI rendering code; the save path just needs to consume the same key.

---

### MOD `musicstreamer/settings_export.py::_station_to_dict` (service, serialize)

**Analog:** self — the hand-rolled stream dict in the serializer.

**Current** (settings_export.py:101-122 — full function):
```python
def _station_to_dict(station: Station) -> dict:
    """Serialize a Station (with its streams) to the settings.json schema."""
    return {
        "name": station.name,
        "provider": station.provider_name or "",
        "tags": station.tags or "",
        "icy_disabled": station.icy_disabled,
        "is_favorite": station.is_favorite,
        "last_played_at": station.last_played_at,
        "logo_file": None,  # populated in build_zip when file exists
        "streams": [
            {
                "url": s.url,
                "label": s.label,
                "quality": s.quality,
                "position": s.position,
                "stream_type": s.stream_type,
                "codec": s.codec,
            }
            for s in station.streams
        ],
    }
```

**Edit:** add one line to the inner stream dict:
```python
"codec": s.codec,
"bitrate_kbps": s.bitrate_kbps,
```
Forgetting this is P-1 (export silently drops the field).

---

### MOD `musicstreamer/settings_export.py::_insert_station` / `_replace_station` (service, persist)

**Analog:** self — two near-identical SQL blocks, both need the same 7→8 column extension.

**Current `_insert_station` 7-column insert** (settings_export.py:371-386):
```python
for stream in data.get("streams", []):
    repo.con.execute(
        "INSERT INTO station_streams"
        "(station_id, url, label, quality, position, stream_type, codec) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            station_id,
            stream.get("url", ""),
            stream.get("label", ""),
            stream.get("quality", ""),
            stream.get("position", 1),
            stream.get("stream_type", ""),
            stream.get("codec", ""),
        ),
    )
```

**Edit — 8-column version:**
```python
for stream in data.get("streams", []):
    repo.con.execute(
        "INSERT INTO station_streams"
        "(station_id, url, label, quality, position, stream_type, codec, bitrate_kbps) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            station_id,
            stream.get("url", ""),
            stream.get("label", ""),
            stream.get("quality", ""),
            stream.get("position", 1),
            stream.get("stream_type", ""),
            stream.get("codec", ""),
            int(stream.get("bitrate_kbps", 0) or 0),  # P-2 forward-compat + defense
        ),
    )
```

**Current `_replace_station`** (settings_export.py:426-440) is byte-identical to the block above except in context. Apply exactly the same 8-column edit there too.

**Defensive coerce rationale (Threat table row 3):** pre-47 ZIPs lack the key (`.get(..., 0)` handles), and a malformed value gets neutralized by `int(... or 0)`.

---

### MOD `musicstreamer/ui_qt/edit_station_dialog.py` (component, QTableWidget extension)

**Analog:** self — existing 4-column idiom + in-tree `QStyledItemDelegate` reference.

**Delegate analog (in-tree):** `musicstreamer/ui_qt/station_star_delegate.py`. This is a painting/event delegate rather than an editor delegate, but it establishes the project convention for subclassing `QStyledItemDelegate` as a local module-level class with a brief docstring and `parent=None` init signature.

**Delegate class header pattern** (station_star_delegate.py:12-41):
```python
from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

...

class StationStarDelegate(QStyledItemDelegate):
    """Paints star icon on station rows and toggles is_favorite on click."""

    star_toggled = Signal(object)

    def __init__(self, repo, parent=None) -> None:
        super().__init__(parent)
        self._repo = repo
```

**Apply for Phase 47 (minimal editor delegate, P-5):**
```python
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QStyledItemDelegate

class _BitrateDelegate(QStyledItemDelegate):
    """Numeric-only editor for the bitrate column (D-12/D-13, P-5)."""

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setValidator(QIntValidator(0, 9999, parent))
        return editor
```
Keep the class local to `edit_station_dialog.py` (prefix with `_` to signal module-private). Register once in `_build_ui`:
```python
self.streams_table.setItemDelegateForColumn(_COL_BITRATE, _BitrateDelegate(self))
```

**Column constants** (edit_station_dialog.py:146-150 — current):
```python
# Stream table columns
_COL_URL = 0
_COL_QUALITY = 1
_COL_CODEC = 2
_COL_POSITION = 3
```
Edit:
```python
_COL_URL = 0
_COL_QUALITY = 1
_COL_CODEC = 2
_COL_BITRATE = 3
_COL_POSITION = 4
```

**Table constructor** (edit_station_dialog.py:275-286 — current):
```python
self.streams_table = QTableWidget(0, 4)
self.streams_table.setHorizontalHeaderLabels(["URL", "Quality", "Codec", "Position"])
self.streams_table.setAlternatingRowColors(True)
self.streams_table.setSelectionBehavior(QTableWidget.SelectRows)
hdr = self.streams_table.horizontalHeader()
hdr.setSectionResizeMode(_COL_URL, QHeaderView.Stretch)
hdr.setSectionResizeMode(_COL_QUALITY, QHeaderView.Fixed)
hdr.setSectionResizeMode(_COL_CODEC, QHeaderView.Fixed)
hdr.setSectionResizeMode(_COL_POSITION, QHeaderView.Fixed)
self.streams_table.setColumnWidth(_COL_QUALITY, 80)
self.streams_table.setColumnWidth(_COL_CODEC, 80)
self.streams_table.setColumnWidth(_COL_POSITION, 60)
```
Edit — bump to 5 columns, insert "Bitrate" label, add resize/width/delegate for new column:
```python
self.streams_table = QTableWidget(0, 5)
self.streams_table.setHorizontalHeaderLabels(
    ["URL", "Quality", "Codec", "Bitrate", "Position"]
)
...
hdr.setSectionResizeMode(_COL_BITRATE, QHeaderView.Fixed)
self.streams_table.setColumnWidth(_COL_BITRATE, 70)
self.streams_table.setItemDelegateForColumn(_COL_BITRATE, _BitrateDelegate(self))
```

**Row populate** (edit_station_dialog.py:399-416 — current `_add_stream_row`):
```python
def _add_stream_row(self, url: str = "", quality: str = "",
                    codec: str = "", position: int = 1,
                    stream_id: Optional[int] = None) -> int:
    ...
    self.streams_table.setItem(row, _COL_URL, url_item)
    self.streams_table.setItem(row, _COL_QUALITY, QTableWidgetItem(quality))
    self.streams_table.setItem(row, _COL_CODEC, QTableWidgetItem(codec))
    self.streams_table.setItem(row, _COL_POSITION, QTableWidgetItem(str(position)))
    return row
```
Edit — add `bitrate_kbps: int = 0` param + setItem line (empty string when 0, per D-12/G-5):
```python
def _add_stream_row(self, url: str = "", quality: str = "",
                    codec: str = "", bitrate_kbps: int = 0, position: int = 1,
                    stream_id: Optional[int] = None) -> int:
    ...
    self.streams_table.setItem(row, _COL_CODEC, QTableWidgetItem(codec))
    self.streams_table.setItem(
        row, _COL_BITRATE,
        QTableWidgetItem(str(bitrate_kbps) if bitrate_kbps else ""),
    )
    self.streams_table.setItem(row, _COL_POSITION, QTableWidgetItem(str(position)))
    return row
```

**Populate caller** (edit_station_dialog.py:354-355):
```python
for s in streams:
    self._add_stream_row(s.url, s.quality, s.codec, s.position, stream_id=s.id)
```
Edit — thread `s.bitrate_kbps`:
```python
self._add_stream_row(s.url, s.quality, s.codec, s.bitrate_kbps, s.position, stream_id=s.id)
```

**Save loop — existing coercion analog** (edit_station_dialog.py:667-693 — Position column handling at lines 672, 677-680 is the template for Bitrate, P-4):
```python
pos_item = table.item(row, _COL_POSITION)
...
try:
    position = int(pos_item.text()) if pos_item else row + 1
except ValueError:
    position = row + 1

stream_id: Optional[int] = url_item.data(Qt.UserRole) if url_item else None

if stream_id is not None:
    repo.update_stream(stream_id, url, "", quality, position, "", codec)
    ordered_ids.append(stream_id)
else:
    new_id = repo.insert_stream(
        station.id, url, label="", quality=quality,
        position=position, stream_type="", codec=codec,
    )
```
Edit — read bitrate cell (D-14 `int(text or "0")`), pass to repo calls:
```python
bitrate_item = table.item(row, _COL_BITRATE)
bitrate_text = bitrate_item.text() if bitrate_item else ""
try:
    bitrate_kbps = int(bitrate_text or "0")
except ValueError:
    bitrate_kbps = 0
...
if stream_id is not None:
    repo.update_stream(stream_id, url, "", quality, position, "", codec,
                       bitrate_kbps=bitrate_kbps)
    ordered_ids.append(stream_id)
else:
    new_id = repo.insert_stream(
        station.id, url, label="", quality=quality,
        position=position, stream_type="", codec=codec,
        bitrate_kbps=bitrate_kbps,
    )
```

**`_swap_rows`** (edit_station_dialog.py:442-448): already iterates `range(table.columnCount())` — no edit needed; handles 5 columns unchanged.

---

### MOD tests (extend existing suites)

**`tests/test_aa_import.py`** — analog `test_quality_tier_mapping` (line 91) + `test_import_multi_creates_streams` (line 400).

Add (PB-12):
```python
def test_fetch_channels_multi_bitrate_kbps():
    """hi=320, med=128, low=64 populated per-stream."""
    channel_data = _mock_channel_json("Jazz", "jazz")
    with patch(...):
        result = fetch_channels_multi("testkey123")
    for ch in result:
        bitrates = {s["quality"]: s["bitrate_kbps"] for s in ch["streams"]}
        assert bitrates == {"hi": 320, "med": 128, "low": 64}
```
Existing `test_import_multi_creates_streams` MagicMock-based assertion should be extended to verify `bitrate_kbps=` kwarg on `insert_stream`/`update_stream` calls (via `mock_repo.insert_stream.call_args_list`).

**`tests/test_settings_export.py`** — analog the `seeded_repo` fixture (line 37) + its existing 7-col `INSERT INTO station_streams` statements (lines 54, 58, 74).

Add (PB-14, PB-15):
- PB-14 round-trip: extend `seeded_repo` to insert a row with `bitrate_kbps=320`, build → preview → commit, assert it survives.
- PB-15 forward-compat: construct a JSON payload explicitly omitting `bitrate_kbps`, run `commit_import`, assert `list_streams(station_id)[0].bitrate_kbps == 0`.

Critically: also update the fixture's raw SQL INSERT (line 54-56) to use the new 8-col form once the schema edit lands, OR leave 7-col (it still works — default 0 fills the new column). Safer to upgrade to 8-col explicit for test clarity.

**`tests/test_edit_station_dialog.py`** — analog the `repo` fixture (line 33-46) with its MagicMock `list_streams` return.

Add (PB-16, PB-17):
```python
def test_bitrate_column_populated(qtbot, station, player, repo):
    repo.list_streams.return_value = [
        StationStream(id=10, station_id=1, url="http://s1.mp3",
                      quality="hi", bitrate_kbps=320, codec="AAC"),
    ]
    d = EditStationDialog(station, player, repo)
    qtbot.addWidget(d)
    # _COL_BITRATE == 3
    assert d.streams_table.item(0, 3).text() == "320"


def test_empty_bitrate_saves_as_zero(qtbot, station, player, repo):
    ...
    d.streams_table.item(0, 3).setText("")
    d._on_save()
    repo.update_stream.assert_called_with(
        ..., bitrate_kbps=0,
    )
```

---

## Shared Patterns

### Defensive integer coercion (import boundary)

**Sources:**
- Existing position-column analog in `edit_station_dialog.py:677-680` (try/except ValueError)
- D-14 mandate: `int(text or "0")`

**Apply to:** every seam where a string becomes `bitrate_kbps`:
- `edit_station_dialog.py::_on_save` save loop (read cell)
- `settings_export.py::_insert_station` and `::_replace_station` (import from JSON)
- `discovery_dialog.py::_on_save_row` (read from API result dict)

**Canonical form:**
```python
bitrate_kbps = int((value or 0) or 0)   # for pre-typed ints
# or
try:
    bitrate_kbps = int(text or "0")
except ValueError:
    bitrate_kbps = 0                    # for UI cells
```

### Post-insert fix-up of auto-created stream

**Source:** `aa_import.py:186-196` (`import_stations_multi`).
**Apply to:** `discovery_dialog.py::_on_save_row` (G-2 Option 1). Avoid widening `insert_station`'s public signature.

```python
station_id = repo.insert_station(name=..., url=url, provider_name=..., tags=...)
streams = repo.list_streams(station_id)
if streams:
    s = streams[0]
    repo.update_stream(s.id, s.url, s.label, s.quality, s.position,
                       s.stream_type, s.codec, bitrate_kbps=bitrate_val)
```

### Additive ALTER TABLE migration

**Source:** three in-file instances in `repo.py:66-82`.
**Apply to:** new `bitrate_kbps` column on `station_streams`. Idempotent via `try/except sqlite3.OperationalError: pass`. No PRAGMA `user_version` bump (D-02).

### Pure-function purity guard

**Source:** none existing; new invariant for `order_streams` (D-09, G-6, P-3).
**Apply to:** `stream_ordering.py`. Always `sorted(list, key=...)`, never `list.sort(key=...)`. Add a unit test asserting input identity is preserved (`original = [...]; copy = list(original); order_streams(original); assert original == copy`).

---

## No Analog Found

None — every file has a clear in-tree or in-file analog. The only "new pattern" is the minimal `QStyledItemDelegate` editor subclass, and `station_star_delegate.py` provides the project-local convention for subclassing and naming. The overriding `createEditor` method is new but small and unambiguous per Qt docs.

---

## Metadata

**Analog search scope:**
- `musicstreamer/` (all top-level modules)
- `musicstreamer/ui_qt/` (all Qt widgets + delegates)
- `tests/` (test conventions for pure + Qt-widget tests)

**Files scanned (full reads):**
- `musicstreamer/models.py`, `musicstreamer/repo.py`, `musicstreamer/aa_import.py`, `musicstreamer/settings_export.py`, `musicstreamer/url_helpers.py`, `musicstreamer/radio_browser.py`, `musicstreamer/ui_qt/station_star_delegate.py`
- Partial reads: `musicstreamer/player.py` (150-210), `musicstreamer/ui_qt/edit_station_dialog.py` (1-100, 140-320, 340-450, 650-717), `musicstreamer/ui_qt/discovery_dialog.py` (1-60, 320-490)
- Test style: `tests/test_aa_import.py` (full), `tests/test_settings_export.py` (1-120), `tests/test_edit_station_dialog.py` (1-80)

**Grep verifications:**
- `QStyledItemDelegate|setItemDelegateForColumn|QIntValidator` → one in-tree analog (`station_star_delegate.py`) — confirms project convention.
- `bitrate` (case-insensitive) in `musicstreamer/` → UI-render sites only; no persistence today (confirms G-2).

**Pattern extraction date:** 2026-04-17
