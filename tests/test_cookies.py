"""Tests for COOKIES_PATH constant and cookie flag injection into yt-dlp and mpv calls."""
import os
import shutil
import time
from unittest.mock import MagicMock, patch, call
import subprocess

import gi
gi.require_version("Gst", "1.0")

import pytest


def make_player():
    """Create a Player with GStreamer pipeline mocked out."""
    from musicstreamer.player import Player
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch("musicstreamer.player.Gst.ElementFactory.make", return_value=mock_pipeline):
        player = Player()
    return player


# ---------------------------------------------------------------------------
# 1. Constant test
# ---------------------------------------------------------------------------

def test_cookie_path_constant():
    """COOKIES_PATH resolves to DATA_DIR/cookies.txt."""
    from musicstreamer.constants import COOKIES_PATH, DATA_DIR
    assert COOKIES_PATH == os.path.join(DATA_DIR, "cookies.txt")
    assert COOKIES_PATH.endswith("/musicstreamer/cookies.txt")


# ---------------------------------------------------------------------------
# 2. yt-dlp tests
# ---------------------------------------------------------------------------

def test_ytdlp_no_cookies_from_browser_always_when_file_exists(tmp_path, monkeypatch):
    """scan_playlist() always passes --no-cookies-from-browser when cookies.txt exists."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("netscape-format cookies")
    monkeypatch.setattr("musicstreamer.yt_import.COOKIES_PATH", str(cookies_file))

    mock_result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout='', stderr=''
    )
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")
        cmd = mock_run.call_args[0][0]
        assert "--no-cookies-from-browser" in cmd


def test_ytdlp_no_cookies_from_browser_always_when_file_absent(tmp_path, monkeypatch):
    """scan_playlist() always passes --no-cookies-from-browser even when cookies.txt absent."""
    cookies_file = tmp_path / "cookies.txt"
    # Do NOT create the file
    monkeypatch.setattr("musicstreamer.yt_import.COOKIES_PATH", str(cookies_file))

    mock_result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout='', stderr=''
    )
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")
        cmd = mock_run.call_args[0][0]
        assert "--no-cookies-from-browser" in cmd


def test_ytdlp_uses_cookies_when_file_exists(tmp_path, monkeypatch):
    """scan_playlist() includes --cookies <some-path> when cookies.txt exists."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("netscape-format cookies")
    monkeypatch.setattr("musicstreamer.yt_import.COOKIES_PATH", str(cookies_file))

    mock_result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout='', stderr=''
    )
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")
        cmd = mock_run.call_args[0][0]
        assert "--cookies" in cmd


def test_ytdlp_no_cookies_flag_when_absent(tmp_path, monkeypatch):
    """scan_playlist() does NOT include --cookies when cookies.txt does not exist."""
    cookies_file = tmp_path / "cookies.txt"
    # Do NOT create the file
    monkeypatch.setattr("musicstreamer.yt_import.COOKIES_PATH", str(cookies_file))

    mock_result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout='', stderr=''
    )
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")
        cmd = mock_run.call_args[0][0]
        assert "--cookies" not in cmd


# ---------------------------------------------------------------------------
# 3. mpv tests
# ---------------------------------------------------------------------------

def test_mpv_uses_cookies_when_file_exists(tmp_path, monkeypatch):
    """_play_youtube() includes --ytdl-raw-options=cookies=<some-path> when cookies.txt exists."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("netscape-format cookies")
    monkeypatch.setattr("musicstreamer.player.COOKIES_PATH", str(cookies_file))

    player = make_player()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # still running — no retry
    with patch("subprocess.Popen", return_value=mock_proc):
        with patch("time.sleep"):
            player._play_youtube(
                "https://youtube.com/watch?v=test", "Test", lambda t: None
            )
        cmd = mock_proc.call_args[0][0] if mock_proc.call_args else None
        # Check via the Popen mock's call args
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        with patch("time.sleep"):
            player._play_youtube(
                "https://youtube.com/watch?v=test", "Test", lambda t: None
            )
        cmd = mock_popen.call_args[0][0]
        assert any("ytdl-raw-options=cookies=" in arg for arg in cmd)


def test_mpv_no_cookies_when_absent(tmp_path, monkeypatch):
    """_play_youtube() does NOT include cookie flags when cookies.txt does not exist."""
    cookies_file = tmp_path / "cookies.txt"
    # Do NOT create the file
    monkeypatch.setattr("musicstreamer.player.COOKIES_PATH", str(cookies_file))

    player = make_player()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        with patch("time.sleep"):
            player._play_youtube(
                "https://youtube.com/watch?v=test", "Test", lambda t: None
            )
        cmd = mock_popen.call_args[0][0]
        assert not any("ytdl-raw-options" in arg for arg in cmd)
        assert not any("cookies-file" in arg for arg in cmd)


# ---------------------------------------------------------------------------
# 4. clear_cookies() utility
# ---------------------------------------------------------------------------

def test_clear_removes_cookies_file(tmp_path, monkeypatch):
    """clear_cookies() deletes COOKIES_PATH if it exists and returns True."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("some cookies")
    monkeypatch.setattr("musicstreamer.constants.COOKIES_PATH", str(cookies_file))

    from musicstreamer.constants import clear_cookies
    result = clear_cookies()
    assert result is True
    assert not cookies_file.exists()


def test_clear_returns_false_when_absent(tmp_path, monkeypatch):
    """clear_cookies() returns False when cookies.txt does not exist."""
    cookies_file = tmp_path / "cookies.txt"
    # Do NOT create the file
    monkeypatch.setattr("musicstreamer.constants.COOKIES_PATH", str(cookies_file))

    from musicstreamer.constants import clear_cookies
    result = clear_cookies()
    assert result is False


# ---------------------------------------------------------------------------
# 5. Temp cookie copy tests (Phase 23)
# ---------------------------------------------------------------------------

COOKIE_CONTENT = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\ttest123"


def test_ytdlp_uses_temp_cookie_copy(tmp_path, monkeypatch):
    """scan_playlist passes a DIFFERENT path (not COOKIES_PATH) to --cookies."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(COOKIE_CONTENT)
    monkeypatch.setattr("musicstreamer.yt_import.COOKIES_PATH", str(cookies_file))

    mock_result = subprocess.CompletedProcess(args=[], returncode=0, stdout='', stderr='')
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")
        cmd = mock_run.call_args[0][0]
        assert "--cookies" in cmd
        idx = cmd.index("--cookies")
        passed_path = cmd[idx + 1]
        assert passed_path != str(cookies_file), "Must use temp copy, not original"
        assert cookies_file.read_text() == COOKIE_CONTENT, "Original file must be unchanged"


def test_ytdlp_cleans_up_temp_cookie(tmp_path, monkeypatch):
    """After scan_playlist returns, the temp cookie file no longer exists on disk."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(COOKIE_CONTENT)
    monkeypatch.setattr("musicstreamer.yt_import.COOKIES_PATH", str(cookies_file))

    captured_temp_path = []

    def capture_run(cmd, **kwargs):
        if "--cookies" in cmd:
            idx = cmd.index("--cookies")
            captured_temp_path.append(cmd[idx + 1])
        return subprocess.CompletedProcess(args=[], returncode=0, stdout='', stderr='')

    with patch("subprocess.run", side_effect=capture_run):
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")

    assert captured_temp_path, "Expected temp path to be captured"
    assert not os.path.exists(captured_temp_path[0]), "Temp cookie file must be cleaned up"


def test_ytdlp_fallback_no_cookies_on_copy_failure(tmp_path, monkeypatch):
    """If shutil.copy2 raises OSError, scan_playlist runs yt-dlp without --cookies."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(COOKIE_CONTENT)
    monkeypatch.setattr("musicstreamer.yt_import.COOKIES_PATH", str(cookies_file))
    monkeypatch.setattr("shutil.copy2", MagicMock(side_effect=OSError("disk full")))

    mock_result = subprocess.CompletedProcess(args=[], returncode=0, stdout='', stderr='')
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")
        cmd = mock_run.call_args[0][0]
        assert "--cookies" not in cmd, "Must not pass --cookies when copy fails"


def test_mpv_uses_temp_cookie_copy(tmp_path, monkeypatch):
    """_play_youtube passes a temp file path (not COOKIES_PATH) to --ytdl-raw-options=cookies=."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(COOKIE_CONTENT)
    monkeypatch.setattr("musicstreamer.player.COOKIES_PATH", str(cookies_file))

    player = make_player()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # still running — no retry
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        with patch("time.sleep"):  # skip sleep
            player._play_youtube("https://youtube.com/watch?v=test", "Test", lambda t: None)
        cmd = mock_popen.call_args[0][0]
        cookie_args = [a for a in cmd if "ytdl-raw-options=cookies=" in a]
        assert cookie_args, "Expected --ytdl-raw-options=cookies= in cmd"
        passed_path = cookie_args[0].split("=", 2)[2]
        assert passed_path != str(cookies_file), "Must use temp copy, not original"
        assert cookies_file.read_text() == COOKIE_CONTENT, "Original file must be unchanged"


def test_mpv_cleans_up_temp_cookie_on_stop(tmp_path, monkeypatch):
    """After _stop_yt_proc is called, the temp cookie file no longer exists on disk."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(COOKIE_CONTENT)
    monkeypatch.setattr("musicstreamer.player.COOKIES_PATH", str(cookies_file))

    player = make_player()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # still running — no retry

    captured_temp_path = []

    def capture_popen(cmd, **kwargs):
        cookie_args = [a for a in cmd if "ytdl-raw-options=cookies=" in a]
        if cookie_args:
            captured_temp_path.append(cookie_args[0].split("=", 2)[2])
        return mock_proc

    with patch("subprocess.Popen", side_effect=capture_popen):
        with patch("time.sleep"):
            player._play_youtube("https://youtube.com/watch?v=test", "Test", lambda t: None)

    assert captured_temp_path, "Expected temp path to be captured"
    player._stop_yt_proc()
    assert not os.path.exists(captured_temp_path[0]), "Temp cookie file must be cleaned up on stop"


def test_mpv_retry_without_cookies_on_fast_exit(tmp_path, monkeypatch):
    """If mpv exits within 2s, _play_youtube retries without --ytdl-raw-options=cookies=."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(COOKIE_CONTENT)
    monkeypatch.setattr("musicstreamer.player.COOKIES_PATH", str(cookies_file))

    player = make_player()

    first_proc = MagicMock()
    first_proc.poll.return_value = 1  # exited immediately

    second_proc = MagicMock()
    second_proc.poll.return_value = None  # still running

    popen_calls = []

    def fake_popen(cmd, **kwargs):
        popen_calls.append(cmd[:])
        if len(popen_calls) == 1:
            return first_proc
        return second_proc

    import itertools
    monotonic_values = itertools.count(start=0.0, step=1.0)
    monkeypatch.setattr("time.monotonic", lambda: next(monotonic_values))

    timeout_callbacks = []

    with patch("musicstreamer.player.subprocess.Popen", side_effect=fake_popen), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.timeout_add.side_effect = lambda ms, cb: timeout_callbacks.append(cb) or 99
        player._play_youtube("https://youtube.com/watch?v=test", "Test", lambda t: None)
        # Simulate the GLib timer firing the cookie retry callback
        assert timeout_callbacks, "Expected GLib.timeout_add callback for cookie retry"
        for cb in timeout_callbacks:
            cb()

    assert len(popen_calls) == 2, f"Expected 2 Popen calls, got {len(popen_calls)}"
    second_cmd = popen_calls[1]
    assert not any("ytdl-raw-options=cookies=" in a for a in second_cmd), \
        "Second (retry) call must not include cookies flag"


def test_mpv_no_retry_on_slow_exit(tmp_path, monkeypatch):
    """If mpv runs longer than 2s before exiting, no retry occurs."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(COOKIE_CONTENT)
    monkeypatch.setattr("musicstreamer.player.COOKIES_PATH", str(cookies_file))

    player = make_player()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # still running after sleep

    monotonic_values = iter([0.0, 5.0])
    monkeypatch.setattr("time.monotonic", lambda: next(monotonic_values))

    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        with patch("time.sleep"):
            player._play_youtube("https://youtube.com/watch?v=test", "Test", lambda t: None)

    assert mock_popen.call_count == 1, "No retry expected when mpv runs longer than 2s"


def test_mpv_fallback_no_cookies_on_copy_failure(tmp_path, monkeypatch):
    """If shutil.copy2 raises OSError, _play_youtube launches mpv without cookies flag."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(COOKIE_CONTENT)
    monkeypatch.setattr("musicstreamer.player.COOKIES_PATH", str(cookies_file))
    monkeypatch.setattr("shutil.copy2", MagicMock(side_effect=OSError("disk full")))

    player = make_player()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        with patch("time.sleep"):
            player._play_youtube("https://youtube.com/watch?v=test", "Test", lambda t: None)

    cmd = mock_popen.call_args[0][0]
    assert not any("ytdl-raw-options=cookies=" in a for a in cmd), \
        "Must not pass cookies flag when copy fails"
