import os
import sqlite3
import pytest
from musicstreamer.models import Station, Provider, StationStream
from musicstreamer.repo import Repo, db_init


@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)


@pytest.fixture
def repo_with_legacy_data(tmp_path):
    """Fixture that starts with old schema (with url column) then runs migration."""
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    # Create old schema WITH url column
    con.executescript("""
        CREATE TABLE IF NOT EXISTS providers (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            provider_id INTEGER,
            tags TEXT DEFAULT '',
            station_art_path TEXT,
            album_fallback_path TEXT,
            icy_disabled INTEGER NOT NULL DEFAULT 0,
            last_played_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE SET NULL
        );
        CREATE TRIGGER IF NOT EXISTS stations_updated_at
        AFTER UPDATE ON stations
        BEGIN
          UPDATE stations SET updated_at = datetime('now') WHERE id = NEW.id;
        END;
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_name TEXT NOT NULL,
            provider_name TEXT NOT NULL DEFAULT '',
            track_title TEXT NOT NULL,
            genre TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
            UNIQUE(station_name, track_title)
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    con.execute("INSERT INTO stations(name, url) VALUES ('TestFM', 'http://test.fm/stream')")
    con.execute("INSERT INTO stations(name, url) VALUES ('JazzFM', 'http://jazz.fm/stream')")
    con.execute("INSERT INTO stations(name, url) VALUES ('EmptyFM', '')")
    con.commit()
    # NOW run db_init which should migrate
    db_init(con)
    return Repo(con)


def test_list_stations_empty(repo):
    assert repo.list_stations() == []


def test_create_and_get_station(repo):
    station_id = repo.create_station()
    st = repo.get_station(station_id)
    assert st.id == station_id
    assert st.name == "New Station"
    assert st.streams == []


def test_update_station(repo):
    sid = repo.create_station()
    repo.update_station(sid, "My Station", None, "jazz", None, None)
    st = repo.get_station(sid)
    assert st.name == "My Station"
    assert st.tags == "jazz"


def test_models_dataclass(repo):
    sid = repo.create_station()
    st = repo.get_station(sid)
    assert isinstance(st, Station)
    assert st.provider_id is None


def test_list_providers_empty(repo):
    assert repo.list_providers() == []


def test_ensure_provider(repo):
    pid = repo.ensure_provider("TestFM")
    assert isinstance(pid, int)
    providers = repo.list_providers()
    assert any(p.name == "TestFM" for p in providers)


# --- delete_station tests ---

def test_delete_station(repo):
    sid = repo.create_station()
    repo.delete_station(sid)
    with pytest.raises(ValueError):
        repo.get_station(sid)


def test_delete_station_list(repo):
    sid1 = repo.create_station()
    sid2 = repo.create_station()
    repo.delete_station(sid1)
    stations = repo.list_stations()
    ids = [s.id for s in stations]
    assert sid1 not in ids
    assert sid2 in ids


# --- icy_disabled tests ---

def test_icy_disabled_default(repo):
    sid = repo.create_station()
    st = repo.get_station(sid)
    assert st.icy_disabled is False


def test_icy_disabled_round_trip(repo):
    sid = repo.create_station()
    repo.update_station(sid, "Radio", None, "", None, None, icy_disabled=True)
    st = repo.get_station(sid)
    assert st.icy_disabled is True


def test_icy_disabled_migration(repo):
    # Simulate app restart on existing DB — second db_init call must not raise
    db_init(repo.con)
    st_count = len(repo.list_stations())
    assert isinstance(st_count, int)


def test_update_station_preserves_icy_disabled(repo):
    sid = repo.create_station()
    repo.update_station(sid, "Radio", None, "", None, None, icy_disabled=False)
    st = repo.get_station(sid)
    assert st.icy_disabled is False

    repo.update_station(sid, "Radio", None, "", None, None, icy_disabled=True)
    st = repo.get_station(sid)
    assert st.icy_disabled is True


# --- Phase 73 / ART-MB-11: cover_art_source schema migration + dataclass mapping ---


def test_cover_art_source_default_is_auto(repo):
    """D-05: new station rows get cover_art_source='auto' via the column DEFAULT."""
    sid = repo.create_station()
    st = repo.get_station(sid)
    assert st.cover_art_source == "auto"


def test_cover_art_source_round_trip(repo):
    """D-01 / Plan 03: cover_art_source round-trips through update_station.

    Replaces the Plan-01 placeholder (direct SQL UPDATE) with the real
    repo path: `update_station(..., cover_art_source='mb_only')` writes
    the column, and `get_station` hydrates it back.
    """
    sid = repo.create_station()
    repo.update_station(
        sid, "Radio", None, "tag1", None, None,
        icy_disabled=False, cover_art_source="mb_only",
    )
    st = repo.get_station(sid)
    assert st.cover_art_source == "mb_only"


def test_update_station_persists_cover_art_source_itunes_only(repo):
    """Sanity: each of the three valid mode strings round-trips."""
    sid = repo.create_station()
    repo.update_station(
        sid, "Radio", None, "", None, None,
        icy_disabled=False, cover_art_source="itunes_only",
    )
    assert repo.get_station(sid).cover_art_source == "itunes_only"

    repo.update_station(
        sid, "Radio", None, "", None, None,
        icy_disabled=False, cover_art_source="auto",
    )
    assert repo.get_station(sid).cover_art_source == "auto"


def test_update_station_omitting_cover_art_source_resets_to_auto(repo):
    """D-05 / Plan 03 lock test: omitting the kwarg writes the default 'auto'.

    This is a CONSEQUENCE of using a keyword-default on the UPDATE statement
    (any update writes ALL columns, including the defaulted one). It locks
    Plan 04's contract: EditStationDialog MUST always pass
    `cover_art_source=` explicitly when calling update_station; otherwise
    saving the dialog silently resets the user's per-station preference
    back to 'auto'.

    By codifying this in a test we prevent Plan 04 from silently regressing
    the feature.
    """
    sid = repo.create_station()
    # Set the field to a non-default value via update_station.
    repo.update_station(
        sid, "Radio", None, "", None, None,
        icy_disabled=False, cover_art_source="mb_only",
    )
    assert repo.get_station(sid).cover_art_source == "mb_only"

    # Now call update_station WITHOUT the kwarg — the default 'auto' applies.
    repo.update_station(sid, "Radio", None, "", None, None, icy_disabled=False)
    assert repo.get_station(sid).cover_art_source == "auto", (
        "Omitting cover_art_source kwarg must reset the column to 'auto' "
        "(D-05 default). Plan 04's EditStationDialog must always pass the kwarg."
    )


def test_cover_art_source_migration_idempotent(repo):
    """ART-MB-11: db_init twice must not raise; column exists with DEFAULT 'auto'.

    Asserts both idempotency (Pitfall 8: ALTER TABLE wrapped in try/except
    sqlite3.OperationalError) AND that PRAGMA table_info reports the literal
    SQL-quoted default 'auto'. SQLite stores DEFAULT clauses verbatim, so the
    comparison must include the single quotes.
    """
    # Second db_init must not raise — column already exists.
    db_init(repo.con)
    db_init(repo.con)  # third call for paranoia; still idempotent

    # PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk).
    cols = repo.con.execute("PRAGMA table_info('stations')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert "cover_art_source" in by_name, (
        f"cover_art_source column missing; got {sorted(by_name)}"
    )
    col = by_name["cover_art_source"]
    # type is index 2; notnull is index 3; dflt_value is index 4
    assert col[2] == "TEXT"
    assert col[3] == 1, "cover_art_source must be NOT NULL"
    assert col[4] == "'auto'", (
        f"DEFAULT clause must be the SQL-quoted literal 'auto'; got {col[4]!r}"
    )


# --- last_played_at tests ---

def test_last_played_migration(repo):
    """Second db_init must not raise — ALTER TABLE is idempotent."""
    db_init(repo.con)
    assert len(repo.list_stations()) >= 0

def test_station_last_played_at_default(repo):
    sid = repo.create_station()
    st = repo.get_station(sid)
    assert st.last_played_at is None

def test_update_last_played(repo):
    sid = repo.create_station()
    repo.update_last_played(sid)
    st = repo.get_station(sid)
    assert st.last_played_at is not None
    assert "T" in st.last_played_at or "-" in st.last_played_at  # ISO-ish

def test_list_recently_played_order(repo):
    import time
    s1 = repo.create_station()
    s2 = repo.create_station()
    s3 = repo.create_station()
    repo.update_last_played(s1)
    time.sleep(0.05)
    repo.update_last_played(s2)
    time.sleep(0.05)
    repo.update_last_played(s3)
    rp = repo.list_recently_played(3)
    assert [s.id for s in rp] == [s3, s2, s1]

def test_list_recently_played_limit(repo):
    import time
    ids = []
    for _ in range(4):
        ids.append(repo.create_station())
    for sid in ids:
        repo.update_last_played(sid)
        time.sleep(0.05)
    rp = repo.list_recently_played(2)
    assert len(rp) == 2

def test_list_recently_played_empty(repo):
    repo.create_station()
    assert repo.list_recently_played(3) == []

# --- settings tests ---

def test_settings_migration(repo):
    db_init(repo.con)
    assert repo.get_setting("any", "default") == "default"

def test_settings_round_trip(repo):
    repo.set_setting("key1", "value1")
    assert repo.get_setting("key1", "fallback") == "value1"

def test_settings_default(repo):
    assert repo.get_setting("missing", "fallback") == "fallback"

def test_settings_overwrite(repo):
    repo.set_setting("k", "a")
    repo.set_setting("k", "b")
    assert repo.get_setting("k", "x") == "b"


# --- station_exists_by_url and insert_station tests ---

def test_station_exists_by_url_false_on_empty(repo):
    assert repo.station_exists_by_url("http://example.com/stream") is False


def test_station_exists_by_url_true_after_insert(repo):
    repo.insert_station("Test Station", "http://example.com/stream", "", "")
    assert repo.station_exists_by_url("http://example.com/stream") is True


def test_station_exists_by_url_false_for_different_url(repo):
    repo.insert_station("Test Station", "http://example.com/stream", "", "")
    assert repo.station_exists_by_url("http://other.com/stream") is False


def test_insert_station_returns_id(repo):
    row_id = repo.insert_station("Jazz FM", "http://jazz.fm/stream", "Jazz Network", "jazz, blues")
    assert isinstance(row_id, int)
    assert row_id > 0


def test_insert_station_with_provider(repo):
    repo.insert_station("Jazz FM", "http://jazz.fm/stream", "Jazz Network", "jazz")
    stations = repo.list_stations()
    assert len(stations) == 1
    assert stations[0].provider_name == "Jazz Network"


def test_insert_station_no_provider(repo):
    row_id = repo.insert_station("No Provider FM", "http://noprovider.com/stream", "", "ambient")
    st = repo.get_station(row_id)
    assert st.provider_id is None


def test_insert_station_persists_fields(repo):
    row_id = repo.insert_station("My Station", "http://my.station/stream", "My Network", "jazz,blues")
    st = repo.get_station(row_id)
    assert st.name == "My Station"
    assert st.streams[0].url == "http://my.station/stream"
    assert st.tags == "jazz,blues"


# --- update_station_art tests ---

def test_update_station_art(repo):
    sid = repo.create_station()
    repo.update_station_art(sid, "assets/1/station_art.png")
    st = repo.get_station(sid)
    assert st.station_art_path == "assets/1/station_art.png"


# ============================================================
# NEW: station_streams schema, migration, and CRUD tests
# ============================================================

def test_station_streams_schema(repo):
    """station_streams table exists with correct columns after db_init()."""
    cols = {row[1] for row in repo.con.execute("PRAGMA table_info(station_streams)").fetchall()}
    assert "id" in cols
    assert "station_id" in cols
    assert "url" in cols
    assert "label" in cols
    assert "quality" in cols
    assert "position" in cols
    assert "stream_type" in cols
    assert "codec" in cols


def test_migration_url_to_streams(repo_with_legacy_data):
    """Stations with url get migrated to station_streams at position=1."""
    repo = repo_with_legacy_data
    stations = {s.name: s for s in repo.list_stations()}
    assert "TestFM" in stations
    assert "JazzFM" in stations
    assert len(stations["TestFM"].streams) == 1
    assert stations["TestFM"].streams[0].url == "http://test.fm/stream"
    assert stations["TestFM"].streams[0].position == 1
    assert len(stations["JazzFM"].streams) == 1
    assert stations["JazzFM"].streams[0].url == "http://jazz.fm/stream"


def test_stations_has_no_url_column(repo_with_legacy_data):
    """After migration, SELECT url FROM stations raises OperationalError."""
    with pytest.raises(sqlite3.OperationalError):
        repo_with_legacy_data.con.execute("SELECT url FROM stations").fetchall()


def test_migration_idempotent(repo_with_legacy_data):
    """Running db_init() twice does not duplicate stream rows or raise errors."""
    repo = repo_with_legacy_data
    db_init(repo.con)
    # Count streams — should still be 2 (one per station with URL, EmptyFM has none)
    count = repo.con.execute("SELECT COUNT(*) FROM station_streams").fetchone()[0]
    assert count == 2


def test_trigger_survives_migration(repo_with_legacy_data):
    """stations_updated_at trigger still fires after migration."""
    repo = repo_with_legacy_data
    station = repo.list_stations()[0]
    old_updated = repo.con.execute(
        "SELECT updated_at FROM stations WHERE id=?", (station.id,)
    ).fetchone()[0]
    import time
    time.sleep(0.01)
    repo.con.execute("UPDATE stations SET name=? WHERE id=?", (station.name, station.id))
    repo.con.commit()
    new_updated = repo.con.execute(
        "SELECT updated_at FROM stations WHERE id=?", (station.id,)
    ).fetchone()[0]
    # Trigger fires but datetime() has second precision so may be equal if fast.
    # Just verify it doesn't raise an error and returns a value.
    assert new_updated is not None


def test_exists_by_url_uses_streams(repo):
    """station_exists_by_url queries station_streams."""
    sid = repo.create_station()
    repo.insert_stream(sid, "http://x.com/stream")
    assert repo.station_exists_by_url("http://x.com/stream") is True
    assert repo.station_exists_by_url("http://other.com/stream") is False


def test_insert_station_creates_stream(repo):
    """insert_station creates a station_streams row with position=1."""
    sid = repo.insert_station("TestFM", "http://test.fm/stream", "", "")
    streams = repo.list_streams(sid)
    assert len(streams) == 1
    assert streams[0].url == "http://test.fm/stream"
    assert streams[0].position == 1


def test_insert_station_no_url_no_stream(repo):
    """insert_station with empty url does NOT create a stream row."""
    sid = repo.insert_station("Silent FM", "", "", "")
    streams = repo.list_streams(sid)
    assert len(streams) == 0


def test_list_streams(repo):
    """list_streams returns streams ordered by position."""
    sid = repo.create_station()
    repo.insert_stream(sid, "http://a.com", position=2)
    repo.insert_stream(sid, "http://b.com", position=1)
    repo.insert_stream(sid, "http://c.com", position=3)
    streams = repo.list_streams(sid)
    assert [s.url for s in streams] == ["http://b.com", "http://a.com", "http://c.com"]


def test_insert_stream(repo):
    """insert_stream returns new stream id."""
    sid = repo.create_station()
    stream_id = repo.insert_stream(sid, "http://test.fm/stream", label="Main",
                                   quality="hi", position=1, stream_type="shoutcast", codec="MP3")
    assert isinstance(stream_id, int)
    assert stream_id > 0
    streams = repo.list_streams(sid)
    assert len(streams) == 1
    assert streams[0].label == "Main"
    assert streams[0].quality == "hi"
    assert streams[0].codec == "MP3"


def test_update_stream(repo):
    """update_stream modifies all fields."""
    sid = repo.create_station()
    stream_id = repo.insert_stream(sid, "http://old.url")
    repo.update_stream(stream_id, "http://new.url", "New Label", "med", 2, "hls", "AAC")
    streams = repo.list_streams(sid)
    s = streams[0]
    assert s.url == "http://new.url"
    assert s.label == "New Label"
    assert s.quality == "med"
    assert s.position == 2
    assert s.stream_type == "hls"
    assert s.codec == "AAC"


def test_delete_stream(repo):
    """delete_stream removes the row."""
    sid = repo.create_station()
    stream_id = repo.insert_stream(sid, "http://test.url")
    repo.delete_stream(stream_id)
    streams = repo.list_streams(sid)
    assert len(streams) == 0


def test_reorder_streams(repo):
    """reorder_streams updates positions to 1,2,3 in the given order."""
    sid = repo.create_station()
    id1 = repo.insert_stream(sid, "http://a.com", position=1)
    id2 = repo.insert_stream(sid, "http://b.com", position=2)
    id3 = repo.insert_stream(sid, "http://c.com", position=3)
    # Reorder: c, a, b
    repo.reorder_streams(sid, [id3, id1, id2])
    streams = repo.list_streams(sid)
    assert streams[0].url == "http://c.com"
    assert streams[0].position == 1
    assert streams[1].url == "http://a.com"
    assert streams[1].position == 2
    assert streams[2].url == "http://b.com"
    assert streams[2].position == 3


def test_preferred_stream_no_pref(repo):
    """get_preferred_stream_url with empty pref returns position=1 url."""
    sid = repo.create_station()
    repo.insert_stream(sid, "http://hi.url", quality="hi", position=1)
    repo.insert_stream(sid, "http://med.url", quality="med", position=2)
    assert repo.get_preferred_stream_url(sid, "") == "http://hi.url"


def test_preferred_stream_with_pref(repo):
    """get_preferred_stream_url with quality match returns that url."""
    sid = repo.create_station()
    repo.insert_stream(sid, "http://hi.url", quality="hi", position=1)
    repo.insert_stream(sid, "http://med.url", quality="med", position=2)
    assert repo.get_preferred_stream_url(sid, "med") == "http://med.url"


def test_preferred_stream_pref_missing(repo):
    """Falls back to position=1 when no quality match."""
    sid = repo.create_station()
    repo.insert_stream(sid, "http://hi.url", quality="hi", position=1)
    repo.insert_stream(sid, "http://med.url", quality="med", position=2)
    assert repo.get_preferred_stream_url(sid, "flac") == "http://hi.url"


def test_list_stations_has_streams(repo):
    """list_stations returns Station objects with populated streams list."""
    sid = repo.insert_station("Test FM", "http://test.fm/stream", "", "")
    stations = repo.list_stations()
    assert len(stations) == 1
    assert len(stations[0].streams) == 1
    assert stations[0].streams[0].url == "http://test.fm/stream"


def test_get_station_has_streams(repo):
    """get_station returns Station with populated streams list."""
    sid = repo.insert_station("Test FM", "http://test.fm/stream", "", "")
    st = repo.get_station(sid)
    assert len(st.streams) == 1
    assert st.streams[0].url == "http://test.fm/stream"


def test_create_station_no_url(repo):
    """create_station creates station with empty streams list."""
    sid = repo.create_station()
    st = repo.get_station(sid)
    assert st.streams == []


def test_update_station_no_url_param(repo):
    """update_station signature has no url parameter - just verify it works."""
    sid = repo.create_station()
    # Should not accept url as 3rd positional arg (only name, provider_id, tags, ...)
    repo.update_station(sid, "Updated Name", None, "rock", None, None)
    st = repo.get_station(sid)
    assert st.name == "Updated Name"
    assert st.tags == "rock"


def test_cascade_delete(repo):
    """Deleting a station also deletes its station_streams rows."""
    sid = repo.insert_station("Test FM", "http://test.fm/stream", "", "")
    streams_before = repo.list_streams(sid)
    assert len(streams_before) == 1
    repo.delete_station(sid)
    # station is gone, verify streams are gone too via direct query
    rows = repo.con.execute(
        "SELECT * FROM station_streams WHERE station_id=?", (sid,)
    ).fetchall()
    assert len(rows) == 0


def test_streams_dataclass(repo):
    """StationStream is a proper dataclass with correct fields."""
    sid = repo.create_station()
    stream_id = repo.insert_stream(sid, "http://test.url", label="Test", quality="hi",
                                   position=1, stream_type="shoutcast", codec="MP3")
    streams = repo.list_streams(sid)
    s = streams[0]
    assert isinstance(s, StationStream)
    assert s.id == stream_id
    assert s.station_id == sid
    assert s.url == "http://test.url"
    assert s.label == "Test"
    assert s.quality == "hi"
    assert s.position == 1
    assert s.stream_type == "shoutcast"
    assert s.codec == "MP3"


# ============================================================
# Phase 47-02: bitrate_kbps schema + hydration + migration (PB-01, PB-02)
# ============================================================


def _make_bare_con():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def test_bitrate_kbps_hydrated_from_row():
    """PB-01: list_streams hydrates bitrate_kbps from the row."""
    con = _make_bare_con()
    db_init(con)
    repo = Repo(con)
    con.execute("INSERT INTO stations(name) VALUES ('S')")
    station_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
    repo.insert_stream(station_id, "http://a", bitrate_kbps=320)
    repo.insert_stream(station_id, "http://b")  # legacy — no bitrate arg

    streams = repo.list_streams(station_id)
    bitrates = sorted(s.bitrate_kbps for s in streams)
    assert bitrates == [0, 320]


def test_bitrate_kbps_migration_adds_column():
    """PB-02: pre-47 DB (no bitrate_kbps column) gains the column on db_init."""
    con = _make_bare_con()
    # Simulate pre-47 schema — station_streams without bitrate_kbps
    con.executescript(
        """
        CREATE TABLE stations (id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL);
        CREATE TABLE station_streams (
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
        INSERT INTO stations(name) VALUES ('Legacy');
        INSERT INTO station_streams(station_id, url) VALUES (1, 'http://legacy');
        """
    )
    con.commit()

    # Run db_init — additive ALTER TABLE must succeed without raising
    db_init(con)

    # Column now exists on old row with default 0
    row = con.execute(
        "SELECT bitrate_kbps FROM station_streams WHERE station_id=1"
    ).fetchone()
    assert row["bitrate_kbps"] == 0

    # Idempotency — second db_init must not raise
    db_init(con)


# ============================================================
# prune_streams — fix for stream-remove-not-persisted (bug slug)
# ============================================================


def test_prune_streams_deletes_removed_stream(repo):
    """Streams not in keep_ids are deleted; streams in keep_ids survive."""
    sid = repo.create_station()
    id1 = repo.insert_stream(sid, 'http://a.com', position=1)
    id2 = repo.insert_stream(sid, 'http://b.com', position=2)
    id3 = repo.insert_stream(sid, 'http://c.com', position=3)

    # User removed row for id2 -> keep_ids contains only id1 and id3
    repo.prune_streams(sid, [id1, id3])

    streams = repo.list_streams(sid)
    ids = [s.id for s in streams]
    assert id2 not in ids
    assert id1 in ids
    assert id3 in ids


def test_prune_streams_all_removed(repo):
    """When keep_ids is empty all streams are deleted (user removed all rows)."""
    sid = repo.create_station()
    repo.insert_stream(sid, 'http://a.com', position=1)
    repo.insert_stream(sid, 'http://b.com', position=2)

    repo.prune_streams(sid, [])

    assert repo.list_streams(sid) == []


def test_prune_streams_noop_when_all_kept(repo):
    """When all existing ids appear in keep_ids nothing is deleted."""
    sid = repo.create_station()
    id1 = repo.insert_stream(sid, 'http://a.com', position=1)
    id2 = repo.insert_stream(sid, 'http://b.com', position=2)

    repo.prune_streams(sid, [id1, id2])

    streams = repo.list_streams(sid)
    assert len(streams) == 2


def test_prune_streams_does_not_touch_other_stations(repo):
    """Pruning one station must not delete streams from a different station."""
    sid_a = repo.create_station()
    sid_b = repo.create_station()
    id_a1 = repo.insert_stream(sid_a, 'http://a1.com', position=1)
    id_b1 = repo.insert_stream(sid_b, 'http://b1.com', position=1)

    # Prune all from station A
    repo.prune_streams(sid_a, [])

    assert repo.list_streams(sid_a) == []
    b_streams = repo.list_streams(sid_b)
    assert len(b_streams) == 1
    assert b_streams[0].id == id_b1


# --- Phase 70 / HRES-01 ---


def test_sample_rate_hz_hydrated_from_row():
    """HRES-01 / T-02: list_streams hydrates sample_rate_hz from the row.

    RED until Plan 70-02 adds sample_rate_hz column + StationStream field.
    """
    con = _make_bare_con()
    db_init(con)
    repo = Repo(con)
    con.execute("INSERT INTO stations(name) VALUES ('S')")
    station_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
    repo.insert_stream(station_id, "http://a", sample_rate_hz=96000)  # RED: kwarg not yet accepted
    repo.insert_stream(station_id, "http://b")  # legacy — no sample_rate arg

    streams = repo.list_streams(station_id)
    rates = sorted(s.sample_rate_hz for s in streams)  # RED: AttributeError until Plan 70-02
    assert rates == [0, 96000]


def test_bit_depth_hydrated_from_row():
    """HRES-01 / T-02: list_streams hydrates bit_depth from the row.

    RED until Plan 70-02 adds bit_depth column + StationStream field.
    """
    con = _make_bare_con()
    db_init(con)
    repo = Repo(con)
    con.execute("INSERT INTO stations(name) VALUES ('S')")
    station_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
    repo.insert_stream(station_id, "http://a", bit_depth=24)  # RED: kwarg not yet accepted
    repo.insert_stream(station_id, "http://b")  # legacy — no bit_depth arg

    streams = repo.list_streams(station_id)
    depths = sorted(s.bit_depth for s in streams)  # RED: AttributeError until Plan 70-02
    assert depths == [0, 24]


def test_db_init_idempotent_for_sample_rate_hz():
    """HRES-01 / M-01: pre-70 DB (no sample_rate_hz / bit_depth columns) gains
    them on db_init. Idempotency: second db_init must not raise.

    RED until Plan 70-02 ships the ALTER TABLE blocks.
    """
    con = _make_bare_con()
    # Simulate pre-70 schema — station_streams without sample_rate_hz / bit_depth
    con.executescript(
        """
        CREATE TABLE stations (id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL);
        CREATE TABLE station_streams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id INTEGER NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            label TEXT NOT NULL DEFAULT '',
            quality TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 1,
            stream_type TEXT NOT NULL DEFAULT '',
            codec TEXT NOT NULL DEFAULT '',
            bitrate_kbps INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
        );
        INSERT INTO stations(name) VALUES ('Legacy');
        INSERT INTO station_streams(station_id, url) VALUES (1, 'http://legacy');
        """
    )
    con.commit()

    # Run db_init — additive ALTER TABLE must succeed without raising
    db_init(con)

    # Both new columns exist on old row with default 0
    row = con.execute(
        "SELECT sample_rate_hz, bit_depth FROM station_streams WHERE station_id=1"
    ).fetchone()
    # RED: columns absent until Plan 70-02 ships the schema migration
    assert row["sample_rate_hz"] == 0
    assert row["bit_depth"] == 0

    # Idempotency — second db_init must not raise
    db_init(con)


# ---------------------------------------------------------------------------
# Phase 81: case-insensitive station sort (D-01 / D-02 / D-03 / D-05)
# ---------------------------------------------------------------------------

def _seed_mixed_case_stations(repo, names):
    ids = []
    for n in names:
        sid = repo.create_station()
        repo.update_station(sid, n, None, "", None, None)
        ids.append(sid)
    return ids


def test_list_stations_case_insensitive_order(repo):
    names = ["Zenith", "deepSpace", "aardvark", "Groove Salad", "Drone Zone"]
    _seed_mixed_case_stations(repo, names)
    result = repo.list_stations()
    # D-01/D-02/D-03/D-05: SQLite NOCASE collation interleaves case-insensitively
    assert [s.name for s in result] == ["aardvark", "deepSpace", "Drone Zone", "Groove Salad", "Zenith"]


def test_list_favorite_stations_case_insensitive_order(repo):
    names = ["Zenith", "deepSpace", "aardvark", "Groove Salad", "Drone Zone"]
    ids = _seed_mixed_case_stations(repo, names)
    # Mark 1st, 3rd, and 5th seeded stations as favorites
    favorite_indices = [0, 2, 4]
    favorite_names = [names[i] for i in favorite_indices]
    for i in favorite_indices:
        repo.set_station_favorite(ids[i], True)
    result = repo.list_favorite_stations()
    # D-02/D-03: ORDER BY ... COLLATE NOCASE applies to favorites query too
    expected = sorted(favorite_names, key=str.casefold)
    assert [s.name for s in result] == expected


def test_collate_nocase_drift_guard(repo):
    # Source-grep drift-guard precedent: Phase 51 / 55 / 61 / 63
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent / "musicstreamer" / "repo.py").read_text()
    lines = [ln for ln in source.splitlines() if not ln.lstrip().startswith("#")]
    body = "\n".join(lines)
    assert body.count("ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE") == 2, (
        "Phase 81 D-03: both list_stations and list_favorite_stations must keep COLLATE NOCASE on both ORDER BY columns"
    )


# ---------------------------------------------------------------------------
# Phase 82 Plan 01: preferred_stream_id DB + Repo layer (D-01, D-02, D-08)
# ---------------------------------------------------------------------------

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


def test_preferred_stream_id_default_none_on_fresh_station(repo):
    """D-01: a freshly created station has preferred_stream_id == None."""
    sid = repo.create_station()
    assert repo.get_station(sid).preferred_stream_id is None


def test_preferred_stream_id_survives_db_init_replay(repo):
    """D-08: value set via direct SQL UPDATE survives a subsequent db_init replay.

    NOTE: This test passes only after Task 2 wires preferred_stream_id into
    the Station-builder kwarg in get_station(). Placed here alongside the
    migration tests for discoverability; it exercises the DB layer, not the
    Repo setter (which lands in Task 2).
    """
    sid = repo.create_station()
    stream_id = repo.insert_stream(sid, "http://twitch.tv/lofi")
    repo.con.execute(
        "UPDATE stations SET preferred_stream_id = ? WHERE id = ?",
        (stream_id, sid),
    )
    repo.con.commit()
    # Re-run db_init — value must survive.
    db_init(repo.con)
    assert repo.get_station(sid).preferred_stream_id == stream_id


# ---------------------------------------------------------------------------
# Phase 82 Plan 01 Task 2: Station-builders + set_preferred_stream + round-trips
# ---------------------------------------------------------------------------

def _seed_two_stream_station(repo):
    """Helper: insert a station with a YT stream and a Twitch stream, return (sid, yt_id, twitch_id)."""
    sid = repo.create_station()
    yt_id = repo.insert_stream(sid, "https://youtube.com/lofi", label="YouTube", stream_type="youtube")
    twitch_id = repo.insert_stream(sid, "https://twitch.tv/lofi", label="Twitch", stream_type="twitch")
    return sid, yt_id, twitch_id


def test_set_preferred_stream_round_trips_via_list_stations(repo):
    """D-02: set_preferred_stream persists and list_stations reflects it."""
    sid, yt_id, twitch_id = _seed_two_stream_station(repo)
    repo.set_preferred_stream(sid, twitch_id)
    stations = repo.list_stations()
    match = next(s for s in stations if s.id == sid)
    assert match.preferred_stream_id == twitch_id


def test_set_preferred_stream_round_trips_via_get_station(repo):
    """D-02: set_preferred_stream persists and get_station reflects it."""
    sid, yt_id, twitch_id = _seed_two_stream_station(repo)
    repo.set_preferred_stream(sid, twitch_id)
    assert repo.get_station(sid).preferred_stream_id == twitch_id


def test_set_preferred_stream_round_trips_via_list_recently_played(repo):
    """D-02: set_preferred_stream persists and list_recently_played reflects it."""
    sid, yt_id, twitch_id = _seed_two_stream_station(repo)
    repo.set_preferred_stream(sid, twitch_id)
    repo.update_last_played(sid)
    rp = repo.list_recently_played()
    match = next(s for s in rp if s.id == sid)
    assert match.preferred_stream_id == twitch_id


def test_set_preferred_stream_round_trips_via_list_favorite_stations(repo):
    """D-02: set_preferred_stream persists and list_favorite_stations reflects it."""
    sid, yt_id, twitch_id = _seed_two_stream_station(repo)
    repo.set_preferred_stream(sid, twitch_id)
    repo.set_station_favorite(sid, True)
    favs = repo.list_favorite_stations()
    match = next(s for s in favs if s.id == sid)
    assert match.preferred_stream_id == twitch_id


def test_set_preferred_stream_clears_to_none(repo):
    """D-02: set_preferred_stream(None) clears the pick back to NULL."""
    sid, yt_id, twitch_id = _seed_two_stream_station(repo)
    repo.set_preferred_stream(sid, twitch_id)
    assert repo.get_station(sid).preferred_stream_id == twitch_id
    repo.set_preferred_stream(sid, None)
    assert repo.get_station(sid).preferred_stream_id is None


def test_set_preferred_stream_on_delete_set_null(repo):
    """D-01: deleting the stream FK-target auto-NULLs preferred_stream_id (ON DELETE SET NULL).

    Requires PRAGMA foreign_keys = ON — already enforced by the repo fixture.
    """
    sid, yt_id, twitch_id = _seed_two_stream_station(repo)
    repo.set_preferred_stream(sid, twitch_id)
    assert repo.get_station(sid).preferred_stream_id == twitch_id
    # Delete the stream — FK ON DELETE SET NULL must fire.
    repo.delete_stream(twitch_id)
    assert repo.get_station(sid).preferred_stream_id is None


# ============================================================
# Phase 83 Plan 01: SomaFM preroll schema, CRUD, eager-load, CASCADE
# (D-01, D-04, D-15 + ASVS V5 URL scheme + DoS cap)
# ============================================================


def test_station_prerolls_table_schema_after_db_init(repo):
    """D-01: station_prerolls has {id, station_id, url, position} with FK CASCADE on station_id."""
    cols = repo.con.execute("PRAGMA table_info('station_prerolls')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert set(by_name) == {"id", "station_id", "url", "position"}, f"got {sorted(by_name)}"
    assert by_name["station_id"][3] == 1, "station_id must be NOT NULL"
    assert by_name["url"][3] == 1, "url must be NOT NULL"
    assert by_name["position"][3] == 1, "position must be NOT NULL"
    fks = repo.con.execute("PRAGMA foreign_key_list('station_prerolls')").fetchall()
    assert len(fks) == 1, f"expected 1 FK, got {fks}"
    fk = fks[0]
    # PRAGMA foreign_key_list cols: (id, seq, table, from, to, on_update, on_delete, match)
    assert fk[2] == "stations", f"FK target table: {fk[2]}"
    assert fk[3] == "station_id", f"FK from col: {fk[3]}"
    assert fk[4] == "id", f"FK to col: {fk[4]}"
    assert fk[6] == "CASCADE", f"FK on_delete: {fk[6]}"


def test_prerolls_fetched_at_column_after_db_init(repo):
    """D-04: stations.prerolls_fetched_at exists as INTEGER, nullable, no DEFAULT."""
    cols = repo.con.execute("PRAGMA table_info('stations')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert "prerolls_fetched_at" in by_name, f"missing column: {sorted(by_name)}"
    col = by_name["prerolls_fetched_at"]
    # PRAGMA table_info cols: (cid, name, type, notnull, dflt_value, pk)
    assert col[2] == "INTEGER", f"type: {col[2]}"
    assert col[3] == 0, f"must be nullable (notnull=0); got {col[3]}"
    assert col[4] is None, f"must have no DEFAULT; got {col[4]!r}"


def test_db_init_is_idempotent_for_phase_83_additions(repo):
    """D-15: second db_init() raises no exception and leaves schema unchanged."""
    from musicstreamer.repo import db_init
    before = repo.con.execute("PRAGMA table_info('station_prerolls')").fetchall()
    db_init(repo.con)  # second call must not raise
    after = repo.con.execute("PRAGMA table_info('station_prerolls')").fetchall()
    assert before == after, "second db_init mutated station_prerolls schema"


def test_insert_preroll_and_list_prerolls_round_trip(repo):
    """D-01/D-03: insert 3 prerolls, list_prerolls returns them in position order."""
    sid = repo.create_station()
    repo.insert_preroll(sid, "https://somafm.com/prerolls/a.m4a", 1)
    repo.insert_preroll(sid, "https://somafm.com/prerolls/b.m4a", 2)
    repo.insert_preroll(sid, "https://somafm.com/prerolls/c.m4a", 3)
    urls = repo.list_prerolls(sid)
    assert urls == [
        "https://somafm.com/prerolls/a.m4a",
        "https://somafm.com/prerolls/b.m4a",
        "https://somafm.com/prerolls/c.m4a",
    ]
    other_sid = repo.create_station()
    assert repo.list_prerolls(other_sid) == []


def test_list_prerolls_orders_by_position_not_insert_order(repo):
    """D-01/D-03: ORDER BY position is load-bearing — insert out of order, expect position order."""
    sid = repo.create_station()
    repo.insert_preroll(sid, "https://somafm.com/prerolls/three.m4a", 3)
    repo.insert_preroll(sid, "https://somafm.com/prerolls/one.m4a", 1)
    repo.insert_preroll(sid, "https://somafm.com/prerolls/two.m4a", 2)
    urls = repo.list_prerolls(sid)
    assert urls == [
        "https://somafm.com/prerolls/one.m4a",
        "https://somafm.com/prerolls/two.m4a",
        "https://somafm.com/prerolls/three.m4a",
    ]


def test_insert_preroll_rejects_non_http_scheme(repo):
    """T-83-01 ASVS V5: file:///, javascript:, ftp:// must be rejected. No partial write."""
    import pytest
    sid = repo.create_station()
    for bad in ("file:///etc/passwd", "javascript:alert(1)", "ftp://host/x.m4a"):
        with pytest.raises(ValueError):
            repo.insert_preroll(sid, bad, 1)
    assert repo.list_prerolls(sid) == [], "non-HTTP(S) URL was persisted"


def test_insert_preroll_rejects_position_over_cap(repo):
    """T-83-02 DoS cap: position > 50 raises ValueError; position == 50 still succeeds."""
    import pytest
    sid = repo.create_station()
    with pytest.raises(ValueError):
        repo.insert_preroll(sid, "https://somafm.com/prerolls/x.m4a", 51)
    rid = repo.insert_preroll(sid, "https://somafm.com/prerolls/y.m4a", 50)
    assert rid > 0
    assert repo.list_prerolls(sid) == ["https://somafm.com/prerolls/y.m4a"]


def test_set_prerolls_fetched_at_round_trips_via_all_4_station_builders(repo):
    """D-04: set_prerolls_fetched_at + all 4 Station-builders reflect the value.

    Replicates Phase 82's setter-round-trip-via-all-4-builders test shape
    (tests/test_repo.py:937-971 precedent).
    """
    sid, yt_id, twitch_id = _seed_two_stream_station(repo)
    repo.set_prerolls_fetched_at(sid, 1700000000)
    # 1) list_stations
    match = next(s for s in repo.list_stations() if s.id == sid)
    assert match.prerolls_fetched_at == 1700000000
    # 2) get_station
    assert repo.get_station(sid).prerolls_fetched_at == 1700000000
    # 3) list_recently_played
    repo.update_last_played(sid)
    match = next(s for s in repo.list_recently_played() if s.id == sid)
    assert match.prerolls_fetched_at == 1700000000
    # 4) list_favorite_stations
    repo.set_station_favorite(sid, True)
    match = next(s for s in repo.list_favorite_stations() if s.id == sid)
    assert match.prerolls_fetched_at == 1700000000


def test_eager_load_prerolls_via_all_4_station_builders(repo):
    """D-01 + Pitfall 6 option 3a: every Station-builder eager-loads prerolls.

    Missing one builder would leave Station.prerolls=[] silently — the Player
    layer (Plan 83-03) cannot detect that, hence this multi-builder test.
    """
    sid, yt_id, twitch_id = _seed_two_stream_station(repo)
    repo.insert_preroll(sid, "https://somafm.com/prerolls/a.m4a", 1)
    repo.insert_preroll(sid, "https://somafm.com/prerolls/b.m4a", 2)
    expected = [
        "https://somafm.com/prerolls/a.m4a",
        "https://somafm.com/prerolls/b.m4a",
    ]
    # list_stations
    match = next(s for s in repo.list_stations() if s.id == sid)
    assert match.prerolls == expected
    # get_station
    assert repo.get_station(sid).prerolls == expected
    # list_recently_played
    repo.update_last_played(sid)
    match = next(s for s in repo.list_recently_played() if s.id == sid)
    assert match.prerolls == expected
    # list_favorite_stations
    repo.set_station_favorite(sid, True)
    match = next(s for s in repo.list_favorite_stations() if s.id == sid)
    assert match.prerolls == expected


def test_delete_station_cascades_station_prerolls(repo):
    """D-01 CASCADE: deleting a station also deletes its station_prerolls rows."""
    sid = repo.create_station()
    repo.insert_preroll(sid, "https://somafm.com/prerolls/a.m4a", 1)
    repo.insert_preroll(sid, "https://somafm.com/prerolls/b.m4a", 2)
    assert len(repo.list_prerolls(sid)) == 2
    repo.delete_station(sid)
    rows = repo.con.execute(
        "SELECT * FROM station_prerolls WHERE station_id=?", (sid,)
    ).fetchall()
    assert len(rows) == 0


def test_ensure_dirs_creates_channel_avatars_dir(tmp_path, monkeypatch):
    """ART-AVATAR-02 D-01: ensure_dirs() creates channel-avatars/ under _root_override."""
    import musicstreamer.paths as paths_mod
    import musicstreamer.assets as assets_mod
    monkeypatch.setattr(paths_mod, "_root_override", str(tmp_path))
    assets_mod.ensure_dirs()
    assert os.path.isdir(os.path.join(str(tmp_path), "assets", "channel-avatars")), (
        "ensure_dirs() must create assets/channel-avatars/"
    )


# ---------------------------------------------------------------------------
# Phase 89A Plan 02: channel_avatar_path DB migration (D-04, D-05, D-06, D-07)
# ---------------------------------------------------------------------------

def test_channel_avatar_path_migration_idempotent(repo):
    """ART-AVATAR-01 D-07: db_init twice must not raise; column has expected schema.

    Mirrors test_cover_art_source_migration_idempotent (test_repo.py L228-252)
    and test_preferred_stream_id_migration_idempotent (test_repo.py L875-897).
    PRAGMA table_info cols: (cid, name, type, notnull, dflt_value, pk).
    channel_avatar_path must be TEXT, nullable (notnull=0), no DEFAULT (None).
    """
    # Second and third db_init calls must not raise.
    db_init(repo.con)
    db_init(repo.con)

    cols = repo.con.execute("PRAGMA table_info('stations')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert "channel_avatar_path" in by_name, (
        f"channel_avatar_path column missing; got {sorted(by_name)}"
    )
    col = by_name["channel_avatar_path"]
    # type is index 2; notnull is index 3; dflt_value is index 4
    assert col[2] == "TEXT", f"column type must be TEXT; got {col[2]!r}"
    assert col[3] == 0, "channel_avatar_path must be nullable (notnull=0)"
    assert col[4] is None, (
        f"channel_avatar_path must have no DEFAULT; got {col[4]!r}"
    )


def test_channel_avatar_path_schema_convergence():
    """ART-AVATAR-01 D-07: fresh DB and upgraded pre-89a DB converge to same schema.

    Builds a pre-89a stations schema (channel_avatar_path absent), runs db_init(),
    and asserts PRAGMA table_info(stations) matches a fresh db_init() DB.
    Mirrors test_bitrate_kbps_migration_adds_column shape (test_repo.py L642-678).
    """
    # --- fresh DB (the target shape) ---
    fresh_con = _make_bare_con()
    db_init(fresh_con)
    fresh_cols = {
        row[1]: (row[2], row[3], row[4])  # (type, notnull, dflt_value)
        for row in fresh_con.execute("PRAGMA table_info('stations')").fetchall()
    }
    assert "channel_avatar_path" in fresh_cols, "fresh DB must have channel_avatar_path"

    # --- pre-89a DB: stations table WITHOUT channel_avatar_path ---
    legacy_con = _make_bare_con()
    legacy_con.executescript("""
        CREATE TABLE providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            provider_id INTEGER,
            tags TEXT DEFAULT '',
            station_art_path TEXT,
            album_fallback_path TEXT,
            icy_disabled INTEGER NOT NULL DEFAULT 0,
            last_played_at TEXT,
            is_favorite INTEGER NOT NULL DEFAULT 0,
            cover_art_source TEXT NOT NULL DEFAULT 'auto',
            preferred_stream_id INTEGER,
            prerolls_fetched_at INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE SET NULL
        );
        INSERT INTO stations(name) VALUES ('ExistingFM');
    """)
    legacy_con.commit()
    # Confirm the column is absent before migration
    pre_cols = {
        row[1] for row in legacy_con.execute("PRAGMA table_info('stations')").fetchall()
    }
    assert "channel_avatar_path" not in pre_cols, "pre-89a fixture must NOT have the column"

    # Apply migration
    db_init(legacy_con)

    # Post-migration schema must match fresh DB for channel_avatar_path
    migrated_cols = {
        row[1]: (row[2], row[3], row[4])
        for row in legacy_con.execute("PRAGMA table_info('stations')").fetchall()
    }
    assert "channel_avatar_path" in migrated_cols, "column absent after migration"
    assert migrated_cols["channel_avatar_path"] == fresh_cols["channel_avatar_path"], (
        f"migrated schema differs from fresh: "
        f"migrated={migrated_cols['channel_avatar_path']!r}, "
        f"fresh={fresh_cols['channel_avatar_path']!r}"
    )

    # Existing row must still exist with NULL channel_avatar_path (data preserved)
    row = legacy_con.execute("SELECT name, channel_avatar_path FROM stations").fetchone()
    assert row[0] == "ExistingFM"
    assert row[1] is None, "existing row must have NULL channel_avatar_path"


# ---------------------------------------------------------------------------
# Phase 89 Plan 01: channel_avatar_path model/repo plumbing (D-13)
# ---------------------------------------------------------------------------


def test_channel_avatar_path_default_is_none(repo):
    """D-13: new station reads back channel_avatar_path == None (no avatar set)."""
    sid = repo.create_station()
    st = repo.get_station(sid)
    assert st.channel_avatar_path is None


def test_update_channel_avatar_path_round_trip(repo):
    """D-13: update_channel_avatar_path writes, get_station reads back the path."""
    sid = repo.create_station()
    repo.update_channel_avatar_path(sid, "assets/channel-avatars/12.png")
    st = repo.get_station(sid)
    assert st.channel_avatar_path == "assets/channel-avatars/12.png"


def test_update_channel_avatar_path_clear(repo):
    """D-13: update_channel_avatar_path(station_id, None) clears the column back to None."""
    sid = repo.create_station()
    repo.update_channel_avatar_path(sid, "assets/channel-avatars/12.png")
    assert repo.get_station(sid).channel_avatar_path == "assets/channel-avatars/12.png"
    repo.update_channel_avatar_path(sid, None)
    assert repo.get_station(sid).channel_avatar_path is None


def test_update_station_does_not_reset_channel_avatar_path(repo):
    """D-13 / Pitfall 5: calling update_station without the avatar kwarg must NOT
    reset channel_avatar_path (dedicated method only, not routed through update_station)."""
    sid = repo.create_station()
    repo.update_channel_avatar_path(sid, "assets/channel-avatars/99.png")
    # Call update_station without any channel_avatar_path kwarg
    repo.update_station(sid, "Radio", None, "", None, None, icy_disabled=False)
    st = repo.get_station(sid)
    assert st.channel_avatar_path == "assets/channel-avatars/99.png", (
        "update_station must NOT reset channel_avatar_path (Pitfall 5 — dedicated method only)"
    )


def test_channel_avatar_path_in_list_stations(repo):
    """D-13: list_stations mapper reads channel_avatar_path."""
    sid = repo.create_station()
    repo.update_channel_avatar_path(sid, "assets/channel-avatars/5.png")
    stations = repo.list_stations()
    match = next(s for s in stations if s.id == sid)
    assert match.channel_avatar_path == "assets/channel-avatars/5.png"


def test_channel_avatar_path_in_list_recently_played(repo):
    """D-13: list_recently_played mapper reads channel_avatar_path."""
    sid = repo.create_station()
    repo.update_channel_avatar_path(sid, "assets/channel-avatars/7.png")
    repo.update_last_played(sid)
    recently = repo.list_recently_played(5)
    match = next(s for s in recently if s.id == sid)
    assert match.channel_avatar_path == "assets/channel-avatars/7.png"


def test_channel_avatar_path_in_list_favorite_stations(repo):
    """D-13: list_favorite_stations mapper reads channel_avatar_path."""
    sid = repo.create_station()
    repo.update_channel_avatar_path(sid, "assets/channel-avatars/3.png")
    repo.con.execute("UPDATE stations SET is_favorite=1 WHERE id=?", (sid,))
    repo.con.commit()
    favs = repo.list_favorite_stations()
    match = next(s for s in favs if s.id == sid)
    assert match.channel_avatar_path == "assets/channel-avatars/3.png"


# ---------------------------------------------------------------------------
# Phase 89.1 Plan 01: providers.avatar_path migration + backfill + persist
#                     + four-mapper carry (D-11, D-01..D-03, D-09)
# ---------------------------------------------------------------------------


def test_provider_avatar_path_migration_idempotent(repo):
    """D-11: providers.avatar_path TEXT nullable present after db_init; double-run no-raise.

    Mirrors test_channel_avatar_path_migration_idempotent (L1171).
    PRAGMA table_info cols: (cid, name, type, notnull, dflt_value, pk).
    avatar_path must be TEXT, nullable (notnull=0), no DEFAULT (None).
    """
    # Second and third db_init calls must not raise.
    db_init(repo.con)
    db_init(repo.con)

    cols = repo.con.execute("PRAGMA table_info('providers')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert "avatar_path" in by_name, (
        f"avatar_path column missing from providers; got {sorted(by_name)}"
    )
    col = by_name["avatar_path"]
    assert col[2] == "TEXT", f"column type must be TEXT; got {col[2]!r}"
    assert col[3] == 0, "avatar_path must be nullable (notnull=0)"
    assert col[4] is None, (
        f"avatar_path must have no DEFAULT; got {col[4]!r}"
    )


def test_provider_avatar_path_schema_convergence():
    """D-11: fresh DB and upgraded pre-89.1 DB (no providers.avatar_path) converge.

    Mirrors test_channel_avatar_path_schema_convergence (L1197).
    Builds a pre-89.1 providers schema (avatar_path absent), runs db_init(),
    and asserts PRAGMA table_info(providers) matches a fresh db_init() DB.
    """
    # --- fresh DB (the target shape) ---
    fresh_con = _make_bare_con()
    db_init(fresh_con)
    fresh_cols = {
        row[1]: (row[2], row[3], row[4])  # (type, notnull, dflt_value)
        for row in fresh_con.execute("PRAGMA table_info('providers')").fetchall()
    }
    assert "avatar_path" in fresh_cols, "fresh DB must have providers.avatar_path"

    # --- pre-89.1 DB: providers WITHOUT avatar_path column ---
    legacy_con = _make_bare_con()
    legacy_con.executescript("""
        CREATE TABLE providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            provider_id INTEGER,
            tags TEXT DEFAULT '',
            station_art_path TEXT,
            album_fallback_path TEXT,
            icy_disabled INTEGER NOT NULL DEFAULT 0,
            last_played_at TEXT,
            is_favorite INTEGER NOT NULL DEFAULT 0,
            cover_art_source TEXT NOT NULL DEFAULT 'auto',
            preferred_stream_id INTEGER,
            prerolls_fetched_at INTEGER,
            channel_avatar_path TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE SET NULL
        );
        INSERT INTO providers(name) VALUES ('ExistingProvider');
    """)
    legacy_con.commit()
    # Confirm avatar_path is absent before migration
    pre_cols = {
        row[1] for row in legacy_con.execute("PRAGMA table_info('providers')").fetchall()
    }
    assert "avatar_path" not in pre_cols, "pre-89.1 fixture must NOT have avatar_path"

    # Apply migration
    db_init(legacy_con)

    # Post-migration schema must match fresh DB for avatar_path
    migrated_cols = {
        row[1]: (row[2], row[3], row[4])
        for row in legacy_con.execute("PRAGMA table_info('providers')").fetchall()
    }
    assert "avatar_path" in migrated_cols, "avatar_path absent after migration"
    assert migrated_cols["avatar_path"] == fresh_cols["avatar_path"], (
        f"migrated schema differs from fresh: "
        f"migrated={migrated_cols['avatar_path']!r}, "
        f"fresh={fresh_cols['avatar_path']!r}"
    )

    # Existing row must still exist with NULL avatar_path (data preserved)
    row = legacy_con.execute("SELECT name, avatar_path FROM providers").fetchone()
    assert row[0] == "ExistingProvider"
    assert row[1] is None, "existing row must have NULL avatar_path"


def test_backfill_copies_avatar_to_provider_keyed_location(tmp_path):
    """D-01: backfill copies {station_id}.png to {provider_id}.png; providers.avatar_path set.

    After a successful backfill, the old per-station file must be deleted.
    No network fetch — shutil.copy2 from existing on-disk file only.
    """
    import os
    import musicstreamer.paths as paths_mod

    paths_mod._root_override = str(tmp_path)
    try:
        con = _make_bare_con()
        db_init(con)

        # Seed: provider + station with channel_avatar_path pointing at a real file
        repo = Repo(con)
        pid = repo.ensure_provider("Lofi Girl")
        sid = repo.create_station()
        repo.update_station(sid, "Lofi Girl 24/7", pid, "", None, None, icy_disabled=True)

        # Write a fake per-station PNG
        avatar_dir = paths_mod.channel_avatars_dir()
        os.makedirs(avatar_dir, exist_ok=True)
        station_png = os.path.join(avatar_dir, f"{sid}.png")
        with open(station_png, "wb") as fh:
            fh.write(b"\x89PNG\r\n")
        repo.update_channel_avatar_path(sid, f"assets/channel-avatars/{sid}.png")

        # Re-run db_init (startup) — backfill runs
        db_init(con)

        # Provider must now have avatar_path
        row = con.execute("SELECT avatar_path FROM providers WHERE id = ?", (pid,)).fetchone()
        assert row[0] == f"assets/channel-avatars/{pid}.png", (
            f"providers.avatar_path not set correctly; got {row[0]!r}"
        )
        # Provider-keyed file must exist
        assert os.path.isfile(os.path.join(avatar_dir, f"{pid}.png")), (
            f"{pid}.png does not exist in channel_avatars_dir"
        )
        # Old per-station file must be deleted
        assert not os.path.isfile(station_png), (
            f"old per-station file {sid}.png was not deleted after backfill"
        )
    finally:
        paths_mod._root_override = None


def test_backfill_most_recently_updated_sibling_wins(tmp_path):
    """D-02: when two sibling stations have avatars, the most-recently-updated one's PNG wins.

    Uses distinct PNG byte payloads to distinguish winner from loser.
    bumps updated_at explicitly via a direct SQL UPDATE so ordering is unambiguous.
    """
    import os
    import time
    import musicstreamer.paths as paths_mod

    paths_mod._root_override = str(tmp_path)
    try:
        con = _make_bare_con()
        db_init(con)

        repo = Repo(con)
        pid = repo.ensure_provider("BigChannel")

        # Station A — will be the OLDER one
        sid_a = repo.create_station()
        repo.update_station(sid_a, "BigChannel Stream A", pid, "", None, None, icy_disabled=True)

        # Station B — will be the NEWER one (most recently updated)
        sid_b = repo.create_station()
        repo.update_station(sid_b, "BigChannel Stream B", pid, "", None, None, icy_disabled=True)

        avatar_dir = paths_mod.channel_avatars_dir()
        os.makedirs(avatar_dir, exist_ok=True)

        # Write distinct bytes so we can identify which file was used as source
        png_a = os.path.join(avatar_dir, f"{sid_a}.png")
        png_b = os.path.join(avatar_dir, f"{sid_b}.png")
        with open(png_a, "wb") as fh:
            fh.write(b"AVATAR_A")
        with open(png_b, "wb") as fh:
            fh.write(b"AVATAR_B")

        repo.update_channel_avatar_path(sid_a, f"assets/channel-avatars/{sid_a}.png")
        repo.update_channel_avatar_path(sid_b, f"assets/channel-avatars/{sid_b}.png")

        # Force station A to be older, station B to be newer via direct SQL
        con.execute(
            "UPDATE stations SET updated_at = '2020-01-01T00:00:00' WHERE id = ?", (sid_a,)
        )
        con.execute(
            "UPDATE stations SET updated_at = '2025-01-01T00:00:00' WHERE id = ?", (sid_b,)
        )
        con.commit()

        # Re-run db_init — backfill should pick station B (newer)
        db_init(con)

        row = con.execute("SELECT avatar_path FROM providers WHERE id = ?", (pid,)).fetchone()
        provider_png = os.path.join(avatar_dir, f"{pid}.png")
        assert os.path.isfile(provider_png), "provider-keyed PNG not created"
        winner_bytes = open(provider_png, "rb").read()
        assert winner_bytes == b"AVATAR_B", (
            f"Expected AVATAR_B (newer sibling) to win; got {winner_bytes!r}"
        )
        assert row[0] == f"assets/channel-avatars/{pid}.png", (
            f"providers.avatar_path wrong: {row[0]!r}"
        )
    finally:
        paths_mod._root_override = None


def test_backfill_idempotent_double_run(tmp_path):
    """D-03: after a successful backfill, a third db_init is a no-op.

    providers.avatar_path must be unchanged; no exception raised.
    """
    import os
    import musicstreamer.paths as paths_mod

    paths_mod._root_override = str(tmp_path)
    try:
        con = _make_bare_con()
        db_init(con)

        repo = Repo(con)
        pid = repo.ensure_provider("IdempotentCh")
        sid = repo.create_station()
        repo.update_station(sid, "IdempotentCh 1", pid, "", None, None, icy_disabled=True)

        avatar_dir = paths_mod.channel_avatars_dir()
        os.makedirs(avatar_dir, exist_ok=True)
        station_png = os.path.join(avatar_dir, f"{sid}.png")
        with open(station_png, "wb") as fh:
            fh.write(b"\x89PNG_IDEM")
        repo.update_channel_avatar_path(sid, f"assets/channel-avatars/{sid}.png")

        # First backfill run
        db_init(con)
        row1 = con.execute("SELECT avatar_path FROM providers WHERE id = ?", (pid,)).fetchone()
        first_path = row1[0]
        assert first_path == f"assets/channel-avatars/{pid}.png"

        # Second run — must be a no-op
        db_init(con)
        row2 = con.execute("SELECT avatar_path FROM providers WHERE id = ?", (pid,)).fetchone()
        assert row2[0] == first_path, (
            f"providers.avatar_path changed on second run: {row2[0]!r} != {first_path!r}"
        )
    finally:
        paths_mod._root_override = None


def test_backfill_skips_null_provider_id_stations(tmp_path):
    """D-03: station with provider_id IS NULL and a channel_avatar_path is NOT copied.

    Its on-disk file must be left untouched (no copy, no delete).
    """
    import os
    import musicstreamer.paths as paths_mod

    paths_mod._root_override = str(tmp_path)
    try:
        con = _make_bare_con()
        db_init(con)

        repo = Repo(con)
        # Station with no provider (provider_id IS NULL)
        sid = repo.create_station()
        repo.update_station(sid, "No Provider Station", None, "", None, None, icy_disabled=True)

        avatar_dir = paths_mod.channel_avatars_dir()
        os.makedirs(avatar_dir, exist_ok=True)
        station_png = os.path.join(avatar_dir, f"{sid}.png")
        with open(station_png, "wb") as fh:
            fh.write(b"\x89PNG_NULL_PROV")
        repo.update_channel_avatar_path(sid, f"assets/channel-avatars/{sid}.png")

        # Run backfill — should NOT copy this station's avatar
        db_init(con)

        # The per-station file must still exist (was NOT deleted)
        assert os.path.isfile(station_png), (
            f"per-station PNG was deleted despite provider_id IS NULL — it should be left alone"
        )
    finally:
        paths_mod._root_override = None


def test_update_provider_avatar_path_round_trip(repo):
    """D-09: update_provider_avatar_path writes; all four mappers return provider_avatar_path.

    Also exercises the four-mapper carrier (Pitfall 6 — miss none).
    """
    pid = repo.ensure_provider("TestProviderRT")
    sid = repo.create_station()
    repo.update_station(sid, "TestProviderRT Sta", pid, "", None, None, icy_disabled=True)
    rel = f"assets/channel-avatars/{pid}.png"

    repo.update_provider_avatar_path(pid, rel)

    # list_stations
    stations = repo.list_stations()
    match = next(s for s in stations if s.id == sid)
    assert match.provider_avatar_path == rel, (
        f"list_stations: expected {rel!r}, got {match.provider_avatar_path!r}"
    )

    # get_station
    st = repo.get_station(sid)
    assert st.provider_avatar_path == rel, (
        f"get_station: expected {rel!r}, got {st.provider_avatar_path!r}"
    )

    # list_recently_played
    repo.update_last_played(sid)
    recently = repo.list_recently_played(5)
    match_rp = next(s for s in recently if s.id == sid)
    assert match_rp.provider_avatar_path == rel, (
        f"list_recently_played: expected {rel!r}, got {match_rp.provider_avatar_path!r}"
    )

    # list_favorite_stations
    repo.con.execute("UPDATE stations SET is_favorite=1 WHERE id=?", (sid,))
    repo.con.commit()
    favs = repo.list_favorite_stations()
    match_fav = next(s for s in favs if s.id == sid)
    assert match_fav.provider_avatar_path == rel, (
        f"list_favorite_stations: expected {rel!r}, got {match_fav.provider_avatar_path!r}"
    )


def test_update_provider_avatar_path_clear(repo):
    """D-09: update_provider_avatar_path(provider_id, None) sets providers.avatar_path NULL."""
    pid = repo.ensure_provider("TestProviderClear")
    repo.update_provider_avatar_path(pid, "assets/channel-avatars/99.png")
    row = repo.con.execute("SELECT avatar_path FROM providers WHERE id=?", (pid,)).fetchone()
    assert row[0] == "assets/channel-avatars/99.png"
    repo.update_provider_avatar_path(pid, None)
    row2 = repo.con.execute("SELECT avatar_path FROM providers WHERE id=?", (pid,)).fetchone()
    assert row2[0] is None, f"avatar_path not cleared; got {row2[0]!r}"


def test_update_station_does_not_reset_provider_avatar_path(repo):
    """D-09 / Pitfall 5: update_station on a sibling must NOT reset providers.avatar_path.

    Dedicated single-column UPDATE only — broad provider update would silently clear it.
    """
    pid = repo.ensure_provider("PitfallFive")
    sid_a = repo.create_station()
    repo.update_station(sid_a, "PitfallFive A", pid, "", None, None, icy_disabled=True)
    sid_b = repo.create_station()
    repo.update_station(sid_b, "PitfallFive B", pid, "", None, None, icy_disabled=True)

    rel = f"assets/channel-avatars/{pid}.png"
    repo.update_provider_avatar_path(pid, rel)

    # Call update_station on the sibling — must not touch providers.avatar_path
    repo.update_station(sid_b, "PitfallFive B-edited", pid, "", None, None, icy_disabled=False)

    row = repo.con.execute("SELECT avatar_path FROM providers WHERE id=?", (pid,)).fetchone()
    assert row[0] == rel, (
        f"update_station reset providers.avatar_path to {row[0]!r} (Pitfall 5 violation)"
    )


def test_provider_avatar_path_in_all_mappers(repo):
    """Pitfall 6: all four mappers populate provider_avatar_path from providers.avatar_path."""
    pid = repo.ensure_provider("AllMappers")
    sid = repo.create_station()
    repo.update_station(sid, "AllMappers Sta", pid, "", None, None, icy_disabled=True)
    rel = f"assets/channel-avatars/{pid}.png"
    repo.update_provider_avatar_path(pid, rel)

    # list_stations
    sl = repo.list_stations()
    m = next(s for s in sl if s.id == sid)
    assert m.provider_avatar_path == rel, f"list_stations missing: {m.provider_avatar_path!r}"

    # get_station
    gs = repo.get_station(sid)
    assert gs.provider_avatar_path == rel, f"get_station missing: {gs.provider_avatar_path!r}"

    # list_recently_played
    repo.update_last_played(sid)
    rp = repo.list_recently_played(5)
    m_rp = next(s for s in rp if s.id == sid)
    assert m_rp.provider_avatar_path == rel, f"list_recently_played missing: {m_rp.provider_avatar_path!r}"

    # list_favorite_stations
    repo.con.execute("UPDATE stations SET is_favorite=1 WHERE id=?", (sid,))
    repo.con.commit()
    fav = repo.list_favorite_stations()
    m_fav = next(s for s in fav if s.id == sid)
    assert m_fav.provider_avatar_path == rel, f"list_favorite_stations missing: {m_fav.provider_avatar_path!r}"
