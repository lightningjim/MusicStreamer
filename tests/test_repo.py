import sqlite3
import pytest
from musicstreamer.models import Station, Provider
from musicstreamer.repo import Repo, db_init


@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)


def test_list_stations_empty(repo):
    assert repo.list_stations() == []


def test_create_and_get_station(repo):
    station_id = repo.create_station()
    st = repo.get_station(station_id)
    assert st.id == station_id
    assert st.name == "New Station"
    assert st.url == ""


def test_update_station(repo):
    sid = repo.create_station()
    repo.update_station(sid, "My Station", "http://example.com/stream", None, "jazz", None, None)
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
    repo.update_station(sid, "Radio", "http://example.com", None, "", None, None, icy_disabled=True)
    st = repo.get_station(sid)
    assert st.icy_disabled is True


def test_icy_disabled_migration(repo):
    # Simulate app restart on existing DB — second db_init call must not raise
    db_init(repo.con)
    st_count = len(repo.list_stations())
    assert isinstance(st_count, int)


def test_update_station_preserves_icy_disabled(repo):
    sid = repo.create_station()
    repo.update_station(sid, "Radio", "http://example.com", None, "", None, None, icy_disabled=False)
    st = repo.get_station(sid)
    assert st.icy_disabled is False

    repo.update_station(sid, "Radio", "http://example.com", None, "", None, None, icy_disabled=True)
    st = repo.get_station(sid)
    assert st.icy_disabled is True


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
    assert st.url == "http://my.station/stream"
    assert st.tags == "jazz,blues"


# --- update_station_art tests ---

def test_update_station_art(repo):
    sid = repo.create_station()
    repo.update_station_art(sid, "assets/1/station_art.png")
    st = repo.get_station(sid)
    assert st.station_art_path == "assets/1/station_art.png"
