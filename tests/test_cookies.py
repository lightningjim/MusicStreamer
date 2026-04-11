"""Tests for cookie handling in yt_import + mpv YouTube playback.

Phase 35 port:
- yt_import now uses the yt_dlp library API (not subprocess); cookie
  selection is via the ``cookiefile`` option on ``YoutubeDL``.
- mpv playback (KEEP_MPV branch) copies the cookies file into a temp
  path and passes ``--ytdl-raw-options=cookies=<temp>`` to mpv via
  ``musicstreamer._popen.popen``.
- The monkeypatch target for all cookie tests is
  ``musicstreamer.paths._root_override`` — yt_import and player both
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
# mpv YouTube playback cookie injection (KEEP_MPV branch)
# ---------------------------------------------------------------------------

def test_mpv_uses_temp_cookie_copy(tmp_path, monkeypatch, qtbot):
    """_play_youtube copies cookies.txt to a temp file and passes
    --ytdl-raw-options=cookies=<temp> to mpv via _popen."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n")

    player = make_player(qtbot)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # still running

    temp_cookie = str(tmp_path / "ms_cookies_AAAAAA.txt")

    with patch("musicstreamer.player._popen", return_value=mock_proc) as mock_popen, \
         patch("musicstreamer.player.tempfile.mkstemp",
               return_value=(0, temp_cookie)), \
         patch("musicstreamer.player.os.close"), \
         patch("musicstreamer.player.shutil.copy2"):
        player._play_youtube("https://youtube.com/watch?v=test")

    cmd = mock_popen.call_args[0][0]
    cookie_args = [a for a in cmd if "ytdl-raw-options=cookies=" in a]
    assert cookie_args, "Expected --ytdl-raw-options=cookies= in cmd"
    passed_path = cookie_args[0].split("=", 2)[2]
    assert passed_path == temp_cookie
    assert passed_path != str(cookies_file), "Must use temp copy, not original"
    # Original unchanged
    assert cookies_file.read_text() == "# Netscape HTTP Cookie File\n"


def test_mpv_no_cookies_when_absent(tmp_path, monkeypatch, qtbot):
    """_play_youtube does NOT include cookie flags when cookies.txt is absent."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    # Do NOT create the file.

    player = make_player(qtbot)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    with patch("musicstreamer.player._popen", return_value=mock_proc) as mock_popen:
        player._play_youtube("https://youtube.com/watch?v=test")

    cmd = mock_popen.call_args[0][0]
    assert not any("ytdl-raw-options=cookies=" in a for a in cmd)


def test_mpv_fallback_no_cookies_on_copy_failure(tmp_path, monkeypatch, qtbot):
    """If shutil.copy2 raises OSError, _play_youtube launches without cookies flag."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("cookies")

    player = make_player(qtbot)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    with patch("musicstreamer.player._popen", return_value=mock_proc) as mock_popen, \
         patch("musicstreamer.player.tempfile.mkstemp",
               return_value=(0, str(tmp_path / "ms_cookies_X.txt"))), \
         patch("musicstreamer.player.os.close"), \
         patch("musicstreamer.player.shutil.copy2",
               side_effect=OSError("disk full")):
        player._play_youtube("https://youtube.com/watch?v=test")

    cmd = mock_popen.call_args[0][0]
    assert not any("ytdl-raw-options=cookies=" in a for a in cmd)


def test_mpv_cleans_up_temp_cookie_on_stop(tmp_path, monkeypatch, qtbot):
    """After _stop_yt_proc is called, the temp cookie file is removed."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("cookies")
    temp_cookie = tmp_path / "ms_cookies_Y.txt"
    temp_cookie.write_text("copy")

    player = make_player(qtbot)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    with patch("musicstreamer.player._popen", return_value=mock_proc), \
         patch("musicstreamer.player.tempfile.mkstemp",
               return_value=(0, str(temp_cookie))), \
         patch("musicstreamer.player.os.close"), \
         patch("musicstreamer.player.shutil.copy2",
               side_effect=lambda s, d: temp_cookie.write_text(cookies_file.read_text())):
        player._play_youtube("https://youtube.com/watch?v=test")

    assert temp_cookie.exists()
    player._stop_yt_proc()
    assert not temp_cookie.exists()


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
