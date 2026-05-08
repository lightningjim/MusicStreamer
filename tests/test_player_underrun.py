"""Tests for Phase 62 / BUG-09 — Player buffer-underrun cycle integration.

Verifies _on_gst_buffering drives _BufferUnderrunTracker, terminator hooks
(pause / stop / _try_next_stream) force-close the cycle with correct outcomes,
the structured log line is written at INFO with all 9 fields, the 1500ms
dwell timer fires underrun_recovery_started, and sub-1500ms recoveries are
silent (Pitfalls 1, 2, 3 — qt-glib-bus-threading.md).
"""
import logging
from unittest.mock import MagicMock, patch

from musicstreamer.models import StationStream
from musicstreamer.player import Player


def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out.

    Verbatim duplicate of tests/test_player_buffering.py:8-18 (per
    PATTERNS.md §S-7 — codebase convention is per-file helper duplication,
    not shared conftest extraction).
    """
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    return player


def _fake_buffering_msg(percent, as_tuple=False):
    """Verbatim duplicate of tests/test_player_buffering.py:21-27."""
    msg = MagicMock()
    msg.parse_buffering.return_value = (percent,) if as_tuple else percent
    return msg


def _seed_url(player, url="http://example.test/stream", station_id=42, station_name="Test Station"):
    """Helper: bind tracker to a URL so observe() has station context.

    Plan 01/02 introduces _tracker.bind_url(); pre-Plan-01 this access raises
    AttributeError, which is the RED contract.
    """
    player._tracker.bind_url(station_id, station_name, url)


def test_buffering_drop_emits_cycle_opened(qtbot):
    """Pitfall 2 — bus handler must emit _underrun_cycle_opened on first <100 post-arm."""
    player = make_player(qtbot)
    _seed_url(player)
    # Arm the tracker first (bus-handler delivers percent=100 → arms)
    player._on_gst_buffering(None, _fake_buffering_msg(100))
    # Now a drop must emit _underrun_cycle_opened (queued cross-thread)
    with qtbot.waitSignal(player._underrun_cycle_opened, timeout=1000):
        player._on_gst_buffering(None, _fake_buffering_msg(70))


def test_buffering_recover_emits_cycle_closed(qtbot):
    """D-02: cycle close emits _underrun_cycle_closed with full record payload."""
    player = make_player(qtbot)
    _seed_url(player, url="http://prem2.di.fm/ambient", station_id=7, station_name="DI.fm Ambient")
    player._on_gst_buffering(None, _fake_buffering_msg(100))   # arm
    player._on_gst_buffering(None, _fake_buffering_msg(70))    # open

    closed_records = []
    player._underrun_cycle_closed.connect(closed_records.append)
    player._on_gst_buffering(None, _fake_buffering_msg(100))   # close
    qtbot.wait(100)

    assert len(closed_records) == 1
    rec = closed_records[0]
    assert rec.outcome == "recovered"
    assert rec.station_id == 7
    assert rec.station_name == "DI.fm Ambient"
    assert rec.url == "http://prem2.di.fm/ambient"
    assert rec.cause_hint == "unknown"
    assert rec.duration_ms >= 0


def test_try_next_stream_force_closes_with_failover_outcome(qtbot):
    """D-03 + T-62-02: force-close path runs BEFORE binding new URL, with outcome='failover'."""
    player = make_player(qtbot)
    _seed_url(player, url="http://old.test/", station_id=1, station_name="Old")
    player._on_gst_buffering(None, _fake_buffering_msg(100))   # arm
    player._on_gst_buffering(None, _fake_buffering_msg(60))    # open

    closed_records = []
    player._underrun_cycle_closed.connect(closed_records.append)

    # Queue a new stream and advance — _try_next_stream must force-close BEFORE binding
    new_stream = StationStream(
        id=99, station_id=1, url="http://new.test/", codec="MP3",
        quality="hi", label="test", position=0, bitrate_kbps=128,
    )
    player._streams_queue = [new_stream]
    player._is_first_attempt = False
    player._try_next_stream()
    qtbot.wait(100)

    assert len(closed_records) == 1
    assert closed_records[0].outcome == "failover"
    # T-62-02: the old URL's record was emitted, not the new URL's context
    assert closed_records[0].url == "http://old.test/"


def test_pause_force_closes_with_pause_outcome(qtbot):
    """D-03: pause() force-closes any open cycle with outcome='pause'."""
    player = make_player(qtbot)
    _seed_url(player)
    player._on_gst_buffering(None, _fake_buffering_msg(100))   # arm
    player._on_gst_buffering(None, _fake_buffering_msg(40))    # open

    closed_records = []
    player._underrun_cycle_closed.connect(closed_records.append)
    player.pause()
    qtbot.wait(100)

    assert len(closed_records) == 1
    assert closed_records[0].outcome == "pause"


def test_stop_force_closes_with_stop_outcome(qtbot):
    """D-03: stop() force-closes any open cycle with outcome='stop'."""
    player = make_player(qtbot)
    _seed_url(player)
    player._on_gst_buffering(None, _fake_buffering_msg(100))   # arm
    player._on_gst_buffering(None, _fake_buffering_msg(40))    # open

    closed_records = []
    player._underrun_cycle_closed.connect(closed_records.append)
    player.stop()
    qtbot.wait(100)

    assert len(closed_records) == 1
    assert closed_records[0].outcome == "stop"


def test_cycle_close_writes_structured_log(qtbot, caplog):
    """D-02 + T-62-01: cycle close writes one INFO log line with all 9 fields;
    station_name + url are quoted via %r so log-injection control chars are escaped."""
    caplog.set_level(logging.INFO, logger="musicstreamer.player")
    player = make_player(qtbot)
    _seed_url(player, url="http://example.test/", station_id=42, station_name="Test Station")
    player._on_gst_buffering(None, _fake_buffering_msg(100))   # arm
    player._on_gst_buffering(None, _fake_buffering_msg(60))    # open
    player._on_gst_buffering(None, _fake_buffering_msg(100))   # close
    qtbot.wait(100)

    underrun_records = [r for r in caplog.records if "buffer_underrun" in r.message]
    assert len(underrun_records) == 1, f"expected 1 buffer_underrun INFO log; got {[r.message for r in caplog.records]}"
    msg = underrun_records[0].message
    # All 9 field tokens present
    for token in ("start_ts=", "end_ts=", "duration_ms=", "min_percent=",
                  "station_id=", "station_name=", "url=", "outcome=recovered", "cause_hint=unknown"):
        assert token in msg, f"missing field token {token!r} in log line: {msg}"
    # T-62-01: station_name and url are %r-quoted (single quotes around the value)
    assert "station_name='Test Station'" in msg
    assert "url='http://example.test/'" in msg


def test_dwell_timer_fires_after_threshold(qtbot):
    """D-07: dwell timer (1500ms) fires underrun_recovery_started when timeout elapses.

    Drives _underrun_dwell_timer.timeout.emit() synchronously (mirrors
    tests/test_player.py:54 elapsed-timer pattern) — does not wait for real wall clock.
    """
    player = make_player(qtbot)
    _seed_url(player)
    player._on_gst_buffering(None, _fake_buffering_msg(100))   # arm
    player._on_gst_buffering(None, _fake_buffering_msg(40))    # open → main slot starts dwell timer
    qtbot.wait(50)   # let queued connection deliver and start the timer

    # Drive the timer synchronously (bypass real wall clock, mirror tests/test_player.py:54)
    with qtbot.waitSignal(player.underrun_recovery_started, timeout=1000):
        player._underrun_dwell_timer.timeout.emit()


def test_sub_dwell_recovery_silent(qtbot):
    """D-07: cycle that closes BEFORE the 1500ms dwell elapses cancels the timer
    and does NOT emit underrun_recovery_started."""
    player = make_player(qtbot)
    _seed_url(player)
    player._on_gst_buffering(None, _fake_buffering_msg(100))   # arm
    player._on_gst_buffering(None, _fake_buffering_msg(60))    # open
    qtbot.wait(50)
    # Recover before dwell elapses — main-thread slot stops the timer
    player._on_gst_buffering(None, _fake_buffering_msg(100))   # close
    qtbot.wait(100)

    # Dwell timer must NOT be active anymore
    assert not player._underrun_dwell_timer.isActive()

    # Drive timer.timeout — even if an erroneous emit slipped through,
    # the open-cycle state is gone, so underrun_recovery_started must NOT fire.
    # Use assertNotEmitted with a short wait.
    with qtbot.assertNotEmitted(player.underrun_recovery_started, wait=200):
        # No-op: just verify nothing fires during the wait window
        pass
