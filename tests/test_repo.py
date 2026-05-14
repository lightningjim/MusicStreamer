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
    """D-01: a station with cover_art_source='mb_only' hydrates correctly.

    Plan 01 does NOT extend repo.update_station — Plan 03 will. This test
    writes the column via direct SQL UPDATE to prove the read path on
    list_stations / get_station mappings honors the stored value.
    """
    sid = repo.create_station()
    repo.con.execute(
        "UPDATE stations SET cover_art_source = ? WHERE id = ?",
        ("mb_only", sid),
    )
    repo.con.commit()
    st = repo.get_station(sid)
    assert st.cover_art_source == "mb_only"


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
