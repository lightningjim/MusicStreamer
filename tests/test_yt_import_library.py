"""Tests for musicstreamer.yt_import library-API port (PORT-09 / D-17).

These tests mock ``yt_dlp.YoutubeDL`` so no network is needed. They verify:
- Happy path filters to currently-live entries
- ``live_status`` falls back when ``is_live`` is missing (RESEARCH Pitfall 1)
- Private playlist → ValueError; other DownloadError → RuntimeError
- ``cookiefile`` is added to opts iff ``paths.cookies_path()`` exists on disk
- ``is_yt_playlist_url`` regression
- ``import_stations`` regression (dedup + on_progress)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import yt_dlp

from musicstreamer import paths, yt_import


@pytest.fixture(autouse=True)
def _reset_root_override(tmp_path):
    """Redirect paths root to a per-test tmp dir; restore afterward."""
    saved = paths._root_override
    paths._root_override = str(tmp_path)
    yield
    paths._root_override = saved


def _patch_youtubedl(extract_info_return=None, extract_info_side_effect=None):
    """Helper: patch yt_dlp.YoutubeDL to return a context manager whose
    extract_info returns/raises the given value."""
    fake_ydl = MagicMock()
    if extract_info_side_effect is not None:
        fake_ydl.extract_info.side_effect = extract_info_side_effect
    else:
        fake_ydl.extract_info.return_value = extract_info_return
    cm = MagicMock()
    cm.__enter__.return_value = fake_ydl
    cm.__exit__.return_value = False
    youtubedl_cls = MagicMock(return_value=cm)
    return patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", youtubedl_cls), youtubedl_cls, fake_ydl


def test_scan_playlist_happy_path_returns_live_entries():
    info = {
        "entries": [
            {
                "title": "A",
                "url": "https://x/a",
                "is_live": True,
                "live_status": "is_live",
                "playlist_uploader": "Uploader",
            },
            {
                "title": "B",
                "url": "https://x/b",
                "is_live": False,
                "live_status": "was_live",
            },
        ]
    }
    p, _, _ = _patch_youtubedl(extract_info_return=info)
    with p:
        result = yt_import.scan_playlist("https://youtube.com/@lofigirl/streams")
    assert result == [
        {"title": "A", "url": "https://x/a", "provider": "Uploader"},
    ]


def test_scan_playlist_uses_live_status_when_is_live_missing():
    """Pitfall 1 — extract_flat may leave is_live as None for sparse entries."""
    info = {
        "entries": [
            {
                "title": "A",
                "url": "https://x/a",
                "is_live": None,
                "live_status": "is_live",
                "playlist_uploader": "Uploader",
            },
        ]
    }
    p, _, _ = _patch_youtubedl(extract_info_return=info)
    with p:
        result = yt_import.scan_playlist("https://youtube.com/@lofigirl/streams")
    assert len(result) == 1
    assert result[0]["title"] == "A"


def test_scan_playlist_private_raises_valueerror():
    err = yt_dlp.utils.DownloadError("Video is private")
    p, _, _ = _patch_youtubedl(extract_info_side_effect=err)
    with p, pytest.raises(ValueError, match="Playlist Not Accessible"):
        yt_import.scan_playlist("https://youtube.com/playlist?list=PRIVATE")


def test_scan_playlist_other_error_raises_runtimeerror():
    err = yt_dlp.utils.DownloadError("HTTP Error 500: Internal Server Error")
    p, _, _ = _patch_youtubedl(extract_info_side_effect=err)
    with p, pytest.raises(RuntimeError):
        yt_import.scan_playlist("https://youtube.com/@x/streams")


def test_scan_playlist_passes_cookies_when_file_exists(tmp_path):
    # tmp_path is already the root override via the autouse fixture.
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    info = {"entries": []}
    p, youtubedl_cls, _ = _patch_youtubedl(extract_info_return=info)
    with p:
        yt_import.scan_playlist("https://youtube.com/@x/streams")
    youtubedl_cls.assert_called_once()
    opts = youtubedl_cls.call_args.args[0]
    assert opts.get("cookiefile") == str(cookies)


def test_scan_playlist_omits_cookiefile_when_missing(tmp_path):
    # Ensure no cookies file exists.
    assert not (tmp_path / "cookies.txt").exists()
    info = {"entries": []}
    p, youtubedl_cls, _ = _patch_youtubedl(extract_info_return=info)
    with p:
        yt_import.scan_playlist("https://youtube.com/@x/streams")
    opts = youtubedl_cls.call_args.args[0]
    assert "cookiefile" not in opts


def test_is_yt_playlist_url_unchanged():
    assert yt_import.is_yt_playlist_url("https://www.youtube.com/playlist?list=PL123") is True
    assert yt_import.is_yt_playlist_url("https://www.youtube.com/@lofigirl/streams") is True
    assert yt_import.is_yt_playlist_url("https://example.com") is False


def test_import_stations_unchanged():
    class FakeRepo:
        def __init__(self):
            self.inserted: list[dict] = []
            self.existing: set[str] = {"https://x/dup"}

        def station_exists_by_url(self, url: str) -> bool:
            return url in self.existing

        def insert_station(self, name, url, provider_name, tags):
            self.inserted.append(
                {"name": name, "url": url, "provider_name": provider_name, "tags": tags}
            )
            self.existing.add(url)

    progress_calls: list[tuple[int, int]] = []

    def on_progress(imp, skp):
        progress_calls.append((imp, skp))

    repo = FakeRepo()
    entries = [
        {"title": "A", "url": "https://x/a", "provider": "P1"},
        {"title": "Dup", "url": "https://x/dup", "provider": "P2"},
        {"title": "B", "url": "https://x/b", "provider": "P3"},
    ]
    imported, skipped = yt_import.import_stations(entries, repo, on_progress=on_progress)
    assert (imported, skipped) == (2, 1)
    assert len(repo.inserted) == 2
    assert repo.inserted[0] == {
        "name": "A",
        "url": "https://x/a",
        "provider_name": "P1",
        "tags": "",
    }
    assert progress_calls == [(1, 0), (1, 1), (2, 1)]
