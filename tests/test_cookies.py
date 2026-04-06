"""Tests for COOKIES_PATH constant and cookie flag injection into yt-dlp and mpv calls."""
import os
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
    """scan_playlist() includes --cookies COOKIES_PATH when cookies.txt exists."""
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
        idx = cmd.index("--cookies")
        assert cmd[idx + 1] == str(cookies_file)


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
    """_play_youtube() includes --ytdl-raw-options=cookies=<path> when cookies.txt exists."""
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("netscape-format cookies")
    monkeypatch.setattr("musicstreamer.player.COOKIES_PATH", str(cookies_file))

    player = make_player()
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        player._play_youtube(
            "https://youtube.com/watch?v=test", "Test", lambda t: None
        )
        cmd = mock_popen.call_args[0][0]
        expected_flag = f"--ytdl-raw-options=cookies={cookies_file}"
        assert expected_flag in cmd


def test_mpv_no_cookies_when_absent(tmp_path, monkeypatch):
    """_play_youtube() does NOT include cookie flags when cookies.txt does not exist."""
    cookies_file = tmp_path / "cookies.txt"
    # Do NOT create the file
    monkeypatch.setattr("musicstreamer.player.COOKIES_PATH", str(cookies_file))

    player = make_player()
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
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
