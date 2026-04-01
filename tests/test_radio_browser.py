import io
import json
import unittest.mock
from unittest.mock import MagicMock, patch
import urllib.error

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_urlopen_mock(data):
    """Return a mock that behaves like urllib.request.urlopen context manager."""
    body = json.dumps(data).encode()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=io.BytesIO(body))
    cm.__exit__ = MagicMock(return_value=False)
    return cm


SAMPLE_STATIONS = [
    {
        "name": "Jazz FM",
        "url": "http://jazz.fm/stream",
        "url_resolved": "http://jazz.fm/stream128",
        "tags": "jazz,smooth jazz",
        "countrycode": "US",
        "country": "The United States Of America",
        "bitrate": 128,
        "homepage": "https://www.jazz.fm",
        "network": "Jazz Network",
        "lastcheckok": 1,
        "votes": 500,
    },
    {
        "name": "Blues Radio",
        "url": "http://blues.example.com/stream",
        "url_resolved": "http://blues.example.com/stream",
        "tags": "blues",
        "countrycode": "US",
        "country": "The United States Of America",
        "bitrate": 96,
        "homepage": "https://blues.example.com",
        "network": "",
        "lastcheckok": 1,
        "votes": 200,
    },
]

SAMPLE_TAGS = [
    {"name": "pop", "stationcount": 5079},
    {"name": "music", "stationcount": 4004},
    {"name": "jazz", "stationcount": 1200},
]

SAMPLE_COUNTRIES = [
    {"name": "The United States Of America", "iso_3166_1": "US", "stationcount": 6785},
    {"name": "Germany", "iso_3166_1": "DE", "stationcount": 3000},
    {"name": "Unknown", "iso_3166_1": "", "stationcount": 100},  # should be skipped
]


# ---------------------------------------------------------------------------
# search_stations tests
# ---------------------------------------------------------------------------

def test_search_stations_returns_list_of_dicts():
    import musicstreamer.radio_browser as rb
    mock_cm = _make_urlopen_mock(SAMPLE_STATIONS)
    with patch("musicstreamer.radio_browser.urllib.request.urlopen", return_value=mock_cm):
        results = rb.search_stations("jazz")
    assert isinstance(results, list)
    assert len(results) == 2
    assert isinstance(results[0], dict)


def test_search_stations_required_keys():
    import musicstreamer.radio_browser as rb
    mock_cm = _make_urlopen_mock(SAMPLE_STATIONS)
    with patch("musicstreamer.radio_browser.urllib.request.urlopen", return_value=mock_cm):
        results = rb.search_stations("jazz")
    for key in ("name", "url", "tags", "countrycode", "bitrate", "homepage", "network"):
        assert key in results[0], f"Missing key: {key}"


def test_search_stations_url_contains_base_and_params():
    import musicstreamer.radio_browser as rb
    captured_urls = []

    def fake_urlopen(url, timeout=10):
        captured_urls.append(url)
        return _make_urlopen_mock(SAMPLE_STATIONS)

    with patch("musicstreamer.radio_browser.urllib.request.urlopen", side_effect=fake_urlopen):
        rb.search_stations("jazz", tag="blues", countrycode="US")

    assert len(captured_urls) == 1
    url = captured_urls[0]
    assert "all.api.radio-browser.info" in url
    assert "name=jazz" in url
    assert "tag=blues" in url
    assert "countrycode=US" in url
    assert "hidebroken=true" in url
    assert "order=votes" in url
    assert "reverse=true" in url
    assert "limit=" in url


def test_search_stations_omits_empty_optional_params():
    import musicstreamer.radio_browser as rb
    captured_urls = []

    def fake_urlopen(url, timeout=10):
        captured_urls.append(url)
        return _make_urlopen_mock(SAMPLE_STATIONS)

    with patch("musicstreamer.radio_browser.urllib.request.urlopen", side_effect=fake_urlopen):
        rb.search_stations("jazz")  # no tag, no countrycode

    url = captured_urls[0]
    assert "tag=" not in url
    assert "countrycode=" not in url


def test_search_stations_network_error_raises():
    import musicstreamer.radio_browser as rb
    with patch(
        "musicstreamer.radio_browser.urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        with pytest.raises(urllib.error.URLError):
            rb.search_stations("jazz")


# ---------------------------------------------------------------------------
# fetch_tags tests
# ---------------------------------------------------------------------------

def test_fetch_tags_returns_list_of_strings():
    import musicstreamer.radio_browser as rb
    mock_cm = _make_urlopen_mock(SAMPLE_TAGS)
    with patch("musicstreamer.radio_browser.urllib.request.urlopen", return_value=mock_cm):
        tags = rb.fetch_tags()
    assert isinstance(tags, list)
    assert all(isinstance(t, str) for t in tags)
    assert tags == ["pop", "music", "jazz"]


def test_fetch_tags_url_contains_limit():
    import musicstreamer.radio_browser as rb
    captured_urls = []

    def fake_urlopen(url, timeout=10):
        captured_urls.append(url)
        return _make_urlopen_mock(SAMPLE_TAGS)

    with patch("musicstreamer.radio_browser.urllib.request.urlopen", side_effect=fake_urlopen):
        rb.fetch_tags(limit=5)

    assert "limit=5" in captured_urls[0]


# ---------------------------------------------------------------------------
# fetch_countries tests
# ---------------------------------------------------------------------------

def test_fetch_countries_returns_list_of_tuples():
    import musicstreamer.radio_browser as rb
    mock_cm = _make_urlopen_mock(SAMPLE_COUNTRIES)
    with patch("musicstreamer.radio_browser.urllib.request.urlopen", return_value=mock_cm):
        countries = rb.fetch_countries()
    assert isinstance(countries, list)
    for item in countries:
        assert isinstance(item, tuple)
        assert len(item) == 2


def test_fetch_countries_skips_empty_iso():
    import musicstreamer.radio_browser as rb
    mock_cm = _make_urlopen_mock(SAMPLE_COUNTRIES)
    with patch("musicstreamer.radio_browser.urllib.request.urlopen", return_value=mock_cm):
        countries = rb.fetch_countries()
    # SAMPLE_COUNTRIES has 3 entries but one has empty iso_3166_1 — should be 2
    assert len(countries) == 2
    iso_codes = [c[0] for c in countries]
    assert "US" in iso_codes
    assert "DE" in iso_codes
    assert "" not in iso_codes


def test_fetch_countries_tuple_order():
    import musicstreamer.radio_browser as rb
    mock_cm = _make_urlopen_mock(SAMPLE_COUNTRIES)
    with patch("musicstreamer.radio_browser.urllib.request.urlopen", return_value=mock_cm):
        countries = rb.fetch_countries()
    # First element is iso code, second is name
    assert countries[0] == ("US", "The United States Of America")
