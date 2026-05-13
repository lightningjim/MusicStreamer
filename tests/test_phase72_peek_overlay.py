"""Phase 72-04 / LAYOUT-01: Hover-to-peek overlay integration tests.

Covers the StationListPeekOverlay class + MainWindow's filled-in peek lifecycle
(_install_peek_hover_filter / _remove_peek_hover_filter / _open_peek_overlay /
_close_peek_overlay) per the Plan 03 stub hand-off contract.

Decisions locked here:
  * D-11: Hover-to-peek on the left edge is the chosen secondary reveal mechanism.
  * D-12: Peek overlay floats OVER the now-playing pane (overlay style), NOT
          splitter reflow — `_splitter.sizes()` stable during peek.
  * D-13: Trigger zone = left <= 4px; dwell timer = 280ms.
  * D-14: Dismiss = mouse-leaves-overlay ONLY — Esc does NOT dismiss; click on
          a station does NOT auto-dismiss.
  * D-15: Peek overlay is fully interactive — click-to-play fires station_activated.

Test doubles imported from tests/test_main_window_integration.py
(FakePlayer + FakeRepo + _make_station).
"""
from __future__ import annotations

import inspect

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame

from musicstreamer.ui_qt import main_window as mw_mod
from musicstreamer.ui_qt.main_window import MainWindow

# Reuse the established integration-test fixtures + doubles.
from tests.test_main_window_integration import FakePlayer, FakeRepo, _make_station


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_player():
    return FakePlayer()


@pytest.fixture
def fake_repo():
    return FakeRepo(stations=[_make_station()])


@pytest.fixture
def window(qtbot, fake_player, fake_repo):
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    w.resize(1200, 800)
    return w


# ---------------------------------------------------------------------------
# Helpers — synthesize Qt mouse-move events on a widget
# ---------------------------------------------------------------------------


def _send_mouse_move(widget, x: int, y: int) -> None:
    """Synthesize a QEvent.MouseMove on the given widget at local pos (x, y).

    Routes through QApplication.sendEvent so the receiving widget's event
    filter chain (MainWindow.eventFilter installed on centralWidget) sees it
    exactly as Qt would deliver a real cursor move.
    """
    from PySide6.QtWidgets import QApplication

    pos_local = QPointF(x, y)
    global_pos = QPointF(widget.mapToGlobal(QPoint(x, y)))
    ev = QMouseEvent(
        QEvent.MouseMove,
        pos_local,
        global_pos,
        Qt.NoButton,
        Qt.NoButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(widget, ev)


def _send_leave(widget) -> None:
    """Synthesize a QEvent.Leave on the given widget."""
    from PySide6.QtWidgets import QApplication

    ev = QEvent(QEvent.Leave)
    QApplication.sendEvent(widget, ev)


# ---------------------------------------------------------------------------
# Trigger zone + dwell timer
# ---------------------------------------------------------------------------


def test_dwell_fires_after_280ms_in_zone(window, qtbot):
    """D-13: hover within <= 4px for 280ms opens the peek overlay.

    Compact ON -> MouseMove at x=2 -> wait 50ms (peek not yet open) ->
    wait 280ms total (peek open).
    """
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    cw = window.centralWidget()
    assert window._peek_overlay is None or not window._peek_overlay.isVisible()
    _send_mouse_move(cw, 2, 100)
    # Not yet — dwell still pending
    qtbot.wait(50)
    assert window._peek_overlay is None or not window._peek_overlay.isVisible()
    # After full dwell — overlay should be visible
    qtbot.wait(280)
    assert window._peek_overlay is not None
    assert window._peek_overlay.isVisible() is True


def test_zone_exit_cancels_dwell(window, qtbot):
    """D-13: leaving the zone before 280ms cancels the pending dwell."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    cw = window.centralWidget()
    _send_mouse_move(cw, 2, 100)
    qtbot.wait(100)
    # Cursor leaves the zone before the dwell completes
    _send_mouse_move(cw, 200, 100)
    qtbot.wait(300)
    # Peek must NOT have opened
    assert window._peek_overlay is None or not window._peek_overlay.isVisible()
    # And the dwell timer must be inactive (either None or stopped)
    assert (
        window._peek_dwell_timer is None
        or not window._peek_dwell_timer.isActive()
    )


def test_mouse_tracking_enabled_when_compact_on(window):
    """Pitfall 2: mouse tracking on BOTH MainWindow and centralWidget."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    assert window.hasMouseTracking() is True
    assert window.centralWidget().hasMouseTracking() is True


def test_event_filter_removed_on_compact_off(window, qtbot):
    """Pitfall 7: leaving compact mode removes the event filter so the dwell
    timer no longer fires on subsequent mouse moves."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    btn.click()  # compact OFF
    cw = window.centralWidget()
    _send_mouse_move(cw, 2, 100)
    qtbot.wait(300)
    # Peek must NOT have opened — filter removed, dwell timer not restarted
    assert window._peek_overlay is None or not window._peek_overlay.isVisible()


# ---------------------------------------------------------------------------
# Overlay open / close lifecycle
# ---------------------------------------------------------------------------


def test_peek_overlay_does_not_reflow_splitter(window, qtbot):
    """D-12: opening the peek must NOT change splitter sizes."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    sizes_before = window._splitter.sizes()
    # Open peek
    window._open_peek_overlay()
    assert window._peek_overlay is not None
    assert window._peek_overlay.isVisible() is True
    sizes_after = window._splitter.sizes()
    assert sizes_after == sizes_before, (
        f"D-12 violated — peek reflowed splitter: {sizes_before} -> {sizes_after}"
    )


def test_leave_closes_overlay(window, qtbot):
    """D-14: mouse-leaves-overlay closes the peek and reparents back to splitter."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    window._open_peek_overlay()
    assert window._peek_overlay.isVisible() is True
    # Fire Leave on the overlay
    _send_leave(window._peek_overlay)
    # Overlay hidden
    assert window._peek_overlay.isVisible() is False
    # station_panel reparented back to splitter at index 0, but stays hidden
    # because compact mode is still active.
    assert window._splitter.indexOf(window.station_panel) == 0
    assert window.station_panel.isHidden() is True


def test_esc_does_not_dismiss(window, qtbot):
    """D-14: Esc must NOT dismiss the peek overlay."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    window._open_peek_overlay()
    assert window._peek_overlay.isVisible() is True
    qtbot.keyClick(window, Qt.Key_Escape)
    assert window._peek_overlay.isVisible() is True


def test_click_station_keeps_overlay_open(window, qtbot):
    """D-14: clicking a station inside the peeked panel does NOT auto-dismiss."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    window._open_peek_overlay()
    assert window._peek_overlay.isVisible() is True
    # Synthetically emit station_activated as a stand-in for a click. The
    # overlay's eventFilter is gated on QEvent.Leave only — emitting a signal
    # does not trigger that path.
    station = _make_station()
    window.station_panel.station_activated.emit(station)
    assert window._peek_overlay.isVisible() is True


def test_peek_station_click_activates_playback(window, qtbot, fake_player):
    """D-15: the peeked StationListPanel is the SAME instance — emitting
    station_activated still drives the player."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    window._open_peek_overlay()
    station = _make_station("Drone Zone", "SomaFM")
    window.station_panel.station_activated.emit(station)
    assert len(fake_player.play_calls) == 1
    assert fake_player.play_calls[0] is station


def test_exit_compact_while_peeking_closes_overlay(window, qtbot):
    """Exiting compact mode while peek is open closes the overlay and returns
    station_panel to the splitter at index 0, visible (compact OFF)."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    window._open_peek_overlay()
    assert window._peek_overlay.isVisible() is True
    # Toggle compact OFF — the else-branch's peek-release guard MUST fire
    btn.click()
    assert window._peek_overlay.isVisible() is False
    assert window.station_panel.isVisible() is True
    assert window._splitter.indexOf(window.station_panel) == 0


# ---------------------------------------------------------------------------
# Z-order + parent (Pitfall 8)
# ---------------------------------------------------------------------------


def test_peek_overlay_parent_is_central_widget(window, qtbot):
    """Pitfall 8: peek overlay parents to centralWidget; ToastOverlay parents
    to MainWindow — toasts win z-order naturally."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    window._open_peek_overlay()
    # Peek overlay parent is centralWidget
    assert window._peek_overlay.parent() is window.centralWidget()
    # Toast overlay parent is MainWindow (window itself)
    assert window._toast.parent() is window


# ---------------------------------------------------------------------------
# Reparent integrity (Pitfall 6)
# ---------------------------------------------------------------------------


def test_station_panel_returns_to_splitter_index_0(window, qtbot):
    """Pitfall 6: `splitter.insertWidget(0, station_panel)` (NOT addWidget)
    after closing the peek. station_panel must come back at the LEFT, not
    the right."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    window._open_peek_overlay()
    # Sanity — panel has moved into the overlay
    assert window._splitter.indexOf(window.station_panel) == -1
    # Close peek
    window._close_peek_overlay()
    # Back at index 0 (LEFT child)
    assert window._splitter.indexOf(window.station_panel) == 0
    assert window._splitter.widget(0) is window.station_panel
    assert window._splitter.widget(1) is window.now_playing


# ---------------------------------------------------------------------------
# Overlay width (snapshot + fallback branches)
# ---------------------------------------------------------------------------


def test_peek_overlay_width_matches_snapshot(window, qtbot):
    """UI-SPEC §Spacing: snapshot-present branch uses
    `_splitter_sizes_before_compact[0]` as the overlay width."""
    window.resize(1200, 800)
    window._splitter.setSizes([400, 800])
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON — snapshot taken BEFORE hide -> [400, 800]
    expected_w = window._splitter_sizes_before_compact[0]
    window._open_peek_overlay()
    actual_w = window._peek_overlay.width()
    assert abs(actual_w - expected_w) <= 2, (
        f"Width mismatch: expected ~ {expected_w}, got {actual_w}"
    )


def test_peek_overlay_width_fallback_to_360_when_no_resize(window, qtbot):
    """UI-SPEC §Spacing: snapshot-absent branch falls back to 360px.

    RESEARCH Open Question 2 RESOLVED — when no prior splitter resize is
    available, the overlay defaults to the splitter's design-default width
    (360px from `[360, 840]` at main_window.py:285).

    The branch is exercised by forcing the snapshot to None AFTER compact-ON
    has populated it (so the event-filter / hover-peek path is still wired)
    but BEFORE the open call inspects the snapshot.
    """
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON — snapshot populated by the toggle slot
    # Monkey-patch the snapshot to None — force the else-fallback branch
    window._splitter_sizes_before_compact = None
    window._open_peek_overlay()
    actual_w = window._peek_overlay.width()
    assert abs(actual_w - 360) <= 2, (
        f"Fallback width mismatch: expected ~ 360, got {actual_w}"
    )


# ---------------------------------------------------------------------------
# Structural source asserts (QA-05 + frontmatter must_haves)
# ---------------------------------------------------------------------------


def test_no_lambda_in_peek_connects():
    """QA-05: no lambda on any peek-related .connect line in MainWindow.

    Greps the MainWindow source for any line that references _peek_overlay
    or _peek_dwell_timer alongside .connect; asserts no 'lambda' on those
    lines.
    """
    src = inspect.getsource(mw_mod.MainWindow)
    needles = ("_peek_overlay", "_peek_dwell_timer", "_open_peek_overlay",
               "_close_peek_overlay")
    for line in src.splitlines():
        if ".connect(" in line and any(n in line for n in needles):
            assert "lambda" not in line, (
                f"QA-05 violated — lambda on peek connect line: {line!r}"
            )


def test_peek_overlay_is_qframe_subclass():
    """Source assertion: StationListPeekOverlay is a QFrame subclass."""
    from musicstreamer.ui_qt.station_list_peek_overlay import (
        StationListPeekOverlay,
    )

    assert issubclass(StationListPeekOverlay, QFrame)
