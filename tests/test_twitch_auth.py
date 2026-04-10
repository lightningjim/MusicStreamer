"""Tests for TWITCH_TOKEN_PATH constant, clear_twitch_token() utility,
and --twitch-api-header injection in _play_twitch()."""
import os
from unittest.mock import MagicMock, patch
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

def test_twitch_token_path_constant():
    """TWITCH_TOKEN_PATH resolves to DATA_DIR/twitch-token.txt."""
    from musicstreamer.constants import TWITCH_TOKEN_PATH, DATA_DIR
    assert TWITCH_TOKEN_PATH == os.path.join(DATA_DIR, "twitch-token.txt")
    assert TWITCH_TOKEN_PATH.endswith("/musicstreamer/twitch-token.txt")


# ---------------------------------------------------------------------------
# 2. clear_twitch_token() utility tests
# ---------------------------------------------------------------------------

def test_clear_twitch_token_removes_file(tmp_path, monkeypatch):
    """clear_twitch_token() deletes TWITCH_TOKEN_PATH if it exists and returns True."""
    token_file = tmp_path / "twitch-token.txt"
    token_file.write_text("abc123")
    monkeypatch.setattr("musicstreamer.constants.TWITCH_TOKEN_PATH", str(token_file))

    from musicstreamer.constants import clear_twitch_token
    result = clear_twitch_token()
    assert result is True
    assert not token_file.exists()


def test_clear_twitch_token_returns_false_when_absent(tmp_path, monkeypatch):
    """clear_twitch_token() returns False when twitch-token.txt does not exist."""
    token_file = tmp_path / "twitch-token.txt"
    # Do NOT create the file
    monkeypatch.setattr("musicstreamer.constants.TWITCH_TOKEN_PATH", str(token_file))

    from musicstreamer.constants import clear_twitch_token
    result = clear_twitch_token()
    assert result is False


# ---------------------------------------------------------------------------
# 3. _play_twitch() auth header injection tests
# ---------------------------------------------------------------------------

def test_play_twitch_includes_auth_header(tmp_path, monkeypatch):
    """When TWITCH_TOKEN_PATH exists with content 'abc123', subprocess.run is called
    with cmd containing '--twitch-api-header' and 'Authorization=OAuth abc123'."""
    token_file = tmp_path / "twitch-token.txt"
    token_file.write_text("abc123")
    monkeypatch.setattr("musicstreamer.player.TWITCH_TOKEN_PATH", str(token_file))

    player = make_player()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "https://example.m3u8\n"
    mock_result.stderr = ""

    captured_cmd = []

    def fake_thread(target, daemon):
        class T:
            def start(self):
                target()
        return T()

    monkeypatch.setattr("musicstreamer.player.threading.Thread",
                        lambda target, daemon: type('T', (), {'start': lambda self: target()})())

    with patch("musicstreamer.player.subprocess.run", return_value=mock_result) as mock_run, \
         patch("musicstreamer.player.GLib"):
        player._play_twitch("https://www.twitch.tv/testchannel")

    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert "--twitch-api-header" in cmd
    assert "Authorization=OAuth abc123" in cmd


def test_play_twitch_no_header_when_absent(tmp_path, monkeypatch):
    """When TWITCH_TOKEN_PATH does not exist, subprocess.run cmd does NOT contain
    '--twitch-api-header'."""
    token_file = tmp_path / "twitch-token.txt"
    # Do NOT create the file
    monkeypatch.setattr("musicstreamer.player.TWITCH_TOKEN_PATH", str(token_file))

    player = make_player()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "https://example.m3u8\n"
    mock_result.stderr = ""

    monkeypatch.setattr("musicstreamer.player.threading.Thread",
                        lambda target, daemon: type('T', (), {'start': lambda self: target()})())

    with patch("musicstreamer.player.subprocess.run", return_value=mock_result) as mock_run, \
         patch("musicstreamer.player.GLib"):
        player._play_twitch("https://www.twitch.tv/testchannel")

    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert "--twitch-api-header" not in cmd


def test_play_twitch_no_header_when_empty(tmp_path, monkeypatch):
    """When TWITCH_TOKEN_PATH exists but is empty/whitespace, subprocess.run cmd does NOT
    contain '--twitch-api-header'."""
    token_file = tmp_path / "twitch-token.txt"
    token_file.write_text("   \n")  # whitespace only
    monkeypatch.setattr("musicstreamer.player.TWITCH_TOKEN_PATH", str(token_file))

    player = make_player()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "https://example.m3u8\n"
    mock_result.stderr = ""

    monkeypatch.setattr("musicstreamer.player.threading.Thread",
                        lambda target, daemon: type('T', (), {'start': lambda self: target()})())

    with patch("musicstreamer.player.subprocess.run", return_value=mock_result) as mock_run, \
         patch("musicstreamer.player.GLib"):
        player._play_twitch("https://www.twitch.tv/testchannel")

    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert "--twitch-api-header" not in cmd
