"""Tests for musicstreamer/settings_export.py — SYNC-01 through SYNC-04."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pytest

from musicstreamer import paths
from musicstreamer.repo import Repo, db_init
from musicstreamer.settings_export import (
    ImportDetailRow,
    ImportPreview,
    build_zip,
    commit_import,
    preview_import,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)


@pytest.fixture
def seeded_repo(repo, tmp_path):
    """Repo with 2 stations, streams, favorites, and a credential setting."""
    # Station 1 — with art
    art_dir = tmp_path / "assets" / "1"
    art_dir.mkdir(parents=True)
    art_file = art_dir / "station_art.jpg"
    art_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # minimal JPEG header

    cur = repo.con.execute(
        "INSERT INTO stations(name, provider_id, tags, icy_disabled, last_played_at, is_favorite, station_art_path) "
        "VALUES (?, NULL, ?, 0, ?, 1, ?)",
        ("Groove Radio", "electronic,trance", "2026-04-16T10:00:00.000", "assets/1/station_art.jpg"),
    )
    repo.con.commit()
    station1_id = cur.lastrowid
    repo.con.execute(
        "INSERT INTO station_streams(station_id, url, label, quality, position, stream_type, codec) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (station1_id, "http://groove.example/hi.mp3", "Hi", "hi", 1, "shoutcast", "MP3"),
    )
    repo.con.execute(
        "INSERT INTO station_streams(station_id, url, label, quality, position, stream_type, codec) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (station1_id, "http://groove.example/lo.mp3", "Lo", "low", 2, "shoutcast", "MP3"),
    )
    repo.con.commit()

    # Station 2 — no art
    cur2 = repo.con.execute(
        "INSERT INTO stations(name, provider_id, tags, icy_disabled, last_played_at, is_favorite) "
        "VALUES (?, NULL, ?, 0, NULL, 0)",
        ("Jazz Lounge", "jazz"),
    )
    repo.con.commit()
    station2_id = cur2.lastrowid
    repo.con.execute(
        "INSERT INTO station_streams(station_id, url, label, quality, position, stream_type, codec) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (station2_id, "http://jazz.example/stream.mp3", "Default", "", 1, "", "MP3"),
    )
    repo.con.commit()

    # Favorites
    repo.con.execute(
        "INSERT OR IGNORE INTO favorites(station_name, provider_name, track_title, genre) "
        "VALUES (?, ?, ?, ?)",
        ("Groove Radio", "", "Artist - Track 1", "trance"),
    )
    repo.con.commit()

    # Settings — include credential key that should be excluded
    repo.con.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", ("volume", "80"))
    repo.con.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
        ("audioaddict_listen_key", "super_secret_key_abc123"),
    )
    repo.con.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
        ("accent_color", "#bf00ff"),
    )
    repo.con.commit()

    # Point paths._root_override at tmp_path so art resolution works
    paths._root_override = str(tmp_path)
    yield repo
    paths._root_override = None


# ---------------------------------------------------------------------------
# Helper: build a ZIP for import tests
# ---------------------------------------------------------------------------


def _make_import_zip(
    tmp_path: Path,
    payload: dict,
    logo_bytes: bytes | None = None,
    logo_filename: str = "logos/Groove_Radio.jpg",
) -> Path:
    """Write a minimal valid ZIP to tmp_path/import.zip and return the path."""
    zip_path = tmp_path / "import.zip"
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("settings.json", json.dumps(payload))
        if logo_bytes is not None:
            zf.writestr(logo_filename, logo_bytes)
    return zip_path


def _default_payload(stations=None, favorites=None, settings=None) -> dict:
    return {
        "version": 1,
        "exported_at": "2026-04-16T10:00:00",
        "stations": stations or [],
        "track_favorites": favorites or [],
        "settings": settings or [],
    }


# ---------------------------------------------------------------------------
# build_zip tests (SYNC-01, SYNC-02)
# ---------------------------------------------------------------------------


def test_build_zip_structure(seeded_repo, tmp_path):
    """build_zip produces a ZIP with settings.json and logos/ entries for stations with art."""
    zip_path = str(tmp_path / "export.zip")
    build_zip(seeded_repo, zip_path)

    assert os.path.exists(zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
    assert "settings.json" in names
    logo_entries = [n for n in names if n.startswith("logos/")]
    assert len(logo_entries) >= 1  # station with art has logo entry


def test_export_content_completeness(seeded_repo, tmp_path):
    """settings.json contains version, stations, track_favorites, settings."""
    zip_path = str(tmp_path / "export.zip")
    build_zip(seeded_repo, zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        payload = json.loads(zf.read("settings.json"))

    assert payload["version"] == 1
    assert "exported_at" in payload
    assert isinstance(payload["stations"], list)
    assert len(payload["stations"]) == 2
    assert isinstance(payload["track_favorites"], list)
    assert isinstance(payload["settings"], list)

    # Check station fields
    groove = next(s for s in payload["stations"] if s["name"] == "Groove Radio")
    assert "streams" in groove
    assert len(groove["streams"]) == 2
    assert "provider" in groove
    assert "tags" in groove
    assert "icy_disabled" in groove
    assert "is_favorite" in groove
    assert "last_played_at" in groove
    assert "logo_file" in groove

    # Station without art should have logo_file = null
    jazz = next(s for s in payload["stations"] if s["name"] == "Jazz Lounge")
    assert jazz["logo_file"] is None

    # Favorites present
    assert len(payload["track_favorites"]) == 1
    fav = payload["track_favorites"][0]
    assert "station_name" in fav
    assert "track_title" in fav
    assert "provider_name" in fav
    assert "genre" in fav


def test_credentials_excluded(seeded_repo, tmp_path):
    """audioaddict_listen_key must NOT appear in exported settings."""
    zip_path = str(tmp_path / "export.zip")
    build_zip(seeded_repo, zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        payload = json.loads(zf.read("settings.json"))

    keys = [s["key"] for s in payload["settings"]]
    assert "audioaddict_listen_key" not in keys
    assert "volume" in keys
    assert "accent_color" in keys


def test_export_logo_files(seeded_repo, tmp_path):
    """Stations with art have logos/ entry; logo_file field matches."""
    zip_path = str(tmp_path / "export.zip")
    build_zip(seeded_repo, zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        payload = json.loads(zf.read("settings.json"))

    groove = next(s for s in payload["stations"] if s["name"] == "Groove Radio")
    assert groove["logo_file"] is not None
    assert groove["logo_file"] in names

    jazz = next(s for s in payload["stations"] if s["name"] == "Jazz Lounge")
    assert jazz["logo_file"] is None


def test_sanitize_filename(tmp_path):
    """_sanitize handles Unicode, slashes, colons, emoji, empty string, long names."""
    from musicstreamer.settings_export import _sanitize

    assert _sanitize("Hello World") == "Hello_World"
    assert _sanitize("Caf\u00e9 Radio") == "Cafe_Radio"  # é → NFKD decomposes to e + combining → e retained
    assert _sanitize("Groove/Radio:FM") == "GrooveRadioFM"
    assert _sanitize("") == "station"
    long_name = "A" * 100
    result = _sanitize(long_name)
    assert len(result) <= 80
    # emoji stripped
    emoji_name = "Music \U0001f3b5 Radio"
    result = _sanitize(emoji_name)
    assert "\U0001f3b5" not in result


# ---------------------------------------------------------------------------
# preview_import tests (SYNC-03)
# ---------------------------------------------------------------------------


def test_preview_merge_counts(repo, tmp_path):
    """preview_import with 1 new + 1 URL-matched station returns added=1, replaced=1."""
    # Seed the DB with one existing station matching the import URL
    cur = repo.con.execute(
        "INSERT INTO stations(name, tags) VALUES (?, ?)", ("Existing Station", "")
    )
    repo.con.commit()
    existing_id = cur.lastrowid
    repo.con.execute(
        "INSERT INTO station_streams(station_id, url, label, quality, position) VALUES (?, ?, ?, ?, ?)",
        (existing_id, "http://existing.example/stream.mp3", "", "", 1),
    )
    repo.con.commit()

    payload = _default_payload(
        stations=[
            {
                "name": "Existing Station",
                "provider": "",
                "tags": "updated",
                "icy_disabled": False,
                "is_favorite": False,
                "last_played_at": None,
                "logo_file": None,
                "streams": [{"url": "http://existing.example/stream.mp3", "label": "", "quality": "", "position": 1, "stream_type": "", "codec": ""}],
            },
            {
                "name": "New Station",
                "provider": "TestProvider",
                "tags": "new",
                "icy_disabled": False,
                "is_favorite": False,
                "last_played_at": None,
                "logo_file": None,
                "streams": [{"url": "http://new.example/stream.mp3", "label": "", "quality": "", "position": 1, "stream_type": "", "codec": ""}],
            },
        ]
    )
    zip_path = _make_import_zip(tmp_path, payload)
    preview = preview_import(str(zip_path), repo)

    assert isinstance(preview, ImportPreview)
    assert preview.added == 1
    assert preview.replaced == 1
    assert preview.skipped == 0
    assert preview.errors == 0
    assert len(preview.detail_rows) == 2


def test_preview_invalid_zip(repo, tmp_path):
    """preview_import on non-ZIP file raises ValueError('Not a valid ZIP archive')."""
    bad_file = tmp_path / "bad.zip"
    bad_file.write_bytes(b"this is not a zip file at all")

    with pytest.raises(ValueError, match="Not a valid ZIP archive"):
        preview_import(str(bad_file), repo)


def test_preview_missing_settings_json(repo, tmp_path):
    """preview_import on ZIP without settings.json raises ValueError."""
    zip_path = tmp_path / "no_settings.zip"
    with zipfile.ZipFile(str(zip_path), "w") as zf:
        zf.writestr("other_file.txt", "hello")

    with pytest.raises(ValueError, match="Missing settings.json"):
        preview_import(str(zip_path), repo)


def test_preview_path_traversal(repo, tmp_path):
    """preview_import on ZIP with '../evil' member raises ValueError containing 'Unsafe path'."""
    zip_path = tmp_path / "traversal.zip"
    # zipfile won't normally allow writing '..' paths through normal API,
    # so we use a raw write approach via ZipInfo
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        payload = _default_payload()
        zf.writestr("settings.json", json.dumps(payload))
        # Manually create ZipInfo with traversal path
        info = zipfile.ZipInfo(filename="../evil.txt")
        zf.writestr(info, "malicious content")
    zip_path.write_bytes(buf.getvalue())

    with pytest.raises(ValueError, match="Unsafe path"):
        preview_import(str(zip_path), repo)


def test_preview_bad_version(repo, tmp_path):
    """preview_import on ZIP with version!=1 raises ValueError containing 'Unsupported version'."""
    payload = _default_payload()
    payload["version"] = 99
    zip_path = _make_import_zip(tmp_path, payload)

    with pytest.raises(ValueError, match="Unsupported version"):
        preview_import(str(zip_path), repo)


# ---------------------------------------------------------------------------
# commit_import tests (SYNC-03, SYNC-04)
# ---------------------------------------------------------------------------


def test_commit_merge_add(repo, tmp_path):
    """commit_import merge mode adds new station with correct attributes."""
    payload = _default_payload(
        stations=[
            {
                "name": "New Station",
                "provider": "TestProvider",
                "tags": "rock,metal",
                "icy_disabled": True,
                "is_favorite": True,
                "last_played_at": "2026-04-16T10:00:00",
                "logo_file": None,
                "streams": [
                    {"url": "http://new.example/hi.mp3", "label": "Hi", "quality": "hi",
                     "position": 1, "stream_type": "shoutcast", "codec": "MP3"}
                ],
            }
        ]
    )
    zip_path = _make_import_zip(tmp_path, payload)
    preview = preview_import(str(zip_path), repo)
    commit_import(preview, repo, mode="merge")

    stations = repo.list_stations()
    assert len(stations) == 1
    s = stations[0]
    assert s.name == "New Station"
    assert s.provider_name == "TestProvider"
    assert s.tags == "rock,metal"
    assert s.icy_disabled is True
    assert s.is_favorite is True
    assert len(s.streams) == 1
    assert s.streams[0].url == "http://new.example/hi.mp3"
    assert s.streams[0].quality == "hi"


def test_commit_merge_replace(repo, tmp_path):
    """commit_import merge mode on URL match replaces station name/tags/streams (old streams deleted)."""
    # Seed existing station with 2 streams
    cur = repo.con.execute(
        "INSERT INTO stations(name, tags) VALUES (?, ?)", ("Old Name", "old_tag")
    )
    repo.con.commit()
    old_id = cur.lastrowid
    repo.con.execute(
        "INSERT INTO station_streams(station_id, url, position) VALUES (?, ?, ?)",
        (old_id, "http://match.example/stream.mp3", 1),
    )
    repo.con.execute(
        "INSERT INTO station_streams(station_id, url, position) VALUES (?, ?, ?)",
        (old_id, "http://match.example/stream2.mp3", 2),
    )
    repo.con.commit()

    payload = _default_payload(
        stations=[
            {
                "name": "New Name",
                "provider": "",
                "tags": "new_tag",
                "icy_disabled": False,
                "is_favorite": False,
                "last_played_at": None,
                "logo_file": None,
                "streams": [
                    {"url": "http://match.example/stream.mp3", "label": "Only",
                     "quality": "hi", "position": 1, "stream_type": "", "codec": ""}
                ],
            }
        ]
    )
    zip_path = _make_import_zip(tmp_path, payload)
    preview = preview_import(str(zip_path), repo)
    assert preview.replaced == 1

    commit_import(preview, repo, mode="merge")

    stations = repo.list_stations()
    assert len(stations) == 1
    s = stations[0]
    assert s.name == "New Name"
    assert s.tags == "new_tag"
    # Old streams deleted, only the imported one remains
    assert len(s.streams) == 1
    assert s.streams[0].url == "http://match.example/stream.mp3"
    assert s.streams[0].quality == "hi"


def test_commit_replace_all(repo, tmp_path):
    """commit_import replace_all wipes stations+streams+favorites+providers then restores."""
    # Seed existing data
    cur = repo.con.execute(
        "INSERT INTO stations(name, tags) VALUES (?, ?)", ("To Be Deleted", "old")
    )
    repo.con.commit()
    old_id = cur.lastrowid
    repo.con.execute(
        "INSERT INTO station_streams(station_id, url, position) VALUES (?, ?, ?)",
        (old_id, "http://old.example/stream.mp3", 1),
    )
    repo.con.execute(
        "INSERT OR IGNORE INTO favorites(station_name, provider_name, track_title, genre) "
        "VALUES (?, ?, ?, ?)",
        ("Old Station", "", "Old Track", "old_genre"),
    )
    repo.con.commit()

    payload = _default_payload(
        stations=[
            {
                "name": "Restored Station",
                "provider": "RestoredProvider",
                "tags": "restored",
                "icy_disabled": False,
                "is_favorite": False,
                "last_played_at": None,
                "logo_file": None,
                "streams": [
                    {"url": "http://restored.example/stream.mp3", "label": "",
                     "quality": "", "position": 1, "stream_type": "", "codec": ""}
                ],
            }
        ],
        favorites=[
            {"station_name": "Restored Station", "provider_name": "RestoredProvider",
             "track_title": "Restored Track", "genre": "jazz", "created_at": None}
        ],
    )
    zip_path = _make_import_zip(tmp_path, payload)
    preview = preview_import(str(zip_path), repo)
    commit_import(preview, repo, mode="replace_all")

    stations = repo.list_stations()
    assert len(stations) == 1
    assert stations[0].name == "Restored Station"

    # Old station gone
    assert not any(s.name == "To Be Deleted" for s in stations)

    # Old favorites gone, new one present
    favorites = repo.list_favorites()
    assert len(favorites) == 1
    assert favorites[0].track_title == "Restored Track"


def test_commit_favorites_union(repo, tmp_path):
    """commit_import merge mode adds new favorites; existing ones (same station_name+track_title) untouched."""
    # Seed an existing favorite
    repo.con.execute(
        "INSERT OR IGNORE INTO favorites(station_name, provider_name, track_title, genre) "
        "VALUES (?, ?, ?, ?)",
        ("My Station", "", "Existing Track", "rock"),
    )
    repo.con.commit()

    payload = _default_payload(
        favorites=[
            {"station_name": "My Station", "provider_name": "", "track_title": "Existing Track",
             "genre": "rock", "created_at": None},  # duplicate — should not double-insert
            {"station_name": "My Station", "provider_name": "", "track_title": "New Track",
             "genre": "rock", "created_at": None},
        ]
    )
    zip_path = _make_import_zip(tmp_path, payload)
    preview = preview_import(str(zip_path), repo)
    commit_import(preview, repo, mode="merge")

    favorites = repo.list_favorites()
    titles = [f.track_title for f in favorites]
    assert "Existing Track" in titles
    assert "New Track" in titles
    assert titles.count("Existing Track") == 1  # no duplicate


def test_commit_settings_restored(repo, tmp_path):
    """commit_import restores settings key/value pairs."""
    payload = _default_payload(
        settings=[
            {"key": "volume", "value": "75"},
            {"key": "accent_color", "value": "#ff0000"},
        ]
    )
    zip_path = _make_import_zip(tmp_path, payload)
    preview = preview_import(str(zip_path), repo)
    commit_import(preview, repo, mode="merge")

    assert repo.get_setting("volume", "") == "75"
    assert repo.get_setting("accent_color", "") == "#ff0000"


def test_commit_logo_extraction(repo, tmp_path):
    """commit_import extracts logo from ZIP to assets/{station_id}/station_art{ext}."""
    paths._root_override = str(tmp_path)
    try:
        logo_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # fake JPEG

        payload = _default_payload(
            stations=[
                {
                    "name": "Logo Station",
                    "provider": "",
                    "tags": "",
                    "icy_disabled": False,
                    "is_favorite": False,
                    "last_played_at": None,
                    "logo_file": "logos/Logo_Station.jpg",
                    "streams": [
                        {"url": "http://logo.example/stream.mp3", "label": "",
                         "quality": "", "position": 1, "stream_type": "", "codec": ""}
                    ],
                }
            ]
        )
        zip_path = _make_import_zip(tmp_path, payload, logo_bytes=logo_bytes, logo_filename="logos/Logo_Station.jpg")
        preview = preview_import(str(zip_path), repo)
        commit_import(preview, repo, mode="merge")

        stations = repo.list_stations()
        assert len(stations) == 1
        s = stations[0]
        assert s.station_art_path is not None
        assert s.station_art_path.endswith(".jpg")
        # File should exist on disk
        art_abs = os.path.join(str(tmp_path), s.station_art_path)
        assert os.path.exists(art_abs)
    finally:
        paths._root_override = None


def test_cancel_no_change(repo, tmp_path):
    """Calling preview_import without commit_import leaves DB unchanged."""
    payload = _default_payload(
        stations=[
            {
                "name": "Ghost Station",
                "provider": "",
                "tags": "",
                "icy_disabled": False,
                "is_favorite": False,
                "last_played_at": None,
                "logo_file": None,
                "streams": [
                    {"url": "http://ghost.example/stream.mp3", "label": "",
                     "quality": "", "position": 1, "stream_type": "", "codec": ""}
                ],
            }
        ]
    )
    zip_path = _make_import_zip(tmp_path, payload)
    _preview = preview_import(str(zip_path), repo)
    # Don't call commit_import — DB should be untouched
    stations = repo.list_stations()
    assert len(stations) == 0


# ---------------------------------------------------------------------------
# PB-14 / PB-15: bitrate_kbps export/import roundtrip + forward-compat (Phase 47-03)
# ---------------------------------------------------------------------------


def _fresh_repo(tmp_path_factory_or_path) -> Repo:
    """Build a fresh Repo on a new file DB; mimics repo fixture."""
    # Accept either a Path (tests pass tmp_path / <subdir>) or a pytest tmp_path_factory.
    db_path = str(tmp_path_factory_or_path / "fresh.db")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)


def test_export_import_roundtrip_preserves_bitrate_kbps(repo, tmp_path):
    """PB-14: bitrate_kbps survives build_zip -> commit_import roundtrip."""
    # Seed a station + stream with bitrate_kbps=320 via raw SQL.
    cur = repo.con.execute(
        "INSERT INTO stations(name, tags) VALUES (?, ?)", ("Bitrate Test", "")
    )
    repo.con.commit()
    sid = int(cur.lastrowid)
    repo.con.execute(
        "INSERT INTO station_streams"
        "(station_id, url, label, quality, position, stream_type, codec, bitrate_kbps) "
        "VALUES (?, ?, '', 'hi', 1, '', 'AAC', ?)",
        (sid, "http://bitrate-test.example/stream", 320),
    )
    repo.con.commit()

    # Export
    zip_path = tmp_path / "settings.zip"
    build_zip(repo, str(zip_path))

    # Sanity check: bitrate_kbps appears in exported JSON
    with zipfile.ZipFile(str(zip_path)) as zf:
        payload = json.loads(zf.read("settings.json"))
    target_stations = [
        st for st in payload["stations"]
        if any(s.get("url") == "http://bitrate-test.example/stream"
               for s in st.get("streams", []))
    ]
    assert target_stations, "test station missing from export payload"
    target_stream = next(
        s for s in target_stations[0]["streams"]
        if s.get("url") == "http://bitrate-test.example/stream"
    )
    assert target_stream["bitrate_kbps"] == 320

    # Import into a fresh repo, replace_all mode.
    fresh_dir = tmp_path / "fresh"
    fresh_dir.mkdir()
    fresh = _fresh_repo(fresh_dir)
    preview = preview_import(str(zip_path), fresh)
    commit_import(preview, fresh, mode="replace_all")

    row = fresh.con.execute(
        "SELECT bitrate_kbps FROM station_streams WHERE url = ?",
        ("http://bitrate-test.example/stream",),
    ).fetchone()
    assert row is not None
    assert row["bitrate_kbps"] == 320


def test_commit_import_forward_compat_missing_bitrate_key(tmp_path):
    """PB-15: pre-47 ZIP (stream dict without bitrate_kbps) imports cleanly with default 0."""
    payload = {
        "version": 1,
        "exported_at": "2026-01-01T00:00:00",
        "stations": [
            {
                "name": "Legacy Station",
                "provider": "",
                "tags": "",
                "icy_disabled": False,
                "is_favorite": False,
                "last_played_at": None,
                "logo_file": None,
                "streams": [
                    # NO bitrate_kbps key — simulates a pre-47 export.
                    {
                        "url": "http://legacy.example/stream",
                        "label": "",
                        "quality": "",
                        "position": 1,
                        "stream_type": "",
                        "codec": "",
                    }
                ],
            }
        ],
        "track_favorites": [],
        "settings": [],
    }
    zip_path = tmp_path / "legacy.zip"
    with zipfile.ZipFile(str(zip_path), "w") as zf:
        zf.writestr("settings.json", json.dumps(payload))

    fresh_dir = tmp_path / "fresh"
    fresh_dir.mkdir()
    fresh = _fresh_repo(fresh_dir)
    preview = preview_import(str(zip_path), fresh)
    commit_import(preview, fresh, mode="replace_all")  # no KeyError expected

    row = fresh.con.execute(
        "SELECT bitrate_kbps FROM station_streams WHERE url = ?",
        ("http://legacy.example/stream",),
    ).fetchone()
    assert row is not None
    assert row["bitrate_kbps"] == 0


def test_station_to_dict_emits_bitrate_kbps(repo):
    """PB-14b: _station_to_dict emits 'bitrate_kbps' key from StationStream.bitrate_kbps."""
    from musicstreamer.settings_export import _station_to_dict

    cur = repo.con.execute(
        "INSERT INTO stations(name, tags) VALUES (?, ?)", ("Test", "")
    )
    repo.con.commit()
    sid = int(cur.lastrowid)
    repo.con.execute(
        "INSERT INTO station_streams"
        "(station_id, url, label, quality, position, stream_type, codec, bitrate_kbps) "
        "VALUES (?, ?, '', '', 1, '', '', ?)",
        (sid, "http://t.example/stream", 192),
    )
    repo.con.commit()

    stations = repo.list_stations()
    station = next(s for s in stations if s.name == "Test")
    d = _station_to_dict(station)
    assert d["streams"][0]["bitrate_kbps"] == 192


# ---------------------------------------------------------------------------
# Phase 47.2 D-16: eq-profiles/ ZIP integration
# ---------------------------------------------------------------------------


def test_export_includes_eq_profiles(tmp_path, monkeypatch, repo):
    """D-16: build_zip writes every .txt in eq_profiles_dir to the archive."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    eq_dir = paths.eq_profiles_dir()
    os.makedirs(eq_dir, exist_ok=True)
    (Path(eq_dir) / "hd650.txt").write_text(
        "Preamp: -6.2 dB\nFilter 1: ON PK Fc 105 Hz Gain -3.5 dB Q 0.7\n"
    )
    (Path(eq_dir) / "airpods.txt").write_text(
        "Preamp: -3.0 dB\nFilter 1: ON LSC Fc 100 Hz Gain 2.0 dB Q 0.7\n"
    )
    dest = tmp_path / "out.zip"
    build_zip(repo, str(dest))
    with zipfile.ZipFile(dest, "r") as zf:
        names = zf.namelist()
    assert "eq-profiles/hd650.txt" in names
    assert "eq-profiles/airpods.txt" in names


def test_eq_profiles_zip_round_trip(tmp_path, monkeypatch, repo):
    """D-16: export + import restores every eq-profiles/*.txt byte-for-byte."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    eq_dir = paths.eq_profiles_dir()
    os.makedirs(eq_dir, exist_ok=True)
    text1 = "Preamp: -6.2 dB\nFilter 1: ON PK Fc 105 Hz Gain -3.5 dB Q 0.7\n"
    (Path(eq_dir) / "hd650.txt").write_text(text1)
    dest = tmp_path / "out.zip"
    build_zip(repo, str(dest))
    # Nuke the dir to simulate a fresh machine
    shutil.rmtree(eq_dir)
    # Fresh repo (empty DB) for clean import
    fresh_dir = tmp_path / "fresh"
    fresh_dir.mkdir()
    fresh_repo = _fresh_repo(fresh_dir)
    preview = preview_import(str(dest), fresh_repo)
    commit_import(preview, fresh_repo, mode="merge")
    restored = Path(eq_dir) / "hd650.txt"
    assert restored.exists()
    assert restored.read_text() == text1


def test_eq_profiles_path_traversal_rejected(tmp_path, monkeypatch, repo):
    """Pitfall 8: hostile eq-profiles/../evil.txt is rejected by _validate_zip_members."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(paths.eq_profiles_dir(), exist_ok=True)
    dest = tmp_path / "hostile.zip"
    build_zip(repo, str(dest))
    # Re-open and inject a traversal member via raw ZipInfo so zipfile will
    # accept the hostile name without normalizing it away.
    with zipfile.ZipFile(dest, "a") as zf:
        info = zipfile.ZipInfo(filename="eq-profiles/../evil.txt")
        zf.writestr(info, "nope")
    fresh_dir = tmp_path / "fresh"
    fresh_dir.mkdir()
    fresh_repo = _fresh_repo(fresh_dir)
    with pytest.raises(ValueError, match="Unsafe path"):
        preview_import(str(dest), fresh_repo)
