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
    _try_next_stream() and emit failover(None) on an empty queue.

    This is the hard constraint: the guard must suppress ONLY stale (pre-restart)
    recoveries, never a genuine current-generation exhaustion whose error was
    posted AFTER the latest restart.

    The EXPLICIT current-seq argument (not the -1 default) is required so this
    genuinely exercises the pass-through branch of the staleness check rather
    than the sentinel bypass.
    """
    p = make_player(qtbot)
    old = make_stream(10, position=1, quality="hi", url="http://yt/old")
    station = make_station_with_streams([old])
    _simulate_playing(p, station, old)

    # Empty queue + guard clear: post-restart state before resolution arrives.
    p._streams_queue = []
    p._recovery_in_flight = False

    # Part A: explicit current-seq MUST call _try_next_stream (pass-through).
    with patch.object(p, "_try_next_stream", MagicMock()) as mock_try_next:
        p._handle_gst_error_recovery(p._recovery_seq)
        mock_try_next.assert_called_once()

    # Part B: explicit current-seq on an empty queue MUST emit failover(None).
    p._recovery_in_flight = False  # reset after Part A
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
