import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from musicstreamer.aa_import import fetch_channels, import_stations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_channel_json(name: str, key: str) -> bytes:
    return json.dumps([{"name": name, "key": key}]).encode()


def _urlopen_factory(data: bytes):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read = MagicMock(return_value=data)
    return cm


def _make_http_error(code: int):
    return urllib.error.HTTPError(url="http://test", code=code, msg="err", hdrs=None, fp=None)


# ---------------------------------------------------------------------------
# fetch_channels tests
# ---------------------------------------------------------------------------

def test_fetch_channels_returns_list():
    """fetch_channels returns list of dicts with title, url, provider for all 6 networks."""
    channel_data = _mock_channel_json("Ambient", "ambient")

    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(channel_data)):
        result = fetch_channels("testkey123", "hi")

    assert isinstance(result, list)
    assert len(result) == 6
    for item in result:
        assert "title" in item
        assert "url" in item
        assert "provider" in item
        assert "premium_high" in item["url"]
        assert ".pls?listen_key=" in item["url"]


def test_fetch_channels_invalid_key():
    """fetch_channels raises ValueError('invalid_key') on 401 or 403."""
    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=_make_http_error(403)):
        with pytest.raises(ValueError, match="invalid_key"):
            fetch_channels("badkey", "hi")


def test_fetch_channels_no_channels():
    """fetch_channels raises ValueError('no_channels') when all networks return empty arrays."""
    empty_data = json.dumps([]).encode()

    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(empty_data)):
        with pytest.raises(ValueError, match="no_channels"):
            fetch_channels("testkey123", "hi")


def test_fetch_channels_skips_failed_network():
    """fetch_channels continues on non-auth HTTP errors; returns channels from successful networks."""
    channel_data = _mock_channel_json("Ambient", "ambient")
    call_count = [0]

    def side_effect(url, timeout=None):
        call_count[0] += 1
        if call_count[0] == 1:
            raise _make_http_error(500)
        return _urlopen_factory(channel_data)

    with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=side_effect):
        result = fetch_channels("testkey123", "hi")

    # First network failed (500), 5 remaining should succeed
    assert len(result) == 5


def test_quality_tier_mapping():
    """Quality hi->premium_high, med->premium, low->premium_medium in URLs."""
    channel_data = _mock_channel_json("Jazz", "jazz")

    for quality, expected_tier in [("hi", "premium_high"), ("med", "premium"), ("low", "premium_medium")]:
        with patch("musicstreamer.aa_import.urllib.request.urlopen",
                   side_effect=lambda url, timeout=None: _urlopen_factory(channel_data)):
            result = fetch_channels("testkey123", quality)
        for item in result:
            assert expected_tier in item["url"], f"quality={quality!r}: expected {expected_tier!r} in {item['url']!r}"


# ---------------------------------------------------------------------------
# import_stations tests
# ---------------------------------------------------------------------------

def test_import_creates_station():
    """import_stations inserts new station when URL is not already in library."""
    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False

    channels = [{"title": "Ambient", "url": "https://listen.di.fm/premium_high/ambient.pls?listen_key=x", "provider": "DI.fm"}]
    imported, skipped = import_stations(channels, mock_repo)

    mock_repo.insert_station.assert_called_once_with(
        name="Ambient",
        url="https://listen.di.fm/premium_high/ambient.pls?listen_key=x",
        provider_name="DI.fm",
        tags="",
    )
    assert imported == 1
    assert skipped == 0


def test_import_skips_duplicate():
    """import_stations skips stations whose URL already exists; returns (0, 1)."""
    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = True

    channels = [{"title": "Ambient", "url": "https://listen.di.fm/premium_high/ambient.pls?listen_key=x", "provider": "DI.fm"}]
    imported, skipped = import_stations(channels, mock_repo)

    mock_repo.insert_station.assert_not_called()
    assert imported == 0
    assert skipped == 1


def test_import_calls_on_progress():
    """on_progress is called after each entry with running (imported, skipped) counts."""
    mock_repo = MagicMock()
    # First entry: new, second entry: duplicate
    mock_repo.station_exists_by_url.side_effect = [False, True]

    channels = [
        {"title": "Ambient", "url": "https://listen.di.fm/premium_high/ambient.pls?listen_key=x", "provider": "DI.fm"},
        {"title": "Jazz", "url": "https://listen.jazzradio.com/premium_high/jazz.pls?listen_key=x", "provider": "JazzRadio"},
    ]

    progress_calls = []
    import_stations(channels, mock_repo, on_progress=lambda imp, skip: progress_calls.append((imp, skip)))

    assert progress_calls == [(1, 0), (1, 1)]
