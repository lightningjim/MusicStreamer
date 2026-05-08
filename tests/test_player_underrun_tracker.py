"""Tests for _BufferUnderrunTracker pure-logic state machine — Phase 62 / BUG-09.

Mirrors tests/test_stream_ordering.py shape: pure-logic helper class,
no qtbot fixture. The tracker has an injectable clock for deterministic
duration_ms assertions. RED on Wave 0; turns GREEN when Plan 01 lands the
class in musicstreamer/player.py.
"""
from __future__ import annotations

from musicstreamer.player import _BufferUnderrunTracker  # RED until Plan 01


def test_unarmed_initial_fill_does_not_open_cycle():
    """D-04 unarmed gate: percent < 100 while unarmed must NOT open a cycle."""
    clock = iter([10.0, 11.0, 12.0])
    t = _BufferUnderrunTracker(clock=lambda: next(clock))
    t.bind_url(1, "Test", "http://x/")
    assert t.observe(0) is None
    assert t.observe(50) is None
    assert t.observe(100) is None    # arms here


def test_armed_drop_opens_cycle():
    """D-01 / D-04: percent < 100 post-arming opens a cycle (returns 'OPENED')."""
    times = [10.0, 11.0]
    it = iter(times)
    t = _BufferUnderrunTracker(clock=lambda: next(it))
    t.bind_url(1, "Test", "http://x/")
    assert t.observe(100) is None             # arms
    assert t.observe(80) == "OPENED"           # opens cycle


def test_first_100_arms_tracker():
    """D-04: first percent == 100 per URL flips arm to True (mirror of Phase 47.1 D-14)."""
    t = _BufferUnderrunTracker(clock=iter([10.0, 11.0]).__next__)
    t.bind_url(1, "Test", "http://x/")
    # Before arming, percent < 100 returns None
    assert t.observe(70) is None
    # First 100 arms — but does NOT itself return "OPENED"
    assert t.observe(100) is None


def test_armed_drop_then_recover_returns_close_record():
    """D-02: natural close returns _CycleClose with outcome='recovered',
    duration_ms, min_percent, full station context, cause_hint='unknown'."""
    times = [10.0, 11.0, 11.5, 13.0]   # [arm, open, mid-cycle, close]
    it = iter(times)
    t = _BufferUnderrunTracker(clock=lambda: next(it))
    t.bind_url(7, "DI.fm Ambient", "http://prem2.di.fm/ambient")
    t.observe(100)                     # arms
    assert t.observe(80) == "OPENED"   # opens cycle at t=11.0
    assert t.observe(60) is None       # min_percent updates, no transition
    record = t.observe(100)            # closes at t=13.0
    assert record.outcome == "recovered"
    assert record.duration_ms == 2000
    assert record.min_percent == 60
    assert record.station_id == 7
    assert record.station_name == "DI.fm Ambient"
    assert record.url == "http://prem2.di.fm/ambient"
    assert record.cause_hint == "unknown"


def test_force_close_returns_record_with_outcome():
    """D-03: force_close on open cycle returns record with given outcome.
    force_close on closed cycle returns None (idempotent guard)."""
    t = _BufferUnderrunTracker(clock=iter([10.0, 11.0, 12.5]).__next__)
    t.bind_url(1, "Test", "http://x/")
    t.observe(100)                      # arms
    t.observe(70)                       # opens (t=11.0)
    record = t.force_close("pause")     # closes (t=12.5)
    assert record.outcome == "pause"
    assert record.duration_ms == 1500
    # Second force_close on already-closed cycle: returns None
    assert t.force_close("stop") is None


def test_bind_url_resets_state():
    """D-04 / Pitfall 3: bind_url() resets armed + open. New URL's first <100
    must NOT open a cycle until that URL has seen percent == 100 first."""
    t = _BufferUnderrunTracker(clock=iter([10.0, 11.0, 12.0, 13.0, 14.0]).__next__)
    t.bind_url(1, "Old", "http://old/")
    t.observe(100)                      # arms old
    t.observe(70)                       # opens cycle on old URL
    # Bind a NEW URL — must reset arm + open
    t.bind_url(2, "New", "http://new/")
    # First <100 on new URL is initial fill — must NOT open a cycle
    assert t.observe(50) is None
    # 100 arms the new URL
    assert t.observe(100) is None
    # NOW <100 opens a cycle
    assert t.observe(40) == "OPENED"


def test_cause_hint_network_after_error():
    """D-02 Discretion: note_error_in_cycle during open cycle flips cause_hint
    to 'network'; the close record carries it."""
    t = _BufferUnderrunTracker(clock=iter([10.0, 11.0, 12.0, 13.0]).__next__)
    t.bind_url(1, "Test", "http://x/")
    t.observe(100)                      # arms
    t.observe(70)                       # opens
    t.note_error_in_cycle()             # cause_hint flips
    record = t.observe(100)             # closes naturally
    assert record.cause_hint == "network"
    assert record.outcome == "recovered"
