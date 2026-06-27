"""Phase 98 / Wave 0 unit tests — Player codec/bitrate detection seams.

Tests cover:
  - test_normalise_audio_codec: truth-table for _normalise_audio_codec pure function
  - test_bitrate_bps_to_kbps_conversion: TAG_NOMINAL_BITRATE preferred over TAG_BITRATE
  - test_codec_tag_emits_on_first_tag: armed guard → emits audio_format_detected
  - test_codec_tag_one_shot_disarm: guard disarms after first emit; second call no-ops
  - test_codec_tag_suppressed_during_preroll: _preroll_in_flight=True blocks emission

Analogs:
  - tests/test_player_caps.py — one-shot guard pattern, make_player, waitSignal,
    assertNotEmitted, disarm check
  - tests/test_player_tag.py — _fake_tag_msg / taglist.get_string mock pattern
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from musicstreamer.player import Gst, Player, _normalise_audio_codec


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out.

    Mirrors test_player_tag.py:28-38 pattern exactly (module-local copy for
    isolation — do NOT import from test_player_tag.py).
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


def _fake_codec_tag_msg(codec=None, nominal_bps=0, bitrate_bps=0):
    """Build a fake GStreamer tag message with codec/bitrate fields.

    taglist.get_string is routed by argument:
      - TAG_TITLE (any tag not containing 'audio-codec') → (False, None)
      - TAG_AUDIO_CODEC (arg containing 'audio-codec') → (codec is not None, codec or '')
    taglist.get_uint is routed by argument:
      - TAG_NOMINAL_BITRATE (arg containing 'nominal') → (nominal_bps > 0, nominal_bps)
      - TAG_BITRATE (any other uint tag) → (bitrate_bps > 0, bitrate_bps)

    Phase 98: arg-routing variant from 98-PATTERNS.md '_fake_codec_tag_msg' section.
    """
    taglist = MagicMock()

    def _get_string(tag):
        if "audio-codec" in str(tag):
            return (codec is not None, codec or "")
        return (False, None)  # TAG_TITLE not found

    def _get_uint(tag):
        if "nominal" in str(tag):
            return (nominal_bps > 0, nominal_bps)
        return (bitrate_bps > 0, bitrate_bps)

    taglist.get_string.side_effect = _get_string
    taglist.get_uint.side_effect = _get_uint
    msg = MagicMock()
    msg.parse_tag.return_value = taglist
    return msg


# ---------------------------------------------------------------------------
# _normalise_audio_codec truth-table
# ---------------------------------------------------------------------------

def test_normalise_audio_codec():
    """Truth-table for _normalise_audio_codec (Phase 98 D-03 vocabulary)."""
    cases = [
        # GStreamer TAG_AUDIO_CODEC string        expected output
        ("MPEG-1 Layer 3 (MP3)",                 "MP3"),
        ("MPEG-2 Layer 3 (MP3)",                 "MP3"),
        ("MPEG-1 Layer 2 (MP2)",                 "MP3"),   # A5: MP2 → MP3 family
        ("MPEG-4 AAC",                           "AAC"),
        ("MPEG-2 AAC",                           "AAC"),
        ("Free Lossless Audio Codec (FLAC)",     "FLAC"),
        ("Opus",                                 "OPUS"),   # exact match (case-insensitive)
        ("Vorbis",                               "OGG"),
        (None,                                   ""),
        ("",                                     ""),
        ("weird-unknown",                        ""),
    ]
    for raw, expected in cases:
        result = _normalise_audio_codec(raw)
        assert result == expected, (
            f"_normalise_audio_codec({raw!r}) → {result!r}, expected {expected!r}"
        )


# ---------------------------------------------------------------------------
# Emission and one-shot guard tests
# ---------------------------------------------------------------------------

def test_codec_tag_emits_on_first_tag(qtbot):
    """Armed guard + codec tag → emits audio_format_detected(sid, 'AAC', 128).

    Phase 98 D-06: detected codec/bitrate captured one-shot at preroll
    and emitted exactly once per stream.
    """
    player = make_player(qtbot)
    player._codec_tag_armed_for_stream_id = 42
    msg = _fake_codec_tag_msg(codec="MPEG-4 AAC", nominal_bps=128_000)
    with qtbot.waitSignal(player.audio_format_detected, timeout=1000) as blocker:
        player._on_gst_tag(bus=None, msg=msg)
    assert blocker.args == [42, "AAC", 128], (
        f"Expected [42, 'AAC', 128], got {blocker.args}"
    )


def test_bitrate_bps_to_kbps_conversion(qtbot):
    """TAG_NOMINAL_BITRATE (bps) preferred over TAG_BITRATE; both converted // 1000.

    Phase 98 / Pitfall 4: integer division (not round) for bps→kbps.
    """
    player = make_player(qtbot)

    # Case 1: both present — nominal wins
    player._codec_tag_armed_for_stream_id = 1
    msg = _fake_codec_tag_msg(codec="MPEG-4 AAC", nominal_bps=320_000, bitrate_bps=319_000)
    with qtbot.waitSignal(player.audio_format_detected, timeout=1000) as blocker:
        player._on_gst_tag(bus=None, msg=msg)
    assert blocker.args[2] == 320, (
        f"Expected bitrate_kbps=320 (nominal wins), got {blocker.args[2]}"
    )

    # Case 2: only TAG_BITRATE present
    player._codec_tag_armed_for_stream_id = 2
    msg2 = _fake_codec_tag_msg(codec="MPEG-4 AAC", nominal_bps=0, bitrate_bps=128_000)
    with qtbot.waitSignal(player.audio_format_detected, timeout=1000) as blocker2:
        player._on_gst_tag(bus=None, msg=msg2)
    assert blocker2.args[2] == 128, (
        f"Expected bitrate_kbps=128 (TAG_BITRATE fallback), got {blocker2.args[2]}"
    )


def test_codec_tag_dedup_repeated_identical(qtbot):
    """Repeated identical tags yield exactly ONE emission; the guard stays armed.

    Phase 98 gap-closure: detection accumulates for the stream's lifetime (the
    guard is NOT disarmed after the first emit, so late-arriving bitrate is still
    captured) but de-dups on the last-emitted (codec, bitrate), so a stream that
    re-sends the same tag does not flood the main thread (gap G-02 / FLAC lockup).
    """
    player = make_player(qtbot)
    player._arm_codec_detect_for_stream(42)
    msg = _fake_codec_tag_msg(codec="MPEG-4 AAC", nominal_bps=128_000)

    emissions = []
    player.audio_format_detected.connect(lambda *a: emissions.append(a))
    player._on_gst_tag(bus=None, msg=msg)
    # Guard stays armed for continued detection (late bitrate, corrected values).
    assert player._codec_tag_armed_for_stream_id == 42
    # Repeated identical tags must be de-duplicated.
    player._on_gst_tag(bus=None, msg=msg)
    player._on_gst_tag(bus=None, msg=msg)
    qtbot.waitUntil(lambda: True, timeout=100)
    assert len(emissions) == 1, (
        f"Expected exactly 1 emission for identical tags, got {len(emissions)}"
    )
    assert emissions[0] == (42, "AAC", 128)


def test_codec_tag_suppressed_during_preroll(qtbot):
    """_preroll_in_flight=True with armed guard → audio_format_detected NOT emitted.

    Phase 98 / Phase 83 D-07: preroll guard covers both title and codec paths
    (Critical Sequencing Note: preroll check moved BEFORE codec block).
    """
    player = make_player(qtbot)
    player._codec_tag_armed_for_stream_id = 42
    player._preroll_in_flight = True
    msg = _fake_codec_tag_msg(codec="MPEG-4 AAC", nominal_bps=128_000)
    with qtbot.assertNotEmitted(player.audio_format_detected, wait=200):
        player._on_gst_tag(bus=None, msg=msg)


# ---------------------------------------------------------------------------
# Phase 98 gap closure — accumulate-and-emit-on-change detection
# (G-01 no-downgrade, G-02 dedup/no-storm, G-03 corrected bitrate, #2 late FLAC
#  bitrate, WR-01 arm-before-PLAYING, SomaFM preroll-handoff arming)
# ---------------------------------------------------------------------------

def test_codec_then_late_bitrate_emits_corrected(qtbot):
    """Gap #2/#3: codec and bitrate arrive in SEPARATE tags. The first tag (codec
    only) emits with bitrate 0; a later bitrate tag merges and re-emits with the
    real bitrate. This is what captures FLAC's late bitrate and lets a corrected
    bitrate clear a false amber mismatch.
    """
    player = make_player(qtbot)
    player._arm_codec_detect_for_stream(5)
    emissions = []
    player.audio_format_detected.connect(lambda *a: emissions.append(a))

    # Tag 1: codec only (no bitrate yet).
    player._on_gst_tag(bus=None, msg=_fake_codec_tag_msg(codec="Free Lossless Audio Codec (FLAC)"))
    # Tag 2: bitrate only arrives later.
    player._on_gst_tag(bus=None, msg=_fake_codec_tag_msg(bitrate_bps=900_000))
    qtbot.waitUntil(lambda: True, timeout=100)

    assert emissions[0] == (5, "FLAC", 0), f"first emit codec-only, got {emissions[0]}"
    assert emissions[-1] == (5, "FLAC", 900), (
        f"late bitrate must merge and re-emit, got {emissions[-1]}"
    )


def test_codec_not_downgraded_by_codecless_tag(qtbot):
    """Gap G-01: once a codec is known, a later codec-less tag must NOT blank it.

    This is the YouTube symptom — a rebuffer re-sent a tag with bitrate but no
    codec, which used to re-emit an empty codec and blank the encoding row.
    """
    player = make_player(qtbot)
    player._arm_codec_detect_for_stream(8)
    emissions = []
    player.audio_format_detected.connect(lambda *a: emissions.append(a))

    player._on_gst_tag(bus=None, msg=_fake_codec_tag_msg(codec="MPEG-4 AAC", nominal_bps=128_000))
    assert emissions[-1] == (8, "AAC", 128)
    # A later tag with the SAME bitrate but no codec → merged value unchanged → no emit.
    player._on_gst_tag(bus=None, msg=_fake_codec_tag_msg(nominal_bps=128_000))
    qtbot.waitUntil(lambda: True, timeout=100)
    assert len(emissions) == 1, "codec-less identical tag must not re-emit / blank"
    assert player._codec_detect_codec == "AAC", "known codec must be retained"


def test_arm_idempotent_preserves_accumulator(qtbot):
    """Gap G-02: re-arming the SAME stream (e.g. a rebuffer PLAYING transition)
    preserves the accumulator and last-emitted dedup state — no re-detect storm.
    """
    player = make_player(qtbot)
    player._arm_codec_detect_for_stream(3)
    player._on_gst_tag(bus=None, msg=_fake_codec_tag_msg(codec="MPEG-4 AAC", nominal_bps=128_000))
    assert player._codec_detect_last == ("AAC", 128)

    # Re-arm same stream (idempotent): accumulator/dedup state survive.
    player._arm_codec_detect_for_stream(3)
    assert player._codec_detect_codec == "AAC"
    assert player._codec_detect_last == ("AAC", 128)

    # A genuinely new stream resets the accumulator.
    player._arm_codec_detect_for_stream(4)
    assert player._codec_detect_codec == ""
    assert player._codec_detect_bitrate == 0
    assert player._codec_detect_last == (None, None)


def test_rearm_for_new_stream_via_state_change(qtbot):
    """A PLAYING transition for a NEW current stream re-arms detection for it."""
    player = make_player(qtbot)
    player._current_stream = SimpleNamespace(id=42)
    player._pending_live_dvr_seek = False
    player._arm_codec_detect_for_stream(42)
    player._on_gst_tag(bus=None, msg=_fake_codec_tag_msg(codec="MPEG-4 AAC", nominal_bps=128_000))

    player._current_stream = SimpleNamespace(id=99)
    with patch.object(player, "_arm_caps_watch_for_current_stream"):
        player._on_playbin_state_changed()
    assert player._codec_tag_armed_for_stream_id == 99, "must arm for the new stream"
    assert player._codec_detect_last == (None, None), "accumulator reset for new stream"


def test_set_uri_arms_detection_before_playing(qtbot):
    """Gap G-03 / WR-01: _set_uri must arm detection BEFORE set_state(PLAYING) so
    any tag the bus-loop thread sees is accumulated under the correct stream id.
    """
    player = make_player(qtbot)
    player._current_stream = SimpleNamespace(id=7)

    guard_at_playing = []

    def _record_set_state(state):
        if state == Gst.State.PLAYING:
            guard_at_playing.append(player._codec_tag_armed_for_stream_id)

    player._pipeline.set_state.side_effect = _record_set_state
    with patch.object(player, "_arm_caps_watch_for_current_stream"):
        player._set_uri("http://example.com/stream.mp3")

    assert guard_at_playing, "set_state(PLAYING) was not called"
    assert guard_at_playing[0] == 7, (
        "detection must be armed with the current stream id BEFORE "
        "set_state(PLAYING) runs (WR-01/G-03)"
    )


def test_preroll_handoff_arms_detection(qtbot):
    """SomaFM gap: the gapless preroll handoff must arm detection for the real
    stream, or the Stats rows never populate after the intro jingle.
    """
    player = make_player(qtbot)
    real_stream = SimpleNamespace(id=55, url="http://ice.somafm.test/groovesalad")
    player._streams_queue = [real_stream]
    player._preroll_in_flight = True
    player._preroll_seq = 1
    player._preroll_handler_id = 0
    player._current_station_name = "Groove Salad"
    player._current_station_id = 1
    player._is_first_attempt = False  # skip elapsed-timer seeding branch

    with patch.object(player, "_arm_caps_watch_for_current_stream"):
        player._on_preroll_about_to_finish(expected_seq=1)

    assert player._current_stream is real_stream
    assert player._codec_tag_armed_for_stream_id == 55, (
        "preroll handoff must arm codec detection for the real stream (SomaFM)"
    )
