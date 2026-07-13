# Phase 97: Resolve Station URL Duplication - Research

**Researched:** 2026-06-23
**Domain:** PySide6 QTableWidget UI + SQLite schema migration + data-model refactor
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Remove the top **"URL:" field** (`url_edit`) from the edit dialog entirely. The **streams table is the sole URL editor.** All metadata/derivation code currently reading `url_edit.text()` is rewired to read from the table instead.
- **D-02:** Metadata operations read the **live (unsaved) cell text** of the canonical stream's table row — preserving today's interactive behavior where avatar / siblings / channel-scan toggle / provider derivation react as the user types (not only after Save).
- **D-03:** The table **auto-creates an editable primary row** when a station has no streams (new station) or when the dialog opens with none, so the common single-stream case stays one-step (no "Add stream" click required to enter the first URL).
- **D-04:** Introduce a **new, pinned "canonical/primary" marker** on a stream (e.g. a star/radio control on the row). It **auto-defaults to the first stream** when a station is created, but once set it **stays pinned through reordering** (it does NOT follow row position). This is a **new, distinct field** — separate from Phase-82 `preferred_stream_id`.
- **D-05:** The canonical marker anchors the **canonical station URL + all metadata**; Phase-82 `preferred_stream_id` continues to control **which stream plays**. The two are independent.
- **D-06:** Divergence between the canonical (metadata) stream and the preferred (playback) stream on multi-stream stations is **allowed silently — no warning or guard.**
- **D-07:** **All** metadata/derivation consumers key off the single canonical stream URL uniformly — avatar fetch, Twitch provider derivation, YouTube channel-scan toggle, Phase-96 live-resync anchor, **and** AA sibling detection. One rule.

### Claude's Discretion

- Exact widget/control used for the canonical marker (star vs radio button vs context action) and its placement in the streams table.
- Precise DB representation of the canonical marker (`stations.canonical_stream_id` FK vs a `station_streams.is_canonical` boolean) — planner/researcher to choose, with a migration that defaults existing stations' canonical to their position-1 stream.
- Exact mechanism for wiring the metadata consumers to the live canonical table cell.

### Deferred Ideas (OUT OF SCOPE)

- New-station entry flow polish beyond D-03 auto-create row.
- Warning/guard UI for canonical-vs-playback divergence (D-06 chose silent).
</user_constraints>

---

## Summary

Phase 97 eliminates the two-surface URL duplication in `EditStationDialog` where the same URL must be maintained in both the top-level `url_edit` field and the streams table's first row. The database was already unified (no `stations.url` column; all URLs live in `station_streams`). The work is entirely in the UI layer and the data model's canonical-stream concept.

The primary work is:
1. Add a `stations.canonical_stream_id` FK column (mirroring `preferred_stream_id` shape), with a migration that backfills each station's first (position-1) stream as canonical.
2. Remove `url_edit` from the dialog UI. Add a "canonical" marker column (_COL_CANONICAL, column index 0 or a new leading column) to the streams table using `QWidget`-in-cell radio buttons that enforce single-selection.
3. Rewire all 15 `url_edit.text()` reads inside `edit_station_dialog.py` to read the canonical row's live cell text from `streams_table`. Wire the canonical row's `cellChanged` signal to trigger the same debounced metadata actions that `url_edit.textChanged` currently drives.
4. Update all 4 external `streams[0].url` read sites that D-07 governs (url_helpers, station_filter_proxy, now_playing_panel, aa_live/aa_import) to resolve from `canonical_stream_id` rather than positional index 0.
5. Persist the canonical marker in the save loop, guarded against the canonical-stream-deleted edge case.

**Primary recommendation:** Use `stations.canonical_stream_id` FK (ON DELETE SET NULL) mirroring the `preferred_stream_id` shape exactly. Use `QToolButton` with checkable+exclusive-per-column enforcement for the in-table canonical marker — this is simpler than a full custom delegate and matches the existing `setCellWidget` pattern on other dialogs.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Canonical marker persistence (DB schema) | Data Layer (repo.py) | — | All column mutations go through Repo; mirrors preferred_stream_id pattern |
| Canonical marker UI display/enforcement | Frontend (EditStationDialog) | — | Per-dialog UX; no other surface edits this |
| Canonical URL read (metadata/derivation) | API/Logic layer (url_helpers, now_playing_panel) | Frontend (dialog) | Consumers are both in-dialog live reads (D-02) and post-load model reads (D-07) |
| Playback stream selection | Player (player.py) | — | preferred_stream_id unchanged — D-05 |
| Live canonical cell read (debounced) | Frontend (EditStationDialog) | — | D-02: mirrors current url_edit debounce; must stay in dialog |

---

## Standard Stack

This phase is a pure Python/PySide6/SQLite refactor — no new packages. [VERIFIED: codebase grep]

### Core (existing, no new installs)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.11+ | QTableWidget, QToolButton, Signal/Slot | Already the app's UI framework |
| sqlite3 | stdlib | ALTER TABLE migration, ON DELETE SET NULL FK | Already the persistence layer |

### No new packages required
This phase installs nothing. All required primitives (QToolButton, QTableWidget.cellChanged, QButtonGroup, etc.) are in the existing PySide6 dependency.

---

## Package Legitimacy Audit

No external packages are introduced in this phase. Section not applicable.

---

## Architecture Patterns

### System Architecture Diagram

```
User types URL into streams_table canonical row
          |
          v
streams_table.cellChanged(row, col) signal
          |
    [col == _COL_URL AND row == canonical_row?]
          |
          v
_on_canonical_cell_changed()   [mirrors _on_url_text_changed]
    - restart _url_timer (500ms debounce)
    - clear _logo_status
    - update _refresh_avatar_btn enabled state
    - update _live_resync_checkbox enabled state
          |
     [timer fires]
          v
_on_url_timer_timeout()   [unchanged logic, reads canonical URL]
    - read canonical cell: _get_canonical_url_live()
    - launch _LogoFetchWorker(url, ...)
    - conditionally launch _AvatarFetchWorker(url, ...)
          |
          v
Save (_on_save):
    - persist canonical_stream_id via repo.set_canonical_stream(station_id, stream_id)
    - rest of stream loop unchanged
```

### Recommended Project Structure

No new modules. Changes are in-place to existing files:
```
musicstreamer/
├── models.py            # + canonical_stream_id: Optional[int] on Station
├── repo.py              # + migration ALTER + set_canonical_stream() + get_canonical_stream_id()
├── url_helpers.py       # update find_aa_siblings + suggest_similar: streams[0] -> canonical_url()
├── aa_live.py           # update get_di_channel_key: streams[0] -> canonical_url()
└── ui_qt/
    ├── edit_station_dialog.py  # remove url_edit, add _COL_CANONICAL, rewire 15 reads
    ├── now_playing_panel.py    # _refresh_siblings: streams[0].url -> canonical_url(station)
    ├── station_filter_proxy.py # filterAcceptsRow: streams[0].url -> canonical_url(station)
    └── add_sibling_dialog.py   # fallback streams[0].url -> canonical_url(station)
```

### Pattern 1: Single-Column Setter (repo.py canonical-marker setter)

**What:** A dedicated `UPDATE stations SET canonical_stream_id = ? WHERE id = ?` method on `Repo` — NOT wired through `update_station`. [VERIFIED: codebase inspection of Phase 82/96 setter pattern]

**When to use:** Any time the canonical marker changes (in the `_on_save` path, after the stream loop completes and `ordered_ids` is known).

```python
# Source: musicstreamer/repo.py (Phase 82 set_preferred_stream shape)
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

### Pattern 2: DB Migration (repo.py ALTER TABLE)

**What:** Add `canonical_stream_id` to `stations` with `ON DELETE SET NULL`, then backfill from the position-1 stream for each station. [ASSUMED] — exact backfill SQL is research, but mirrors the `preferred_stream_id` shape exactly.

```python
# Source: repo.py lines 282-295 (preferred_stream_id migration shape)
# Phase 97 D-04 — per-station canonical (metadata anchor) stream FK.
# MUST land AFTER the legacy URL-column rebuild block (Pitfall 2): the
# rebuild's CREATE TABLE stations_new / INSERT SELECT does not carry
# dynamically-added columns, so placing the ALTER here ensures the column
# lands on the rebuilt (or fresh) table.
# ON DELETE SET NULL: if the canonical stream is deleted, the FK goes NULL
# and callers fall through to the position-1 fallback (same as preferred_stream_id).
try:
    con.execute(
        "ALTER TABLE stations ADD COLUMN canonical_stream_id INTEGER "
        "REFERENCES station_streams(id) ON DELETE SET NULL"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent

# One-time backfill: set canonical_stream_id to the position-1 stream
# for all stations that have at least one stream and no canonical set yet.
# The NOT EXISTS guard makes this idempotent — a second db_init is a no-op.
con.execute(
    """
    UPDATE stations
    SET canonical_stream_id = (
        SELECT id FROM station_streams
        WHERE station_id = stations.id
        ORDER BY position, id
        LIMIT 1
    )
    WHERE canonical_stream_id IS NULL
      AND EXISTS (SELECT 1 FROM station_streams WHERE station_id = stations.id)
    """
)
con.commit()
```

**Key detail:** The backfill uses `ORDER BY position, id` (position first, then id as tiebreak) to guarantee determinism. The NOT EXISTS guard (`WHERE canonical_stream_id IS NULL`) means running db_init a second time never changes a canonical marker the user has set. [ASSUMED: SQL idiom based on standard SQLite patterns — no Context7 lookup needed for this.]

### Pattern 3: Live Canonical URL Accessor (dialog-internal helper)

**What:** A private method `_get_canonical_url_live()` that reads the QTableWidget cell text for the canonical row. Used everywhere `url_edit.text()` is currently read in the dialog.

```python
# Source: pattern derived from existing _add_stream_row / streams_table API
def _get_canonical_url_live(self) -> str:
    """Phase 97 D-02: return the live (unsaved) text of the canonical stream's URL cell.

    Reads from the streams table widget directly, preserving D-02's
    requirement that metadata consumers react as the user types (not only
    after Save). Falls back to "" when no rows or no canonical row is set.
    """
    row = self._canonical_row  # index into streams_table; -1 when no rows
    if row < 0 or row >= self.streams_table.rowCount():
        return ""
    item = self.streams_table.item(row, _COL_URL)
    return item.text() if item else ""
```

`self._canonical_row` is a tracked integer instance variable:
- Set to 0 on dialog open when streams exist (default first row = canonical).
- Updated when the user clicks a different canonical marker button.
- Pinned: does NOT change on `_move_up` / `_move_down` row reordering.

### Pattern 4: Canonical Marker Widget (QToolButton in cell)

**What:** Add a new `_COL_CANONICAL = 0` (leftmost) column to `streams_table` using `setCellWidget(row, _COL_CANONICAL, btn)` where `btn` is a `QToolButton` with `setCheckable(True)`, star icon, and a `QButtonGroup` ensuring single-selection across all rows. [VERIFIED: PySide6 QTableWidget docs, QButtonGroup exclusivity]

**Concrete approach:**
```python
# Pattern: QButtonGroup for exclusive single-select across rows
# One group per streams_table; buttons added on row creation.
self._canonical_group = QButtonGroup(self)
self._canonical_group.setExclusive(True)

# Per row, in _add_stream_row:
canonical_btn = QToolButton()
canonical_btn.setText("★")  # or setIcon(star_icon)
canonical_btn.setCheckable(True)
canonical_btn.setAutoExclusive(False)  # managed by QButtonGroup instead
canonical_btn.setToolTip("Set as canonical (metadata anchor) stream")
self._canonical_group.addButton(canonical_btn, id=row_index)
self.streams_table.setCellWidget(row, _COL_CANONICAL, canonical_btn)

# When canonical changes:
self._canonical_group.buttonClicked.connect(self._on_canonical_changed)

def _on_canonical_changed(self, btn: QToolButton) -> None:
    # Determine which row this button is in
    self._canonical_row = self._canonical_group.id(btn)
    # Trigger debounced metadata refresh (D-02)
    self._url_timer.start()
    self._logo_status_clear_timer.stop()
    self._logo_status.clear()
    self._update_url_gated_controls()
```

**Alternative approach (simpler — no QButtonGroup):** Keep the group management manually: on any canonical button click, iterate all rows, uncheck all OTHER canonical buttons, check only this one, and set `self._canonical_row`. This is more explicit and easier to debug in tests.

**Recommended:** Manual single-selection is clearer and avoids QButtonGroup ID tracking complexity when rows are added/removed mid-session. The planner should choose whichever the implementer finds simpler.

**Column shift:** Adding `_COL_CANONICAL = 0` shifts all existing columns by 1:
```
Before: _COL_URL=0, _COL_QUALITY=1, _COL_CODEC=2, _COL_BITRATE=3, _COL_POSITION=4, _COL_AUDIO_QUALITY=5
After:  _COL_CANONICAL=0, _COL_URL=1, _COL_QUALITY=2, _COL_CODEC=3, _COL_BITRATE=4, _COL_POSITION=5, _COL_AUDIO_QUALITY=6
```
Every reference to `_COL_URL`, `_COL_QUALITY`, etc. in the dialog and tests must be updated.

### Pattern 5: Station.canonical_url() accessor (models.py helper or standalone function)

**What:** A `Station.canonical_url` property or a standalone `canonical_url(station: Station) -> str` function in `url_helpers.py` that resolves the canonical stream URL from the loaded Station model. Used by external consumers (D-07 — `url_helpers`, `now_playing_panel`, `station_filter_proxy`, `aa_live`).

```python
# Recommended: property on Station dataclass OR module-level helper in url_helpers.py
def canonical_url(station: "Station") -> str:
    """Return the URL of the station's canonical (metadata anchor) stream.

    Phase 97 D-07: all metadata/derivation consumers key off this single URL.
    Resolution order:
      1. Stream matching station.canonical_stream_id (if set and present in streams)
      2. Stream at position 1 (fallback: unset or stale FK after delete)
      3. First stream by list order (defensive: position not yet normalized)
      4. "" (no streams at all)
    """
    if not station.streams:
        return ""
    if station.canonical_stream_id is not None:
        for s in station.streams:
            if s.id == station.canonical_stream_id:
                return s.url
    # Fallback: position-1 stream (same semantics as before Phase 97)
    by_pos = sorted(station.streams, key=lambda s: (s.position, s.id))
    return by_pos[0].url if by_pos else ""
```

Adding a property directly to the `Station` dataclass is cleaner for callers:
```python
@property
def canonical_url(self) -> str:
    ...
```
BUT: `Station` is a `@dataclass` — properties on dataclasses work in Python but the presence of `@dataclass` does not prevent adding `@property` methods. However, frozen dataclasses (`frozen=True`) would prevent this; `Station` is NOT frozen. [VERIFIED: models.py inspection — no `frozen=True`]

**Planner's choice:** Either a property on `Station` or a module-level function in `url_helpers.py`. Property is cleaner (all callers already hold a `Station`). Function is easier to test in isolation. Research recommendation: **property on Station** — it's self-contained and requires no import in consumers.

### Anti-Patterns to Avoid

- **Overloading `update_station` with `canonical_stream_id`:** The documented Pitfall 1 (Phase 96, repo.py:1023-1035). The setter must be a separate `set_canonical_stream` method. [VERIFIED: codebase grep of Pitfall 1 comment]
- **Reading `streams[0].url` as proxy for canonical URL in D-07 call sites:** Phase 97's whole point. After the migration, `streams[0]` is positionally first but NOT necessarily canonical.
- **Placing the canonical backfill ALTER before the legacy URL rebuild block:** SQLite's CREATE TABLE stations_new / INSERT SELECT in the existing migration (lines 208-265) does NOT carry dynamically-added columns, so the canonical_stream_id ALTER must land AFTER that block. [VERIFIED: repo.py inspection, existing Phase 82/83/89A/96 comments on this Pitfall]
- **Tracking canonical by row index alone:** If the user reorders rows (Move Up/Down), `_canonical_row` must be updated to reflect the NEW row index of the canonical stream's content — OR the canonical marker must be tracked by stream_id (stored in the button itself as a Python attribute), and `_canonical_row` derived from which row currently holds that stream_id. See Pitfall 4 below.
- **Putting the `url_edit` snapshot in the dirty-state baseline after removal:** `_snapshot_form_state` currently captures `"url": self.url_edit.text()`. After removing `url_edit`, this must be replaced with `"canonical_url": self._get_canonical_url_live()` — otherwise dirty detection breaks.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Single-select button group in table | Manual tracking with flags | QButtonGroup(exclusive=True) OR manual uncheck-others | Qt provides the mechanism; the concern is QButtonGroup + setCellWidget ID alignment — manual is equally valid |
| ON DELETE behavior for canonical_stream_id | Application-level cascade | SQLite ON DELETE SET NULL on the FK | SQLite enforces this at DB level even if app logic misses the case; mirrors preferred_stream_id |
| Debounce timer | Re-implement | Reuse existing `_url_timer` QTimer | The timer already exists and drives logo/avatar fetch; just ensure it's restarted from the canonical cell change handler |

**Key insight:** The hardest engineering problem in this phase is not the DB or UI individually — it is the N-to-1 rewiring of 15 `url_edit.text()` call sites to a single `_get_canonical_url_live()` helper, while ensuring the `cellChanged` signal (which fires for ALL columns and ALL rows) is correctly filtered to only trigger metadata actions when the canonical row's URL column changes.

---

## Full Call-Site Inventory

### url_edit.text() reads in edit_station_dialog.py (verified by grep)

| Line | Context | D-07 or internal? | Action |
|------|---------|-------------------|--------|
| 754 | `_snapshot_form_state` dirty baseline — `"url": self.url_edit.text()` | Internal dialog | Replace with `"canonical_url": self._get_canonical_url_live()` |
| 792 | `_refresh_siblings` docstring comment (describes the read at 832) | Doc only | Update comment |
| 832 | `_refresh_siblings` live read: `current_url = self.url_edit.text().strip()` | Internal dialog (D-07 AA) | Replace with `_get_canonical_url_live()` |
| 1057 | `_on_add_sibling_clicked` passes `live_url=self.url_edit.text().strip()` | Internal dialog | Replace with `_get_canonical_url_live()` |
| 1318 | `_on_url_text_changed` — URL gate for `_refresh_avatar_btn` enable | Becomes `_on_canonical_cell_changed` | Method renamed/replaced — reads canonical cell |
| 1334 | `_on_live_resync_toggled` — `url = self.url_edit.text().strip()` for YT gate | Internal dialog | Replace with `_get_canonical_url_live()` |
| 1350 | `_on_url_timer_timeout` — `url = self.url_edit.text().strip()` for logo fetch | Internal dialog | Replace with `_get_canonical_url_live()` |
| 1410 | Avatar fetch block: `url = self.url_edit.text().strip()` | Internal dialog | Replace with `_get_canonical_url_live()` |
| 1526 | `_on_logo_fetched`: error path `url = self.url_edit.text().strip()` | Internal dialog | Replace with `_get_canonical_url_live()` |
| 1684 | `_on_refresh_avatar_clicked`: `url = self.url_edit.text().strip()` | Internal dialog | Replace with `_get_canonical_url_live()` |
| 1789 | `_on_save` Twitch provider derivation: `_url_for_derive = self.url_edit.text().strip()` | D-07 Twitch derive | Replace with `_get_canonical_url_live()` |
| 1916 | `_on_save` sync avatar fetch: `self._maybe_fetch_avatar_sync(self.url_edit.text()...)` | Internal dialog | Replace with `_get_canonical_url_live()` |

Also the `url_edit` initialization (lines 431-444) and the `_populate` seeding (line 652) are removed entirely.

### streams[0].url D-07 external call sites (verified by grep)

These callers read the persisted Station model (after load from DB) — they must switch to the `canonical_url(station)` accessor:

| File | Line | Context | Action |
|------|------|---------|--------|
| `musicstreamer/url_helpers.py` | 216 | `find_aa_siblings` — `cand_url = st.streams[0].url` | → `canonical_url(st)` |
| `musicstreamer/url_helpers.py` | 358 | `suggest_similar` — `current_station.streams[0].url` | → `canonical_url(current_station)` |
| `musicstreamer/ui_qt/station_filter_proxy.py` | 179 | `filterAcceptsRow` — `url = streams[0].url` | → `canonical_url(station)` |
| `musicstreamer/ui_qt/now_playing_panel.py` | 2433 | `_refresh_siblings` — `current_url = self._station.streams[0].url` | → `canonical_url(self._station)` |
| `musicstreamer/aa_live.py` | 161 | `get_di_channel_key` — `url = streams[0].url` | → `canonical_url(station)` |

### streams[0] reads that are NOT D-07 and should NOT be changed

These access streams[0] for reasons OTHER than metadata/derivation:

| File | Line | Context | Keep as-is? |
|------|------|---------|-------------|
| `live_refresh_dialog.py:271` | Fallback stream for live-refresh remap when stream_id stale | YES — positional fallback in remap logic, not metadata derivation |
| `live_refresh_dialog.py:455` | Primary stream ID for remap operation (uses position==1 loop first) | YES — this is about finding the update target stream, not canonical URL |
| `live_refresh_dialog.py:613` | Same as :455 in DiscoverRowWidget | YES |
| `ui_qt/add_sibling_dialog.py:286` | Fallback when no live_url provided — `station.streams[0].url` | Consider updating to `canonical_url(station)` for consistency, but NOT a D-07 requirement |
| `ui_qt/now_playing_panel.py:2796,2803` | Non-URL reads (`self._streams[0]` for playback stream logic) | Not URL reads — leave alone |
| `musicstreamer/aa_import.py:233` | Import path — uses `streams[0].id` to update, not URL metadata | Leave alone |
| `musicstreamer/soma_import.py:318` | Import path — `streams[0].id` for stream update | Leave alone |
| `musicstreamer/gbs_api.py:1241` | `first_url = streams[0]["url"]` in GBS context — dict, not Station | Not a Station.streams read — leave alone |

---

## Common Pitfalls

### Pitfall 1: Never add canonical_stream_id to update_station

**What goes wrong:** Adding `canonical_stream_id` as a parameter to `update_station()` means any caller that omits it (all 7+ existing callers) silently resets it to NULL on every Save.

**Why it happens:** `update_station` already has documented this anti-pattern (Phase 73 D-05 cover_art_source). The pattern repeats.

**How to avoid:** `set_canonical_stream(station_id, stream_id)` is a dedicated single-column setter. The save loop calls it AFTER the stream-persist block, once `ordered_ids` is known. [VERIFIED: repo.py:1023-1049 set_live_url_syncs_from_channel + set_live_url_title_anchor as precedents]

**Warning signs:** Tests fail with canonical_stream_id = NULL after a Save that did not call `set_canonical_stream`.

### Pitfall 2: canonical_stream_id ALTER must land after the legacy URL rebuild block

**What goes wrong:** The existing migration block (lines 208-265) does a `CREATE TABLE stations_new / INSERT SELECT / DROP TABLE stations / ALTER TABLE stations_new RENAME TO stations`. Any ALTER TABLE that precedes this block is applied to the OLD stations table, which then gets dropped.

**Why it happens:** SQLite doesn't support DROP COLUMN before 3.35; the pattern is table-rebuild. Dynamically-added columns are only preserved if they appear AFTER the rebuild.

**How to avoid:** Place the canonical_stream_id ALTER AFTER line 265 (after the `except sqlite3.OperationalError: pass` of the rebuild block). This is the explicit pattern called out in every Phase 73/82/83/89A/96 ALTER comment. [VERIFIED: repo.py inline comments]

### Pitfall 3: Orphan sweep does NOT need updating

**What goes wrong:** Developer adds `canonical_stream_id` to `sweep_orphans` — but `sweep_orphans` only sweeps FK-child tables where the PARENT was deleted outside the app (station_streams orphaned by manual station deletion). `canonical_stream_id` is a nullable FK on stations WITH `ON DELETE SET NULL`, so SQLite handles it automatically when the stream is deleted with FK enabled.

**Why it happens:** `sweep_orphans` sweeps child rows; `canonical_stream_id` is a nullable column on the PARENT table.

**How to avoid:** The existing `sweep_orphans` function needs NO changes. The `ON DELETE SET NULL` on `canonical_stream_id` handles the case automatically. [VERIFIED: repo.py:456-502 sweep_orphans scope comment D-05..D-08]

### Pitfall 4: Canonical row tracking after Move Up / Move Down

**What goes wrong:** `self._canonical_row` stores the TABLE ROW INDEX. After `_on_move_up` or `_on_move_down`, the canonical stream's content shifts to a different row index but `_canonical_row` still points at the OLD index.

**Why it happens:** QTableWidget row operations (insertRow/removeRow + copy) physically rearrange items; the row-index-to-content mapping changes.

**How to avoid:** Two approaches:
1. Store canonical stream_id (from `Qt.UserRole` of the URL item) rather than row index. After any reorder, scan all rows to find the row whose `_COL_URL` item's `Qt.UserRole` matches the stored canonical stream_id. More robust.
2. In `_on_move_up` / `_on_move_down`, explicitly update `_canonical_row` to follow the content. Simpler but requires careful bookkeeping.

**Recommendation:** Approach 2 is consistent with how `_on_move_up` already adjusts `table.selectRow(new_row)`. Add `if self._canonical_row == row: self._canonical_row = new_row` (and the inverse for the adjacent row).

**Warning signs:** After reordering a 2-stream station, the canonical marker visually stays on row 0 but `_canonical_row` is 1 (or vice versa), causing metadata to read from the wrong row.

### Pitfall 5: cellChanged fires for ALL columns and ALL rows

**What goes wrong:** Connecting `streams_table.cellChanged` to the URL debounce handler causes logo/avatar fetch to fire when the user edits Quality, Codec, Bitrate, or Position columns.

**Why it happens:** `QTableWidget.cellChanged(row, col)` emits for any item change in any cell.

**How to avoid:** In `_on_canonical_cell_changed(row, col)`, early-exit unless `row == self._canonical_row AND col == _COL_URL`. [ASSUMED: standard Qt pattern, cross-verified against QTableWidget signal docs]

**Warning signs:** Avatar fetch fires when user changes bitrate of the canonical stream.

### Pitfall 6: canonical_stream_id deleted in prune_streams — FK handles it, but dialog must resync

**What goes wrong:** User removes all streams via the UI, then the save path calls `prune_streams(station.id, [])`. SQLite FK `ON DELETE SET NULL` fires, setting `canonical_stream_id = NULL`. But the dialog's internal `_canonical_row = -1` may not be in sync.

**Why it happens:** prune_streams deletes rows; ON DELETE SET NULL fires in SQLite; the dialog's in-memory `self._canonical_row` is stale.

**How to avoid:** In `_on_save`, after calling `prune_streams` and `reorder_streams`, determine the new canonical stream_id: find the table row at `_canonical_row`, read its `Qt.UserRole` stream_id; if that id is in `ordered_ids`, call `repo.set_canonical_stream(station.id, stream_id)`. If it is NOT in `ordered_ids` (user deleted the canonical stream), call `repo.set_canonical_stream(station.id, ordered_ids[0] if ordered_ids else None)`.

**Warning signs:** After deleting the canonical stream and saving, the new canonical is NULL, and the next dialog open re-defaults to position-1 (correct behavior but must be tested).

### Pitfall 7: dirty-state snapshot still references url_edit

**What goes wrong:** `_snapshot_form_state` currently includes `"url": self.url_edit.text()`. After removing `url_edit`, this key must be replaced — otherwise _snapshot_form_state raises `AttributeError` or always returns stale data.

**Why it happens:** Mechanical removal of url_edit without updating all downstream consumers.

**How to avoid:** Replace `"url": self.url_edit.text()` with `"canonical_url": self._get_canonical_url_live()` in `_snapshot_form_state`. [VERIFIED: edit_station_dialog.py:753-762]

### Pitfall 8: QButtonGroup IDs become stale after row removal

**What goes wrong:** If using QButtonGroup with integer IDs = row index, removing a row makes all subsequent rows' IDs off-by-one.

**Why it happens:** QButtonGroup IDs are set at add-time; they don't auto-update.

**How to avoid:** If using QButtonGroup, assign IDs as stream_id (from Qt.UserRole) not row index. Or avoid QButtonGroup and do manual uncheck logic (simpler in this context). **Recommendation: skip QButtonGroup, use manual tracking.**

---

## DB Schema Recommendation

**Recommended representation:** `stations.canonical_stream_id INTEGER REFERENCES station_streams(id) ON DELETE SET NULL`

**Why FK on stations (not boolean on station_streams):**
- Mirrors `preferred_stream_id` shape exactly — zero new patterns for maintainers.
- ON DELETE SET NULL is handled atomically by SQLite when FK enforcement is ON (which db_connect guarantees). [VERIFIED: repo.py db_connect, PRAGMA foreign_keys = ON]
- No partial-unique index needed (vs the is_canonical boolean approach, which would require a partial index `WHERE is_canonical = 1` to enforce one-per-station).
- Single `JOIN` to resolve: `SELECT ss.url FROM station_streams ss WHERE ss.id = s.canonical_stream_id`.
- `sweep_orphans` needs zero changes.

**Why not `station_streams.is_canonical` boolean:**
- Requires enforcing one-per-station at application level OR a partial-unique index.
- SQLite supports partial indexes (`CREATE UNIQUE INDEX ... WHERE is_canonical = 1`) but this is a more complex invariant to maintain and test.
- Every stream update that changes is_canonical requires verifying the invariant.
- Backfill is more complex (set exactly one row per station).
- The FK pattern is already established and well-tested in this codebase.

**Exact migration SQL (idempotent):**

```sql
-- Step 1: Add column (idempotent via try/except OperationalError)
ALTER TABLE stations ADD COLUMN canonical_stream_id INTEGER
    REFERENCES station_streams(id) ON DELETE SET NULL;

-- Step 2: Backfill (idempotent: only runs for NULL canonical_stream_id rows)
UPDATE stations
SET canonical_stream_id = (
    SELECT id FROM station_streams
    WHERE station_id = stations.id
    ORDER BY position ASC, id ASC
    LIMIT 1
)
WHERE canonical_stream_id IS NULL
  AND EXISTS (
    SELECT 1 FROM station_streams WHERE station_id = stations.id
  );
```

**FK enforcement gate:** Because `PRAGMA foreign_keys = ON` is set by `db_connect()` (verified), the `ON DELETE SET NULL` fires correctly when a stream is deleted via `repo.delete_stream()` or `repo.prune_streams()`. The `PRAGMA foreign_keys = OFF` block in the stations table rebuild (lines 227-261) is only executed once (when `stations.url` still exists); after that migration has run, the OFF block never executes again. Therefore canonical_stream_id's ON DELETE SET NULL is always active in production. [VERIFIED: repo.py inspection]

---

## D-03: Auto-Create Primary Row

**Current behavior (existing code):** When `is_new=True`, `__init__` calls `self._add_stream_row()` after `_populate()` to pre-add one blank stream row (edit_station_dialog.py:367-374). This already exists. [VERIFIED: edit_station_dialog.py:367-374]

**Phase 97 change:** D-03 extends this to also fire when an existing station has no streams (the `if streams:` branch in `_populate` falls through). Currently when `streams = []`, `url_edit.setText(streams[0].url)` is skipped and the streams table is empty.

**Implementation:** In `_populate`, after the streams-table loop, if `self.streams_table.rowCount() == 0`, call `self._add_stream_row()` and set `self._canonical_row = 0`. This is a one-liner addition to the existing populate path.

---

## D-02: Wiring Live Canonical Cell Read

**Current mechanism:** `url_edit.textChanged` → `_on_url_text_changed()` → starts `_url_timer` (500ms). Timer fires → `_on_url_timer_timeout()` → reads `url_edit.text()`, launches workers.

**Phase 97 replacement:**
- `url_edit.textChanged` → REMOVED (url_edit deleted).
- `streams_table.cellChanged(row, col)` → `_on_canonical_cell_changed(row, col)`.
  - `_on_canonical_cell_changed` early-exits unless `row == self._canonical_row AND col == _COL_URL`.
  - Otherwise: same body as current `_on_url_text_changed` — restart timer, clear status, update gated controls.
- `_on_url_timer_timeout` — unchanged except reads `_get_canonical_url_live()` instead of `url_edit.text()`.

**Signal to connect:** `QTableWidget.cellChanged(row: int, column: int)` fires when an item's data changes. This is the correct signal for in-place typing. [ASSUMED: standard Qt behavior from training knowledge — not Context7-verified, but well-established Qt behavior]

**Note:** `cellChanged` also fires during programmatic item population in `_add_stream_row` (when `setItem` is called). This requires a guard: set a `self._populating` flag in `_populate` / `_add_stream_row` and skip the canonical-cell-changed handler while it is True. Otherwise, `_add_stream_row` during `_populate` fires the debounce timer for the initial url. [ASSUMED: standard Qt gotcha with cellChanged during programmatic population — consistent with how this codebase uses timers]

---

## Code Examples

### Adding canonical_stream_id to Station dataclass
```python
# Source: musicstreamer/models.py (mirrors preferred_stream_id field)
@dataclass
class Station:
    ...
    preferred_stream_id: Optional[int] = None  # Phase 82 D-01
    canonical_stream_id: Optional[int] = None  # Phase 97 D-04: metadata anchor stream
    ...
```

### Repo list_stations / get_station update
```python
# Add to SELECT in list_stations and get_station:
# (s.canonical_stream_id is already selected via s.*)
Station(
    ...
    preferred_stream_id=r["preferred_stream_id"],
    canonical_stream_id=r["canonical_stream_id"],  # Phase 97 D-04
    ...
)
```

### _on_save canonical persist
```python
# In _on_save, after repo.reorder_streams(station.id, ordered_ids):
# Phase 97 D-04: persist canonical marker
_canonical_url_item = table.item(self._canonical_row, _COL_URL) if self._canonical_row >= 0 else None
_canonical_stream_id: Optional[int] = (
    _canonical_url_item.data(Qt.UserRole) if _canonical_url_item else None
)
# If canonical stream was deleted (not in ordered_ids), fall back to first
if _canonical_stream_id not in ordered_ids:
    _canonical_stream_id = ordered_ids[0] if ordered_ids else None
repo.set_canonical_stream(station.id, _canonical_stream_id)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `stations.url` column | Migrated to `station_streams.url` | Pre-Phase 97 (migration in repo.py:208-265) | DB already single-source |
| `streams[0].url` as canonical | `station.canonical_url` property / FK | Phase 97 | Canonical no longer positional |
| `url_edit` as live metadata source | Canonical table row cell live text | Phase 97 | Removes duplicate UI surface |

**Deprecated/outdated after this phase:**
- `url_edit` QLineEdit widget: removed from dialog
- `self._url_timer` connected to `url_edit.textChanged`: rewired to `streams_table.cellChanged`
- The `"url"` key in `_snapshot_form_state`: replaced by `"canonical_url"`

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9+ with pytest-qt |
| Config file | pyproject.toml |
| Quick run command | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py tests/test_repo.py -x --tb=short` |
| Full suite command | `.venv/bin/python -m pytest tests/ -x --tb=short` (suite > 600s — scope it) |

### Phase Requirements → Test Map
| Behavior | Test Type | Automated Command |
|----------|-----------|-------------------|
| canonical_stream_id column added idempotently | unit/migration | `.venv/bin/python -m pytest tests/test_repo.py -k canonical_stream_id -x` |
| Backfill defaults to position-1 stream | unit/migration | `.venv/bin/python -m pytest tests/test_repo.py -k canonical_backfill -x` |
| `set_canonical_stream` round-trip | unit | `.venv/bin/python -m pytest tests/test_repo.py -k canonical -x` |
| Dialog opens without url_edit widget | unit/UI | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k "no_url_edit or canonical" -x` |
| Canonical marker defaults to first row | unit/UI | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k canonical -x` |
| Metadata reads canonical row live (D-02) | unit/UI | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k canonical_live -x` |
| canonical_stream_id persisted on Save | unit/UI | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k save_canonical -x` |
| canonical_url() resolves FK correctly | unit | `.venv/bin/python -m pytest tests/test_url_helpers.py -k canonical -x` |
| AA siblings use canonical_url not streams[0] | unit | `.venv/bin/python -m pytest tests/test_aa_siblings.py -k canonical -x` |
| playback still uses preferred_stream_id (D-05) | unit | `.venv/bin/python -m pytest tests/test_player_* -x --tb=short` |
| Reorder: canonical stays pinned, not positional | unit/UI | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k reorder_canonical -x` |

### Sampling Rate
- **Per task commit:** Quick run (test_edit_station_dialog.py + test_repo.py targeted)
- **Per wave merge:** Full suite scoped to modified-file tests
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps (tests to create)
- [ ] `tests/test_repo.py` — `test_canonical_stream_id_migration_idempotent` (mirrors test_preferred_stream_id_migration_idempotent)
- [ ] `tests/test_repo.py` — `test_canonical_stream_id_backfill_defaults_position1`
- [ ] `tests/test_repo.py` — `test_canonical_stream_id_default_none_on_fresh_station`
- [ ] `tests/test_repo.py` — `test_set_canonical_stream_round_trip`
- [ ] `tests/test_repo.py` — `test_canonical_stream_id_on_delete_set_null_when_stream_deleted`
- [ ] `tests/test_edit_station_dialog.py` — `test_url_edit_widget_does_not_exist` (drift-guard: `hasattr(dialog, 'url_edit')` is False after D-01)
- [ ] `tests/test_edit_station_dialog.py` — `test_canonical_marker_defaults_to_row_0`
- [ ] `tests/test_edit_station_dialog.py` — `test_canonical_marker_stays_pinned_after_reorder`
- [ ] `tests/test_edit_station_dialog.py` — `test_save_persists_canonical_stream_id`
- [ ] `tests/test_edit_station_dialog.py` — `test_dirty_state_captures_canonical_url_not_url_edit`

### Existing tests that will break and need updating

| Test | Why it breaks | Fix |
|------|---------------|-----|
| `test_name_field_populated` | Not affected | No change |
| `test_stream_table_populated_and_add` | `table.item(0, 0)` now `table.item(0, _COL_URL)` = column 1 (if canonical column added at 0) | Update column index |
| `test_move_up_down_reorder` | Same column index shift | Update |
| `test_save_calls_repo_correctly` | `repo.set_canonical_stream` must now be asserted | Add assertion |
| `test_is_dirty_after_url_edit` (line 885) | `dialog.url_edit` removed | Replace with table cell edit |
| Tests at lines 515, 574, 587, 595, 601, 1956, 1965, 1973, 2123, 2148, 2168, 2256, 2280, 2287 | `dialog.url_edit.setText(...)` | Replace with `dialog.streams_table.item(0, _COL_URL).setText(...)` |

Note: test_edit_station_dialog.py has 97 tests (counted from grep). The canonical column shift from `_COL_URL=0` to `_COL_URL=1` will affect every test that references column index 0 by literal value or via `_COL_URL`. Importing `_COL_URL` from the module in tests means the constant shift propagates automatically — but tests that use literal `0` for the column index will break.

---

## Security Domain

This phase is a UI refactor with no network-facing surface changes, no new input parsing, and no authentication changes. The existing security posture (T-39-01 PlainText on labels, parameterized SQL in all Repo methods) is preserved without modification.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes (URL in canonical cell) | Same as current — no new validation needed; url_helpers already validates URLs for AA/YT patterns |
| V1 Architecture | yes (data flow change) | Architecture review: D-07 ensures one canonical URL source, reducing attack surface vs two divergent surfaces |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `cellChanged` fires during programmatic `setItem` in `_add_stream_row`, requiring a `_populating` guard | D-02 Wiring | If it doesn't fire, the guard is harmless overhead. If it does and no guard is added, spurious debounce during populate; low severity |
| A2 | `QButtonGroup` with per-row buttons requires careful ID management on row add/remove — manual tracking is simpler | Pattern 4 | If QButtonGroup is chosen, implementer must update IDs on removal |
| A3 | The backfill `ORDER BY position ASC, id ASC` correctly selects position-1 stream as canonical for all existing stations | DB migration | If any station has multiple streams at position=1, id order is used as tiebreak — acceptable |
| A4 | Adding a `canonical_url` property to the `Station` dataclass is valid Python (dataclass + property coexists) | Pattern 5 | If dataclass decorator conflicts (it does not — verified in models.py no frozen=True), implementer must use a standalone function in url_helpers instead |

---

## Open Questions (RESOLVED)

All three open questions were resolved during planning; the resolutions are encoded in the 97-0x-PLAN.md context/interface blocks.

1. **Column position for `_COL_CANONICAL`** — RESOLVED: **trailing column `_COL_CANONICAL = 6`** (after `_COL_AUDIO_QUALITY = 5`). Minimizes test breakage — all existing `_COL_URL=0` references stay valid. Locked in 97-03.
   - Original analysis: Adding canonical at column 0 would shift every column index; trailing accepted (star visually farther from URL) to avoid churn across the dialog tests.

2. **`Station.canonical_url` as property vs standalone function** — RESOLVED: **`@property def canonical_url` on the `Station` dataclass** (models.py) for cleaner call sites. Locked in 97-02.
   - Original analysis: Both equally testable; property chosen over a standalone url_helpers function.

3. **`add_sibling_dialog.py:286` `streams[0].url` fallback** — RESOLVED: **YES, treat as a D-07 consumer** — update to `canonical_url(station)`, consistent with D-07's "all metadata/derivation" rule. Locked in 97-04 Task 2.
   - Original analysis: This is the CR-03 backward-compat fallback when no `live_url` is passed; D-07 covers all metadata consumers.

---

## Environment Availability

Step 2.6: SKIPPED — this phase is code/config changes only. No external tooling dependencies beyond the project's existing Python venv with PySide6 and pytest.

---

## Sources

### Primary (HIGH confidence)
- `musicstreamer/repo.py` (direct inspection) — migration patterns, preferred_stream_id FK shape, Pitfall 1/2 comments, sweep_orphans scope
- `musicstreamer/ui_qt/edit_station_dialog.py` (direct inspection) — url_edit wiring, 15 call sites, existing column constants, dirty-state snapshot, _on_save stream loop
- `musicstreamer/models.py` (direct inspection) — Station dataclass shape, existing optional fields
- `musicstreamer/url_helpers.py` (direct inspection) — streams[0].url D-07 call sites at lines 216, 358
- `musicstreamer/ui_qt/station_filter_proxy.py` (direct inspection) — streams[0].url at line 179
- `musicstreamer/ui_qt/now_playing_panel.py` (direct inspection) — streams[0].url at line 2433
- `musicstreamer/aa_live.py` (direct inspection) — streams[0].url at line 161
- `tests/test_edit_station_dialog.py` (direct inspection) — existing test count, url_edit.setText usages
- `tests/test_repo.py` (direct inspection) — preferred_stream_id test shape to mirror

### Secondary (MEDIUM confidence)
- Standard PySide6 QTableWidget patterns (QButtonGroup, setCellWidget, cellChanged signal) — training knowledge, consistent with existing codebase patterns
- SQLite ON DELETE SET NULL behavior with FK enforcement — training knowledge + verified against repo.py PRAGMA enforcement pattern

### Tertiary (LOW confidence — flagged [ASSUMED])
- cellChanged fires during programmatic setItem (A1)
- QButtonGroup ID management concerns (A2)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all primitives are existing PySide6/SQLite
- Architecture: HIGH — clear from codebase inspection; migration pattern is exact copy of preferred_stream_id
- Pitfalls: HIGH — all verified against actual code (Pitfall 1/2/3 cited with exact line numbers)
- Call-site inventory: HIGH — grep-verified, all 15 url_edit.text() and streams[0].url reads documented

**Research date:** 2026-06-23
**Valid until:** 2026-07-23 (stable codebase; no external dependencies)
