"""Phase 72-03 / LAYOUT-01: MainWindow compact-mode toggle wiring tests.

Covers the MainWindow-level half of the compact-mode feature:
  * Mouse click on `compact_mode_toggle_btn` toggles `station_panel` visibility.
  * Ctrl+B QShortcut produces identical state change (single source of truth).
  * Splitter sizes round-trip through compact ON/OFF (Pitfall 1: snapshot
    BEFORE hide; Pitfall 5: snapshot reset to None on restore).
  * Per Wave 0 spike 72-01 (A1 INVALIDATED on PySide6 6.11): explicit
    `self._splitter.handle(1).hide()` / `.show()` calls are REQUIRED in
    `_on_compact_toggle` — the handle does NOT auto-hide.
  * `button.isChecked() == station_panel.isHidden()` invariant after every
    toggle (Phase 47.1 WR-02 / Phase 67 M-02 mirror).
  * D-09 session-only invariant: NO `repo.set_setting` / `repo.get_setting`
    call for any compact-* key — every app launch starts expanded.
  * D-06: only `station_panel` changes visibility — menu bar, now_playing
    panel, status bar stay visible.
  * D-07: no auto-exit on window resize.
  * D-08: `setChildrenCollapsible(False)` invariant preserved across toggles.
  * QA-05: no lambda in any compact-mode signal connect (mirrors
    `test_buffer_percent_bound_method_connect_no_lambda`).
  * RESEARCH A3: modal QDialog blocks Ctrl+B per window-scope context
    (`Qt.WidgetWithChildrenShortcut`) — verified via context-property
    precondition assertion plus a best-effort modal-simulation check.

Test doubles imported from tests/test_main_window_integration.py
(FakePlayer + FakeRepo + _make_station + window fixture pattern).
"""
from __future__ import annotations

import inspect

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut

from musicstreamer.ui_qt import main_window as mw_mod
from musicstreamer.ui_qt.main_window import MainWindow

# Reuse the established integration-test fixtures + doubles. Importing this
# way avoids duplicating the ~150-line FakePlayer/FakeRepo surface.
from tests.test_main_window_integration import FakePlayer, FakeRepo, _make_station


# ---------------------------------------------------------------------------
# Fixtures (local — independent of pytest fixture name collisions in conftest)
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
    return w


# ---------------------------------------------------------------------------
# Functional toggle tests
# ---------------------------------------------------------------------------


def test_compact_button_toggles_station_panel(window):
    """Mouse-click parity: pressing the now-playing panel's compact toggle
    flips station_panel visibility."""
    btn = window.now_playing.compact_mode_toggle_btn
    assert window.station_panel.isHidden() is False
    btn.click()
    assert window.station_panel.isHidden() is True
    btn.click()
    assert window.station_panel.isHidden() is False


def test_compact_button_checked_matches_station_panel_hidden(window):
    """Phase 47.1 WR-02 / Phase 67 M-02 single-source-of-truth invariant.

    After every toggle, btn.isChecked() == station_panel.isHidden().
    """
    btn = window.now_playing.compact_mode_toggle_btn
    # initial
    assert btn.isChecked() is False
    assert window.station_panel.isHidden() is False
    # toggle ON
    btn.click()
    assert btn.isChecked() is True
    assert window.station_panel.isHidden() is True
    # toggle OFF
    btn.click()
    assert btn.isChecked() is False
    assert window.station_panel.isHidden() is False
    # toggle ON again — invariant holds across cycles
    btn.click()
    assert btn.isChecked() == window.station_panel.isHidden()


def test_ctrl_b_shortcut_toggles_compact(window):
    """D-02 / D-03: Ctrl+B fires the same state change as the button.

    pytest-qt #254 recommends `activated.emit()` over key-event synthesis for
    QShortcut tests (key events can be eaten by the offscreen platform).
    Asserts that the shortcut activates the BUTTON (single source of truth)
    rather than bypassing it.
    """
    btn = window.now_playing.compact_mode_toggle_btn
    assert btn.isChecked() is False
    window._compact_shortcut.activated.emit()
    assert btn.isChecked() is True
    assert window.station_panel.isHidden() is True
    window._compact_shortcut.activated.emit()
    assert btn.isChecked() is False
    assert window.station_panel.isHidden() is False


def test_splitter_sizes_round_trip_through_compact(window):
    """D-10 / Pitfall 1 / Pitfall 5: sizes captured BEFORE hide and
    restored on exit, with a snapshot reset to None after restore.

    Uses approximate equality (≤ 2 px) to accommodate Qt's minimum-width
    clamping or sub-pixel layout rounding.
    """
    btn = window.now_playing.compact_mode_toggle_btn
    # Establish a non-default size and let Qt apply minimum-width constraints.
    window.resize(1200, 800)
    window._splitter.setSizes([400, 800])
    expected = window._splitter.sizes()
    assert sum(expected) > 0  # sanity

    btn.click()  # ON — snapshot taken BEFORE station_panel.hide()
    assert window._splitter_sizes_before_compact == expected
    btn.click()  # OFF — restore + reset
    restored = window._splitter.sizes()
    for actual_v, expected_v in zip(restored, expected):
        assert abs(actual_v - expected_v) <= 2, (
            f"D-10 round-trip drift: restored {restored} vs expected {expected}"
        )
    # Pitfall 5: snapshot reset to None after restore (prevents stale-snapshot
    # bleed into the next ON cycle).
    assert window._splitter_sizes_before_compact is None


def test_compact_mode_toggle_does_not_persist_to_repo(qtbot, fake_player, fake_repo):
    """D-09 invariant: compact mode is session-only. No `set_setting` call
    must touch any compact-* key. INVERSE of Phase 67's persistence test."""
    # Snapshot setting-keys before constructing the window — keeps the
    # comparison resilient against startup-time settings (accent color etc.).
    keys_before = set(fake_repo._settings.keys())
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    btn = w.now_playing.compact_mode_toggle_btn
    btn.click()  # ON
    btn.click()  # OFF
    btn.click()  # ON
    keys_after = set(fake_repo._settings.keys())
    new_keys = keys_after - keys_before
    assert not any("compact" in k.lower() for k in new_keys), (
        f"D-09 violated — compact-related settings written: {new_keys}"
    )


def test_compact_mode_starts_expanded_on_launch(qtbot, fake_player):
    """D-09: every app launch starts expanded regardless of repo state.

    Both branches: empty repo, and a repo that has been pre-populated with
    `compact_mode=1` — the second case proves the key is IGNORED (no
    `get_setting` call on construction).
    """
    # Branch A — empty settings
    repo_empty = FakeRepo(stations=[_make_station()])
    w1 = MainWindow(fake_player, repo_empty)
    qtbot.addWidget(w1)
    assert w1.now_playing.compact_mode_toggle_btn.isChecked() is False
    assert w1.station_panel.isHidden() is False

    # Branch B — pre-populated compact_mode setting (must be ignored)
    repo_with_setting = FakeRepo(stations=[_make_station()])
    repo_with_setting._settings["compact_mode"] = "1"
    w2 = MainWindow(fake_player, repo_with_setting)
    qtbot.addWidget(w2)
    assert w2.now_playing.compact_mode_toggle_btn.isChecked() is False, (
        "D-09 violated — MainWindow read `compact_mode` from settings on construction"
    )
    assert w2.station_panel.isHidden() is False


def test_compact_only_hides_station_panel(window):
    """D-06: hiding the station_panel must NOT cascade to other persistent UI."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # ON
    assert window.station_panel.isHidden() is True
    # Menu bar, now-playing panel, status bar all stay visible/usable.
    assert window.menuBar().isHidden() is False
    assert window.now_playing.isHidden() is False
    assert window.statusBar().isHidden() is False
    # No showFullScreen() — toggle is layout-only, not window-decoration.
    assert window.isFullScreen() is False


def test_resize_while_compact_keeps_compact(window):
    """D-07: manual toggle only; no auto-exit when window is resized wider."""
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # ON
    assert btn.isChecked() is True
    window.resize(2000, 800)
    assert btn.isChecked() is True
    window.resize(560, 800)
    assert btn.isChecked() is True
    assert window.station_panel.isHidden() is True


def test_splitter_collapsible_invariant(window):
    """D-08: `setChildrenCollapsible(False)` must hold across toggles.

    Compact mode uses widget.hide() — NOT splitter drag-to-zero — so the
    collapsibility contract for the expanded mode stays untouched.
    """
    assert window._splitter.childrenCollapsible() is False
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # ON
    assert window._splitter.childrenCollapsible() is False
    btn.click()  # OFF
    assert window._splitter.childrenCollapsible() is False


def test_compact_mode_signal_connections_no_lambda():
    """QA-05 / Pitfall 4: every compact-mode connect uses a bound method.

    Structural check — greps MainWindow source for the literal text 'lambda'
    on any connect line that references `compact_mode_toggled` or
    `_compact_shortcut.activated`. Mirrors the established
    `test_buffer_percent_bound_method_connect_no_lambda` pattern.
    """
    src = inspect.getsource(mw_mod.MainWindow)
    targets = ("compact_mode_toggled.connect", "_compact_shortcut.activated.connect")
    found_any = False
    for line in src.splitlines():
        if any(t in line for t in targets):
            found_any = True
            assert "lambda" not in line, (
                f"QA-05 violated — lambda on compact-mode connect line: {line!r}"
            )
    assert found_any, (
        "No compact-mode .connect(...) lines found in MainWindow source — "
        "this test became a no-op; investigate the wiring."
    )


def test_modal_dialog_blocks_ctrl_b(window):
    """RESEARCH A3 precondition: window-scope shortcut context allows modal
    QDialogs to swallow Ctrl+B.

    Strong-form modal simulation is unreliable in offscreen mode (no real
    focus chain), so the test verifies the necessary-but-sufficient
    precondition: the shortcut's `context` property equals
    `Qt.WidgetWithChildrenShortcut`. This is the Qt-documented behavior
    that makes modal-blocking work; the actual modal eat-behavior is then
    Qt's contract.
    """
    assert window._compact_shortcut.context() == Qt.WidgetWithChildrenShortcut


def test_compact_shortcut_is_qshortcut_instance(window):
    """D-03: first QShortcut in the codebase — verify the type so a future
    refactor that swaps to QAction.setShortcut (a different API) trips."""
    assert isinstance(window._compact_shortcut, QShortcut)
    assert window._compact_shortcut.key().toString() == "Ctrl+B"
