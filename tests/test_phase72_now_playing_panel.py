"""Phase 72-02 / LAYOUT-01: NowPlayingPanel compact-mode toggle button tests.

Covers the panel-level half of the compact-mode feature:
  * compact_mode_toggle_btn QToolButton at the correct control-row position
    (after volume_slider, before controls.addStretch(1)) — UI-SPEC §Interaction
    Contract, corrected from CONTEXT D-04's pre-EQ/pre-volume description.
  * 28x28 button with 20x20 icon (matches star_btn / eq_toggle_btn precedent).
  * compact_mode_toggled = Signal(bool) emitted on toggle (bound-method connect,
    no lambda per QA-05).
  * Icon + tooltip flip via set_compact_button_icon(checked) helper.
  * D-09 session-only invariant: NO repo.set_setting call for compact-mode key
    inside NowPlayingPanel (the MainWindow slot is also forbidden from writing
    per the upstream design, but this file tests the panel-level half).

Test doubles mirror tests/test_now_playing_panel.py:1-90 (FakePlayer + FakeRepo).
"""
from __future__ import annotations

import inspect
from typing import Any, List, Optional

from PySide6.QtCore import QObject, QSize, Signal
from PySide6.QtWidgets import QToolButton, QWidget

from musicstreamer.ui_qt import icons_rc  # noqa: F401  side-effect: registers :/icons
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel


# ---------------------------------------------------------------------------
# Test doubles (mirror tests/test_now_playing_panel.py)
# ---------------------------------------------------------------------------


class FakePlayer(QObject):
    """Minimal QObject mirroring Player's Signal surface used by NowPlayingPanel."""

    title_changed = Signal(str)
    failover = Signal(object)
    offline = Signal(str)
    playback_error = Signal(str)
    elapsed_updated = Signal(int)
    buffer_percent = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.set_volume_calls: List[float] = []
        self.stop_called: bool = False
        self.pause_called: bool = False
        self.play_calls: list = []
        self.calls: List[tuple] = []

    def set_volume(self, v: float) -> None:
        self.set_volume_calls.append(v)

    def stop(self) -> None:
        self.stop_called = True

    def pause(self) -> None:
        self.pause_called = True

    def play(self, station, **kwargs) -> None:
        self.play_calls.append(station)

    def set_eq_enabled(self, enabled: bool) -> None:
        self.calls.append(("enabled", bool(enabled)))


class FakeRepo:
    def __init__(self, settings: Optional[dict] = None) -> None:
        self._settings = dict(settings or {})
        self._favorites: list = []
        self._stations: list = []

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value

    def is_favorited(self, station_name: str, track_title: str) -> bool:
        return any(f == (station_name, track_title) for f in self._favorites)

    def add_favorite(
        self, station_name: str, provider_name: str, track_title: str, genre: str
    ) -> None:
        key = (station_name, track_title)
        if key not in self._favorites:
            self._favorites.append(key)

    def remove_favorite(self, station_name: str, track_title: str) -> None:
        key = (station_name, track_title)
        if key in self._favorites:
            self._favorites.remove(key)

    def all_stations(self) -> list:
        return list(self._stations)


def _make_panel(qtbot, settings: Optional[dict] = None) -> NowPlayingPanel:
    panel = NowPlayingPanel(FakePlayer(), FakeRepo(settings or {"volume": "80"}))
    qtbot.addWidget(panel)
    return panel


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_compact_mode_toggle_button_present_at_far_right(qtbot):
    """D-04 + UI-SPEC §Interaction Contract: button is in the controls HBox
    AFTER volume_slider and BEFORE the trailing addStretch.

    Walks the controls layout to locate the volume_slider index, then asserts
    the next non-stretch item is compact_mode_toggle_btn.
    """
    panel = _make_panel(qtbot)

    assert hasattr(panel, "compact_mode_toggle_btn"), (
        "NowPlayingPanel must expose compact_mode_toggle_btn"
    )
    assert isinstance(panel.compact_mode_toggle_btn, QToolButton), (
        f"Expected QToolButton, got {type(panel.compact_mode_toggle_btn).__name__}"
    )

    # Locate the controls QHBoxLayout that contains the volume_slider.
    controls_layout = panel.volume_slider.parentWidget().layout()
    # The volume_slider's parent widget is the center container; the controls
    # row is a child layout of `center`. Walk all layouts to find the one
    # containing volume_slider.
    # Simpler approach: locate via QObject hierarchy — both volume_slider and
    # compact_mode_toggle_btn share the same parent widget (the center).
    assert panel.compact_mode_toggle_btn.parentWidget() is panel.volume_slider.parentWidget(), (
        "compact_mode_toggle_btn must share volume_slider's parent (the controls row)"
    )

    # Walk the layout containing volume_slider to verify ordering.
    found_layout = None

    def _walk_layouts(layout):
        nonlocal found_layout
        if found_layout is not None:
            return
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget() is panel.volume_slider:
                found_layout = layout
                return
            sub = item.layout()
            if sub is not None:
                _walk_layouts(sub)

    _walk_layouts(panel.layout())
    assert found_layout is not None, "Could not locate layout containing volume_slider"

    # Build the index map.
    items_in_order = []
    for i in range(found_layout.count()):
        item = found_layout.itemAt(i)
        if item.widget() is not None:
            items_in_order.append(("widget", item.widget()))
        elif item.spacerItem() is not None:
            items_in_order.append(("stretch", item.spacerItem()))
        else:
            items_in_order.append(("other", item))

    # Find indices.
    vol_idx = next(
        i for i, (kind, w) in enumerate(items_in_order)
        if kind == "widget" and w is panel.volume_slider
    )
    compact_idx = next(
        i for i, (kind, w) in enumerate(items_in_order)
        if kind == "widget" and w is panel.compact_mode_toggle_btn
    )
    stretch_idx = next(
        i for i, (kind, w) in enumerate(items_in_order)
        if kind == "stretch"
    )
    assert vol_idx < compact_idx < stretch_idx, (
        f"Order violation: volume_slider@{vol_idx} < compact@{compact_idx} < stretch@{stretch_idx}"
    )


def test_compact_button_size_and_icon_size(qtbot):
    """UI-SPEC §Spacing: 28x28 button with 20x20 icon — matches star_btn / eq_toggle_btn."""
    panel = _make_panel(qtbot)
    btn = panel.compact_mode_toggle_btn

    # setFixedSize sets minimumSize and maximumSize to the same value.
    assert btn.minimumSize() == QSize(28, 28), (
        f"Expected fixed size 28x28, got {btn.minimumSize().width()}x{btn.minimumSize().height()}"
    )
    assert btn.maximumSize() == QSize(28, 28)
    assert btn.iconSize() == QSize(20, 20), (
        f"Expected iconSize 20x20, got {btn.iconSize().width()}x{btn.iconSize().height()}"
    )


def test_compact_button_is_checkable(qtbot):
    """UI-SPEC §Compact-toggle button visual states: setCheckable(True), initial unchecked."""
    panel = _make_panel(qtbot)
    btn = panel.compact_mode_toggle_btn
    assert btn.isCheckable() is True
    assert btn.isChecked() is False


def test_compact_button_initial_tooltip(qtbot):
    """UI-SPEC §Copywriting Contract: initial tooltip 'Hide stations (Ctrl+B)' (panel visible)."""
    panel = _make_panel(qtbot)
    assert panel.compact_mode_toggle_btn.toolTip() == "Hide stations (Ctrl+B)"


def test_compact_button_icon_flips_per_state(qtbot):
    """D-05 + UI-SPEC §Interaction Contract: set_compact_button_icon(checked) flips
    icon + tooltip. Mirrors test_play_pause_icon_toggle at
    tests/test_now_playing_panel.py:290-298.
    """
    panel = _make_panel(qtbot)
    btn = panel.compact_mode_toggle_btn

    # Initial state (panel visible, "about to hide").
    assert btn.toolTip() == "Hide stations (Ctrl+B)"
    initial_cache_key = btn.icon().cacheKey()

    # Flip to checked (panel hidden, "about to show").
    panel.set_compact_button_icon(True)
    assert btn.toolTip() == "Show stations (Ctrl+B)"
    new_cache_key = btn.icon().cacheKey()
    assert new_cache_key != initial_cache_key, (
        "Icon cacheKey must differ between checked and unchecked states"
    )

    # Flip back to unchecked.
    panel.set_compact_button_icon(False)
    assert btn.toolTip() == "Hide stations (Ctrl+B)"
    restored_cache_key = btn.icon().cacheKey()
    assert restored_cache_key != new_cache_key, (
        "Icon cacheKey must differ when flipping back to unchecked"
    )


def test_compact_mode_toggled_signal_emits_on_click(qtbot):
    """LAYOUT-01 §key_links: btn.toggled -> _on_compact_btn_toggled -> compact_mode_toggled.emit.

    Uses qtbot.waitSignal twice (once per toggle) — receives True then False.
    """
    panel = _make_panel(qtbot)
    btn = panel.compact_mode_toggle_btn

    # Toggle ON: signal payload True.
    with qtbot.waitSignal(panel.compact_mode_toggled, timeout=1000) as blocker:
        btn.toggle()
    assert blocker.args == [True], f"Expected [True], got {blocker.args!r}"
    assert btn.isChecked() is True

    # Toggle OFF: signal payload False.
    with qtbot.waitSignal(panel.compact_mode_toggled, timeout=1000) as blocker:
        btn.toggle()
    assert blocker.args == [False], f"Expected [False], got {blocker.args!r}"
    assert btn.isChecked() is False


def test_compact_button_no_repo_setting_write(qtbot):
    """D-09 session-only (panel-level half): toggling the button must NOT write any
    'compact'-keyed setting into the repo. INVERSE of Phase 47.1 / Phase 67
    positive-persistence test.
    """
    fake_player = FakePlayer()
    fake_repo = FakeRepo({"volume": "80"})
    panel = NowPlayingPanel(fake_player, fake_repo)
    qtbot.addWidget(panel)

    keys_before = set(fake_repo._settings.keys())

    btn = panel.compact_mode_toggle_btn
    btn.toggle()  # ON
    btn.toggle()  # OFF
    btn.toggle()  # ON again

    keys_after = set(fake_repo._settings.keys())
    new_keys = keys_after - keys_before
    compact_keys = {k for k in new_keys if "compact" in k.lower()}
    assert not compact_keys, (
        f"D-09 violated — compact-mode key(s) written to repo by NowPlayingPanel: "
        f"{compact_keys}"
    )


def test_no_lambda_in_compact_connect():
    """QA-05 + RESEARCH Pitfall 4: the compact_mode_toggle_btn.toggled.connect line
    must use a bound method (no lambda). Mirrors
    tests/test_main_window_integration.py:631-652
    test_buffer_percent_bound_method_connect_no_lambda.
    """
    src = inspect.getsource(NowPlayingPanel)
    found = False
    for line in src.splitlines():
        if "compact_mode_toggle_btn.toggled.connect" in line:
            found = True
            assert "lambda" not in line, (
                f"QA-05 violated — lambda on compact_mode_toggle_btn.toggled.connect: {line!r}"
            )
    assert found, (
        "compact_mode_toggle_btn.toggled.connect line not found in NowPlayingPanel source"
    )
