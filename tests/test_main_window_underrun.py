"""Tests for Phase 62 / BUG-09 — MainWindow underrun toast cooldown gate.

Verifies _on_underrun_recovery_started shows a `Buffering…` toast (D-06) on
first emit, suppresses repeats within 10s (D-08), and re-allows after the
cooldown elapses; closeEvent calls Player.shutdown_underrun_tracker() so an
in-flight cycle still writes its log line (D-03 / Pitfall 4); __main__ adds
the per-logger INFO level for musicstreamer.player (Pitfall 5).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtGui import QCloseEvent

from musicstreamer.ui_qt.main_window import MainWindow
from tests.test_main_window_integration import FakePlayer, FakeRepo


@pytest.fixture
def fake_player():
    return FakePlayer()


@pytest.fixture
def fake_repo():
    return FakeRepo()


def test_first_call_shows_toast(qtbot, fake_player, fake_repo, monkeypatch):
    """D-06: first underrun_recovery_started emission shows Buffering toast."""
    monkeypatch.setattr(
        "musicstreamer.ui_qt.main_window.time.monotonic",
        lambda: 1000.0,
    )
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    fake_player.underrun_recovery_started.emit()
    qtbot.wait(50)
    assert "Buffering" in w._toast.label.text()


def test_second_call_within_cooldown_suppressed(qtbot, fake_player, fake_repo, monkeypatch):
    """D-08: second emit within 10s does NOT update the toast (cooldown gate)."""
    times = iter([1000.0, 1005.0])  # 5s gap — within 10s cooldown
    monkeypatch.setattr(
        "musicstreamer.ui_qt.main_window.time.monotonic",
        lambda: next(times),
    )
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    # First call — toast appears
    fake_player.underrun_recovery_started.emit()
    qtbot.wait(50)
    first_text = w._toast.label.text()
    assert "Buffering" in first_text

    # Replace the toast text with a marker — if the cooldown gate suppresses
    # the second call, the marker text remains; if it fires, the marker is
    # overwritten with "Buffering…".
    w._toast.label.setText("MARKER_NOT_OVERWRITTEN")

    # Second call within cooldown — must be suppressed
    fake_player.underrun_recovery_started.emit()
    qtbot.wait(50)
    assert w._toast.label.text() == "MARKER_NOT_OVERWRITTEN", \
        f"second toast within cooldown should have been suppressed; got: {w._toast.label.text()!r}"


def test_toast_after_cooldown_allowed(qtbot, fake_player, fake_repo, monkeypatch):
    """D-08: emission AFTER the 10s cooldown elapses shows a fresh toast."""
    times = iter([1000.0, 1011.0])  # 11s gap — past 10s cooldown
    monkeypatch.setattr(
        "musicstreamer.ui_qt.main_window.time.monotonic",
        lambda: next(times),
    )
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    fake_player.underrun_recovery_started.emit()
    qtbot.wait(50)
    assert "Buffering" in w._toast.label.text()

    # Replace toast with marker; second call is past cooldown → toast should re-appear
    w._toast.label.setText("MARKER")
    fake_player.underrun_recovery_started.emit()
    qtbot.wait(50)
    assert "Buffering" in w._toast.label.text()


def test_close_event_force_closes_open_cycle(qtbot, fake_player, fake_repo):
    """D-03 / Pitfall 4: closeEvent calls Player.shutdown_underrun_tracker()
    so any in-flight cycle still writes its log line before app exit."""
    shutdown_calls = []
    # Replace the no-op stub on the FakePlayer instance with a spy
    fake_player.shutdown_underrun_tracker = lambda: shutdown_calls.append(True)

    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    w.closeEvent(QCloseEvent())
    assert shutdown_calls == [True], \
        f"closeEvent must call player.shutdown_underrun_tracker(); got calls={shutdown_calls}"


def test_main_module_sets_player_logger_to_info():
    """Pitfall 5: __main__.py adds per-logger INFO level for musicstreamer.player
    (must NOT use global logging.basicConfig(level=logging.INFO) which would
    surface chatter from aa_import / gbs_api / mpris2)."""
    main_path = Path("musicstreamer/__main__.py")
    text = main_path.read_text()
    # The exact line shape Plan 03 adds — comment lines are stripped to avoid
    # false positives from header docs (PATTERNS.md §S-3 grep hygiene).
    code_only = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    pattern = re.compile(
        r'getLogger\(\s*["\']musicstreamer\.player["\']\s*\)\.setLevel\(\s*logging\.INFO\s*\)'
    )
    matches = pattern.findall(code_only)
    assert len(matches) >= 1, (
        f"expected per-logger INFO level for musicstreamer.player in __main__.py "
        f"(Pitfall 5 — global INFO would pollute other modules); got 0 matches"
    )
    # Sanity: basicConfig is still WARNING (NOT bumped to INFO globally)
    basicconfig_pattern = re.compile(r'logging\.basicConfig\(\s*level=logging\.WARNING\s*\)')
    assert basicconfig_pattern.search(code_only), (
        "logging.basicConfig(level=logging.WARNING) must remain in __main__.py — "
        "do NOT change global level (Pitfall 5)"
    )
