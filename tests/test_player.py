"""Tests for Player elapsed-time QTimer (Plan 40.1-06) and EQ pipeline (Phase 47.2-02).

Regression tests locking in v1.5 elapsed-time parity: the Player emits
elapsed_updated(int) once per second while playing, halts on stop()/pause(),
and resets the counter on a new play() (but NOT on failover).

Phase 47.2-02 EQ tests cover equalizer-nbands pipeline integration:
element construction, apply/bypass, rebuild-on-band-count-change, preamp
additive offset, bandwidth=freq/Q conversion, shelf enum mapping,
settings round-trip, and graceful degradation when the plugin is missing.
"""
import pytest
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


# --------------------------------------------------------------------------- #
# Phase 47.2-02 — equalizer-nbands pipeline integration tests
# These construct a real Player (conftest stubs the GLib bus bridge only),
# so they require the gst-plugins-good equalizer element to be installed.
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module", autouse=True)
def _gst_init():
    """Initialize GStreamer once per test module.

    Production code runs ``Gst.init(None)`` in ``musicstreamer.__main__``;
    unit tests that construct a real pipeline must do the same.
    """
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    if not Gst.is_initialized():
        Gst.init(None)


@pytest.fixture
def player(qtbot):
    """Real Player instance (real playbin3 + real equalizer-nbands).

    The autouse ``_stub_bus_bridge`` fixture in conftest.py replaces the
    GLib.MainLoop daemon; everything else is a genuine GStreamer pipeline.
    """
    from musicstreamer.player import Player
    p = Player()
    yield p
    p.stop()


def test_player_eq_element_created(player):
    """D-01: equalizer-nbands is constructed at __init__ and wired into
    playbin3's audio-filter slot with the 10-band default placeholder."""
    assert player._eq is not None, (
        "Player must construct equalizer-nbands at __init__ (D-01)"
    )
    assert player._eq.get_property("num-bands") == 10, (
        "Default num-bands placeholder should be 10"
    )
    assert player._pipeline.get_property("audio-filter") is player._eq, (
        "Element must be assigned to playbin3.audio-filter slot (D-01)"
    )


def test_player_eq_apply_profile(player):
    """D-02, D-05: profile apply writes freq/gain/bandwidth per band;
    disable zeros every band gain (bypass semantics).

    Phase 52: gain is now ramped over 8 ticks; freq/bandwidth/type are still
    written synchronously in _start_eq_ramp's fresh-ramp branch. Drive the
    ramp to completion before asserting final gain values.
    """
    from musicstreamer.eq_profile import EqBand, EqProfile
    profile = EqProfile(preamp_db=0.0, bands=[
        EqBand("PK", 1000.0, -3.5, 1.0),
        EqBand("PK", 4000.0, 2.0, 2.0),
    ])
    player.set_eq_profile(profile)
    player.set_eq_enabled(True)
    # Phase 52: drive the gain ramp to completion (final tick commits exact target).
    for _ in range(player._EQ_RAMP_TICKS):
        player._eq_ramp_timer.timeout.emit()

    b0 = player._eq.get_child_by_index(0)
    b1 = player._eq.get_child_by_index(1)
    assert b0.get_property("freq") == pytest.approx(1000.0)
    assert b0.get_property("gain") == pytest.approx(-3.5)
    assert b0.get_property("bandwidth") == pytest.approx(1000.0)  # 1000 / 1.0
    assert b1.get_property("freq") == pytest.approx(4000.0)
    assert b1.get_property("gain") == pytest.approx(2.0)
    assert b1.get_property("bandwidth") == pytest.approx(2000.0)  # 4000 / 2.0

    # D-05: disable → every band gain zeroed (bypass) -- via ramp.
    player.set_eq_enabled(False)
    for _ in range(player._EQ_RAMP_TICKS):
        player._eq_ramp_timer.timeout.emit()
    n = player._eq.get_children_count()
    for i in range(n):
        assert player._eq.get_child_by_index(i).get_property("gain") == pytest.approx(0.0), (
            f"bypass must zero band {i} gain (D-05)"
        )


def test_player_eq_rebuild_on_band_count_change(player):
    """D-04 + Pitfall 1: changing the band count rebuilds the element."""
    from musicstreamer.eq_profile import EqBand, EqProfile
    assert player._eq.get_property("num-bands") == 10  # starting state

    profile5 = EqProfile(preamp_db=0.0, bands=[
        EqBand("PK", float(100 * (i + 1)), 0.0, 1.0) for i in range(5)
    ])
    player.set_eq_profile(profile5)
    assert player._eq is not None
    assert player._eq.get_property("num-bands") == 5

    profile8 = EqProfile(preamp_db=0.0, bands=[
        EqBand("PK", float(100 * (i + 1)), 0.0, 1.0) for i in range(8)
    ])
    player.set_eq_profile(profile8)
    assert player._eq is not None
    assert player._eq.get_property("num-bands") == 8


def test_player_eq_preamp_uniform_offset(player):
    """D-17, D-18, Pitfall 5: preamp is ADDED to every band gain (not subtracted).

    Phase 52: gain is now ramped on set_eq_enabled; drive the ramp to commit
    the exact target before asserting Pitfall 5 ADD semantics.
    """
    from musicstreamer.eq_profile import EqBand, EqProfile
    profile = EqProfile(preamp_db=0.0, bands=[
        EqBand("PK", 100.0, 4.0, 1.0),
        EqBand("PK", 1000.0, -2.0, 1.0),
    ])
    player.set_eq_profile(profile)
    player.set_eq_preamp(-6.0)
    player.set_eq_enabled(True)
    # Phase 52: drive the gain ramp to completion (final tick commits exact target).
    for _ in range(player._EQ_RAMP_TICKS):
        player._eq_ramp_timer.timeout.emit()

    b0 = player._eq.get_child_by_index(0)
    b1 = player._eq.get_child_by_index(1)
    # band 0: 4.0 + (-6.0) == -2.0
    assert b0.get_property("gain") == pytest.approx(-2.0), (
        "preamp must be ADDED to band gain (Pitfall 5)"
    )
    # band 1: -2.0 + (-6.0) == -8.0
    assert b1.get_property("gain") == pytest.approx(-8.0)


def test_player_eq_bandwidth_conversion(player):
    """Pitfall 4: GStreamer bandwidth (Hz) = freq_hz / Q (quality factor)."""
    from musicstreamer.eq_profile import EqBand, EqProfile
    profile = EqProfile(preamp_db=0.0, bands=[
        EqBand("PK", 500.0, 0.0, 0.5),   # bw = 1000.0
        EqBand("PK", 1000.0, 0.0, 1.0),  # bw = 1000.0
        EqBand("PK", 1000.0, 0.0, 3.0),  # bw ≈ 333.333
    ])
    player.set_eq_profile(profile)
    player.set_eq_enabled(True)

    assert player._eq.get_child_by_index(0).get_property("bandwidth") == pytest.approx(1000.0)
    assert player._eq.get_child_by_index(1).get_property("bandwidth") == pytest.approx(1000.0)
    assert player._eq.get_child_by_index(2).get_property("bandwidth") == pytest.approx(1000.0 / 3.0)


def test_player_eq_shelf_band_types(player):
    """D-03 revised (C-2): native shelf enum mapping PK=0, LSC=1, HSC=2."""
    from musicstreamer.eq_profile import EqBand, EqProfile
    profile = EqProfile(preamp_db=0.0, bands=[
        EqBand("LSC", 105.0, -3.0, 0.7),
        EqBand("PK", 1000.0, 0.0, 1.0),
        EqBand("HSC", 8000.0, 2.0, 0.7),
    ])
    player.set_eq_profile(profile)
    player.set_eq_enabled(True)

    # GstIirEqualizerBandType: 0=peak, 1=low-shelf, 2=high-shelf (Pitfall 3)
    assert int(player._eq.get_child_by_index(0).get_property("type")) == 1, "LSC → 1"
    assert int(player._eq.get_child_by_index(1).get_property("type")) == 0, "PK → 0"
    assert int(player._eq.get_child_by_index(2).get_property("type")) == 2, "HSC → 2"


def test_player_eq_settings_roundtrip(player, tmp_path, monkeypatch):
    """D-15: restore_eq_from_settings loads active_profile + enabled + preamp
    from a repo and wires the EQ element to match — with preamp applied."""
    import os
    from musicstreamer import paths

    # Redirect paths._root_override to tmp_path so eq_profiles_dir() resolves
    # under the test temp directory.
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))

    # Write a minimal AutoEQ profile
    eq_dir = os.path.join(str(tmp_path), "eq-profiles")
    os.makedirs(eq_dir, exist_ok=True)
    with open(os.path.join(eq_dir, "test.txt"), "w", encoding="utf-8") as fh:
        fh.write(
            "Preamp: -3.0 dB\n"
            "Filter 1: ON PK Fc 100 Hz Gain 2 dB Q 1.0\n"
        )

    class FakeRepo:
        def __init__(self):
            self._d = {}
        def get_setting(self, key, default=""):
            return self._d.get(key, default)
        def set_setting(self, key, value):
            self._d[key] = value

    repo = FakeRepo()
    repo.set_setting("eq_active_profile", "test.txt")
    repo.set_setting("eq_enabled", "1")
    repo.set_setting("eq_preamp_db", "-3.0")

    player.restore_eq_from_settings(repo)

    assert player._eq_profile is not None
    assert player._eq_preamp_db == pytest.approx(-3.0)
    assert player._eq_enabled is True
    # Element reflects state: band 0 gain = 2.0 + (-3.0) == -1.0
    assert player._eq.get_child_by_index(0).get_property("gain") == pytest.approx(-1.0)


def test_player_eq_handles_missing_plugin(qtbot, monkeypatch):
    """Graceful degrade: when equalizer-nbands is absent, Player still
    constructs and every set_eq_* call is a no-op instead of crashing."""
    import musicstreamer.player as player_mod
    from musicstreamer.eq_profile import EqBand, EqProfile

    real_make = player_mod.Gst.ElementFactory.make

    def fake_make(factory_name, *args, **kwargs):
        if factory_name == "equalizer-nbands":
            return None
        return real_make(factory_name, *args, **kwargs)

    monkeypatch.setattr(player_mod.Gst.ElementFactory, "make", fake_make)

    p = player_mod.Player()
    try:
        assert p._eq is None
        # None of these should raise
        p.set_eq_enabled(True)
        p.set_eq_profile(EqProfile(preamp_db=0.0, bands=[
            EqBand("PK", 1000.0, -3.0, 1.0),
        ]))
        p.set_eq_preamp(5.0)
    finally:
        p.stop()


# ----------------------------------------------------------------------
# Phase 52: EQ toggle smooth-ramp tests (BUG-03)
#
# These tests exercise the QTimer-driven gain ramp introduced in
# Player._start_eq_ramp / _on_eq_ramp_tick. The ramp lerps each band's
# gain from its current value to its target over _EQ_RAMP_TICKS ticks.
# Tests drive the timer manually via _eq_ramp_timer.timeout.emit() --
# same idiom as test_elapsed_timer_emits_seconds_while_playing (no wall
# clock). The real-pipeline `player` fixture is used so get_property('gain')
# reads are authoritative GstChildProxy reads.
# ----------------------------------------------------------------------


def test_player_eq_ramp_progression_lerps_each_band(player):
    """D-02: ticks 1..7 lerp gain linearly from 0.0 to target; tick 8 exact."""
    from musicstreamer.eq_profile import EqBand, EqProfile
    profile = EqProfile(preamp_db=0.0, bands=[
        EqBand("PK", 1000.0, -3.5, 1.0),  # target band 0: -3.5
        EqBand("PK", 4000.0,  2.0, 1.0),  # target band 1:  2.0
    ])
    player.set_eq_profile(profile)
    # Initial state: bypass (gains zeroed). Profile applied -> ramp starts.
    player.set_eq_enabled(True)

    targets = [-3.5, 2.0]
    b0 = player._eq.get_child_by_index(0)
    b1 = player._eq.get_child_by_index(1)

    # Drive 7 intermediate ticks; each must lerp linearly.
    for k in range(1, 8):
        player._eq_ramp_timer.timeout.emit()
        t = k / 8.0
        assert b0.get_property("gain") == pytest.approx(0.0 + (targets[0] - 0.0) * t, abs=1e-6), (
            f"tick {k}: band 0 gain mismatch (D-02 lerp)"
        )
        assert b1.get_property("gain") == pytest.approx(0.0 + (targets[1] - 0.0) * t, abs=1e-6), (
            f"tick {k}: band 1 gain mismatch (D-02 lerp)"
        )


def test_player_eq_ramp_final_tick_commits_exact_target(player):
    """D-02 final-tick exact-commit: tick 8 writes target verbatim, no residual.

    Also: ramp timer is stopped and ramp state cleared after final tick.
    """
    from musicstreamer.eq_profile import EqBand, EqProfile
    profile = EqProfile(preamp_db=0.0, bands=[
        EqBand("PK", 1000.0, -3.5, 1.0),
        EqBand("PK", 4000.0,  2.0, 1.0),
    ])
    player.set_eq_profile(profile)
    player.set_eq_enabled(True)

    # Drive all 8 ticks.
    for _ in range(8):
        player._eq_ramp_timer.timeout.emit()

    b0 = player._eq.get_child_by_index(0)
    b1 = player._eq.get_child_by_index(1)
    assert b0.get_property("gain") == pytest.approx(-3.5, abs=1e-9), (
        "tick 8 must commit exact target on band 0 (no lerp residual)"
    )
    assert b1.get_property("gain") == pytest.approx(2.0, abs=1e-9), (
        "tick 8 must commit exact target on band 1 (no lerp residual)"
    )
    assert player._eq_ramp_timer.isActive() is False, (
        "timer must stop after final tick"
    )
    assert player._eq_ramp_state is None, (
        "ramp state must clear after final tick"
    )


def test_player_eq_ramp_reverses_from_current_on_re_toggle(player):
    """D-05: mid-ramp re-toggle captures live gains as new start_gain.

    A ramp toward T1=non-zero is in flight after 3 ticks; flipping
    set_eq_enabled(False) does NOT snap the start back to 0.0 nor forward
    to T1 -- it captures the LIVE mid-ramp gains as the new start and
    interpolates from there to all-zeros over the next 8 ticks.
    """
    from musicstreamer.eq_profile import EqBand, EqProfile
    profile = EqProfile(preamp_db=0.0, bands=[
        EqBand("PK", 1000.0, -6.0, 1.0),
        EqBand("PK", 4000.0,  4.0, 1.0),
    ])
    player.set_eq_profile(profile)
    player.set_eq_enabled(True)
    targets_phase1 = [-6.0, 4.0]

    # Drive 3 ticks of the first ramp.
    for _ in range(3):
        player._eq_ramp_timer.timeout.emit()

    b0 = player._eq.get_child_by_index(0)
    b1 = player._eq.get_child_by_index(1)
    mid0 = b0.get_property("gain")
    mid1 = b1.get_property("gain")
    # Sanity: mid-ramp values are between 0 and the original targets.
    assert 0.0 < abs(mid0) < abs(targets_phase1[0]), (
        "phase 1: mid-ramp gain must be partial, not snapped"
    )
    assert 0.0 < abs(mid1) < abs(targets_phase1[1]), (
        "phase 1: mid-ramp gain must be partial, not snapped"
    )

    # Re-toggle mid-ramp: target becomes [0, 0]; start MUST be the
    # live mid-ramp gains (D-05 reverse-from-current).
    player.set_eq_enabled(False)
    state = player._eq_ramp_state
    assert state is not None, "ramp state must exist after re-toggle"
    assert state["tick_index"] == 0, "tick_index resets on re-toggle"
    assert state["target_gain"][0] == pytest.approx(0.0)
    assert state["target_gain"][1] == pytest.approx(0.0)
    assert state["start_gain"][0] == pytest.approx(mid0, abs=1e-6), (
        "D-05: start_gain must be live mid-ramp gain (not 0.0, not original target)"
    )
    assert state["start_gain"][1] == pytest.approx(mid1, abs=1e-6), (
        "D-05: start_gain must be live mid-ramp gain (not 0.0, not original target)"
    )

    # Drive 8 more ticks: gains must converge exactly to zero.
    for _ in range(8):
        player._eq_ramp_timer.timeout.emit()
    assert b0.get_property("gain") == pytest.approx(0.0, abs=1e-9)
    assert b1.get_property("gain") == pytest.approx(0.0, abs=1e-9)
    assert player._eq_ramp_timer.isActive() is False


def test_player_eq_ramp_graceful_degrade_no_timer_when_eq_missing(qtbot, monkeypatch):
    """When equalizer-nbands plugin is missing (_eq is None), set_eq_enabled
    flips the state flag (D-06) but starts NO ramp timer (graceful-degrade)."""
    import musicstreamer.player as player_mod

    real_make = player_mod.Gst.ElementFactory.make

    def fake_make(factory_name, *args, **kwargs):
        if factory_name == "equalizer-nbands":
            return None
        return real_make(factory_name, *args, **kwargs)

    monkeypatch.setattr(player_mod.Gst.ElementFactory, "make", fake_make)

    p = player_mod.Player()
    try:
        assert p._eq is None
        # Must not raise; must not start the timer.
        p.set_eq_enabled(True)
        assert p._eq_enabled is True, "D-06: state flag flips immediately"
        assert p._eq_ramp_timer.isActive() is False, (
            "graceful-degrade: ramp timer NOT started when _eq is None"
        )
        assert p._eq_ramp_state is None, (
            "graceful-degrade: no ramp state when _eq is None"
        )
        p.set_eq_enabled(False)
        assert p._eq_enabled is False
        assert p._eq_ramp_timer.isActive() is False
    finally:
        p.stop()


def test_player_eq_ramp_set_eq_profile_stops_in_flight_ramp(player):
    """T-52-01: set_eq_profile cancels any in-flight ramp (the new profile
    will get a fresh ramp on the next set_eq_enabled call). Avoids writing
    via stale GstChildProxy after _rebuild_eq_element runs.
    """
    from musicstreamer.eq_profile import EqBand, EqProfile
    profile_a = EqProfile(preamp_db=0.0, bands=[
        EqBand("PK", 1000.0, -3.0, 1.0),
        EqBand("PK", 4000.0,  3.0, 1.0),
    ])
    player.set_eq_profile(profile_a)
    player.set_eq_enabled(True)
    # Mid-ramp: timer is active, ramp state is populated.
    player._eq_ramp_timer.timeout.emit()
    player._eq_ramp_timer.timeout.emit()
    assert player._eq_ramp_timer.isActive() is True
    assert player._eq_ramp_state is not None

    # Same band count as profile_a -> _rebuild_eq_element NOT triggered;
    # we are testing the explicit ramp-cancel guard at set_eq_profile entry.
    profile_b = EqProfile(preamp_db=0.0, bands=[
        EqBand("PK", 1500.0, -2.0, 1.0),
        EqBand("PK", 5000.0,  2.0, 1.0),
    ])
    player.set_eq_profile(profile_b)
    assert player._eq_ramp_timer.isActive() is False, (
        "set_eq_profile must stop any in-flight ramp (T-52-01)"
    )
    assert player._eq_ramp_state is None, (
        "set_eq_profile must clear ramp state (T-52-01)"
    )


# ---------------------------------------------------------------------------
# Phase 82 D-01/D-03/D-05: preferred_stream_id behavioral tests + drift-guard
#
# Task 1 minimal RED contract + Task 2 full behavioral suite.
# All tests assert on _streams_queue / _current_stream per MEMORY.md
# GStreamer-mock-blind-spot (do NOT assert on pipeline.emit(...)).
# ---------------------------------------------------------------------------


def _make_player_mock(qtbot):
    """Create a Player with pipeline mocked (mirrors make_player in this file)."""
    from musicstreamer.player import Player
    from unittest.mock import MagicMock, patch
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    player._pipeline = MagicMock()
    return player


def _make_stream_ph82(id_, position, quality, url="http://stream.test/"):
    """Construct a minimal StationStream for Phase 82 preferred_stream_id tests."""
    from musicstreamer.models import StationStream
    return StationStream(
        id=id_,
        station_id=1,
        url=f"{url}{id_}",
        quality=quality,
        position=position,
    )


def _make_station_ph82(streams, preferred_stream_id=None):
    """Construct a minimal Station for Phase 82 preferred_stream_id tests."""
    from musicstreamer.models import Station
    return Station(
        id=1,
        name="Test Station",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=streams,
        preferred_stream_id=preferred_stream_id,
    )


def test_preferred_stream_id_minimal_red(qtbot):
    """Phase 82 D-01/D-03 RED gate (Task 1): preferred_stream_id places
    the user-picked stream at queue head despite lower quality rank.
    """
    from unittest.mock import patch
    p = _make_player_mock(qtbot)
    s_hi = _make_stream_ph82(1, 1, "hi", "http://yt/")
    s_med = _make_stream_ph82(2, 2, "med", "http://twitch/")
    station = _make_station_ph82([s_hi, s_med], preferred_stream_id=2)
    with patch.object(p, "_set_uri"):
        p.play(station)
    assert p._current_stream.id == 2, (
        "Phase 82 D-03: preferred_stream_id=2 must place stream id=2 at queue "
        "head; got id=%d instead" % p._current_stream.id
    )


def test_preferred_stream_id_at_queue_head(qtbot):
    """Phase 82 D-01/D-03: preferred_stream_id places that stream at queue head
    and remaining stream in _streams_queue.
    """
    from unittest.mock import patch
    p = _make_player_mock(qtbot)
    s_hi = _make_stream_ph82(1, 1, "hi", "http://yt/")
    s_med = _make_stream_ph82(2, 2, "med", "http://twitch/")
    station = _make_station_ph82([s_hi, s_med], preferred_stream_id=2)
    with patch.object(p, "_set_uri"):
        p.play(station)
    assert p._current_stream.id == 2
    assert len(p._streams_queue) == 1
    assert p._streams_queue[0].id == 1


def test_preferred_stream_id_not_duplicated(qtbot):
    """Phase 82 D-03: picked stream appears exactly once across _current_stream
    and _streams_queue (no duplicate via identity vs equality pitfall).
    """
    from unittest.mock import patch
    p = _make_player_mock(qtbot)
    s1 = _make_stream_ph82(1, 1, "hi")
    s2 = _make_stream_ph82(2, 2, "med")
    station = _make_station_ph82([s1, s2], preferred_stream_id=2)
    with patch.object(p, "_set_uri"):
        p.play(station)
    all_ids = [p._current_stream.id] + [s.id for s in p._streams_queue]
    assert all_ids.count(2) == 1


def test_preferred_stream_id_none_falls_back_to_order_streams(qtbot):
    """Phase 82 D-03: when preferred_stream_id is None, order_streams ordering
    applies (existing Phase 47 behavior unchanged).

    Both streams have bitrate_kbps=0 (unknown), so order_streams sorts by
    position asc — stream at position=1 comes first regardless of quality.
    This matches order_streams D-07: unknown bitrates partitioned LAST and
    sorted by position asc among themselves.
    """
    from unittest.mock import patch
    p = _make_player_mock(qtbot)
    # Streams with no bitrate: order_streams sorts by position asc (D-07).
    s_pos1 = _make_stream_ph82(1, 1, "low", "http://x/")
    s_pos2 = _make_stream_ph82(2, 2, "hi", "http://x/")
    station = _make_station_ph82([s_pos2, s_pos1], preferred_stream_id=None)
    with patch.object(p, "_set_uri"):
        p.play(station)
    # order_streams puts position=1 first (unknown-bitrate partition, sorted by pos)
    assert p._current_stream.id == 1


def test_preferred_stream_id_stale_resolves_to_none_falls_back(qtbot):
    """Phase 82 RQ4: stale preferred_stream_id (id not in station.streams) falls
    back gracefully to order_streams ordering — D-05 'preferred first, not only'.
    """
    from unittest.mock import patch
    p = _make_player_mock(qtbot)
    s1 = _make_stream_ph82(1, 1, "hi")
    station = _make_station_ph82([s1], preferred_stream_id=999)  # stale
    with patch.object(p, "_set_uri"):
        p.play(station)
    assert p._current_stream.id == 1  # falls back to order_streams


def test_preferred_stream_id_beats_preferred_quality(qtbot):
    """Phase 82 D-03 precedence: explicit DB pick wins over programmatic kwarg
    hint when both are set and they point to different streams.
    """
    from unittest.mock import patch
    p = _make_player_mock(qtbot)
    s_hi = _make_stream_ph82(1, 1, "hi")
    s_med = _make_stream_ph82(2, 2, "med")
    station = _make_station_ph82([s_hi, s_med], preferred_stream_id=2)
    with patch.object(p, "_set_uri"):
        p.play(station, preferred_quality="hi")  # kwarg says hi
    assert p._current_stream.id == 2  # DB pick wins


def test_failover_after_preferred_stream_advances_queue(qtbot):
    """Phase 82 D-05 regression: user's picked stream fails → queue advances
    through the rest in order_streams order (existing failover semantics intact).
    """
    from unittest.mock import patch
    p = _make_player_mock(qtbot)
    s_hi = _make_stream_ph82(1, 1, "hi")
    s_med = _make_stream_ph82(2, 2, "med")
    station = _make_station_ph82([s_hi, s_med], preferred_stream_id=2)
    with patch.object(p, "_set_uri"):
        p.play(station)
    assert p._current_stream.id == 2  # preferred_stream_id pick at head
    with patch.object(p, "_set_uri"):
        p._try_next_stream()  # simulate stream 2 failing
    assert p._current_stream.id == 1  # queue advanced to next in order_streams


def test_preferred_stream_id_drift_guard():
    """Phase 82 D-03 drift-guard (Phase 51/55/61/63/81 precedent).

    Reads musicstreamer/player.py, filters non-comment lines, asserts the
    literal 'preferred_stream_id' appears at least once. Without the
    non-comment filter this test would pass trivially by matching a comment
    line — defeating the drift-guard purpose.
    """
    from pathlib import Path
    source = (
        Path(__file__).resolve().parent.parent / "musicstreamer" / "player.py"
    ).read_text()
    non_comments = "\n".join(
        ln for ln in source.splitlines() if not ln.lstrip().startswith("#")
    )
    assert "preferred_stream_id" in non_comments, (
        "Phase 82 D-03: preferred_stream_id lookup must exist in player.py "
        "(Player.play queue-build block). Do not remove silently."
    )


# ---------------------------------------------------------------------------
# Phase 83 D-03/D-05/D-06/D-07/D-08/D-09/D-10/D-11/D-12/D-13/D-14 + live-spike Q3
# behavioral tests + source-grep drift-guard.
#
# All tests use _make_player_mock (mocked pipeline) and patch _set_uri to
# suppress real I/O — same idiom as Phase 82 tests above. Do NOT assert on
# pipeline.emit(...) (MEMORY feedback_gstreamer_mock_blind_spot.md).
# ---------------------------------------------------------------------------


def _make_station_ph83(
    streams,
    *,
    id_=1,
    name="Test SomaFM Station",
    provider_name="SomaFM",
    prerolls=None,
    prerolls_fetched_at=None,
):
    """Construct a minimal Station for Phase 83 preroll tests. Default
    provider_name='SomaFM' because most Phase 83 tests use it; the bypass
    test (D-11) overrides to e.g. 'DI.fm'."""
    from musicstreamer.models import Station
    return Station(
        id=id_,
        name=name,
        provider_id=None,
        provider_name=provider_name,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=streams,
        prerolls=list(prerolls or []),
        prerolls_fetched_at=prerolls_fetched_at,
    )


def _connect_calls_include_about_to_finish(p):
    """Helper: True if any p._pipeline.connect(...) call had 'about-to-finish'
    as its first positional arg."""
    for c in p._pipeline.connect.call_args_list:
        if c.args and c.args[0] == "about-to-finish":
            return True
    return False


def test_preroll_sets_uri_and_connects_handler(qtbot):
    """Phase 83 D-05: SomaFM + prerolls + throttle expired → _set_uri gets
    a preroll URL, _pipeline.connect('about-to-finish', ...) is attached,
    _preroll_in_flight is True, _streams_queue == order_streams(streams),
    _try_next_stream is NOT called from play()."""
    p = _make_player_mock(qtbot)
    s_hi = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    s_med = _make_stream_ph82(2, 2, "med", "http://stream.test/")
    preroll_urls = [
        "https://somafm.com/preroll1.m4a",
        "https://somafm.com/preroll2.m4a",
    ]
    station = _make_station_ph83(
        [s_hi, s_med], prerolls=preroll_urls, prerolls_fetched_at=12345
    )
    with patch.object(p, "_set_uri") as mock_set_uri, \
         patch.object(p, "_try_next_stream") as mock_try_next:
        p.play(station)
    # _set_uri called with one of the preroll URLs (random pick).
    assert mock_set_uri.call_count == 1
    chosen = mock_set_uri.call_args[0][0]
    assert chosen in preroll_urls, (
        f"Phase 83 D-05: _set_uri must be called with a preroll URL; "
        f"got {chosen!r}"
    )
    # about-to-finish handler attached.
    assert _connect_calls_include_about_to_finish(p), (
        "Phase 83 D-05: _pipeline.connect('about-to-finish', ...) must be "
        "called when a preroll fires."
    )
    assert p._preroll_in_flight is True
    assert p._last_preroll_played_at is not None
    # _try_next_stream NOT called from play() — about-to-finish slot triggers it.
    assert mock_try_next.call_count == 0
    # _streams_queue content unchanged by preroll path (D-06).
    assert len(p._streams_queue) == len(station.streams)


def test_throttle_window_suppresses_preroll(qtbot):
    """Phase 83 D-12 (window): SomaFM + prerolls + throttle window NOT expired
    → preroll skipped; _set_uri called with the stream URL (not a preroll)."""
    import time
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station = _make_station_ph83(
        [s],
        prerolls=["https://somafm.com/preroll.m4a"],
        prerolls_fetched_at=12345,
    )
    # Pretend a preroll just played: throttle window NOT yet elapsed.
    p._last_preroll_played_at = time.monotonic()
    with patch.object(p, "_set_uri") as mock_set_uri:
        p.play(station)
    chosen = mock_set_uri.call_args[0][0]
    assert "preroll" not in chosen, (
        "Phase 83 D-12 window: preroll must be suppressed when window not "
        f"elapsed; got {chosen!r}"
    )
    assert not _connect_calls_include_about_to_finish(p), (
        "Phase 83 D-12 window: _pipeline.connect('about-to-finish', ...) "
        "must NOT be called when throttle suppresses preroll."
    )
    assert p._preroll_in_flight is False


def test_throttle_timestamp_set_on_start(qtbot, monkeypatch):
    """Phase 83 D-12 (timestamp): _last_preroll_played_at is set at preroll
    START (in _start_preroll), NOT at handoff (about-to-finish slot)."""
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station = _make_station_ph83(
        [s], prerolls=["https://somafm.com/preroll.m4a"], prerolls_fetched_at=1
    )
    # Patch musicstreamer.player.time.monotonic to a fixed value.
    import musicstreamer.player as player_mod
    fake_monotonic = MagicMock(return_value=1000.0)
    monkeypatch.setattr(player_mod.time, "monotonic", fake_monotonic)
    with patch.object(p, "_set_uri"), \
         patch.object(p, "_try_next_stream"):
        p.play(station)
    assert p._last_preroll_played_at == 1000.0, (
        "Phase 83 D-12 timestamp: _last_preroll_played_at must be set at "
        "preroll START via time.monotonic(); got "
        f"{p._last_preroll_played_at!r}"
    )


def test_preroll_does_not_pollute_streams_queue(qtbot):
    """Phase 83 D-06: preroll URLs NEVER enter _streams_queue; queue equals
    order_streams(streams) exactly."""
    from musicstreamer.stream_ordering import order_streams
    p = _make_player_mock(qtbot)
    s_hi = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    s_med = _make_stream_ph82(2, 2, "med", "http://stream.test/")
    station = _make_station_ph83(
        [s_hi, s_med],
        prerolls=["https://somafm.com/p1.m4a", "https://somafm.com/p2.m4a"],
        prerolls_fetched_at=1,
    )
    with patch.object(p, "_set_uri"), \
         patch.object(p, "_try_next_stream"):
        p.play(station)
    expected = list(order_streams(station.streams))
    assert p._streams_queue == expected, (
        "Phase 83 D-06: _streams_queue must equal order_streams(streams); "
        "preroll URLs must NEVER enter the queue."
    )
    assert len(p._streams_queue) == len(station.streams)


def test_preroll_backfill_scheduled_when_unfetched(qtbot, monkeypatch):
    """Phase 83 D-03/D-13: SomaFM + prerolls=[] + prerolls_fetched_at=None
    AND station.id not in _backfill_in_flight → daemon Thread spawned with
    target=_preroll_backfill_worker, daemon=True, args=(station.id, name);
    station.id added to _backfill_in_flight; play proceeds to stream."""
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station = _make_station_ph83(
        [s], id_=42, name="Beat Blender",
        prerolls=[], prerolls_fetched_at=None,
    )
    captured = {}

    class MockThread:
        def __init__(self, target=None, args=(), daemon=None, **kwargs):
            captured["target"] = target
            captured["args"] = args
            captured["daemon"] = daemon
            captured["kwargs"] = kwargs

        def start(self):
            captured["started"] = True

    import musicstreamer.player as player_mod
    monkeypatch.setattr(player_mod.threading, "Thread", MockThread)
    with patch.object(p, "_set_uri"):
        p.play(station)
    assert captured.get("target") == p._preroll_backfill_worker, (
        "Phase 83 D-13: Thread target must be _preroll_backfill_worker; "
        f"got {captured.get('target')!r}"
    )
    assert captured.get("daemon") is True, (
        "Phase 83 D-13: backfill Thread must be daemon=True; got "
        f"{captured.get('daemon')!r}"
    )
    assert captured.get("args") == (42, "Beat Blender")
    assert captured.get("started") is True
    assert 42 in p._backfill_in_flight, (
        "Phase 83 T-83-10: station.id must be added to _backfill_in_flight "
        "before Thread.start (single-flight)."
    )


def test_backfill_non_blocking(qtbot, monkeypatch):
    """Phase 83 D-13: play() does NOT block on the backfill — _set_uri is
    invoked synchronously after the Thread is scheduled; play returns
    without waiting."""
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station = _make_station_ph83(
        [s], prerolls=[], prerolls_fetched_at=None,
    )

    class MockThread:
        def __init__(self, **kwargs):
            pass

        def start(self):
            pass

    import musicstreamer.player as player_mod
    monkeypatch.setattr(player_mod.threading, "Thread", MockThread)
    with patch.object(p, "_set_uri") as mock_set_uri:
        p.play(station)
    # Play returned synchronously and called _set_uri exactly once with
    # the stream URL (NOT a preroll URL — prerolls=[]).
    assert mock_set_uri.call_count == 1, (
        "Phase 83 D-13: play() must call _set_uri exactly once (non-blocking; "
        "the stream URL goes out immediately while backfill runs in background)."
    )
    chosen = mock_set_uri.call_args[0][0]
    assert "stream.test" in chosen


def test_non_somafm_provider_bypasses_preroll(qtbot):
    """Phase 83 D-11: non-SomaFM station (e.g. provider_name='DI.fm') with
    SYNTHETIC prerolls — preroll codepath is bypassed entirely; _set_uri
    called with stream URL; _pipeline.connect NOT called with
    'about-to-finish'; _preroll_in_flight stays False."""
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station = _make_station_ph83(
        [s],
        provider_name="DI.fm",
        prerolls=["https://example.com/synthetic.m4a"],
        prerolls_fetched_at=1,
    )
    with patch.object(p, "_set_uri") as mock_set_uri:
        p.play(station)
    chosen = mock_set_uri.call_args[0][0]
    assert "stream.test" in chosen, (
        "Phase 83 D-11: non-SomaFM provider must bypass preroll codepath; "
        f"_set_uri got {chosen!r} (expected the stream URL)."
    )
    assert not _connect_calls_include_about_to_finish(p), (
        "Phase 83 D-11: _pipeline.connect('about-to-finish', ...) must NOT "
        "be called for non-SomaFM providers."
    )
    assert p._preroll_in_flight is False


def test_title_tag_suppressed_during_preroll(qtbot):
    """Phase 83 D-07: while _preroll_in_flight is True, _on_gst_tag MUST NOT
    emit title_changed (the preroll's m4a TAG_TITLE is suppressed so Now
    Playing keeps showing the station name). Once cleared, title_changed
    fires again (proves the guard is gated, not unconditional)."""
    p = _make_player_mock(qtbot)
    # Build a mock msg whose parse_tag().get_string(TAG_TITLE) returns
    # (True, "BeatBlenderID1").
    mock_taglist = MagicMock()
    mock_taglist.get_string.return_value = (True, "BeatBlenderID1")
    mock_msg = MagicMock()
    mock_msg.parse_tag.return_value = mock_taglist
    mock_bus = MagicMock()
    # Phase 83 D-07: in-flight → no title_changed.
    p._preroll_in_flight = True
    with patch.object(p, "title_changed") as mock_title_changed:
        p._on_gst_tag(mock_bus, mock_msg)
        assert mock_title_changed.emit.call_count == 0, (
            "Phase 83 D-07: title_changed.emit must NOT fire while "
            "_preroll_in_flight is True."
        )
    # Gate cleared → title_changed fires again.
    p._preroll_in_flight = False
    with patch.object(p, "title_changed") as mock_title_changed:
        p._on_gst_tag(mock_bus, mock_msg)
        assert mock_title_changed.emit.call_count == 1, (
            "Phase 83 D-07: title_changed.emit must fire once _preroll_in_flight "
            "is cleared (proves the guard is gated, not unconditional)."
        )


def test_preroll_bus_error_advances_to_stream(qtbot):
    """Phase 83 D-09: _handle_gst_error_recovery during preroll → disconnect
    handler, clear flag, advance via _try_next_stream; NO retry of a
    different preroll (no second 'about-to-finish' connect)."""
    p = _make_player_mock(qtbot)
    s_hi = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station = _make_station_ph83(
        [s_hi], prerolls=["https://somafm.com/p.m4a"], prerolls_fetched_at=1
    )
    with patch.object(p, "_set_uri"), \
         patch.object(p, "_try_next_stream"):
        p.play(station)
    assert p._preroll_in_flight is True
    # Snapshot how many about-to-finish connects happened before the error.
    connects_before = sum(
        1 for c in p._pipeline.connect.call_args_list
        if c.args and c.args[0] == "about-to-finish"
    )
    with patch.object(p, "_try_next_stream") as mock_try_next, \
         patch.object(p, "_clear_recovery_guard"):
        p._handle_gst_error_recovery()
    assert p._preroll_in_flight is False, (
        "Phase 83 D-09: _preroll_in_flight must be cleared after bus-error."
    )
    assert p._preroll_handler_id == 0
    assert mock_try_next.called, (
        "Phase 83 D-09: _try_next_stream must run after preroll bus-error."
    )
    # No second about-to-finish connect — D-09 says NO retry of a different preroll.
    connects_after = sum(
        1 for c in p._pipeline.connect.call_args_list
        if c.args and c.args[0] == "about-to-finish"
    )
    assert connects_after == connects_before, (
        "Phase 83 D-09: must NOT retry a different preroll on bus-error "
        f"(about-to-finish connects: before={connects_before}, after={connects_after})."
    )


def test_preroll_in_flight_pause_does_not_clear_flag(qtbot):
    """Phase 83 D-08 (WARNING-4): pause during preroll behaves as today —
    _preroll_in_flight stays True, _try_next_stream is NOT invoked from
    pause(), pipeline state transitions follow today's pause semantics."""
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station = _make_station_ph83(
        [s], prerolls=["https://somafm.com/p.m4a"], prerolls_fetched_at=1
    )
    with patch.object(p, "_set_uri"), \
         patch.object(p, "_try_next_stream"):
        p.play(station)
    assert p._preroll_in_flight is True
    with patch.object(p, "_try_next_stream") as mock_try_next:
        p.pause()
    assert p._preroll_in_flight is True, (
        "Phase 83 D-08: pause() must NOT clear _preroll_in_flight."
    )
    assert mock_try_next.call_count == 0, (
        "Phase 83 D-08: pause() must NOT invoke _try_next_stream."
    )


def test_streams_queue_failover_after_preroll_handoff(qtbot):
    """Phase 83 D-10 (WARNING-4, UAT-updated): after the gapless URI
    handoff completes (set_property on still-PLAYING pipeline), a
    subsequent bus-error on the station stream advances _streams_queue
    exactly as Phase 82 — the preroll handler does NOT regress D-10
    failover semantics."""
    p = _make_player_mock(qtbot)
    s0 = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    s1 = _make_stream_ph82(2, 2, "med", "http://stream.test/")
    station = _make_station_ph83(
        [s0, s1],
        prerolls=["https://somafm.com/p.m4a"],
        prerolls_fetched_at=1,
    )
    with patch.object(p, "_set_uri"), \
         patch.object(p, "_try_next_stream"):
        p.play(station)
    assert p._preroll_in_flight is True
    # Simulate the about-to-finish main-thread slot firing (gapless path).
    with patch.object(p, "_tracker", MagicMock()), \
         patch.object(p, "_underrun_dwell_timer", MagicMock()), \
         patch.object(p, "_failover_timer", MagicMock()), \
         patch.object(p, "_elapsed_timer", MagicMock()):
        # CR-01/WR-03: simulate the queued slot delivery — pass the current
        # _preroll_seq so the new seq-stamp guard accepts this call. _start_preroll
        # bumped it to >= 1 via play() above; passing it here mirrors what the
        # streaming-thread callback emits at the real about-to-finish point.
        p._on_preroll_about_to_finish(p._preroll_seq)
    # After gapless handoff: flag cleared, _current_stream is queue head.
    assert p._preroll_in_flight is False
    assert p._current_stream is not None
    first_played_id = p._current_stream.id
    assert first_played_id in (1, 2)
    # Reset recovery guard so the next call exercises the post-handoff
    # path, not the preroll-error branch (which D-09 covers separately).
    p._recovery_in_flight = False
    with patch.object(p, "_set_uri"), \
         patch.object(p, "_clear_recovery_guard"):
        p._handle_gst_error_recovery()
    # Post-handoff failover: _current_stream advanced via Phase 82
    # head-of-queue path; preroll handler did NOT regress failover.
    assert p._current_stream is None or p._current_stream.id != first_played_id, (
        "Phase 83 D-10 (UAT-updated): post-gapless-handoff failover must "
        "advance _current_stream via Phase 82 head-of-queue path."
    )


def test_preroll_eos_without_about_to_finish_advances_to_stream(qtbot):
    """Phase 83 live-spike Q3 RESOLVED (WARNING-5): malformed-preroll EOS
    bridge — bus.connect('message::eos', _on_gst_eos_during_preroll) fires
    the existing _try_next_stream_requested queued Signal when
    _preroll_in_flight is True; no-op when False (preserves today's EOS
    semantics)."""
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station = _make_station_ph83(
        [s], prerolls=["https://somafm.com/p.m4a"], prerolls_fetched_at=1
    )
    with patch.object(p, "_set_uri"), \
         patch.object(p, "_try_next_stream"):
        p.play(station)
    assert p._preroll_in_flight is True
    mock_bus = MagicMock()
    mock_msg = MagicMock()
    # True branch: in-flight → emit the existing queued Signal.
    with patch.object(p, "_try_next_stream_requested") as mock_signal:
        p._on_gst_eos_during_preroll(mock_bus, mock_msg)
        assert mock_signal.emit.call_count == 1, (
            "Phase 83 Q3: _on_gst_eos_during_preroll must emit "
            "_try_next_stream_requested when _preroll_in_flight is True."
        )
    # Flag stays True — the streaming-thread handler does NOT touch the flag;
    # the main-thread slot (or D-09 recovery branch) clears it.
    assert p._preroll_in_flight is True
    # False branch: no-op (preserves today's EOS semantics, which is none).
    p._preroll_in_flight = False
    with patch.object(p, "_try_next_stream_requested") as mock_signal:
        p._on_gst_eos_during_preroll(mock_bus, mock_msg)
        assert mock_signal.emit.call_count == 0, (
            "Phase 83 Q3: _on_gst_eos_during_preroll must be a no-op when "
            "_preroll_in_flight is False (today's EOS semantics unchanged)."
        )


def test_phase_83_preroll_drift_guard():
    """Phase 83 D-11 / D-14 drift-guard (Phase 51/55/61/63/81/82 precedent).
    Pins both the provider-gate literal '"SomaFM"' and the throttle-state
    token '_last_preroll_played_at' in non-comment text of player.py.
    Non-comment filter is REQUIRED (Pitfall 8 — a comment-only literal
    would satisfy the assert even after the gate code is removed)."""
    from pathlib import Path
    import re
    source = (
        Path(__file__).resolve().parent.parent / "musicstreamer" / "player.py"
    ).read_text()
    non_comments = "\n".join(
        re.sub(r"^\s*#.*$", "", ln) for ln in source.splitlines()
    )
    assert '"SomaFM"' in non_comments, (
        "Phase 83 D-11: SomaFM provider-gate literal must remain in Player. "
        "Do not remove silently."
    )
    assert "_last_preroll_played_at" in non_comments, (
        "Phase 83 D-12: throttle-state token must remain in Player. "
        "Do not remove silently."
    )
    # Phase 83 D-05 (UAT-corrected) — gapless URI handoff invariant,
    # SLICE-ANCHORED to the _on_preroll_about_to_finish method body.
    #
    # WHY SLICE EXTRACTION: a global non-comment grep for
    # `set_property("uri", ...)` would false-negative on the exact
    # regression this drift-guard exists to catch — a refactor that
    # reverts ONLY the slot to call _try_next_stream() removes the slot's
    # set_property("uri", ...) literal, BUT _set_uri retains its own
    # set_property("uri", ...) elsewhere in the file. A global grep would
    # still pass. Extracting the method body and asserting the literal
    # appears INSIDE the slice fails loudly in that scenario (focus
    # area 6 from the checker BLOCKER).
    slot_match = re.search(
        r'def _on_preroll_about_to_finish\(.*?\)(.*?)(?=\n    def |\Z)',
        non_comments,
        re.DOTALL,
    )
    assert slot_match, (
        "test_phase_83_preroll_drift_guard: _on_preroll_about_to_finish "
        "method removed from musicstreamer/player.py — regression scenario."
    )
    slot_body = slot_match.group(1)
    assert re.search(r'set_property\([^)]{0,80}["\']uri["\']', slot_body), (
        "test_phase_83_preroll_drift_guard: "
        "_on_preroll_about_to_finish must call set_property('uri', ...) "
        "directly to invoke playbin3's gapless URI handoff. A regression "
        "that reverts the slot to _try_next_stream() / _set_uri() would "
        "tear down the preroll mid-playback via set_state(NULL). The "
        "shipped slot body must contain the set_property('uri', ...) "
        "literal so a future refactor that removes it fails loudly."
    )


def test_preroll_about_to_finish_uses_gapless_uri_swap(qtbot):
    """Phase 83 D-05 (UAT-corrected): the about-to-finish slot performs a
    GAPLESS URI handoff via pipeline.set_property("uri", ...) on the
    still-PLAYING pipeline. set_state(NULL) is NOT called between preroll
    start and the stream URI swap; _try_next_stream() is NOT called on
    the direct-URL path."""
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station = _make_station_ph83(
        [s], prerolls=["https://somafm.com/p.m4a"], prerolls_fetched_at=1
    )
    with patch.object(p, "_set_uri"), \
         patch.object(p, "_try_next_stream") as mock_try_next:
        p.play(station)
    assert p._preroll_in_flight is True
    # Capture pre-slot set_state call count to verify the slot adds none.
    pre_set_state_calls = p._pipeline.set_state.call_count
    # Stub tracker + timers so the slot's bookkeeping calls are no-ops in test.
    with patch.object(p, "_tracker", MagicMock()), \
         patch.object(p, "_underrun_dwell_timer", MagicMock()), \
         patch.object(p, "_failover_timer", MagicMock()), \
         patch.object(p, "_elapsed_timer", MagicMock()):
        # CR-01/WR-03: simulate the queued slot delivery — pass the current
        # _preroll_seq so the new seq-stamp guard accepts this call. _start_preroll
        # bumped it to >= 1 via play() above; passing it here mirrors what the
        # streaming-thread callback emits at the real about-to-finish point.
        p._on_preroll_about_to_finish(p._preroll_seq)
    # Gapless invariant: set_property called once with the stream URL.
    set_property_calls = [
        c for c in p._pipeline.set_property.call_args_list
        if c.args and c.args[0] == "uri"
    ]
    assert len(set_property_calls) >= 1, (
        "Phase 83 D-05 (UAT fix): _on_preroll_about_to_finish must call "
        "pipeline.set_property('uri', ...) on the gapless path."
    )
    # The most-recent set_property('uri', ...) call carries the stream URL
    # (URI funnel normalization preserves the http(s):// scheme — Phase
    # 70 / WIN-01 only rewrites DI.fm-style URLs; stream.test passes through).
    last_uri = set_property_calls[-1].args[1]
    assert "stream.test" in last_uri, (
        f"Phase 83 D-05 (UAT fix): gapless set_property must receive the "
        f"station stream URL; got {last_uri!r}"
    )
    # No state-cycle: set_state call count UNCHANGED by the slot.
    assert p._pipeline.set_state.call_count == pre_set_state_calls, (
        "Phase 83 D-05 (UAT fix): _on_preroll_about_to_finish must NOT "
        "call pipeline.set_state on the gapless path (state cycle is "
        "exactly what 83-UAT identified as the bug)."
    )
    # _try_next_stream is NOT called on the direct-URL gapless path.
    assert mock_try_next.call_count == 0, (
        "Phase 83 D-05 (UAT fix): _try_next_stream must NOT be called "
        "from _on_preroll_about_to_finish on the direct-URL gapless path."
    )
    assert p._preroll_in_flight is False
    assert p._preroll_handler_id == 0
    # _streams_queue head consumed; tail (if any) remains for failover.
    assert s not in p._streams_queue, (
        "Phase 83 D-05 (UAT fix): gapless handoff must pop _streams_queue[0]."
    )
    # _current_stream now points to the consumed head.
    assert p._current_stream is s


def test_preroll_handoff_normalizes_url_via_aa_normalize(qtbot):
    """Phase 83 D-05 (UAT fix) drift-guard: the gapless set_property call
    routes through aa_normalize_stream_url (the project URI funnel —
    Phase 70 / WIN-01 / D-01 DI.fm HTTPS->HTTP rewrite). Bypassing the
    funnel would be a regression even though SomaFM URLs pass through
    unchanged."""
    from musicstreamer.url_helpers import aa_normalize_stream_url
    p = _make_player_mock(qtbot)
    # Use a DI.fm-style URL to make the funnel observable (https→http).
    s = _make_stream_ph82(1, 1, "hi", "https://prem4.di.fm/foo")
    station = _make_station_ph83(
        [s], prerolls=["https://somafm.com/p.m4a"], prerolls_fetched_at=1
    )
    with patch.object(p, "_set_uri"), \
         patch.object(p, "_try_next_stream"):
        p.play(station)
    with patch.object(p, "_tracker", MagicMock()), \
         patch.object(p, "_underrun_dwell_timer", MagicMock()), \
         patch.object(p, "_failover_timer", MagicMock()), \
         patch.object(p, "_elapsed_timer", MagicMock()):
        # CR-01/WR-03: simulate the queued slot delivery — pass the current
        # _preroll_seq so the new seq-stamp guard accepts this call. _start_preroll
        # bumped it to >= 1 via play() above; passing it here mirrors what the
        # streaming-thread callback emits at the real about-to-finish point.
        p._on_preroll_about_to_finish(p._preroll_seq)
    set_property_calls = [
        c for c in p._pipeline.set_property.call_args_list
        if c.args and c.args[0] == "uri"
    ]
    assert set_property_calls, (
        "Phase 83 D-05 (UAT fix): set_property('uri', ...) must be called."
    )
    last_uri = set_property_calls[-1].args[1]
    expected = aa_normalize_stream_url(s.url)
    assert last_uri == expected, (
        f"Phase 83 D-05 (UAT fix): gapless set_property must route the "
        f"URL through aa_normalize_stream_url (URI funnel); got "
        f"{last_uri!r}, expected {expected!r}"
    )


@pytest.mark.parametrize(
    "url_fragment", ["youtube.com", "youtu.be", "twitch.tv"]
)
def test_preroll_handoff_falls_back_for_youtube_url(qtbot, url_fragment):
    """Phase 83 D-05 (UAT fix) scope guard: if _streams_queue[0] is a
    YouTube/Twitch URL, the gapless path falls back to _try_next_stream()
    (the legacy path with async resolution via _play_youtube/_play_twitch)
    instead of set_property — playbin3 cannot stream a YouTube watch URL
    or Twitch channel URL directly."""
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", f"https://{url_fragment}/fake")
    station = _make_station_ph83(
        [s], prerolls=["https://somafm.com/p.m4a"], prerolls_fetched_at=1
    )
    with patch.object(p, "_set_uri"), \
         patch.object(p, "_try_next_stream"):
        p.play(station)
    # Slot invocation: should NOT directly set_property; should call
    # _try_next_stream() (the legacy fallback).
    with patch.object(p, "_try_next_stream") as mock_try_next_slot:
        # CR-01/WR-03: simulate the queued slot delivery — pass the current
        # _preroll_seq so the new seq-stamp guard accepts this call. _start_preroll
        # bumped it to >= 1 via play() above; passing it here mirrors what the
        # streaming-thread callback emits at the real about-to-finish point.
        p._on_preroll_about_to_finish(p._preroll_seq)
    assert mock_try_next_slot.call_count == 1, (
        f"Phase 83 D-05 (UAT fix): {url_fragment} URL must route through "
        f"_try_next_stream() fallback (async resolution path)."
    )
    # set_property('uri', ...) must NOT have been called with the
    # async-resolution URL by the slot itself.
    matching_set_property_calls = [
        c for c in p._pipeline.set_property.call_args_list
        if c.args
        and c.args[0] == "uri"
        and url_fragment in str(c.args[1])
    ]
    assert not matching_set_property_calls, (
        f"Phase 83 D-05 (UAT fix): gapless set_property must NOT be "
        f"called with a {url_fragment} URL — async resolution required."
    )
    # Flag + handler-id cleared before the fallback (so the inner
    # _try_next_stream's bookkeeping sees clean state).
    assert p._preroll_in_flight is False
    assert p._preroll_handler_id == 0


def test_preroll_handoff_invokes_tracker_bind_and_failover_timer_arm(qtbot):
    """Phase 83 D-05 (UAT fix) bookkeeping parity: the gapless slot
    mirrors _try_next_stream's tracker bind + failover-timer arm + elapsed-
    timer first-attempt seeding so underrun analytics + failover-timeout
    watchdog + elapsed-time display don't silently regress. force_close
    uses the 'preroll' outcome token (NOT 'failover') so analytics
    distinguish gapless handoff from a true stream failover."""
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station = _make_station_ph83(
        [s], prerolls=["https://somafm.com/p.m4a"], prerolls_fetched_at=1
    )
    with patch.object(p, "_set_uri"), \
         patch.object(p, "_try_next_stream"):
        p.play(station)
    mock_tracker = MagicMock()
    mock_tracker.force_close.return_value = None  # no prior cycle to close
    mock_failover_timer = MagicMock()
    mock_elapsed_timer = MagicMock()
    # Sanity: the preroll path enters the slot with _is_first_attempt True
    # (neither _start_preroll nor the bus-error preroll path touches it).
    assert p._is_first_attempt is True, (
        "Phase 83 D-05 (UAT fix) precondition: preroll path enters the "
        "about-to-finish slot with _is_first_attempt == True."
    )
    # Pre-seed elapsed_seconds to a sentinel so we can confirm the slot
    # resets it to 0 (mirror of _try_next_stream:1076).
    p._elapsed_seconds = 999
    with patch.object(p, "_tracker", mock_tracker), \
         patch.object(p, "_underrun_dwell_timer", MagicMock()), \
         patch.object(p, "_failover_timer", mock_failover_timer), \
         patch.object(p, "_elapsed_timer", mock_elapsed_timer):
        # CR-01/WR-03: simulate the queued slot delivery — pass the current
        # _preroll_seq so the new seq-stamp guard accepts this call. _start_preroll
        # bumped it to >= 1 via play() above; passing it here mirrors what the
        # streaming-thread callback emits at the real about-to-finish point.
        p._on_preroll_about_to_finish(p._preroll_seq)
    # Tracker.force_close called with outcome="preroll" (NOT "failover")
    # so analytics see this is a gapless handoff close, not a true failover.
    force_close_calls = mock_tracker.force_close.call_args_list
    assert force_close_calls, (
        "Phase 83 D-05 (UAT fix): tracker.force_close must run before "
        "tracker.bind_url (mirror of _try_next_stream:1060)."
    )
    force_close_arg = force_close_calls[0].args[0]
    assert force_close_arg == "preroll", (
        f"Phase 83 D-05 (UAT fix): force_close outcome token must be "
        f"'preroll' so analytics distinguish gapless handoff from true "
        f"failover; got {force_close_arg!r}"
    )
    # Tracker.bind_url called with the new stream URL (mirror of
    # _try_next_stream:1064-1068).
    bind_calls = mock_tracker.bind_url.call_args_list
    assert bind_calls, (
        "Phase 83 D-05 (UAT fix): tracker.bind_url must be called on the "
        "new stream URL after gapless handoff."
    )
    bind_kwargs = bind_calls[0].kwargs
    assert bind_kwargs.get("url") == s.url, (
        f"Phase 83 D-05 (UAT fix): tracker.bind_url must receive the "
        f"new stream's URL; got {bind_kwargs!r}"
    )
    # Failover-timer armed (mirror of _try_next_stream:1087).
    mock_failover_timer.start.assert_called_once()
    # The timer is armed with BUFFER_DURATION_S * 1000 ms (canonical value).
    from musicstreamer.constants import BUFFER_DURATION_S
    timer_arg = mock_failover_timer.start.call_args.args[0]
    assert timer_arg == BUFFER_DURATION_S * 1000, (
        f"Phase 83 D-05 (UAT fix): _failover_timer must be armed with "
        f"BUFFER_DURATION_S * 1000 = {BUFFER_DURATION_S * 1000}ms; got "
        f"{timer_arg}"
    )
    # Elapsed-timer seeding (mirror of _try_next_stream:1073-1077). The
    # checker WARNING called this out: without the seeding block, the
    # user-facing elapsed-time display freezes at 0 across the preroll→
    # stream handoff (analytics regression).
    mock_elapsed_timer.start.assert_called_once()
    assert p._elapsed_seconds == 0, (
        f"Phase 83 D-05 (UAT fix): _elapsed_seconds must reset to 0 at "
        f"the gapless handoff (mirror of _try_next_stream:1076); got "
        f"{p._elapsed_seconds}. Without this reset the elapsed-time "
        f"display freezes at the pre-handoff value."
    )
    # _is_first_attempt flipped to False AFTER the seeding block (mirror
    # of _try_next_stream:1078); a second handoff in the same Player
    # instance would not re-seed the timer.
    assert p._is_first_attempt is False, (
        "Phase 83 D-05 (UAT fix): _is_first_attempt must flip to False "
        "after the gapless handoff (mirror of _try_next_stream:1078)."
    )


# ---------------------------------------------------------------------------
# Phase 83 code-review CR-01 / WR-03 regression tests — preroll race guards.
# Documents the double-pop / stale-slot defenses added in response to the
# Phase 83 code review (.planning/.../83-REVIEW.md).
# ---------------------------------------------------------------------------


def test_cr01_preroll_bus_error_then_about_to_finish_does_not_double_pop(qtbot):
    """CR-01 Scenario 1: bus-error preroll recovery fires FIRST, then the
    queued about-to-finish slot arrives stale. The slot must no-op (NOT pop
    _streams_queue a second time, NOT replace the in-progress stream).

    Without the _preroll_seq guard, the slot would pop queue[0] = Y after
    _handle_gst_error_recovery already advanced to X, replacing X with Y
    mid-track. With the guard, the stale-seq check rejects the call.
    """
    p = _make_player_mock(qtbot)
    s0 = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    s1 = _make_stream_ph82(2, 2, "med", "http://stream.test/")
    station = _make_station_ph83(
        [s0, s1], prerolls=["https://somafm.com/p.m4a"], prerolls_fetched_at=1
    )
    with patch.object(p, "_set_uri"), patch.object(p, "_try_next_stream"):
        p.play(station)
    assert p._preroll_in_flight is True
    seq_at_emit = p._preroll_seq  # callback captured this value on streaming thread
    # Bus-error preroll recovery runs first (main-thread queued slot).
    with patch.object(p, "_try_next_stream") as mock_try_next, \
         patch.object(p, "_clear_recovery_guard"):
        p._handle_gst_error_recovery()
    assert p._preroll_in_flight is False
    assert mock_try_next.called  # advanced to s0
    # Seq bumped — the queued about-to-finish slot now arrives stale.
    assert p._preroll_seq != seq_at_emit, (
        "CR-01: _handle_gst_error_recovery preroll branch must bump _preroll_seq "
        "so the queued about-to-finish slot rejects its delivery."
    )
    # Snapshot queue + set_property state BEFORE the stale slot runs.
    queue_len_before = len(p._streams_queue)
    set_property_uri_calls_before = sum(
        1 for c in p._pipeline.set_property.call_args_list
        if c.args and c.args[0] == "uri"
    )
    # Now the queued about-to-finish slot delivers with the OLD seq.
    p._on_preroll_about_to_finish(seq_at_emit)
    # The stale slot must NOT pop queue and must NOT set_property('uri', ...).
    assert len(p._streams_queue) == queue_len_before, (
        "CR-01: stale about-to-finish slot must NOT pop _streams_queue after "
        "bus-error recovery already advanced. Without the seq guard, the "
        "slot would pop queue[0] and replace the in-progress stream."
    )
    set_property_uri_calls_after = sum(
        1 for c in p._pipeline.set_property.call_args_list
        if c.args and c.args[0] == "uri"
    )
    assert set_property_uri_calls_after == set_property_uri_calls_before, (
        "CR-01: stale about-to-finish slot must NOT call set_property('uri', "
        "...) — that would clobber the stream _handle_gst_error_recovery "
        "just started."
    )


def test_wr01_start_preroll_arms_failover_timer_watchdog(qtbot):
    """WR-01: _start_preroll arms self._failover_timer with
    BUFFER_DURATION_S * 1000 so a stuck/dead preroll URL falls through to
    the station's actual stream. Pre-Phase 83 _try_next_stream:1087 armed
    the same timer; the preroll path regressed this watchdog."""
    from musicstreamer.constants import BUFFER_DURATION_S
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station = _make_station_ph83(
        [s], prerolls=["https://somafm.com/p.m4a"], prerolls_fetched_at=1
    )
    mock_failover_timer = MagicMock()
    with patch.object(p, "_set_uri"), \
         patch.object(p, "_failover_timer", mock_failover_timer):
        p.play(station)
    assert p._preroll_in_flight is True
    mock_failover_timer.start.assert_called_once_with(BUFFER_DURATION_S * 1000), (
        "WR-01: _start_preroll must arm _failover_timer with "
        "BUFFER_DURATION_S * 1000 as the watchdog for stuck preroll URLs."
    )


def test_wr01_on_timeout_during_preroll_runs_cleanup_before_advance(qtbot):
    """WR-01: when _on_timeout fires while _preroll_in_flight is True, the
    handler-id and flag are cleared AND _preroll_seq is bumped BEFORE
    _try_next_stream runs (same cleanup contract as the bus-error preroll
    branch in _handle_gst_error_recovery — CR-01)."""
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station = _make_station_ph83(
        [s], prerolls=["https://somafm.com/p.m4a"], prerolls_fetched_at=1
    )
    with patch.object(p, "_set_uri"), patch.object(p, "_try_next_stream"):
        p.play(station)
    assert p._preroll_in_flight is True
    seq_before = p._preroll_seq
    handler_before = p._preroll_handler_id
    assert handler_before != 0
    with patch.object(p, "_try_next_stream") as mock_try_next:
        p._on_timeout()
    assert p._preroll_in_flight is False, (
        "WR-01: _on_timeout during preroll must clear _preroll_in_flight."
    )
    assert p._preroll_handler_id == 0, (
        "WR-01: _on_timeout during preroll must disconnect + zero handler-id."
    )
    assert p._preroll_seq == seq_before + 1, (
        "WR-01: _on_timeout during preroll must bump _preroll_seq to "
        "invalidate any in-flight about-to-finish slot (CR-01 contract)."
    )
    assert mock_try_next.called


def test_cr01_stale_slot_from_prior_play_rejected(qtbot):
    """WR-03: a queued about-to-finish slot from a PRIOR play()/preroll
    lifecycle must not act on the NEW station's queue. The slot's
    expected_seq stamp belongs to the dead preroll; the current _preroll_seq
    is newer (bumped by the second _start_preroll). The guard rejects."""
    p = _make_player_mock(qtbot)
    s = _make_stream_ph82(1, 1, "hi", "http://stream.test/")
    station_a = _make_station_ph83(
        [s], prerolls=["https://somafm.com/a.m4a"], prerolls_fetched_at=1
    )
    with patch.object(p, "_set_uri"), patch.object(p, "_try_next_stream"):
        p.play(station_a)
    stale_seq = p._preroll_seq  # streaming-thread callback would have captured this

    # Simulate stop() (clears state for a fresh play); see WR-02 fix.
    with patch.object(p, "_failover_timer", MagicMock()), \
         patch.object(p, "_elapsed_timer", MagicMock()):
        p.stop()
    # Second play with a different station — _start_preroll bumps _preroll_seq again.
    s2 = _make_stream_ph82(2, 2, "hi", "http://stream2.test/")
    station_b = _make_station_ph83(
        [s2],
        id_=2,
        name="Test Station B",
        prerolls=["https://somafm.com/b.m4a"],
        prerolls_fetched_at=1,
    )
    # Throttle window — set _last_preroll_played_at well in the past to allow preroll.
    p._last_preroll_played_at = None
    with patch.object(p, "_set_uri"), patch.object(p, "_try_next_stream"):
        p.play(station_b)
    fresh_seq = p._preroll_seq
    assert fresh_seq != stale_seq, (
        "WR-03: each _start_preroll must bump _preroll_seq so stale slots "
        "from prior lifecycles can be rejected."
    )
    queue_len_before = len(p._streams_queue)
    # The OLD streaming-thread callback finally delivers — main-thread slot
    # gets the stale seq from station_a's preroll.
    p._on_preroll_about_to_finish(stale_seq)
    # Must NOT pop station_b's queue.
    assert len(p._streams_queue) == queue_len_before, (
        "WR-03: stale about-to-finish slot from prior play() must NOT pop "
        "the new station's _streams_queue."
    )
