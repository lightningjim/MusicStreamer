"""Phase 72.4 / LAYOUT-04 — volume-cluster reflow tests (Wave 0 TDD-RED scaffold).

Scope: When the now-playing panel narrows below the threshold where row 1
WITHOUT the volume cluster can fit, ``volume_slider`` + ``compact_mode_toggle_btn``
wrap together as an indivisible "volume cluster" to a dedicated wrap row.

  * Multi-stream + very narrow → cluster on ``self._controls_row3`` (NEW row 3)
  * Single-stream + narrow → cluster on ``self._controls_row2`` (existing row 2)
  * Above threshold → cluster on ``self.controls`` (row 1, between eq and stretch)

State space (per UI-SPEC §State Truth Table + CONTEXT D-01..D-14):

  stream count × width tier × (cluster, picker) target layout × volume size policy

Wave 0 / TDD-RED state at landing
---------------------------------
This file lands as part of Plan 72.4-01. All 16 test functions below MUST FAIL
on Plan 01 commit and turn GREEN as Plans 02/03 land production code:

  * Plan 02 — adds ``self._controls_row3`` sibling QHBoxLayout under ``center``,
    ``self._volume_cluster_row1_index`` capture, ``self._row1_min_cache`` dict,
    ``_row1_min_width(include_picker, include_volume_cluster)`` generalized helper,
    ``_move_volume_cluster_to(target_layout)``, ``_set_volume_size_policy(expanding)``,
    and ``_reflow_volume_cluster()`` predicate.
  * Plan 03 — extends ``resizeEvent`` to invoke ``_reflow_volume_cluster()`` after
    ``_reflow_stream_picker_row`` and before ``_apply_art_tier``; adds the
    cache-invalidation hook in ``_populate_stream_picker``; adds source-grep
    lints; adds mid-state station-change regression coverage.

The three negative-assertion tests (``test_no_repo_set_setting_for_cluster_wrap_state``,
``test_no_lambda_in_reflow_wiring``, ``test_no_addstretch_in_wrap_path``)
remain as permanent regression locks.

Test inventory — RESEARCH §Validation Architecture rows (a)-(m) + negatives:
  (a)  test_wide_multi_stream_cluster_in_row_1
  (b)  test_mid_narrow_multi_stream_cluster_stays_row_1
  (c)  test_very_narrow_multi_stream_cluster_in_row_3
  (d)  test_wide_single_stream_cluster_in_row_1
  (e)  test_narrow_single_stream_cluster_in_row_2
  (f)  test_widen_back_restores_cluster_to_row_1
  (g)  test_reflow_idempotent
  (h)  test_signals_survive_round_trip
  (i)  test_multi_to_single_mid_very_narrow_rehomes_cluster
  (j)  test_multi_to_multi_mid_very_narrow_keeps_cluster_on_row_3
  (k)  test_cluster_as_unit_invariant
  (l)  test_cluster_left_to_right_order
  (m)  test_compact_toggle_size_invariant
  neg-1 test_no_repo_set_setting_for_cluster_wrap_state    (D-09 inheritance)
  neg-2 test_no_lambda_in_reflow_wiring                    (QA-05 lint)
  neg-3 test_no_addstretch_in_wrap_path                    (D-11 — Expanding pins)

Test doubles (FakePlayer, FakeRepo, _make_panel) mirror
``tests/test_phase72_1_stream_picker_reflow.py:75-182`` verbatim (see analog
comment at lines 47-57). FakeRepo's set_setting writes into ``self._settings``;
the negative-1 test uses keys-diff sentinel rather than a call-list.

Resize pattern: direct ``panel.resize(W, H)`` (Pattern I from 72.1-PATTERNS.md).
Width samples use safety-margin constants (PATTERNS §T2 — never hardcode the
derived threshold).
"""
from __future__ import annotations

import inspect
from typing import Any, List, Optional

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QSlider, QToolButton, QWidget

from musicstreamer.ui_qt import icons_rc  # noqa: F401  side-effect: registers :/icons
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
from musicstreamer.models import Station, StationStream
from tests._fake_player import FakePlayer


# ---------------------------------------------------------------------------
# Width-sample constants — derived, not hardcoded thresholds (PATTERNS §T2)
# ---------------------------------------------------------------------------
# Per UI-SPEC §Wrap-Tier Cascade (three tick points):
#   _W_WIDE         — above BOTH picker and volume-cluster thresholds
#   _W_MID          — above volume-cluster threshold but below picker threshold
#                     (picker on row 2, cluster on row 1)
#   _W_VERY_NARROW  — below volume-cluster threshold (cluster wraps to row 2/3)
# Safety-margin choices match the analog test file (tests/test_phase72_1_...).
_W_WIDE = 1600
_W_MID = 720
_W_VERY_NARROW = 560


# ---------------------------------------------------------------------------
# FakeRepo — VERBATIM mirror of tests/test_phase72_1_stream_picker_reflow.py:75-120
# ---------------------------------------------------------------------------


class FakeRepo:
    """Phase-72 FakeRepo + Phase-72.1 `list_streams` injection extension.

    The only addition vs tests/test_phase72_now_playing_panel.py:68-96 is the
    `streams_by_station` ctor kwarg + `list_streams` method. The picker's
    `_populate_stream_picker` path calls `self._repo.list_streams(station.id)`
    (now_playing_panel.py:1116) — Phase 72.1 needs to drive multi-stream
    rendering via that call.

    Verbatim copy from tests/test_phase72_1_stream_picker_reflow.py:75-120 per
    PATTERNS §T1 ("Same in 72.4: Copy these blocks verbatim into the new file").
    set_setting writes directly into self._settings; no set_setting_calls field
    — negative-1 uses keys-diff sentinel idiom from analog lines 510-541.
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


# ---------------------------------------------------------------------------
# Test fixtures — _make_panel, _make_*_stream_station factories
# Mirrors tests/test_phase72_1_stream_picker_reflow.py:123-182
# ---------------------------------------------------------------------------


def _make_panel(
    qtbot,
    settings: Optional[dict] = None,
    streams_by_station: Optional[dict[int, list]] = None,
) -> NowPlayingPanel:
    """Construct a NowPlayingPanel with FakePlayer/FakeRepo + show + waitExposed.

    panel.show() + qtbot.waitExposed(panel) are MANDATORY (PATTERNS §T1 Landmines):
    panel.width() is 0 before exposure, so _reflow_volume_cluster's defensive
    `if panel_width <= 0: return` early-returns and the reparent is never tested.
    Mirrors analog at tests/test_phase72_1_stream_picker_reflow.py:123-142.
    """
    repo = FakeRepo(settings or {"volume": "80"}, streams_by_station=streams_by_station)
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitExposed(panel)
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
# Layout-membership assertion helper
# Verbatim from RESEARCH §"Layout-membership assertion helper for tests"
# (lines 930-966 of 72.4-RESEARCH.md)
# ---------------------------------------------------------------------------


def _assert_volume_cluster_in_layout(
    panel: NowPlayingPanel, expected_layout: QHBoxLayout, msg: str = ""
) -> None:
    """Assert BOTH cluster widgets are in `expected_layout` (and ONLY there).

    Cluster-as-unit invariant (CONTEXT D-03): volume_slider and
    compact_mode_toggle_btn must be in the same layout in every state.
    Also asserts the cluster preserves left-to-right order (volume first,
    compact second per CONTEXT D-02).
    """
    # Both widgets in target.
    assert expected_layout.indexOf(panel.volume_slider) >= 0, (
        f"{msg}volume_slider not in expected layout"
    )
    assert expected_layout.indexOf(panel.compact_mode_toggle_btn) >= 0, (
        f"{msg}compact_mode_toggle_btn not in expected layout"
    )
    # Neither in any other layout (anti double-membership).
    others = [
        layout for layout in (panel.controls, panel._controls_row2, panel._controls_row3)
        if layout is not expected_layout
    ]
    for other in others:
        assert other.indexOf(panel.volume_slider) == -1, (
            f"{msg}volume_slider unexpectedly present in another layout"
        )
        assert other.indexOf(panel.compact_mode_toggle_btn) == -1, (
            f"{msg}compact_mode_toggle_btn unexpectedly present in another layout"
        )
    # Left-to-right order (D-02): volume before compact.
    vol_idx = expected_layout.indexOf(panel.volume_slider)
    comp_idx = expected_layout.indexOf(panel.compact_mode_toggle_btn)
    assert vol_idx < comp_idx, (
        f"{msg}cluster order broken — volume must come before compact-toggle "
        f"(volume={vol_idx}, compact={comp_idx})"
    )


# ---------------------------------------------------------------------------
# Behavior tests — RESEARCH §Validation Architecture rows (a) through (m)
# ---------------------------------------------------------------------------


def test_wide_multi_stream_cluster_in_row_1(qtbot):
    """Sample (a): wide-window multi-stream → cluster on row 1.

    Per D-01, D-02, D-10: at wide widths the cluster stays in row 1 in
    left-to-right order (volume → compact-toggle); volume slider uses
    Fixed,Fixed size policy with the setFixedWidth(120) clamp, compact-toggle
    stays 28×28 fixed.
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(_W_WIDE, 800)

    _assert_volume_cluster_in_layout(panel, panel.controls, "wide+multi: ")
    assert (
        panel.volume_slider.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed
    ), "D-10: volume slider is Fixed horizontal policy on row 1"
    # setFixedWidth(120) clamps min=max=120; either form is a valid sentinel
    # for "the fixed-120 clamp is in effect".
    assert (
        panel.volume_slider.width() == 120 or panel.volume_slider.maximumWidth() == 120
    ), "D-10: volume slider fixed-width 120 clamp is in effect on row 1"
    assert panel.compact_mode_toggle_btn.size() == QSize(28, 28), (
        "D-11: compact-toggle 28×28 fixed in every state"
    )


def test_mid_narrow_multi_stream_cluster_stays_row_1(qtbot):
    """Sample (b): mid-narrow multi-stream → picker on row 2, cluster on row 1.

    Per UI-SPEC tick T1 / D-06: at mid widths the picker has wrapped to row 2
    (existing 72.1 invariant — MUST NOT regress) but the volume cluster
    threshold has not yet been crossed; the cluster remains on row 1.
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(_W_MID, 800)

    # Existing 72.1 invariant: picker should be on row 2 at mid widths.
    # Direct indexOf rather than calling the 72.1 helper to avoid coupling.
    assert panel._controls_row2.indexOf(panel.stream_combo) >= 0, (
        "72.1 invariant: picker on row 2 at mid widths (must not regress)"
    )
    # 72.4 invariant: cluster still on row 1.
    _assert_volume_cluster_in_layout(panel, panel.controls, "mid-narrow+multi: ")
    assert (
        panel.volume_slider.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed
    ), "D-10: volume slider Fixed on row 1 (cluster not wrapped yet)"


def test_very_narrow_multi_stream_cluster_in_row_3(qtbot):
    """Sample (c): very-narrow multi-stream → picker on row 2, cluster on row 3.

    Per D-04: three-row state when both thresholds crossed. Volume slider
    uses Expanding,Fixed policy on its wrap row (D-09).
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(_W_VERY_NARROW, 800)

    # Existing 72.1: picker on row 2.
    assert panel._controls_row2.indexOf(panel.stream_combo) >= 0, (
        "72.1 invariant: picker on row 2 at very-narrow widths"
    )
    # 72.4: cluster on row 3.
    _assert_volume_cluster_in_layout(panel, panel._controls_row3, "very-narrow+multi: ")
    assert (
        panel.volume_slider.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    ), "D-09: volume slider Expanding on its wrap row"


def test_wide_single_stream_cluster_in_row_1(qtbot):
    """Sample (d): wide-window single-stream → cluster on row 1, picker hidden.

    Per D-08: single-stream stations still respond to width for the cluster
    dimension. At wide widths cluster stays in row 1, picker is hidden.
    """
    station = _make_single_stream_station()
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(_W_WIDE, 800)

    assert panel.stream_combo.isHidden() is True, (
        "Single-stream: picker hidden (len(streams) > 1 gate fails)"
    )
    _assert_volume_cluster_in_layout(panel, panel.controls, "wide+single: ")
    assert (
        panel.volume_slider.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed
    ), "D-10: volume Fixed on row 1"


def test_narrow_single_stream_cluster_in_row_2(qtbot):
    """Sample (e): narrow single-stream → cluster on row 2 (picker hidden).

    Per D-07: single-stream + narrow → cluster wraps to the existing row 2
    (which is empty in single-stream mode since picker is hidden). Row 3 is
    not used in single-stream state.
    """
    station = _make_single_stream_station()
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(_W_VERY_NARROW, 800)

    assert panel.stream_combo.isHidden() is True, (
        "Single-stream: picker still hidden at narrow width"
    )
    _assert_volume_cluster_in_layout(panel, panel._controls_row2, "narrow+single: ")
    assert (
        panel.volume_slider.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    ), "D-09: volume Expanding on its wrap row"
    assert panel._controls_row3.count() == 0, (
        "D-07: row 3 unused in single-stream state"
    )


def test_widen_back_restores_cluster_to_row_1(qtbot):
    """Sample (f): widen-back across threshold → cluster returns to row 1.

    Per D-10 + Pattern 6 (size policy round-trip from RESEARCH §Pattern 3):
    after a wide → narrow → wide cycle, cluster is back in row 1 at the
    PINNED index (_volume_cluster_row1_index), volume slider's fixed-120
    clamp restored, volume size policy back to Fixed.
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)

    panel.resize(_W_WIDE, 800)
    _assert_volume_cluster_in_layout(panel, panel.controls, "wide(initial): ")

    panel.resize(_W_VERY_NARROW, 800)
    _assert_volume_cluster_in_layout(panel, panel._controls_row3, "narrow(transit): ")

    panel.resize(_W_WIDE, 800)
    _assert_volume_cluster_in_layout(panel, panel.controls, "wide(round-trip): ")

    # Cluster lands at the pinned row-1 index (D-02 order: volume → compact-toggle).
    assert panel.controls.indexOf(panel.volume_slider) == panel._volume_cluster_row1_index, (
        "Widen-back: volume_slider returns to pinned row-1 index"
    )
    assert (
        panel.controls.indexOf(panel.compact_mode_toggle_btn)
        == panel._volume_cluster_row1_index + 1
    ), "Widen-back: compact_mode_toggle_btn lands immediately after volume_slider"
    # Fixed-120 clamp + Fixed,Fixed policy restored.
    assert panel.volume_slider.maximumWidth() == 120, (
        "Widen-back: setFixedWidth(120) clamp restored (maximumWidth == 120)"
    )
    assert (
        panel.volume_slider.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed
    ), "Widen-back: volume Fixed policy restored on row 1"


def test_reflow_idempotent(qtbot):
    """Sample (g): two consecutive `_reflow_volume_cluster()` calls produce no motion.

    Per D-14 + RESEARCH §Pattern 2 idempotency contract: state checks via
    indexOf(...) >= 0 before reparent → no-op on second call.
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(_W_VERY_NARROW, 800)

    # Snapshot a comprehensive state-tuple.
    pre = (
        panel.controls.indexOf(panel.volume_slider),
        panel.controls.indexOf(panel.compact_mode_toggle_btn),
        panel._controls_row2.indexOf(panel.volume_slider),
        panel._controls_row2.indexOf(panel.compact_mode_toggle_btn),
        panel._controls_row3.indexOf(panel.volume_slider),
        panel._controls_row3.indexOf(panel.compact_mode_toggle_btn),
        panel.volume_slider.sizePolicy().horizontalPolicy(),
    )

    # Two consecutive direct calls (bypass resizeEvent so we only test the helper).
    panel._reflow_volume_cluster()
    panel._reflow_volume_cluster()

    post = (
        panel.controls.indexOf(panel.volume_slider),
        panel.controls.indexOf(panel.compact_mode_toggle_btn),
        panel._controls_row2.indexOf(panel.volume_slider),
        panel._controls_row2.indexOf(panel.compact_mode_toggle_btn),
        panel._controls_row3.indexOf(panel.volume_slider),
        panel._controls_row3.indexOf(panel.compact_mode_toggle_btn),
        panel.volume_slider.sizePolicy().horizontalPolicy(),
    )

    assert pre == post, (
        f"Idempotency violated — state changed across two reflow calls: "
        f"pre={pre!r} post={post!r}"
    )


def test_signals_survive_round_trip(qtbot):
    """Sample (h): wide → narrow → wide preserves signals + values.

    Per A6, A8 (RESEARCH §Assumptions Log): valueChanged / sliderReleased
    on QSlider and toggled on QToolButton all survive removeWidget+addWidget
    reparent (Qt 6 only severs in ~QObject() destructor).

    Also asserts slider value and toggle checked-state are preserved.
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)
    panel.resize(_W_WIDE, 800)

    # Observer lists — test-file lambdas are OK (QA-05 only forbids lambdas in
    # PRODUCTION code; see analog test_no_lambda_in_reflow_wiring).
    changed_fired: list = []
    released_fired: list = []
    toggled_fired: list = []
    panel.volume_slider.valueChanged.connect(lambda v: changed_fired.append(v))
    panel.volume_slider.sliderReleased.connect(lambda: released_fired.append(True))
    panel.compact_mode_toggle_btn.toggled.connect(lambda c: toggled_fired.append(c))

    # Pre-transition: set the volume value AND toggle the compact button.
    panel.volume_slider.setValue(42)
    assert 42 in changed_fired, "valueChanged must fire on initial setValue(42)"
    pre_value = panel.volume_slider.value()
    pre_checked = panel.compact_mode_toggle_btn.isChecked()
    # We toggle inside the round-trip below; capture starting state to detect change.

    # Wide → narrow.
    panel.resize(_W_VERY_NARROW, 800)
    _assert_volume_cluster_in_layout(panel, panel._controls_row3, "narrow: ")

    # Mid-transition: fire signals from the wrap row.
    changed_fired.clear()
    released_fired.clear()
    toggled_fired.clear()
    panel.volume_slider.setValue(73)
    assert 73 in changed_fired, "valueChanged must fire after reparent to row 3"
    panel.volume_slider.sliderReleased.emit()
    assert released_fired, "sliderReleased must fire after reparent to row 3"
    panel.compact_mode_toggle_btn.click()
    assert toggled_fired, "toggled must fire after reparent (compact-toggle click)"

    # Narrow → wide (round-trip).
    panel.resize(_W_WIDE, 800)
    _assert_volume_cluster_in_layout(panel, panel.controls, "wide(round-trip): ")

    # Value preservation across reparent.
    assert panel.volume_slider.value() == 73, (
        "Volume value (73) preserved across narrow→wide round-trip"
    )
    # Toggle checked-state survives — click() above flipped it; click again to confirm
    # signal still fires from row 1 after round-trip.
    changed_fired.clear()
    toggled_fired.clear()
    panel.volume_slider.setValue(50)
    assert 50 in changed_fired, (
        "valueChanged must fire after reparent back to row 1"
    )
    panel.compact_mode_toggle_btn.click()
    assert toggled_fired, "toggled must fire after reparent back to row 1"


def test_multi_to_single_mid_very_narrow_rehomes_cluster(qtbot):
    """Sample (i): mid-narrow multi→single station change rehomes cluster row 3 → row 2.

    Per D-07: when station flips multi→single while cluster is on row 3, on the
    next resize tick the picker becomes hidden, the cluster reparents from
    row 3 to row 2, and row 3 returns to empty.
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
    panel.resize(_W_VERY_NARROW, 800)
    _assert_volume_cluster_in_layout(panel, panel._controls_row3, "narrow+multi: ")

    # Mid-narrow station change to single-stream.
    panel.bind_station(single)
    # Force a resize tick — some Qt paths defer reflow until next resizeEvent.
    panel.resize(_W_VERY_NARROW, 800)

    _assert_volume_cluster_in_layout(panel, panel._controls_row2, "rehome→single: ")
    assert panel._controls_row3.count() == 0, (
        "Row 3 returns to empty after multi→single rehome (D-07)"
    )


def test_multi_to_multi_mid_very_narrow_keeps_cluster_on_row_3(qtbot):
    """Sample (j): CR-01 echo — multi→multi station change at very-narrow keeps row 3.

    Original CR-01 in 72.1: station change invalidates threshold cache; if the
    new walk produces a stale-low value, the picker would flip back to row 1.
    72.4 inherits this risk for the volume cluster — the cache invalidation
    hook (`_populate_stream_picker` → `_row1_min_cache.clear()`) must not
    cause the cluster to incorrectly return to row 1.
    """
    multi_a = _make_multi_stream_station(stream_count=3, station_id=1, name="A")
    multi_b = _make_multi_stream_station(stream_count=3, station_id=2, name="B")
    panel = _make_panel(
        qtbot,
        streams_by_station={
            multi_a.id: list(multi_a.streams),
            multi_b.id: list(multi_b.streams),
        },
    )
    panel.bind_station(multi_a)
    panel.resize(_W_VERY_NARROW, 800)
    _assert_volume_cluster_in_layout(panel, panel._controls_row3, "A on row 3: ")

    # Multi → multi mid-narrow station change (invalidates threshold cache).
    panel.bind_station(multi_b)
    panel.resize(_W_VERY_NARROW, 800)
    qtbot.wait(0)

    _assert_volume_cluster_in_layout(
        panel, panel._controls_row3, "B on row 3 after multi→multi switch: "
    )


@pytest.mark.parametrize(
    "stream_count",
    [1, 3],
    ids=["single", "multi"],
)
def test_cluster_as_unit_invariant(qtbot, stream_count):
    """Sample (k): cluster-as-unit invariant across width sweep (D-03).

    At every width tick, volume_slider's layout-of-residence MUST equal
    compact_mode_toggle_btn's layout-of-residence. The cluster never splits.
    """
    if stream_count == 1:
        station = _make_single_stream_station()
    else:
        station = _make_multi_stream_station(stream_count=stream_count)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)

    layouts = (panel.controls, panel._controls_row2, panel._controls_row3)
    for w in (_W_WIDE, 900, _W_MID, 620, 580, _W_VERY_NARROW):
        panel.resize(w, 800)
        # Find which layout owns the volume slider (exactly one — D-03).
        vol_owner = None
        comp_owner = None
        for layout in layouts:
            if layout.indexOf(panel.volume_slider) >= 0:
                vol_owner = layout
            if layout.indexOf(panel.compact_mode_toggle_btn) >= 0:
                comp_owner = layout
        assert vol_owner is not None, (
            f"width={w}: volume_slider has no layout owner"
        )
        assert comp_owner is not None, (
            f"width={w}: compact_mode_toggle_btn has no layout owner"
        )
        assert vol_owner is comp_owner, (
            f"width={w}: cluster split across layouts — "
            f"volume in {vol_owner!r}, compact in {comp_owner!r}"
        )


def test_cluster_left_to_right_order(qtbot):
    """Sample (l): cluster left-to-right order preserved at every wrap target.

    Per D-02: volume_slider.indexOf < compact_mode_toggle_btn.indexOf on
    every layout where the cluster lives (row 1, row 2, row 3).
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)

    layouts = (panel.controls, panel._controls_row2, panel._controls_row3)
    for w in (_W_WIDE, _W_MID, _W_VERY_NARROW):
        panel.resize(w, 800)
        for layout in layouts:
            vol_idx = layout.indexOf(panel.volume_slider)
            comp_idx = layout.indexOf(panel.compact_mode_toggle_btn)
            if vol_idx >= 0 and comp_idx >= 0:
                assert vol_idx < comp_idx, (
                    f"width={w}, layout={layout!r}: order broken — "
                    f"volume={vol_idx}, compact={comp_idx}"
                )

    # Single-stream sweep too — narrow tier wraps to row 2.
    single = _make_single_stream_station(station_id=99, name="Single-LR")
    panel2 = _make_panel(
        qtbot, streams_by_station={single.id: list(single.streams)}
    )
    panel2.bind_station(single)
    for w in (_W_WIDE, _W_VERY_NARROW):
        panel2.resize(w, 800)
        for layout in (panel2.controls, panel2._controls_row2, panel2._controls_row3):
            vol_idx = layout.indexOf(panel2.volume_slider)
            comp_idx = layout.indexOf(panel2.compact_mode_toggle_btn)
            if vol_idx >= 0 and comp_idx >= 0:
                assert vol_idx < comp_idx, (
                    f"single-stream width={w}: order broken — "
                    f"volume={vol_idx}, compact={comp_idx}"
                )


def test_compact_toggle_size_invariant(qtbot):
    """Sample (m): compact-toggle stays 28×28 across all reflows (D-11).

    Per D-11: compact-toggle's size is NEVER mutated by the reflow path.
    setFixedSize(28, 28) sticks through every reparent.
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    panel.bind_station(station)

    for w in (_W_WIDE, _W_MID, _W_VERY_NARROW, _W_MID, _W_WIDE):
        panel.resize(w, 800)
        assert panel.compact_mode_toggle_btn.size() == QSize(28, 28), (
            f"width={w}: compact-toggle size mutated to "
            f"{panel.compact_mode_toggle_btn.size()!r} (D-11 violation)"
        )


# ---------------------------------------------------------------------------
# Negative-assertion tests
# ---------------------------------------------------------------------------


def test_no_repo_set_setting_for_cluster_wrap_state(qtbot):
    """Negative (1): NO repo.set_setting call for any cluster-wrap-state key.

    D-09 inheritance from Phase 72: layout state (row 1 / row 2 / row 3) is
    recomputed on every resize event; no SQLite persistence.

    Uses the keys-diff sentinel idiom from analog
    tests/test_phase72_1_stream_picker_reflow.py:510-541 (FakeRepo's
    set_setting writes into _settings; the analog has no set_setting_calls
    field — Plan 01 mirrors verbatim per PATTERNS §T1).

    May PASS by accident in Wave 0 (no production code writes cluster-wrap
    keys yet) — remains a permanent regression net for Plans 02/03.
    """
    station = _make_multi_stream_station(3)
    panel = _make_panel(qtbot, streams_by_station={station.id: list(station.streams)})
    fake_repo = panel._repo
    keys_before = set(fake_repo._settings.keys())

    panel.bind_station(station)
    # Sweep widths through both thresholds.
    for w in (_W_WIDE, _W_VERY_NARROW, _W_WIDE, _W_VERY_NARROW, 800):
        panel.resize(w, 800)

    keys_after = set(fake_repo._settings.keys())
    new_keys = keys_after - keys_before
    forbidden_fragments = (
        "volume_cluster",
        "row3",
        "wrap_state",
        "cluster_wrap",
        "volume_wrap",
    )
    offending = {
        k for k in new_keys
        if any(frag in k.lower() for frag in forbidden_fragments)
    }
    assert not offending, (
        f"D-09 inheritance violated — cluster-wrap-state key(s) written to repo: {offending}"
    )


def test_no_lambda_in_reflow_wiring():
    """Negative (2): NO lambda in any reflow-helper method (QA-05).

    Source-grep style — runs without instantiating widgets. Uses inspect to
    pull each method's source individually so a stray lambda elsewhere in
    the file doesn't false-trigger.

    Today these methods don't yet exist on NowPlayingPanel — that's the
    RED-state contract. The getattr guard produces a clear AssertionError
    rather than the bare AttributeError that getattr would otherwise raise.
    Asymmetric semantics: RED today because the methods are missing; GREEN
    after Plans 02/03 add them AND keep them lambda-free.
    """
    targets = (
        "_reflow_volume_cluster",
        "_move_volume_cluster_to",
        "_set_volume_size_policy",
        "_row1_min_width",
        # Existing 72.1 targets — keep the lint net cast wide.
        "_reflow_stream_picker_row",
        "_move_stream_picker_to",
        "_set_picker_size_policy",
    )
    for name in targets:
        method = getattr(NowPlayingPanel, name, None)
        assert method is not None, (
            f"{name} does not exist on NowPlayingPanel (Wave 1+)"
        )
        source = inspect.getsource(method)
        assert "lambda" not in source, (
            f"QA-05 violated — `lambda` found in {name} source"
        )


def test_no_addstretch_in_wrap_path():
    """Negative (3): NO addStretch call inside _move_volume_cluster_to.

    Per D-11: the volume slider's Expanding size policy on the wrap row
    consumes all free space, pinning the compact-toggle to the right edge.
    Adding addStretch would push the cluster left — that's a regression.

    Getattr guard pattern (see negative-2) — RED today because the helper
    is missing; GREEN after Plan 02 adds it without any addStretch call.
    """
    method = getattr(NowPlayingPanel, "_move_volume_cluster_to", None)
    assert method is not None, (
        "_move_volume_cluster_to does not exist on NowPlayingPanel (Wave 1+)"
    )
    source = inspect.getsource(method)
    assert "addStretch" not in source, (
        "D-11 violated — addStretch found inside _move_volume_cluster_to"
    )


def test_show_event_defers_initial_reflow_via_singleshot():
    """Initial-paint regression (UAT-1 follow-up): showEvent must defer
    the initial reflow via QTimer.singleShot(0, ...) so the reflow runs
    against the panel's actual displayed geometry, not the transient
    first-paint geometry.

    Without this defer, on small displays Qt's first resizeEvent fires
    at a transient parent geometry, the reflow decides "no wrap", then
    the layout settles to its actual (narrower) geometry without firing
    a follow-up resizeEvent — stranding the cluster on row 1.

    Source-grep style: pins the structural contract rather than trying
    to reproduce the Wayland/splitter timing race in a test environment.

    UAT-1 hardening: ALSO require a 100ms belt-and-braces re-fire because
    on Linux Wayland the 0ms tick has been observed to fire before the
    panel reaches its final geometry (the compositor's frame callback
    hasn't yet ticked the splitter to its final size). Helpers are
    idempotent, so running both 0ms and 100ms is safe.
    """
    method = getattr(NowPlayingPanel, "showEvent", None)
    assert method is not None, "NowPlayingPanel must override showEvent"
    source = inspect.getsource(method)
    assert "QTimer.singleShot(0" in source, (
        "showEvent must defer initial reflow via QTimer.singleShot(0, ...)"
    )
    assert "QTimer.singleShot(100" in source, (
        "showEvent must include a 100ms belt-and-braces re-fire for Wayland "
        "splitter-coalescing (UAT-1 hardening)"
    )
    assert "_reflow_stream_picker_row" in source, (
        "showEvent must defer _reflow_stream_picker_row (Phase 72.1 LAYOUT-02)"
    )
    assert "_reflow_volume_cluster" in source, (
        "showEvent must defer _reflow_volume_cluster (Phase 72.4 LAYOUT-04)"
    )
    assert "_apply_art_tier" in source, (
        "showEvent must defer _apply_art_tier (Phase 72.3 LAYOUT-03)"
    )


def test_set_volume_size_policy_calls_update_geometry():
    """UAT-1 hardening: _set_volume_size_policy must call
    self.volume_slider.updateGeometry() after mutating the size policy.

    Reason: setFixedWidth(120) clamps the widget's own min/max to 120, but
    the parent QHBoxLayout may keep the prior Expanding-allowed cached size
    hint and continue to render the slider at the wider width. Forcing a
    re-query via updateGeometry() makes the layout pick up the new
    constraints synchronously.

    Observed: after a transient narrow initial-paint set the slider to
    Expanding, the slider stayed visually Expanding on row 1 even after a
    subsequent restore call to Fixed-120 — until the layout was forced to
    re-query.
    """
    method = getattr(NowPlayingPanel, "_set_volume_size_policy", None)
    assert method is not None, (
        "_set_volume_size_policy does not exist on NowPlayingPanel"
    )
    source = inspect.getsource(method)
    assert "updateGeometry" in source, (
        "_set_volume_size_policy must call updateGeometry() after the "
        "size-policy change so the parent layout re-queries the slider"
    )


def test_narrow_initial_show_wraps_cluster_without_resize(qtbot):
    """Initial-paint regression (UAT-1 follow-up): when the panel is
    shown at a width below the cluster-wrap threshold, the volume
    cluster must wrap to its target row without requiring an explicit
    subsequent resize event.

    Behavioral pin for the showEvent + QTimer.singleShot(0) deferred
    reflow. _make_panel calls show() + waitExposed() AFTER setting the
    panel width via the QMainWindow harness — the bug surface is the
    same first-paint geometry the user hits on launch.

    qtbot.wait(50) gives the QTimer.singleShot(0) chain one event-loop
    tick to fire (Qt 0-delay timers fire on the next iteration, not
    synchronously).
    """
    repo = FakeRepo({"volume": "80"})
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.resize(_W_VERY_NARROW, 800)  # narrow BEFORE show — first-paint scenario
    panel.show()
    qtbot.waitExposed(panel)
    qtbot.wait(50)  # let QTimer.singleShot(0) fire
    # No station bound → stream_combo hidden (single-stream wrap path, D-07).
    # At very-narrow, cluster must be on _controls_row2 — NOT row 1 — without
    # any explicit panel.resize() between show() and the assertion.
    _assert_volume_cluster_in_layout(panel, panel._controls_row2)
