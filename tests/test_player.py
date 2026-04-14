"""Tests for Player elapsed-time QTimer (Plan 40.1-06).

Regression tests locking in v1.5 elapsed-time parity: the Player emits
elapsed_updated(int) once per second while playing, halts on stop()/pause(),
and resets the counter on a new play() (but NOT on failover).
"""
from unittest.mock import MagicMock, patch


def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out.

    Mirrors the harness pattern in tests/test_player_pause.py.
    """
    from musicstreamer.player import Player
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    # Swap in a clean pipeline mock so assertions on set_state don't see
    # setup-time calls from __init__.
    player._pipeline = MagicMock()
    return player


def _seed_playback(player):
    """Put the player into the same state as a fresh play()/play_stream()
    without invoking the real GStreamer / network paths.

    The elapsed timer is seeded by _try_next_stream when _is_first_attempt
    is True. We call _try_next_stream directly with a single fake non-YT,
    non-Twitch stream so it takes the _set_uri branch (which is also mocked).
    """
    from musicstreamer.models import StationStream
    stream = StationStream(
        id=1, station_id=1, url="http://example.com/stream",
        quality="hi", position=1, stream_type="shoutcast", codec="MP3",
    )
    player._streams_queue = [stream]
    player._is_first_attempt = True
    player._try_next_stream()


def test_elapsed_timer_emits_seconds_while_playing(qtbot):
    """Timer ticks emit elapsed_updated(1), (2), (3); stop() halts the timer."""
    p = make_player(qtbot)
    emissions = []
    p.elapsed_updated.connect(emissions.append)

    _seed_playback(p)

    # Manually drive the timer three times (bypass real wall clock).
    p._elapsed_timer.timeout.emit()
    p._elapsed_timer.timeout.emit()
    p._elapsed_timer.timeout.emit()

    assert emissions == [1, 2, 3]

    p.stop()
    # After stop(), the timer must be inactive; no further emissions on its
    # own. (Manually firing the signal would still call the slot, so the
    # contract-level assertion is isActive() == False.)
    assert p._elapsed_timer.isActive() is False


def test_elapsed_timer_resets_on_new_play(qtbot):
    """stop() resets counter to 0; next play() starts fresh at 1."""
    p = make_player(qtbot)
    emissions = []
    p.elapsed_updated.connect(emissions.append)

    _seed_playback(p)
    p._elapsed_timer.timeout.emit()
    p._elapsed_timer.timeout.emit()
    assert emissions[-1] == 2

    p.stop()
    assert p._elapsed_seconds == 0

    # Start a new playback; first-attempt branch in _try_next_stream must
    # re-seed the counter to 0 before the first tick fires.
    _seed_playback(p)
    p._elapsed_timer.timeout.emit()

    assert emissions[-1] == 1, (
        f"expected fresh play to emit 1, got {emissions[-1]} "
        f"(full emissions: {emissions})"
    )


def test_elapsed_timer_halts_on_pause(qtbot):
    """pause() stops the elapsed timer."""
    p = make_player(qtbot)
    emissions = []
    p.elapsed_updated.connect(emissions.append)

    _seed_playback(p)
    p._elapsed_timer.timeout.emit()
    assert emissions == [1]

    p.pause()
    assert p._elapsed_timer.isActive() is False


def test_elapsed_timer_does_not_reset_on_failover(qtbot):
    """Failover (non-first-attempt _try_next_stream) must NOT reset the counter.

    Locks in the 'failover is transparent to user' contract from the plan.
    """
    from musicstreamer.models import StationStream
    p = make_player(qtbot)
    emissions = []
    p.elapsed_updated.connect(emissions.append)

    _seed_playback(p)
    p._elapsed_timer.timeout.emit()
    p._elapsed_timer.timeout.emit()
    p._elapsed_timer.timeout.emit()
    assert emissions == [1, 2, 3]

    # Simulate failover: another stream in queue, _is_first_attempt is now False
    # (set by the prior _try_next_stream call).
    assert p._is_first_attempt is False
    p._streams_queue = [
        StationStream(id=2, station_id=1, url="http://example.com/fallback",
                      quality="med", position=2, stream_type="shoutcast",
                      codec="MP3"),
    ]
    p._try_next_stream()

    # Counter must NOT have been reset by the failover.
    p._elapsed_timer.timeout.emit()
    assert emissions[-1] == 4, (
        f"failover must not reset counter; expected 4, got {emissions[-1]}"
    )
