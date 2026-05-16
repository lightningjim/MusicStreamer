"""Phase 72.1 / LAYOUT-02 — stream-picker reflow tests (Wave 0 TDD-RED scaffold).

Scope: When the now-playing panel narrows below the threshold where row 1 with
the stream picker can fit AND the active station has multiple streams,
`stream_combo` reparents into a dedicated second row beneath the existing
controls row; it returns to row 1 when width allows. Single-stream stations
stay one-row at all widths.

Wave 0 / TDD-RED state at landing
---------------------------------
This file lands as part of Plan 72.1-01 (Wave 0 scaffold). All 10 test
functions below MUST FAIL on Plan 01 commit and turn GREEN as Plans 02/03
land production code:

  * Plan 02 — adds ``self.controls`` (promoted from local), ``self._controls_row2``
    QHBoxLayout sibling under ``center``, ``resizeEvent`` override, and
    ``_reflow_stream_picker_row`` helper.
  * Plan 03 — adds the multi-to-single mid-narrow rehome hook into
    ``_populate_stream_picker``, the compact-mode integration regression,
    palette-after-reparent assertion, and the QA-05 source-grep lint.

The two negative-assertion tests
(``test_no_repo_set_setting_for_wrap_state``,
``test_no_lambda_in_reflow_wiring``) may pass by accident pre-Plan-02 because
no production code exists yet to trip them; they remain in place as
permanent regression locks.

Test names match ``.planning/phases/72.1-*/72.1-VALIDATION.md`` Per-Task
Verification Map verbatim — do NOT rename without updating the Validation
Map alongside.

Test inventory (Per-Task Verification Map)
------------------------------------------
  Sample points (a)-(h):
    1. test_wide_multi_stream_picker_in_row_1        — (a)
    2. test_narrow_multi_stream_picker_in_row_2      — (b)
    3. test_wide_single_stream_picker_hidden_in_row_1  — (c)
    4. test_narrow_single_stream_picker_hidden_in_row_1 — (d)
    5. test_signal_survives_round_trip               — (e)
    6. test_multi_to_single_mid_narrow_rehomes_picker — (f)
    7. test_compact_mode_and_picker_wrap_independent — (g)
    8. test_palette_survives_reparent                — (h)
  Negative assertions:
    9. test_no_repo_set_setting_for_wrap_state       — negative-1 (D-09 inheritance)
   10. test_no_lambda_in_reflow_wiring               — negative-2 (QA-05 lint)

Test doubles (FakePlayer, FakeRepo, _make_panel) mirror
``tests/test_phase72_now_playing_panel.py:34-102`` with one extension to
FakeRepo: ``list_streams`` accepts per-station injected stream lists so the
``_populate_stream_picker`` path can be exercised against multi-stream
stations.

Resize pattern: direct ``panel.resize(W, H)`` per
``.planning/phases/72.1-*/72.1-PATTERNS.md`` Pattern I — the established
repo convention (no pytest-qt resize-and-wait helpers; the offscreen
platform delivers ``resizeEvent`` to non-exposed widgets reliably enough
that no widget-exposure wait is needed).
"""
from __future__ import annotations

import inspect
from typing import Any, List, Optional

import pytest
from PySide6.QtCore import QObject, QSize, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QToolButton, QWidget

from musicstreamer.ui_qt import icons_rc  # noqa: F401  side-effect: registers :/icons
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
from musicstreamer.models import Station, StationStream


# ---------------------------------------------------------------------------
# Test doubles (mirror tests/test_phase72_now_playing_panel.py:34-102)
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
    """Phase-72 FakeRepo + Phase-72.1 `list_streams` injection extension.

    The only addition vs tests/test_phase72_now_playing_panel.py:68-96 is the
    `streams_by_station` ctor kwarg + `list_streams` method. The picker's
    `_populate_stream_picker` path calls `self._repo.list_streams(station.id)`
    (now_playing_panel.py:1116) — Phase 72.1 needs to drive multi-stream
    rendering via that call.
    """

    def __init__(
        self,
        settings: Optional[dict] = None,
        streams_by_station: Optional[dict[int, list]] = None,
    ) -> None:
        self._settings = dict(settings or {})
        self._favorites: list = []
        self._stations: list = []
        self._streams_by_station = dict(streams_by_station or {})

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

    def list_streams(self, station_id: int) -> list:
        return list(self._streams_by_station.get(station_id, []))


def _make_panel(
    qtbot,
    settings: Optional[dict] = None,
    streams_by_station: Optional[dict[int, list]] = None,
) -> NowPlayingPanel:
    repo = FakeRepo(settings or {"volume": "80"}, streams_by_station=streams_by_station)
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    return panel


def _make_multi_stream_station(
    stream_count: int = 3,
    station_id: int = 1,
    name: str = "Multi-Stream Test",
) -> Station:
    """Construct a Station with N StationStream rows."""
    streams = [
        StationStream(
            id=i + 1,
            station_id=station_id,
            url=f"http://example.test/{i + 1}",
            quality=f"q{i}",
            position=i + 1,
        )
        for i in range(stream_count)
    ]
    return Station(
        id=station_id,
        name=name,
        provider_id=None,
        provider_name="TestFM",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=streams,
        last_played_at=None,
    )


def _make_single_stream_station(
    station_id: int = 1,
    name: str = "Single-Stream Test",
) -> Station:
    """Same shape as _make_multi_stream_station but with one stream."""
    return _make_multi_stream_station(
        stream_count=1, station_id=station_id, name=name
    )


# ---------------------------------------------------------------------------
# Layout-walk assertion helper (mirrors 72.1-RESEARCH §Code Examples lines
# 600-616 and Pattern H from 72.1-PATTERNS.md)
# ---------------------------------------------------------------------------


def _assert_stream_combo_in_layout(
    panel: NowPlayingPanel, expected_layout: QHBoxLayout, msg: str = ""
) -> None:
    """Assert stream_combo is a child of `expected_layout` (controls or _controls_row2).

    Both layouts share NowPlayingPanel as the QObject parent (a QHBoxLayout's
    `addWidget` does not change a widget's QObject parent — only its layout
    membership), so cross-checking via `.parent()` always returns the panel.
    The authoritative membership check is `layout.indexOf(widget) >= 0`.
    """
    assert expected_layout.indexOf(panel.stream_combo) >= 0, (
        f"{msg}stream_combo not in expected layout "
        f"(indexOf={expected_layout.indexOf(panel.stream_combo)})"
    )
    assert panel.stream_combo.parent() is panel, (
        f"{msg}stream_combo's QObject parent should always be the NowPlayingPanel"
    )


# ---------------------------------------------------------------------------
# Sample-point tests (a)-(h)
# ---------------------------------------------------------------------------


def test_wide_multi_stream_picker_in_row_1(qtbot):
    """Sample (a): wide-window multi-stream → picker stays in row 1.

    Plan 02 promotes the local ``controls`` in ``NowPlayingPanel.__init__`` to
    ``self.controls`` so tests can address it.
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(1200, 800)

    _assert_stream_combo_in_layout(panel, panel.controls, "wide+multi: ")
    assert panel.stream_combo.isVisible(), (
        "Picker must be visible for a multi-stream station"
    )


def test_narrow_multi_stream_picker_in_row_2(qtbot):
    """Sample (b): narrow-window multi-stream → picker reparents to row 2.

    Per D-07, the picker uses QSizePolicy.Expanding horizontally when in row 2
    so it stretches to fill the row width.
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(560, 800)

    _assert_stream_combo_in_layout(panel, panel._controls_row2, "narrow+multi: ")
    assert panel.stream_combo.isVisible(), (
        "Picker remains visible after reparent (visibility decoupled from layout)"
    )
    assert (
        panel.stream_combo.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    ), "D-07: picker uses Expanding horizontal policy on row 2"


def test_wide_single_stream_picker_hidden_in_row_1(qtbot):
    """Sample (c): wide-window single-stream → picker hidden, stays in row 1.

    D-02: single-stream stations stay one-row at all widths.
    """
    station = _make_single_stream_station()
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(1200, 800)

    _assert_stream_combo_in_layout(panel, panel.controls, "wide+single: ")
    assert panel.stream_combo.isVisible() is False, (
        "Single-stream station: picker hidden (len(streams) > 1 gate fails)"
    )


def test_narrow_single_stream_picker_hidden_in_row_1(qtbot):
    """Sample (d): narrow-window single-stream → picker hidden, stays in row 1.

    D-02: single-stream stations stay one-row at all widths — no reparent
    logic runs when the picker is hidden.
    """
    station = _make_single_stream_station()
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(560, 800)

    _assert_stream_combo_in_layout(panel, panel.controls, "narrow+single: ")
    assert panel.stream_combo.isVisible() is False, (
        "Single-stream station: picker still hidden even at narrow width"
    )


def test_signal_survives_round_trip(qtbot):
    """Sample (e): width transitions (wide → narrow → wide) preserve picker
    signal connections, currentIndex, and itemData.

    Captures the signal-firing behavior across reparents — Qt's setParent /
    layout reparent does NOT disconnect signals (only ``~QObject()`` does;
    see Qt docs cited in 72.1-RESEARCH §Secondary sources).
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(1200, 800)
    _assert_stream_combo_in_layout(panel, panel.controls, "wide(initial): ")

    # Note: the `fired.append` lambda below is a TEST FILE lambda — QA-05
    # forbids lambda in PRODUCTION connects only (test 10 below grep-asserts
    # this in `NowPlayingPanel` source).
    fired: list = []
    panel.stream_combo.currentIndexChanged.connect(lambda i: fired.append(i))

    panel.stream_combo.setCurrentIndex(1)
    assert fired == [1], "Signal must fire in initial wide state"
    fired.clear()

    # Wrap to row 2
    panel.resize(560, 800)
    _assert_stream_combo_in_layout(panel, panel._controls_row2, "narrow: ")

    panel.stream_combo.setCurrentIndex(2)
    assert fired == [2], "Signal must still fire after reparent into row 2"
    fired.clear()

    # Round-trip back to row 1
    panel.resize(1200, 800)
    _assert_stream_combo_in_layout(panel, panel.controls, "wide(round-trip): ")

    panel.stream_combo.setCurrentIndex(0)
    assert fired == [0], "Signal must fire after reparent back to row 1"


def test_multi_to_single_mid_narrow_rehomes_picker(qtbot):
    """Sample (f): station change multi→single while in narrow state re-homes
    the picker to row 1.

    Per CONTEXT D-02 + RESEARCH §Pattern 2: when ``_populate_stream_picker``
    drives the picker visible→hidden (single-stream station), the picker must
    return to its default row-1 home regardless of the current width. Plan 03
    adds this extension hook to ``_populate_stream_picker``.
    """
    multi = _make_multi_stream_station(3)
    single = _make_single_stream_station(station_id=2, name="Switched-Single")
    panel = _make_panel(
        qtbot,
        streams_by_station={
            multi.id: list(multi.streams),
            single.id: list(single.streams),
        },
    )
    panel.bind_station(multi)
    panel.resize(560, 800)
    _assert_stream_combo_in_layout(panel, panel._controls_row2, "narrow+multi: ")

    # Mid-narrow station change to single-stream.
    panel.bind_station(single)

    _assert_stream_combo_in_layout(
        panel, panel.controls, "narrow→single rehome: "
    )
    assert panel.stream_combo.isVisible() is False, (
        "After switching to single-stream station, picker hidden"
    )


def test_compact_mode_and_picker_wrap_independent(qtbot):
    """Sample (g): compact mode + multi-stream + narrow — Phase 72 compact-toggle
    and Phase 72.1 width-driven reparent are independent state machines.

    Mounts a MainWindow (Phase 72.1 leans on Phase 72's compact toggle which
    is panel-aware via MainWindow wiring); toggles compact ON/OFF; verifies
    picker stays in row 2 regardless of compact state when window is narrow.
    """
    from musicstreamer.ui_qt.main_window import MainWindow
    from tests.test_main_window_integration import (
        FakePlayer as MWFakePlayer,
        FakeRepo as MWFakeRepo,
        _make_station as mw_make_station,
    )

    station = mw_make_station(name="Multi-Stream MW", provider="TestFM")
    streams = [
        StationStream(
            id=i + 1,
            station_id=station.id,
            url=f"http://example.test/{i + 1}",
            quality=f"q{i}",
            position=i + 1,
        )
        for i in range(3)
    ]
    repo = MWFakeRepo(stations=[station], settings={"volume": "80"})
    repo._streams_lookup = {station.id: streams}

    # Override list_streams on the MW FakeRepo instance to feed our streams.
    def _list_streams(station_id: int) -> list:
        return list(repo._streams_lookup.get(station_id, []))

    repo.list_streams = _list_streams  # type: ignore[assignment]

    window = MainWindow(MWFakePlayer(), repo)
    qtbot.addWidget(window)
    panel = window.now_playing
    panel.bind_station(station)
    window.resize(560, 800)

    # Picker should be on row 2 (width-driven trigger).
    _assert_stream_combo_in_layout(
        panel, panel._controls_row2, "narrow + compact-off: "
    )

    # Toggle compact ON.
    panel.compact_mode_toggle_btn.click()
    _assert_stream_combo_in_layout(
        panel, panel._controls_row2, "narrow + compact-on: "
    )

    # Toggle compact OFF.
    panel.compact_mode_toggle_btn.click()
    _assert_stream_combo_in_layout(
        panel, panel._controls_row2, "narrow + compact-off (round-trip): "
    )


def test_palette_survives_reparent(qtbot):
    """Sample (h): palette/style after reparent — no visual regression.

    Qt's QWidget propagates explicit palette roles from parent to child
    (see https://doc.qt.io/qt-6/qwidget.html#setParent). Layout reparenting
    does not change the QObject parent so the palette inheritance chain is
    fully preserved. This test pins the invariant in case a future refactor
    swaps `addWidget` for an `setParent`-then-`addWidget` sequence that
    inadvertently breaks inheritance.
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(1200, 800)

    pre = panel.stream_combo.palette()
    pre_roles = {
        role: pre.color(role).rgba()
        for role in (
            QPalette.Window,
            QPalette.WindowText,
            QPalette.Button,
            QPalette.ButtonText,
            QPalette.Text,
        )
    }

    panel.resize(560, 800)

    post = panel.stream_combo.palette()
    post_roles = {
        role: post.color(role).rgba()
        for role in (
            QPalette.Window,
            QPalette.WindowText,
            QPalette.Button,
            QPalette.ButtonText,
            QPalette.Text,
        )
    }

    assert pre_roles == post_roles, (
        f"Palette roles changed across reparent: "
        f"pre={pre_roles!r} post={post_roles!r}"
    )


# ---------------------------------------------------------------------------
# Negative-assertion tests (1)-(2)
# ---------------------------------------------------------------------------


def test_no_repo_set_setting_for_wrap_state(qtbot):
    """Negative (1): NO repo.set_setting call for any wrap-state key.

    Mirrors tests/test_phase72_compact_toggle.py:149-165 pattern. Locks D-09
    inheritance from Phase 72: layout state (row 1 / row 2) is recomputed on
    every resize event; no SQLite persistence.

    This test may PASS by accident in Wave 0 (no production code is writing
    any wrap-state keys yet) — that is acceptable and the test remains a
    permanent regression net for Plans 02/03.
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    fake_repo = panel._repo
    keys_before = set(fake_repo._settings.keys())

    panel.bind_station(station)
    # Sweep wide → narrow → wide → narrow to exercise reparent in both
    # directions multiple times.
    for w in (1200, 560, 1200, 560, 800):
        panel.resize(w, 800)

    keys_after = set(fake_repo._settings.keys())
    new_keys = keys_after - keys_before
    forbidden_fragments = ("wrap", "row2", "picker_row", "picker_position", "reflow")
    offending = {
        k for k in new_keys
        if any(frag in k.lower() for frag in forbidden_fragments)
    }
    assert not offending, (
        f"D-09 inheritance violated — wrap-state key(s) written to repo: {offending}"
    )


def test_no_lambda_in_reflow_wiring():
    """Negative (2): NO lambda in any reflow-helper wiring (QA-05).

    Mirrors tests/test_phase72_now_playing_panel.py:290-306 pattern. Source-
    grep style — runs without instantiating widgets.

    This test may PASS by accident in Wave 0 (no production
    `_reflow_stream_picker_row` / `_move_stream_picker_to` / `resizeEvent`
    method exists yet) — that is acceptable and it remains a permanent
    regression net for Plans 02/03.
    """
    src = inspect.getsource(NowPlayingPanel)
    targets = (
        "_reflow_stream_picker_row",
        "_move_stream_picker_to",
        "resizeEvent",
    )
    for line in src.splitlines():
        if any(t in line for t in targets):
            assert "lambda" not in line, (
                f"QA-05 violated — lambda on reflow-related line: {line!r}"
            )
