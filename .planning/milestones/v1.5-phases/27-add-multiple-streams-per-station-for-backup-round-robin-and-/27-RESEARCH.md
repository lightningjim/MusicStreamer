# Phase 27: Add Multiple Streams Per Station - Research

**Researched:** 2026-04-08
**Domain:** SQLite schema migration, GTK4/Libadwaita sub-dialog UX, multi-stream data model
**Confidence:** HIGH

## Summary

This phase normalizes the station data model from a single `url` field on the `stations` table to a dedicated `station_streams` table. The scope is: schema creation + migration, Station dataclass update, all CRUD callsites updated to use streams, a "Manage Streams" sub-dialog in the station editor, quality tier constants, a global preferred-quality setting, and updated import flows (AudioAddict multi-quality, Radio-Browser attach-to-existing).

Phase 28 handles the actual failover/round-robin playback. This phase only needs to expose "get first/preferred stream URL" to satisfy `Player.play()`.

Every decision is locked in CONTEXT.md (D-01 through D-09). The only discretion areas are stream reorder UX and sub-dialog layout.

**Primary recommendation:** Use a single `db_init()` extension block to create `station_streams` and migrate data, then drop `stations.url` via table recreation. Use Up/Down buttons for stream reordering — simpler than GTK4 drag-and-drop (no `Gtk.DragSource`/`Gtk.DropTarget` ceremony) and consistent with the existing button-heavy dialog style.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** New normalized `station_streams` table with columns: `id`, `station_id` (FK), `url`, `label` (free text), `quality` (tier), `position` (integer for ordering), `stream_type` (hint: shoutcast/youtube/hls), `codec` (MP3/AAC/OPUS/FLAC/etc)
- **D-02:** Migrate existing `stations.url` column data into `station_streams` (one row per existing station at position 1). Remove `stations.url` column after migration. Single source of truth in `station_streams`.
- **D-03:** "Manage Streams" button in the station editor opens a separate sub-dialog for adding/editing/removing/reordering streams
- **D-05:** Quality tiers use fixed presets (hi/med/low) plus a custom text option
- **D-06:** Global "preferred quality" setting (key: `preferred_quality`) in addition to position-based ordering
- **D-07:** AudioAddict import creates one station per channel with all quality variants (hi/med/low) as separate streams
- **D-08:** Radio-Browser Discovery saves a single stream per action — "Add as new station" OR "Add stream to existing station"
- **D-09:** Radio-Browser attach-to-existing: auto-detect by similar name/provider, manual override, default to new station when no match

### Claude's Discretion

- **D-04:** Stream reorder UX — up/down buttons vs drag-and-drop (recommendation: up/down buttons)
- Exact sub-dialog layout for stream management

### Deferred Ideas (OUT OF SCOPE)

None
</user_constraints>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 (stdlib) | 3.x | Schema migration, stream CRUD | Already in use; no ORM introduced |
| gi / GTK4 | 4.x | Sub-dialog, list editing UI | Project stack |
| gi / Libadwaita | 1.x | `Adw.Window`, `Adw.ActionRow` | Project stack |

No new dependencies needed. [VERIFIED: codebase grep — all existing UI uses GTK4 + Adw]

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses (stdlib) | 3.x | `StationStream` model | Consistent with existing `Station`, `Provider`, `Favorite` pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Up/Down reorder buttons | `Gtk.DragSource` / `Gtk.DropTarget` drag-and-drop | GTK4 DnD is verbose, requires gesture setup and drop target registration; up/down buttons are 10 lines vs ~60 and fit the existing dialog style |
| Table recreation for DROP COLUMN | `ALTER TABLE stations RENAME TO`, new table, INSERT SELECT, DROP old | SQLite didn't support DROP COLUMN until 3.35.0 (2021); recreation is the safe, idempotent approach matching existing try/except migration pattern |

---

## Architecture Patterns

### Data Model

New `StationStream` dataclass in `models.py`:

```python
# [ASSUMED] — standard dataclass pattern matching existing models
@dataclass
class StationStream:
    id: int
    station_id: int
    url: str
    label: str           # free text, e.g. "High Quality", "Mobile"
    quality: str         # "hi" | "med" | "low" | custom string
    position: int        # 1-based ordering
    stream_type: str     # "shoutcast" | "youtube" | "hls" | ""
    codec: str           # "MP3" | "AAC" | "OPUS" | "FLAC" | ""
```

Update `Station` dataclass: remove `url: str` field, add `streams: list[StationStream] = field(default_factory=list)`.

### Schema Migration Pattern

Extend `db_init()` following the existing try/except idiom [VERIFIED: repo.py lines 54–73]:

```python
# 1. Create station_streams table (idempotent)
con.execute("""
    CREATE TABLE IF NOT EXISTS station_streams (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        station_id  INTEGER NOT NULL,
        url         TEXT NOT NULL,
        label       TEXT NOT NULL DEFAULT '',
        quality     TEXT NOT NULL DEFAULT '',
        position    INTEGER NOT NULL DEFAULT 1,
        stream_type TEXT NOT NULL DEFAULT '',
        codec       TEXT NOT NULL DEFAULT '',
        FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
    )
""")
con.commit()

# 2. Migrate existing stations.url -> station_streams (idempotent guard)
try:
    # Only migrate if stations still has a url column
    con.execute("SELECT url FROM stations LIMIT 1")
    con.execute("""
        INSERT INTO station_streams (station_id, url, position)
        SELECT id, url, 1 FROM stations WHERE url != '' AND url IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM station_streams ss WHERE ss.station_id = stations.id)
    """)
    con.commit()
    # Recreate stations table without url column
    con.executescript("""
        BEGIN;
        CREATE TABLE stations_new (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT NOT NULL,
            provider_id         INTEGER,
            tags                TEXT DEFAULT '',
            station_art_path    TEXT,
            album_fallback_path TEXT,
            icy_disabled        INTEGER NOT NULL DEFAULT 0,
            last_played_at      TEXT,
            created_at          TEXT DEFAULT (datetime('now')),
            updated_at          TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE SET NULL
        );
        INSERT INTO stations_new SELECT id, name, provider_id, tags,
            station_art_path, album_fallback_path, icy_disabled, last_played_at,
            created_at, updated_at FROM stations;
        DROP TABLE stations;
        ALTER TABLE stations_new RENAME TO stations;
        COMMIT;
    """)
except sqlite3.OperationalError:
    pass  # url column already gone — migration already ran
```

Note: the existing `stations_updated_at` trigger must be recreated after table recreation. [VERIFIED: repo.py line 36-40]

### Repo Pattern — Stream CRUD

New methods on `Repo` following existing style [VERIFIED: repo.py patterns]:

```python
def list_streams(self, station_id: int) -> list[StationStream]: ...
def insert_stream(self, station_id: int, url: str, label: str, quality: str,
                  position: int, stream_type: str, codec: str) -> int: ...
def update_stream(self, stream_id: int, url: str, label: str, quality: str,
                  position: int, stream_type: str, codec: str): ...
def delete_stream(self, stream_id: int): ...
def reorder_streams(self, station_id: int, ordered_ids: list[int]): ...
def get_preferred_stream_url(self, station_id: int, preferred_quality: str = "") -> str: ...
def station_exists_by_url(self, url: str) -> bool: ...  # update to query station_streams
```

`get_preferred_stream_url`: if `preferred_quality` is set and a matching stream exists, return that URL; otherwise return the stream at position=1. This is what Phase 28 builds on.

`insert_station` must also create a stream row when a URL is provided. `update_station` URL routing goes to stream table.

### Station Editor — "Manage Streams" Sub-Dialog

Add a `Gtk.Button(label="Manage Streams…")` to `EditStationDialog.__init__` form grid (row 2, after URL, or below URL as its own row). The URL entry row can remain for backward compat during the transition or can be removed — but per D-02, URL is removed from stations table, so the url_entry must be removed from the editor and replaced by the Manage Streams button.

The `ManageStreamsDialog` (new `Adw.Window` subclass) opens as a transient child of `EditStationDialog`:

```
ManageStreamsDialog layout:
  HeaderBar: title="Streams", Close button
  Body (vertical box):
    Gtk.ListBox (stream rows)
      per-row: Adw.ActionRow
        title = label or url (truncated)
        subtitle = quality badge + codec
        suffix: Up button | Down button | Delete button
    "Add Stream" button (+ expander or sub-form below list)
  Add/Edit form (inline at bottom or popover):
    URL entry
    Label entry
    Quality dropdown (hi / med / low / custom)
    Custom quality entry (visible when "custom" selected)
    Stream type dropdown (shoutcast / youtube / hls / blank)
    Codec entry (free text with placeholder "MP3, AAC…")
    Save / Cancel buttons
```

Up/Down reorder: swap `position` values between adjacent rows, refresh listbox. [ASSUMED] — GTK4 ListBox has no built-in reorder; position column handles persistence.

### Quality Tier Constants

Define in a new `musicstreamer/constants.py` addition (or as a module-level tuple in models.py):

```python
QUALITY_PRESETS = ("hi", "med", "low")
QUALITY_SETTING_KEY = "preferred_quality"
```

Global setting stored as `repo.get_setting("preferred_quality", "")`. Empty string = position-based fallback.

### Anti-Patterns to Avoid

- **Don't query `stations.url` after migration:** All callsites must switch to `station_streams`. Three files contain `station.url` references: `player.py`, `discovery_dialog.py`, `edit_dialog.py`. [VERIFIED: codebase — player.py line 68, edit_dialog.py line 202 (url_entry), discovery_dialog.py line 315]
- **Don't leave `station_exists_by_url` pointing at `stations.url`:** It must query `station_streams.url` after migration or dedup will silently break. [VERIFIED: repo.py line 267]
- **Don't skip trigger recreation:** SQLite `DROP TABLE` removes all triggers on that table. The `stations_updated_at` trigger must be re-added after table recreation.
- **Don't call `insert_station` without creating a stream row:** Any code that calls `insert_station(name, url, ...)` must also insert a stream. Easiest: `insert_station` internally calls `insert_stream` when url is non-empty.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Fuzzy name matching for RB attach-to-existing | Custom string distance algorithm | Simple case-insensitive substring match on station name; if zero matches, show manual picker |
| Stream reorder persistence | Custom position recalculator | Single `UPDATE station_streams SET position=? WHERE id=?` per row after swap |
| Quality tier UI | Custom widget | `Gtk.DropDown` with `Gtk.StringList` + a conditional `Gtk.Entry` for custom text |

---

## Common Pitfalls

### Pitfall 1: SQLite DROP COLUMN Version Compatibility
**What goes wrong:** `ALTER TABLE stations DROP COLUMN url` works only on SQLite >= 3.35.0 (2021). Older systems (Raspberry Pi OS, Ubuntu 20.04) will fail silently or crash.
**Why it happens:** SQLite version is OS-dependent, not project-controlled.
**How to avoid:** Use table recreation approach (rename → new table → INSERT SELECT → drop old → rename new). This is what the migration pattern above does.
**Warning signs:** `sqlite3.OperationalError: near "DROP"` in logs.

### Pitfall 2: Trigger Loss After Table Recreation
**What goes wrong:** `stations_updated_at` trigger disappears when the old `stations` table is dropped.
**Why it happens:** Triggers are attached to tables; dropping the table drops the trigger.
**How to avoid:** Re-issue `CREATE TRIGGER IF NOT EXISTS stations_updated_at` after table recreation in the same migration block.

### Pitfall 3: station_exists_by_url Still Points at stations.url
**What goes wrong:** Import dedup silently fails — every URL appears new because the column being checked no longer exists (OperationalError) or returns 0 rows.
**Why it happens:** Three import callsites use `repo.station_exists_by_url()`. Easy to forget to update the underlying query.
**How to avoid:** Update `station_exists_by_url` to `SELECT 1 FROM station_streams WHERE url = ?` as part of the repo migration step.

### Pitfall 4: AudioAddict PLS Resolution Produces One URL Per Quality
**What goes wrong:** The existing `_resolve_pls()` returns only `File1=`. For multi-quality import, each quality tier needs its own PLS resolved separately.
**Why it happens:** Current `fetch_channels()` only calls for one tier. Multi-quality requires three separate PLS fetches per channel.
**How to avoid:** In the updated AA import, call `_resolve_pls()` for each of the three PLS URLs (hi/med/low) per channel dict, then insert all three streams.

### Pitfall 5: Player.play() Receives a Station With No .url
**What goes wrong:** After removing `Station.url`, `player.py` line 68 (`url = (station.url or "").strip()`) raises `AttributeError`.
**Why it happens:** Player is called from main_window before streams are loaded onto the Station object.
**How to avoid:** Add a `get_preferred_stream_url(station_id, preferred_quality)` repo method. Call it in `Player.play()` (passing `repo` or resolving before call) to get the URL. Alternatively, load `station.streams` eagerly in `list_stations()` and have `Player.play()` resolve from the list. The simplest: `station.streams[0].url` after sorting by position.

### Pitfall 6: Migration Runs Twice (Not Idempotent)
**What goes wrong:** If `db_init()` is called on a DB that already had the migration run, a second attempt to INSERT old URLs into `station_streams` duplicates data.
**Why it happens:** The outer try/except catches `OperationalError` on `SELECT url FROM stations` — but if the column is already gone, the except fires correctly. The guard `NOT EXISTS` in the INSERT prevents duplicate rows even on partial runs.
**How to avoid:** The `NOT EXISTS` guard in the INSERT plus the try/except on `SELECT url FROM stations LIMIT 1` makes it fully idempotent.

---

## Code Examples

### list_stations() With Streams Eager-Loaded

```python
# [ASSUMED] — pattern consistent with existing Repo methods
def list_stations(self) -> list[Station]:
    rows = self.con.execute("""
        SELECT s.*, p.name AS provider_name
        FROM stations s
        LEFT JOIN providers p ON p.id = s.provider_id
        ORDER BY COALESCE(p.name,''), s.name
    """).fetchall()
    stations = []
    for r in rows:
        stream_rows = self.con.execute(
            "SELECT * FROM station_streams WHERE station_id=? ORDER BY position",
            (r["id"],)
        ).fetchall()
        streams = [StationStream(...) for sr in stream_rows]
        stations.append(Station(id=r["id"], ..., streams=streams))
    return stations
```

### Player.play() URL Resolution

```python
# [ASSUMED] — minimal change to player.py
def play(self, station: Station, on_title: callable):
    self._on_title = on_title
    url = ""
    if station.streams:
        url = station.streams[0].url  # position-sorted, phase 28 adds quality logic
    url = url.strip()
    if not url:
        on_title("(no streams configured)")
        return
    ...
```

### AudioAddict Multi-Quality Import

```python
# [ASSUMED] — based on existing fetch_channels() and QUALITY_TIERS
QUALITY_TIERS = {"hi": "premium_high", "med": "premium", "low": "premium_medium"}

def fetch_channels_multi(listen_key: str) -> list[dict]:
    """Returns list of {title, provider, image_url, streams: [{url, quality}]}"""
    results = []
    for net in NETWORKS:
        # fetch all three quality tiers per channel
        streams_by_key = {}
        for quality, tier in QUALITY_TIERS.items():
            url = f"https://{net['domain']}/{tier}?listen_key={listen_key}"
            try:
                data = json.loads(urllib.request.urlopen(url, timeout=15).read())
            except ...:
                continue
            for ch in data:
                pls_url = f"https://{net['domain']}/{tier}/{ch['key']}.pls?listen_key={listen_key}"
                stream_url = _resolve_pls(pls_url)
                if ch["key"] not in streams_by_key:
                    streams_by_key[ch["key"]] = {"title": ch["name"], "streams": [], ...}
                streams_by_key[ch["key"]]["streams"].append(
                    {"url": stream_url, "quality": quality, "position": {"hi":1,"med":2,"low":3}[quality]}
                )
        results.extend(streams_by_key.values())
    return results
```

### Radio-Browser Attach-to-Existing (D-08/D-09)

The discovery dialog `_on_save_clicked` needs a two-option dialog:

```python
# [ASSUMED] — Adw.MessageDialog with custom responses
dlg = Adw.MessageDialog(transient_for=self, heading="Save Station Stream",
    body=f'Add "{name}" as a new station, or attach to an existing one?')
dlg.add_response("new", "New Station")
dlg.add_response("attach", "Attach to Existing…")
dlg.set_default_response("new")
```

If "Attach to Existing…": show a second dialog (or popover) listing `repo.list_stations()` for the user to pick from. Auto-detect: pre-select the station whose name most closely matches (case-insensitive substring check on `station.name`).

---

## Callsite Inventory (All Must Be Updated)

| File | Line(s) | Change Required |
|------|---------|----------------|
| `models.py` | Station.url | Remove; add `streams: list[StationStream]` |
| `repo.py` | `db_init()` | Add table, migration, trigger recreation |
| `repo.py` | `list_stations()`, `get_station()`, `list_recently_played()` | Remove url from SELECT/construct; load streams |
| `repo.py` | `create_station()` | No url insert |
| `repo.py` | `update_station()` | Remove url param; route url changes to stream table |
| `repo.py` | `insert_station()` | After INSERT, call `insert_stream()` with url |
| `repo.py` | `station_exists_by_url()` | Query `station_streams` |
| `player.py` | `play()` line 68 | Resolve URL from `station.streams` |
| `ui/edit_dialog.py` | url_entry, _save() | Remove url_entry; add Manage Streams button |
| `ui/edit_dialog.py` | `_on_url_focus_out`, `_on_fetch_clicked` | Move URL-based logic to ManageStreamsDialog |
| `ui/discovery_dialog.py` | `_on_save_clicked` | Add "New vs. Attach" dialog (D-08) |
| `aa_import.py` | `fetch_channels()`, `import_stations()` | Multi-quality streams per channel (D-07) |
| `yt_import.py` | `import_stations()` | Single stream insert via new `insert_stream()` |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (nyquist_validation enabled) |
| Config file | none detected — Wave 0 gap |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STR-01 | `station_streams` table created by `db_init()` | unit | `pytest tests/test_repo.py::test_station_streams_schema -x` | ❌ Wave 0 |
| STR-02 | Migration moves `stations.url` to `station_streams` position=1 | unit | `pytest tests/test_repo.py::test_migration_url_to_streams -x` | ❌ Wave 0 |
| STR-03 | `stations.url` removed post-migration | unit | `pytest tests/test_repo.py::test_stations_has_no_url_column -x` | ❌ Wave 0 |
| STR-04 | `station_exists_by_url` queries station_streams | unit | `pytest tests/test_repo.py::test_exists_by_url_uses_streams -x` | ❌ Wave 0 |
| STR-05 | `insert_station` creates stream row when url provided | unit | `pytest tests/test_repo.py::test_insert_station_creates_stream -x` | ❌ Wave 0 |
| STR-06 | AA import creates hi/med/low streams per channel | unit | `pytest tests/test_aa_import.py::test_multi_quality_streams -x` | ❌ Wave 0 |
| STR-07 | `get_preferred_stream_url` returns position=1 when no quality pref | unit | `pytest tests/test_repo.py::test_preferred_stream_no_pref -x` | ❌ Wave 0 |
| STR-08 | `get_preferred_stream_url` returns quality-matched url when pref set | unit | `pytest tests/test_repo.py::test_preferred_stream_with_pref -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_repo.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_repo.py` — covers STR-01 through STR-05, STR-07, STR-08
- [ ] `tests/test_aa_import.py` — covers STR-06
- [ ] `tests/conftest.py` — shared in-memory SQLite fixture
- [ ] Framework install: `pip install pytest` if not present

---

## Environment Availability

Step 2.6: SKIPPED — this phase is code/config changes only; no new external tools required beyond existing GTK4/GStreamer/SQLite stack.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Up/Down buttons are simpler than drag-and-drop for stream reordering | Architecture Patterns | Low — DnD can be added later if needed |
| A2 | `StationStream` dataclass field names as specified | Standard Stack | Low — naming is internal |
| A3 | ManageStreamsDialog inline add/edit form layout | Architecture Patterns | Low — layout is Claude's discretion per D-04 |
| A4 | AA multi-quality fetch requires three separate API calls per network | Code Examples | Medium — if AA returns all qualities in one call, implementation simplifies |
| A5 | `_resolve_pls()` must be called per quality tier | Common Pitfalls | Medium — if PLS for one tier contains all streams, a single call might suffice |

---

## Open Questions

1. **Does AA API return all quality tier URLs in one channel object, or only one at a time?**
   - What we know: Current `fetch_channels()` passes one tier to the API URL, gets that tier's channels back. The PLS URL is constructed from the tier slug.
   - What's unclear: Whether the channel API response includes URLs for other tiers directly.
   - Recommendation: Implement three separate fetches (safe); optimize after confirming API shape.

2. **Should `list_stations()` eager-load streams, or should streams be loaded on-demand?**
   - What we know: Station list is used in filtering UI, recently-played, and station rows. Streams are only needed at play time.
   - What's unclear: Volume of stations (tens to hundreds for typical user).
   - Recommendation: Eager-load in `list_stations()` for simplicity — N+1 at tens of stations is negligible. Phase 28 can optimize if needed.

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: codebase] `musicstreamer/repo.py` — existing schema, migration pattern, CRUD methods
- [VERIFIED: codebase] `musicstreamer/models.py` — dataclass patterns
- [VERIFIED: codebase] `musicstreamer/player.py` — `play()` method URL resolution
- [VERIFIED: codebase] `musicstreamer/aa_import.py` — import flow, QUALITY_TIERS, PLS resolution
- [VERIFIED: codebase] `musicstreamer/ui/edit_dialog.py` — dialog layout, url_entry callsite
- [VERIFIED: codebase] `musicstreamer/ui/discovery_dialog.py` — save flow, station_exists_by_url usage

### Tertiary (LOW confidence)
- [ASSUMED] GTK4 `Adw.MessageDialog` multi-response pattern for "New vs. Attach" — consistent with existing `_on_delete_clicked` pattern in edit_dialog.py

---

## Metadata

**Confidence breakdown:**
- Schema design: HIGH — directly derived from codebase + locked decisions
- Migration strategy: HIGH — SQLite DROP COLUMN limitation is well-known; table recreation is documented pattern
- UI patterns: MEDIUM — GTK4/Adw patterns assumed from existing codebase style
- AA multi-quality: MEDIUM — API shape confirmed by existing code; three-call approach assumed

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable stack)
