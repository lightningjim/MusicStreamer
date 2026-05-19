"""Phase 72.3 / LAYOUT-03 -- responsive logo + cover-art tier tests (Wave 0 TDD-RED scaffold).

Scope: When the now-playing panel's width changes, both `logo_label` and
`cover_label` retarget to a width-driven tier value drawn from `{140, 180, 240}`.
Trigger is `NowPlayingPanel.width()` evaluated inside the existing
`resizeEvent` override (Phase 72.1 already shipped it). Logo and cover are
always equal-sized at every tier (D-05). The tier is recomputed on every
`resizeEvent`; `setFixedSize` + bound-pixmap rescale fire only when the tier
value differs from the cached previous tier. No SQLite persistence
(D-09 inheritance from Phase 72).

Wave 0 / TDD-RED state at landing
---------------------------------
This file lands as part of Plan 72.3-01 (Wave 0 scaffold). All 13 test
functions below MUST FAIL on Plan 01 commit and turn GREEN as Plans 02/03
land production code:

  * Plan 02 -- adds `_current_art_tier_size()` (pure helper) and
    `_apply_art_tier()` (orchestrator), the cached `self._current_art_tier`
    attribute, and bumps the cover_label default `setFixedSize` from 160 to
    180 (D-05 equal-at-every-tier invariant). Flips TBD-01..TBD-08 and
    TBD-11 to GREEN.
  * Plan 03 -- refactors the three pixmap render call sites
    (`_set_cover_pixmap` line 1468, `_show_station_logo` line 1495,
    `_show_station_logo_in_cover_slot` line 1499) to read the central tier
    via `self._current_art_tier`, extends `resizeEvent` with the
    `_apply_art_tier` call, and tracks `_last_cover_path` for replay.
    Flips TBD-09 and TBD-10 to GREEN.

The two negative-assertion tests
(`test_no_repo_set_setting_for_tier_state`, `test_no_lambda_in_tier_wiring`)
may pass by accident pre-Plan-02 because no production code exists yet to
trip them; they remain in place as permanent regression locks.

Test names match `.planning/phases/72.3-*/72.3-VALIDATION.md`
Per-Task Verification Map verbatim (TBD-01..TBD-13) -- do NOT rename
without updating the Validation Map alongside.

Test inventory (Per-Task Verification Map)
------------------------------------------
   1. test_narrow_tier_at_floor                              -- TBD-01
   2. test_medium_tier_at_default                            -- TBD-02
   3. test_wide_tier_at_widescreen                           -- TBD-03
   4. test_narrow_to_medium_threshold                        -- TBD-04
   5. test_medium_to_wide_threshold                          -- TBD-05
   6. test_logo_equals_cover_at_every_tier                   -- TBD-06
   7. test_pixmap_dimensions_track_tier                      -- TBD-07
   8. test_within_band_resize_is_noop                        -- TBD-08
   9. test_cover_art_ready_after_resize_matches_tier         -- TBD-09
  10. test_youtube_16_9_letterbox_at_every_tier              -- TBD-10
  11. test_compact_and_expanded_modes_same_tier              -- TBD-11
  12. test_no_repo_set_setting_for_tier_state                -- TBD-12 (negative)
  13. test_no_lambda_in_tier_wiring                          -- TBD-13 (negative)

Test doubles (FakePlayer, FakeRepo, _make_panel) mirror
`tests/test_phase72_now_playing_panel.py:44-78` (the simpler FakeRepo shape
without the `streams_by_station` extension -- tier behavior is
stream-count-agnostic). FakePlayer is imported from `tests/_fake_player.py`
per INFRA-01 / D-17 drift-guard (no inline FakePlayer subclasses outside
`_fake_player.py`).

Resize pattern: direct `panel.resize(W, H)` per `72.3-PATTERNS.md` Pattern A
-- preceded inside the `_make_panel` factory by `panel.show()` +
`qtbot.waitExposed(panel)` (Pitfall 6 in 72.3-RESEARCH: without these,
resizeEvent does not dispatch reliably on Wayland and tier assertions
become flaky).
"""
from __future__ import annotations

import inspect
from typing import Any, Optional

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap

from musicstreamer.ui_qt import icons_rc  # noqa: F401  side-effect: registers :/icons
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
from musicstreamer.models import Station, StationStream
from tests._fake_player import FakePlayer


class FakeRepo:
    """Phase-72 FakeRepo shape (no `streams_by_station` extension).

    Tier behavior is stream-count-agnostic per 72.3-RESEARCH Wave 0 Gaps --
    the simpler FakeRepo from `tests/test_phase72_now_playing_panel.py:44-72`
    is sufficient.
    """

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
    """Factory: NowPlayingPanel wired with FakePlayer + simple FakeRepo.

    Phase 72.1 precedent (test_phase72_1_stream_picker_reflow.py:140-141):
    `panel.show()` + `qtbot.waitExposed(panel)` are REQUIRED so resizeEvent
    dispatches reliably. Without this, panel.resize() may not propagate;
    tier assertions become flaky. (Pitfall 6 in 72.3-RESEARCH.)
    """
    repo = FakeRepo(settings or {"volume": "80"})
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitExposed(panel)
    return panel


def _make_bound_station(art_path: Optional[str] = None) -> Station:
    """Minimal Station for tests that bind one (no streams; tier behavior
    is stream-count-agnostic).
    """
    return Station(
        id=1,
        name="Tier Test Station",
        provider_id=None,
        provider_name="TestFM",
        tags="",
        station_art_path=art_path,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[],
        last_played_at=None,
    )


# ---------------------------------------------------------------------------
# TBD-01..TBD-03: three sample-point tier assertions (narrow / medium / wide)
# ---------------------------------------------------------------------------


def test_narrow_tier_at_floor(qtbot):
    """TBD-01: width 600 -> narrow tier (140); both labels 140x140.

    UI-SPEC Tier State Truth Table: width < 700 maps to narrow tier.
    D-05 invariant: logo size equals cover size at every tier.
    Plan 02 adds `panel._current_art_tier` -- AttributeError at Wave 0.
    """
    panel = _make_panel(qtbot)
    panel.resize(600, 600)

    assert panel.logo_label.size().width() == 140
    assert panel.logo_label.size().height() == 140
    assert panel.cover_label.size().width() == 140
    assert panel.cover_label.size().height() == 140
    assert panel._current_art_tier == 140


def test_medium_tier_at_default(qtbot):
    """TBD-02: width 800 -> medium tier (180); both labels 180x180.

    UI-SPEC Tier State Truth Table: 700 <= width < 1100 maps to medium tier.
    D-05 invariant: cover bumps 160 -> 180 to equal logo at every tier.
    Plan 02 adds `panel._current_art_tier` AND bumps cover_label default to
    180; both required for RED -> GREEN transition.
    """
    panel = _make_panel(qtbot)
    panel.resize(800, 600)

    assert panel.logo_label.size().width() == 180
    assert panel.logo_label.size().height() == 180
    assert panel.cover_label.size().width() == 180
    assert panel.cover_label.size().height() == 180
    assert panel._current_art_tier == 180


def test_wide_tier_at_widescreen(qtbot):
    """TBD-03: width 1400 -> wide tier (240); both labels 240x240.

    UI-SPEC Tier State Truth Table: width >= 1100 maps to wide tier.
    D-05 invariant: logo size equals cover size at every tier.
    Plan 02 adds `panel._current_art_tier` -- AttributeError at Wave 0.
    """
    panel = _make_panel(qtbot)
    panel.resize(1400, 800)

    assert panel.logo_label.size().width() == 240
    assert panel.logo_label.size().height() == 240
    assert panel.cover_label.size().width() == 240
    assert panel.cover_label.size().height() == 240
    assert panel._current_art_tier == 240


# ---------------------------------------------------------------------------
# TBD-04..TBD-05: threshold boundaries (narrow -> medium at 700; medium -> wide at 1100)
# ---------------------------------------------------------------------------


def test_narrow_to_medium_threshold(qtbot):
    """TBD-04: narrow -> medium threshold is inclusive on the lower edge at 700.

    UI-SPEC predicate: `width < 700 -> 140; 700 <= width < 1100 -> 180`.
    Locks the four-point boundary: 599 / 699 -> 140; 700 / 701 -> 180.
    Plan 02 adds `_current_art_tier_size()` -- AttributeError at Wave 0.
    """
    panel = _make_panel(qtbot)

    panel.resize(599, 600)
    assert panel._current_art_tier_size() == 140

    panel.resize(699, 600)
    assert panel._current_art_tier_size() == 140

    panel.resize(700, 600)
    assert panel._current_art_tier_size() == 180

    panel.resize(701, 600)
    assert panel._current_art_tier_size() == 180


def test_medium_to_wide_threshold(qtbot):
    """TBD-05: medium -> wide threshold is inclusive on the lower edge at 1100.

    UI-SPEC predicate: `700 <= width < 1100 -> 180; width >= 1100 -> 240`.
    Locks the three-point boundary: 1099 -> 180; 1100 / 1500 -> 240.
    Plan 02 adds `_current_art_tier_size()` -- AttributeError at Wave 0.
    """
    panel = _make_panel(qtbot)

    panel.resize(1099, 600)
    assert panel._current_art_tier_size() == 180

    panel.resize(1100, 600)
    assert panel._current_art_tier_size() == 240

    panel.resize(1500, 600)
    assert panel._current_art_tier_size() == 240


# ---------------------------------------------------------------------------
# TBD-06..TBD-08: equality invariant, pixmap-tracks-tier, in-band idempotence
# ---------------------------------------------------------------------------


def test_logo_equals_cover_at_every_tier(qtbot):
    """TBD-06: logo size == cover size at every tier (D-05 invariant).

    Loops through three representative widths (one per tier) and asserts
    both labels remain equal-sized and square.
    """
    panel = _make_panel(qtbot)

    for width in (600, 800, 1200):
        panel.resize(width, 600)
        logo_size = panel.logo_label.size()
        cover_size = panel.cover_label.size()
        assert logo_size == cover_size, (
            f"D-05 violated at width {width}: logo={logo_size} cover={cover_size}"
        )
        assert logo_size.width() == logo_size.height(), (
            f"Logo not square at width {width}: {logo_size}"
        )
        assert cover_size.width() == cover_size.height(), (
            f"Cover not square at width {width}: {cover_size}"
        )


def test_pixmap_dimensions_track_tier(qtbot):
    """TBD-07: bound-pixmap dimensions track the current tier (D-02 single SoT).

    Binds a station with no station_art_path (the fallback icon renders).
    For each tier width, asserts the logo_label's current pixmap has
    dimensions <= the tier value (KeepAspectRatio: fits inside the box).
    The fallback SVG icon renders as a square so width == height == tier
    exactly. Plan 03 refactors `_show_station_logo` to read the central
    tier; without it the pixmap stays at the old 180x180 size after a
    resize.
    """
    panel = _make_panel(qtbot)
    station = _make_bound_station(art_path=None)
    panel.bind_station(station)

    for width, tier_value in [(600, 140), (800, 180), (1400, 240)]:
        panel.resize(width, 600)
        pix = panel.logo_label.pixmap()
        assert pix.width() <= tier_value, (
            f"Pixmap width {pix.width()} > tier {tier_value} at panel width {width}"
        )
        assert pix.height() <= tier_value, (
            f"Pixmap height {pix.height()} > tier {tier_value} at panel width {width}"
        )


def test_within_band_resize_is_noop(qtbot):
    """TBD-08: repeated resize within a tier band leaves the cached tier value
    unchanged (cached-diff idempotence guard from Pattern 2).

    Plan 02's `_apply_art_tier` early-returns when computed tier matches
    cached tier; this test pins the OUTPUT contract (tier value stable)
    rather than the implementation-side pixmap-thrash avoidance.
    """
    panel = _make_panel(qtbot)
    panel.resize(800, 600)
    assert panel._current_art_tier == 180

    for width in (900, 950, 1050):
        panel.resize(width, 600)
        assert panel._current_art_tier == 180, (
            f"Tier flipped to {panel._current_art_tier} at in-band width {width}"
        )


# ---------------------------------------------------------------------------
# TBD-09..TBD-10: cover-art replay + 16:9 letterbox correctness
# ---------------------------------------------------------------------------


def test_cover_art_ready_after_resize_matches_tier(qtbot, tmp_path):
    """TBD-09: cover-art replay after a tier change produces a pixmap matching
    the new tier (D-03 render-site refactor).

    Builds a 300x300 (1:1) PNG fixture inline, resizes the panel to the wide
    tier (240), then calls `_set_cover_pixmap` directly. The cover_label
    pixmap must scale to (240, 240). Plan 03 refactors `_set_cover_pixmap`
    to read the central tier; pre-Plan-03 it stays hard-coded to
    QSize(160, 160) and this test fails.
    """
    panel = _make_panel(qtbot)
    panel.resize(1400, 800)
    assert panel._current_art_tier == 240

    src = QPixmap(300, 300)
    src.fill(Qt.blue)
    art_path = tmp_path / "fake_cover.png"
    src.save(str(art_path))

    panel._set_cover_pixmap(str(art_path))
    assert panel.cover_label.pixmap().size() == QSize(240, 240)


def test_youtube_16_9_letterbox_at_every_tier(qtbot, tmp_path):
    """TBD-10: YouTube 16:9 logos letterbox correctly at every tier.

    Aspect ratio preserved via `Qt.KeepAspectRatio + Qt.SmoothTransformation`
    in `_load_scaled_pixmap` (now_playing_panel.py:213). At tier N, a 16:9
    source produces a pixmap with width == N and height ~= N * 9/16.

    Tolerance for rounding (RESEARCH Open Question 3): assert width / height
    within 1% of 16/9 (Qt rounds 180 * 9/16 = 101.25 -> 101, giving ratio
    1.782 vs theoretical 1.778).
    """
    src = QPixmap(1280, 720)  # 16:9 source
    src.fill(Qt.red)
    art_path = tmp_path / "yt_16_9.png"
    src.save(str(art_path))

    panel = _make_panel(qtbot)
    station = _make_bound_station(art_path=str(art_path))
    panel.bind_station(station)

    for width, tier_value in [(600, 140), (800, 180), (1400, 240)]:
        panel.resize(width, 600)
        panel._show_station_logo()
        pix = panel.logo_label.pixmap()
        assert pix.width() == tier_value, (
            f"Pixmap width {pix.width()} != tier {tier_value} at panel width {width}"
        )
        ratio = pix.width() / pix.height()
        assert abs(ratio - 16 / 9) < 0.01, (
            f"Aspect ratio {ratio} not within 1% of 16/9 at panel width {width} "
            f"(pixmap {pix.width()}x{pix.height()})"
        )


# ---------------------------------------------------------------------------
# TBD-11: compact-mode vs expanded-mode parity at equal panel width
# ---------------------------------------------------------------------------


def test_compact_and_expanded_modes_same_tier(qtbot):
    """TBD-11: equal panel widths -> equal tiers regardless of compact state
    (D-06 panel-width trigger is mode-agnostic).

    Per UI-SPEC: the trigger is `self.width()` not mode -- equal width
    yields equal tier. Two panels at the same width must report the same
    tier value, mirroring Phase 72.1 D-01 inheritance.
    """
    panel_a = _make_panel(qtbot)
    panel_b = _make_panel(qtbot)

    panel_a.resize(1200, 600)
    panel_b.resize(1200, 600)

    assert panel_a._current_art_tier == 180
    assert panel_b._current_art_tier == 180
    assert panel_a._current_art_tier == panel_b._current_art_tier


# ---------------------------------------------------------------------------
# TBD-12..TBD-13: negative assertions (D-09 no-persistence, QA-05 no-lambda)
# ---------------------------------------------------------------------------


def test_no_repo_set_setting_for_tier_state(qtbot):
    """TBD-12 (negative): NO repo.set_setting call for any tier-state key.

    Locks D-09 inheritance from Phase 72 / 72.1: layout state is recomputed
    on every resize event; no SQLite persistence. Mirrors the negative-test
    pattern at tests/test_phase72_1_stream_picker_reflow.py:510-541.

    May pass by accident at Wave 0 (no production code is writing any
    tier keys yet) -- that is acceptable and the test remains a permanent
    regression net for Plans 02/03.
    """
    panel = _make_panel(qtbot)
    fake_repo = panel._repo
    keys_before = set(fake_repo._settings.keys())

    for w in (560, 800, 1200, 1600, 600, 1100):
        panel.resize(w, 800)

    keys_after = set(fake_repo._settings.keys())
    new_keys = keys_after - keys_before
    forbidden_fragments = ("tier", "art_size", "logo_size", "cover_size")
    offending = {
        k for k in new_keys
        if any(frag in k.lower() for frag in forbidden_fragments)
    }
    assert not offending, (
        f"D-09 inheritance violated -- tier-state key(s) written to repo: {offending}"
    )


def test_no_lambda_in_tier_wiring():
    """TBD-13 (negative): NO lambda in any tier-helper wiring (QA-05).

    Mirrors tests/test_phase72_1_stream_picker_reflow.py:544-571 source-grep
    pattern. Runs without instantiating widgets.

    May pass by accident at Wave 0 (no production `_current_art_tier_size` /
    `_apply_art_tier` method exists yet) -- that is acceptable and it remains
    a permanent regression net for Plans 02/03.
    """
    src = inspect.getsource(NowPlayingPanel)
    targets = (
        "_current_art_tier_size",
        "_apply_art_tier",
        "resizeEvent",
    )
    for line in src.splitlines():
        if any(t in line for t in targets):
            assert "lambda" not in line, (
                f"QA-05 violated -- lambda on tier-related line: {line!r}"
            )
