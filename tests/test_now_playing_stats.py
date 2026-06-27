"""Phase 98-02: NowPlayingPanel stats-for-nerds format rows tests.

Wave 0 panel rendering tests for the four detected-format rows added in
Phase 98 Plan 02: Encoding, Bitrate, Sample rate, Bit depth.

Covers:
- D-01: Encoding/Bitrate show detected AND declared together always
- D-02: mismatch renders detected value amber (_StatLabel.set_mismatch=True)
- D-05: Sample rate / Bit depth are plain _MutedLabel (no set_mismatch)
- D-07: unknown detected renders em-dash; no flag when both unknown
- Finding 5: 5 kbps bitrate mismatch tolerance
- Pitfall 8: no per-row setVisible in _build_stats_widget
"""
from __future__ import annotations

import inspect
from typing import Any, Optional

import pytest
from PySide6.QtCore import QObject, Signal

from musicstreamer.models import StationStream
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _FakePlayer(QObject):
    title_changed = Signal(str)
    failover = Signal(object)
    offline = Signal(str)
    twitch_resolved = Signal(str)
    youtube_resolved = Signal(str, bool, int)
    youtube_resolution_failed = Signal(str, int)
    playback_error = Signal(str)
    cookies_cleared = Signal(str)
    elapsed_updated = Signal(int)
    buffer_percent = Signal(int)
    _cancel_timers_requested = Signal()
    _error_recovery_requested = Signal(int)
    _try_next_stream_requested = Signal()
    _preroll_about_to_finish_requested = Signal(int)
    _playbin_playing_state_reached = Signal()
    _underrun_cycle_opened = Signal()
    _underrun_cycle_closed = Signal(object)
    underrun_recovery_started = Signal()
    underrun_count_changed = Signal(int)
    buffer_duration_changed = Signal(int, bool)
    audio_caps_detected = Signal(int, int, int)
    audio_format_detected = Signal(int, str, int)

    def __init__(self):
        super().__init__()

    def set_volume(self, v): pass
    def play(self, station, **kw): pass
    def pause(self): pass
    def stop(self): pass
    def play_stream(self, s): pass
    def invalidate_for_edit(self, station, is_playing=False, **kw): pass
    def restore_eq_from_settings(self, repo): pass
    def set_eq_enabled(self, enabled): pass
    def set_eq_profile(self, p): pass
    def set_eq_preamp(self, db): pass
    def shutdown_underrun_tracker(self): pass


class _FakeRepo:
    def __init__(self, settings: Optional[dict] = None) -> None:
        self._settings = dict(settings or {})
        self._favorites: list = []
        self._stations: list = []

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value

    def is_favorited(self, station_name: str, track_title: str) -> bool:
        return False

    def add_favorite(self, station_name: str, provider_name: str, track_title: str, genre: str) -> None:
        pass

    def remove_favorite(self, station_name: str, track_title: str) -> None:
        pass

    def list_streams(self, station_id: int) -> list:
        return []

    def list_stations(self) -> list:
        return []

    def get_station(self, station_id: int):
        raise ValueError("Station not found")

    def list_sibling_links(self, station_id: int) -> list:
        return []

    def set_preferred_stream(self, station_id: int, stream_id) -> None:
        pass


def _make_panel(qtbot, streams=None):
    """Construct NowPlayingPanel with _FakePlayer and a _FakeRepo containing streams."""
    repo = _FakeRepo({"volume": "80"})
    panel = NowPlayingPanel(_FakePlayer(), repo)
    qtbot.addWidget(panel)
    if streams is not None:
        # Inject streams directly so update_detected_format can look them up
        panel._streams = streams
    return panel


# ---------------------------------------------------------------------------
# Task 1 structural tests (D-04, D-05, Pitfall 8)
# ---------------------------------------------------------------------------


def test_four_format_labels_default_em_dash(qtbot):
    """D-07 / D-04: all four detected-format labels exist and default to em-dash."""
    panel = _make_panel(qtbot)
    assert hasattr(panel, "_encoding_label"), "missing _encoding_label"
    assert hasattr(panel, "_bitrate_label"), "missing _bitrate_label"
    assert hasattr(panel, "_sample_rate_label"), "missing _sample_rate_label"
    assert hasattr(panel, "_bit_depth_label"), "missing _bit_depth_label"
    assert panel._encoding_label.text() == "—", "_encoding_label should default to em-dash"
    assert panel._bitrate_label.text() == "—", "_bitrate_label should default to em-dash"
    assert panel._sample_rate_label.text() == "—", "_sample_rate_label should default to em-dash"
    assert panel._bit_depth_label.text() == "—", "_bit_depth_label should default to em-dash"


def test_sample_rate_label_is_muted_not_stat(qtbot):
    """D-05: _sample_rate_label is a plain _MutedLabel, NOT a _StatLabel.

    Only Encoding and Bitrate rows get the amber mismatch flag (D-05 scope).
    """
    from musicstreamer.ui_qt.now_playing_panel import _StatLabel
    panel = _make_panel(qtbot)
    assert hasattr(panel, "_sample_rate_label"), "missing _sample_rate_label"
    assert not isinstance(panel._sample_rate_label, _StatLabel), (
        "_sample_rate_label must be a plain _MutedLabel, not _StatLabel (D-05)"
    )
    assert not hasattr(panel._sample_rate_label, "set_mismatch"), (
        "_sample_rate_label must not have set_mismatch (D-05)"
    )


def test_bit_depth_label_is_muted_not_stat(qtbot):
    """D-05: _bit_depth_label is a plain _MutedLabel, NOT a _StatLabel."""
    from musicstreamer.ui_qt.now_playing_panel import _StatLabel
    panel = _make_panel(qtbot)
    assert hasattr(panel, "_bit_depth_label"), "missing _bit_depth_label"
    assert not isinstance(panel._bit_depth_label, _StatLabel), (
        "_bit_depth_label must be a plain _MutedLabel, not _StatLabel (D-05)"
    )


def test_no_per_row_visible_in_build_stats(qtbot):
    """Pitfall 8: _build_stats_widget has exactly one setVisible call (the wrapper).

    No per-row setVisible is permitted — rows inherit visibility from the
    wrapper.setVisible(False) at the bottom of _build_stats_widget.
    """
    src = inspect.getsource(NowPlayingPanel._build_stats_widget)
    code_lines = [line for line in src.splitlines() if not line.lstrip().startswith("#")]
    visible_calls = [line for line in code_lines if "setVisible" in line]
    assert len(visible_calls) == 1, (
        "Only wrapper.setVisible(False) is permitted in _build_stats_widget — "
        f"found {len(visible_calls)} setVisible calls: {visible_calls} (Pitfall 8)"
    )


# ---------------------------------------------------------------------------
# Task 2 behavioral tests (D-01, D-02, D-07, Finding 5)
# ---------------------------------------------------------------------------


def test_encoding_row_shows_detected_and_expected(qtbot):
    """D-01: Encoding row shows BOTH detected value and declared expected value.

    When declared codec is 'AAC' and detected is 'AAC', the label text
    must contain the detected value and the '(exp: AAC)' suffix.
    """
    streams = [StationStream(id=7, station_id=1, url="http://x", label="hi",
                              quality="hi", position=1, codec="AAC",
                              bitrate_kbps=128)]
    panel = _make_panel(qtbot, streams=streams)
    panel.update_detected_format(7, "AAC", 128)
    text = panel._encoding_label.text()
    assert "AAC" in text, f"detected codec must appear in label: {text!r}"
    assert "(exp: AAC)" in text, f"expected codec suffix must appear: {text!r}"


def test_encoding_mismatch_sets_amber(qtbot):
    """D-02: declared 'AAC', detected 'MP3' → _encoding_label._mismatch is True."""
    streams = [StationStream(id=3, station_id=1, url="http://x", label="hi",
                              quality="hi", position=1, codec="AAC",
                              bitrate_kbps=128)]
    panel = _make_panel(qtbot, streams=streams)
    panel.update_detected_format(3, "MP3", 128)
    assert panel._encoding_label._mismatch is True, (
        "Mismatch between declared AAC and detected MP3 must set _mismatch=True"
    )


def test_no_mismatch_flag_when_codec_matches(qtbot):
    """D-02: declared 'MP3', detected 'MP3' → _encoding_label._mismatch is False."""
    streams = [StationStream(id=5, station_id=1, url="http://x", label="hi",
                              quality="hi", position=1, codec="MP3",
                              bitrate_kbps=320)]
    panel = _make_panel(qtbot, streams=streams)
    panel.update_detected_format(5, "MP3", 320)
    assert panel._encoding_label._mismatch is False, (
        "Matching declared and detected codec must leave _mismatch=False"
    )


def test_bitrate_mismatch_tolerance(qtbot):
    """D-02 / Finding 5: 5 kbps tolerance suppresses small drift; >5 kbps flags amber.

    declared 320, detected 318 (Δ2 ≤5) → _bitrate_label._mismatch False
    declared 320, detected 128 (Δ192 >5) → _bitrate_label._mismatch True
    """
    streams = [StationStream(id=11, station_id=1, url="http://x", label="hi",
                              quality="hi", position=1, codec="MP3",
                              bitrate_kbps=320)]
    panel = _make_panel(qtbot, streams=streams)

    # Within tolerance: Δ2 kbps
    panel.update_detected_format(11, "MP3", 318)
    assert panel._bitrate_label._mismatch is False, (
        "Δ2 kbps (declared 320, detected 318) is within 5 kbps tolerance — no flag"
    )

    # Beyond tolerance: Δ192 kbps
    panel.update_detected_format(11, "MP3", 128)
    assert panel._bitrate_label._mismatch is True, (
        "Δ192 kbps (declared 320, detected 128) exceeds 5 kbps tolerance — must flag"
    )


def test_em_dash_when_codec_unknown(qtbot):
    """D-07: detected codec '' → _encoding_label text starts with em-dash.

    When detected codec is unknown but declared is known, the expected suffix
    is still appended. No mismatch flag when detected is unknown.
    """
    streams = [StationStream(id=9, station_id=1, url="http://x", label="hi",
                              quality="hi", position=1, codec="AAC",
                              bitrate_kbps=128)]
    panel = _make_panel(qtbot, streams=streams)
    panel.update_detected_format(9, "", 0)
    text = panel._encoding_label.text()
    assert text.startswith("—"), (
        f"Unknown detected codec must render em-dash first: {text!r}"
    )
    assert "(exp: AAC)" in text, (
        f"Known declared codec must still appear as expected suffix: {text!r}"
    )
    assert panel._encoding_label._mismatch is False, (
        "No mismatch flag when detected codec is unknown (D-07)"
    )


def test_no_mismatch_when_both_unknown(qtbot):
    """D-07: both detected '' and declared '' → text exactly em-dash, _mismatch False."""
    streams = [StationStream(id=13, station_id=1, url="http://x", label="hi",
                              quality="hi", position=1, codec="",
                              bitrate_kbps=0)]
    panel = _make_panel(qtbot, streams=streams)
    panel.update_detected_format(13, "", 0)
    assert panel._encoding_label.text() == "—", (
        "Both unknown: label must be exactly em-dash (no '(exp:...)' suffix)"
    )
    assert panel._encoding_label._mismatch is False, (
        "No mismatch when both detected and declared are unknown (D-07)"
    )


def test_stream_switch_clears_prior_mismatch_amber(qtbot):
    """Gap G-03: after a mismatched stream sets amber, an emission for a DIFFERENT
    stream of the same station that matches its own declared values must clear the
    amber.

    Regression: stale-sid emissions (codec guard armed after set_state(PLAYING),
    code-review WR-01) carried the previous stream's id, so the new stream's
    detected values were compared against the wrong declared row and the amber
    stayed stuck. With the correct id the comparison matches and amber clears.
    """
    streams = [
        StationStream(id=1, station_id=1, url="http://x1", label="hi", quality="hi",
                      position=1, codec="MP3", bitrate_kbps=320),
        StationStream(id=2, station_id=1, url="http://x2", label="lo", quality="lo",
                      position=2, codec="AAC", bitrate_kbps=128),
    ]
    panel = _make_panel(qtbot, streams=streams)
    # Stream 1 declared 320 kbps but detected 128 → bitrate mismatch amber
    panel.update_detected_format(1, "MP3", 128)
    assert panel._bitrate_label._mismatch is True, "Δ192 kbps must set amber first"
    # Switch to stream 2 (declared AAC/128); its emission carries the CORRECT id
    panel.update_detected_format(2, "AAC", 128)
    assert panel._bitrate_label._mismatch is False, (
        "switching to a matching stream must clear the prior bitrate amber (G-03)"
    )
    assert panel._encoding_label._mismatch is False, (
        "encoding amber must also clear on a matching stream switch (G-03)"
    )


def test_mismatch_color_reverts_on_clear(qtbot):
    """UAT #3 root cause: set_mismatch(True) then (False) must actually REVERT the
    label's WindowText color, not just the _mismatch bool.

    The amber was applied via 2-arg setColor, which writes the role for ALL
    palette groups including Disabled — and _MutedLabel reads Disabled/WindowText
    back as its 'muted' color. So once amber was set, clearing read amber as
    'muted' and re-applied it: the highlight could never visually revert.
    """
    from PySide6.QtGui import QPalette
    streams = [StationStream(id=1, station_id=1, url="http://x", label="hi",
                              quality="hi", position=1, codec="MP3", bitrate_kbps=320)]
    panel = _make_panel(qtbot, streams=streams)
    label = panel._bitrate_label
    muted = label.palette().color(QPalette.Active, QPalette.WindowText)

    # Mismatch (declared 320, detected 64) → amber.
    panel.update_detected_format(1, "MP3", 64)
    amber = label.palette().color(QPalette.Active, QPalette.WindowText)
    assert amber != muted, "mismatched label must render a different (amber) color"

    # Matching (declared 320, detected 320) → must revert to muted.
    panel.update_detected_format(1, "MP3", 320)
    reverted = label.palette().color(QPalette.Active, QPalette.WindowText)
    assert reverted == muted, (
        "WindowText must revert to the muted color when the mismatch clears "
        "(UAT #3 — Disabled palette group must stay uncorrupted)"
    )


def test_stale_cross_station_emission_ignored(qtbot):
    """Gap G-03: an emission whose stream_id is not among the bound station's
    streams (a signal queued before the latest bind_station) is ignored — it must
    not overwrite the current row or paint a spurious value.
    """
    streams_b = [StationStream(id=20, station_id=2, url="http://b", label="hi",
                               quality="hi", position=1, codec="FLAC",
                               bitrate_kbps=1411)]
    panel = _make_panel(qtbot, streams=streams_b)
    panel.update_detected_format(20, "FLAC", 1411)  # matches its declared row
    assert panel._bitrate_label._mismatch is False
    # Stale emission for stream 99 — belongs to a different (previous) station.
    panel.update_detected_format(99, "MP3", 64)
    assert "1411" in panel._bitrate_label.text(), (
        "stale cross-station emission must not overwrite the bound row (G-03)"
    )
    assert panel._bitrate_label._mismatch is False, (
        "stale cross-station emission must not paint amber (G-03)"
    )


def test_update_detected_caps_sample_rate(qtbot):
    """D-05: update_detected_caps sets Sample rate label from rate_hz.

    48000 Hz → '48 kHz'; 0 Hz → '—'.
    """
    panel = _make_panel(qtbot)
    panel.update_detected_caps(1, 48000, 24)
    assert panel._sample_rate_label.text() == "48 kHz", (
        f"48000 Hz must render as '48 kHz': {panel._sample_rate_label.text()!r}"
    )
    panel.update_detected_caps(1, 0, 0)
    assert panel._sample_rate_label.text() == "—", (
        "0 Hz must render as em-dash"
    )


def test_update_detected_caps_bit_depth(qtbot):
    """D-05: update_detected_caps sets Bit depth label from bit_depth.

    24 → '24-bit'; 0 → '—'.
    """
    panel = _make_panel(qtbot)
    panel.update_detected_caps(1, 96000, 24)
    assert panel._bit_depth_label.text() == "24-bit", (
        f"bit_depth 24 must render as '24-bit': {panel._bit_depth_label.text()!r}"
    )
    panel.update_detected_caps(1, 0, 0)
    assert panel._bit_depth_label.text() == "—", (
        "bit_depth 0 must render as em-dash"
    )
