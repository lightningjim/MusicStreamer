import json
import urllib.error
from unittest.mock import MagicMock, patch, call

import pytest

from musicstreamer.aa_import import _resolve_pls, fetch_channels, import_stations


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
               side_effect=lambda url, timeout=None: _urlopen_factory(channel_data)), \
         patch("musicstreamer.aa_import._resolve_pls", side_effect=lambda url: url):
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

    with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=side_effect), \
         patch("musicstreamer.aa_import._resolve_pls", side_effect=lambda url: url):
        result = fetch_channels("testkey123", "hi")

    # First network failed (500), 5 remaining should succeed
    assert len(result) == 5


def test_quality_tier_mapping():
    """Quality hi->premium_high, med->premium, low->premium_medium in URLs."""
    channel_data = _mock_channel_json("Jazz", "jazz")

    for quality, expected_tier in [("hi", "premium_high"), ("med", "premium"), ("low", "premium_medium")]:
        with patch("musicstreamer.aa_import.urllib.request.urlopen",
                   side_effect=lambda url, timeout=None: _urlopen_factory(channel_data)), \
             patch("musicstreamer.aa_import._resolve_pls", side_effect=lambda url: url):
            result = fetch_channels("testkey123", quality)
        for item in result:
            assert expected_tier in item["url"], f"quality={quality!r}: expected {expected_tier!r} in {item['url']!r}"


def test_resolve_pls():
    """_resolve_pls fetches a PLS URL and returns the File1 stream URL."""
    pls_content = b"[playlist]\nNumberOfEntries=2\nFile1=http://prem1.di.fm:80/ambient_hi?key\nFile2=http://prem4.di.fm:80/ambient_hi?key\n"

    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(pls_content)):
        result = _resolve_pls("https://listen.di.fm/premium_high/ambient.pls?listen_key=key")

    assert result == "http://prem1.di.fm:80/ambient_hi?key"


def test_resolve_pls_fallback_on_error():
    """_resolve_pls returns the original URL if resolution fails."""
    pls_url = "https://listen.di.fm/premium_high/ambient.pls?listen_key=key"

    with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=Exception("network error")):
        result = _resolve_pls(pls_url)

    assert result == pls_url


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


# ---------------------------------------------------------------------------
# _normalize_aa_image_url tests
# ---------------------------------------------------------------------------

def test_normalize_aa_image_url():
    from musicstreamer.aa_import import _normalize_aa_image_url
    raw = "//cdn-images.audioaddict.com/abc/file.png{?size,height,width,quality,pad}"
    assert _normalize_aa_image_url(raw) == "https://cdn-images.audioaddict.com/abc/file.png"


def test_normalize_aa_image_url_already_https():
    from musicstreamer.aa_import import _normalize_aa_image_url
    raw = "https://cdn-images.audioaddict.com/abc/file.png"
    assert _normalize_aa_image_url(raw) == "https://cdn-images.audioaddict.com/abc/file.png"


# ---------------------------------------------------------------------------
# fetch_channels image_url tests
# ---------------------------------------------------------------------------

def _mock_channel_with_image_json(name: str, key: str, image_url: str) -> bytes:
    return json.dumps([{
        "name": name,
        "key": key,
        "images": {"square": image_url},
    }]).encode()


def _api_channels_json(name: str, key: str, image_url: str) -> bytes:
    return json.dumps([{
        "name": name,
        "key": key,
        "images": {"square": image_url},
    }]).encode()


def test_fetch_channels_includes_image_url():
    """fetch_channels returns image_url per channel from AA API."""
    raw_img = "//cdn-images.audioaddict.com/abc/file.png{?size}"
    listen_data = _mock_channel_json("Ambient", "ambient")
    api_data = _api_channels_json("Ambient", "ambient", raw_img)

    def urlopen_side_effect(url, timeout=None):
        if "api.audioaddict.com" in url:
            return _urlopen_factory(api_data)
        return _urlopen_factory(listen_data)

    with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=urlopen_side_effect), \
         patch("musicstreamer.aa_import._resolve_pls", side_effect=lambda url: url):
        result = fetch_channels("testkey123", "hi")

    assert len(result) == 6
    for item in result:
        assert "image_url" in item
        assert item["image_url"] == "https://cdn-images.audioaddict.com/abc/file.png"


def test_fetch_channels_image_url_none_on_failure():
    """When _fetch_image_map returns empty, channel dicts have image_url=None."""
    listen_data = _mock_channel_json("Ambient", "ambient")

    def urlopen_side_effect(url, timeout=None):
        if "api.audioaddict.com" in url:
            raise Exception("network error")
        return _urlopen_factory(listen_data)

    with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=urlopen_side_effect), \
         patch("musicstreamer.aa_import._resolve_pls", side_effect=lambda url: url):
        result = fetch_channels("testkey123", "hi")

    assert len(result) == 6
    for item in result:
        assert "image_url" in item
        assert item["image_url"] is None


# ---------------------------------------------------------------------------
# import_stations logo download tests
# ---------------------------------------------------------------------------

def test_import_stations_calls_update_art():
    """When channel has image_url and download succeeds, update_station_art is called."""
    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.return_value = 42

    channels = [{
        "title": "Ambient",
        "url": "https://listen.di.fm/premium_high/ambient?listen_key=x",
        "provider": "DI.fm",
        "image_url": "https://cdn-images.audioaddict.com/abc/file.png",
    }]

    logo_progress_calls = []
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read = MagicMock(return_value=png_bytes)

    with patch("musicstreamer.aa_import.urllib.request.urlopen", return_value=mock_resp), \
         patch("musicstreamer.aa_import.copy_asset_for_station", return_value="assets/42/station_art.png") as mock_copy, \
         patch("musicstreamer.aa_import.db_connect") as mock_db_connect:
        mock_thread_repo = MagicMock()
        mock_db_repo_instance = MagicMock()
        mock_db_repo_instance.__enter__ = MagicMock(return_value=mock_db_repo_instance)
        from musicstreamer.repo import Repo as RealRepo
        with patch("musicstreamer.aa_import.Repo") as mock_repo_cls:
            mock_repo_cls.return_value = mock_thread_repo
            imported, skipped = import_stations(
                channels, mock_repo,
                on_logo_progress=lambda done, total: logo_progress_calls.append((done, total))
            )

    assert imported == 1
    assert skipped == 0
    mock_thread_repo.update_station_art.assert_called_once()
    # (0, total) is emitted before downloads start, then (1, 1) after first completes
    assert (0, 1) in logo_progress_calls
    assert (1, 1) in logo_progress_calls


def test_import_stations_logo_failure_silent():
    """When logo download fails, station is still imported, no exception, update_station_art not called."""
    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.return_value = 99

    channels = [{
        "title": "Ambient",
        "url": "https://listen.di.fm/premium_high/ambient?listen_key=x",
        "provider": "DI.fm",
        "image_url": "https://cdn-images.audioaddict.com/abc/file.png",
    }]

    with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=Exception("network error")), \
         patch("musicstreamer.aa_import.db_connect") as mock_db_connect, \
         patch("musicstreamer.aa_import.Repo") as mock_repo_cls:
        mock_thread_repo = MagicMock()
        mock_repo_cls.return_value = mock_thread_repo
        imported, skipped = import_stations(channels, mock_repo)

    assert imported == 1
    assert skipped == 0
    mock_thread_repo.update_station_art.assert_not_called()
