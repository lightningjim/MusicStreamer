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
