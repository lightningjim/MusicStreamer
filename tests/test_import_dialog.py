from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test data (library-API format — dicts from yt_dlp.extract_info)
# ---------------------------------------------------------------------------

LIVE_ENTRY = {
    "title": "Lofi Radio",
    "url": "https://www.youtube.com/watch?v=abc123",
    "is_live": True,
    "playlist_channel": "Lofi Girl",
    "playlist_uploader": "Lofi Girl",
}

NON_LIVE_ENTRY = {
    "title": "Old Video",
    "url": "https://www.youtube.com/watch?v=xyz789",
    "is_live": None,
    "playlist_channel": "Lofi Girl",
    "playlist_uploader": "Lofi Girl",
}

WAS_LIVE_ENTRY = {
    "title": "Past Stream",
    "url": "https://www.youtube.com/watch?v=def456",
    "is_live": False,
    "playlist_channel": "Lofi Girl",
    "playlist_uploader": "Lofi Girl",
}

SECOND_LIVE_ENTRY = {
    "title": "Jazz Live",
    "url": "https://www.youtube.com/watch?v=jjj999",
    "is_live": True,
    "playlist_channel": "Jazz Channel",
    "playlist_uploader": "Jazz Channel",
}


def _fake_ydl_returning(entries):
    """Build a fake yt_dlp.YoutubeDL class that returns ``entries`` as a
    playlist ``info`` dict on ``extract_info``."""

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"entries": list(entries)}

    return FakeYDL


# ---------------------------------------------------------------------------
# test_scan_filters_live_only
# ---------------------------------------------------------------------------

def test_scan_filters_live_only():
    """scan_playlist returns only entries where live_status/is_live indicates live."""
    from musicstreamer.yt_import import scan_playlist

    fake_ydl = _fake_ydl_returning([LIVE_ENTRY, NON_LIVE_ENTRY, WAS_LIVE_ENTRY])
    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", fake_ydl):
        entries = scan_playlist("https://www.youtube.com/playlist?list=PL123")

    assert len(entries) == 1
    assert entries[0]["title"] == "Lofi Radio"
    assert entries[0]["url"] == "https://www.youtube.com/watch?v=abc123"


# ---------------------------------------------------------------------------
# test_parse_flat_playlist_json
# ---------------------------------------------------------------------------

def test_parse_flat_playlist_json():
    """scan_playlist produces list of dicts with 'title', 'url', 'provider' keys."""
    from musicstreamer.yt_import import scan_playlist

    fake_ydl = _fake_ydl_returning([LIVE_ENTRY, SECOND_LIVE_ENTRY])
    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", fake_ydl):
        entries = scan_playlist("https://www.youtube.com/playlist?list=PL123")

    assert len(entries) == 2
    for entry in entries:
        assert "title" in entry
        assert "url" in entry
        assert "provider" in entry


# ---------------------------------------------------------------------------
# test_provider_from_playlist_channel
# ---------------------------------------------------------------------------

def test_provider_from_playlist_channel():
    """Provider comes from playlist_channel; falls back to playlist_uploader if empty."""
    from musicstreamer.yt_import import scan_playlist

    entry_with_channel = {
        "title": "Live Stream",
        "url": "https://www.youtube.com/watch?v=aaaaa1",
        "is_live": True,
        "playlist_channel": "Lofi Girl",
        "playlist_uploader": "SomeOtherName",
    }

    entry_no_channel = {
        "title": "Another Stream",
        "url": "https://www.youtube.com/watch?v=bbbbb2",
        "is_live": True,
        "playlist_channel": "",
        "playlist_uploader": "FallbackName",
    }

    fake_ydl = _fake_ydl_returning([entry_with_channel, entry_no_channel])
    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", fake_ydl):
        entries = scan_playlist("https://www.youtube.com/playlist?list=PL123")

    assert entries[0]["provider"] == "Lofi Girl"
    assert entries[1]["provider"] == "FallbackName"


# ---------------------------------------------------------------------------
# test_import_skips_duplicate
# ---------------------------------------------------------------------------

def test_import_skips_duplicate():
    """When repo.station_exists_by_url returns True, entry is skipped (not inserted)."""
    from musicstreamer.yt_import import import_stations

    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = True

    entries = [
        {"title": "Lofi Radio", "url": "https://www.youtube.com/watch?v=abc123", "provider": "Lofi Girl"},
    ]

    imported, skipped = import_stations(entries, mock_repo)

    mock_repo.insert_station.assert_not_called()
    assert imported == 0
    assert skipped == 1


# ---------------------------------------------------------------------------
# test_import_creates_station
# ---------------------------------------------------------------------------

def test_import_creates_station():
    """When repo.station_exists_by_url returns False, repo.insert_station called correctly."""
    from musicstreamer.yt_import import import_stations

    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False

    entries = [
        {"title": "Lofi Radio", "url": "https://www.youtube.com/watch?v=abc123", "provider": "Lofi Girl"},
    ]

    imported, skipped = import_stations(entries, mock_repo)

    mock_repo.insert_station.assert_called_once_with(
        name="Lofi Radio",
        url="https://www.youtube.com/watch?v=abc123",
        provider_name="Lofi Girl",
        tags="",
    )
    assert imported == 1
    assert skipped == 0


# ---------------------------------------------------------------------------
# test_is_yt_playlist_url
# ---------------------------------------------------------------------------

def test_is_yt_playlist_url():
    """Validates youtube.com/playlist?list=..., /@Channel/streams, /@Channel/live patterns;
    rejects non-playlist URLs."""
    from musicstreamer.yt_import import is_yt_playlist_url

    # Valid patterns
    assert is_yt_playlist_url("https://www.youtube.com/playlist?list=PLabc123") is True
    assert is_yt_playlist_url("https://youtube.com/playlist?list=PLxyz&si=extra") is True
    assert is_yt_playlist_url("https://www.youtube.com/@LofiGirl/streams") is True
    assert is_yt_playlist_url("https://www.youtube.com/@LofiGirl/live") is True
    assert is_yt_playlist_url("https://www.youtube.com/@SomeChannel/videos") is True

    # Invalid patterns
    assert is_yt_playlist_url("https://www.youtube.com/watch?v=abc123") is False
    assert is_yt_playlist_url("https://www.youtube.com/@LofiGirl") is False
    assert is_yt_playlist_url("https://www.youtube.com/@LofiGirl/about") is False
    assert is_yt_playlist_url("https://soundcloud.com/some-playlist") is False
    assert is_yt_playlist_url("not a url") is False
