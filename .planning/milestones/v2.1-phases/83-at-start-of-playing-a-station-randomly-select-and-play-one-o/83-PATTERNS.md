# Phase 83: SomaFM Station Prerolls — Pattern Map

**Mapped:** 2026-05-22
**Files analyzed:** 8 (5 source modified, 3 tests appended)
**Analogs found:** 8 / 8

> **IMPORTANT routing note:** The CONTEXT.md `<canonical_refs>` section once referred to `musicstreamer/migration.py`. That file exists but is the **platformdirs first-launch helper** — it does NOT hold DDL. All schema migrations (CREATE TABLE / ALTER TABLE) live in **`musicstreamer/repo.py` `db_init()` (lines 88–282)**. Phase 83 schema additions land there, NOT in `migration.py`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/repo.py` (mod — schema `db_init` block) | migration | DDL transform | `musicstreamer/repo.py:269–282` (Phase 82 `preferred_stream_id` ALTER block) + `repo.py:124–137` (`station_streams` CREATE) | exact |
| `musicstreamer/repo.py` (mod — Repo methods + Station-builders) | repository | CRUD | `repo.py:351–371` (`list_streams` / `insert_stream`) + `repo.py:574–580` (`set_preferred_stream`) + 4 Station-builder sites (lines 450, 487, 582, 697) | exact |
| `musicstreamer/models.py` (mod — `Station` field) | model | dataclass | `models.py:37,40` (`streams: List[StationStream]` and `preferred_stream_id: Optional[int]`) | exact |
| `musicstreamer/soma_import.py` (mod — `fetch_channels` + `import_stations`) | service | request-response + transform | `soma_import.py:234–242` (channel dict assembly) + `soma_import.py:273–364` (per-channel try/except with rollback sentinel) | exact |
| `musicstreamer/player.py` (mod — `Player.play` preroll cluster + about-to-finish handler + tag suppression + backfill worker) | controller | event-driven + streaming | `player.py:259–263, 404–406` (queued Signal pattern) + `player.py:505–547` (Phase 82 `Player.play` queue-build block) + `player.py:713–722` (`_on_gst_tag` choke-point) + `player.py:1047–1051` (`threading.Thread(daemon=True)` worker) + `soma_import.py:398–402` (thread-local `Repo(db_connect())`) | exact |
| `tests/test_repo.py` (appended) | test | unit | `tests/test_repo.py:875–922` (Phase 82 migration tests) + `tests/test_repo.py:461–612` (stream CRUD + CASCADE tests) | exact |
| `tests/test_soma_import.py` (appended) | test | unit | `tests/test_soma_import.py:123–146` (`fetch_channels` shape test) + `tests/test_soma_import.py:284–314` (`import_stations` repo-call test) | exact |
| `tests/test_player.py` (appended) | test | behavioral + source-grep | `tests/test_player.py:589–765` (Phase 82 `_make_player_mock` helper + behavioral suite + drift-guard) | exact |

## Pattern Assignments

---

### `musicstreamer/repo.py` — schema additions in `db_init()` (migration, DDL transform)

**Analog:** `musicstreamer/repo.py:124–137` (CREATE for `station_streams`) and `musicstreamer/repo.py:269–282` (Phase 82 `preferred_stream_id` ALTER block).

**CREATE TABLE pattern with CASCADE FK** (`repo.py:124–137`, inside the `db_init` `executescript`):

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
    bitrate_kbps INTEGER NOT NULL DEFAULT 0,
    sample_rate_hz INTEGER NOT NULL DEFAULT 0,
    bit_depth INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
);
```

> Phase 83 `station_prerolls` mirrors this shape exactly. Place it **inside** the `executescript` block (lines 89–148), not in the try/except ALTER section below — fresh DBs need it created in the same script as `stations`.

**Idempotent additive-column pattern** (`repo.py:269–282`, Phase 82):

```python
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

> Copy this block verbatim, changing the column to `prerolls_fetched_at INTEGER` (nullable, no DEFAULT, no FK). It MUST land AFTER the stations_new rebuild block (`repo.py:251`) for the same Pitfall 2 reason called out in the Phase 82 comment.

---

### `musicstreamer/repo.py` — new Repo methods (repository, CRUD)

**Analog for `insert_preroll` / `list_prerolls`:** `musicstreamer/repo.py:351–371` (`list_streams` / `insert_stream`).

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

def insert_stream(self, station_id: int, url: str, label: str = "",
                  quality: str = "", position: int = 1,
                  stream_type: str = "", codec: str = "",
                  bitrate_kbps: int = 0,
                  sample_rate_hz: int = 0, bit_depth: int = 0) -> int:
    cur = self.con.execute(
        "INSERT INTO station_streams(station_id,url,label,...,bit_depth) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (station_id, url, label, quality, position, stream_type, codec, bitrate_kbps,
         sample_rate_hz, bit_depth))
    self.con.commit()
    return int(cur.lastrowid)
```

> Phase 83 returns **`list[str]`** of URLs (not a `Preroll` dataclass — the player only needs URLs per RESEARCH Operation 2). `ORDER BY position` is load-bearing.

**Analog for `set_prerolls_fetched_at`:** `musicstreamer/repo.py:574–580` (Phase 82 `set_preferred_stream`).

```python
def set_preferred_stream(self, station_id: int, stream_id: Optional[int]) -> None:
    """Phase 82 D-02: persist the user's stream pick. None clears the pick."""
    self.con.execute(
        "UPDATE stations SET preferred_stream_id = ? WHERE id = ?",
        (stream_id, station_id),
    )
    self.con.commit()
```

> Phase 83 mirrors this exactly; UPDATE column is `prerolls_fetched_at`, value is `epoch_seconds: int`. Same single-line `self.con.execute(...)` + `self.con.commit()` shape.

**Station-builder eager-load pattern** — 4 sites must be updated identically. Reference: `musicstreamer/repo.py:450–478` (`list_stations`):

```python
def list_stations(self) -> List[Station]:
    rows = self.con.execute(
        """
        SELECT s.*, p.name AS provider_name
        FROM stations s
        LEFT JOIN providers p ON p.id = s.provider_id
        ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE
        """
    ).fetchall()
    out = []
    for r in rows:
        out.append(
            Station(
                ...
                preferred_stream_id=r["preferred_stream_id"],
                streams=self.list_streams(r["id"]),   # <-- eager sub-query per row
            )
        )
    return out
```

> Phase 83 adds **two** extra Station kwargs on every builder: `prerolls=self.list_prerolls(r["id"])` and `prerolls_fetched_at=r["prerolls_fetched_at"]`. The 4 builder sites are:
> - `repo.py:450` `list_stations`
> - `repo.py:487` `get_station`
> - `repo.py:582` `list_recently_played`
> - `repo.py:697` `list_favorite_stations`

---

### `musicstreamer/models.py` — `Station` dataclass extension (model, dataclass)

**Analog:** `musicstreamer/models.py:37,40` — existing `streams` field and Phase 82's `preferred_stream_id` field.

```python
@dataclass
class Station:
    id: int
    name: str
    ...
    cover_art_source: Literal["auto", "itunes_only", "mb_only"] = "auto"  # Phase 73 D-01/D-05
    streams: List[StationStream] = field(default_factory=list)
    last_played_at: Optional[str] = None
    is_favorite: bool = False
    preferred_stream_id: Optional[int] = None  # Phase 82 D-01: per-station sticky preferred stream
```

> Phase 83 appends two fields at the bottom in the same shape:
> ```python
> prerolls: list[str] = field(default_factory=list)              # Phase 83 D-01/D-03
> prerolls_fetched_at: Optional[int] = None                      # Phase 83 D-04
> ```
> `prerolls` mirrors `streams` (mutable default → `field(default_factory=list)`); `prerolls_fetched_at` mirrors `preferred_stream_id` (nullable int).

---

### `musicstreamer/soma_import.py` — `fetch_channels` + `import_stations` extensions (service, request-response + transform)

**Analog for `fetch_channels` extension:** `musicstreamer/soma_import.py:234–242` (channel dict assembly inside the per-channel try block).

```python
out.append({
    "id": ch["id"],
    "title": ch["title"],
    "description": ch.get("description", ""),
    # Use "image" (120 px) to match AA logo dimensionality
    # (RESEARCH "Alternatives Considered" — NOT "xlimage" / 512 px)
    "image_url": ch.get("image"),
    "streams": streams,
})
```

> Phase 83 adds **one new key** at the bottom: `"preroll_urls": ch.get("preroll", [])`. Empty list when the channel has no preroll. Per RESEARCH Pitfall 7, URLs are stored verbatim — do NOT decode `%20`.

**Analog for `import_stations` extension:** `musicstreamer/soma_import.py:273–364` (the full per-channel try/except + rollback-sentinel block).

```python
inserted_station_id: int | None = None
try:
    if not ch.get("streams"):
        skipped += 1
        ...
    else:
        any_exists = any(...)
        if any_exists:
            skipped += 1
        else:
            first_url = ch["streams"][0]["url"]
            # D-02: provider_name literal is "SomaFM" (CamelCase, no space, no period)
            inserted_station_id = repo.insert_station(
                name=ch["title"],
                url=first_url,
                provider_name="SomaFM",
                tags="",
            )
            station_id = inserted_station_id
            # ...insert all streams via repo.insert_stream / repo.update_stream...
            imported += 1
            # All streams inserted — clear the rollback sentinel so a
            # later unrelated exception (e.g. inside on_progress) does
            # NOT erase a freshly-imported channel.
            inserted_station_id = None
            if ch.get("image_url"):
                logo_targets.append((station_id, ch["image_url"]))
except Exception as exc:  # noqa: BLE001
    if inserted_station_id is not None:
        try:
            repo.delete_station(inserted_station_id)
        except Exception as rollback_exc:
            _log.warning(...)
    _log.warning("SomaFM channel %r (%s) import skipped: %s", ...)
    skipped += 1
```

> Phase 83 inserts two new lines **inside the `else` branch, BEFORE the `inserted_station_id = None` sentinel clear at line 339** (per RESEARCH Pitfall 4 — keeps both writes inside the rollback window):
> ```python
> for pos, preroll_url in enumerate(ch.get("preroll_urls", []), start=1):
>     repo.insert_preroll(station_id, preroll_url, pos)
> # D-04: mark fetched even if preroll_urls was empty.
> repo.set_prerolls_fetched_at(station_id, int(time.time()))
> # All streams + prerolls inserted — clear the rollback sentinel.
> inserted_station_id = None
> ```
> `import time` must be present at module scope (currently absent — verify and add if needed; Phase 74 patterns already use `urllib`/`json`/`os`/`tempfile`).

---

### `musicstreamer/player.py` — preroll cluster (controller, event-driven + streaming)

This file gets the most surgery. Analog excerpts grouped by what they're for:

#### Imports pattern (player.py top of file)

`player.py:1–60` already imports `threading`, `time`, `random` is NOT yet imported (verify with grep). Phase 83 needs `import random` and `import time` (likely already there) plus a Python `set[int]` type hint.

#### Class-level queued Signal pattern (`player.py:259–263, 404–406`)

```python
# Worker threads (twitch/youtube resolve) have no Qt event loop, so
# QTimer.singleShot(0, ...) from those threads posts to a nonexistent loop
# and the callback never runs. Queued signal marshals _try_next_stream
# onto the main thread -- same pattern as _cancel_timers_requested.
_try_next_stream_requested = Signal()        # worker → main: advance failover queue
```

```python
# 999.8 WR-03: queue worker-thread → main failover advance.
self._try_next_stream_requested.connect(
    self._try_next_stream, Qt.ConnectionType.QueuedConnection
)
```

> Phase 83 adds a sibling **class-level** Signal (must NOT be instance-level per Pitfall 4 comment at line 240): `_preroll_about_to_finish_requested = Signal()`. Wire with `QueuedConnection` inside `__init__` directly under the existing `_try_next_stream_requested.connect(...)` call at lines 404–406.

#### Per-Player instance fields (Phase 82 idiom)

Phase 82 added `preferred_stream_id` handling to `Player.play`; Phase 83 adds three fresh instance fields. They go in `__init__` alongside existing per-Player state (`self._failover_timer`, `self._elapsed_seconds`, etc.). New fields per RESEARCH:

```python
# Phase 83 per-Player preroll state (D-12 / D-13 / D-07)
self._preroll_in_flight: bool = False
self._last_preroll_played_at: float | None = None
self._preroll_handler_id: int = 0
self._backfill_in_flight: set[int] = set()    # D-13 single-flight guard
```

#### `Player.play` queue-build block — preroll gate alongside (not inside) the queue (`player.py:505–547`)

```python
def play(self, station: Station, on_title=None, preferred_quality: str = "",
         on_failover=None, on_offline=None) -> None:
    # Cancel any in-progress failover from previous play
    self._cancel_timers()
    self._streams_queue = []
    self._recovery_in_flight = False
    ...
    if not station.streams:
        self.title_changed.emit("(no streams configured)")
        return

    # Phase 82 D-01/D-03: honor per-station sticky preferred stream.
    streams_by_position = order_streams(station.streams)
    preferred_by_id = None
    preferred_stream_id = getattr(station, "preferred_stream_id", None)
    if preferred_stream_id is not None:
        preferred_by_id = next(
            (s for s in station.streams if s.id == preferred_stream_id), None
        )
    ...
    if preferred:
        queue = [preferred] + [s for s in streams_by_position if s is not preferred]
    else:
        queue = list(streams_by_position)

    self._streams_queue = queue
    self._try_next_stream()
```

> Phase 83 logic sits **between** the queue build and the `self._try_next_stream()` call. Per D-06, `_streams_queue` is NOT mutated. Per RESEARCH Pitfall 5, guard `random.choice` on a non-empty list. Per D-11, gate uses the literal `"SomaFM"` (this is the drift-guard pin). Per D-12, timestamp is `time.monotonic()` and is updated at preroll START, not handoff. The new block:
> ```python
> self._streams_queue = queue
> # Phase 83 D-11/D-12/D-13: SomaFM preroll gate.
> if (
>     station.provider_name == "SomaFM"
>     and (self._last_preroll_played_at is None
>          or time.monotonic() - self._last_preroll_played_at > 600)
> ):
>     urls = list(station.prerolls or [])
>     if urls:
>         preroll_url = random.choice(urls)
>         self._start_preroll(preroll_url, station)
>         return  # _start_preroll handles _set_uri + handler connect
>     elif (
>         getattr(station, "prerolls_fetched_at", None) is None
>         and station.id not in self._backfill_in_flight
>     ):
>         # D-13: kick lazy backfill, do NOT block
>         self._backfill_in_flight.add(station.id)
>         threading.Thread(
>             target=self._preroll_backfill_worker,
>             args=(station.id, station.name),
>             daemon=True,
>         ).start()
> self._try_next_stream()
> ```

#### Bus-handler choke-point pattern (`player.py:713–722`)

```python
def _on_gst_tag(self, bus, msg) -> None:
    taglist = msg.parse_tag()
    found, value = taglist.get_string(Gst.TAG_TITLE)
    # Audio arrived -- cancel failover timer on the main thread via queued
    # signal. Bus-loop thread has no Qt event loop, so singleShot vanishes.
    self._cancel_timers_requested.emit()
    if not found:
        return
    title = _fix_icy_encoding(value)
    self.title_changed.emit(title)  # auto-queued cross-thread to main
```

> Phase 83 D-07 adds a **single early-return** between the `if not found: return` and the `_fix_icy_encoding(value)` line:
> ```python
> if self._preroll_in_flight:
>     return
> ```
> Read of a plain bool from the bus-loop thread is acceptable (atomic in CPython). Set/clear of the bool both happen on the main thread (`Player.play` sets, `_on_preroll_about_to_finish` clears).

#### One-shot GStreamer signal connect + queued-Signal slot pattern

`Player._pipeline.connect("about-to-finish", callback)` is new wiring in this codebase — the closest analog is the bus-handler wiring pattern at `player.py:333–337`:

```python
_bridge.run_sync(lambda: bus.add_signal_watch())  # D-07 literal
bus.connect("message::error", self._on_gst_error)  # async handler
bus.connect("message::tag",   self._on_gst_tag)    # async handler
```

> Phase 83 `_start_preroll`, `_on_preroll_about_to_finish_callback` (streaming-thread), and `_on_preroll_about_to_finish` (main-thread slot) — see RESEARCH Operation 1 for the verbatim shape. Critically: the **streaming-thread callback only emits the queued Signal**; the **main-thread slot does the `disconnect(handler_id)` + flag clear + `_try_next_stream()`** call.

#### Failover-aware error recovery (`player.py:682–704`)

```python
def _handle_gst_error_recovery(self) -> None:
    # Gap-05 fix: coalesce cascading bus errors for a single failing URL.
    if self._recovery_in_flight:
        return
    self._recovery_in_flight = True
    self._cancel_timers()
    if self._current_stream and "twitch.tv" in self._current_stream.url:
        if self._twitch_resolve_attempts < 1:
            self._twitch_resolve_attempts += 1
            self._play_twitch(self._current_stream.url)
            QTimer.singleShot(0, self._clear_recovery_guard)
            return
    self._try_next_stream()
    QTimer.singleShot(0, self._clear_recovery_guard)
```

> Phase 83 D-09 adds a guarded branch at the **top** of `_handle_gst_error_recovery` (after the `_recovery_in_flight` short-circuit, before the Twitch branch) — if `self._preroll_in_flight` is True, disconnect the preroll handler, clear the flag, then route via `self._try_next_stream()` directly. No retry of a different preroll. Excerpt:
> ```python
> if self._preroll_in_flight:
>     if self._preroll_handler_id:
>         try:
>             self._pipeline.disconnect(self._preroll_handler_id)
>         except (TypeError, RuntimeError):
>             pass
>         self._preroll_handler_id = 0
>     self._preroll_in_flight = False
>     self._try_next_stream()
>     QTimer.singleShot(0, self._clear_recovery_guard)
>     return
> ```

#### Daemon-thread worker pattern (`player.py:1047–1051` + `soma_import.py:398–402`)

YouTube/Twitch worker shape:

```python
threading.Thread(
    target=self._youtube_resolve_worker, args=(url,), daemon=True
).start()
```

Thread-local Repo write shape (`soma_import.py:398–402`):

```python
con = db_connect()
try:
    Repo(con).update_station_art(station_id, art_path)
finally:
    con.close()
```

> Phase 83 `_preroll_backfill_worker(self, station_id: int, station_name: str)` combines both: it calls `soma_import.fetch_channels()`, matches the channel by title (RESEARCH Pitfall 3 — option 1), opens its own `db_connect()`, inserts via `Repo(con).insert_preroll(...)` for each URL, calls `Repo(con).set_prerolls_fetched_at(station_id, int(time.time()))` regardless of count (D-04), and finally `self._backfill_in_flight.discard(station_id)` in a `finally` block so a retry can fire on a later play if the fetch raised. Verbatim shape in RESEARCH §"Pattern 4".

---

### `tests/test_repo.py` — appended tests (test, unit)

**Analog:** `tests/test_repo.py:874–971` (Phase 82 migration + setter round-trip suite) and `tests/test_repo.py:461–612` (stream CRUD + CASCADE delete).

**Schema column shape test** (lines 875–896):

```python
def test_preferred_stream_id_migration_idempotent(repo):
    """D-08: db_init is idempotent across multiple calls; column has expected schema."""
    db_init(repo.con)
    db_init(repo.con)

    cols = repo.con.execute("PRAGMA table_info('stations')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert "preferred_stream_id" in by_name
    col = by_name["preferred_stream_id"]
    assert col[2] == "INTEGER"
    assert col[3] == 0          # nullable
    assert col[4] is None       # no DEFAULT
```

> Mirror for Phase 83: assert `prerolls_fetched_at` column on `stations` is INTEGER, nullable, no DEFAULT; assert `station_prerolls` table exists with columns `{id, station_id, url, position}`; assert `db_init` is idempotent.

**Setter round-trip across all 4 Station-builders** (lines 937–971):

```python
def test_set_preferred_stream_round_trips_via_list_stations(repo):
    sid, yt_id, twitch_id = _seed_two_stream_station(repo)
    repo.set_preferred_stream(sid, twitch_id)
    stations = repo.list_stations()
    match = next(s for s in stations if s.id == sid)
    assert match.preferred_stream_id == twitch_id
```

> Mirror for Phase 83: `set_prerolls_fetched_at` round-trip via each of `list_stations` / `get_station` / `list_recently_played` / `list_favorite_stations`; AND eager-load round-trip for `prerolls: list[str]` (insert two prerolls → list_stations → assert station.prerolls == [...] in position order).

**CASCADE delete pattern** (lines 584–594):

```python
def test_cascade_delete(repo):
    """Deleting a station also deletes its station_streams rows."""
    sid = repo.insert_station("Test FM", "http://test.fm/stream", "", "")
    streams_before = repo.list_streams(sid)
    assert len(streams_before) == 1
    repo.delete_station(sid)
    rows = repo.con.execute(
        "SELECT * FROM station_streams WHERE station_id=?", (sid,)
    ).fetchall()
    assert len(rows) == 0
```

> Mirror for Phase 83 prerolls: insert prerolls → delete_station → SELECT FROM station_prerolls returns 0 rows. Critical for re-import flow (Phase 74) — RESEARCH Runtime State Inventory note.

---

### `tests/test_soma_import.py` — appended tests (test, unit)

**Analog for `fetch_channels` shape test:** `tests/test_soma_import.py:123–146`.

```python
def test_fetch_channels_parses_canonical_blob():
    fixture_bytes = _load_fixture("soma_channels_3ch.json")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    assert len(channels) == 3
    for ch in channels:
        assert "id" in ch
        ...
        assert "streams" in ch
```

> Mirror for Phase 83: extend the existing 3-channel fixture (or add a new one with a `"preroll": [...]` array on at least one channel) and assert `"preroll_urls" in ch` plus `ch["preroll_urls"] == [...]` shape.

**Analog for `import_stations` repo-call test:** `tests/test_soma_import.py:284–314`.

```python
def test_import_three_channels_full_path_creates_stations_and_streams():
    ...
    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.side_effect = [42, 43, 44]
    mock_repo.list_streams.side_effect = [
        [MagicMock(id=100)],  # groovesalad first stream
        ...
    ]

    inserted, skipped = soma_import.import_stations(channels, mock_repo)
    assert (inserted, skipped) == (3, 0)
    assert mock_repo.insert_station.call_count == 3
```

> Mirror for Phase 83 — same `MagicMock(spec=Repo)`-style repo stub; assert `mock_repo.insert_preroll.call_count == N` (where N is the number of preroll URLs across all channels); assert `mock_repo.set_prerolls_fetched_at.call_count == channels_imported` (called once per channel even for empty `preroll_urls` per D-04); assert CASCADE rollback: when a stream insert raises mid-channel, `insert_preroll` rows for THAT channel are dropped via `delete_station` (already exercised by RESEARCH Pitfall 4).

---

### `tests/test_player.py` — appended tests (test, behavioral + source-grep)

**Analog:** `tests/test_player.py:589–765` (Phase 82 entire `preferred_stream_id` block — `_make_player_mock` helper + `_make_stream_ph82` / `_make_station_ph82` factories + 7 behavioral tests + drift-guard).

**Player mock factory** (lines 589–602):

```python
def _make_player_mock(qtbot):
    """Create a Player with pipeline mocked (mirrors make_player in this file)."""
    from musicstreamer.player import Player
    from unittest.mock import MagicMock, patch
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    player._pipeline = MagicMock()
    return player
```

**Station/Stream factory pattern** (lines 605–630):

```python
def _make_station_ph82(streams, preferred_stream_id=None):
    from musicstreamer.models import Station
    return Station(
        id=1,
        name="Test Station",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=streams,
        preferred_stream_id=preferred_stream_id,
    )
```

> Phase 83 needs a parallel `_make_station_ph83(streams, *, provider_name=..., prerolls=..., prerolls_fetched_at=...)` factory. **Critical:** the SomaFM tests must set `provider_name="SomaFM"` (exact literal — the drift-guard pin); non-SomaFM bypass test must set `provider_name="Other"` or similar.

**Behavioral assertion pattern — assert on `_streams_queue` / `_current_stream` / `_set_uri` call args, NOT on `pipeline.emit`** (lines 633–647):

```python
def test_preferred_stream_id_minimal_red(qtbot):
    from unittest.mock import patch
    p = _make_player_mock(qtbot)
    s_hi = _make_stream_ph82(1, 1, "hi", "http://yt/")
    s_med = _make_stream_ph82(2, 2, "med", "http://twitch/")
    station = _make_station_ph82([s_hi, s_med], preferred_stream_id=2)
    with patch.object(p, "_set_uri"):
        p.play(station)
    assert p._current_stream.id == 2, (
        "Phase 82 D-03: preferred_stream_id=2 must place stream id=2 at queue "
        "head; got id=%d instead" % p._current_stream.id
    )
```

> Phase 83 mirrors this `with patch.object(p, "_set_uri"):` idiom for every behavioral test. Each Phase 83 behavioral test asserts on:
> - `p._set_uri.call_args[0][0]` == preroll URL (D-05 test 1) or stream URL (D-12 throttle test, non-SomaFM bypass test)
> - `p._preroll_in_flight` == True/False
> - `p._last_preroll_played_at is None` / `is not None`
> - `p._streams_queue` contents == station.streams (D-06 — queue unchanged)
> - `p._pipeline.connect.call_args == call("about-to-finish", ANY)` (D-05 test 1)
> - `threading.Thread.start` was/was-not called (D-13 backfill test; use `monkeypatch.setattr("musicstreamer.player.threading.Thread", MockThread)`)

**Source-grep drift-guard pattern** (lines 746–764):

```python
def test_preferred_stream_id_drift_guard():
    """Phase 82 D-03 drift-guard (Phase 51/55/61/63/81 precedent).

    Reads musicstreamer/player.py, filters non-comment lines, asserts the
    literal 'preferred_stream_id' appears at least once.
    """
    from pathlib import Path
    source = (
        Path(__file__).resolve().parent.parent / "musicstreamer" / "player.py"
    ).read_text()
    non_comments = "\n".join(
        ln for ln in source.splitlines() if not ln.lstrip().startswith("#")
    )
    assert "preferred_stream_id" in non_comments, (
        "Phase 82 D-03: preferred_stream_id lookup must exist in player.py "
        "(Player.play queue-build block). Do not remove silently."
    )
```

> Phase 83 mirrors this exactly. **Two literals must be pinned in non-comment text** (D-14 test 8):
> 1. `'"SomaFM"'` — the provider gate literal (D-11)
> 2. `'_last_preroll_played_at'` — the throttle-state token (D-12; per CONTEXT Claude's Discretion + RESEARCH §Pattern 3)
>
> The non-comment filter is **load-bearing** — without it, a comment-line `"SomaFM"` would satisfy the assert even if the actual gate code had been removed.

---

## Shared Patterns

### Queued cross-thread Signal (Pattern 1)
**Source:** `musicstreamer/player.py:251–263, 404–406` (Phase 43.1 fix `f1333ed`).
**Apply to:** `_preroll_about_to_finish_requested` Signal in Player. Streaming-thread `about-to-finish` callback emits the Signal; `__init__` wires it to a main-thread slot via `Qt.ConnectionType.QueuedConnection`.

```python
# Class-level Signal (NOT instance-level — Pitfall 4 comment at player.py:240)
_preroll_about_to_finish_requested = Signal()

# In __init__, alongside _try_next_stream_requested.connect(...):
self._preroll_about_to_finish_requested.connect(
    self._on_preroll_about_to_finish, Qt.ConnectionType.QueuedConnection
)
```

### Bus-handler single-bool gate (Pattern 2)
**Source:** new gate in `_on_gst_tag` per D-07 (read site).
**Apply to:** preroll metadata suppression. One bool `self._preroll_in_flight`. Set in `Player.play` (main), cleared in `_on_preroll_about_to_finish` (main), read in `_on_gst_tag` (bus-loop — atomic bool read).

### Source-grep drift-guard with non-comment filter (Pattern 3)
**Source:** `tests/test_player.py:746–764` (Phase 82 idiom; precedent Phase 51/55/61/63/81).
**Apply to:** Phase 83 D-14 test 8. Pins `'"SomaFM"'` AND `'_last_preroll_played_at'`. Non-comment filter MUST be present.

### Thread-local `Repo(db_connect())` for worker writes (Pattern 4)
**Source:** `musicstreamer/soma_import.py:398–402` (Phase 74 CR-03).
**Apply to:** `_preroll_backfill_worker` — opens its own `sqlite3.Connection` via `db_connect()`, wraps in `Repo(con)`, closes in `finally`. Never share the main-thread Repo with a worker.

### Per-channel try/except + rollback sentinel
**Source:** `musicstreamer/soma_import.py:273–364` (Phase 74 D-15 / CR-04).
**Apply to:** `import_stations` preroll-insert step. New `repo.insert_preroll(...)` calls AND `repo.set_prerolls_fetched_at(...)` MUST land INSIDE the `try:` block, BEFORE the `inserted_station_id = None` sentinel clear at line 339. Otherwise (per RESEARCH Pitfall 4) a mid-step exception leaves an orphaned `prerolls_fetched_at` timestamp.

### Idempotent additive schema (CREATE TABLE IF NOT EXISTS + ALTER TABLE try/except OperationalError)
**Source:** `musicstreamer/repo.py:124–137` (CREATE) and `repo.py:269–282` (ALTER, Phase 82).
**Apply to:** `station_prerolls` table CREATE goes inside `db_init`'s `executescript` block (lines 89–148); `prerolls_fetched_at` ALTER goes in a fresh `try: ... except sqlite3.OperationalError: pass` block AFTER the legacy `stations_new` rebuild block (line 251) for the same Pitfall 2 reason called out in the Phase 82 comment.

### Eager-load on Station builder (4 sites)
**Source:** `musicstreamer/repo.py:450, 487, 582, 697` (4 Station-builder sites — every one must add the new fields).
**Apply to:** Each of `list_stations` / `get_station` / `list_recently_played` / `list_favorite_stations` must add `prerolls=self.list_prerolls(r["id"])` AND `prerolls_fetched_at=r["prerolls_fetched_at"]` to the `Station(...)` kwargs.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | Every Phase 83 surface has an exact in-codebase precedent. The only **new** GStreamer wiring (the `playbin3.connect("about-to-finish", ...)` callback) is a structural twin of the existing bus-handler `bus.connect("message::error", ...)` pattern at `player.py:333–337`; the streaming-thread → main-thread marshaling is identical to `_try_next_stream_requested` at `player.py:259–263`. No greenfield surface. |

## Metadata

**Analog search scope:** `musicstreamer/` (player.py, repo.py, models.py, soma_import.py, migration.py) and `tests/` (test_player.py, test_repo.py, test_soma_import.py).
**Files scanned:** 8 source + 3 test = 11.
**Pattern extraction date:** 2026-05-22
