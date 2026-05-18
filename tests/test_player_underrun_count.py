"""Tests for Phase 78 / BUG-09 Commit A — Player underrun cycle counter + Signal.

Scope:
  - Counter init: ``Player._underrun_event_count`` starts at 0 (B-78A-07 part A).
  - Counter increment: each ``_on_underrun_cycle_closed`` call increments by 1
    (B-78A-07 part B).
  - Outcome-independence: counter increments for EVERY outcome
    (``recovered`` / ``failover`` / ``stop`` / ``pause`` / ``shutdown``) — mirrors
    the file-sink one-line-per-cycle semantics (B-78A-08, CONTEXT.md <specifics>).
  - Signal emission: ``Player.underrun_count_changed`` emits the new count value
    on every cycle close (B-78A-09).

This file exercises the REAL ``Player`` with a mocked GStreamer pipeline — the
shared Player test double is intentionally NOT used here; its Signal mirror
is covered by the INFRA-01 source-grep drift-guard (B-78A-10).  Per
PATTERNS.md §S-7 (codebase convention), the ``make_player`` helper is
duplicated verbatim from ``tests/test_player_underrun.py:16-31`` rather than
extracted to ``conftest.py``.
"""
from unittest.mock import MagicMock, patch

import pytest

from musicstreamer.player import Player, _CycleClose


def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out.

    Verbatim duplicate of tests/test_player_underrun.py:16-31 (per
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


def _make_record(outcome: str = "recovered") -> _CycleClose:
    """Build a minimal _CycleClose record for the slot-driven assertions.

    Field order matches the _CycleClose dataclass declaration order from
    musicstreamer/player.py:96-112 (start_ts, end_ts, duration_ms, min_percent,
    station_id, station_name, url, outcome, cause_hint).
    """
    return _CycleClose(
        start_ts=10.0,
        end_ts=11.5,
        duration_ms=1500,
        min_percent=60,
        station_id=7,
        station_name="Test",
        url="http://x/",
        outcome=outcome,
        cause_hint="unknown",
    )


def test_count_starts_at_zero(qtbot):
    """B-78A-07 part A: Player._underrun_event_count initialized to 0 in __init__."""
    player = make_player(qtbot)
    assert player._underrun_event_count == 0


def test_count_increments_per_close(qtbot):
    """B-78A-07 part B: each _on_underrun_cycle_closed call increments the counter by 1."""
    player = make_player(qtbot)
    rec = _make_record()
    player._on_underrun_cycle_closed(rec)
    assert player._underrun_event_count == 1
    player._on_underrun_cycle_closed(rec)
    assert player._underrun_event_count == 2


@pytest.mark.parametrize(
    "outcome",
    ["recovered", "failover", "stop", "pause", "shutdown"],
)
def test_count_increments_for_all_outcomes(qtbot, outcome):
    """B-78A-08: counter increments on EVERY outcome (CONTEXT.md <specifics>).

    Mirrors the file-sink one-line-per-cycle semantics — the cycle-close slot
    fires once per cycle regardless of how the cycle terminated.
    """
    player = make_player(qtbot)
    rec = _make_record(outcome=outcome)
    player._on_underrun_cycle_closed(rec)
    assert player._underrun_event_count == 1


def test_signal_emits_with_count_value(qtbot):
    """B-78A-09: underrun_count_changed emits the post-increment count value.

    Both emitter (Player._on_underrun_cycle_closed slot, main thread — receiving
    end of the queued _underrun_cycle_closed connection) and the in-test
    receiver (list.append) are on the main thread, so DirectConnection is
    correct.  The qtbot.wait(50) calls are defensive against test-runner
    ordering on slow CI; they are not semantically required.
    """
    player = make_player(qtbot)
    rec = _make_record()

    received: list[int] = []
    player.underrun_count_changed.connect(received.append)

    player._on_underrun_cycle_closed(rec)
    qtbot.wait(50)
    assert received == [1]

    player._on_underrun_cycle_closed(rec)
    qtbot.wait(50)
    assert received == [1, 2]
