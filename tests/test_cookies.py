"""Tests for cookie handling in yt_import + YouTube playback.

Plan 35-06:
- yt_import uses the yt_dlp library API with cookiefile option.
- _play_youtube also uses the yt_dlp library API -- no external player,
  no temp-file copying. Cookies (if present) are passed directly as the
  ``cookiefile`` option alongside the EJS JS challenge solver
  extractor_args, and yt_dlp resolves the direct HLS URL which is fed
  to GStreamer playbin3.
- The monkeypatch target for all cookie tests is
  ``musicstreamer.paths._root_override`` -- yt_import and player both
  route through ``paths.cookies_path()``.
"""
import os
from unittest.mock import MagicMock, patch

from musicstreamer.player import Player


def make_player(qtbot):
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    return player


# ---------------------------------------------------------------------------
# paths.cookies_path accessor test
# ---------------------------------------------------------------------------

def test_cookie_path_resolves_under_root(tmp_path, monkeypatch):
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    assert paths.cookies_path() == str(tmp_path / "cookies.txt")


def test_cookie_path_constant_via_constants_getattr(tmp_path, monkeypatch):
    """musicstreamer.constants.COOKIES_PATH delegates to paths.cookies_path()."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer import constants
    assert constants.COOKIES_PATH == os.path.join(str(tmp_path), "cookies.txt")


# ---------------------------------------------------------------------------
# yt_import library-API cookie injection
# ---------------------------------------------------------------------------

def test_ytdlp_passes_cookiefile_when_file_exists(tmp_path, monkeypatch):
    """scan_playlist passes cookiefile=<path> to yt_dlp.YoutubeDL when the
    cookies file exists under paths.cookies_path()."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n")

    captured_opts = {}

    class FakeYDL:
        def __init__(self, opts):
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"entries": []}

    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", FakeYDL):
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")

    assert captured_opts.get("cookiefile") == str(cookies_file)


def test_ytdlp_omits_cookiefile_when_absent(tmp_path, monkeypatch):
    """scan_playlist omits the ``cookiefile`` option when the file does not exist."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    # Do NOT create the file.

    captured_opts = {}

    class FakeYDL:
        def __init__(self, opts):
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"entries": []}

    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", FakeYDL):
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")

    assert "cookiefile" not in captured_opts


# ---------------------------------------------------------------------------
# YouTube playback cookie injection (Plan 35-06: yt-dlp library API path)
# ---------------------------------------------------------------------------

def test_youtube_resolve_passes_cookiefile_when_present(tmp_path, monkeypatch, qtbot):
    """_youtube_resolve_worker passes cookiefile=<path> to yt_dlp.YoutubeDL
    when cookies.txt exists, alongside the EJS extractor_args."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n")

    captured_opts = {}

    class FakeYDL:
        def __init__(self, opts):
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"url": "http://resolved.example/stream.m3u8"}

    import yt_dlp
    player = make_player(qtbot)
    with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")

    assert captured_opts.get("cookiefile") == str(cookies_file)
    # EJS solver must be wired for the JS-challenge path
    ejs = captured_opts.get("extractor_args", {}).get("youtubepot-jsruntime", {})
    assert ejs.get("remote_components") == ["ejs:github"]


def test_youtube_resolve_omits_cookiefile_when_absent(tmp_path, monkeypatch, qtbot):
    """_youtube_resolve_worker omits cookiefile when cookies.txt is absent but
    still includes the EJS extractor_args."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    # Do NOT create the file.

    captured_opts = {}

    class FakeYDL:
        def __init__(self, opts):
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"url": "http://resolved.example/stream.m3u8"}

    import yt_dlp
    player = make_player(qtbot)
    with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")

    assert "cookiefile" not in captured_opts
    ejs = captured_opts.get("extractor_args", {}).get("youtubepot-jsruntime", {})
    assert ejs.get("remote_components") == ["ejs:github"]


# ---------------------------------------------------------------------------
# clear_cookies() utility
# ---------------------------------------------------------------------------

def test_clear_removes_cookies_file(tmp_path, monkeypatch):
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("some cookies")
    from musicstreamer.constants import clear_cookies
    assert clear_cookies() is True
    assert not cookies_file.exists()


def test_clear_returns_false_when_absent(tmp_path, monkeypatch):
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.constants import clear_cookies
    assert clear_cookies() is False
