"""Tests for fetch_yt_thumbnail and _is_youtube_url in edit_dialog."""
import subprocess
import threading
from unittest.mock import patch, MagicMock

import pytest


def test_is_youtube_url():
    from musicstreamer.ui.edit_dialog import _is_youtube_url
    assert _is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert _is_youtube_url("https://youtu.be/abc")
    assert not _is_youtube_url("https://radio.example.com")


def test_fetch_yt_thumbnail_success():
    from musicstreamer.ui.edit_dialog import fetch_yt_thumbnail

    result_holder = []
    event = threading.Event()

    def callback(path):
        result_holder.append(path)
        event.set()

    fake_run_result = MagicMock()
    fake_run_result.stdout = "https://example.com/thumb.jpg\n"

    fake_resp = MagicMock()
    fake_resp.read.return_value = b"JPEG_BYTES"
    fake_resp.__enter__ = lambda s: s
    fake_resp.__exit__ = MagicMock(return_value=False)

    with patch("subprocess.run", return_value=fake_run_result), \
         patch("urllib.request.urlopen", return_value=fake_resp), \
         patch("gi.repository.GLib.idle_add", side_effect=lambda fn, arg: fn(arg)):
        fetch_yt_thumbnail("https://www.youtube.com/watch?v=abc", callback)
        event.wait(timeout=5)

    assert len(result_holder) == 1
    assert result_holder[0] is not None


def test_fetch_yt_thumbnail_no_output():
    from musicstreamer.ui.edit_dialog import fetch_yt_thumbnail

    result_holder = []
    event = threading.Event()

    def callback(path):
        result_holder.append(path)
        event.set()

    fake_run_result = MagicMock()
    fake_run_result.stdout = ""

    with patch("subprocess.run", return_value=fake_run_result), \
         patch("gi.repository.GLib.idle_add", side_effect=lambda fn, arg: fn(arg)):
        fetch_yt_thumbnail("https://www.youtube.com/watch?v=abc", callback)
        event.wait(timeout=5)

    assert result_holder == [None]


def test_fetch_yt_thumbnail_subprocess_error():
    from musicstreamer.ui.edit_dialog import fetch_yt_thumbnail

    result_holder = []
    event = threading.Event()

    def callback(path):
        result_holder.append(path)
        event.set()

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="yt-dlp", timeout=15)), \
         patch("gi.repository.GLib.idle_add", side_effect=lambda fn, arg: fn(arg)):
        fetch_yt_thumbnail("https://www.youtube.com/watch?v=abc", callback)
        event.wait(timeout=5)

    assert result_holder == [None]
