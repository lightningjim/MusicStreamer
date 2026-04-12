import json
import sqlite3
import time
import pytest

from musicstreamer.models import Favorite
from musicstreamer.repo import Repo, db_init
from musicstreamer.cover_art import _parse_itunes_result


@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)


# --- Repo favorites tests ---

def test_add_favorite(repo):
    repo.add_favorite("Station A", "Provider X", "Artist - Song", "Pop")
    assert repo.is_favorited("Station A", "Artist - Song") is True


def test_duplicate_ignored(repo):
    repo.add_favorite("Station A", "Provider X", "Artist - Song", "Pop")
    repo.add_favorite("Station A", "Provider X", "Artist - Song", "Pop")
    assert len(repo.list_favorites()) == 1


def test_remove_favorite(repo):
    repo.add_favorite("Station A", "Provider X", "Artist - Song", "Pop")
    repo.remove_favorite("Station A", "Artist - Song")
    assert repo.is_favorited("Station A", "Artist - Song") is False
    assert repo.list_favorites() == []


def test_list_favorites_order(repo):
    repo.add_favorite("Station A", "Provider X", "Track 1", "Pop")
    time.sleep(0.05)
    repo.add_favorite("Station A", "Provider X", "Track 2", "Pop")
    time.sleep(0.05)
    repo.add_favorite("Station A", "Provider X", "Track 3", "Pop")
    favs = repo.list_favorites()
    assert [f.track_title for f in favs] == ["Track 3", "Track 2", "Track 1"]


def test_is_favorited_false(repo):
    assert repo.is_favorited("NoStation", "NoTrack") is False


# --- Station favorites (is_favorite column) ---

def test_station_favorite_add_remove(repo):
    """set_station_favorite(id, True) then is_favorite_station(id) returns True; set False returns False."""
    repo.con.execute("INSERT INTO providers(name) VALUES ('TestProvider')")
    repo.con.commit()
    provider_id = repo.con.execute("SELECT id FROM providers WHERE name='TestProvider'").fetchone()["id"]
    repo.con.execute(
        "INSERT INTO stations(id, name, provider_id) VALUES (101, 'Test Station', ?)",
        (provider_id,),
    )
    repo.con.commit()

    repo.set_station_favorite(101, True)
    assert repo.is_favorite_station(101) is True

    repo.set_station_favorite(101, False)
    assert repo.is_favorite_station(101) is False


def test_list_favorite_stations(repo):
    """After favoriting 2 of 3 stations, list_favorite_stations returns exactly those 2."""
    repo.con.execute("INSERT INTO providers(name) VALUES ('FavProvider')")
    repo.con.commit()
    pid = repo.con.execute("SELECT id FROM providers WHERE name='FavProvider'").fetchone()["id"]
    for sid, name in [(201, "Alpha"), (202, "Beta"), (203, "Gamma")]:
        repo.con.execute(
            "INSERT INTO stations(id, name, provider_id) VALUES (?, ?, ?)", (sid, name, pid)
        )
    repo.con.commit()

    repo.set_station_favorite(201, True)
    repo.set_station_favorite(203, True)

    favs = repo.list_favorite_stations()
    fav_names = {s.name for s in favs}
    assert fav_names == {"Alpha", "Gamma"}
    assert all(s.is_favorite for s in favs)


def test_db_init_idempotent(repo):
    db_init(repo.con)
    assert isinstance(repo.list_favorites(), list)


# --- _parse_itunes_result tests ---

def test_parse_itunes_result_with_genre():
    data = {
        "resultCount": 1,
        "results": [
            {
                "artworkUrl100": "https://example.com/100x100bb.jpg",
                "primaryGenreName": "Pop",
            }
        ],
    }
    result = _parse_itunes_result(json.dumps(data).encode())
    assert result == {
        "artwork_url": "https://example.com/160x160bb.jpg",
        "genre": "Pop",
    }


def test_parse_itunes_result_empty():
    data = {"resultCount": 0, "results": []}
    result = _parse_itunes_result(json.dumps(data).encode())
    assert result == {"artwork_url": None, "genre": ""}


def test_parse_itunes_result_no_genre():
    data = {
        "resultCount": 1,
        "results": [
            {
                "artworkUrl100": "https://example.com/100x100bb.jpg",
            }
        ],
    }
    result = _parse_itunes_result(json.dumps(data).encode())
    assert result["artwork_url"] == "https://example.com/160x160bb.jpg"
    assert result["genre"] == ""
