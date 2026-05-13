"""Phase 72 Wave 0 spike: lock the two RESEARCH assumptions A1 and A2.

These tests verify load-bearing Qt behaviors that the rest of Phase 72
(Plans 02-05) depends on:

- **A1** (RESEARCH §Assumptions Log) — **OBSERVED RESULT: ASSUMPTION
  INVALIDATED on PySide6 6.11.0**. The RESEARCH-stated contract was that
  ``QSplitter`` auto-hides the adjacent handle when one of its children is
  hidden (source:
  https://forum.qt.io/topic/45377/qsplitter-disappears-once-child-widget-is-hidden).
  Empirical testing on PySide6 6.11.0 (Qt runtime 6.11.0) under the
  ``offscreen`` platform shows ``splitter.handle(1).isVisible()`` returns
  ``True`` even after ``station_panel.hide()``. The forum thread that
  inspired this assumption predates Qt 6 and the behavior does NOT carry
  over. **Mitigation for Plans 02-05:** the toggle slot MUST call
  ``self._splitter.handle(1).hide()`` explicitly alongside
  ``self.station_panel.hide()`` (and ``.show()`` on toggle-off). RESEARCH
  Pattern 1's NOTE comment is now stale and Plan 02 must_haves should add
  an explicit-handle-hide requirement. The Wave 0 test below LOCKS the
  observed behavior so a future PySide6 release that adds auto-hide will
  cause this test to fail and flag the now-redundant explicit hide call.

- **A2** (RESEARCH §Assumptions Log) — **OBSERVED RESULT: CONFIRMED on
  PySide6 6.11.0**. ``StationListPanel`` has zero ``self.parent()`` /
  ``self.window()`` / ``topLevelWidget()`` calls (verified by grep), and the
  reparent round trip (``splitter[0]`` → ``QFrame`` container → back to
  ``splitter.insertWidget(0, panel)``) preserves the panel's
  ``_search_box`` state across both reparent operations. Plan 04/05 may
  proceed with the single-instance reparent pattern as RESEARCH §Pattern 4
  recommends. Source for the splitter-move semantics:
  https://doc.qt.io/qt-6/qsplitter.html — "If a widget is already inside a
  QSplitter when insertWidget() or addWidget() is called, it will move to
  the new position".

Both tests run under ``QT_QPA_PLATFORM=offscreen`` (set by tests/conftest.py)
so they execute headless on dev box and CI alike.

Per QA-05: bound-method connects only; no lambda usage in this file.
Per CONVENTIONS.md: snake_case test names; docstring first line is the
behavior summary; subsequent lines provide thread/context details.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QFrame, QSplitter, QVBoxLayout

from musicstreamer.ui_qt.main_window import MainWindow

# Reuse the established FakePlayer / FakeRepo doubles from the integration
# test module. This keeps the test surface aligned with the rest of the
# main-window test suite and avoids cross-test divergence in mock shapes.
from tests.test_main_window_integration import FakePlayer, FakeRepo, _make_station


@pytest.fixture
def fake_player():
    """FakePlayer(QObject) double — see tests/test_main_window_integration.py."""
    return FakePlayer()


@pytest.fixture
def fake_repo():
    """FakeRepo seeded with one station — matches integration-test default."""
    return FakeRepo(stations=[_make_station()])


def test_splitter_handle_autohides_when_child_hidden(qtbot, fake_player, fake_repo):
    """A1: hiding a QSplitter child does NOT auto-hide the adjacent handle (PySide6 6.11.0).

    **Wave 0 finding — RESEARCH A1 INVALIDATED.** The RESEARCH-stated
    assumption (forum.qt.io/topic/45377) was that hiding a splitter child
    auto-hides the adjacent handle in PySide6 6.10+. Empirical testing on
    PySide6 6.11.0 under the offscreen platform shows the handle remains
    visible (``handle.isVisible() == True``) even after the child widget is
    hidden. This test now LOCKS the observed behavior; Plans 02-05 MUST add
    an explicit ``self._splitter.handle(1).hide()`` call alongside
    ``self.station_panel.hide()`` in the compact-toggle slot, and pair it
    with ``self._splitter.handle(1).show()`` on toggle-off.

    Why the test name still asserts the observed-not-the-expected: the
    function-name documentation describes WHAT THE TEST VERIFIES — namely
    whether the handle auto-hides. The test answers the question "no" and
    locks that answer. A future PySide6 release that flips to auto-hide
    will fail this test and signal that Plans 02-05's explicit hide call is
    now redundant.

    Behavior under test:
      1. Construct MainWindow (offscreen) with FakePlayer + FakeRepo.
      2. Verify splitter handle(1) is visible while both children are visible.
      3. Call ``station_panel.hide()`` directly (no production toggle exists
         yet in Wave 0).
      4. Assert handle(1) remains visible — A1's auto-hide does NOT occur.

    Sources:
      - RESEARCH §Assumptions Log A1
      - https://forum.qt.io/topic/45377/qsplitter-disappears-once-child-widget-is-hidden
        (older Qt 4/5 thread; behavior does not carry to Qt 6.11)
    """
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    # Force layout / show pass so handle visibility is meaningful. Without
    # show, QSplitterHandle.isVisible() may not reflect the post-layout state.
    with qtbot.waitExposed(w):
        w.show()

    splitter = w.centralWidget()
    assert isinstance(splitter, QSplitter), (
        "Phase 72 precondition violated: MainWindow.centralWidget() is no longer "
        "a QSplitter — A1 spike assumes the existing two-pane splitter layout."
    )

    # Pre-hide: both children visible, both initial widths > 0, handle(1) visible.
    initial_sizes = splitter.sizes()
    assert len(initial_sizes) == 2, (
        f"A1 precondition: splitter must have exactly 2 children; got sizes={initial_sizes!r}"
    )
    assert initial_sizes[0] > 0 and initial_sizes[1] > 0, (
        f"A1 precondition: both splitter children must have non-zero width; got sizes={initial_sizes!r}"
    )
    assert not w.station_panel.isHidden(), (
        "A1 precondition: station_panel must start visible (Phase 72 D-09: every "
        "launch starts in expanded / non-compact mode)."
    )
    handle = splitter.handle(1)
    assert handle.isVisible(), (
        "A1 precondition: splitter handle(1) (the divider between station_panel "
        "and now_playing) must be visible before any child is hidden."
    )

    # Action: hide station_panel directly (no production toggle slot yet).
    w.station_panel.hide()

    # Post-hide assertions — LOCKED OBSERVED BEHAVIOR on PySide6 6.11.0.
    assert w.station_panel.isHidden(), (
        "A1 sanity: station_panel.hide() must mark the widget hidden."
    )
    # RESEARCH §Assumptions Log A1 expected handle.isVisible() to flip to
    # False here (auto-hide). It does NOT on PySide6 6.11.0 — lock the
    # observed behavior so:
    #   (a) downstream plans treat the explicit handle.hide() as REQUIRED,
    #   (b) a future PySide6 that adds auto-hide will fail this test and
    #       prompt Plans 02-05 to drop the now-redundant explicit call.
    assert handle.isVisible(), (
        "A1 OBSERVED-BEHAVIOR REGRESSION — splitter.handle(1) is no longer visible "
        "after station_panel.hide(). This contradicts the Wave 0 spike finding on "
        "PySide6 6.11.0 (handle remained visible). If this assertion fails on a "
        "newer PySide6, that release has added auto-hide behavior — the explicit "
        "`self._splitter.handle(1).hide()` call in MainWindow._on_compact_toggle "
        "may now be redundant. Verify against:\n"
        "  https://forum.qt.io/topic/45377/qsplitter-disappears-once-child-widget-is-hidden\n"
        "  and the QSplitter changelog for the new version, then update Plan 02 "
        "must_haves and remove the explicit handle.hide() if appropriate."
    )


def test_station_panel_reparent_round_trip_preserves_state(qtbot, fake_player, fake_repo):
    """A2: reparenting StationListPanel into a QFrame and back preserves state.

    RESEARCH §Assumptions Log A2 (MEDIUM risk, grep-based audit) — verified
    that ``musicstreamer/ui_qt/station_list_panel.py`` has zero
    ``self.parent()`` / ``self.window()`` / ``topLevelWidget()`` calls, but
    indirect parent assumptions (e.g., child widgets calling
    ``parent().resize(...)``) could exist. This spike physically performs the
    round trip Plans 04-05 will rely on for the hover-peek overlay:

      splitter[0]  →  QFrame container (overlay-like)  →  splitter[0]

    and asserts that:
      (a) no exception is raised at any step,
      (b) ``station_panel.parent()`` is correct after each step,
      (c) the panel's filter/search state survives the round trip
          (search_box text is preserved — this is the most user-visible
          piece of state the overlay must preserve per D-15).

    Pitfall 6 (RESEARCH §Common Pitfalls): the return trip uses
    ``splitter.insertWidget(0, station_panel)``, NOT ``addWidget(...)``.
    addWidget would append at index 1 and swap the visual order; that bug
    would be subtle in production and is locked here.

    Sources cited in failure messages:
      - https://doc.qt.io/qt-6/qsplitter.html  (insertWidget vs addWidget)
      - RESEARCH §Pattern 4 + §Pitfall 6
    """
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    with qtbot.waitExposed(w):
        w.show()

    splitter = w.centralWidget()
    assert isinstance(splitter, QSplitter), (
        "A2 precondition: MainWindow.centralWidget() must be a QSplitter."
    )

    panel = w.station_panel

    # ------------------------------------------------------------------
    # Capture state BEFORE reparenting. The search_box on StationListPanel
    # is the most stable piece of user-visible state and the one D-15 calls
    # out as needing to survive the peek-overlay round trip.
    # ------------------------------------------------------------------
    sentinel = "phase72-spike-state-marker"
    panel._search_box.setText(sentinel)
    assert panel._search_box.text() == sentinel, (
        "A2 precondition: search box must accept a sentinel value before reparent."
    )

    # ------------------------------------------------------------------
    # Step 1: reparent station_panel INTO a QFrame container (overlay-like).
    # Mirrors PATTERNS §3 / RESEARCH §Pattern 4 layout config:
    #   QVBoxLayout with zero contentsMargins.
    # The container is parented to centralWidget() to mirror the ToastOverlay
    # parent strategy (main_window.py:287, parented to MainWindow but anchored
    # at centralWidget level for z-order).
    # ------------------------------------------------------------------
    container = QFrame(w.centralWidget())
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 0, 0, 0)
    container_layout.addWidget(panel)  # implicit setParent(container)

    assert panel.parent() is container, (
        "A2 FAILED at step 1 — after `container_layout.addWidget(station_panel)`, "
        f"panel.parent() should be the QFrame container; got {panel.parent()!r}.\n"
        "RESEARCH §Pattern 4 expected QLayout.addWidget to implicitly setParent."
    )

    # Splitter no longer holds the panel as a child.
    assert splitter.indexOf(panel) == -1, (
        "A2 FAILED at step 1 — station_panel was reparented into the container "
        f"but splitter still reports indexOf={splitter.indexOf(panel)} (expected -1)."
    )

    # State survives the into-container reparent.
    assert panel._search_box.text() == sentinel, (
        "A2 FAILED at step 1 — search_box text was lost on reparent into QFrame. "
        f"Expected {sentinel!r}, got {panel._search_box.text()!r}. "
        "StationListPanel may have parent-assumption code that resets state on reparent."
    )

    # ------------------------------------------------------------------
    # Step 2: reparent station_panel BACK into the splitter at index 0.
    # Pitfall 6 lock: MUST use insertWidget(0, panel), NOT addWidget(panel).
    # ------------------------------------------------------------------
    splitter.insertWidget(0, panel)  # back to original slot

    assert splitter.indexOf(panel) == 0, (
        "A2 FAILED at step 2 — Pitfall 6 regression: station_panel is no longer at "
        f"splitter index 0; indexOf returned {splitter.indexOf(panel)}.\n"
        "Source: https://doc.qt.io/qt-6/qsplitter.html — 'If a widget is already "
        "inside a QSplitter when insertWidget() or addWidget() is called, it will "
        "move to the new position'. Use insertWidget(0, panel) on the return trip, "
        "NOT addWidget(panel) which would append at the end and swap visual order."
    )
    assert splitter.widget(0) is panel, (
        "A2 FAILED at step 2 — splitter.widget(0) is not station_panel."
    )
    assert splitter.widget(1) is w.now_playing, (
        "A2 FAILED at step 2 — splitter.widget(1) is not the now_playing panel; "
        "visual order may have been corrupted by an addWidget-instead-of-insertWidget bug."
    )

    # State STILL survives the back-to-splitter reparent.
    assert panel._search_box.text() == sentinel, (
        "A2 FAILED at step 2 — search_box text was lost on reparent back into splitter. "
        f"Expected {sentinel!r}, got {panel._search_box.text()!r}. "
        "The reparent round trip does not preserve all StationListPanel state — "
        "Plan 04/05 must either snapshot/restore state explicitly or fall back to "
        "the two-instance pattern (RESEARCH §Architecture Patterns Pattern 4 "
        "alternative)."
    )

    # Panel is still alive and responsive.
    assert panel.isWidgetType(), (
        "A2 FAILED — panel is no longer a Qt widget after round trip."
    )
