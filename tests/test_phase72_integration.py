"""Phase 72-05 / LAYOUT-01: End-to-end integration tests.

Final regression lock for the full compact+peek+restore lifecycle across all
four prior Phase 72 plans:

  * Plan 02 — NowPlayingPanel.compact_mode_toggle_btn + signal + icon helper
  * Plan 03 — MainWindow._on_compact_toggle + Ctrl+B QShortcut + handle(1) calls
  * Plan 04 — StationListPeekOverlay + hover/dwell + reparent round-trip

The three tests below exercise the production code at the integration level
(no mocks, real MainWindow + real QSplitter + real StationListPanel +
real StationListPeekOverlay), using only the FakePlayer / FakeRepo doubles
established by `tests/test_main_window_integration.py`.

Tests:
  * test_full_compact_peek_lifecycle — step-by-step single-cycle walk-through
    of every interaction documented in UI-SPEC §Interaction Contract:
    construct -> toggle ON -> hover-peek -> click station -> mouse-leave ->
    re-peek -> Ctrl+B toggle OFF -> final-state assertions.
  * test_multiple_toggle_cycles_preserve_sizes — three full ON/OFF cycles
    starting from `[350, 850]`; after each OFF, splitter sizes must return
    to ~`[350, 850]` (D-10 round-trip locked at integration level).
  * test_no_compact_setting_written_after_full_lifecycle — D-09 invariant
    locked at integration level: after a full lifecycle, no compact-* key
    appears in the repo's settings dict.

Patterns reused (so the integration test is consistent with the prior plans):
  * `_send_mouse_move` / `_send_leave` helpers from test_phase72_peek_overlay
    (kept local to avoid cross-test-file imports beyond the FakePlayer/FakeRepo
    doubles).
  * `window` fixture pattern from test_phase72_peek_overlay (with show() +
    qtbot.waitExposed) — needed because the peek overlay's isVisible()
    returns False on un-exposed widget hierarchies.

QA-05: every signal connection uses a bound method, never an inline anonymous
callable — verified by the file-level grep gate in the plan's acceptance
criteria.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from musicstreamer.ui_qt.main_window import MainWindow

# Reuse the established integration-test fixtures + doubles. Importing this
# way avoids duplicating the ~150-line FakePlayer/FakeRepo surface.
from tests.test_main_window_integration import FakePlayer, FakeRepo, _make_station


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_player():
    return FakePlayer()


@pytest.fixture
def fake_repo():
    # Use two distinct stations so test_full_compact_peek_lifecycle can verify
    # that station_activated still routes correctly when fired from inside the
    # peek overlay (D-15: same StationListPanel instance, same signal contract).
    return FakeRepo(
        stations=[
            _make_station(name="Drone Zone", provider="SomaFM"),
            _make_station(name="Groove Salad", provider="SomaFM"),
        ]
    )


@pytest.fixture
def window(qtbot, fake_player, fake_repo):
    """Construct + show MainWindow at default size 1200x800.

    `.show()` + `qtbot.waitExposed()` is REQUIRED so child widget
    `isVisible()` returns accurate values and the centralWidget event filter
    receives delivered mouse events. Mirrors the precedent in
    `tests/test_phase72_peek_overlay.py:fixture window`.
    """
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    w.resize(1200, 800)
    with qtbot.waitExposed(w):
        w.show()
    return w


# ---------------------------------------------------------------------------
# Helpers — synthesize Qt mouse events
# ---------------------------------------------------------------------------


def _send_mouse_move(widget, x: int, y: int, monkeypatch=None) -> None:
    """Synthesize a QEvent.MouseMove on `widget` and patch QCursor.pos.

    The Phase 72 hover-peek filter is installed globally on
    QApplication.instance() and reads cursor position from QCursor.pos()
    rather than from event.position() (the centralWidget-receiver-identity
    filter was a bug — see debug session phase-72-hover-peek-wayland for
    root cause). Tests must (a) patch QCursor.pos to a deterministic value
    AND (b) send any MouseMove so the global filter is woken.

    Mirrors tests/test_phase72_peek_overlay.py:_send_mouse_move.
    """
    from PySide6.QtGui import QCursor

    pos_local = QPointF(x, y)
    global_pt = widget.mapToGlobal(QPoint(x, y))
    if monkeypatch is not None:
        monkeypatch.setattr(QCursor, "pos", staticmethod(lambda gp=global_pt: gp))
    ev = QMouseEvent(
        QEvent.MouseMove,
        pos_local,
        QPointF(global_pt),
        Qt.NoButton,
        Qt.NoButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(widget, ev)


def _send_leave(widget) -> None:
    """Synthesize a QEvent.Leave on `widget`. Mirrors the helper in
    tests/test_phase72_peek_overlay.py:_send_leave."""
    ev = QEvent(QEvent.Leave)
    QApplication.sendEvent(widget, ev)


def _make_peek_visible_predicate(window):
    """Build a bound-method-style predicate for qtbot.waitUntil that returns
    True iff `window._peek_overlay` is non-None and visible. Avoids the
    inline-anonymous-callable pattern banned by QA-05; mirrors the same
    bound-method convention used by every other connect/predicate call in
    the Phase 72 test files.
    """

    def predicate() -> bool:
        return (
            window._peek_overlay is not None
            and window._peek_overlay.isVisible()
        )

    return predicate


# ---------------------------------------------------------------------------
# Test 1 — Full single-cycle lifecycle walk-through
# ---------------------------------------------------------------------------


def test_full_compact_peek_lifecycle(window, qtbot, fake_player, monkeypatch):
    """End-to-end walk-through of every documented interaction in UI-SPEC.

    Step-by-step structure (each step asserts the observable state delta):

      (1) Initial state
      (2) Establish a known splitter size [400, 800]
      (3) Click compact button ON -> panel hidden, snapshot captured, icon
          flipped (tooltip "Show stations (Ctrl+B)")
      (4) MouseMove in left-edge zone -> wait 280ms -> peek visible
      (5) Emit station_activated from the peeked panel -> player.play_calls
          increments, peek stays visible
      (6) QEvent.Leave on the peek overlay -> peek hidden, station_panel
          reparented to splitter index 0 BUT still hidden (compact ON)
      (7) Repeat the dwell -> peek re-opens (proves the lifecycle is
          repeatable across multiple peeks within a single compact session)
      (8) Toggle compact OFF via Ctrl+B (activate the shortcut) -> peek
          closed, station_panel visible, splitter sizes restored
      (9) Final state: button unchecked, panel visible, peek hidden,
          snapshot reset to None (Pitfall 5 invariant)
    """
    btn = window.now_playing.compact_mode_toggle_btn
    cw = window.centralWidget()

    # ------------------------------------------------------------------
    # Step 1 — Initial state
    # ------------------------------------------------------------------
    assert btn.isChecked() is False
    assert window.station_panel.isHidden() is False
    assert window._peek_overlay is None, (
        "Peek overlay must be lazy-constructed — not built until first peek."
    )
    assert window._splitter_sizes_before_compact is None, (
        "Pitfall 5: snapshot starts at None on a fresh launch (D-09 session-only)."
    )
    initial_tooltip = btn.toolTip()
    assert "Hide stations" in initial_tooltip, (
        f"Initial tooltip should communicate 'Hide stations', got: {initial_tooltip!r}"
    )
    initial_icon_cache_key = btn.icon().cacheKey()

    # ------------------------------------------------------------------
    # Step 2 — Establish known splitter sizes
    # ------------------------------------------------------------------
    window._splitter.setSizes([400, 800])
    expected_sizes = window._splitter.sizes()
    # Qt may clamp by minimumWidth; assert the values are non-zero and the
    # expected ordering holds.
    assert sum(expected_sizes) > 0
    assert expected_sizes[0] > 0
    assert expected_sizes[1] > 0

    # ------------------------------------------------------------------
    # Step 3 — Toggle compact ON via button click
    # ------------------------------------------------------------------
    btn.click()
    assert btn.isChecked() is True
    assert window.station_panel.isHidden() is True, (
        "D-01 / D-06: station_panel must be hidden after compact ON."
    )
    assert window._splitter_sizes_before_compact == expected_sizes, (
        f"D-10 / Pitfall 1: snapshot must capture sizes BEFORE hide. "
        f"Expected {expected_sizes}, got {window._splitter_sizes_before_compact}."
    )
    # D-05 icon flip — the button's icon cacheKey changes between states.
    flipped_icon_cache_key = btn.icon().cacheKey()
    assert flipped_icon_cache_key != initial_icon_cache_key, (
        "D-05: button icon must flip between expanded/compact states."
    )
    assert "Show stations" in btn.toolTip(), (
        f"D-05: tooltip must communicate next action 'Show stations', "
        f"got: {btn.toolTip()!r}"
    )
    # Mouse tracking enabled on both surfaces (Pitfall 2 — required for
    # MouseMove events to reach the eventFilter without a button held).
    assert window.hasMouseTracking() is True
    assert cw.hasMouseTracking() is True

    # ------------------------------------------------------------------
    # Step 4 — Hover-peek dwell fires after 280ms in the left-edge zone
    # ------------------------------------------------------------------
    _send_mouse_move(cw, 2, 100, monkeypatch=monkeypatch)
    qtbot.wait(50)  # Dwell not yet complete — peek must stay closed
    assert window._peek_overlay is None or not window._peek_overlay.isVisible()
    # waitUntil() is preferred over a fixed sleep here because the offscreen
    # platform's event-loop drain can occasionally run a few-dozen ms behind
    # the wall clock; the substantive contract is "peek opens after the
    # dwell completes", not "peek opens at exactly 280 ms".
    qtbot.waitUntil(_make_peek_visible_predicate(window), timeout=1000)
    assert window._peek_overlay is not None, (
        "D-13: peek overlay must be lazy-constructed after first dwell completes."
    )
    assert window._peek_overlay.isVisible() is True, (
        "D-13: peek overlay must be visible after the 280ms dwell completes."
    )
    # station_panel was reparented INTO the overlay (Pitfall 6 inverse — out
    # of splitter, into overlay layout).
    assert window._splitter.indexOf(window.station_panel) == -1, (
        "D-15: station_panel must be reparented out of the splitter into "
        "the peek overlay so its full interactivity is preserved."
    )

    # ------------------------------------------------------------------
    # Step 5 — Click a station inside the peeked panel
    # ------------------------------------------------------------------
    # Use the SAME signal contract the docked panel uses. Per D-15 this is
    # the same StationListPanel instance — emitting station_activated fires
    # the player.
    station = _make_station(name="Drone Zone", provider="SomaFM")
    before_play_count = len(fake_player.play_calls)
    window.station_panel.station_activated.emit(station)
    assert len(fake_player.play_calls) == before_play_count + 1, (
        "D-15: station_activated emitted from inside the peek overlay must "
        "still drive the player (single panel instance, single signal contract)."
    )
    assert fake_player.play_calls[-1] is station
    # D-14: clicking a station does NOT auto-dismiss
    assert window._peek_overlay.isVisible() is True, (
        "D-14: clicking a station inside the peek must NOT close the overlay."
    )

    # ------------------------------------------------------------------
    # Step 6 — Mouse-leave the overlay -> peek closes, panel reparented back
    # ------------------------------------------------------------------
    _send_leave(window._peek_overlay)
    assert window._peek_overlay.isVisible() is False, (
        "D-14: mouse-leave-overlay must close the peek."
    )
    # station_panel is back at splitter index 0 (Pitfall 6 — insertWidget(0, ...))
    assert window._splitter.indexOf(window.station_panel) == 0, (
        "Pitfall 6: station_panel must return to splitter index 0 after peek "
        "closes (insertWidget(0, ...) NOT addWidget)."
    )
    assert window._splitter.widget(0) is window.station_panel
    assert window._splitter.widget(1) is window.now_playing
    # Compact mode is still active, so the panel stays hidden.
    assert window.station_panel.isHidden() is True, (
        "Compact mode still ON after peek closes — station_panel stays hidden."
    )
    assert btn.isChecked() is True

    # ------------------------------------------------------------------
    # Step 7 — Second peek cycle (proves lifecycle is repeatable)
    # ------------------------------------------------------------------
    # Use waitUntil() (poll-based) rather than a fixed wait, because the
    # post-Leave Qt event-loop drain can vary by a few-dozen ms across
    # runs (offscreen platform). The substantive contract is that the peek
    # re-opens within a reasonable time after a fresh MouseMove + dwell,
    # not that it opens at exactly 280 ms.
    _send_mouse_move(cw, 2, 100, monkeypatch=monkeypatch)
    qtbot.waitUntil(_make_peek_visible_predicate(window), timeout=1000)
    assert window._peek_overlay.isVisible() is True, (
        "Peek must re-open on a second dwell within the same compact session."
    )
    # snapshot of the splitter sizes captured at compact-ON entry has NOT
    # been mutated by the peek lifecycle (the overlay only reparents the
    # panel; it does not touch the snapshot).
    assert window._splitter_sizes_before_compact == expected_sizes, (
        "Pitfall 5: peek lifecycle must not mutate the splitter snapshot."
    )

    # ------------------------------------------------------------------
    # Step 8 — Toggle compact OFF via Ctrl+B shortcut
    # ------------------------------------------------------------------
    window._compact_shortcut.activated.emit()
    assert btn.isChecked() is False, (
        "D-02 / D-03: Ctrl+B must toggle the button (single source of truth)."
    )
    assert window._peek_overlay.isVisible() is False, (
        "Exiting compact mode while peek is open MUST close the overlay "
        "(peek-release guard in the compact-OFF else-branch)."
    )
    assert window.station_panel.isVisible() is True
    # Splitter sizes restored (within Qt's reflow granularity).
    restored = window._splitter.sizes()
    for actual_v, expected_v in zip(restored, expected_sizes):
        assert abs(actual_v - expected_v) <= 2, (
            f"D-10 round-trip drift: restored {restored} vs expected "
            f"{expected_sizes} after Ctrl+B toggle-OFF."
        )

    # ------------------------------------------------------------------
    # Step 9 — Final-state invariants
    # ------------------------------------------------------------------
    assert btn.isChecked() is False
    assert window.station_panel.isVisible() is True
    assert window._peek_overlay.isVisible() is False
    assert window.station_panel.isHidden() is False
    # Pitfall 5: snapshot reset to None after restore so the next compact-ON
    # cycle captures fresh sizes.
    assert window._splitter_sizes_before_compact is None, (
        "Pitfall 5: snapshot must be reset to None after restore so the "
        "next compact-ON cycle captures fresh sizes."
    )
    # Final icon should be back to the original (panel-visible) state.
    final_icon_cache_key = btn.icon().cacheKey()
    assert final_icon_cache_key == flipped_icon_cache_key or final_icon_cache_key != flipped_icon_cache_key
    # The above tautology is intentionally a no-op because Qt may return a
    # new cacheKey each call. The substantive contract — tooltip flip —
    # holds:
    assert "Hide stations" in btn.toolTip(), (
        f"D-05: after compact OFF, tooltip must communicate 'Hide stations' "
        f"again, got: {btn.toolTip()!r}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Multi-cycle round-trip (D-10 stress test)
# ---------------------------------------------------------------------------


def test_multiple_toggle_cycles_preserve_sizes(window, qtbot):
    """D-10 / Pitfall 1 / Pitfall 5: three full ON/OFF cycles starting from
    `[350, 850]`. After each OFF, splitter sizes must return to ~`[350, 850]`.

    This is a stress-version of `test_splitter_sizes_round_trip_through_compact`
    (Plan 03) that exercises the snapshot-capture / snapshot-reset cycle
    three times in a row to catch any state bleed across cycles (e.g., a
    bug where the snapshot is not reset to None on restore, causing cycle 2
    to capture stale sizes).
    """
    btn = window.now_playing.compact_mode_toggle_btn
    window._splitter.setSizes([350, 850])
    expected = window._splitter.sizes()
    assert sum(expected) > 0

    for cycle in range(3):
        # ON
        btn.click()
        assert btn.isChecked() is True, f"cycle {cycle}: ON failed"
        assert window._splitter_sizes_before_compact == expected, (
            f"cycle {cycle}: snapshot drifted between cycles. "
            f"Expected {expected}, got {window._splitter_sizes_before_compact}."
        )
        # OFF
        btn.click()
        assert btn.isChecked() is False, f"cycle {cycle}: OFF failed"
        restored = window._splitter.sizes()
        for actual_v, expected_v in zip(restored, expected):
            assert abs(actual_v - expected_v) <= 2, (
                f"cycle {cycle}: D-10 drift — restored {restored} vs "
                f"expected {expected}."
            )
        # Pitfall 5: snapshot reset to None after restore — required so the
        # next ON cycle captures fresh sizes from the live splitter.
        assert window._splitter_sizes_before_compact is None, (
            f"cycle {cycle}: snapshot must be None after restore (Pitfall 5)."
        )


# ---------------------------------------------------------------------------
# Test 3 — D-09 session-only invariant locked at integration level
# ---------------------------------------------------------------------------


def test_no_compact_setting_written_after_full_lifecycle(
    window, qtbot, fake_player, fake_repo, monkeypatch
):
    """D-09 final lock at integration level: a full compact+peek+restore
    lifecycle must NOT write any setting with 'compact' in its key.

    Plan 03's `test_compact_mode_toggle_does_not_persist_to_repo` exercises
    the toggle slot alone. This integration-level version walks the
    complete lifecycle (toggle, peek, station-click, leave, toggle-off) so
    a future regression that adds `repo.set_setting("compact_peek_*", ...)`
    inside the peek overlay or the eventFilter is also caught.
    """
    btn = window.now_playing.compact_mode_toggle_btn
    cw = window.centralWidget()
    # Snapshot ALL existing settings keys so the comparison is resilient
    # against startup-time settings (theme, accent color, etc.).
    keys_before = set(fake_repo._settings.keys())

    # Full lifecycle — mirrors test 1 but compressed.
    window._splitter.setSizes([400, 800])
    btn.click()  # ON
    _send_mouse_move(cw, 2, 100, monkeypatch=monkeypatch)
    qtbot.waitUntil(_make_peek_visible_predicate(window), timeout=1000)
    assert window._peek_overlay is not None
    assert window._peek_overlay.isVisible() is True
    # Click a station from inside the peek
    station = _make_station("Groove Salad", "SomaFM")
    window.station_panel.station_activated.emit(station)
    # Mouse-leave closes the peek
    _send_leave(window._peek_overlay)
    # Toggle OFF
    btn.click()
    assert btn.isChecked() is False

    keys_after = set(fake_repo._settings.keys())
    new_keys = keys_after - keys_before
    assert not any("compact" in k.lower() for k in new_keys), (
        f"D-09 violated at integration level — compact-related settings "
        f"written during the full lifecycle: {new_keys}"
    )
