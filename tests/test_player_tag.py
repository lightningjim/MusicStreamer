"""Tests for GStreamer TAG bus handling and ICY encoding fix in Player."""
import unittest
from unittest.mock import MagicMock, patch, call

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst

from musicstreamer.player import Player, _fix_icy_encoding
from musicstreamer.models import Station


def make_station():
    return Station(
        id=1,
        name="Test Station",
        provider_id=1,
        provider_name="Test",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
    )


def make_player():
    """Create a Player with GStreamer pipeline mocked out."""
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch("musicstreamer.player.Gst.ElementFactory.make", return_value=mock_pipeline):
        player = Player()
    return player


# --- _fix_icy_encoding ---

def test_fix_icy_encoding_mojibake():
    """UTF-8 bytes decoded as latin-1 should be re-encoded back to UTF-8."""
    # "Röyksopp" in UTF-8 is bytes b'R\xc3\xb6yksopp'
    # If those bytes are decoded as latin-1 you get "RÃ¶yksopp"
    bad_string = "Röyksopp".encode("utf-8").decode("latin-1")
    result = _fix_icy_encoding(bad_string)
    assert result == "Röyksopp", f"Expected 'Röyksopp', got {result!r}"


def test_fix_icy_encoding_ascii_passthrough():
    """Clean ASCII strings should pass through unchanged."""
    result = _fix_icy_encoding("Artist - Title")
    assert result == "Artist - Title"


def test_fix_icy_encoding_latin1_passthrough():
    """Genuine latin-1 strings that cannot re-encode to UTF-8 pass through unchanged."""
    # "café" — the é is U+00E9 which as latin-1 bytes is 0xE9, but 0xE9 alone is
    # not a valid UTF-8 sequence, so the round-trip will fail and the original is returned.
    original = "café"
    result = _fix_icy_encoding(original)
    assert result == original


# --- _on_gst_tag ---

def test_on_gst_tag_calls_on_title():
    """_on_gst_tag with TAG_TITLE present calls GLib.idle_add with on_title and title."""
    player = make_player()
    callback = MagicMock()
    player._on_title = callback

    taglist = MagicMock()
    taglist.get_string.return_value = (True, "Some Track")
    msg = MagicMock()
    msg.parse_tag.return_value = taglist

    with patch("musicstreamer.player.GLib.idle_add") as mock_idle:
        player._on_gst_tag(MagicMock(), msg)
        mock_idle.assert_called_once_with(callback, "Some Track")


def test_on_gst_tag_ignores_missing_title():
    """_on_gst_tag with no TAG_TITLE does NOT call GLib.idle_add."""
    player = make_player()
    player._on_title = MagicMock()

    taglist = MagicMock()
    taglist.get_string.return_value = (False, "")
    msg = MagicMock()
    msg.parse_tag.return_value = taglist

    with patch("musicstreamer.player.GLib.idle_add") as mock_idle:
        player._on_gst_tag(MagicMock(), msg)
        mock_idle.assert_not_called()


def test_on_gst_tag_multiple_updates():
    """Multiple _on_gst_tag calls each invoke idle_add with respective titles."""
    player = make_player()
    callback = MagicMock()
    player._on_title = callback

    def make_msg(title):
        taglist = MagicMock()
        taglist.get_string.return_value = (True, title)
        msg = MagicMock()
        msg.parse_tag.return_value = taglist
        return msg

    with patch("musicstreamer.player.GLib.idle_add") as mock_idle:
        player._on_gst_tag(MagicMock(), make_msg("Track One"))
        player._on_gst_tag(MagicMock(), make_msg("Track Two"))
        assert mock_idle.call_count == 2
        mock_idle.assert_any_call(callback, "Track One")
        mock_idle.assert_any_call(callback, "Track Two")


def test_stop_clears_on_title():
    """After stop(), _on_title is None."""
    player = make_player()
    player._on_title = MagicMock()
    player.stop()
    assert player._on_title is None


def test_play_stores_on_title():
    """play() stores the on_title callback as self._on_title."""
    player = make_player()
    callback = MagicMock()
    station = make_station()

    with patch.object(player, "_set_uri") as mock_set_uri, \
         patch.object(player, "_stop_yt_proc"):
        player.play(station, callback)

    assert player._on_title is callback


def test_on_gst_tag_uses_idle_add():
    """_on_gst_tag dispatches via GLib.idle_add, not by calling on_title directly."""
    player = make_player()
    callback = MagicMock()
    player._on_title = callback

    taglist = MagicMock()
    taglist.get_string.return_value = (True, "Direct Test")
    msg = MagicMock()
    msg.parse_tag.return_value = taglist

    with patch("musicstreamer.player.GLib.idle_add") as mock_idle:
        player._on_gst_tag(MagicMock(), msg)
        # idle_add must have been called
        mock_idle.assert_called_once()
        # callback itself must NOT have been called directly
        callback.assert_not_called()


def test_on_gst_tag_no_call_after_stop():
    """After stop(), a stale TAG message does not invoke the cleared callback."""
    player = make_player()
    callback = MagicMock()
    player._on_title = callback
    player.stop()  # clears _on_title

    taglist = MagicMock()
    taglist.get_string.return_value = (True, "Stale Track")
    msg = MagicMock()
    msg.parse_tag.return_value = taglist

    with patch("musicstreamer.player.GLib.idle_add") as mock_idle:
        player._on_gst_tag(MagicMock(), msg)
        mock_idle.assert_not_called()
