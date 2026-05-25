# Phase 82: User-selected stream provider is honored on next Play — Research

**Researched:** 2026-05-21
**Domain:** SQLite schema evolution · Player failover queue · Repo dataclass propagation · UI persistence hookup
**Confidence:** HIGH — all findings are from direct source inspection of the working codebase

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Per-station sticky in DB. Column: `preferred_stream_id INTEGER NULL REFERENCES streams(id) ON DELETE SET NULL` on `stations`. Selection survives restarts, list re-clicks, pause/resume.
- **D-02:** Selection is set on every `_on_stream_selected` invocation, including when the user picks back the default.
- **D-03:** Fix at the `Player.play(station)` layer only — NOT scattered across UI callsites. Single change covers every play entry point.
- **D-04:** `Player.play_stream(stream)` is unchanged.
- **D-05:** If user-picked stream fails, fall back through `order_streams` ordering — "preferred first", not "only". Existing `_failover_timer` / `_handle_gst_error_recovery` flows stay unchanged.
- **D-07:** Silent UX — no pin icon, no "Using Twitch" tooltip, no "Reset to default" menu.
- **D-08:** Schema change via SQLite `user_version` bump and forward-only migration in `db_init()`. New column defaults to NULL.

### Claude's Discretion

- **Test fixture scope** — behavioral test: insert 2-stream station, pick secondary stream, call `Player.play(station)` again, assert picked stream is at queue head. Plus failover regression (picked stream errors → queue advances through rest). Plus source-grep drift-guard pinning the `preferred_stream_id` access in `Player.play()`.
- **Stream-id stability across re-imports** — researcher to confirm whether SomaFM / AudioAddict / GBS.FM imports use stable stream ids or rebuild per re-import. (Full finding: see Stream-id Stability section below.)
- **Column naming** — `preferred_stream_id` is working name; `last_picked_stream_id` / `user_preferred_stream_id` are alternatives.

### Deferred Ideas (OUT OF SCOPE)

- "Stop and toast" mode
- "Retry with default order" toast button
- Pinned-stream UX cue (icon)
- "Reset to default stream order" hamburger / right-click action
- Cross-device sync of preferred-stream picks
- Per-quality fallback policy
- Bulk "clear all preferred-stream picks" admin action
</user_constraints>

---

## Summary

Phase 82 is a small, high-confidence phase: one new nullable FK column on `stations`, one new Repo setter, one 3-line change inside `Player.play()`, and one new line in `_on_stream_selected`. The existing codebase supplies exact analogs for every piece.

**The `user_version` bump referenced in D-08 does not currently exist in the codebase.** The established migration pattern is the `try/except sqlite3.OperationalError` ALTER TABLE idiom inside `db_init()` in `musicstreamer/repo.py`. The CONTEXT.md's "user_version bump" phrasing describes the *intent* (forward-only, per schema change) but the *mechanism* is the try/except block, not a literal `PRAGMA user_version`. The planner must use the try/except idiom to match existing patterns.

**Stream-id stability:** All three import paths (AA, SomaFM, GBS.FM) use dedup-by-URL skip semantics — once a station is in the library, re-importing is a no-op. They do NOT wipe and rebuild stream IDs on re-import. The SQLite `INTEGER PRIMARY KEY AUTOINCREMENT` on `station_streams.id` is stable as long as the station is not deleted. The `ON DELETE SET NULL` FK on `preferred_stream_id` handles the one case where stability breaks: explicit station deletion (which cascades to stream deletion).

**Primary recommendation:** Follow the `cover_art_source` column addition (Phase 73) as the implementation template — it is the most recent, most complete precedent for the full stack of changes Phase 82 needs.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Persist preferred-stream pick | DB / Repo layer | — | Survives restarts by design (D-01); UI reads it back via Station dataclass |
| Write the pick on user selection | UI (NowPlayingPanel._on_stream_selected) | Repo | Single callsite per D-02 |
| Honor the pick at play time | Player.play() | — | D-03 locks fix to this single layer |
| Failover after pick fails | Player._try_next_stream | — | Existing queue-advance path; unchanged (D-05) |
| Schema migration | Repo.db_init() | — | Established try/except ALTER TABLE pattern |

---

## Research Findings

### RQ1: Stream-id Stability Across Re-imports [VERIFIED: direct source inspection]

**Finding:** Stream IDs (`station_streams.id`) are stable across all three current import paths as long as a station is not deleted.

**Evidence:**

- **SomaFM (`soma_import.py`):** D-05/D-09 dedup semantics — if ANY of a channel's stream URLs already exists in the library, the whole channel is skipped (no insert, no update). On first import, SQLite `AUTOINCREMENT` assigns IDs and they never change unless the station is deleted. [VERIFIED: soma_import.py:290-296]
- **AudioAddict (`aa_import.py`):** Same dedup-by-URL-skip semantics (`station_exists_by_url` check at aa_import.py:214). On match, the channel is skipped entirely — no ID churn. [VERIFIED: aa_import.py:214-216]
- **GBS.FM (`gbs_api.py`):** The re-import path (`import_station`) finds the existing station by URL pattern match and calls `repo.update_stream(rows[0].id, ...)` in-place — stream IDs are preserved on update. [VERIFIED: gbs_api.py:1172-1200]
- **YT Import (`yt_import.py`):** `station_exists_by_url` check (yt_import.py:136); skip if already present. IDs stable.

**What triggers ID instability:** Explicit `repo.delete_station(station_id)` (which ON DELETE CASCADE deletes all `station_streams` rows). On re-import after deletion, new stream rows get new AUTOINCREMENT IDs. The `ON DELETE SET NULL` FK on `preferred_stream_id` handles this case correctly — the user's pick is silently cleared, and they re-pick on next play.

**Conclusion:** `ON DELETE SET NULL` is the right defensive measure and covers the only instability case. Acceptable behavior per D-05's "preferred first, not only" contract.

---

### RQ2: Established Migration Pattern [VERIFIED: direct source inspection]

**Finding:** The project does NOT use `PRAGMA user_version`. The established migration pattern is the `try/except sqlite3.OperationalError` idempotent ALTER TABLE idiom inside `db_init()` in `repo.py`. [VERIFIED: repo.py:151-267]

**The pattern (verbatim from Phase 73's `cover_art_source` addition):**

```python
# repo.py — at the bottom of db_init(), after all CREATE TABLE IF NOT EXISTS blocks
try:
    con.execute(
        "ALTER TABLE stations ADD COLUMN cover_art_source TEXT NOT NULL DEFAULT 'auto'"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent; existing rows backfilled via DEFAULT
```

**For Phase 82, the equivalent is:**

```python
try:
    con.execute(
        "ALTER TABLE stations ADD COLUMN preferred_stream_id INTEGER REFERENCES streams(id) ON DELETE SET NULL"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists
```

**Note on D-08 language:** The CONTEXT.md says "user_version bump" — this reflects the *intent* (forward-only per-schema-change migration tracking), not the literal PRAGMA. The codebase has never used `PRAGMA user_version`. The try/except idiom achieves the same forward-only guarantee without a version counter. The planner should use the try/except form to match existing code.

**Ordering constraint:** The Phase 73 note at repo.py:254-261 is critical: any new `ALTER TABLE stations ADD COLUMN` block must land AFTER the legacy URL-column rebuild block (repo.py:196-252), because that block rebuilds the `stations` table via `CREATE TABLE stations_new / INSERT SELECT / DROP / RENAME`, which does not carry forward dynamically-added columns. A column added by an earlier ALTER would be lost if the URL-column rebuild runs on a fresh DB. The rebuild block is protected by `try/except sqlite3.OperationalError` (the `SELECT url FROM stations` probe triggers the block only when the legacy `url` column exists). On any DB that has already run through the URL-column migration, the rebuild block is a no-op, so ordering is only critical for the very first app launch on an ancient DB. The safe placement is the same as Phase 73 (after the rebuild block, before `db_init` returns).

**Test pattern (from `test_cover_art_source_migration_idempotent`):**

```python
def test_preferred_stream_id_migration_idempotent(repo):
    db_init(repo.con)  # second call must not raise
    db_init(repo.con)  # third call: paranoia
    cols = repo.con.execute("PRAGMA table_info('stations')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert "preferred_stream_id" in by_name
    col = by_name["preferred_stream_id"]
    assert col[2] == "INTEGER"    # type
    assert col[3] == 0            # nullable (NOT NULL = 0 — this column is nullable)
    assert col[4] is None         # no DEFAULT
```

---

### RQ3: Station Dataclass and Repo Methods That Must Be Updated [VERIFIED: direct source inspection]

**Finding:** The `Station` dataclass is defined in `musicstreamer/models.py`. Every Repo method that constructs a `Station` must pass through the new field. [VERIFIED: models.py:26-39, repo.py:435-704]

**Current Station dataclass fields (models.py:27-39):**

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
```

**New field to add (with keyword default = None, must go BEFORE positional fields or alongside other keyword-default fields):**

```python
    preferred_stream_id: Optional[int] = None  # Phase 82 D-01
```

Placement: append after `is_favorite: bool = False` (last field). This is safe because it has a default value and all existing call sites use positional construction for the first 8 required fields only.

**Repo methods that construct Station objects — ALL must add `preferred_stream_id=r["preferred_stream_id"]`:**

| Method | Location | Notes |
|--------|----------|-------|
| `list_stations()` | repo.py:435 | Phase 81 just modified this — confirmed it uses `r["cover_art_source"]` pattern |
| `get_station()` | repo.py:471 | Same SELECT shape |
| `list_recently_played()` | repo.py:557 | Same SELECT shape |
| `list_favorite_stations()` | repo.py:671 | Phase 81 target — same SELECT shape |

All four methods use `SELECT s.*, p.name AS provider_name FROM stations s LEFT JOIN providers ...`. The `s.*` wildcard will pick up the new column automatically after the ALTER TABLE — the `r["preferred_stream_id"]` access will return `None` for existing rows (correct default) and whatever the user last picked for updated rows.

**New Repo method to add (shaped like `update_last_played`):**

```python
def set_preferred_stream(self, station_id: int, stream_id: Optional[int]) -> None:
    self.con.execute(
        "UPDATE stations SET preferred_stream_id = ? WHERE id = ?",
        (stream_id, station_id),
    )
    self.con.commit()
```

Accepts `None` to clear (user re-picks the default stream — D-02).

---

### RQ4: Player.play() Head-of-Queue Insertion Mechanics [VERIFIED: direct source inspection]

**Current `Player.play()` code (player.py:505-536):**

```python
def play(self, station: Station, on_title=None, preferred_quality: str = "",
         on_failover=None, on_offline=None) -> None:
    self._cancel_timers()
    self._streams_queue = []
    self._recovery_in_flight = False
    self._install_legacy_callbacks(on_title, on_failover, on_offline)
    self._current_station_name = station.name
    self._current_station_id = station.id
    self._is_first_attempt = True
    self._twitch_resolve_attempts = 0

    if not station.streams:
        self.title_changed.emit("(no streams configured)")
        return

    # Build ordered stream queue: preferred quality first, then rest in order_streams order
    streams_by_position = order_streams(station.streams)
    preferred = None
    if preferred_quality:
        preferred = next(
            (s for s in streams_by_position if s.quality == preferred_quality),
            None,
        )

    if preferred:
        queue = [preferred] + [s for s in streams_by_position if s is not preferred]
    else:
        queue = list(streams_by_position)

    self._streams_queue = queue
    self._try_next_stream()
```

**Phase 82 change — insert AFTER the `streams_by_position = order_streams(station.streams)` line, BEFORE the `preferred_quality` block:**

```python
    streams_by_position = order_streams(station.streams)

    # Phase 82 D-01/D-03: honor per-station sticky preferred stream.
    # Check preferred_stream_id from the station dataclass (set by Repo.set_preferred_stream
    # on every _on_stream_selected invocation). If it resolves to a stream in station.streams,
    # prepend it to the queue and dedupe — user's explicit pick beats order_streams ranking.
    preferred_stream_id = getattr(station, "preferred_stream_id", None)
    if preferred_stream_id is not None:
        _preferred_by_id = next(
            (s for s in station.streams if s.id == preferred_stream_id), None
        )
        if _preferred_by_id is not None:
            streams_by_position = [_preferred_by_id] + [
                s for s in streams_by_position if s is not _preferred_by_id
            ]
```

**Precedence between `preferred_stream_id` (D-01) and `preferred_quality` kwarg:**

The `preferred_quality` kwarg is used by the Phase 47 "preferred quality" feature (a programmatic preference). The `preferred_stream_id` DB field is the user's explicit interactive pick. **Recommendation: `preferred_stream_id` wins over `preferred_quality`.** Rationale: the user explicitly chose a specific stream; the `preferred_quality` kwarg is a hint, not a user interaction. Implementation: apply `preferred_stream_id` logic first (modifies `streams_by_position`), then apply the existing `preferred_quality` block (which searches `streams_by_position` for a quality match). If both are set and they point to different streams: `preferred_stream_id` wins because it places its stream at index 0 of `streams_by_position`, and the `preferred_quality` search of `streams_by_position` finds a different stream (if any) and moves it to index 0, overriding the id-based pick. This is the wrong behavior.

**Better approach:** Guard the `preferred_quality` block with a check — only apply it when `preferred_stream_id` resolved to `None`:

```python
    streams_by_position = order_streams(station.streams)

    # Phase 82: explicit user pick (preferred_stream_id) takes priority over
    # programmatic preferred_quality hint.
    preferred_by_id = None
    preferred_stream_id = getattr(station, "preferred_stream_id", None)
    if preferred_stream_id is not None:
        preferred_by_id = next(
            (s for s in station.streams if s.id == preferred_stream_id), None
        )

    preferred = preferred_by_id  # may be None
    if preferred is None and preferred_quality:
        preferred = next(
            (s for s in streams_by_position if s.quality == preferred_quality),
            None,
        )

    if preferred:
        queue = [preferred] + [s for s in streams_by_position if s is not preferred]
    else:
        queue = list(streams_by_position)

    self._streams_queue = queue
    self._try_next_stream()
```

This is a minimal, low-risk rewrite of the existing queue-build block — no new control flow, just widened the `preferred` search to include ID-based lookup before quality-based lookup.

---

### RQ5: Player-layer Test Patterns [VERIFIED: direct source inspection]

**Established pattern from `test_player_failover.py`:**

```python
def make_player(qtbot):
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch("musicstreamer.player.Gst.ElementFactory.make",
               return_value=mock_pipeline):
        player = Player()
    player._pipeline = MagicMock()
    return player

def test_preferred_stream_first(qtbot):
    p = make_player(qtbot)
    streams = [make_stream(1, 1, "low"), make_stream(2, 2, "hi")]
    station = make_station_with_streams(streams)
    with patch.object(p, "_set_uri"):
        p.play(station, preferred_quality="hi")
    assert p._current_stream.quality == "hi"
```

**MEMORY.md GStreamer mock blind spot:** `pipeline.emit(...)` calls pass through any mock. For Phase 82, the critical assertion is on `_streams_queue` BEFORE `_try_next_stream` consumes the head. The fix: assert on `_streams_queue` ordering immediately after `play()` returns, not on bus signals. Use `patch.object(p, "_set_uri")` to stop the play from actually attempting network access.

**Phase 82 player test structure:**

```python
def test_preferred_stream_id_at_queue_head(qtbot):
    """D-03: preferred_stream_id places that stream at queue head."""
    p = make_player(qtbot)
    # YT stream has higher quality rank; Twitch stream is the user's pick
    yt_stream = make_stream(id_=1, position=1, quality="hi", url="http://yt/1")
    twitch_stream = make_stream(id_=2, position=2, quality="med", url="http://twitch/2")
    station = make_station_with_streams([yt_stream, twitch_stream])
    station.preferred_stream_id = 2  # user picked Twitch

    with patch.object(p, "_set_uri"):
        p.play(station)

    # Twitch must be the current stream (already popped from queue by _try_next_stream)
    assert p._current_stream.id == 2
    # YT must be the sole remaining failover entry
    assert len(p._streams_queue) == 1
    assert p._streams_queue[0].id == 1


def test_preferred_stream_id_not_duplicated(qtbot):
    """Preferred stream appears exactly once across current_stream + queue."""
    p = make_player(qtbot)
    s1 = make_stream(id_=1, position=1, quality="hi")
    s2 = make_stream(id_=2, position=2, quality="med")
    station = make_station_with_streams([s1, s2])
    station.preferred_stream_id = 2
    with patch.object(p, "_set_uri"):
        p.play(station)
    all_ids = [p._current_stream.id] + [s.id for s in p._streams_queue]
    assert all_ids.count(2) == 1


def test_preferred_stream_id_none_falls_back_to_order_streams(qtbot):
    """When preferred_stream_id is None, order_streams ranking is used."""
    p = make_player(qtbot)
    s_low = make_stream(id_=1, position=1, quality="low", url="http://x/1")
    s_hi  = make_stream(id_=2, position=2, quality="hi",  url="http://x/2")
    station = make_station_with_streams([s_low, s_hi])
    station.preferred_stream_id = None
    with patch.object(p, "_set_uri"):
        p.play(station)
    # order_streams puts hi first
    assert p._current_stream.quality == "hi"


def test_preferred_stream_id_stale_resolved_falls_back(qtbot):
    """If preferred_stream_id resolves to no stream in station.streams, fall back."""
    p = make_player(qtbot)
    s1 = make_stream(id_=1, position=1, quality="hi")
    station = make_station_with_streams([s1])
    station.preferred_stream_id = 999  # stale ID not in station.streams
    with patch.object(p, "_set_uri"):
        p.play(station)
    assert p._current_stream.id == 1  # falls back to order_streams


def test_failover_after_preferred_stream_advances_queue(qtbot):
    """D-05: user's picked stream fails → queue advances through rest."""
    p = make_player(qtbot)
    s1 = make_stream(id_=1, position=1, quality="hi")
    s2 = make_stream(id_=2, position=2, quality="med")
    station = make_station_with_streams([s1, s2])
    station.preferred_stream_id = 2  # user picked s2
    with patch.object(p, "_set_uri"):
        p.play(station)
    assert p._current_stream.id == 2
    # simulate s2 failing → advance queue
    with patch.object(p, "_set_uri"):
        p._try_next_stream()
    assert p._current_stream.id == 1
```

---

### RQ6: Repo Test Patterns [VERIFIED: direct source inspection]

**Fixture setup (from test_repo.py):**

```python
@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)
```

**Seeding a 2-stream station:**

```python
sid = repo.insert_station("Lofi Girl", "http://yt/stream", "YouTube", "lofi")
# insert_station auto-creates stream at position=1; get its id
yt_stream_id = repo.list_streams(sid)[0].id
twitch_stream_id = repo.insert_stream(sid, "http://twitch/stream",
                                       quality="med", position=2,
                                       stream_type="twitch", codec="AAC")
```

**New test targets for Phase 82:**

```python
def test_set_preferred_stream_persists(repo):
    """set_preferred_stream writes the column; list_stations reads it back."""
    sid = repo.insert_station("Test", "http://yt/s", "", "")
    twitch_id = repo.insert_stream(sid, "http://twitch/s", quality="med", position=2)
    repo.set_preferred_stream(sid, twitch_id)
    stations = repo.list_stations()
    assert stations[0].preferred_stream_id == twitch_id


def test_set_preferred_stream_roundtrip_get_station(repo):
    sid = repo.insert_station("Test", "http://s", "", "")
    stream_id = repo.list_streams(sid)[0].id
    repo.set_preferred_stream(sid, stream_id)
    st = repo.get_station(sid)
    assert st.preferred_stream_id == stream_id


def test_set_preferred_stream_clears_to_none(repo):
    """D-02: can set back to None when user re-picks the default."""
    sid = repo.insert_station("Test", "http://s", "", "")
    stream_id = repo.list_streams(sid)[0].id
    repo.set_preferred_stream(sid, stream_id)
    repo.set_preferred_stream(sid, None)
    assert repo.get_station(sid).preferred_stream_id is None


def test_preferred_stream_default_none(repo):
    """New stations have preferred_stream_id=None (D-08 no backfill)."""
    sid = repo.create_station()
    assert repo.get_station(sid).preferred_stream_id is None


def test_preferred_stream_id_in_list_recently_played(repo):
    """list_recently_played also carries preferred_stream_id."""
    sid = repo.insert_station("Test", "http://s", "", "")
    stream_id = repo.list_streams(sid)[0].id
    repo.set_preferred_stream(sid, stream_id)
    repo.update_last_played(sid)
    recent = repo.list_recently_played(5)
    assert recent[0].preferred_stream_id == stream_id


def test_preferred_stream_id_in_list_favorite_stations(repo):
    sid = repo.insert_station("Test", "http://s", "", "")
    stream_id = repo.list_streams(sid)[0].id
    repo.set_preferred_stream(sid, stream_id)
    repo.set_station_favorite(sid, True)
    favs = repo.list_favorite_stations()
    assert favs[0].preferred_stream_id == stream_id
```

---

### RQ7: Migration Test Patterns [VERIFIED: direct source inspection]

The established migration test pattern (from `test_cover_art_source_migration_idempotent` in test_repo.py:228-252):

1. Call `db_init(repo.con)` two or three times — must not raise.
2. Run `PRAGMA table_info('stations')` and assert the column is present with the correct type, nullability, and DEFAULT.

For Phase 82:

```python
def test_preferred_stream_id_migration_idempotent(repo):
    """db_init twice must not raise; column exists as nullable INTEGER with no DEFAULT."""
    db_init(repo.con)
    db_init(repo.con)
    cols = repo.con.execute("PRAGMA table_info('stations')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert "preferred_stream_id" in by_name, (
        f"preferred_stream_id column missing; got {sorted(by_name)}"
    )
    col = by_name["preferred_stream_id"]
    assert col[2] == "INTEGER"  # type
    assert col[3] == 0          # NOT NULL = 0 (nullable — correct for optional FK)
    assert col[4] is None       # no DEFAULT (NULL is the implicit default)
```

There are no existing `user_version` migration tests because the project doesn't use `PRAGMA user_version`. Migration correctness is verified entirely through PRAGMA table_info assertions and idempotency checks.

---

### RQ8: UI Test Patterns [VERIFIED: direct source inspection]

**Established `_on_stream_selected` test pattern (from test_stream_picker.py:162-176):**

```python
def test_stream_selection_calls_play_stream(qtbot, player, repo):
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(multi_stream_station)
    player.play_stream.reset_mock()
    panel.stream_combo.setCurrentIndex(1)  # triggers currentIndexChanged → _on_stream_selected
    player.play_stream.assert_called_once()
    called_with = player.play_stream.call_args[0][0]
    assert called_with.id == MULTI_STREAMS[1].id
```

The signal is triggered by `setCurrentIndex()`. The `FakeRepo` in `test_stream_picker.py` does not currently implement `set_preferred_stream` — Phase 82's new test file must extend or subclass it.

**Phase 82 UI test strategy:**

The UI test for Phase 82 is best placed in a new file `tests/test_phase82_preferred_stream.py` to avoid disrupting the well-established test_stream_picker.py suite. The new test needs a FakeRepo that records `set_preferred_stream` calls:

```python
class FakeRepoWithPreferredStream(FakeRepo):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_preferred_stream_calls: list[tuple] = []

    def set_preferred_stream(self, station_id: int, stream_id) -> None:
        self.set_preferred_stream_calls.append((station_id, stream_id))


def test_stream_selection_calls_set_preferred_stream(qtbot):
    """D-02: _on_stream_selected persists pick to repo."""
    player = FakePlayer()
    player.play_stream = MagicMock()
    repo = FakeRepoWithPreferredStream(streams_by_station_id={2: MULTI_STREAMS})
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(multi_stream_station)  # station.id == 2

    panel.stream_combo.setCurrentIndex(1)   # triggers _on_stream_selected(1)

    assert len(repo.set_preferred_stream_calls) == 1
    station_id_arg, stream_id_arg = repo.set_preferred_stream_calls[0]
    assert station_id_arg == 2
    assert stream_id_arg == MULTI_STREAMS[1].id
```

**Key insight:** The `_on_stream_selected` slot at now_playing_panel.py:1281 currently calls `self._player.play_stream(s)` and then `self._refresh_quality_badge()`. The Phase 82 addition is a `self._repo.set_preferred_stream(self._station.id, s.id)` call inserted between those two lines. The test verifies the repo call happens.

**`_sync_stream_picker` interaction:** Phase 82 does NOT change `_sync_stream_picker`. The picker already calls `blockSignals(True/False)` to prevent `currentIndexChanged` from firing when the failover path updates the combo. This means failover-driven combo updates do NOT trigger `set_preferred_stream` — correct behavior (failover is automatic, not a user pick).

---

### RQ9: Source-grep Drift-guard Target Lines [VERIFIED: direct source inspection]

**Established idiom (Phase 81 — test_repo.py:860-868):**

```python
def test_collate_nocase_drift_guard(repo):
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent / "musicstreamer" / "repo.py").read_text()
    lines = [ln for ln in source.splitlines() if not ln.lstrip().startswith("#")]
    body = "\n".join(lines)
    assert body.count("ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE") == 2, (...)
```

**Phase 82 drift-guard targets:**

For `Player.play()` in `musicstreamer/player.py` — pin the `preferred_stream_id` access literal:

```python
def test_preferred_stream_id_drift_guard_player():
    """Phase 82 D-03: preferred_stream_id lookup must remain in Player.play()."""
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent / "musicstreamer" / "player.py").read_text()
    non_comments = "\n".join(
        ln for ln in source.splitlines() if not ln.lstrip().startswith("#")
    )
    assert "preferred_stream_id" in non_comments, (
        "Phase 82 D-03: preferred_stream_id lookup must exist in player.py "
        "(Player.play queue-build block). Do not remove silently."
    )
```

For `_on_stream_selected` in `musicstreamer/ui_qt/now_playing_panel.py` — pin the `set_preferred_stream` call:

```python
def test_set_preferred_stream_drift_guard_now_playing_panel():
    """Phase 82 D-02: set_preferred_stream call must remain in _on_stream_selected."""
    from pathlib import Path
    source = (
        Path(__file__).resolve().parent.parent
        / "musicstreamer" / "ui_qt" / "now_playing_panel.py"
    ).read_text()
    non_comments = "\n".join(
        ln for ln in source.splitlines() if not ln.lstrip().startswith("#")
    )
    assert "set_preferred_stream" in non_comments, (
        "Phase 82 D-02: set_preferred_stream call must exist in now_playing_panel.py "
        "(_on_stream_selected). Do not remove silently."
    )
```

These two drift-guards can live in `tests/test_phase82_preferred_stream.py` alongside the behavioral tests.

---

### RQ10: Mock Blind Spots Specific to Phase 82 [VERIFIED: direct source inspection + MEMORY.md]

**Identified blind spots:**

1. **GStreamer `pipeline.emit()` (MEMORY.md `feedback_gstreamer_mock_blind_spot.md`):** Phase 82 Player tests must assert on `_streams_queue` ordering and `_current_stream.id` rather than on bus signals or `pipeline.emit()` calls. All proposed test patterns above follow this rule. [ASSUMED — MEMORY.md cites this as a confirmed class-level blind spot]

2. **FakePlayer's `play()` stub:** `FakePlayer.play()` just appends station to `play_calls` list — it does NOT build a `_streams_queue`. Phase 82's Player-layer tests must use the REAL `Player` (with `Gst.ElementFactory.make` mocked, as in `test_player_failover.py`), not FakePlayer. FakePlayer is for UI tests that need to verify the player API is called; Player itself is for queue-ordering correctness tests. [VERIFIED: _fake_player.py:99-100]

3. **FakeRepo in test_stream_picker.py does not implement `set_preferred_stream`:** Any Panel test that calls `_on_stream_selected` against the standard `FakeRepo` will raise `AttributeError`. Phase 82 must either add `set_preferred_stream` to the base `FakeRepo` (in `test_stream_picker.py`) or use a subclass. The subclass approach (new file `test_phase82_preferred_stream.py`) is lower risk and avoids touching the established test_stream_picker.py fixture. [VERIFIED: test_stream_picker.py FakeRepo definition]

4. **`_on_stream_selected` fires on `bind_station()`:** `bind_station` calls `_populate_stream_picker`, which calls `stream_combo.addItems(...)` and may set `currentIndex`, potentially triggering `currentIndexChanged` → `_on_stream_selected`. The existing code blocks this with `stream_combo.blockSignals(True/False)` during population. Phase 82 must NOT call `set_preferred_stream` from inside the `blockSignals` window. [VERIFIED: now_playing_panel.py — stream_combo signal behavior is blockSignals-guarded during populate]

5. **Repo tests use real in-memory SQLite (not mocks):** The `repo` fixture in `test_repo.py` opens a real `sqlite3.connect(str(tmp_path / "test.db"))` — this is the correct approach and is the lowest-risk testing path for schema changes. Do not introduce mocking for the Repo layer. [VERIFIED: test_repo.py:7-13]

---

### RQ (Supplemental): Current _on_stream_selected and its call context [VERIFIED: direct source inspection]

Current `_on_stream_selected` (now_playing_panel.py:1281-1291):

```python
def _on_stream_selected(self, index: int) -> None:
    """User manually selected a stream from the picker (D-21)."""
    if index < 0 or not self._streams:
        return
    stream_id = self.stream_combo.itemData(index)
    for s in self._streams:
        if s.id == stream_id:
            self._player.play_stream(s)
            break
    # Phase 70 / Plan 70-06: refresh quality badge for the newly-selected stream.
    self._refresh_quality_badge()
```

**Phase 82 addition:** After `self._player.play_stream(s)` and before `break`, insert:
```python
            if self._station is not None:
                self._repo.set_preferred_stream(self._station.id, s.id)
```

The `self._station` guard is already implicitly covered by the `if index < 0 or not self._streams: return` guard at the top, but being explicit avoids an AttributeError if `_station` is somehow None.

**The `for...break` structure means `set_preferred_stream` is called exactly once per user pick, only when the stream is found — correct behavior.**

---

## Standard Stack

No new external packages. All changes are pure Python within the existing codebase.

### Changes Required

| Module | Change Type | Details |
|--------|-------------|---------|
| `musicstreamer/models.py` | Additive field | `preferred_stream_id: Optional[int] = None` on `Station` dataclass |
| `musicstreamer/repo.py` | ALTER TABLE + new method + SELECT propagation | `db_init()`: new try/except ALTER block; `set_preferred_stream()`: new 3-line setter; 4 Station-constructing methods: add `preferred_stream_id=r["preferred_stream_id"]` |
| `musicstreamer/player.py` | Logic change in `play()` | ~6 lines replacing the `preferred` variable setup block |
| `musicstreamer/ui_qt/now_playing_panel.py` | 2-line insert in `_on_stream_selected` | After `play_stream(s)`, call `repo.set_preferred_stream(station_id, s.id)` |

---

## Architecture Patterns

### System Architecture Diagram

```
User picks Twitch from stream_combo
        |
        v
_on_stream_selected(index)
        |
        +-- player.play_stream(s)   [immediate effect — D-04 unchanged]
        |
        +-- repo.set_preferred_stream(station.id, s.id)
                |
                v
        UPDATE stations SET preferred_stream_id = ? WHERE id = ?
                |
                v
        stations.preferred_stream_id = stream_id  [persisted]

User presses Play / re-clicks station (next event)
        |
        v
Player.play(station)          [station.preferred_stream_id already populated
        |                       by list_stations / get_station from DB]
        |
        +-- order_streams(station.streams) -> [YT-hi, Twitch-med]
        |
        +-- check station.preferred_stream_id -> resolves to Twitch stream
        |
        +-- queue = [Twitch, YT-hi]  [Twitch at head]
        |
        v
_try_next_stream() -> plays Twitch immediately

If Twitch fails:
        |
        v
_handle_gst_error_recovery -> _try_next_stream -> plays YT  [D-05 failover unchanged]
```

### Recommended Project Structure

No new files needed in production code. One new test file:

```
tests/
└── test_phase82_preferred_stream.py   # Player queue tests + Repo tests + UI tests + drift-guards
```

Alternatively, new tests may be distributed:
- `tests/test_player_failover.py` — append Player queue tests (matches existing pattern)
- `tests/test_repo.py` — append Repo tests (matches existing pattern)
- New `tests/test_phase82_preferred_stream.py` — UI test + drift-guards

**Recommendation:** Single new file `tests/test_phase82_preferred_stream.py`. Keeps Phase 82 changes localized, easy to review, and matches the Phase 73/72.x/70 precedent of per-phase test files.

### Anti-Patterns to Avoid

- **Do not call `set_preferred_stream` from `_sync_stream_picker`** — failover-driven combo updates must not overwrite the user's pick (blockSignals already prevents this, but an explicit call would bypass it).
- **Do not rebuild stream IDs during import** — all importers use dedup-by-URL-skip; stable IDs are preserved naturally.
- **Do not call `set_preferred_stream` during `bind_station` / `_populate_stream_picker`** — that sets the initial combo state, not a user pick.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Deduplication after prepend | Custom set logic | `[preferred] + [s for s in queue if s is not preferred]` | One-liner using `is` identity check — same pattern as existing `preferred_quality` block at player.py:531 |
| Nullable FK with self-heal | Application-level orphan cleanup | `ON DELETE SET NULL` in schema | SQLite enforces it at DELETE time if PRAGMA foreign_keys = ON (which db_connect guarantees per BUG-10 / Phase 80) |
| Forward-only migration | Schema versioning library | `try/except sqlite3.OperationalError` ALTER | Project's established idiom; no new deps |

---

## Common Pitfalls

### Pitfall 1: Calling set_preferred_stream from _populate_stream_picker / blockSignals window
**What goes wrong:** `bind_station` populates the combo and may call `setCurrentIndex(0)`. If `_on_stream_selected` fires during population (blockSignals guard fails), `set_preferred_stream` would overwrite the user's DB pick with index 0 (the highest-quality stream) every time a station is bound.
**Why it happens:** The `currentIndexChanged` signal is connected before `blockSignals(True)` is called, or `blockSignals(False)` fires before the combo is fully populated.
**How to avoid:** The existing code already uses `stream_combo.blockSignals(True/False)` during populate. Phase 82 adds `set_preferred_stream` inside the `for s in self._streams` loop in `_on_stream_selected`, which can only be reached when blockSignals is False. No additional guard needed, but verify the existing blockSignals pattern in `_populate_stream_picker` is intact.
**Warning signs:** `test_stream_selection_calls_set_preferred_stream` sees unexpected calls during `bind_station()`.

### Pitfall 2: ALTER TABLE placement before the legacy URL-column rebuild block
**What goes wrong:** A new column added by ALTER TABLE before the `try: con.execute("SELECT url FROM stations LIMIT 1")` block would be silently dropped on fresh databases that still have the legacy `url` column. The rebuild block does `CREATE TABLE stations_new / INSERT SELECT / DROP / RENAME` without carrying dynamically-added columns.
**Why it happens:** The rebuild block is protected by its own `try/except sqlite3.OperationalError`, but if it runs (because a legacy DB exists), it recreates the table without the new column.
**How to avoid:** Place the Phase 82 ALTER TABLE block AFTER the URL-column rebuild block — same placement as Phase 73's `cover_art_source` ALTER (repo.py:261-267).
**Warning signs:** `test_preferred_stream_id_migration_idempotent` passes but `preferred_stream_id` is missing from PRAGMA table_info on a test DB seeded with the legacy URL column.

### Pitfall 3: `Station` dataclass positional construction at existing call sites
**What goes wrong:** Adding `preferred_stream_id` as a positional field (without a default) would break every existing `Station(...)` construction that doesn't pass it.
**How to avoid:** Add `preferred_stream_id: Optional[int] = None` as a keyword-default field, appended after the last existing field (`is_favorite: bool = False`). All existing call sites continue to work. [VERIFIED: models.py positional construction pattern]

### Pitfall 4: `r["preferred_stream_id"]` KeyError on old DB connections
**What goes wrong:** On a DB opened before the migration runs, `r["preferred_stream_id"]` raises `KeyError` (or `IndexError` for sqlite3.Row) because the column doesn't exist yet.
**Why it happens:** db_init is called on first connection, but if `list_stations()` is called on a connection that didn't run db_init, the column may not exist.
**How to avoid:** All connections go through `db_connect()` → `db_init()` (enforced by Phase 80's drift-guard test `test_db_connect_is_sole_connection_factory.py`). The migration runs on every connection before queries fire. Alternatively, use `r["preferred_stream_id"] if "preferred_stream_id" in r.keys() else None` as a defensive fallback — but this is not needed given the enforced connection factory.

### Pitfall 5: FakePlayer.play_stream() stub swallowing calls in UI tests
**What goes wrong:** `FakePlayer.play_stream()` (in `_fake_player.py:110`) appends to `play_calls` list. If a UI test overrides it with `MagicMock()` (as `test_stream_picker.py:fixture` does), calls are captured but the side-effect `set_preferred_stream` call in `_on_stream_selected` fires against whatever FakeRepo is wired up. If FakeRepo lacks `set_preferred_stream`, it raises `AttributeError`.
**How to avoid:** Use the `FakeRepoWithPreferredStream` subclass in all Phase 82 UI tests. Or add `set_preferred_stream` as a no-op to the base `FakeRepo` in test_stream_picker.py.

---

## State of the Art

| Old Approach | Current Approach | Notes |
|---|---|---|
| No stream preference — always use order_streams | preferred_stream_id column + Player.play() head-of-queue insertion | Phase 82 addition |
| `preferred_quality` kwarg for quality-based bias | `preferred_stream_id` for id-based bias (takes priority) | Phase 82 adds the stronger guarantee |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `user_version` phrasing in CONTEXT.md D-08 refers to the try/except ALTER TABLE idiom (not a literal PRAGMA user_version counter, which does not exist in the codebase) | RQ2 Migration Pattern | Low — both achieve forward-only migration; the try/except idiom is confirmed present in the codebase |
| A2 | `ON DELETE SET NULL` on `preferred_stream_id` is enforced at runtime because `db_connect()` sets `PRAGMA foreign_keys = ON` per Phase 80/BUG-10 | RQ1 | Low — BUG-10 explicitly adds this PRAGMA and a drift-guard test |
| A3 | `preferred_stream_id` should win over `preferred_quality` when both are set | RQ4 Precedence | Medium — the use case for both being set is narrow (programmatic callers using preferred_quality are already deprecated in favor of DB-based picks); wrong precedence would only manifest if both args are supplied simultaneously |

---

## Open Questions

1. **Column name finalized?**
   - What we know: CONTEXT.md uses `preferred_stream_id` throughout, alternatives mentioned are `last_picked_stream_id`, `user_preferred_stream_id`.
   - What's unclear: Whether the planner wants to select a different name.
   - Recommendation: Stick with `preferred_stream_id` — it matches D-01 language verbatim and is clear.

2. **`set_preferred_stream` added to base FakeRepo or subclass?**
   - What we know: `test_stream_picker.py` has its own inline `FakeRepo` (not the shared one in `test_now_playing_panel.py`). Both need `set_preferred_stream` if any test in those files exercises `_on_stream_selected` after Phase 82.
   - Recommendation: Add a no-op `set_preferred_stream(self, *args) -> None: pass` to both inline FakeRepo classes in test_stream_picker.py and test_now_playing_panel.py as part of Phase 82's Plan 1 (DB+Repo layer). This prevents AttributeError regressions in the existing test suite.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 82 is purely code and schema changes. No external CLI tools, services, or runtimes beyond the existing Python/SQLite environment are required.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (via `uv run pytest tests/`) |
| Config file | `pyproject.toml` (inferred from project structure) |
| Quick run command | `uv run pytest tests/test_phase82_preferred_stream.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Decision | Behavior | Test Type | Automated Command | File |
|----------|----------|-----------|-------------------|------|
| D-01 / D-08 | `preferred_stream_id` column exists, nullable INTEGER, migration idempotent | unit (DB) | `uv run pytest tests/test_repo.py -k preferred_stream -x` | ❌ Wave 0 |
| D-01 / D-03 | `Player.play(station)` puts `preferred_stream_id`-resolved stream at queue head | unit (Player) | `uv run pytest tests/test_phase82_preferred_stream.py -k queue_head -x` | ❌ Wave 0 |
| D-02 | `_on_stream_selected` calls `repo.set_preferred_stream(station_id, stream_id)` | unit (UI) | `uv run pytest tests/test_phase82_preferred_stream.py -k set_preferred -x` | ❌ Wave 0 |
| D-03 (stale ID) | Stale `preferred_stream_id` (stream deleted) falls back to `order_streams` | unit (Player) | `uv run pytest tests/test_phase82_preferred_stream.py -k stale -x` | ❌ Wave 0 |
| D-05 | User's picked stream fails → failover advances through rest of queue | unit (Player) | `uv run pytest tests/test_phase82_preferred_stream.py -k failover -x` | ❌ Wave 0 |
| D-07 | No visual change to stream picker UI | manual (trivial — no UI changes) | — | n/a |
| Drift-guard: player.py | `preferred_stream_id` literal present in `player.py` non-comment lines | source-grep | `uv run pytest tests/test_phase82_preferred_stream.py -k drift -x` | ❌ Wave 0 |
| Drift-guard: now_playing_panel.py | `set_preferred_stream` literal present in `now_playing_panel.py` non-comment lines | source-grep | `uv run pytest tests/test_phase82_preferred_stream.py -k drift -x` | ❌ Wave 0 |
| Regression: existing picker tests | `test_stream_selection_calls_play_stream` continues to pass | regression | `uv run pytest tests/test_stream_picker.py -x` | ✅ existing |
| Regression: existing failover tests | `test_preferred_stream_first`, `test_no_preferred_quality_uses_position_order` pass | regression | `uv run pytest tests/test_player_failover.py -x` | ✅ existing |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_phase82_preferred_stream.py tests/test_repo.py tests/test_player_failover.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_phase82_preferred_stream.py` — new file covering all Phase 82 behavioral, migration, UI, and drift-guard tests
- [ ] `tests/test_repo.py` — append `set_preferred_stream` Repo tests (may be placed in the new file instead)
- [ ] `tests/test_stream_picker.py` inline FakeRepo — add no-op `set_preferred_stream` to prevent AttributeError regression
- [ ] `tests/test_now_playing_panel.py` inline FakeRepo — same no-op addition

---

## Security Domain

Security enforcement is enabled. ASVS categories relevant to Phase 82:

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | — |
| V3 Session Management | No | — |
| V4 Access Control | No | Single-user desktop app |
| V5 Input Validation | Minimal | `preferred_stream_id` is an INTEGER FK — SQLite type affinity prevents injection; the value comes from `stream_combo.itemData(index)` which is an integer seeded by `_populate_stream_picker` from DB-backed stream IDs (not user-typed text) |
| V6 Cryptography | No | — |

No new threat surface. The `preferred_stream_id` write path (`_on_stream_selected` → `repo.set_preferred_stream`) accepts only an integer ID that was originally returned by the DB itself — there is no path where external user input flows into this column.

---

## Sources

### Primary (HIGH confidence)

- `musicstreamer/repo.py` — db_init migration pattern (lines 151-267), Station-constructing methods (lines 435-704), insert/update stream methods (lines 336-366), update_last_played shape (lines 550-555) — all direct source inspection [VERIFIED]
- `musicstreamer/models.py` — Station dataclass definition (lines 26-39) [VERIFIED]
- `musicstreamer/player.py` — Player.play() queue build (lines 505-536), play_stream() (lines 538-548), _handle_gst_error_recovery (lines 671-693), _on_youtube_resolution_failed (lines 1130-1134) [VERIFIED]
- `musicstreamer/stream_ordering.py` — order_streams() (lines 46-76) [VERIFIED]
- `musicstreamer/ui_qt/now_playing_panel.py` — _on_stream_selected (lines 1281-1291), _sync_stream_picker (lines 1293-1302), _on_play_pause_clicked (lines 1038-1047) [VERIFIED]
- `musicstreamer/ui_qt/main_window.py` — _on_station_activated (lines 750-760), _on_sibling_activated (lines 762-773), _on_similar_activated (lines 775-785) [VERIFIED]
- `tests/test_player_failover.py` — Player test harness and queue-ordering test patterns [VERIFIED]
- `tests/test_stream_picker.py` — _on_stream_selected test pattern (lines 162-176), FakeRepo shape [VERIFIED]
- `tests/test_repo.py` — Station construction patterns, cover_art_source migration test template (lines 228-252), drift-guard template (lines 860-868) [VERIFIED]
- `tests/_fake_player.py` — FakePlayer signal list and method stubs [VERIFIED]
- `musicstreamer/soma_import.py` — dedup-by-URL-skip pattern (lines 290-296) [VERIFIED]
- `musicstreamer/aa_import.py` — dedup-by-URL-skip pattern (lines 214-216) [VERIFIED]
- `musicstreamer/gbs_api.py` — re-import by URL-align / update_stream in-place (lines 1172-1200) [VERIFIED]

### Secondary (MEDIUM confidence)

- `.planning/phases/82-twitch-only-station-still-tries-to-play-youtube-stream-first/82-CONTEXT.md` — all design decisions D-01..D-08, discretion areas, deferred items [CITED]
- `.planning/phases/74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-/74-CONTEXT.md` — SomaFM D-05/D-09 dedup-by-URL-skip semantics [CITED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pure internal changes, no new dependencies
- Architecture: HIGH — direct source inspection of all integration points
- Migration pattern: HIGH — Phase 73 precedent is exact template
- Pitfalls: HIGH — all identified from direct source inspection; no inference required
- Stream-id stability: HIGH — all three import paths confirmed to use dedup-by-URL-skip, not wipe-rebuild

**Research date:** 2026-05-21
**Valid until:** This research is based on codebase state at commit `01cf189` (Phase 81 complete). Valid until the next schema-changing phase that touches `stations`, `station_streams`, or `Player.play()`.
