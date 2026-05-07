"""pytest-qt session configuration.

Sets the Qt platform plugin to ``offscreen`` so tests run headless on CI
and on headless dev boxes. Must happen BEFORE any PySide6 import.

Also provides an autouse fixture that stubs
``musicstreamer.player._ensure_bus_bridge`` so tests which instantiate
``Player`` never spin up the real GLib.MainLoop daemon thread. The bus
bridge is exercised by dedicated tests for ``gst_bus_bridge.py`` only.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _stub_bus_bridge(monkeypatch):
    """Replace _ensure_bus_bridge with a MagicMock so Player() construction
    never starts the real GLib.MainLoop daemon thread in unit tests."""
    try:
        import musicstreamer.player as _player_mod
    except ImportError:
        return
    monkeypatch.setattr(
        _player_mod, "_ensure_bus_bridge", lambda: MagicMock()
    )


# === Phase 60 (GBS.FM) shared fixtures =====================================
# Spec: 60-PATTERNS.md §"tests/conftest.py extension" + 60-VALIDATION.md
# §Wave 0 Requirements row 5. These fixtures are NON-autouse — opt-in
# per test by injection.

from pathlib import Path
import http.cookiejar


@pytest.fixture
def mock_gbs_api():
    """MagicMock with the gbs_api module surface pre-stubbed.

    Phase 60-02 creates the real module. This fixture stays decoupled
    via spec-by-string-list — no import — so Wave 0 tests can RED against
    the spec before 60-02 lands. spec=[...] catches API drift between
    the conftest fixture and the real module signatures (BLOCKER 4 fix).
    """
    api = MagicMock(spec=[
        "fetch_streams",
        "fetch_station_metadata",
        "import_station",
        "fetch_active_playlist",
        "vote_now_playing",
        "search",
        "submit",
        "load_auth_context",
        "fetch_user_tokens",  # Phase 60.4 D-T1: token-count scraper
    ])
    api.fetch_streams.return_value = [
        {"url": "https://gbs.fm/96", "quality": "96", "position": 60, "codec": "MP3", "bitrate_kbps": 96},
        {"url": "https://gbs.fm/128", "quality": "128", "position": 50, "codec": "MP3", "bitrate_kbps": 128},
        {"url": "https://gbs.fm/192", "quality": "192", "position": 40, "codec": "MP3", "bitrate_kbps": 192},
        {"url": "https://gbs.fm/256", "quality": "256", "position": 30, "codec": "MP3", "bitrate_kbps": 256},
        {"url": "https://gbs.fm/320", "quality": "320", "position": 20, "codec": "MP3", "bitrate_kbps": 320},
        {"url": "https://gbs.fm/flac", "quality": "flac", "position": 10, "codec": "FLAC", "bitrate_kbps": 1411},
    ]
    api.fetch_station_metadata.return_value = {
        "name": "GBS.FM",
        "description": "",
        "logo_url": "https://gbs.fm/images/logo_3.png",
        "homepage": "https://gbs.fm/",
    }
    api.fetch_active_playlist.return_value = {
        "now_playing_entryid": 1810736,
        "now_playing_songid": 782491,
        "icy_title": "Crippling Alcoholism - Templeton",
        "song_length": 274,
        "song_position": 202.68999999999997,
        "user_vote": 0,
        "score": "no votes",
        "queue_html_snippets": [],
        "removed_ids": [],
        "queue_summary": "Playlist is 11:21 long with 3 dongs",
    }
    api.vote_now_playing.return_value = {"user_vote": 3, "score": "4.0 (2 votes)"}
    api.search.return_value = {
        "results": [
            {"songid": 782491, "artist": "Crippling Alcoholism", "title": "Templeton",
             "duration": "4:34", "add_url": "/add/782491"},
        ],
        "page": 1,
        "total_pages": 1,
    }
    api.submit.return_value = "Track added successfully!"
    api.load_auth_context.return_value = None
    return api


class _FakeStation:
    """Mirrors the real musicstreamer.models.Station attribute surface
    that Phase 60 touches. HIGH 1 fix: attribute is `station_art_path`
    (matching models.py:31) — NOT `station_art`. _FakeRepo.update_station_art
    writes through to this canonical attribute name.
    """
    def __init__(self, station_id, name, url, provider_name, tags=""):
        self.id = station_id
        self.name = name
        self.url = url
        self.provider_name = provider_name
        self.tags = tags
        self.streams = []
        self.station_art_path = None   # canonical name (HIGH 1)


class _FakeStream:
    def __init__(self, stream_id, station_id, url, label="", quality="",
                 position=1, stream_type="", codec="", bitrate_kbps=0):
        self.id = stream_id
        self.station_id = station_id
        self.url = url
        self.label = label
        self.quality = quality
        self.position = position
        self.stream_type = stream_type
        self.codec = codec
        self.bitrate_kbps = bitrate_kbps


class _FakeRepo:
    """In-memory Repo double — covers every Repo method Phase 60 calls.

    Tracks stations, streams, and settings via Python dicts. Mirrors:
      - station_exists_by_url
      - insert_station / list_streams / insert_stream / update_stream
      - get_setting / set_setting
      - update_station_art / get_station / list_stations
    """
    def __init__(self):
        self._stations = {}      # station_id -> _FakeStation
        self._streams = {}       # stream_id -> _FakeStream
        self._settings = {}      # key -> str
        self._next_station_id = 1
        self._next_stream_id = 1

    def station_exists_by_url(self, url):
        for s in self._streams.values():
            if s.url == url:
                return True
        return False

    def insert_station(self, name, url, provider_name, tags):
        sid = self._next_station_id
        self._next_station_id += 1
        st = _FakeStation(sid, name, url, provider_name, tags)
        self._stations[sid] = st
        # Mirrors repo.py:407-417 — auto-create first stream
        if url:
            self.insert_stream(sid, url)
        return sid

    def list_streams(self, station_id):
        return [s for s in self._streams.values() if s.station_id == station_id]

    def insert_stream(self, station_id, url, label="", quality="", position=1,
                      stream_type="", codec="", bitrate_kbps=0):
        sid = self._next_stream_id
        self._next_stream_id += 1
        self._streams[sid] = _FakeStream(
            sid, station_id, url, label, quality, position, stream_type, codec, bitrate_kbps,
        )
        return sid

    def update_stream(self, stream_id, url, label, quality, position,
                      stream_type, codec, bitrate_kbps=0):
        s = self._streams[stream_id]
        s.url = url
        s.label = label
        s.quality = quality
        s.position = position
        s.stream_type = stream_type
        s.codec = codec
        s.bitrate_kbps = bitrate_kbps

    def delete_stream(self, stream_id):
        self._streams.pop(stream_id, None)

    def get_setting(self, key, default=""):
        return self._settings.get(key, default)

    def set_setting(self, key, value):
        self._settings[key] = value

    def update_station_art(self, station_id, art_path):
        """HIGH 1 fix: writes to canonical `station_art_path` attribute
        (matching musicstreamer.models.Station.station_art_path)."""
        if station_id in self._stations:
            self._stations[station_id].station_art_path = art_path

    def get_station(self, station_id):
        return self._stations.get(station_id)

    def list_stations(self):
        return list(self._stations.values())


@pytest.fixture
def fake_repo():
    """Empty in-memory Repo double matching the API Phase 60 calls."""
    return _FakeRepo()


@pytest.fixture
def fake_cookies_jar():
    """Empty MozillaCookieJar — drop-in for gbs_api auth_context arguments."""
    return http.cookiejar.MozillaCookieJar()


@pytest.fixture
def gbs_fixtures_dir():
    """Path to tests/fixtures/gbs/ — for tests that read captured HTML/JSON."""
    return Path(__file__).parent / "fixtures" / "gbs"
