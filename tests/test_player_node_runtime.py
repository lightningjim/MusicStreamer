"""Tests for Player node_runtime kwarg + _youtube_resolve_worker opts threading (Phase 79 / BUG-11).

Three-input regression matrix locks the B-79-04..B-79-06 contract:
  B-79-04: NodeRuntime(available=True, path="/fake/node") → opts["js_runtimes"]["node"]["path"] == "/fake/node"
  B-79-05: Player() no-arg (node_runtime=None) → opts["js_runtimes"]["node"]["path"] is None (backwards-compat)
  B-79-06: NodeRuntime(available=False, path=None) → opts["js_runtimes"]["node"]["path"] is None
"""
from __future__ import annotations

import yt_dlp
from unittest.mock import MagicMock, patch

from musicstreamer import paths
from musicstreamer.player import Player
from musicstreamer.runtime_check import NodeRuntime
from tests.test_cookies import make_player


def _make_fake_ydl():
    """Return (FakeYDL_class, captured_opts_dict). Closure captures opts on __init__."""
    captured: dict = {}

    class FakeYDL:
        def __init__(self, opts):
            captured.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"url": "http://resolved.example/stream.m3u8"}

    return FakeYDL, captured


def _make_player_with_node(qtbot, node_runtime):
    """Construct Player(node_runtime=node_runtime) with a mocked GStreamer pipeline.

    Mirrors the body of make_player from test_cookies.py but accepts a node_runtime argument.
    """
    mock_pipeline = MagicMock()
    mock_pipeline.get_bus.return_value = MagicMock()
    with patch("musicstreamer.player.Gst.ElementFactory.make", return_value=mock_pipeline):
        player = Player(node_runtime=node_runtime)
    player._pipeline = MagicMock()
    return player


def test_youtube_resolve_passes_node_path_when_available(qtbot, tmp_path, monkeypatch):
    """B-79-04: Player with NodeRuntime(path='/fake/node') → opts['js_runtimes']['node']['path'] == '/fake/node'."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    nr = NodeRuntime(available=True, path="/fake/node")
    player = _make_player_with_node(qtbot, nr)
    FakeYDL, captured = _make_fake_ydl()
    with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")
    assert captured["js_runtimes"] == {"node": {"path": "/fake/node"}}


def test_youtube_resolve_passes_none_when_no_node_runtime(qtbot, tmp_path, monkeypatch):
    """B-79-05: Player() no-arg (node_runtime=None) passes opts["js_runtimes"]["node"]["path"] is None.

    Backwards-compat case: same shape tests/test_cookies.py:157,190 already assert.
    This test pins the invariant in the Phase 79 regression file too.
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    player = make_player(qtbot)
    FakeYDL, captured = _make_fake_ydl()
    with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")
    assert captured["js_runtimes"] == {"node": {"path": None}}


def test_youtube_resolve_passes_none_when_unavailable(qtbot, tmp_path, monkeypatch):
    """B-79-06: NodeRuntime(available=False, path=None) → opts["js_runtimes"]["node"]["path"] is None."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    nr = NodeRuntime(available=False, path=None)
    player = _make_player_with_node(qtbot, nr)
    FakeYDL, captured = _make_fake_ydl()
    with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")
    assert captured["js_runtimes"] == {"node": {"path": None}}
