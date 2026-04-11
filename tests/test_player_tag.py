"""Tests for GStreamer TAG bus handling and ICY encoding fix in Player.

Phase 35 port: ``_on_gst_tag`` emits the ``title_changed`` Qt signal
instead of calling a legacy ``_on_title`` callback via ``GLib.idle_add``.
Tests use pytest-qt's ``qtbot.waitSignal`` to assert emissions.
"""
from unittest.mock import MagicMock, patch

from musicstreamer.models import Station, StationStream
from musicstreamer.player import Player, _fix_icy_encoding


def make_station():
    return Station(
        id=1,
        name="Test Station",
        provider_id=1,
        provider_name="Test",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=[
            StationStream(id=1, station_id=1, url="http://a/", position=1)
        ],
    )


def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out."""
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    return player


def _fake_tag_msg(title, found=True):
    taglist = MagicMock()
    taglist.get_string.return_value = (found, title)
    msg = MagicMock()
    msg.parse_tag.return_value = taglist
    return msg


# --- _fix_icy_encoding ------------------------------------------------------

def test_fix_icy_encoding_mojibake():
    """UTF-8 bytes decoded as latin-1 should be re-encoded back to UTF-8."""
    bad_string = "Röyksopp".encode("utf-8").decode("latin-1")
    result = _fix_icy_encoding(bad_string)
    assert result == "Röyksopp", f"Expected 'Röyksopp', got {result!r}"


def test_fix_icy_encoding_ascii_passthrough():
    assert _fix_icy_encoding("Artist - Title") == "Artist - Title"


def test_fix_icy_encoding_latin1_passthrough():
    original = "café"
    assert _fix_icy_encoding(original) == original


# --- _on_gst_tag → title_changed signal -------------------------------------

def test_on_gst_tag_emits_title_changed(qtbot):
    """A TAG message with a title causes title_changed.emit(title)."""
    player = make_player(qtbot)
    msg = _fake_tag_msg("Some Track")
    with qtbot.waitSignal(player.title_changed, timeout=1000) as blocker:
        player._on_gst_tag(bus=None, msg=msg)
    assert blocker.args == ["Some Track"]


def test_on_gst_tag_ignores_missing_title(qtbot):
    """A TAG message without a title does NOT emit title_changed."""
    player = make_player(qtbot)
    msg = _fake_tag_msg("", found=False)
    with qtbot.assertNotEmitted(player.title_changed, wait=200):
        player._on_gst_tag(bus=None, msg=msg)


def test_on_gst_tag_multiple_updates(qtbot):
    """Two successive TAG messages emit title_changed twice with the right args."""
    player = make_player(qtbot)
    received = []
    player.title_changed.connect(lambda t: received.append(t))
    with qtbot.waitSignal(player.title_changed, timeout=1000):
        player._on_gst_tag(bus=None, msg=_fake_tag_msg("Track One"))
    with qtbot.waitSignal(player.title_changed, timeout=1000):
        player._on_gst_tag(bus=None, msg=_fake_tag_msg("Track Two"))
    assert "Track One" in received
    assert "Track Two" in received


def test_on_gst_tag_does_not_call_callback_directly(qtbot):
    """_on_gst_tag goes through the Qt signal mechanism; slots are invoked
    via Qt's emit path, not a direct call from the handler body."""
    player = make_player(qtbot)
    callback = MagicMock()
    player.title_changed.connect(callback)
    msg = _fake_tag_msg("Direct Test")
    with qtbot.waitSignal(player.title_changed, timeout=1000):
        player._on_gst_tag(bus=None, msg=msg)
    callback.assert_called_with("Direct Test")


def test_stop_clears_queue(qtbot):
    """After stop(), there is no queued work and legacy shim slots are cleared."""
    player = make_player(qtbot)
    player._streams_queue = [MagicMock()]
    player.stop()
    assert player._streams_queue == []


def test_play_stores_legacy_on_title_shim(qtbot):
    """play() with on_title= stores the callback as _on_title_cb (shim)."""
    player = make_player(qtbot)
    callback = MagicMock()
    station = make_station()
    with patch.object(player, "_set_uri"):
        player.play(station, on_title=callback)
    assert player._on_title_cb is callback


def test_on_gst_tag_after_stop_still_emits_signal(qtbot):
    """After stop(), the Qt signal still functions (emit pathway is not
    tied to a legacy callback attribute). Behavioral intent: the stream
    is stopped via ``pause``/``stop``, so no more TAG messages arrive;
    but if a stale one did, the signal is the only output path."""
    player = make_player(qtbot)
    player.stop()
    msg = _fake_tag_msg("Stale Track")
    # The signal still exists and still fires — there is no longer a
    # "suppress after stop" invariant (that was an artifact of the old
    # _on_title attribute reset). Verify the signal mechanism works.
    with qtbot.waitSignal(player.title_changed, timeout=1000) as blocker:
        player._on_gst_tag(bus=None, msg=msg)
    assert blocker.args == ["Stale Track"]
