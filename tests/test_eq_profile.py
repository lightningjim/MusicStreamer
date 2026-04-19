"""Tests for musicstreamer.eq_profile — AutoEQ parser + serializer.

Covers Phase 47.2 D-21/D-22/D-23 (revised per RESEARCH C-1: LSC/HSC tokens)
plus Pitfall 5 preamp sign convention.
"""
from __future__ import annotations

import pytest

from musicstreamer.eq_profile import (
    EqBand,
    EqProfile,
    parse_autoeq,
    serialize_autoeq,
)


# ---------------------------------------------------------------------------
# Parse happy paths
# ---------------------------------------------------------------------------

def test_parse_single_pk_band():
    text = "Preamp: 0.0 dB\nFilter 1: ON PK Fc 105 Hz Gain -3.5 dB Q 0.7"
    p = parse_autoeq(text)
    assert len(p.bands) == 1
    assert p.preamp_db == 0.0
    b = p.bands[0]
    assert b.filter_type == "PK"
    assert b.freq_hz == 105.0
    assert b.gain_db == -3.5
    assert b.q == 0.7


def test_parse_preamp_header():
    text = "Preamp: -6.2 dB\nFilter 1: ON PK Fc 100 Hz Gain 0 dB Q 1.0"
    p = parse_autoeq(text)
    assert p.preamp_db == -6.2


def test_parse_shelf_tokens():
    """C-1 correction: AutoEQ uses LSC/HSC, not LS/HS."""
    text = (
        "Filter 1: ON LSC Fc 105 Hz Gain -3 dB Q 0.7\n"
        "Filter 2: ON HSC Fc 8000 Hz Gain 2 dB Q 0.7"
    )
    p = parse_autoeq(text)
    assert [b.filter_type for b in p.bands] == ["LSC", "HSC"]


def test_parse_case_insensitive_tokens():
    text = "filter 1: on pk fc 100 hz gain 1 db q 1"
    p = parse_autoeq(text)
    assert len(p.bands) == 1
    # Canonical uppercase preserved in output
    assert p.bands[0].filter_type == "PK"


def test_parse_skips_off_filters():
    text = (
        "Filter 1: ON PK Fc 100 Hz Gain 1 dB Q 1\n"
        "Filter 2: OFF PK Fc 200 Hz Gain 2 dB Q 1\n"
        "Filter 3: ON PK Fc 300 Hz Gain 3 dB Q 1\n"
    )
    p = parse_autoeq(text)
    freqs = [b.freq_hz for b in p.bands]
    assert freqs == [100.0, 300.0]


def test_parse_rejects_zero_on_filters():
    """D-06 path: all OFF → ValueError."""
    text = (
        "Preamp: 0 dB\n"
        "Filter 1: OFF PK Fc 100 Hz Gain 0 dB Q 1.0\n"
        "Filter 2: OFF PK Fc 200 Hz Gain 0 dB Q 1.0\n"
    )
    with pytest.raises(ValueError, match="no ON filters"):
        parse_autoeq(text)


def test_parse_rejects_malformed():
    with pytest.raises(ValueError):
        parse_autoeq("this is not an autoeq file")


def test_parse_tolerates_blank_and_comment_lines():
    text = (
        "\n"
        "# This is a comment\n"
        "Preamp: -3.0 dB\n"
        "\n"
        "# Another comment\n"
        "Filter 1: ON PK Fc 100 Hz Gain 1 dB Q 1.0\n"
        "\n"
    )
    p = parse_autoeq(text)
    assert p.preamp_db == -3.0
    assert len(p.bands) == 1


def test_preamp_sign_convention():
    """Pitfall 5: preamp stored as-is; callers ADD to band gain."""
    text = (
        "Preamp: -6.2 dB\n"
        "Filter 1: ON PK Fc 100 Hz Gain 4.0 dB Q 1.0"
    )
    p = parse_autoeq(text)
    assert p.preamp_db == -6.2
    assert p.bands[0].gain_db == 4.0  # NOT combined with preamp


# ---------------------------------------------------------------------------
# Serialize + round-trip
# ---------------------------------------------------------------------------

def test_serialize_round_trip():
    original = (
        "Preamp: -6.2 dB\n"
        "Filter 1: ON PK Fc 105 Hz Gain -3.5 dB Q 0.70\n"
        "Filter 2: ON LSC Fc 60 Hz Gain 2.5 dB Q 0.71\n"
        "Filter 3: ON HSC Fc 10000 Hz Gain -1.0 dB Q 0.80\n"
    )
    p1 = parse_autoeq(original)
    text2 = serialize_autoeq(p1)
    p2 = parse_autoeq(text2)
    assert p2.preamp_db == p1.preamp_db
    assert len(p2.bands) == len(p1.bands)
    for b1, b2 in zip(p1.bands, p2.bands):
        assert b2.filter_type == b1.filter_type
        assert b2.freq_hz == b1.freq_hz
        assert b2.gain_db == b1.gain_db
        assert b2.q == b1.q


def test_serialize_produces_header_line():
    p = EqProfile(preamp_db=-3.0, bands=[
        EqBand(filter_type="PK", freq_hz=1000.0, gain_db=2.0, q=1.0)
    ])
    out = serialize_autoeq(p)
    assert out.startswith("Preamp: ")


def test_parse_whitespace_tolerance():
    text = (
        "   Preamp:   -3.0   dB   \n"
        "\tFilter 1: ON PK Fc 100 Hz Gain 1.0 dB Q 1.0   \n"
    )
    p = parse_autoeq(text)
    assert p.preamp_db == -3.0
    assert len(p.bands) == 1
    assert p.bands[0].freq_hz == 100.0
