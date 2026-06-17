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
from musicstreamer.runtime_check import NodeRuntime


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
    import tempfile as _tempfile
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    info = {"entries": []}
    p, youtubedl_cls, _ = _patch_youtubedl(extract_info_return=info)
    with p:
        yt_import.scan_playlist("https://youtube.com/@x/streams")
    youtubedl_cls.assert_called_once()
    opts = youtubedl_cls.call_args.args[0]
    # Phase 999.7: cookiefile is now a per-call temp copy, not the canonical path.
    cf = opts.get("cookiefile")
    assert cf is not None, "cookiefile must be set when canonical file exists"
    assert cf != str(cookies), "cookiefile must NOT point at canonical path (Phase 999.7 temp-copy)"
    assert cf.startswith(_tempfile.gettempdir()), f"expected temp path, got {cf}"


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


def test_scan_playlist_passes_node_path_when_available():
    """B-79-07: scan_playlist threads NodeRuntime.path into yt_dlp opts."""
    p, youtubedl_cls, _ = _patch_youtubedl(extract_info_return={"entries": []})
    with p:
        yt_import.scan_playlist(
            "https://youtube.com/@x/streams",
            node_runtime=NodeRuntime(available=True, path="/fake/node"),
        )
    opts = youtubedl_cls.call_args[0][0]
    assert opts["js_runtimes"] == {"node": {"path": "/fake/node"}}


def test_scan_playlist_default_none_node_runtime():
    """B-79-08: scan_playlist default (no node_runtime kwarg) yields {'path': None}."""
    p, youtubedl_cls, _ = _patch_youtubedl(extract_info_return={"entries": []})
    with p:
        yt_import.scan_playlist("https://youtube.com/@x/streams")
    opts = youtubedl_cls.call_args[0][0]
    assert opts["js_runtimes"] == {"node": {"path": None}}


def test_scan_playlist_passes_none_when_unavailable():
    """B-79-09: scan_playlist with NodeRuntime(available=False, path=None) yields {'path': None} (D-02)."""
    p, youtubedl_cls, _ = _patch_youtubedl(extract_info_return={"entries": []})
    with p:
        yt_import.scan_playlist(
            "https://youtube.com/@x/streams",
            node_runtime=NodeRuntime(available=False, path=None),
        )
    opts = youtubedl_cls.call_args[0][0]
    assert opts["js_runtimes"] == {"node": {"path": None}}


# ---------------------------------------------------------------------------
# ART-AVATAR-03: fetch_channel_avatar field-filter tests (Task 1 / Phase 89-02)
# ---------------------------------------------------------------------------

def _make_channel_info(thumbnails):
    """Return a minimal yt-dlp info dict (channel page type) with the given thumbnails."""
    return {"thumbnails": thumbnails, "_type": "channel"}


def test_avatar_prefers_avatar_uncropped():
    """ART-AVATAR-03: avatar_uncropped entry is selected over numeric-id entries."""
    thumbnails = [
        {"id": "0", "url": "http://cropped.jpg", "width": 200, "height": 200},
        {"id": "avatar_uncropped", "url": "http://uncropped.jpg"},
    ]
    info = _make_channel_info(thumbnails)
    fake_bytes = b"\x89PNG\r\n\x1a\n"  # PNG magic
    p, _, fake_ydl = _patch_youtubedl(extract_info_return=info)
    with p, patch("urllib.request.urlopen") as mock_urlopen:
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = fake_bytes
        mock_urlopen.return_value = resp
        result = yt_import.fetch_channel_avatar("https://www.youtube.com/@TestChannel")
    assert result == fake_bytes
    # Verify the URL used to download was the uncropped one
    mock_urlopen.assert_called_once()
    call_args = mock_urlopen.call_args
    assert "uncropped" in call_args[0][0]


def test_avatar_raises_when_no_avatar_entry():
    """ART-AVATAR-03: raises ValueError when no avatar_uncropped or avatar entry exists."""
    thumbnails = [
        {"id": "0", "url": "http://banner.jpg", "width": 2560, "height": 1440},
    ]
    info = _make_channel_info(thumbnails)
    p, _, _ = _patch_youtubedl(extract_info_return=info)
    with p, pytest.raises(ValueError, match="No channel avatar found"):
        yt_import.fetch_channel_avatar("https://www.youtube.com/@TestChannel")


def test_avatar_rejects_non_square_entry():
    """ART-AVATAR-03: raises ValueError when width and height are both present and unequal."""
    thumbnails = [
        {"id": "avatar_uncropped", "url": "http://bad.jpg", "width": 200, "height": 150},
    ]
    info = _make_channel_info(thumbnails)
    p, _, _ = _patch_youtubedl(extract_info_return=info)
    with p, pytest.raises(ValueError, match="not square"):
        yt_import.fetch_channel_avatar("https://www.youtube.com/@TestChannel")


def test_avatar_allows_none_dimensions():
    """ART-AVATAR-03 / RESEARCH.md Pitfall 2: None dims must NOT be rejected.

    avatar_uncropped has no width/height; None != None is False in Python so the
    entry must pass through the null-safe square-guard unchanged.
    """
    thumbnails = [
        {"id": "avatar_uncropped", "url": "http://uncropped.jpg"},  # no width/height
    ]
    info = _make_channel_info(thumbnails)
    fake_bytes = b"\xff\xd8\xff"  # JPEG magic
    p, _, _ = _patch_youtubedl(extract_info_return=info)
    with p, patch("urllib.request.urlopen") as mock_urlopen:
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = fake_bytes
        mock_urlopen.return_value = resp
        result = yt_import.fetch_channel_avatar("https://www.youtube.com/@TestChannel")
    assert result == fake_bytes


def test_avatar_opts_do_not_contain_extract_flat():
    """RESEARCH.md Pitfall 3: extract_flat must NOT appear in the avatar fetch opts."""
    thumbnails = [{"id": "avatar_uncropped", "url": "http://uncropped.jpg"}]
    info = _make_channel_info(thumbnails)
    p, youtubedl_cls, _ = _patch_youtubedl(extract_info_return=info)
    with p, patch("urllib.request.urlopen") as mock_urlopen:
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = b"\xff\xd8\xff"
        mock_urlopen.return_value = resp
        yt_import.fetch_channel_avatar("https://www.youtube.com/@TestChannel")
    opts = youtubedl_cls.call_args[0][0]
    assert "extract_flat" not in opts, "extract_flat must NOT be in avatar fetch opts (Pitfall 3)"


def test_avatar_opts_bound_playlist_items_to_zero():
    """Phase 89 UAT gap: a bare channel URL with no playlist bound makes yt-dlp
    recursively extract every video in the channel (since extract_flat is omitted),
    hanging on large channels. The avatar lives at the channel level, so
    playlist_items="0" must bound extraction to channel metadata only."""
    thumbnails = [{"id": "avatar_uncropped", "url": "http://uncropped.jpg"}]
    info = _make_channel_info(thumbnails)
    p, youtubedl_cls, _ = _patch_youtubedl(extract_info_return=info)
    with p, patch("urllib.request.urlopen") as mock_urlopen:
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = b"\xff\xd8\xff"
        mock_urlopen.return_value = resp
        yt_import.fetch_channel_avatar("https://www.youtube.com/@TestChannel")
    opts = youtubedl_cls.call_args[0][0]
    assert opts.get("playlist_items") == "0", (
        "avatar fetch opts must bound playlist_items to '0' so a channel URL does "
        "not trigger full per-video extraction (UAT hang)"
    )


def test_avatar_video_url_two_step_resolution():
    """ART-AVATAR-03 / RESEARCH.md Open Question 3: video URL resolves to channel_url first."""
    # First call returns a video info dict (no thumbnails / no avatar_uncropped)
    video_info = {
        "_type": "video",
        "thumbnails": [{"id": "0", "url": "http://video-thumb.jpg", "width": 320, "height": 180}],
        "channel_url": "https://www.youtube.com/@TestChannel",
    }
    # Second call (re-resolved on channel URL) returns avatar
    channel_info = {
        "_type": "channel",
        "thumbnails": [
            {"id": "avatar_uncropped", "url": "http://channel-avatar.jpg"},
        ],
    }
    fake_bytes = b"\x89PNG\r\n\x1a\n"

    fake_ydl = MagicMock()
    fake_ydl.extract_info.side_effect = [video_info, channel_info]
    cm = MagicMock()
    cm.__enter__.return_value = fake_ydl
    cm.__exit__.return_value = False
    youtubedl_cls = MagicMock(return_value=cm)

    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", youtubedl_cls):
        with patch("urllib.request.urlopen") as mock_urlopen:
            resp = MagicMock()
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = fake_bytes
            mock_urlopen.return_value = resp
            result = yt_import.fetch_channel_avatar("https://www.youtube.com/watch?v=abc123")
    assert result == fake_bytes
    # Verify two-step: extract_info called twice
    assert fake_ydl.extract_info.call_count == 2
    # Second call should have been on the channel_url
    second_call_url = fake_ydl.extract_info.call_args_list[1][0][0]
    assert "TestChannel" in second_call_url or "youtube.com" in second_call_url


# ---------------------------------------------------------------------------
# D-04: Per-provider avatar fetcher registry tests (Task 2 / Phase 89-02)
# ---------------------------------------------------------------------------

def test_avatar_registry_youtube_registered():
    """D-04: get_avatar_fetcher('youtube') returns fetch_channel_avatar after module import."""
    fetcher = yt_import.get_avatar_fetcher("youtube")
    assert fetcher is not None, "youtube fetcher must be registered at module load"
    assert fetcher is yt_import.fetch_channel_avatar


# ---------------------------------------------------------------------------
# BUG-11 / D-02: fetch_channel_avatar node_runtime threading tests
# (mirrors scan_playlist node-threading tests at L179-209)
# ---------------------------------------------------------------------------

def _make_avatar_urlopen_mock(fake_bytes: bytes):
    """Return a mock suitable for patch("urllib.request.urlopen") in avatar tests."""
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = fake_bytes
    return resp


def test_fetch_channel_avatar_passes_node_path_when_available():
    """BUG-11: fetch_channel_avatar threads NodeRuntime.path into yt_dlp opts.

    GNOME .desktop launchers strip the shell PATH, so yt-dlp's own PATH-lookup
    for node fails. Passing an absolute node path via build_js_runtimes bypasses
    the PATH entirely. This mirrors the identical fix for scan_playlist (B-79-07).
    """
    thumbnails = [{"id": "avatar_uncropped", "url": "http://uncropped.jpg"}]
    info = _make_channel_info(thumbnails)
    p, youtubedl_cls, _ = _patch_youtubedl(extract_info_return=info)
    with p, patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_avatar_urlopen_mock(b"\x89PNG\r\n\x1a\n")
        yt_import.fetch_channel_avatar(
            "https://www.youtube.com/@TestChannel",
            node_runtime=NodeRuntime(available=True, path="/usr/local/bin/node"),
        )
    opts = youtubedl_cls.call_args[0][0]
    assert opts["js_runtimes"] == {"node": {"path": "/usr/local/bin/node"}}


def test_fetch_channel_avatar_default_none_node_runtime():
    """BUG-11: fetch_channel_avatar with no node_runtime kwarg yields {'path': None}.

    Preserves yt-dlp's own PATH-lookup fallback for callers that don't supply
    a NodeRuntime (registry callees, tests, Twitch). Mirrors B-79-08.
    """
    thumbnails = [{"id": "avatar_uncropped", "url": "http://uncropped.jpg"}]
    info = _make_channel_info(thumbnails)
    p, youtubedl_cls, _ = _patch_youtubedl(extract_info_return=info)
    with p, patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_avatar_urlopen_mock(b"\x89PNG\r\n\x1a\n")
        yt_import.fetch_channel_avatar("https://www.youtube.com/@TestChannel")
    opts = youtubedl_cls.call_args[0][0]
    assert opts["js_runtimes"] == {"node": {"path": None}}


def test_fetch_channel_avatar_passes_none_when_unavailable():
    """BUG-11: NodeRuntime(available=False, path=None) still yields {'path': None}.

    An unavailable runtime should not inject a bogus path. Mirrors B-79-09.
    """
    thumbnails = [{"id": "avatar_uncropped", "url": "http://uncropped.jpg"}]
    info = _make_channel_info(thumbnails)
    p, youtubedl_cls, _ = _patch_youtubedl(extract_info_return=info)
    with p, patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_avatar_urlopen_mock(b"\x89PNG\r\n\x1a\n")
        yt_import.fetch_channel_avatar(
            "https://www.youtube.com/@TestChannel",
            node_runtime=NodeRuntime(available=False, path=None),
        )
    opts = youtubedl_cls.call_args[0][0]
    assert opts["js_runtimes"] == {"node": {"path": None}}


def test_avatar_registry_twitch_registered_in_phase_89b():
    """Phase 89b (ART-AVATAR-04): get_avatar_fetcher('twitch') resolves the Twitch fetcher.

    Supersedes the Phase 89 precondition (twitch absent). 89B-01 registers
    twitch_helix.fetch_channel_avatar at module load via register_avatar_fetcher.
    """
    from musicstreamer import twitch_helix
    fetcher = yt_import.get_avatar_fetcher("twitch")
    assert fetcher is twitch_helix.fetch_channel_avatar, (
        "twitch fetcher must be registered in Phase 89b"
    )


def test_avatar_registry_register_and_retrieve():
    """D-04: register_avatar_fetcher then get_avatar_fetcher returns the registered callable."""
    def fake_twitch_fetcher(url: str) -> bytes:
        return b"twitch-avatar"

    # Save original so we can restore after test
    original = yt_import._AVATAR_FETCHERS.copy()
    try:
        yt_import.register_avatar_fetcher("twitch", fake_twitch_fetcher)
        result = yt_import.get_avatar_fetcher("twitch")
        assert result is fake_twitch_fetcher
    finally:
        yt_import._AVATAR_FETCHERS.clear()
        yt_import._AVATAR_FETCHERS.update(original)


def test_avatar_registry_unknown_provider_returns_none():
    """D-04: unknown provider returns None."""
    assert yt_import.get_avatar_fetcher("unknown_provider_xyz") is None
