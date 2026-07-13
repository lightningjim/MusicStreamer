# Phase 97: Resolve Station URL Duplication - Pattern Map

**Mapped:** 2026-06-23
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/models.py` | model | transform | same file, `preferred_stream_id` field (line 41) | exact |
| `musicstreamer/repo.py` | service | CRUD | same file, `set_preferred_stream` (line 814), Phase-96 setters (lines 1023/1037) | exact |
| `musicstreamer/ui_qt/edit_station_dialog.py` | component | request-response | same file, existing `_add_stream_row` / column-constant block (lines 278-283, 1102-1137) | exact |
| `musicstreamer/url_helpers.py` | utility | transform | same file, `find_aa_siblings` / `suggest_similar` (lines 216, 358) | exact |
| `musicstreamer/ui_qt/station_filter_proxy.py` | middleware | request-response | same file, `filterAcceptsRow` (line 179) | exact |
| `musicstreamer/ui_qt/now_playing_panel.py` | component | event-driven | same file, `_refresh_siblings` (line 2433) | exact |
| `musicstreamer/aa_live.py` | service | request-response | same file, `get_di_channel_key` (line 161) | exact |
| `tests/test_repo.py` | test | CRUD | same file, `test_preferred_stream_id_migration_idempotent` block (lines 876-923) | exact |
| `tests/test_edit_station_dialog.py` | test | request-response | same file, `test_is_dirty_after_url_edit` / `test_stream_table_populated_and_add` (lines 134-183, 885-926) | exact |

---

## Pattern Assignments

### `musicstreamer/models.py` (model, transform)

**Analog:** same file — `preferred_stream_id` field at line 41 and surrounding Phase-N field pattern

**Existing field that canonical_stream_id mirrors** (lines 41-47):
```python
# musicstreamer/models.py:41-47
preferred_stream_id: Optional[int] = None  # Phase 82 D-01: per-station sticky preferred stream
prerolls: List[str] = field(default_factory=list)              # Phase 83 D-01/D-03
prerolls_fetched_at: Optional[int] = None                      # Phase 83 D-04
channel_avatar_path: Optional[str] = None                      # Phase 89 D-13 — deprecated Phase 89.1 (use provider_avatar_path)
provider_avatar_path: Optional[str] = None                     # Phase 89.1 D-11
live_url_syncs_from_channel: bool = False                      # Phase 96 D-01
live_url_title_anchor: Optional[str] = None                    # Phase 96 D-03
```

**What to add** — one new line immediately after `preferred_stream_id` (line 41):
```python
preferred_stream_id: Optional[int] = None  # Phase 82 D-01: per-station sticky preferred stream
canonical_stream_id: Optional[int] = None  # Phase 97 D-04: metadata anchor stream (separate from playback preferred)
```

**Optional canonical_url property** — add at bottom of `Station` dataclass (after all fields); `Station` is NOT `frozen=True` (verified line 28: `@dataclass` with no flags), so `@property` is valid:
```python
@property
def canonical_url(self) -> str:
    """Phase 97 D-07: URL of the canonical (metadata anchor) stream.

    Resolution order:
      1. Stream matching canonical_stream_id (if set and present)
      2. Position-1 stream (fallback: unset or stale FK after delete)
      3. First stream by list order (defensive: position not yet normalized)
      4. "" (no streams at all)
    """
    if not self.streams:
        return ""
    if self.canonical_stream_id is not None:
        for s in self.streams:
            if s.id == self.canonical_stream_id:
                return s.url
    by_pos = sorted(self.streams, key=lambda s: (s.position, s.id))
    return by_pos[0].url if by_pos else ""
```

---

### `musicstreamer/repo.py` (service, CRUD)

**Analog:** same file — three distinct reference points:

#### 1. Migration ALTER block (the exact pattern to copy)

**Analog: `preferred_stream_id` ALTER** (lines 282-295):
```python
# musicstreamer/repo.py:282-295
# Phase 82 D-01/D-08 — per-station sticky preferred stream FK.
# MUST land AFTER the legacy URL-column rebuild block (Pitfall 2): the
# rebuild's CREATE TABLE stations_new / INSERT SELECT does not carry
# dynamically-added columns, so placing the ALTER here ensures the column
# lands on the rebuilt (or fresh) table. Nullable INTEGER with no DEFAULT
# (D-01 — NULL means no preference set; no backfill needed). Idempotent
# via the same try/except sqlite3.OperationalError idiom as above.
try:
    con.execute(
        "ALTER TABLE stations ADD COLUMN preferred_stream_id INTEGER REFERENCES station_streams(id) ON DELETE SET NULL"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent
```

**What the Phase-96 block looks like (the last block before where Phase-97 lands)** (lines 336-366):
```python
# musicstreamer/repo.py:336-366
# Phase 96 D-01 — per-station opt-in live URL re-sync flag; INTEGER NOT NULL DEFAULT 0.
try:
    con.execute(
        "ALTER TABLE stations ADD COLUMN live_url_syncs_from_channel INTEGER NOT NULL DEFAULT 0"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent

# Phase 96 D-03 — per-station title anchor from live stream; nullable TEXT no DEFAULT.
try:
    con.execute("ALTER TABLE stations ADD COLUMN live_url_title_anchor TEXT")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent

# Phase 96 D-04 — per-provider channel scan URL; nullable TEXT no DEFAULT.
try:
    con.execute("ALTER TABLE providers ADD COLUMN channel_scan_url TEXT")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent
```

**The legacy URL rebuild block that canonical ALTER MUST follow** (lines 208-265):
```python
# musicstreamer/repo.py:208-265 (Pitfall 2 anchor — canonical ALTER goes AFTER this)
# Migration: if stations table still has url column, migrate data and drop column
try:
    con.execute("SELECT url FROM stations LIMIT 1")
    # url column exists — migrate to station_streams then recreate table without url
    ...
    con.executescript("""
        PRAGMA foreign_keys = OFF;
        CREATE TABLE stations_new (...);
        INSERT INTO stations_new (...) SELECT ... FROM stations;
        DROP TABLE stations;
        ALTER TABLE stations_new RENAME TO stations;
        ...
        PRAGMA foreign_keys = ON;
    """)
    con.commit()
except sqlite3.OperationalError:
    pass  # url column already gone — migration already ran
```

**New ALTER block for Phase 97** (place AFTER the Phase-96 blocks, around line 367):
```python
# Phase 97 D-04 — per-station canonical (metadata anchor) stream FK.
# MUST land AFTER the legacy URL-column rebuild block (Pitfall 2): the
# rebuild's CREATE TABLE stations_new / INSERT SELECT does not carry
# dynamically-added columns, so placing the ALTER here ensures the column
# lands on the rebuilt (or fresh) table. ON DELETE SET NULL: if the canonical
# stream is deleted, FK goes NULL and callers fall through to position-1
# fallback. Idempotent via the same try/except sqlite3.OperationalError idiom.
try:
    con.execute(
        "ALTER TABLE stations ADD COLUMN canonical_stream_id INTEGER "
        "REFERENCES station_streams(id) ON DELETE SET NULL"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent

# One-time backfill: set canonical_stream_id to the position-1 stream for all
# stations that have at least one stream and no canonical set yet.
# WHERE canonical_stream_id IS NULL makes this idempotent — second db_init no-op.
con.execute(
    """
    UPDATE stations
    SET canonical_stream_id = (
        SELECT id FROM station_streams
        WHERE station_id = stations.id
        ORDER BY position ASC, id ASC
        LIMIT 1
    )
    WHERE canonical_stream_id IS NULL
      AND EXISTS (SELECT 1 FROM station_streams WHERE station_id = stations.id)
    """
)
con.commit()
```

#### 2. Dedicated single-column setter (NEVER overload update_station)

**Analog: `set_preferred_stream`** (lines 814-820):
```python
# musicstreamer/repo.py:814-820
def set_preferred_stream(self, station_id: int, stream_id: Optional[int]) -> None:
    """Phase 82 D-02: persist the user's stream pick. None clears the pick."""
    self.con.execute(
        "UPDATE stations SET preferred_stream_id = ? WHERE id = ?",
        (stream_id, station_id),
    )
    self.con.commit()
```

**Analog: Phase-96 single-column setters — the "NEVER update_station" pattern** (lines 1023-1052):
```python
# musicstreamer/repo.py:1023-1035
def set_live_url_syncs_from_channel(self, station_id: int, value: bool) -> None:
    """Phase 96 D-01: set per-station live URL re-sync flag.

    Not routed through update_station — that method does not include this
    column (Pitfall 1: adding new columns to update_station risks silent-reset
    on saves that omit the kwarg). Dedicated single-column UPDATE only.
    Stores as INTEGER (0/1); callers receive bool via Station dataclass.
    """
    self.con.execute(
        "UPDATE stations SET live_url_syncs_from_channel = ? WHERE id = ?",
        (int(value), station_id),
    )
    self.con.commit()

# musicstreamer/repo.py:1037-1052
def set_live_url_title_anchor(self, station_id: int, title: Optional[str]) -> None:
    """Phase 96 D-03: write/clear the live URL title anchor.

    Not routed through update_station for the same Pitfall 1 reason as
    set_live_url_syncs_from_channel. NULL clears the anchor.
    """
    if title is not None:
        title = title[:500]
    self.con.execute(
        "UPDATE stations SET live_url_title_anchor = ? WHERE id = ?",
        (title, station_id),
    )
    self.con.commit()
```

**New setter for Phase 97** (place near `set_preferred_stream`, after line 820):
```python
def set_canonical_stream(self, station_id: int, stream_id: Optional[int]) -> None:
    """Phase 97 D-04: persist the canonical (metadata anchor) stream.

    Not routed through update_station — that method does not include this
    column (Pitfall 1: adding new columns to update_station risks silent-reset
    on saves that omit the kwarg). Dedicated single-column UPDATE only.
    None clears the marker (e.g. all streams deleted — fallback to position 1).
    """
    self.con.execute(
        "UPDATE stations SET canonical_stream_id = ? WHERE id = ?",
        (stream_id, station_id),
    )
    self.con.commit()
```

#### 3. Station-builder kwarg threading (all list_*/get_station methods)

**Analog: how `preferred_stream_id` is threaded into all Station constructors** (lines 702, 745, 858):
```python
# musicstreamer/repo.py:690-710  (list_stations Station-builder)
Station(
    id=r["id"],
    name=r["name"],
    ...
    preferred_stream_id=r["preferred_stream_id"],
    streams=self.list_streams(r["id"]),
    ...
    live_url_syncs_from_channel=bool(r["live_url_syncs_from_channel"]),  # Phase 96 D-01
    live_url_title_anchor=r["live_url_title_anchor"],      # Phase 96 D-03
)

# musicstreamer/repo.py:733-753  (get_station)
Station(
    id=r["id"],
    ...
    preferred_stream_id=r["preferred_stream_id"],
    ...
    live_url_syncs_from_channel=bool(r["live_url_syncs_from_channel"]),
    live_url_title_anchor=r["live_url_title_anchor"],
)
```

Every `Station(...)` constructor call in `list_stations`, `get_station`, `list_recently_played`, `list_favorite_stations`, `list_flagged_stations_for_provider` must add `canonical_stream_id=r["canonical_stream_id"]` immediately after `preferred_stream_id=r["preferred_stream_id"]`.

---

### `musicstreamer/ui_qt/edit_station_dialog.py` (component, request-response)

**Analog:** same file — column constants and `_add_stream_row` are the direct pattern.

#### 1. Column constant block (lines 278-283)

```python
# musicstreamer/ui_qt/edit_station_dialog.py:278-283
# Stream table columns
_COL_URL = 0
_COL_QUALITY = 1
_COL_CODEC = 2
_COL_BITRATE = 3
_COL_POSITION = 4
_COL_AUDIO_QUALITY = 5  # Phase 70 — read-only auto-detected tier (DS-03)
```

**Phase 97 change:** Add `_COL_CANONICAL`. RESEARCH recommends trailing position to minimize test breakage:
```python
# Phase 97 D-04: add as trailing column to avoid shifting all existing _COL_* refs
_COL_URL = 0
_COL_QUALITY = 1
_COL_CODEC = 2
_COL_BITRATE = 3
_COL_POSITION = 4
_COL_AUDIO_QUALITY = 5
_COL_CANONICAL = 6  # Phase 97 D-04: canonical (metadata anchor) marker; QToolButton star
```

#### 2. streams_table initialization (lines 544-574)

```python
# musicstreamer/ui_qt/edit_station_dialog.py:544-574
self.streams_table = QTableWidget(0, 6)
self.streams_table.setHorizontalHeaderLabels(
    ["URL", "Quality", "Codec", "Bitrate (kbps)", "Position", "Audio quality"]
)
self.streams_table.setAlternatingRowColors(True)
self.streams_table.setSelectionBehavior(QTableWidget.SelectRows)
hdr = self.streams_table.horizontalHeader()
hdr.setSectionResizeMode(_COL_URL, QHeaderView.Stretch)
hdr.setSectionResizeMode(_COL_QUALITY, QHeaderView.Fixed)
...
self.streams_table.setItemDelegateForColumn(_COL_BITRATE, _BitrateDelegate(self))
```

**Phase 97 adds:** Change column count to 7, add header label, add resize mode for `_COL_CANONICAL`, connect `cellChanged`:
```python
self.streams_table = QTableWidget(0, 7)  # +1 for _COL_CANONICAL
self.streams_table.setHorizontalHeaderLabels(
    ["URL", "Quality", "Codec", "Bitrate (kbps)", "Position", "Audio quality", "Primary"]
)
...
hdr.setSectionResizeMode(_COL_CANONICAL, QHeaderView.Fixed)
self.streams_table.setColumnWidth(_COL_CANONICAL, 50)
self.streams_table.horizontalHeaderItem(_COL_CANONICAL).setToolTip(
    "Mark as canonical (metadata anchor) stream. Stays pinned through reordering."
)
self.streams_table.cellChanged.connect(self._on_canonical_cell_changed)
```

Instance variable `self._canonical_row: int = -1` (updated in `_populate` and on marker click; pinned through Move Up/Down).

#### 3. `_add_stream_row` — the exact method to extend (lines 1102-1137)

```python
# musicstreamer/ui_qt/edit_station_dialog.py:1102-1137
def _add_stream_row(self, url: str = "", quality: str = "",
                    codec: str = "", bitrate_kbps: int = 0,
                    position: int = 1,
                    stream_id: Optional[int] = None,
                    sample_rate_hz: int = 0,
                    bit_depth: int = 0) -> int:
    """Insert a new row in the stream table.

    stream_id stored in URL item's Qt.UserRole — survives row swaps.
    bitrate_kbps=0 renders as empty string (D-12/G-5).
    sample_rate_hz + bit_depth feed Phase 70 _COL_AUDIO_QUALITY (DS-03).
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

    # Phase 70 / DS-03: read-only auto-detected audio tier cell.
    tier = classify_tier(codec, sample_rate_hz, bit_depth, bitrate_kbps or 0)
    audio_quality_item = QTableWidgetItem(TIER_LABEL_PROSE[tier])
    audio_quality_item.setFlags(audio_quality_item.flags() & ~Qt.ItemIsEditable)
    self.streams_table.setItem(row, _COL_AUDIO_QUALITY, audio_quality_item)

    return row
```

**Phase 97 adds canonical marker at end of `_add_stream_row`:**
```python
    # Phase 97 D-04: canonical marker QToolButton — checkable, star icon.
    # Manual single-selection (not QButtonGroup) avoids ID-tracking issues on remove.
    canonical_btn = QToolButton()
    canonical_btn.setText("★")
    canonical_btn.setCheckable(True)
    canonical_btn.setToolTip("Set as canonical (metadata anchor) stream")
    canonical_btn.setAutoRaise(True)
    # Check this button if it is the current canonical row
    if row == self._canonical_row:
        canonical_btn.setChecked(True)
    canonical_btn.clicked.connect(lambda checked, r=row: self._on_canonical_btn_clicked(r))
    self.streams_table.setCellWidget(row, _COL_CANONICAL, canonical_btn)

    return row
```

#### 4. `_on_move_up` / `_on_move_down` — canonical row tracking on reorder (lines 1149-1169)

```python
# musicstreamer/ui_qt/edit_station_dialog.py:1149-1161
def _on_move_up(self) -> None:
    row = self.streams_table.currentRow()
    if row <= 0:
        return
    self._swap_rows(row - 1, row)
    self.streams_table.selectRow(row - 1)

def _on_move_down(self) -> None:
    row = self.streams_table.currentRow()
    if row < 0 or row >= self.streams_table.rowCount() - 1:
        return
    self._swap_rows(row, row + 1)
    self.streams_table.selectRow(row + 1)

def _swap_rows(self, r1: int, r2: int) -> None:
    table = self.streams_table
    for col in range(table.columnCount()):
        item1 = table.takeItem(r1, col) or QTableWidgetItem("")
        item2 = table.takeItem(r2, col) or QTableWidgetItem("")
        table.setItem(r1, col, item2)
        table.setItem(r2, col, item1)
```

**Phase 97 adds:** `_swap_rows` must also swap `setCellWidget` canonical buttons, and `_on_move_up`/`_on_move_down` must update `_canonical_row`:
```python
# After self._swap_rows(row - 1, row) in _on_move_up:
if self._canonical_row == row:
    self._canonical_row = row - 1
elif self._canonical_row == row - 1:
    self._canonical_row = row
self.streams_table.selectRow(row - 1)
```

`_swap_rows` must also swap the `setCellWidget` buttons for `_COL_CANONICAL` (since `takeItem`/`setItem` only works for `QTableWidgetItem`, not cell widgets — use `cellWidget`/`setCellWidget` with a separate swap block).

#### 5. `url_edit` definition to remove (lines 431-444)

```python
# musicstreamer/ui_qt/edit_station_dialog.py:431-444  — REMOVE THIS BLOCK
self.url_edit = QLineEdit()
self._url_timer = QTimer()
self._url_timer.setSingleShot(True)
self._url_timer.setInterval(500)
self.url_edit.textChanged.connect(self._on_url_text_changed)
self._url_timer.timeout.connect(self._on_url_timer_timeout)
...
form.addRow("URL:", self.url_edit)
```

Keep `self._url_timer` (rewire its start to `_on_canonical_cell_changed`). Remove `self.url_edit` and the `form.addRow("URL:", ...)` line.

#### 6. `_populate` seeding from `streams[0]` to remove (line 652)

```python
# musicstreamer/ui_qt/edit_station_dialog.py:650-652  — REMOVE lines 651-652
streams = self._repo.list_streams(station.id)
if streams:
    self.url_edit.setText(streams[0].url)  # REMOVE THIS LINE
```

**Phase 97 adds** in `_populate` after the streams-table loop: set `_canonical_row` from `station.canonical_stream_id`:
```python
# Phase 97 D-04: initialize canonical row from persisted canonical_stream_id.
# If no canonical_stream_id, default to row 0 (first stream).
self._canonical_row = 0  # default
canonical_id = getattr(station, "canonical_stream_id", None)
if canonical_id is not None:
    for r in range(self.streams_table.rowCount()):
        item = self.streams_table.item(r, _COL_URL)
        if item and item.data(Qt.UserRole) == canonical_id:
            self._canonical_row = r
            break
# D-03: if no streams at all, auto-create one blank row
if self.streams_table.rowCount() == 0:
    self._add_stream_row()
    self._canonical_row = 0
```

#### 7. `_snapshot_form_state` — replace url key (line 754)

```python
# musicstreamer/ui_qt/edit_station_dialog.py:752-762  — CURRENT (to update)
return {
    "name": self.name_edit.text(),
    "url": self.url_edit.text(),   # <-- REPLACE
    "provider": self.provider_combo.currentText(),
    ...
}

# Phase 97 replacement:
return {
    "name": self.name_edit.text(),
    "canonical_url": self._get_canonical_url_live(),   # Phase 97 D-04 / Pitfall 7
    "provider": self.provider_combo.currentText(),
    ...
}
```

#### 8. `_on_save` canonical persist (lines 1876-1878 area)

```python
# musicstreamer/ui_qt/edit_station_dialog.py:1872-1878  — existing save tail
repo.prune_streams(station.id, ordered_ids)
if ordered_ids:
    repo.reorder_streams(station.id, ordered_ids)

# Phase 97 D-04: persist canonical marker (add AFTER reorder_streams)
_can_item = table.item(self._canonical_row, _COL_URL) if self._canonical_row >= 0 else None
_can_stream_id: Optional[int] = _can_item.data(Qt.UserRole) if _can_item else None
# If canonical stream was deleted (not in ordered_ids), fall back to first
if _can_stream_id not in ordered_ids:
    _can_stream_id = ordered_ids[0] if ordered_ids else None
repo.set_canonical_stream(station.id, _can_stream_id)

# Phase 96 D-01/D-03/D-04 setters follow (unchanged)
flag = self._live_resync_checkbox.isChecked()
repo.set_live_url_syncs_from_channel(station.id, flag)
...
```

---

### `musicstreamer/url_helpers.py` (utility, transform)

**Analog:** same file — the two `streams[0].url` call sites being replaced.

**Existing `find_aa_siblings` call site** (lines 213-216):
```python
# musicstreamer/url_helpers.py:213-216
if not st.streams:
    continue
cand_url = st.streams[0].url   # <-- REPLACE with canonical_url(st)
```

**Existing `suggest_similar` call site** (lines 354-358):
```python
# musicstreamer/url_helpers.py:354-358
if current_station.streams:
    aa = find_aa_siblings(
        stations,
        current_station_id=current_station.id,
        current_first_url=current_station.streams[0].url,   # <-- REPLACE
    )
```

**Phase 97 replacement pattern:**
```python
# Replace both with: station.canonical_url  (property on Station)
# or: from musicstreamer.models import canonical_url; canonical_url(st)
# Whichever form the planner chooses for the canonical_url accessor.
cand_url = st.canonical_url          # find_aa_siblings line 216
current_first_url=current_station.canonical_url  # suggest_similar line 358
```

---

### `musicstreamer/ui_qt/station_filter_proxy.py` (middleware, request-response)

**Analog:** same file — `filterAcceptsRow` streams[0].url read (line 179).

**Existing pattern** (lines 177-182):
```python
# musicstreamer/ui_qt/station_filter_proxy.py:177-182
streams = getattr(station, "streams", None) or []
if streams:
    url = streams[0].url    # <-- REPLACE
    if _is_aa_url(url):
        slug = _aa_slug_from_url(url)
        ch_key = _aa_channel_key_from_url(url, slug=slug)
```

**Phase 97 replacement:**
```python
url = station.canonical_url   # Phase 97 D-07
if url and _is_aa_url(url):
    ...
```

---

### `musicstreamer/ui_qt/now_playing_panel.py` (component, event-driven)

**Analog:** same file — `_refresh_siblings` streams[0].url read (line 2433).

**Existing pattern** (lines 2429-2433):
```python
# musicstreamer/ui_qt/now_playing_panel.py:2429-2433
if self._station is None or not self._station.streams:
    self._sibling_label.setVisible(False)
    self._sibling_label.setText("")
    return
current_url = self._station.streams[0].url   # <-- REPLACE
```

**Phase 97 replacement:**
```python
if self._station is None:
    self._sibling_label.setVisible(False)
    self._sibling_label.setText("")
    return
current_url = self._station.canonical_url    # Phase 97 D-07
if not current_url:
    self._sibling_label.setVisible(False)
    return
```

---

### `musicstreamer/aa_live.py` (service, request-response)

**Analog:** same file — `get_di_channel_key` streams[0].url read (line 161).

**Existing pattern** (lines 158-167):
```python
# musicstreamer/aa_live.py:158-167
streams = getattr(station, "streams", None) or []
if not streams:
    return None
url = streams[0].url   # <-- REPLACE
if not _is_aa_url(url):
    return None
slug = _aa_slug_from_url(url)
if slug != "di":
    return None
return _aa_channel_key_from_url(url, slug="di")
```

**Phase 97 replacement:**
```python
url = station.canonical_url   # Phase 97 D-07
if not url or not _is_aa_url(url):
    return None
...
```

---

### `tests/test_repo.py` (test, CRUD)

**Analog:** same file — the `preferred_stream_id` test block at lines 873-971 is the exact template for all new `canonical_stream_id` tests.

**Migration idempotence test to mirror** (lines 876-897):
```python
# tests/test_repo.py:876-897
def test_preferred_stream_id_migration_idempotent(repo):
    """D-08: db_init is idempotent across multiple calls; column has expected schema.

    PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk).
    preferred_stream_id must be INTEGER, nullable (notnull=0), no default (None).
    """
    # Second and third db_init calls must not raise.
    db_init(repo.con)
    db_init(repo.con)

    cols = repo.con.execute("PRAGMA table_info('stations')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert "preferred_stream_id" in by_name, (
        f"preferred_stream_id column missing; got {sorted(by_name)}"
    )
    col = by_name["preferred_stream_id"]
    # type is index 2; notnull is index 3; dflt_value is index 4
    assert col[2] == "INTEGER", f"column type must be INTEGER; got {col[2]!r}"
    assert col[3] == 0, "preferred_stream_id must be nullable (notnull=0)"
    assert col[4] is None, (
        f"preferred_stream_id must have no DEFAULT; got {col[4]!r}"
    )
```

**Default-None test to mirror** (lines 900-903):
```python
# tests/test_repo.py:900-903
def test_preferred_stream_id_default_none_on_fresh_station(repo):
    """D-01: a freshly created station has preferred_stream_id == None."""
    sid = repo.create_station()
    assert repo.get_station(sid).preferred_stream_id is None
```

**db_init-replay survivability test to mirror** (lines 906-923):
```python
# tests/test_repo.py:906-923
def test_preferred_stream_id_survives_db_init_replay(repo):
    sid = repo.create_station()
    stream_id = repo.insert_stream(sid, "http://twitch.tv/lofi")
    repo.con.execute(
        "UPDATE stations SET preferred_stream_id = ? WHERE id = ?",
        (stream_id, sid),
    )
    repo.con.commit()
    db_init(repo.con)
    assert repo.get_station(sid).preferred_stream_id == stream_id
```

**Round-trip setter tests to mirror** (lines 938-971):
```python
# tests/test_repo.py:938-951
def test_set_preferred_stream_round_trips_via_list_stations(repo):
    sid, yt_id, twitch_id = _seed_two_stream_station(repo)
    repo.set_preferred_stream(sid, twitch_id)
    stations = repo.list_stations()
    match = next(s for s in stations if s.id == sid)
    assert match.preferred_stream_id == twitch_id

def test_set_preferred_stream_round_trips_via_get_station(repo):
    sid, yt_id, twitch_id = _seed_two_stream_station(repo)
    repo.set_preferred_stream(sid, twitch_id)
    assert repo.get_station(sid).preferred_stream_id == twitch_id
```

**New tests for Phase 97** follow the same structure but substitute `canonical_stream_id` and `set_canonical_stream`, and add a backfill test (no preferred_stream_id equivalent):
```python
# New: test_canonical_stream_id_backfill_defaults_position1
def test_canonical_stream_id_backfill_defaults_position1(repo):
    """D-04 backfill: existing station gets canonical_stream_id = position-1 stream."""
    sid = repo.create_station()
    s1_id = repo.insert_stream(sid, "http://hi.mp3", quality="hi")
    s2_id = repo.insert_stream(sid, "http://lo.mp3", quality="lo")
    # Simulate a db_init replay that runs the backfill
    db_init(repo.con)
    station = repo.get_station(sid)
    # s1_id is position=1 (first inserted) — must be canonical
    assert station.canonical_stream_id == s1_id
```

---

### `tests/test_edit_station_dialog.py` (test, request-response)

**Analog:** same file — key patterns for column-index tests and url_edit tests that will break.

**Column-index pattern that will break** (lines 134-182):
```python
# tests/test_edit_station_dialog.py:138  — uses literal column 0
assert table.item(0, 0).text() == "http://s1.mp3"   # breaks if _COL_CANONICAL = 0

# tests/test_edit_station_dialog.py:170-177
dialog.streams_table.item(1, 0).setText("http://s2.mp3")   # breaks if _COL_URL shifts
assert table.item(0, 0).text() == "http://s2.mp3"
```

If `_COL_CANONICAL = 6` (trailing — RESEARCH recommendation), `_COL_URL` remains 0 and these tests are UNAFFECTED. If `_COL_CANONICAL = 0` (leading), every literal `0` in these column-index reads must change to `_COL_URL`.

**`url_edit` test that breaks** (lines 885-888):
```python
# tests/test_edit_station_dialog.py:885-888  — MUST UPDATE
def test_is_dirty_after_url_edit(dialog):
    """D-12: editing the URL field marks the dialog dirty."""
    dialog.url_edit.setText("http://other.example/stream")   # AttributeError after D-01
    assert dialog._is_dirty() is True
```

**Phase 97 replacement:**
```python
def test_is_dirty_after_url_edit(dialog):
    """D-12: editing the canonical stream URL cell marks the dialog dirty."""
    from PySide6.QtWidgets import QTableWidgetItem
    table = dialog.streams_table
    item = table.item(dialog._canonical_row, _COL_URL)
    if item is None:
        table.setItem(dialog._canonical_row, _COL_URL, QTableWidgetItem("http://other.example/stream"))
    else:
        item.setText("http://other.example/stream")
    assert dialog._is_dirty() is True
```

**`test_save_calls_repo_correctly` to extend** (lines 214-229):
```python
# tests/test_edit_station_dialog.py:214-229  — add assertion for set_canonical_stream
def test_save_calls_repo_correctly(qtbot, dialog, repo):
    ...
    dialog.button_box.accepted.emit()
    repo.ensure_provider.assert_called_once_with("TestProvider")
    repo.update_station.assert_called_once()
    # Phase 97 D-04: canonical marker must be persisted via dedicated setter
    repo.set_canonical_stream.assert_called_once()   # ADD THIS
```

**New drift-guard test:**
```python
def test_url_edit_widget_does_not_exist(dialog):
    """D-01 drift-guard: url_edit must not exist after Phase 97 removes it."""
    assert not hasattr(dialog, "url_edit"), (
        "url_edit survived Phase 97 D-01 removal — remove it from _build_ui"
    )
```

---

## Shared Patterns

### Single-Column Setter — "NEVER overload update_station"
**Source:** `musicstreamer/repo.py` lines 1023-1052 (`set_live_url_syncs_from_channel`, `set_live_url_title_anchor`)
**Also:** lines 814-820 (`set_preferred_stream`)
**Apply to:** `set_canonical_stream` in repo.py

The inline Pitfall 1 docstring comment is part of the pattern — copy it verbatim for `set_canonical_stream`.

### ALTER TABLE Migration Block Shape
**Source:** `musicstreamer/repo.py` lines 282-295 (preferred_stream_id ALTER)
**Apply to:** canonical_stream_id ALTER in repo.py (place after line 366 — after the last Phase-96 ALTER)

Shape: `try / con.execute("ALTER TABLE ... ADD COLUMN ...") / con.commit() / except sqlite3.OperationalError: / pass  # column already exists — idempotent`

### QTableWidgetItem with Qt.UserRole for stream_id
**Source:** `musicstreamer/ui_qt/edit_station_dialog.py` lines 1117-1118
```python
url_item = QTableWidgetItem(url)
url_item.setData(Qt.UserRole, stream_id)  # None for new rows
```
**Apply to:** reading `stream_id` back in `_on_save` (line 1848) and in the canonical marker persistence block — always read stream_id via `item.data(Qt.UserRole)`, not by table index.

### Read-only table cell (flags)
**Source:** `musicstreamer/ui_qt/edit_station_dialog.py` lines 1133-1134
```python
audio_quality_item.setFlags(audio_quality_item.flags() & ~Qt.ItemIsEditable)
```
**Apply to:** `_COL_CANONICAL` cell if the canonical marker is a `QToolButton` in a `setCellWidget` (not a `QTableWidgetItem` at all — `setCellWidget` bypasses item flags entirely).

### Migration test schema-check pattern
**Source:** `tests/test_repo.py` lines 882-897 (PRAGMA table_info, by_name dict, index-2/3/4 assertions)
**Apply to:** `test_canonical_stream_id_migration_idempotent` — identical structure, substitute column name.

---

## No Analog Found

All files have close analogs. No entries in this section.

---

## Metadata

**Analog search scope:** `musicstreamer/` and `tests/` directories
**Files scanned:** 9 (repo.py, models.py, edit_station_dialog.py, url_helpers.py, station_filter_proxy.py, now_playing_panel.py, aa_live.py, test_repo.py, test_edit_station_dialog.py)
**Pattern extraction date:** 2026-06-23
