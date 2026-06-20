"""Phase 95: Player edit-invalidation + YouTube resolve-generation guard.

Covers the YT URL-change replay bug fix (D-01..D-05 + the in-flight YouTube
resolution race guard). After a station's stream URL is edited, the Player's
cached state (``_streams_queue`` / ``_current_stream`` / loaded URI / in-flight
YouTube resolution) must never serve the stale URL on the first play.

Validation matrix (see 95-VALIDATION.md / 95-RESEARCH.md):
  - V1  (D-01/D-03): playing-stream URL changed while playing -> play() re-issued.
  - V2  (D-02):      metadata-only edit on playing stream -> NO restart.
  - V3  (D-04):      non-playing sibling stream edited -> no restart, queue invalidated.
  - V4  (same-URL):  edit to identical URL -> no restart.
  - V5  (seq guard): late stale youtube_resolved delivery is ignored.
  - V6  (D-05):      station edited while NOT playing -> no restart, state cleared.
  - V10 (deleted):   playing stream deleted while playing -> play() re-issued on survivor.

Harness shape copied from tests/test_player_failover.py (Gst.ElementFactory.make
mocked, ``player._pipeline = MagicMock()``).
"""
from unittest.mock import MagicMock, patch

from musicstreamer.models import Station, StationStream
from musicstreamer.player import Gst, Player


# ---------------------------------------------------------------------------
# Harness (mirrors tests/test_player_failover.py:16-50)
# ---------------------------------------------------------------------------

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
    player._pipeline = MagicMock()
    return player


def make_stream(id_, position, quality, url="http://stream.test/"):
    return StationStream(
        id=id_,
        station_id=1,
        url=f"{url}{id_}",
        quality=quality,
        position=position,
    )


def make_station_with_streams(streams):
    return Station(
        id=1,
        name="Test Station",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=streams,
    )


def _simulate_playing(player, station, playing_stream):
    """Put the player into a 'currently playing station X on stream Y' state
    without touching a real pipeline."""
    player._current_station_id = station.id
    player._current_station_name = station.name
    player._current_stream = playing_stream
    player._streams_queue = [playing_stream]


# ---------------------------------------------------------------------------
# V1 (D-01/D-03): playing-stream URL changed while actively playing -> restart
# ---------------------------------------------------------------------------

def test_v1_playing_stream_url_changed_reissues_play(qtbot):
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://old/")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    new = StationStream(
        id=10, station_id=1, url="http://new/changed", quality="hi", position=1
    )
    updated = make_station_with_streams([new])

    with patch.object(p, "play", MagicMock()) as play_spy:
        p.invalidate_for_edit(updated, is_playing=True)

    play_spy.assert_called_once()
    # play() re-issued for the UPDATED station (carries the NEW url).
    assert play_spy.call_args.args[0] is updated
    assert play_spy.call_args.args[0].streams[0].url == "http://new/changed"


# ---------------------------------------------------------------------------
# V2 (D-02): metadata-only edit on playing stream -> NO restart, audio untouched
# ---------------------------------------------------------------------------

def test_v2_metadata_only_edit_does_not_restart(qtbot):
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://same/")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)
    queue_before = p._streams_queue
    current_before = p._current_stream

    # Same URL, changed quality (metadata-only).
    meta = StationStream(
        id=10, station_id=1, url=old.url, quality="low", position=1
    )
    updated = make_station_with_streams([meta])

    with patch.object(p, "play", MagicMock()) as play_spy:
        p.invalidate_for_edit(updated, is_playing=True)

    play_spy.assert_not_called()
    p._pipeline.set_state.assert_not_called()
    # Queue / current_stream untouched — audio continues.
    assert p._streams_queue is queue_before
    assert p._current_stream is current_before


# ---------------------------------------------------------------------------
# V3 (D-04): non-playing sibling stream edited -> no restart, queue invalidated
# ---------------------------------------------------------------------------

def test_v3_non_playing_sibling_edited_invalidates_queue_no_restart(qtbot):
    p = make_player(qtbot)
    playing = make_stream(10, position=1, quality="hi", url="http://playing/")
    sibling = make_stream(11, position=2, quality="low", url="http://sib/")
    station = make_station_with_streams([playing, sibling])
    p._current_station_id = station.id
    p._current_stream = playing
    p._streams_queue = [playing, sibling]
    seq_before = p._youtube_resolve_seq

    # Playing stream unchanged; sibling URL changed.
    new_sibling = StationStream(
        id=11, station_id=1, url="http://sib/CHANGED", quality="low", position=2
    )
    updated = make_station_with_streams([playing, new_sibling])

    with patch.object(p, "play", MagicMock()) as play_spy:
        p.invalidate_for_edit(updated, is_playing=True)

    play_spy.assert_not_called()
    p._pipeline.set_state.assert_not_called()
    # Queue invalidated so later failover rebuilds from fresh URLs.
    assert p._streams_queue == []
    # Resolve generation bumped (in-flight YT resolutions no-op).
    assert p._youtube_resolve_seq > seq_before


# ---------------------------------------------------------------------------
# V4 (same-URL no-op): edit playing stream URL to identical value -> no restart
# ---------------------------------------------------------------------------

def test_v4_same_url_is_noop(qtbot):
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://identical/")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    # Identical URL (with incidental surrounding whitespace -> .strip() equal).
    same = StationStream(
        id=10, station_id=1, url="  " + old.url + "  ", quality="hi", position=1
    )
    updated = make_station_with_streams([same])

    with patch.object(p, "play", MagicMock()) as play_spy:
        p.invalidate_for_edit(updated, is_playing=True)

    play_spy.assert_not_called()
    p._pipeline.set_state.assert_not_called()


# ---------------------------------------------------------------------------
# V5 (race / seq guard): a stale youtube_resolved delivery must NOT clobber URI
# ---------------------------------------------------------------------------

def test_v5_stale_youtube_resolution_is_ignored(qtbot):
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/old")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    # Capture the seq an in-flight resolution would have stamped BEFORE the edit.
    stale_seq = p._youtube_resolve_seq

    new = StationStream(
        id=10, station_id=1, url="http://yt/new", quality="hi", position=1
    )
    updated = make_station_with_streams([new])

    with patch.object(p, "play", MagicMock()):
        # The edit restarts (URL changed) and bumps the resolve generation.
        p.invalidate_for_edit(updated, is_playing=True)

    assert p._youtube_resolve_seq > stale_seq

    with patch.object(p, "_set_uri", MagicMock()) as set_uri_spy:
        # Stale delivery (captured the pre-edit seq) must be ignored.
        p._on_youtube_resolved("http://yt/OLD_RESOLVED", False, stale_seq)
        for c in set_uri_spy.call_args_list:
            assert c.args[0] != "http://yt/OLD_RESOLVED"
        set_uri_spy.assert_not_called()

        # A fresh delivery carrying the CURRENT seq IS honored.
        p._on_youtube_resolved("http://yt/FRESH", False, p._youtube_resolve_seq)
        set_uri_spy.assert_called_once_with("http://yt/FRESH")


# ---------------------------------------------------------------------------
# V6 (D-05): station edited while NOT playing -> no restart, state cleared fresh
# ---------------------------------------------------------------------------

def test_v6_edit_while_not_playing_clears_state_no_restart(qtbot):
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://idle/old")
    station = make_station_with_streams([old])
    # The player last loaded this station, but is now stopped/paused
    # (_current_station_id survives stop()/pause()).
    p._current_station_id = station.id
    p._current_stream = old
    p._streams_queue = [old]

    new = StationStream(
        id=10, station_id=1, url="http://idle/new", quality="hi", position=1
    )
    updated = make_station_with_streams([new])

    with patch.object(p, "play", MagicMock()) as play_spy:
        p.invalidate_for_edit(updated, is_playing=False)

    play_spy.assert_not_called()
    # Next play() must rebuild fresh — no stale queue/current carried over.
    assert p._streams_queue == []
    assert p._current_stream is None


# ---------------------------------------------------------------------------
# V10 (deleted playing stream): survivor picked; all-deleted is graceful
# ---------------------------------------------------------------------------

def test_v10_deleted_playing_stream_reissues_play_on_survivor(qtbot):
    p = make_player(qtbot)
    playing = make_stream(10, position=1, quality="hi", url="http://gone/")
    sibling = make_stream(11, position=2, quality="low", url="http://survivor/")
    station = make_station_with_streams([playing, sibling])
    p._current_station_id = station.id
    p._current_stream = playing
    p._streams_queue = [playing, sibling]

    # Playing stream id=10 deleted; sibling id=11 remains.
    updated = make_station_with_streams([sibling])

    with patch.object(p, "play", MagicMock()) as play_spy:
        p.invalidate_for_edit(updated, is_playing=True)

    play_spy.assert_called_once()
    assert play_spy.call_args.args[0] is updated


def test_v10_all_streams_deleted_is_graceful(qtbot):
    p = make_player(qtbot)
    playing = make_stream(10, position=1, quality="hi", url="http://gone/")
    station = make_station_with_streams([playing])
    p._current_station_id = station.id
    p._current_stream = playing
    p._streams_queue = [playing]

    updated = make_station_with_streams([])  # every stream deleted

    # play()'s no-streams guard handles this — invalidate must not crash.
    with patch.object(p, "play", MagicMock()) as play_spy:
        p.invalidate_for_edit(updated, is_playing=True)

    # Re-issued play() (which itself emits "(no streams configured)") — no crash.
    play_spy.assert_called_once()
    assert play_spy.call_args.args[0] is updated


# ---------------------------------------------------------------------------
# D-05 for a DIFFERENT station the player never loaded -> seq bump only, no-op
# ---------------------------------------------------------------------------

def test_unrelated_station_edit_is_noop_beyond_seq_bump(qtbot):
    p = make_player(qtbot)
    playing = make_stream(10, position=1, quality="hi", url="http://current/")
    station = make_station_with_streams([playing])
    _simulate_playing(p, station, playing)
    seq_before = p._youtube_resolve_seq

    other = Station(
        id=999,
        name="Other",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=[make_stream(50, position=1, quality="hi", url="http://other/")],
    )

    with patch.object(p, "play", MagicMock()) as play_spy:
        p.invalidate_for_edit(other, is_playing=True)

    play_spy.assert_not_called()
    p._pipeline.set_state.assert_not_called()
    # The currently-playing station's state is untouched.
    assert p._current_stream is playing
    assert p._streams_queue == [playing]
    # Generation still bumped (harmless; any unrelated in-flight resolve no-ops).
    assert p._youtube_resolve_seq > seq_before


# ---------------------------------------------------------------------------
# V11 (Phase 95-02 gap-closure): stale pre-restart recovery MUST be suppressed
# ---------------------------------------------------------------------------

def test_v11_stale_recovery_suppressed_after_edit_restart(qtbot):
    """A queued _error_recovery_requested from BEFORE an edit-restart must no-op.

    Reproduces the race: old YT stream exhausts (error posted to bus), user
    edits the URL (D-01 restart via play()), then the queued stale recovery
    runs on the main loop with an empty queue — it must NOT emit failover(None).

    The _recovery_seq guard (Phase 95-02) is the fix: the stale delivery
    carries a stamp captured before the restart, which is < the current
    _recovery_seq after play() bumped it, so the handler early-returns.

    The EXPLICIT stale_recovery_seq argument (not the -1 default) is essential:
    it exercises the real checked branch of the staleness guard.
    """
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/old")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    # Capture the stamp a bus-thread error would have carried BEFORE the edit.
    stale_recovery_seq = p._recovery_seq

    # Emulate the edit-restart: bump _recovery_seq (as play() entry will do),
    # then set the post-restart state (empty queue, guard cleared — exactly
    # what play() + _play_youtube leave during async YT resolution).
    p._recovery_seq += 1  # play() entry bump supersedes the stale delivery
    p._streams_queue = []
    p._recovery_in_flight = False

    # Deliver the stale recovery (explicit stamp < current _recovery_seq).
    # Must NOT call _try_next_stream() — the queue is empty and would emit
    # failover(None) → "Stream exhausted" toast (the spurious toast gap).
    with patch.object(p, "_try_next_stream", MagicMock()) as mock_try_next:
        p._handle_gst_error_recovery(stale_recovery_seq)
        mock_try_next.assert_not_called()


# ---------------------------------------------------------------------------
# V12 (Phase 95-02 hard constraint): GENUINE current-gen exhaustion STILL toasts
# ---------------------------------------------------------------------------

def test_v12_genuine_current_gen_exhaustion_still_toasts(qtbot):
    """A recovery carrying the CURRENT _recovery_seq must still reach
    _try_next_stream() and emit failover(None) on an empty queue, when no
    YouTube resolve is in flight (genuine exhaustion, not a transient race).

    This is the hard constraint: the guard must suppress ONLY stale (pre-restart)
    recoveries, never a genuine current-generation exhaustion whose error was
    posted AFTER the latest restart AND no async YouTube resolve is pending.

    The EXPLICIT current-seq argument (not the -1 default) is required so this
    genuinely exercises the pass-through branch of the staleness check rather
    than the sentinel bypass.

    Reconciled for Phase 95-03: explicitly sets _youtube_resolve_in_flight=False
    (genuine exhaustion — no resolve in flight) so the assertions still hold under
    the new in-flight gate. When a resolve IS in flight, V14/V15 cover that case.
    """
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/old")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    # Empty queue + guard clear + NO resolve in flight: genuine exhaustion state.
    p._streams_queue = []
    p._recovery_in_flight = False
    p._youtube_resolve_in_flight = False  # Phase 95-03: explicit — genuine exhaustion

    # Part A: explicit current-seq MUST call _try_next_stream (pass-through).
    with patch.object(p, "_try_next_stream", MagicMock()) as mock_try_next:
        p._handle_gst_error_recovery(p._recovery_seq)
        mock_try_next.assert_called_once()

    # Part B: explicit current-seq on an empty queue MUST emit failover(None).
    p._recovery_in_flight = False  # reset after Part A
    p._youtube_resolve_in_flight = False  # ensure gate still clear for Part B
    with qtbot.waitSignal(p.failover, timeout=1000) as blocker:
        p._handle_gst_error_recovery(p._recovery_seq)
    assert blocker.args == [None]


# ---------------------------------------------------------------------------
# V13 (Phase 95-02): metadata-only edit does NOT suppress a legitimate recovery
# ---------------------------------------------------------------------------

def test_v13_metadata_only_edit_leaves_recovery_unaffected(qtbot):
    """A metadata-only edit (URL unchanged, quality changed) must NOT bump
    _recovery_seq in a way that rejects a legitimate current-generation recovery.

    D-02 (no restart): invalidate_for_edit returns without calling play(),
    so _recovery_seq must stay at the same value and a genuine same-session
    recovery (explicit current-seq stamp) still advances the queue normally.

    The EXPLICIT current-seq argument exercises the real checked branch.
    """
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/same")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    recovery_seq_before = p._recovery_seq

    # Metadata-only edit: same URL, quality changed -> D-02 path (no restart).
    meta = StationStream(
        id=10, station_id=1, url=old.url, quality="low", position=1
    )
    updated = make_station_with_streams([meta])

    with patch.object(p, "play", MagicMock()) as play_spy:
        p.invalidate_for_edit(updated, is_playing=True)

    play_spy.assert_not_called()  # D-02: no restart for metadata-only edit

    # _recovery_seq must not have been bumped by the metadata-only path
    # (the D-02 branch does NOT call play(), so _recovery_seq is unchanged).
    assert p._recovery_seq == recovery_seq_before

    # A legitimate current-generation recovery with an explicit current-seq
    # stamp must still advance normally (non-empty queue scenario).
    sibling = make_stream(11, position=2, quality="low", url="http://yt/fallback")
    p._streams_queue = [sibling]
    p._recovery_in_flight = False

    with patch.object(p, "_set_uri", MagicMock()) as set_uri_spy:
        p._handle_gst_error_recovery(p._recovery_seq)
        # The recovery should have advanced to the sibling stream.
        set_uri_spy.assert_called_once()


# ---------------------------------------------------------------------------
# V14 (Phase 95-03): resolve-in-flight gate suppresses transient false exhaustion
# ---------------------------------------------------------------------------

def test_v14_resolve_in_flight_gates_false_exhaustion(qtbot):
    """While a YouTube resolve is in flight, neither _handle_gst_error_recovery
    nor a direct _try_next_stream() call may emit failover(None).

    Reproduces the residual Phase 95 UAT bug: the old stream's bus error arrives
    AFTER the edit-restart (carrying the CURRENT _recovery_seq), so the 95-02
    _recovery_seq guard cannot block it. The new 95-03 _youtube_resolve_in_flight
    gate is the fix: the pending async resolve owns the next state transition.

    Part (a): _handle_gst_error_recovery with current-gen stamp, gate set ->
              _try_next_stream NOT called (gate early-returns).
    Part (b): direct _try_next_stream() call, gate set, empty queue ->
              failover.emit(None) NOT emitted (the gate short-circuits before
              the failover line).
    """
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/old")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    # Post-restart state: empty queue, guard clear, but resolve IS in flight.
    p._streams_queue = []
    p._recovery_in_flight = False
    p._youtube_resolve_in_flight = True  # Phase 95-03: resolve pending

    # Part (a): current-gen recovery must NOT advance to _try_next_stream.
    with patch.object(p, "_try_next_stream", MagicMock()) as mock_try_next:
        p._handle_gst_error_recovery(p._recovery_seq)
        mock_try_next.assert_not_called()  # gate must short-circuit before advance

    # Part (b): direct _try_next_stream() with gate set must NOT emit failover(None).
    p._youtube_resolve_in_flight = True  # still in flight for Part (b)
    failover_emitted = []

    def _record_failover(station_or_none):
        failover_emitted.append(station_or_none)

    p.failover.connect(_record_failover)
    p._try_next_stream()
    p.failover.disconnect(_record_failover)
    assert failover_emitted == [], (
        f"failover.emit(None) fired while resolve in flight: {failover_emitted}"
    )


# ---------------------------------------------------------------------------
# V15 (Phase 95-03): genuine exhaustion still toasts when no resolve in flight
# ---------------------------------------------------------------------------

def test_v15_genuine_exhaustion_toasts_when_no_resolve_in_flight(qtbot):
    """When the resolve-in-flight gate is clear AND the queue is empty, a
    current-generation error MUST still emit failover(None) exactly once.

    Hard constraint (D-03): the in-flight gate must not over-suppress. An
    all-streams-failed exhaustion must still surface as "Stream exhausted".

    Uses qtbot.waitSignal for deterministic signal assertion (mirrors V12 Part B).
    """
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/old")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    # Post-restart state: empty queue, guard clear, resolve settled (gate False).
    p._streams_queue = []
    p._recovery_in_flight = False
    p._youtube_resolve_in_flight = False  # gate clear -> genuine exhaustion path

    # Current-gen error recovery -> _try_next_stream -> failover(None) exactly once.
    with qtbot.waitSignal(p.failover, timeout=1000) as blocker:
        p._handle_gst_error_recovery(p._recovery_seq)
    assert blocker.args == [None], (
        f"Expected failover(None), got: {blocker.args}"
    )


# ---------------------------------------------------------------------------
# V16 (Phase 95-03): gate lifecycle — set on spawn, seq-matched clear, stale no-ops
# ---------------------------------------------------------------------------

def test_v16_gate_cleared_by_current_gen_resolved_success(qtbot):
    """_on_youtube_resolved with the CURRENT generation clears the in-flight gate
    (current generation settled — success path)."""
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/old")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    p._youtube_resolve_in_flight = True  # gate set as if _play_youtube was called

    # Patch pipeline-touching helpers so no real GStreamer calls occur.
    with patch.object(p, "_set_uri", MagicMock()), \
         patch.object(p, "_failover_timer", MagicMock()):
        # Deliver current-generation success.
        p._on_youtube_resolved("http://yt/RESOLVED", False, p._youtube_resolve_seq)

    assert p._youtube_resolve_in_flight is False, (
        "Gate must be cleared by a current-generation _on_youtube_resolved"
    )


def test_v16_gate_not_cleared_by_stale_resolved_success(qtbot):
    """_on_youtube_resolved with a STALE generation must NOT clear the in-flight gate
    and must NOT call _set_uri (re-uses the 95-01 V5 staleness idiom)."""
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/old")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    # Capture a stale seq, then bump the current generation (simulating an edit).
    stale_seq = p._youtube_resolve_seq
    p._youtube_resolve_seq += 1  # new generation started

    p._youtube_resolve_in_flight = True  # fresh gate set for the new generation

    with patch.object(p, "_set_uri", MagicMock()) as set_uri_spy:
        # Deliver a stale resolution (old generation).
        p._on_youtube_resolved("http://yt/STALE", False, stale_seq)
        set_uri_spy.assert_not_called()  # stale -> ignored, _set_uri NOT called

    assert p._youtube_resolve_in_flight is True, (
        "Gate must NOT be cleared by a stale (old-generation) _on_youtube_resolved"
    )


def test_v16_gate_cleared_by_current_gen_resolution_failed(qtbot):
    """_on_youtube_resolution_failed for the CURRENT generation clears the gate
    (failure path) AND allows _try_next_stream to run (legitimate advance/exhaust).

    Phase 95-04: updated to pass the CARRIED current seq to the handler, mirroring
    how _on_youtube_resolved receives its seq stamp from the Signal payload.
    The no-arg form (seq defaults to -1) must ALSO pass the guard — assert both.
    """
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/old")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    p._streams_queue = []  # empty -> _try_next_stream will exhaust to failover(None)
    p._youtube_resolve_in_flight = True  # gate set as if resolve was pending

    # Deliver current-generation failure WITH the carried current seq.
    # After the gate clears, _try_next_stream -> failover(None) (legitimate exhaust).
    with qtbot.waitSignal(p.failover, timeout=1000) as blocker:
        p._on_youtube_resolution_failed("timed out", p._youtube_resolve_seq)

    assert p._youtube_resolve_in_flight is False, (
        "Gate must be cleared by a current-generation _on_youtube_resolution_failed"
    )
    assert blocker.args == [None], (
        f"Expected failover(None) after current-gen failure, got: {blocker.args}"
    )

    # Also verify the no-arg form (seq=-1 default) still passes the guard.
    p._streams_queue = []
    p._youtube_resolve_in_flight = True
    with qtbot.waitSignal(p.failover, timeout=1000) as blocker2:
        p._on_youtube_resolution_failed("timed out via no-arg")

    assert p._youtube_resolve_in_flight is False, (
        "Gate must be cleared by no-arg _on_youtube_resolution_failed (seq=-1 default)"
    )
    assert blocker2.args == [None]


def test_v16_stale_resolution_failed_does_not_clear_gate_or_advance(qtbot):
    """A STALE (old-generation) _on_youtube_resolution_failed delivery must NOT
    clear the in-flight gate and must NOT call _try_next_stream.

    Phase 95-04 reconciliation: drives the REAL _play_youtube arming path
    (with threading.Thread patched so no real yt_dlp runs) so the test exercises
    the same state production path as real code. The old seq is delivered as a
    CARRIED argument (Signal arity: str, int), not via the instance attribute.

    This guards against a race where the old generation's failure callback arrives
    after the new generation's resolve has already been spawned — the stale failure
    must not declare exhaustion on the new generation's transiently-empty queue.
    """
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/old")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    # Arm the gate via the REAL _play_youtube path (patched spawn — no real yt_dlp).
    with patch("musicstreamer.player.threading.Thread"):
        p._play_youtube("http://yt/station-a")
    stale_seq = p._youtube_resolve_seq  # capture the OLD generation's seq

    # Start a new generation (simulating an edit-restart or a second _play_youtube).
    with patch("musicstreamer.player.threading.Thread"):
        p._play_youtube("http://yt/station-a-v2")
    # Now _youtube_resolve_seq > stale_seq and the fresh gate is set.

    p._streams_queue = []  # empty — stale failure must NOT exhaust this

    with patch.object(p, "_try_next_stream", MagicMock()) as mock_try_next:
        # Deliver the OLD generation's failure with the OLD carried seq.
        p._on_youtube_resolution_failed("old stream ended", stale_seq)
        mock_try_next.assert_not_called()  # stale failure must NOT advance queue

    assert p._youtube_resolve_in_flight is True, (
        "Gate must NOT be cleared by a stale _on_youtube_resolution_failed"
    )


# ---------------------------------------------------------------------------
# V17 (Phase 95-04 CR-01 leak regression): edit-to-direct clears the gate
# ---------------------------------------------------------------------------

def test_v17_edit_to_direct_url_clears_gate_and_stale_failure_rejected(qtbot):
    """CR-01 LEAK regression: editing a playing YouTube station to a non-YouTube/
    direct URL mid-resolve must clear the gate (_set_uri is the direct funnel).
    The old YouTube worker's stale failure must be rejected (carried seq mismatch),
    and a LATER genuine exhaustion must still fire failover(None).

    Scenario:
      1. Arm gate for generation N via _play_youtube (patched spawn).
      2. Simulate edit-to-direct restart: bump _youtube_resolve_seq (as play() does)
         + call _set_uri("http://direct/stream") (the branch the restart takes).
      3. Assert gate is now False (cleared by _set_uri).
      4. Deliver OLD YouTube worker's failure with stale_seq: assert it is rejected
         (gate stays False, _try_next_stream NOT called).
      5. With gate clear and empty queue, drive genuine exhaustion via
         _handle_gst_error_recovery(p._recovery_seq) -> assert failover(None) fires
         exactly once.
    """
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/old")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    # Step 1: arm gate for generation N via real _play_youtube (patched thread).
    with patch("musicstreamer.player.threading.Thread"):
        p._play_youtube("http://yt/station-a")
    stale_seq = p._youtube_resolve_seq  # generation N

    assert p._youtube_resolve_in_flight is True, "Gate must be armed by _play_youtube"

    # Step 2: simulate edit-to-direct restart (as play() + _try_next_stream/_set_uri does).
    # play() bumps _youtube_resolve_seq (Phase 95-04 fix).
    p._youtube_resolve_seq += 1  # simulate the play() bump
    # _set_uri is the direct/non-YouTube URI funnel — must clear the gate.
    with patch.object(p, "_arm_caps_watch_for_current_stream"):
        p._set_uri("http://direct/stream")

    # Step 3: gate must now be False (cleared by _set_uri on the direct restart path).
    assert p._youtube_resolve_in_flight is False, (
        "Gate must be cleared by _set_uri (direct/non-YouTube restart path)"
    )

    # Step 4: deliver OLD YouTube worker's stale failure (old generation N seq).
    p._streams_queue = []
    p._recovery_in_flight = False
    with patch.object(p, "_try_next_stream", MagicMock()) as mock_try_next:
        p._on_youtube_resolution_failed("stream ended", stale_seq)
        mock_try_next.assert_not_called()  # stale failure must NOT advance queue

    assert p._youtube_resolve_in_flight is False, (
        "Stale failure must not re-strand the gate"
    )

    # Step 5: genuine exhaustion with gate clear must still fire failover(None) once.
    failover_emitted = []

    def _record_failover(station_or_none):
        failover_emitted.append(station_or_none)

    p.failover.connect(_record_failover)
    p._handle_gst_error_recovery(p._recovery_seq)
    p.failover.disconnect(_record_failover)

    assert failover_emitted == [None], (
        f"Genuine exhaustion must still emit failover(None), got: {failover_emitted}"
    )


# ---------------------------------------------------------------------------
# V18 (Phase 95-04 CR-01 spurious-exhaustion regression): same-gen A->B no emit
# ---------------------------------------------------------------------------

def test_v18_same_gen_station_switch_stale_failure_rejected_no_spurious_exhaustion(qtbot):
    """CR-01 SPURIOUS-EXHAUSTION regression: a rapid YouTube A->B station switch
    (plain play(), no edit) must not emit a spurious failover(None) 'Stream
    exhausted' while B is still resolving.

    Scenario:
      1. Arm gate for A via _play_youtube (patched spawn), capture seq_a.
      2. Simulate A->B switch via play() semantics: bump _youtube_resolve_seq (the
         new play() behavior) + re-arm for B via _play_youtube (patched spawn).
      3. With B's queue transiently empty, deliver A's LATE failure carrying seq_a.
      4. Assert: B's gate stays True AND NO failover(None) emitted.
    """
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/a")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    # Step 1: arm gate for A via real _play_youtube (patched thread).
    with patch("musicstreamer.player.threading.Thread"):
        p._play_youtube("http://yt/station-a")
    seq_a = p._youtube_resolve_seq  # A's generation

    # Step 2: simulate A->B switch with play() semantics.
    # play() bumps _youtube_resolve_seq (Phase 95-04 fix that was missing in 95-03).
    p._youtube_resolve_seq += 1  # simulate the new play() bump
    p._streams_queue = []         # queue is transiently empty during B's resolve
    with patch("musicstreamer.player.threading.Thread"):
        p._play_youtube("http://yt/station-b")
    # Now _youtube_resolve_seq > seq_a and B's gate is True.

    assert p._youtube_resolve_in_flight is True, "Gate must be armed for B"

    # Step 3/4: deliver A's late failure with A's seq_a — must be rejected as stale.
    failover_emitted = []

    def _record_failover(station_or_none):
        failover_emitted.append(station_or_none)

    p.failover.connect(_record_failover)
    p._on_youtube_resolution_failed("A stream ended", seq_a)
    p.failover.disconnect(_record_failover)

    assert failover_emitted == [], (
        f"Stale A failure must NOT emit failover(None) while B resolves: {failover_emitted}"
    )
    assert p._youtube_resolve_in_flight is True, (
        "B's gate must stay True after a stale A failure delivery"
    )


# ---------------------------------------------------------------------------
# V19 (Phase 95-04): stop() clears a stranded gate AND invalidates in-flight worker
# ---------------------------------------------------------------------------

def test_v19_stop_clears_stranded_gate_and_invalidates_in_flight_worker(qtbot):
    """stop() must clear a stranded in-flight gate AND invalidate an in-flight
    YouTube worker so its late failure delivery emits NO spurious failover(None).

    Part A (stranded gate): set _youtube_resolve_in_flight = True, call stop(),
    assert gate is False.

    Part B (no spurious post-stop exhaustion): arm a worker via _play_youtube
    (patched spawn), capture seq_a, call stop(), then deliver the worker's LATE
    failure carrying seq_a; assert NO failover(None) is emitted (the late failure
    is rejected as stale because stop() bumped _youtube_resolve_seq).
    """
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/old")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    # Part A: stranded gate cleared by stop().
    p._youtube_resolve_in_flight = True  # strand the gate manually
    p.stop()
    assert p._youtube_resolve_in_flight is False, (
        "stop() must clear a stranded _youtube_resolve_in_flight gate"
    )

    # Part B: no spurious post-stop exhaustion from an in-flight worker's late failure.
    # Re-arm for a fresh test leg (stop() left a clean slate).
    with patch("musicstreamer.player.threading.Thread"):
        p._play_youtube("http://yt/station-a")
    seq_a = p._youtube_resolve_seq  # worker's generation stamp

    p.stop()  # stop() bumps _youtube_resolve_seq so seq_a is now stale

    # Deliver worker's late failure with the OLD seq_a.
    failover_emitted = []

    def _record_failover(station_or_none):
        failover_emitted.append(station_or_none)

    p.failover.connect(_record_failover)
    p._on_youtube_resolution_failed("ended", seq_a)
    p.failover.disconnect(_record_failover)

    assert failover_emitted == [], (
        f"Late post-stop failure must NOT emit failover(None): {failover_emitted}"
    )
