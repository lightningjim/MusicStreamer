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
