"""Tests for Twitch OAuth token handling via the streamlink library API.

Phase 35 port: the pre-rewrite code injected ``--twitch-api-header`` on
the streamlink CLI. The new code calls
``session.set_plugin_option("twitch", "api-header", ...)`` — scoped to
the twitch plugin only (Pitfall 6), not a global http-header. Tests
read/write the token under a monkeypatched ``paths.twitch_token_path``
so they never touch the dev user's real token file.
"""
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


def test_play_twitch_sets_plugin_option_when_token_present(qtbot, tmp_path, monkeypatch):
    """When the token file exists and has content, the worker calls
    session.set_plugin_option('twitch', 'api-header', [...])."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    token_file = tmp_path / "twitch-token.txt"
    token_file.write_text("abc123")

    session = MagicMock()
    session.streams.return_value = {"best": _FakeStream("https://ok.m3u8")}

    p = make_player(qtbot)
    with patch("streamlink.session.Streamlink", return_value=session):
        with qtbot.waitSignal(p.twitch_resolved, timeout=2000):
            p._twitch_resolve_worker("https://www.twitch.tv/testchannel")

    session.set_plugin_option.assert_called_once_with(
        "twitch", "api-header", [("Authorization", "OAuth abc123")]
    )


def test_play_twitch_no_header_when_token_absent(qtbot, tmp_path, monkeypatch):
    """No token file → no set_plugin_option call."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    # Do NOT create the token file.

    session = MagicMock()
    session.streams.return_value = {"best": _FakeStream("https://ok.m3u8")}

    p = make_player(qtbot)
    with patch("streamlink.session.Streamlink", return_value=session):
        with qtbot.waitSignal(p.twitch_resolved, timeout=2000):
            p._twitch_resolve_worker("https://www.twitch.tv/testchannel")

    session.set_plugin_option.assert_not_called()


def test_play_twitch_no_header_when_token_empty(qtbot, tmp_path, monkeypatch):
    """Whitespace-only token is treated as absent."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    token_file = tmp_path / "twitch-token.txt"
    token_file.write_text("   \n")

    session = MagicMock()
    session.streams.return_value = {"best": _FakeStream("https://ok.m3u8")}

    p = make_player(qtbot)
    with patch("streamlink.session.Streamlink", return_value=session):
        with qtbot.waitSignal(p.twitch_resolved, timeout=2000):
            p._twitch_resolve_worker("https://www.twitch.tv/testchannel")

    session.set_plugin_option.assert_not_called()
