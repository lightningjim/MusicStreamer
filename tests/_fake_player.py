"""Shared FakePlayer(QObject) test double for musicstreamer tests.

Phase 77 D-07 / D-08 / D-16 / D-17.

This module declares a single canonical ``FakePlayer(QObject)`` that mirrors
**all 20 Signals** currently on ``musicstreamer.player.Player`` (Phase 83
added ``_preroll_about_to_finish_requested``), PLUS one Wave-0 forward-
compatible mirror that Player itself will gain in Wave 1 (Phase 84 / D-12
``buffer_duration_changed`` — added here in Wave 0 per INFRA-01 drift-guard
convention: parity edits ship in the same wave as the new Signal contract
under test, even when the Player half doesn't land until the next wave).
The canonical Signal source of truth is ``musicstreamer/player.py:241-297``.

Rule 1 — before any future maintenance session, re-grep the production Signal
block to confirm no signals were added since this file was last updated::

    grep -nE "^\\s*[a-zA-Z_][a-zA-Z0-9_]*\\s*=\\s*Signal\\(" musicstreamer/player.py

The two drift-guard tests enforce this automatically:
  - tests/test_fake_player_signal_parity.py  (D-16 — name + arity parity)
  - tests/test_fake_player_no_inline.py      (D-17 — only this file may declare
                                               FakePlayer(QObject))

Usage::

    from tests._fake_player import FakePlayer
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal

from musicstreamer.models import Station


class FakePlayer(QObject):
    """Canonical shared Player test double.

    Mirrors every Signal declared on ``musicstreamer.player.Player``
    (20 signals, D-16 invariant) plus one Wave-0 forward-compatible mirror
    for the Phase 84 / D-12 ``buffer_duration_changed`` Signal that Player
    will gain in Wave 1 (21 signals total on FakePlayer in Wave 0; the
    parity test allows FakePlayer to lead Player by design — see the
    drift-guard tests below). Provides method stubs for the API surface
    touched by MainWindow, EditStationDialog, and NowPlayingPanel
    test consumers.

    Drift-guards:
      - tests/test_fake_player_signal_parity.py  (D-16)
      - tests/test_fake_player_no_inline.py      (D-17)
    """

    # ------------------------------------------------------------------
    # Signals — production declaration order from player.py:241-282
    # MUST match production arities exactly (D-16 arity drift-guard).
    # ------------------------------------------------------------------

    # Public signals (10)
    title_changed              = Signal(str)
    failover                   = Signal(object)
    offline                    = Signal(str)
    twitch_resolved            = Signal(str)
    youtube_resolved           = Signal(str, bool, int)  # Phase 95: (resolved_url, is_live, resolve_seq) — int carries the _youtube_resolve_seq generation guard (mirrors _preroll_about_to_finish_requested)
    youtube_resolution_failed  = Signal(str)
    playback_error             = Signal(str)
    cookies_cleared            = Signal(str)
    elapsed_updated            = Signal(int)
    buffer_percent             = Signal(int)

    # Internal cross-thread marshaling signals (10 — 7 underscore-prefixed +
    # 3 non-underscore: underrun_recovery_started + underrun_count_changed +
    # buffer_duration_changed).
    # Phase 83 added _preroll_about_to_finish_requested = Signal(int) — the
    # int payload carries the _preroll_seq stamp for CR-01/WR-03 race guards.
    # Phase 84 / D-12 added buffer_duration_changed = Signal(int, bool) — the
    # (seconds, is_adapted) tuple drives the stats-for-nerds Buf duration row.
    _cancel_timers_requested           = Signal()
    _error_recovery_requested          = Signal(int)  # Phase 95-02: int carries _recovery_seq (recovery generation captured at error-post time on the bus thread, mirroring _preroll_about_to_finish_requested)
    _try_next_stream_requested         = Signal()
    _preroll_about_to_finish_requested = Signal(int)  # Phase 83 D-05 — preroll about-to-finish handoff (int = preroll_seq for CR-01/WR-03 guard)
    _playbin_playing_state_reached     = Signal()
    _underrun_cycle_opened         = Signal()
    _underrun_cycle_closed         = Signal(object)
    underrun_recovery_started      = Signal()
    underrun_count_changed         = Signal(int)  # Phase 78 / BUG-09 Commit A
    buffer_duration_changed        = Signal(int, bool)  # Phase 84 / BUG-09 Commit B / D-12 (WR-02: (seconds, is_adapted))

    # Phase 70 / DS-01 caps signal (1)
    audio_caps_detected = Signal(int, int, int)  # stream_id, rate_hz, bit_depth

    # ------------------------------------------------------------------
    # Initializer
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()
        self.play_calls: list[Station] = []
        self.pause_calls: int = 0
        self.stop_calls: int = 0
        self.volume: Optional[float] = None
        # Extended tracking attributes used by NowPlayingPanel / media-keys consumers
        self.set_volume_calls: list[float] = []
        self.stop_called: bool = False
        self.pause_called: bool = False
        self.calls: list[tuple] = []  # EQ toggle tracking: ("enabled", bool) tuples
        # Phase 95: records (station, is_playing) tuples for invalidate_for_edit
        # so MainWindow edit→sync wiring tests (V7) can assert the player was
        # notified exactly once with the updated station.
        self.invalidate_calls: list[tuple] = []

    # ------------------------------------------------------------------
    # Method stubs — API surface consumed by MainWindow / test consumers
    # ------------------------------------------------------------------

    def set_volume(self, value: float) -> None:
        self.volume = value
        self.set_volume_calls.append(value)

    def play(self, station: Station, **kwargs) -> None:
        self.play_calls.append(station)

    def pause(self) -> None:
        self.pause_calls += 1
        self.pause_called = True

    def stop(self) -> None:
        self.stop_calls += 1
        self.stop_called = True

    def play_stream(self, stream) -> None:
        """Phase 72.1: NowPlayingPanel calls player.play_stream(s) on picker selection."""
        self.play_calls.append(stream)

    def invalidate_for_edit(self, station, is_playing: bool = False, **kwargs) -> None:
        """Phase 95: MainWindow._sync_now_playing_station notifies the player on
        every committed edit so stale stream state cannot survive a URL change.
        Records the call for the V7 integration assertion."""
        self.invalidate_calls.append((station, is_playing))

    # Phase 47.2: EQ API stubs — MainWindow calls restore_eq_from_settings
    # from __init__; the others are referenced by EqualizerDialog.
    def restore_eq_from_settings(self, repo) -> None:
        pass

    def set_eq_enabled(self, enabled: bool) -> None:
        # Track EQ toggle calls — consumers assert on self.calls as ("enabled", bool) tuples
        self.calls.append(("enabled", bool(enabled)))

    def set_eq_profile(self, profile) -> None:
        pass

    def set_eq_preamp(self, db: float) -> None:
        pass

    def shutdown_underrun_tracker(self) -> None:
        """Phase 62 / D-03: no-op stub — real Player force-closes any open cycle.

        FakePlayer has no tracker so the call is a no-op; MainWindow.closeEvent
        calls this in a try/except, but having it defined avoids the warning log.
        """
        pass
