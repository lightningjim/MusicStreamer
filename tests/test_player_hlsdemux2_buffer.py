"""BUG-YT-LIVE-BUFFER / D-01 + D-02 — hlsdemux2 internal buffer configuration
and YouTube live DVR seek.

Root-cause summary (D-01, already fixed):
  In GStreamer >= 1.22, playbin3 selects hlsdemux2 (adaptivedemux2 family,
  rank 257) over the legacy hlsdemux (rank 256) for HLS URLs.  hlsdemux2
  manages its own internal download queue via max-buffering-time and
  high-watermark-time (default: 30 s each), independent of
  playbin3.buffer-duration.  The Phase 84 stage-and-apply path propagates
  buffer-duration to queue2 (decoded-audio buffer), which is downstream of
  hlsdemux2 and irrelevant to its segment-download buffer.  Raising
  BUFFER_DURATION_S from 30 to 120 s therefore had no effect on YouTube live
  stream underruns — hlsdemux2's internal buffer stayed at its 30 s default.

  Fix (D-01): Player.__init__ connects to deep-element-added on the playbin3
  pipeline.  _on_deep_element_added detects "hlsdemux2" factory-name elements
  and sets max-buffering-time + high-watermark-time to
  self._current_buffer_duration_s (CPython-atomic int read — same justification
  as _preroll_in_flight cross-thread reads in qt-glib-bus-threading.md
  Pattern 2).

Root-cause summary (D-02, this cycle's fix):
  max-buffering-time=120 s sets the download CEILING, but at the live edge
  there are only ~0-6 s of already-published segments ahead of the play
  position (RFC 8216: start no closer than 3 * targetduration from edge).
  Live verification confirmed underruns still occur: 1418 ms gap drains the
  buffer to 0 % — physically impossible with a true 120 s buffer, but
  consistent with ~2 s at the live edge.  YouTube exposes a DVR window of
  7200 s (3600 × 2 s segments); a GStreamer SEEK_TYPE_END seek of -30 s
  after first PLAYING state positions playback ~36 s behind the live edge,
  giving a genuine ~30 s cushion of already-published segments.

  Fix (D-02): youtube_resolved Signal now carries is_live bool.
  _on_youtube_resolved sets _pending_live_dvr_seek = is_live.
  _on_playbin_state_changed fires _apply_live_dvr_seek() once.

Test conventions:
  - _GST_SECOND hard-coded (no ``import gi``) per D-26 / QA-02.
  - ``make_player`` verbatim-duplicate pattern per PATTERNS.md §S-6.
  - ``mock_pipeline.connect`` calls captured via call_args_list.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from musicstreamer.constants import BUFFER_DURATION_S
from musicstreamer.player import Player

# Gst.SECOND is 1_000_000_000 (nanoseconds) — hard-coded here so the test
# file does not need ``import gi`` (D-26 / QA-02).
_GST_SECOND = 1_000_000_000


# ----------------------------------------------------------------------
# Per-file helpers
# ----------------------------------------------------------------------

def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out.

    Per PATTERNS.md §S-6 — per-file helper duplication, not conftest.
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


def _make_element(factory_name: str) -> MagicMock:
    """Build a mock GStreamer element with a factory that returns factory_name."""
    factory = MagicMock()
    factory.get_name.return_value = factory_name
    element = MagicMock()
    element.get_factory.return_value = factory
    return element


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------

def test_deep_element_added_connected_at_init(qtbot):
    """Player.__init__ must connect deep-element-added on the pipeline.

    D-01 contract: the connection is made during __init__ so every URI
    bind that creates a new hlsdemux2 instance is covered, including the
    very first play() call.
    """
    p = make_player(qtbot)
    connect_calls = [c for c in p._pipeline.connect.call_args_list
                     if c.args and c.args[0] == "deep-element-added"]
    assert connect_calls, (
        "deep-element-added signal not connected in Player.__init__. "
        "BUG-YT-LIVE-BUFFER D-01 requires this connection so hlsdemux2 "
        "elements are configured with the correct max-buffering-time."
    )


def test_on_deep_element_added_configures_hlsdemux2(qtbot):
    """_on_deep_element_added sets max-buffering-time and high-watermark-time
    on hlsdemux2 elements to BUFFER_DURATION_S * Gst.SECOND.
    """
    p = make_player(qtbot)
    element = _make_element("hlsdemux2")

    p._on_deep_element_added(p._pipeline, MagicMock(), element)

    target_ns = BUFFER_DURATION_S * _GST_SECOND
    element.set_property.assert_any_call("max-buffering-time", target_ns)
    element.set_property.assert_any_call("high-watermark-time", target_ns)


def test_on_deep_element_added_uses_current_buffer_duration(qtbot):
    """_on_deep_element_added uses _current_buffer_duration_s, not the
    constant BUFFER_DURATION_S, so adaptive growth (Phase 84) is reflected
    when hlsdemux2 is created for the next URI bind.
    """
    p = make_player(qtbot)
    p._current_buffer_duration_s = 120  # simulate adaptive growth to cap
    element = _make_element("hlsdemux2")

    p._on_deep_element_added(p._pipeline, MagicMock(), element)

    expected_ns = 120 * _GST_SECOND
    element.set_property.assert_any_call("max-buffering-time", expected_ns)
    element.set_property.assert_any_call("high-watermark-time", expected_ns)


def test_on_deep_element_added_ignores_non_hlsdemux2(qtbot):
    """_on_deep_element_added must not touch elements that are not hlsdemux2.

    deep-element-added fires for EVERY child element added to the pipeline
    (pulsesink, equalizer-nbands, aacparse, queue2, etc.).  Only hlsdemux2
    must be configured; all others must be left untouched.
    """
    p = make_player(qtbot)

    for name in ("hlsdemux", "queue2", "pulsesink", "aacparse",
                 "decodebin3", "uridecodebin3", "fakesink"):
        element = _make_element(name)
        p._on_deep_element_added(p._pipeline, MagicMock(), element)
        element.set_property.assert_not_called(), (
            f"set_property was called on non-hlsdemux2 element '{name}'"
        )


def test_on_deep_element_added_handles_missing_factory(qtbot):
    """_on_deep_element_added must not raise if get_factory() returns None.

    GStreamer can return elements with no factory (e.g. elements created
    directly without a factory).  The handler must be defensive.
    """
    p = make_player(qtbot)
    element = MagicMock()
    element.get_factory.return_value = None

    # Must not raise
    p._on_deep_element_added(p._pipeline, MagicMock(), element)
    element.set_property.assert_not_called()


def test_on_deep_element_added_survives_set_property_exception(qtbot):
    """_on_deep_element_added must not propagate exceptions from
    element.set_property (e.g. property not available on this build).

    The handler wraps set_property in a try/except so a GLib property
    error on an unusual GStreamer build does not crash the player.
    """
    p = make_player(qtbot)
    element = _make_element("hlsdemux2")
    element.set_property.side_effect = RuntimeError("property unavailable")

    # Must not raise
    p._on_deep_element_added(p._pipeline, MagicMock(), element)


# ======================================================================
# D-02 — YouTube live DVR seek
# ======================================================================

def test_pending_live_dvr_seek_false_at_init(qtbot):
    """_pending_live_dvr_seek must be False at Player construction.

    The flag must not be True at startup; it is only set when
    _on_youtube_resolved fires with is_live=True.
    """
    p = make_player(qtbot)
    assert p._pending_live_dvr_seek is False


def test_on_youtube_resolved_sets_flag_for_live_stream(qtbot):
    """_on_youtube_resolved must set _pending_live_dvr_seek=True when
    is_live=True, so _on_playbin_state_changed will issue the DVR seek.
    """
    p = make_player(qtbot)
    p._on_youtube_resolved("https://example.com/live.m3u8", True)
    assert p._pending_live_dvr_seek is True


def test_on_youtube_resolved_clears_flag_for_vod(qtbot):
    """_on_youtube_resolved must leave _pending_live_dvr_seek=False when
    is_live=False (VOD stream).  A DVR seek on a VOD stream would seek to
    30 s before the video's END, which is wrong.
    """
    p = make_player(qtbot)
    p._on_youtube_resolved("https://example.com/vod.m3u8", False)
    assert p._pending_live_dvr_seek is False


def test_apply_live_dvr_seek_calls_pipeline_seek(qtbot):
    """_apply_live_dvr_seek must call pipeline.seek() with SEEK_TYPE_END and
    a negative nanosecond offset equal to _LIVE_DVR_SEEK_OFFSET_S * Gst.SECOND.

    Uses a hard-coded _GST_SECOND constant (D-26 / QA-02 — no 'import gi').
    """
    p = make_player(qtbot)
    p._pipeline.seek.return_value = True

    p._apply_live_dvr_seek()

    assert p._pipeline.seek.called, "_apply_live_dvr_seek did not call pipeline.seek()"
    args = p._pipeline.seek.call_args
    # Positional args: rate, format, flags, start_type, start, stop_type, stop
    # start must be negative (seeking behind live edge)
    pos_args = args[0] if args[0] else list(args[1].values())
    # start value (index 4) must be -_LIVE_DVR_SEEK_OFFSET_S * Gst.SECOND
    start_ns = pos_args[4]
    expected_ns = -(p._LIVE_DVR_SEEK_OFFSET_S * _GST_SECOND)
    assert start_ns == expected_ns, (
        f"DVR seek start offset is {start_ns} ns, expected {expected_ns} ns "
        f"(-{p._LIVE_DVR_SEEK_OFFSET_S} s)"
    )


def test_on_playbin_state_changed_fires_dvr_seek_once(qtbot):
    """_on_playbin_state_changed must call _apply_live_dvr_seek() when
    _pending_live_dvr_seek is True and clear the flag immediately.

    The flag must be False after the call so subsequent PLAYING transitions
    (e.g. PAUSED→PLAYING after a CDN recovery) do NOT re-seek.
    """
    p = make_player(qtbot)
    p._pending_live_dvr_seek = True
    p._pipeline.seek.return_value = True

    p._on_playbin_state_changed()

    assert p._pipeline.seek.called, (
        "_on_playbin_state_changed did not call pipeline.seek() "
        "when _pending_live_dvr_seek was True"
    )
    assert p._pending_live_dvr_seek is False, (
        "_pending_live_dvr_seek should be cleared after the seek fires "
        "so subsequent PLAYING transitions do not re-seek"
    )


def test_on_playbin_state_changed_no_seek_without_flag(qtbot):
    """_on_playbin_state_changed must NOT call pipeline.seek() when
    _pending_live_dvr_seek is False (non-live or already-seeked stream).
    """
    p = make_player(qtbot)
    assert p._pending_live_dvr_seek is False  # default

    p._on_playbin_state_changed()

    # seek() must not have been called for the DVR path
    # (it may be called by other internal code, so we check only the
    # SEEK_TYPE_END pattern that _apply_live_dvr_seek uses)
    for call_args in p._pipeline.seek.call_args_list:
        pos = call_args[0] if call_args[0] else list(call_args[1].values())
        if len(pos) >= 4:
            import gi
            gi.require_version("Gst", "1.0")
            from gi.repository import Gst
            if pos[3] == Gst.SeekType.END:
                raise AssertionError(
                    "pipeline.seek() was called with SEEK_TYPE_END even though "
                    "_pending_live_dvr_seek was False"
                )


# ======================================================================
# D-02 addendum — tracker disarm + _last_buffer_percent reset on DVR seek
# ======================================================================

def test_apply_live_dvr_seek_disarms_tracker(qtbot):
    """_apply_live_dvr_seek must call _tracker.disarm_for_seek() so the
    post-seek BUFFERING=0% events from the FLUSH do not open a false
    underrun cycle.

    Before the seek the tracker is armed (simulated by having it observe
    percent=100).  After _apply_live_dvr_seek the tracker must be disarmed
    so a subsequent observe(0) does NOT return "OPENED".
    """
    p = make_player(qtbot)
    p._pipeline.seek.return_value = True

    # Arm the tracker the normal way: observe percent=100 first.
    # Tracker starts unarmed; first percent==100 flips it to armed.
    p._tracker.observe(100)
    assert p._tracker._armed is True, "tracker should be armed after observe(100)"

    # Now apply the DVR seek; this must call disarm_for_seek().
    p._apply_live_dvr_seek()

    assert p._tracker._armed is False, (
        "_apply_live_dvr_seek must disarm the tracker so post-seek "
        "BUFFERING=0% events are not logged as underruns"
    )
    assert p._tracker._open is False, (
        "_apply_live_dvr_seek must ensure no cycle is open after disarm"
    )


def test_apply_live_dvr_seek_resets_last_buffer_percent(qtbot):
    """_apply_live_dvr_seek must reset _last_buffer_percent to -1 so the
    post-seek BUFFERING=0% event is not swallowed by the de-dup guard.

    _on_gst_buffering skips messages where percent == _last_buffer_percent.
    If _last_buffer_percent is still 100 (from before the seek), the first
    post-seek 0% message is de-duped away and the tracker never re-arms on
    the subsequent 100%.
    """
    p = make_player(qtbot)
    p._pipeline.seek.return_value = True

    # Simulate state after initial fill: last seen percent was 100.
    p._last_buffer_percent = 100

    p._apply_live_dvr_seek()

    assert p._last_buffer_percent == -1, (
        "_apply_live_dvr_seek must reset _last_buffer_percent to -1 so "
        "the post-seek BUFFERING=0% message is not de-duped away"
    )


def test_apply_live_dvr_seek_uses_key_unit_flag(qtbot):
    """_apply_live_dvr_seek must use GST_SEEK_FLAG_KEY_UNIT (not SNAP_BEFORE).

    GStreamer 1.28.2 emits a warning 'SNAP seeks only work in combination
    with the KEY_UNIT flag' if SNAP_BEFORE is used without KEY_UNIT.
    KEY_UNIT alone is the correct flag for efficient live-stream repositioning.
    """
    p = make_player(qtbot)
    p._pipeline.seek.return_value = True

    p._apply_live_dvr_seek()

    assert p._pipeline.seek.called
    args = p._pipeline.seek.call_args[0]
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    flags = args[2]  # third positional arg: GstSeekFlags
    assert flags & Gst.SeekFlags.KEY_UNIT, (
        "_apply_live_dvr_seek must include GST_SEEK_FLAG_KEY_UNIT to avoid "
        "GStreamer SNAP_BEFORE warning and ensure clean segment alignment"
    )
    assert not (flags & Gst.SeekFlags.SNAP_BEFORE), (
        "_apply_live_dvr_seek must not use GST_SEEK_FLAG_SNAP_BEFORE without "
        "KEY_UNIT — use KEY_UNIT only"
    )


# ======================================================================
# BUG-YT-LIVE-DROPS-BUFFER-UNDERRUN Round 2 — message-forward instrumentation
# ======================================================================

def test_on_deep_element_added_enables_message_forward(qtbot):
    """_on_deep_element_added must set message-forward=True on hlsdemux2 so
    its internal children's ERROR/WARNING messages (otherwise swallowed by
    GstBin) are surfaced via message::element / GstBinForwarded.
    """
    p = make_player(qtbot)
    element = _make_element("hlsdemux2")

    p._on_deep_element_added(p._pipeline, MagicMock(), element)

    element.set_property.assert_any_call("message-forward", True)


def test_message_forward_config_survives_exception(qtbot):
    """_enable_hlsdemux2_message_forwarding must not raise if set_property
    fails (older/unusual GStreamer build without this property)."""
    p = make_player(qtbot)
    element = _make_element("hlsdemux2")

    # Must not raise even if set_property always fails.
    element.set_property.side_effect = RuntimeError("property unavailable")
    p._on_deep_element_added(p._pipeline, MagicMock(), element)


def test_bus_connects_message_element(qtbot):
    """Player.__init__ must wire message::element to _on_gst_element_message
    so forwarded GstBinForwarded messages from hlsdemux2 are handled."""
    p = make_player(qtbot)
    connect_calls = [c for c in p._pipeline.get_bus.return_value.connect.call_args_list
                      if c.args and c.args[0] == "message::element"]
    assert connect_calls, (
        "message::element not connected in Player.__init__ — forwarded "
        "hlsdemux2 child messages (GstBinForwarded) will never be observed."
    )
    assert connect_calls[0].args[1] == p._on_gst_element_message


def _fake_forwarded_element_msg(inner):
    """Build a fake bus message wrapping `inner` as a GstBinForwarded envelope."""
    struct = MagicMock()
    struct.get_name.return_value = "GstBinForwarded"
    struct.get_value.return_value = inner
    msg = MagicMock()
    msg.get_structure.return_value = struct
    return msg


def test_on_gst_element_message_ignores_non_forwarded(qtbot):
    """Non-GstBinForwarded element messages must be silently ignored."""
    p = make_player(qtbot)
    struct = MagicMock()
    struct.get_name.return_value = "some-other-structure"
    msg = MagicMock()
    msg.get_structure.return_value = struct

    with patch.object(p._tracker, "note_segment_retry_in_cycle") as mock_note:
        p._on_gst_element_message(None, msg)
    mock_note.assert_not_called()


def test_on_gst_element_message_ignores_missing_structure(qtbot):
    """A message with no structure (get_structure() -> None) must not raise."""
    p = make_player(qtbot)
    msg = MagicMock()
    msg.get_structure.return_value = None

    # Must not raise
    p._on_gst_element_message(None, msg)


def test_on_gst_element_message_handles_forwarded_warning(qtbot):
    """A forwarded WARNING from hlsdemux2's internal children must log and
    flip the tracker's cause_hint to 'segment_retry' (Round 2 fix)."""
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst as _Gst

    p = make_player(qtbot)
    p._tracker.bind_url(1, "Test", "http://x/")
    p._tracker.observe(100)  # arm
    p._tracker.observe(70)   # open cycle

    inner = MagicMock()
    inner.type = _Gst.MessageType.WARNING
    inner.parse_warning.return_value = ("connection timed out", "souphttpsrc debug info")
    inner.src.get_name.return_value = "souphttpsrc0"
    msg = _fake_forwarded_element_msg(inner)

    p._on_gst_element_message(None, msg)

    assert p._tracker._cause_hint == "segment_retry"


def test_on_gst_element_message_handles_forwarded_error(qtbot):
    """A forwarded ERROR from hlsdemux2's internal children must also flip
    cause_hint to 'segment_retry' (non-fatal from the top-level pipeline's
    perspective — the top-level bus never saw a message::error)."""
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst as _Gst

    p = make_player(qtbot)
    p._tracker.bind_url(1, "Test", "http://x/")
    p._tracker.observe(100)  # arm
    p._tracker.observe(70)   # open cycle

    inner = MagicMock()
    inner.type = _Gst.MessageType.ERROR
    inner.parse_error.return_value = ("could not read from resource", "debug")
    inner.src.get_name.return_value = "download-worker-0"
    msg = _fake_forwarded_element_msg(inner)

    p._on_gst_element_message(None, msg)

    assert p._tracker._cause_hint == "segment_retry"


def test_on_gst_element_message_ignores_other_forwarded_types(qtbot):
    """A forwarded message that is neither ERROR nor WARNING (e.g. INFO) must
    not touch cause_hint."""
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst as _Gst

    p = make_player(qtbot)
    p._tracker.bind_url(1, "Test", "http://x/")
    p._tracker.observe(100)  # arm
    p._tracker.observe(70)   # open cycle

    inner = MagicMock()
    inner.type = _Gst.MessageType.INFO
    msg = _fake_forwarded_element_msg(inner)

    p._on_gst_element_message(None, msg)

    assert p._tracker._cause_hint == "unknown"


def test_on_gst_element_message_survives_malformed_forwarded_payload(qtbot):
    """If the forwarded message's introspection raises (unfamiliar payload
    shape), the bus-loop-thread handler must swallow it, not crash."""
    p = make_player(qtbot)
    inner = MagicMock()
    inner.type = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    struct = MagicMock()
    struct.get_name.return_value = "GstBinForwarded"
    struct.get_value.side_effect = RuntimeError("boom")
    msg = MagicMock()
    msg.get_structure.return_value = struct

    # Must not raise
    p._on_gst_element_message(None, msg)


def test_disarm_for_seek_clears_armed_and_open(qtbot):
    """_BufferUnderrunTracker.disarm_for_seek clears both _armed and _open.

    Called directly on the tracker to verify the pure-Python contract.
    """
    from musicstreamer.player import _BufferUnderrunTracker
    t = _BufferUnderrunTracker()

    # Arm + open cycle
    t.observe(100)   # arm
    t.observe(0)     # open cycle
    assert t._armed is True
    assert t._open is True

    t.disarm_for_seek()

    assert t._armed is False, "disarm_for_seek must clear _armed"
    assert t._open is False, "disarm_for_seek must clear _open"

    # After disarm, observe(0) must NOT open a new cycle
    result = t.observe(0)
    assert result is None, (
        "after disarm_for_seek, observe(0) must return None (tracker not armed)"
    )

    # Re-arm on 100% → now observe(0) should open a cycle normally
    t.observe(100)
    result2 = t.observe(0)
    assert result2 == "OPENED", (
        "tracker must re-arm normally after disarm → observe(100) → observe(0)"
    )
