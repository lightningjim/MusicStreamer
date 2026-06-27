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

from unittest.mock import MagicMock, patch

from musicstreamer.player import Player, _normalise_audio_codec


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


def test_codec_tag_one_shot_disarm(qtbot):
    """After first emit _codec_tag_armed_for_stream_id == 0; second call no-ops.

    Phase 98 D-06 + Pitfall 6: disarm-before-emit; repeated tag messages yield
    exactly one emission per stream.
    """
    player = make_player(qtbot)
    player._codec_tag_armed_for_stream_id = 42
    msg = _fake_codec_tag_msg(codec="MPEG-4 AAC", nominal_bps=128_000)

    emission_count = []

    def _on_fmt(*args):
        emission_count.append(args)

    player.audio_format_detected.connect(_on_fmt)
    player._on_gst_tag(bus=None, msg=msg)
    # Guard should be disarmed
    assert player._codec_tag_armed_for_stream_id == 0, (
        "Expected _codec_tag_armed_for_stream_id == 0 after first emit"
    )
    # Second call with the same message must not emit
    player._on_gst_tag(bus=None, msg=msg)
    qtbot.waitUntil(lambda: True, timeout=200)
    assert len(emission_count) == 1, (
        f"Expected exactly 1 emission, got {len(emission_count)} "
        "(Pitfall 6 one-shot guard failure)"
    )


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
