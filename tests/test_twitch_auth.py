"""Tests for Twitch OAuth token handling via the streamlink library API.

Production at ``musicstreamer/player.py:1156`` calls
``session.set_option("twitch-api-header", [("Authorization", "OAuth <token>")])``
on the streamlink session when a non-empty ``twitch-token.txt`` exists in
paths.twitch_token_path().

Phase 77 D-05 (REVISED) note: the old per-plugin scoped API was removed from
streamlink in version 6.0.0 (PR #5033, 2023-07-20). Project pins
``streamlink>=8.3``. These tests use ``MagicMock(spec=Streamlink)`` so any
future regression that reintroduces the removed API raises AttributeError at
test time — drift-guard via spec.
"""
from unittest.mock import MagicMock, patch

from streamlink.session import Streamlink

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
# paths.twitch_token_path accessor test
# ---------------------------------------------------------------------------

def test_twitch_token_path_constant(tmp_path, monkeypatch):
    """paths.twitch_token_path() honors _root_override."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    assert paths.twitch_token_path() == str(tmp_path / "twitch-token.txt")


# ---------------------------------------------------------------------------
# clear_twitch_token() utility tests (backed by paths)
# ---------------------------------------------------------------------------

def test_clear_twitch_token_removes_file(tmp_path, monkeypatch):
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    token_file = tmp_path / "twitch-token.txt"
    token_file.write_text("abc123")
    from musicstreamer.constants import clear_twitch_token
    assert clear_twitch_token() is True
    assert not token_file.exists()


def test_clear_twitch_token_returns_false_when_absent(tmp_path, monkeypatch):
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.constants import clear_twitch_token
    assert clear_twitch_token() is False


# ---------------------------------------------------------------------------
# _twitch_resolve_worker auth header injection tests
# ---------------------------------------------------------------------------

class _FakeStream:
    def __init__(self, url):
        self.url = url


def test_play_twitch_sets_option_when_token_present(qtbot, tmp_path, monkeypatch):
    """When the token file exists and has content, the worker calls
    session.set_option('twitch-api-header', [...])."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    token_file = tmp_path / "twitch-token.txt"
    token_file.write_text("abc123")

    session = MagicMock(spec=Streamlink)
    session.streams.return_value = {"best": _FakeStream("https://ok.m3u8")}

    p = make_player(qtbot)
    with patch("streamlink.session.Streamlink", return_value=session):
        with qtbot.waitSignal(p.twitch_resolved, timeout=2000):
            p._twitch_resolve_worker("https://www.twitch.tv/testchannel")

    session.set_option.assert_called_once_with(
        "twitch-api-header", [("Authorization", "OAuth abc123")]
    )


def test_play_twitch_no_header_when_token_absent(qtbot, tmp_path, monkeypatch):
    """No token file → no set_option call."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    # Do NOT create the token file.

    session = MagicMock(spec=Streamlink)
    session.streams.return_value = {"best": _FakeStream("https://ok.m3u8")}

    p = make_player(qtbot)
    with patch("streamlink.session.Streamlink", return_value=session):
        with qtbot.waitSignal(p.twitch_resolved, timeout=2000):
            p._twitch_resolve_worker("https://www.twitch.tv/testchannel")

    session.set_option.assert_not_called()


def test_play_twitch_no_header_when_token_empty(qtbot, tmp_path, monkeypatch):
    """Whitespace-only token is treated as absent → no set_option call."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    token_file = tmp_path / "twitch-token.txt"
    token_file.write_text("   \n")

    session = MagicMock(spec=Streamlink)
    session.streams.return_value = {"best": _FakeStream("https://ok.m3u8")}

    p = make_player(qtbot)
    with patch("streamlink.session.Streamlink", return_value=session):
        with qtbot.waitSignal(p.twitch_resolved, timeout=2000):
            p._twitch_resolve_worker("https://www.twitch.tv/testchannel")

    session.set_option.assert_not_called()
