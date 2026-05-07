"""Phase 37-02: NowPlayingPanel widget tests.

Covers layout contract, Player signal slots, volume persistence through repo,
play/pause icon toggling, elapsed timer formatting, Name·Provider middle dot
separator, cover art signal adapter, YouTube 16:9 letterbox (UI-14), plain-text
lockdown on the ICY label, and media-playback icon resource load.

Uses a FakePlayer(QObject) test double instead of the real GStreamer Player.
"""
from __future__ import annotations

from typing import Any, List, Optional

import pytest
from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QFormLayout

from musicstreamer.models import Station, StationStream
from musicstreamer.ui_qt import icons_rc  # noqa: F401
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakePlayer(QObject):
    """Minimal QObject mirroring Player's Signal surface used by NowPlayingPanel."""

    title_changed = Signal(str)
    failover = Signal(object)
    offline = Signal(str)
    playback_error = Signal(str)
    elapsed_updated = Signal(int)
    buffer_percent = Signal(int)  # Phase 47.1 D-12

    def __init__(self) -> None:
        super().__init__()
        self.set_volume_calls: List[float] = []
        self.stop_called: bool = False
        self.pause_called: bool = False
        self.play_calls: List[Station] = []
        # Phase 47.2 D-08: track EQ toggle invocations as ("enabled", bool) tuples.
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
        # Phase 47.2 D-08: mirrors Plan 03's canonical FakePlayer shape.
        self.calls.append(("enabled", bool(enabled)))


class FakeRepo:
    def __init__(self, settings: Optional[dict] = None,
                 stations: Optional[list] = None) -> None:
        self._settings = dict(settings or {})
        self._favorites: list = []
        # Phase 64 Wave 0 (RESEARCH Pitfall #1): library backing for the
        # new sibling-list path. Default empty list keeps every existing
        # test (which passes only `settings`) working unchanged.
        self._stations: list = list(stations or [])

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value

    def is_favorited(self, station_name: str, track_title: str) -> bool:
        return any(
            f == (station_name, track_title) for f in self._favorites
        )

    def add_favorite(self, station_name: str, provider_name: str, track_title: str, genre: str) -> None:
        key = (station_name, track_title)
        if key not in self._favorites:
            self._favorites.append(key)

    def remove_favorite(self, station_name: str, track_title: str) -> None:
        key = (station_name, track_title)
        if key in self._favorites:
            self._favorites.remove(key)

    def list_streams(self, station_id: int) -> list:
        return []

    # Phase 64 Wave 0 (RESEARCH Pitfall #1): list_stations and get_station
    # are required by the new NowPlayingPanel._refresh_siblings + click
    # handler paths. get_station raises ValueError on miss to match
    # production Repo.get_station semantics (repo.py:271 raises
    # ValueError "Station not found") -- the panel handler MUST wrap this
    # call in try/except Exception per RESEARCH Pitfall #2.
    def list_stations(self) -> list:
        return list(self._stations)

    def get_station(self, station_id: int):
        for s in self._stations:
            if s.id == station_id:
                return s
        raise ValueError("Station not found")


def _station(name: str = "Drone Zone", provider: Optional[str] = "SomaFM",
             art: Optional[str] = None) -> Station:
    return Station(
        id=1,
        name=name,
        provider_id=1 if provider else None,
        provider_name=provider,
        tags="",
        station_art_path=art,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[StationStream(id=1, station_id=1, url="http://x/s", label="hi",
                               quality="hi", position=1, stream_type="shoutcast",
                               codec="MP3")],
    )


def _make_aa_station(station_id: int, name: str, url: str,
                     provider: str = "DI.fm") -> Station:
    """Phase 64 Wave 0: factory mirroring tests/test_edit_station_dialog.py:783-806.

    Used by the sibling-label tests below to construct AA-flavored stations
    whose first stream URL drives find_aa_siblings. Distinct from `_station`
    above: this factory takes an explicit URL so each test can construct
    DI.fm / ZenRadio / JazzRadio URLs deterministically.
    """
    return Station(
        id=station_id,
        name=name,
        provider_id=1,
        provider_name=provider,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[
            StationStream(
                id=station_id * 10,
                station_id=station_id,
                url=url,
                position=1,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Construction / layout
# ---------------------------------------------------------------------------


def test_panel_construction(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    assert panel.minimumWidth() == 560
    assert panel.logo_label.size() == QSize(180, 180)
    assert panel.cover_label.size() == QSize(160, 160)
    assert panel.play_pause_btn.size() == QSize(36, 36)
    assert panel.stop_btn.size() == QSize(36, 36)
    assert panel.volume_slider.width() == 120
    assert panel.volume_slider.minimum() == 0
    assert panel.volume_slider.maximum() == 100


def test_icy_label_plaintext_format(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    assert panel.icy_label.textFormat() == Qt.PlainText


# ---------------------------------------------------------------------------
# Volume initialization + persistence
# ---------------------------------------------------------------------------


def test_volume_slider_initial_from_repo(qtbot):
    fp = FakePlayer()
    panel = NowPlayingPanel(fp, FakeRepo({"volume": "65"}))
    qtbot.addWidget(panel)
    assert panel.volume_slider.value() == 65
    assert fp.set_volume_calls[-1] == pytest.approx(0.65)


def test_volume_slider_default_when_unset(qtbot):
    fp = FakePlayer()
    panel = NowPlayingPanel(fp, FakeRepo({}))  # no "volume" key
    qtbot.addWidget(panel)
    assert panel.volume_slider.value() == 80


def test_volume_slider_default_on_bad_value(qtbot):
    fp = FakePlayer()
    panel = NowPlayingPanel(fp, FakeRepo({"volume": "abc"}))
    qtbot.addWidget(panel)
    assert panel.volume_slider.value() == 80


def test_volume_slider_persist_on_release(qtbot):
    fp = FakePlayer()
    repo = FakeRepo({"volume": "80"})
    panel = NowPlayingPanel(fp, repo)
    qtbot.addWidget(panel)
    panel.volume_slider.setValue(42)
    panel.volume_slider.sliderReleased.emit()
    assert repo.get_setting("volume") == "42"


def test_volume_slider_live_updates_player(qtbot):
    fp = FakePlayer()
    panel = NowPlayingPanel(fp, FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    fp.set_volume_calls.clear()
    panel.volume_slider.setValue(25)
    assert fp.set_volume_calls[-1] == pytest.approx(0.25)
    assert "25" in panel.volume_slider.toolTip()


# ---------------------------------------------------------------------------
# Player slot methods
# ---------------------------------------------------------------------------


def test_icy_title_update(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.on_title_changed("Artist - Song")
    assert panel.icy_label.text() == "Artist - Song"


def test_elapsed_label_advances_on_signal(qtbot):
    """Plan 40.1-06 regression: elapsed_label advances when Player emits
    elapsed_updated via Qt signal path (not just direct slot call)."""
    fp = FakePlayer()
    panel = NowPlayingPanel(fp, FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    # Mirror the main_window wiring (the panel does not self-connect; this
    # plan intentionally leaves NowPlayingPanel untouched).
    fp.elapsed_updated.connect(panel.on_elapsed_updated)

    assert panel.elapsed_label.text() == "0:00"

    fp.elapsed_updated.emit(1)
    assert panel.elapsed_label.text() == "0:01"

    fp.elapsed_updated.emit(2)
    assert panel.elapsed_label.text() == "0:02"

    fp.elapsed_updated.emit(65)
    assert panel.elapsed_label.text() == "1:05"

    fp.elapsed_updated.emit(3725)
    assert panel.elapsed_label.text() == "1:02:05"


def test_elapsed_format_mm_ss(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.on_elapsed_updated(125)
    assert panel.elapsed_label.text() == "2:05"


def test_elapsed_format_zero_pads_seconds(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.on_elapsed_updated(7)
    assert panel.elapsed_label.text() == "0:07"


def test_elapsed_format_hh_mm_ss(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.on_elapsed_updated(3725)
    assert panel.elapsed_label.text() == "1:02:05"


def test_play_pause_icon_toggle(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    # Initial: paused → tooltip "Play"
    assert panel.play_pause_btn.toolTip() == "Play"
    panel.on_playing_state_changed(True)
    assert panel.play_pause_btn.toolTip() == "Pause"
    panel.on_playing_state_changed(False)
    assert panel.play_pause_btn.toolTip() == "Play"


def test_stop_button_calls_player_stop(qtbot):
    fp = FakePlayer()
    panel = NowPlayingPanel(fp, FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.stop_btn.click()
    assert fp.stop_called is True


# ---------------------------------------------------------------------------
# bind_station
# ---------------------------------------------------------------------------


def test_name_provider_separator_u00b7(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.bind_station(_station("Drone Zone", "SomaFM"))
    assert panel.name_provider_label.text() == "Drone Zone \u00B7 SomaFM"
    assert "\u00B7" in panel.name_provider_label.text()


def test_bind_station_no_provider(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.bind_station(_station("Solo", provider=None))
    assert panel.name_provider_label.text() == "Solo"


# ---------------------------------------------------------------------------
# Cover art adapter + UI-14 letterbox
# ---------------------------------------------------------------------------


def test_cover_art_signal_adapter(qtbot, tmp_path):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    # Create a real 160x160 image on disk
    src = QPixmap(160, 160)
    src.fill(Qt.blue)
    path = tmp_path / "cover.png"
    assert src.save(str(path), "PNG")
    panel._set_cover_pixmap(str(path))
    pm = panel.cover_label.pixmap()
    assert not pm.isNull()


def test_cover_art_ready_signal_missing_path_falls_back(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.bind_station(_station())
    # Empty path → station logo fallback, no crash
    # Token 0 matches the initial _cover_fetch_token value.
    panel._on_cover_art_ready("0:")
    assert panel.cover_label.size() == QSize(160, 160)


def test_youtube_thumbnail_letterbox(qtbot, tmp_path):
    """UI-14: a 16:9 source pixmap letterboxes to 160x90 inside the 160x160 slot,
    and the label's fixed size is unchanged."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    src = QPixmap(320, 180)
    src.fill(Qt.red)
    path = tmp_path / "yt_thumb.png"
    assert src.save(str(path), "PNG")
    panel._set_cover_pixmap(str(path))
    assert panel.cover_label.size() == QSize(160, 160), "cover slot must stay 160x160"
    pm = panel.cover_label.pixmap()
    assert pm.size() == QSize(160, 90), f"expected 160x90 letterbox, got {pm.size()}"


# ---------------------------------------------------------------------------
# Icon resource
# ---------------------------------------------------------------------------


def test_new_icons_load(qtbot):
    # Ensure QApplication exists via qtbot fixture.
    for p in [
        ":/icons/media-playback-start-symbolic.svg",
        ":/icons/media-playback-pause-symbolic.svg",
        ":/icons/media-playback-stop-symbolic.svg",
    ]:
        assert not QIcon(p).isNull(), f"icon missing from resource: {p}"


# ---------------------------------------------------------------------------
# Phase 38-02: Track star button tests
# ---------------------------------------------------------------------------


def test_star_btn_disabled_without_icy(qtbot):
    """star_btn is disabled initially (no station, no ICY title)."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    assert hasattr(panel, "star_btn"), "NowPlayingPanel must have star_btn"
    assert not panel.star_btn.isEnabled()


def test_star_btn_enabled_after_title(qtbot):
    """star_btn becomes enabled after binding a station and receiving an ICY title."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.bind_station(_station())
    panel.on_title_changed("Artist - Song")
    assert panel.star_btn.isEnabled()


def test_star_btn_toggle(qtbot):
    """Clicking star saves to favorites; clicking again removes it."""
    repo = FakeRepo({"volume": "80"})
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    station = _station()
    panel.bind_station(station)
    panel.on_title_changed("Artist - Song")

    # Not favorited yet
    assert not repo.is_favorited(station.name, "Artist - Song")

    # Click star → should favorite
    panel.star_btn.click()
    assert repo.is_favorited(station.name, "Artist - Song")

    # Click again → should unfavorite
    panel.star_btn.click()
    assert not repo.is_favorited(station.name, "Artist - Song")


def test_star_btn_disabled_after_stop(qtbot):
    """star_btn is disabled after stop is clicked."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.bind_station(_station())
    panel.on_title_changed("Artist - Song")
    assert panel.star_btn.isEnabled()
    panel._on_stop_clicked()
    assert not panel.star_btn.isEnabled()


# ---------------------------------------------------------------------------
# Phase 40.1-04: Logo render regression (D-11, D-14)
# ---------------------------------------------------------------------------


def test_logo_loads_via_abs_path(qtbot, tmp_path, monkeypatch):
    """Relative station_art_path resolves against paths.data_dir() before QPixmap load."""
    import os
    from musicstreamer import paths as _paths
    monkeypatch.setattr(_paths, "_root_override", str(tmp_path))
    # Write a real PNG so QPixmap load succeeds.
    asset_dir = os.path.join(str(tmp_path), "assets", "42")
    os.makedirs(asset_dir, exist_ok=True)
    pix = QPixmap(16, 16)
    pix.fill(Qt.red)
    asset_path = os.path.join(asset_dir, "station_art.png")
    assert pix.save(asset_path, "PNG")

    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    station = _station(art="assets/42/station_art.png")
    station.id = 42
    panel.bind_station(station)

    pm = panel.logo_label.pixmap()
    assert pm is not None
    assert not pm.isNull(), "logo pixmap must load from abs resolved path"
    # Must match our red source — not the fallback SVG. Fallback renders with
    # transparent / neutral pixels, never pure red at center.
    img = pm.toImage()
    center = img.pixelColor(img.width() // 2, img.height() // 2)
    assert (center.red(), center.green(), center.blue()) == (255, 0, 0), \
        f"expected red from resolved abs path, got {center.getRgb()} (likely fallback icon)"


def test_logo_none_when_path_missing(qtbot):
    """station_art_path=None → fallback icon, no crash."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.bind_station(_station(art=None))
    # Should not raise — fallback icon rendered.
    assert panel.logo_label.size() == QSize(180, 180)


def test_star_btn_track_starred_signal(qtbot):
    """Clicking star emits track_starred signal with correct args."""
    repo = FakeRepo({"volume": "80"})
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    station = _station("Groove Salad", "SomaFM")
    panel.bind_station(station)
    panel.on_title_changed("DJ Mix")

    with qtbot.waitSignal(panel.track_starred, timeout=500) as blocker:
        panel.star_btn.click()

    station_name, track_title, provider, is_fav = blocker.args
    assert station_name == "Groove Salad"
    assert track_title == "DJ Mix"
    assert provider == "SomaFM"
    assert is_fav is True


# ---------------------------------------------------------------------------
# Phase 40.1-05: icy_disabled suppression regression tests (D-15, D-16, D-17)
# ---------------------------------------------------------------------------


def _icy_disabled_station(name: str = "My Station") -> Station:
    return Station(
        id=1,
        name=name,
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=True,
        streams=[StationStream(id=1, station_id=1, url="http://x/s", label="hi",
                               quality="hi", position=1, stream_type="shoutcast",
                               codec="MP3")],
    )


def test_icy_disabled_suppresses_all(qtbot, monkeypatch):
    """When icy_disabled=True, on_title_changed must not overwrite icy_label
    or call _fetch_cover_art_async. bind_station must show station name."""
    from unittest.mock import MagicMock

    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)

    station = _icy_disabled_station("My Station")
    panel.bind_station(station)

    # After bind, the station name should appear in icy_label (fallback per D-15).
    assert panel.icy_label.text() == "My Station"

    # Patch _fetch_cover_art_async on the instance — capture any call.
    fetch_mock = MagicMock()
    monkeypatch.setattr(panel, "_fetch_cover_art_async", fetch_mock)

    panel.on_title_changed("Some Artist - Some Track")

    assert fetch_mock.call_count == 0, (
        "icy_disabled=True must suppress cover-art fetch"
    )
    assert panel.icy_label.text() == "My Station", (
        "icy_disabled=True must keep station name in icy_label, not overwrite with ICY title"
    )


def test_icy_disabled_suppresses_itunes_call(qtbot, monkeypatch):
    """When icy_disabled=True, cover_art.fetch_cover_art must never be invoked."""
    from unittest.mock import MagicMock
    import musicstreamer.cover_art as cover_art_mod

    fetch_spy = MagicMock()
    monkeypatch.setattr(cover_art_mod, "fetch_cover_art", fetch_spy)
    # Also patch the symbol already imported into the panel module.
    import musicstreamer.ui_qt.now_playing_panel as npp_mod
    monkeypatch.setattr(npp_mod, "fetch_cover_art", fetch_spy)

    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.bind_station(_icy_disabled_station("My Station"))

    panel.on_title_changed("Foo - Bar")
    qtbot.wait(200)

    assert fetch_spy.call_count == 0, (
        "icy_disabled=True must not trigger iTunes cover-art lookup"
    )


def test_icy_enabled_still_updates_title(qtbot, monkeypatch):
    """Control test: icy_disabled=False preserves existing behavior."""
    from unittest.mock import MagicMock

    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)

    station = _station("On-Air", "SomaFM")  # icy_disabled=False
    panel.bind_station(station)

    fetch_mock = MagicMock()
    monkeypatch.setattr(panel, "_fetch_cover_art_async", fetch_mock)

    panel.on_title_changed("Artist - Track")

    assert panel.icy_label.text() == "Artist - Track"
    fetch_mock.assert_called_once_with("Artist - Track")


def test_icy_disabled_rebind_takes_effect(qtbot, monkeypatch):
    """Rebinding with a fresh icy_disabled=True Station must suppress subsequent titles."""
    from unittest.mock import MagicMock

    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)

    # Start with icy_disabled=False
    s_enabled = _station("S", None)
    panel.bind_station(s_enabled)

    fetch_mock = MagicMock()
    monkeypatch.setattr(panel, "_fetch_cover_art_async", fetch_mock)

    panel.on_title_changed("T")
    assert panel.icy_label.text() == "T"

    # Rebind with a fresh station instance, icy_disabled=True, same name "S"
    s_disabled = _icy_disabled_station("S")
    panel.bind_station(s_disabled)

    # Re-patch because bind_station didn't reassign but keep the mock.
    monkeypatch.setattr(panel, "_fetch_cover_art_async", fetch_mock)

    panel.on_title_changed("T2")
    assert panel.icy_label.text() == "S", (
        "After rebind to icy_disabled=True station, icy_label must show station name, not 'T2'"
    )


# ---------------------------------------------------------------- #
# Phase 47.1 — Stats for Nerds buffer indicator tests
# Covers D-01/D-02/D-05/D-07/D-08/D-09/D-11
# ---------------------------------------------------------------- #


def test_stats_widget_always_constructed(qtbot):
    """D-08: stats widget is always built, even when hidden."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    assert panel._stats_widget is not None


def test_stats_hidden_by_default(qtbot):
    """D-05: fresh install (no setting) -> stats widget hidden."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    # Use isHidden (flag) not isVisible (visibility chain) -- Pitfall 6
    assert panel._stats_widget.isHidden() is True


def test_stats_visible_after_set_stats_visible_true(qtbot):
    """D-04 + D-07 (WR-02): set_stats_visible(True) is the single path that
    makes the stats widget visible. The panel no longer reads the setting
    directly -- MainWindow drives visibility from the QAction's checked state
    so menu checkmark and panel cannot desync."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    assert panel._stats_widget.isHidden() is True  # default hidden
    panel.show()  # needed for isHidden() to reflect the child's own flag
    panel.set_stats_visible(True)
    assert panel._stats_widget.isHidden() is False


def test_stats_uses_form_layout(qtbot):
    """D-09: wrapper uses QFormLayout for extensibility."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    assert isinstance(panel._stats_widget.layout(), QFormLayout)


def test_buffer_bar_properties(qtbot):
    """D-01 + D-02: progress bar is 0-100, text hidden, fixed width 120."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    assert panel.buffer_bar.minimum() == 0
    assert panel.buffer_bar.maximum() == 100
    assert panel.buffer_bar.isTextVisible() is False
    assert panel.buffer_bar.maximumWidth() == 120


def test_set_buffer_percent_updates_both(qtbot):
    """D-11: single slot updates both bar and label atomically."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.set_buffer_percent(73)
    assert panel.buffer_bar.value() == 73
    assert panel.buffer_pct_label.text() == "73%"


def test_set_stats_visible_toggles(qtbot):
    """D-07: set_stats_visible flips the wrapper hidden flag both ways."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    # starts hidden
    assert panel._stats_widget.isHidden() is True
    panel.set_stats_visible(True)
    assert panel._stats_widget.isHidden() is False
    panel.set_stats_visible(False)
    assert panel._stats_widget.isHidden() is True


# ---------------------------------------------------------------- #
# Phase 47.2 D-08: EQ toggle button tests
# ---------------------------------------------------------------- #


def test_eq_toggle_initial_state_from_setting(qtbot):
    """D-15: eq_toggle_btn reflects persisted eq_enabled on construction."""
    repo = FakeRepo({"volume": "80", "eq_enabled": "1"})
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    assert panel.eq_toggle_btn.isChecked() is True


def test_eq_toggle_click_calls_player_and_persists(qtbot):
    """D-08: Clicking the toggle calls player.set_eq_enabled AND persists eq_enabled setting."""
    repo = FakeRepo({"volume": "80"})
    player = FakePlayer()
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    # Start unchecked
    panel.eq_toggle_btn.setChecked(False)
    # Click -> checked -> player.set_eq_enabled(True) + eq_enabled="1"
    panel.eq_toggle_btn.click()
    assert ("enabled", True) in player.calls
    assert repo.get_setting("eq_enabled") == "1"
    # Click again -> unchecked -> player.set_eq_enabled(False) + eq_enabled="0"
    panel.eq_toggle_btn.click()
    assert ("enabled", False) in player.calls
    assert repo.get_setting("eq_enabled") == "0"


def test_eq_toggle_fires_exactly_once_per_click(qtbot):
    """SC #3 (Phase 52): each click of eq_toggle_btn invokes
    player.set_eq_enabled exactly once.

    Defensive against accidental double-wiring (e.g., connecting both
    `clicked` and `toggled` to `_on_eq_toggled`, or adding a programmatic
    `.click()` somewhere in the toggle path). The existing test above
    uses `in` membership, which would NOT distinguish 1 call from 2 of
    the same value. This test asserts the exact call-count delta.

    The wiring under test lives at
    musicstreamer/ui_qt/now_playing_panel.py:261 (`clicked.connect(...)`).
    """
    repo = FakeRepo({"volume": "80"})
    player = FakePlayer()
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.eq_toggle_btn.setChecked(False)

    initial = len(player.calls)
    panel.eq_toggle_btn.click()
    assert len(player.calls) - initial == 1, (
        "SC #3: exactly one set_eq_enabled call per click "
        "(no double-fire from clicked+toggled both connected)"
    )
    after_first = len(player.calls)
    panel.eq_toggle_btn.click()
    assert len(player.calls) - after_first == 1, (
        "SC #3: second click also fires set_eq_enabled exactly once"
    )

    # Sanity: the per-click values are correct (True then False) and each
    # appears exactly once across the two clicks.
    assert player.calls.count(("enabled", True)) == 1, (
        "exactly one True call across the two clicks"
    )
    assert player.calls.count(("enabled", False)) == 1, (
        "exactly one False call across the two clicks"
    )


# ---------------------------------------------------------------------------
# Phase 64 / D-01..D-08, SC #1..SC #5: cross-network sibling line on the panel
# ---------------------------------------------------------------------------


def test_sibling_label_visible_for_aa_station_with_siblings(qtbot):
    """Phase 64 / SC #1: bound AA station with cross-network sibling ->
    _sibling_label visible with 'Also on:' + a network <a> link."""
    di = _make_aa_station(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    zr = _make_aa_station(2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc",
                          provider="ZenRadio")
    repo = FakeRepo({"volume": "80"}, stations=[di, zr])
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(di)
    # isHidden() reflects setVisible() state directly without windowing-system
    # parent-shown dependency (per test_edit_station_dialog.py:846-849 rationale).
    assert panel._sibling_label.isHidden() is False
    text = panel._sibling_label.text()
    assert "Also on:" in text
    assert 'href="sibling://2"' in text
    assert "ZenRadio" in text


def test_sibling_label_hidden_for_non_aa_station(qtbot):
    """Phase 64 / SC #3 / D-05 case 3: non-AA URL -> _sibling_label hidden."""
    yt = _make_aa_station(1, "Whatever", "https://www.youtube.com/watch?v=xyz",
                          provider="YouTube")
    repo = FakeRepo({"volume": "80"}, stations=[yt])
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(yt)
    assert panel._sibling_label.isHidden() is True


def test_sibling_label_hidden_when_no_siblings(qtbot):
    """Phase 64 / SC #3 / D-05 case 4: AA station with no other AA stations on
    other networks sharing the channel key -> hidden."""
    di = _make_aa_station(1, "UniqueName", "http://prem1.di.fm:80/uniquechannel_hi?listen_key=abc")
    repo = FakeRepo({"volume": "80"}, stations=[di])  # only the bound station
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(di)
    assert panel._sibling_label.isHidden() is True


def test_sibling_label_hidden_when_no_station_bound(qtbot):
    """Phase 64 / SC #3 / D-05 case 1: panel constructed but bind_station never
    called -> _sibling_label hidden (default state)."""
    repo = FakeRepo({"volume": "80"})
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    # Default state: no bind_station call.
    assert panel._sibling_label.isHidden() is True


def test_sibling_label_excludes_self(qtbot):
    """Phase 64 / SC #5 / D-07: even if the bound station's id appears as a
    candidate, find_aa_siblings excludes it. With only the bound station in
    the repo (no other AA stations), label hidden."""
    di = _make_aa_station(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    repo = FakeRepo({"volume": "80"}, stations=[di])  # only itself
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(di)
    # Self-exclusion at url_helpers.py:122 -> empty siblings -> hidden.
    assert panel._sibling_label.isHidden() is True
    # Belt-and-braces: even if shown, the self-id MUST NOT appear in any href.
    assert 'href="sibling://1"' not in panel._sibling_label.text()


def test_sibling_link_emits_sibling_activated_with_station_payload(qtbot):
    """Phase 64 / SC #2 / D-02: clicking a sibling link emits
    sibling_activated(Station) with the resolved sibling Station -- payload is
    Station, not int id."""
    di = _make_aa_station(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    zr = _make_aa_station(2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc",
                          provider="ZenRadio")
    repo = FakeRepo({"volume": "80"}, stations=[di, zr])
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(di)
    with qtbot.waitSignal(panel.sibling_activated, timeout=1000) as blocker:
        panel._on_sibling_link_activated("sibling://2")
    assert blocker.args == [zr]


def test_sibling_link_handler_no_op_when_id_matches_bound_station(qtbot):
    """Phase 64 / D-08: defense-in-depth -- sibling://{self.id} must be a no-op
    even though find_aa_siblings should never produce such a link."""
    di = _make_aa_station(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    repo = FakeRepo({"volume": "80"}, stations=[di])
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(di)
    emitted: list = []
    panel.sibling_activated.connect(lambda s: emitted.append(s))
    panel._on_sibling_link_activated("sibling://1")  # bound station's own id
    assert emitted == []


def test_sibling_link_handler_no_op_when_repo_get_station_raises(qtbot):
    """Phase 64 / RESEARCH Pitfall #2: production Repo.get_station raises
    ValueError on miss; the panel handler MUST wrap in try/except Exception
    and bail silently. FakeRepo.get_station also raises ValueError per Task 1."""
    di = _make_aa_station(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    repo = FakeRepo({"volume": "80"}, stations=[di])  # id 999 NOT in repo
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(di)
    emitted: list = []
    panel.sibling_activated.connect(lambda s: emitted.append(s))
    panel._on_sibling_link_activated("sibling://999")
    assert emitted == []  # silent no-op despite ValueError raised by FakeRepo


def test_sibling_link_handler_no_op_on_malformed_href(qtbot):
    """Phase 64 / D-08: malformed href (wrong prefix, non-int payload, empty)
    must be a silent no-op."""
    di = _make_aa_station(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    repo = FakeRepo({"volume": "80"}, stations=[di])
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(di)
    emitted: list = []
    panel.sibling_activated.connect(lambda s: emitted.append(s))
    for bad_href in ("garbage", "sibling://abc", "sibling://", "https://example.com", ""):
        panel._on_sibling_link_activated(bad_href)
    assert emitted == []


def test_refresh_siblings_runs_once_per_bind_station_call(qtbot):
    """Phase 64 / D-04 invariant (negative spy): _refresh_siblings runs
    EXACTLY once per bind_station call -- proves no other call site (e.g., no
    library-mutation signal subscription wired)."""
    di = _make_aa_station(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    repo = FakeRepo({"volume": "80"}, stations=[di])
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    call_count = {"n": 0}
    original = panel._refresh_siblings

    def spy():
        call_count["n"] += 1
        original()

    panel._refresh_siblings = spy  # type: ignore[method-assign]
    panel.bind_station(di)
    assert call_count["n"] == 1


def test_panel_does_not_reimplement_aa_detection():
    """Phase 64 / SC #4: the panel module imports ONLY find_aa_siblings and
    render_sibling_html from url_helpers; does NOT import _is_aa_url,
    _aa_slug_from_url, _aa_channel_key_from_url, or NETWORKS. Single source
    of AA detection -- no parallel detection logic."""
    import musicstreamer.ui_qt.now_playing_panel as panel_mod
    src = open(panel_mod.__file__, encoding="utf-8").read()
    assert "from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html" in src
    # Negative spy: forbidden symbols MUST NOT be imported in the panel module.
    forbidden = [
        "from musicstreamer.url_helpers import _is_aa_url",
        "from musicstreamer.url_helpers import _aa_slug_from_url",
        "from musicstreamer.url_helpers import _aa_channel_key_from_url",
        "from musicstreamer.aa_import import NETWORKS",
    ]
    for line in forbidden:
        assert line not in src, f"SC #4 violation: panel imports {line!r}"


# ===========================================================================
# Phase 60 / GBS-01c: active-playlist widget on NowPlayingPanel
# Pattern source: 60-PATTERNS.md §"tests/ui_qt/test_now_playing_panel_gbs.py"
# Hide-when-empty contract from Phase 64 / Phase 51.
# ===========================================================================

import os
from unittest.mock import MagicMock, patch
from musicstreamer import paths


def _make_gbs_station(provider_name: str = "GBS.FM", name: str = "GBS.FM"):
    """Lightweight Station-shaped object for GBS bind_station tests."""
    s = MagicMock()
    s.id = 99
    s.name = name
    s.provider_name = provider_name
    s.tags = ""
    s.streams = []
    return s


def _construct_gbs_panel(qtbot):
    """Construct NowPlayingPanel using the same FakePlayer/FakeRepo as the rest of this file."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    return panel


def test_gbs_playlist_hidden_for_non_gbs(qtbot, tmp_path, monkeypatch):
    """GBS-01c: non-GBS station -> widget invisible."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_gbs_panel(qtbot)
    panel.bind_station(_make_gbs_station(provider_name="DI.fm"))
    assert panel._gbs_playlist_widget.isVisible() is False


def test_gbs_playlist_hidden_when_logged_out(qtbot, tmp_path, monkeypatch):
    """D-06b: GBS station but cookies file absent -> widget hidden, timer stopped."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_gbs_panel(qtbot)
    panel.bind_station(_make_gbs_station())
    assert panel._gbs_playlist_widget.isVisible() is False
    assert panel._gbs_poll_timer.isActive() is False


def test_gbs_playlist_visible_when_gbs_and_logged_in(qtbot, tmp_path, monkeypatch):
    """D-06: GBS + logged-in -> widget visible + timer started."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    # Stub the worker's start so bind_station doesn't actually hit the network
    monkeypatch.setattr(
        "musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
        lambda self: None,
    )
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    # isVisible() returns False for unrealized widgets even when setVisible(True) was called.
    # isHidden() checks the widget's explicit visibility flag (same fix as Plan 60-04).
    assert not panel._gbs_playlist_widget.isHidden()
    assert panel._gbs_poll_timer.isActive() is True


def test_gbs_playlist_populates_from_mock_state(qtbot, tmp_path, monkeypatch):
    """Emitting playlist_ready directly populates the widget with enumerated queue rows.

    60-10 / T8 (Step 3a): Updated per revision-2 plan directive to assert on
    enumerated queue_rows rendering instead of the removed queue_summary line.
    - queue_rows added with 2 entries (D-10b format asserted)
    - queue_summary is retained on the state dict for parity but is NO LONGER asserted
      (D-10c: pllength summary not rendered)
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr(
        "musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
        lambda self: None,
    )
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    # Phase 60.3 Plan 02 regression-protection: helper now fires cover-art lookup.
    # Mock to preserve offline-CI invariant (existing test does not assert cover-art behaviour).
    monkeypatch.setattr(panel, "_fetch_cover_art_async", MagicMock())
    panel._gbs_poll_token = 5  # set known token
    state = {
        "now_playing_entryid": 1810736,
        "now_playing_songid": 782491,
        "icy_title": "Crippling Alcoholism - Templeton",
        # 60-10 / T8: queue_summary is no longer rendered (D-10c). Replace with
        # queue_rows so the test exercises the new enumerated-rendering path.
        "queue_summary": "Playlist is 11:21 long with 3 dongs",  # kept on state dict for parity, but no longer asserted on
        "queue_rows": [
            {"entryid": 1810810, "songid": 1, "artist": "Foo", "title": "Bar", "duration": "3:00"},
            {"entryid": 1810811, "songid": 2, "artist": "Baz", "title": "Quux", "duration": "4:30"},
        ],
        "score": "5.0 (1 vote)",
        "user_vote": 0,
        "queue_html_snippets": [],
        "removed_ids": [],
    }
    panel._on_gbs_playlist_ready(5, state)
    items = [
        panel._gbs_playlist_widget.item(i).text()
        for i in range(panel._gbs_playlist_widget.count())
    ]
    # Now-playing prefixed with arrow marker (unchanged)
    assert any("Crippling Alcoholism - Templeton" in t for t in items)
    # 60-10 / T8: queue_rows enumerated per D-10b — was queue_summary "Playlist is 11:21" (REMOVED).
    assert any("1. Foo - Bar [3:00]" in t for t in items)
    assert any("2. Baz - Quux [4:30]" in t for t in items)
    # 60-10 / T8: pllength summary line is NOT rendered (D-10c).
    assert not any("Playlist is 11:21" in t for t in items)
    # Score (unchanged)
    assert any("5.0 (1 vote)" in t for t in items)


def test_gbs_poll_timer_pauses_when_widget_hidden(qtbot, tmp_path, monkeypatch):
    """Pitfall 5 / D-06a: rebinding to non-GBS station must stop the timer."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr(
        "musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
        lambda self: None,
    )
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    assert panel._gbs_poll_timer.isActive() is True
    # Re-bind to non-GBS — timer must stop
    panel.bind_station(_make_gbs_station(provider_name="DI.fm"))
    assert panel._gbs_poll_timer.isActive() is False
    assert panel._gbs_playlist_widget.isVisible() is False


def test_gbs_stale_token_discarded(qtbot, tmp_path, monkeypatch):
    """Pitfall 1: old-token playlist_ready must NOT mutate the widget."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_gbs_panel(qtbot)
    panel._gbs_poll_token = 10
    # Pre-populate so we can detect mutation
    panel._gbs_playlist_widget.addItem("BASELINE")
    assert panel._gbs_playlist_widget.count() == 1
    # Emit with stale token (3 != 10)
    panel._on_gbs_playlist_ready(3, {"icy_title": "should not render"})
    assert panel._gbs_playlist_widget.count() == 1
    assert panel._gbs_playlist_widget.item(0).text() == "BASELINE"


def test_gbs_auth_expired_hides_widget_no_toast(qtbot, tmp_path, monkeypatch):
    """Pitfall 3: auth_expired -> widget hidden + timer stopped, no toast spam."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr(
        "musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
        lambda self: None,
    )
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    panel._gbs_poll_token = 5
    panel._gbs_playlist_widget.setVisible(True)
    panel._gbs_poll_timer.start()
    panel._on_gbs_playlist_error(5, "auth_expired")
    assert panel._gbs_playlist_widget.isVisible() is False
    assert panel._gbs_poll_timer.isActive() is False


def test_refresh_gbs_visibility_runs_once_per_bind_station(qtbot, tmp_path, monkeypatch):
    """Phase 64 D-04 invariant: _refresh_gbs_visibility is called EXACTLY once per bind_station."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_gbs_panel(qtbot)
    counter = {"n": 0}
    original = panel._refresh_gbs_visibility

    def counting_refresh():
        counter["n"] += 1
        original()

    monkeypatch.setattr(panel, "_refresh_gbs_visibility", counting_refresh)
    panel.bind_station(_make_gbs_station(provider_name="DI.fm"))
    assert counter["n"] == 1


def test_gbs_playlist_resets_position_on_track_change(qtbot, tmp_path, monkeypatch):
    """HIGH 4 fix: position cursor resets to 0 on track-entryid change.

    Three-step sequence:
      1. First call: entryid=100, song_position=200 -> cursor["position"] == 0 (new track)
      2. Second call: entryid=200 (different), song_position=15 -> cursor["position"] == 0
         (reset on track transition, NOT 15)
      3. Third call: entryid=200 (same as #2), song_position=42 -> cursor["position"] == 42
         (advances normally when entryid is stable)
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_gbs_panel(qtbot)
    panel._gbs_poll_token = 7

    # Step 1: first poll response — brand-new entryid (no prev_entryid)
    panel._on_gbs_playlist_ready(7, {
        "now_playing_entryid": 100,
        "song_position": 200,
    })
    # New entryid, no previous -> track_changed=True -> position reset to 0
    assert panel._gbs_poll_cursor.get("position") == 0

    # Step 2: different entryid -> track transition -> position reset to 0
    panel._on_gbs_playlist_ready(7, {
        "now_playing_entryid": 200,
        "song_position": 15,
    })
    assert panel._gbs_poll_cursor.get("position") == 0, (
        "Expected position=0 on track change (HIGH 4 fix), got "
        + str(panel._gbs_poll_cursor.get("position"))
    )

    # Step 3: same entryid as step 2 -> position advances normally
    panel._on_gbs_playlist_ready(7, {
        "now_playing_entryid": 200,
        "song_position": 42,
    })
    assert panel._gbs_poll_cursor.get("position") == 42


# ===========================================================================
# Phase 60.3 Plan 01: scaffolding tests for _gbs_label_source + _gbs_poll_in_flight
# ===========================================================================


def test_gbs_label_source_default_none_outside_gbs(qtbot, tmp_path, monkeypatch):
    """Phase 60.3 Plan 01: source flag is None after a non-GBS bind."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_gbs_panel(qtbot)
    # Non-GBS station bind
    non_gbs = _make_gbs_station(provider_name="SomaFM", name="Drone Zone")
    panel.bind_station(non_gbs)
    assert panel._gbs_label_source is None


def test_gbs_label_source_resets_on_leaving_gbs_context(qtbot, tmp_path, monkeypatch):
    """Phase 60.3 Plan 01: _refresh_gbs_visibility resets source flag on context exit."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr(
        "musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
        lambda self: None,
    )
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    # Simulate a writer having flipped the flag (Plans 02/03 do this for real)
    panel._gbs_label_source = "ajax"
    # Now bind a non-GBS station — _refresh_gbs_visibility should reset the flag
    panel.bind_station(_make_gbs_station(provider_name="SomaFM", name="Drone Zone"))
    assert panel._gbs_label_source is None


def test_gbs_poll_in_flight_predicate_truth_table(qtbot, tmp_path, monkeypatch):
    """Phase 60.3 Plan 01 / D-04: predicate truth table over the SYNC-05 slot."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_gbs_panel(qtbot)
    # State 1: worker is None
    panel._gbs_poll_worker = None
    assert panel._gbs_poll_in_flight() is False
    # State 2: worker exists but isRunning() returns False
    finished_worker = MagicMock()
    finished_worker.isRunning.return_value = False
    panel._gbs_poll_worker = finished_worker
    assert panel._gbs_poll_in_flight() is False
    # State 3: worker exists and isRunning() returns True
    running_worker = MagicMock()
    running_worker.isRunning.return_value = True
    panel._gbs_poll_worker = running_worker
    assert panel._gbs_poll_in_flight() is True


# ===========================================================================
# Phase 60.3 Plan 02: D-01/D-06/D-07 /ajax-stamping + icy_disabled lock tests
# ===========================================================================


def test_gbs_icy_label_upgrades_on_ajax_after_icy(qtbot, tmp_path, monkeypatch):
    """Phase 60.3 T-60.3-01 / D-01/D-06: bare ICY arrives first, /ajax upgrades to full Artist - Title.

    After /ajax stamps:
      - icy_label.text() == full "Artist - Title" string
      - _last_icy_title == same full string (D-06 single coupling point)
      - _gbs_label_source == 'ajax'
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr(
        "musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
        lambda self: None,
    )
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    gbs_station = _make_gbs_station()
    # Per checker BLOCKER #1: MagicMock auto-attribute icy_disabled is truthy by default.
    # Explicit override required so bind_station does NOT take the icy_disabled fallback
    # and on_title_changed does NOT early-return at line 524.
    gbs_station.icy_disabled = False
    panel.bind_station(gbs_station)
    # Mock cover-art fetch BEFORE on_title_changed — that slot also triggers
    # _fetch_cover_art_async (line 555). Mocking only after bind_station but
    # before any code path that hits _fetch_cover_art_async preserves the
    # offline-CI invariant and prevents a daemon thread from emitting against
    # the panel signal after the qtbot teardown.
    monkeypatch.setattr(panel, "_fetch_cover_art_async", MagicMock())
    panel._gbs_poll_token = 5
    # 1) Bare ICY arrives first (pre-/ajax bridge — flows through on_title_changed unchanged in Plan 02)
    panel.on_title_changed("La Frontière de la Nuit")
    assert panel.icy_label.text() == "La Frontière de la Nuit"
    assert panel._last_icy_title == "La Frontière de la Nuit"
    # 2) /ajax arrives, upgrades to full Artist - Title via _apply_gbs_icy_label
    panel._on_gbs_playlist_ready(5, {
        "now_playing_entryid": 1810736,
        "icy_title": "Cimerion & Oublieth (Arcanes) - La Frontière de la Nuit",
        "queue_rows": [],
        "removed_ids": [],
        "queue_html_snippets": [],
        "user_vote": 0,
    })
    assert panel.icy_label.text() == "Cimerion & Oublieth (Arcanes) - La Frontière de la Nuit"
    assert panel._last_icy_title == "Cimerion & Oublieth (Arcanes) - La Frontière de la Nuit"
    assert panel._gbs_label_source == "ajax"


def test_gbs_ajax_stamps_label_first_no_prior_icy(qtbot, tmp_path, monkeypatch):
    """Phase 60.3 D-01: cold /ajax response stamps icy_label even with no prior on_title_changed.

    Scenario: user binds GBS station; /ajax response arrives BEFORE any
    ICY tag (race possible if GStreamer takes longer to parse than /ajax round-trip).
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr(
        "musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
        lambda self: None,
    )
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    gbs_station = _make_gbs_station()
    # Per checker BLOCKER #1: explicit override (see preamble in test above).
    gbs_station.icy_disabled = False
    panel.bind_station(gbs_station)
    # Mock cover-art fetch — this test asserts on label text + source flag, not on cover-art.
    monkeypatch.setattr(panel, "_fetch_cover_art_async", MagicMock())
    panel._gbs_poll_token = 5
    # No prior on_title_changed — go straight to /ajax response
    panel._on_gbs_playlist_ready(5, {
        "now_playing_entryid": 1810736,
        "icy_title": "Artist X - Track Y",
        "queue_rows": [],
        "removed_ids": [],
        "queue_html_snippets": [],
        "user_vote": 0,
    })
    assert panel.icy_label.text() == "Artist X - Track Y"
    assert panel._last_icy_title == "Artist X - Track Y"
    assert panel._gbs_label_source == "ajax"


def test_gbs_icy_disabled_suppresses_ajax_stamp(qtbot, tmp_path, monkeypatch):
    """Phase 60.3 T-60.3-09 / Open Question 1 lock: icy_disabled=True on a GBS station
    suppresses /ajax label stamping (consistent with on_title_changed gate at line 524).

    After /ajax response with icy_disabled=True:
      - icy_label.text() == station name (the bind_station fallback)
      - _last_icy_title == "" (the bind_station reset)
      - _gbs_label_source != 'ajax' (helper early-returned before the flip)
      - _fetch_cover_art_async NOT called
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr(
        "musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
        lambda self: None,
    )
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    # Bind a GBS station with icy_disabled=True (explicit — testing the LOCK)
    gbs_station = _make_gbs_station()
    gbs_station.icy_disabled = True
    panel.bind_station(gbs_station)
    # Spy on cover-art fetch to verify it is not called
    fetch_mock = MagicMock()
    monkeypatch.setattr(panel, "_fetch_cover_art_async", fetch_mock)
    panel._gbs_poll_token = 5
    # /ajax response arrives — helper should early-return on icy_disabled
    panel._on_gbs_playlist_ready(5, {
        "now_playing_entryid": 1810736,
        "icy_title": "Artist X - Track Y",
        "queue_rows": [],
        "removed_ids": [],
        "queue_html_snippets": [],
        "user_vote": 0,
    })
    # Label keeps the bind_station fallback (station name); _last_icy_title is "" from bind reset
    assert panel.icy_label.text() == gbs_station.name
    assert panel._last_icy_title == ""
    assert panel._gbs_label_source != "ajax"
    fetch_mock.assert_not_called()


# ===========================================================================
# Phase 60 / GBS-01d: vote control on NowPlayingPanel
# ===========================================================================


def _make_state(entryid: int = 1810736, user_vote: int = 0,
               icy_title: str = "Test Artist - Test Title"):
    """Folded /ajax state shape from gbs_api.fetch_active_playlist."""
    return {
        "now_playing_entryid": entryid,
        "now_playing_songid": 1,
        "icy_title": icy_title,
        "user_vote": user_vote,
        "score": "5.0 (1 vote)" if user_vote == 0 else f"{user_vote}.0 (1 vote)",
        "queue_html_snippets": [],
        "removed_ids": [],
    }


def test_gbs_vote_buttons_hidden_for_non_gbs(qtbot, tmp_path, monkeypatch):
    """D-07: non-GBS station bound -> all 5 buttons invisible."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_gbs_panel(qtbot)
    panel.bind_station(_make_gbs_station(provider_name="DI.fm"))
    for btn in panel._gbs_vote_buttons:
        assert btn.isVisible() is False


def test_gbs_vote_buttons_hidden_when_logged_out(qtbot, tmp_path, monkeypatch):
    """D-07 / D-04 ladder #3: GBS station, no cookies file -> buttons invisible."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_gbs_panel(qtbot)
    panel.bind_station(_make_gbs_station())  # GBS but no cookies file
    for btn in panel._gbs_vote_buttons:
        assert btn.isVisible() is False


def test_gbs_vote_buttons_visible_when_gbs_and_logged_in(qtbot, tmp_path, monkeypatch):
    """D-07: GBS + cookies -> buttons visible, count == 5."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    for btn in panel._gbs_vote_buttons:
        assert not btn.isHidden()
    assert len(panel._gbs_vote_buttons) == 5


def test_gbs_vote_optimistic_success(qtbot, tmp_path, monkeypatch):
    """Pitfall 2: server-returned user_vote is the FINAL highlighted state."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsVoteWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    # Stamp entryid via the playlist-ready hook (Pitfall 1)
    panel._gbs_poll_token = 1
    panel._on_gbs_playlist_ready(1, _make_state(entryid=999, user_vote=0))
    assert panel._gbs_current_entryid == 999
    # Simulate a click on button 3 (index 2)
    btn3 = panel._gbs_vote_buttons[2]  # vote_value=3
    btn3.click()
    # Optimistic: button 3 highlighted
    assert btn3.isChecked() is True
    assert panel._current_highlighted_vote() == 3
    # Worker emits server-confirmed user_vote=3
    panel._on_gbs_vote_finished(panel._gbs_vote_token, 3, 0, "4.0 (2 votes)")
    assert panel._current_highlighted_vote() == 3


def test_gbs_vote_optimistic_rollback_on_error(qtbot, tmp_path, monkeypatch):
    """Worker error -> button reverts to prior_vote, toast emitted."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsVoteWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    panel._gbs_poll_token = 1
    panel._on_gbs_playlist_ready(1, _make_state(entryid=999, user_vote=0))
    captured_toasts = []
    panel.gbs_vote_error_toast.connect(captured_toasts.append)
    panel._gbs_vote_buttons[2].click()  # click button 3
    panel._on_gbs_vote_error(panel._gbs_vote_token, 0, "Connection refused")
    # Highlight reverts to prior_vote=0 (no button highlighted)
    assert panel._current_highlighted_vote() == 0
    assert any("Vote failed" in t and "Connection refused" in t for t in captured_toasts)


def test_gbs_vote_optimistic_rollback_on_auth_expired(qtbot, tmp_path, monkeypatch):
    """auth_expired path -> 'session expired' toast + rollback."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsVoteWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    panel._gbs_poll_token = 1
    panel._on_gbs_playlist_ready(1, _make_state(entryid=999, user_vote=0))
    captured_toasts = []
    panel.gbs_vote_error_toast.connect(captured_toasts.append)
    panel._gbs_vote_buttons[2].click()
    panel._on_gbs_vote_error(panel._gbs_vote_token, 0, "auth_expired")
    assert panel._current_highlighted_vote() == 0
    assert any("session expired" in t.lower() and "Accounts" in t for t in captured_toasts)


def test_gbs_vote_entryid_only_from_ajax(qtbot, tmp_path, monkeypatch):
    """Pitfall 1: ICY title change does NOT update _gbs_current_entryid."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_gbs_panel(qtbot)
    assert panel._gbs_current_entryid is None
    # Simulate ICY title change (on_title_changed should NOT update entryid)
    if hasattr(panel, "on_title_changed"):
        panel.on_title_changed("New Track - New Title")
    # _gbs_current_entryid still None
    assert panel._gbs_current_entryid is None
    # Now simulate /ajax response — this is the ONLY way entryid gets set
    panel._gbs_poll_token = 1
    panel._on_gbs_playlist_ready(1, _make_state(entryid=12345))
    assert panel._gbs_current_entryid == 12345


def test_gbs_vote_clicking_same_value_clears(qtbot, tmp_path, monkeypatch):
    """RESEARCH §Capability 4: re-clicking the same vote value submits vote=0 (clear)."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    captured_worker_args = {}

    # Use a plain object (not MagicMock subclass) so __init__ kwargs are
    # captured reliably without MagicMock intercepting the call protocol.
    class FakeVoteWorker:
        def __init__(self, *args, **kwargs):
            captured_worker_args["kwargs"] = kwargs

        def start(self):
            pass

        def vote_finished(self, *args):
            pass

        def vote_error(self, *args):
            pass

        def connect(self, *args):
            pass

    # Patch the signals too since connect() is called on them
    import musicstreamer.ui_qt.now_playing_panel as _npp_mod
    original_worker = _npp_mod._GbsVoteWorker

    class _CapturingWorker:
        """Captures kwargs and provides no-op signal stubs."""
        def __init__(self, *args, **kwargs):
            captured_worker_args["kwargs"] = kwargs
            self._token = kwargs.get("token", 0)

        def start(self):
            pass

        class _Sig:
            def connect(self, *a): pass

        vote_finished = _Sig()
        vote_error = _Sig()

    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsVoteWorker", _CapturingWorker)
    panel.bind_station(_make_gbs_station())
    panel._gbs_poll_token = 1
    # Pre-set highlight to 3 via server-confirmed vote
    panel._on_gbs_playlist_ready(1, _make_state(entryid=999, user_vote=3))
    assert panel._current_highlighted_vote() == 3
    # Click button '3' again -> should submit vote=0 (clear)
    panel._gbs_vote_buttons[2].click()
    assert captured_worker_args["kwargs"]["vote_value"] == 0


def test_gbs_vote_stale_token_discarded(qtbot, tmp_path, monkeypatch):
    """Stale vote_finished from a stale token must NOT mutate the highlight."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_gbs_panel(qtbot)
    panel._gbs_vote_token = 10
    panel._apply_vote_highlight(2)  # Set baseline highlight
    panel._on_gbs_vote_finished(3, 5, 0, "5.0 (1 vote)")  # stale token=3
    assert panel._current_highlighted_vote() == 2


def test_gbs_vote_no_entryid_ignores_click(qtbot, tmp_path, monkeypatch):
    """In-handler entryid-None guard returns silently with no worker started.

    60-09 / T10: after this plan, the vote buttons are also DISABLED at the
    Qt level when entryid is None. This test bypasses the Qt gate via a
    direct _on_gbs_vote_clicked call so the IN-HANDLER guard at line 1031
    remains exercised — defense-in-depth coverage.
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    assert panel._gbs_current_entryid is None
    started = []
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsVoteWorker.start",
                        lambda self: started.append(True))
    # 60-09: bypass the disabled-button Qt gate by temporarily enabling the
    # button so we can reach the in-handler guard (the button is disabled
    # while entryid is None after this plan's fix).
    panel._gbs_vote_buttons[2].setEnabled(True)
    panel._gbs_vote_buttons[2].click()  # now reaches handler; in-handler guard catches None
    assert started == [], "in-handler guard must drop click when _gbs_current_entryid is None"


# ---------------------------------------------------------------------------
# Phase 60-09 TDD-RED: 3 failing tests for T10 (vote button enable gate) +
# T11 (cookies-None toast emission)
# ---------------------------------------------------------------------------


def test_gbs_vote_buttons_disabled_until_entryid_stamped(qtbot, tmp_path, monkeypatch):
    """60-09 / T10 (RED): vote buttons must be disabled until /ajax stamps entryid.

    Currently fails: buttons are enabled by default after setVisible(True).
    Fix (Task 2): add setEnabled(False) in the construction loop; enable via
    _apply_vote_buttons_enabled(True) in _on_gbs_playlist_ready.
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    # Buttons should be visible (GBS + logged in) but DISABLED until entryid arrives
    for btn in panel._gbs_vote_buttons:
        assert not btn.isHidden(), "button should be visible after bind"
        assert btn.isEnabled() is False, (
            f"button {btn.property('vote_value')} must be DISABLED "
            "until /ajax stamps _gbs_current_entryid"
        )


def test_gbs_vote_buttons_enabled_after_first_ajax(qtbot, tmp_path, monkeypatch):
    """60-09 / T10 (RED): buttons become enabled once _on_gbs_playlist_ready stamps entryid.

    Currently fails: _on_gbs_playlist_ready does not call any enable toggle.
    Fix (Task 2): _on_gbs_playlist_ready calls _apply_vote_buttons_enabled(True)
    inside the `if new_entryid is not None` block.
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    # Pre-condition: all buttons disabled (before /ajax response)
    for btn in panel._gbs_vote_buttons:
        assert btn.isEnabled() is False, "pre-condition: must be disabled before first poll"
    # Simulate a successful /ajax response that stamps the entryid
    panel._gbs_poll_token = 1
    panel._on_gbs_playlist_ready(1, _make_state(entryid=1810809, user_vote=0))
    assert panel._gbs_current_entryid == 1810809
    # After /ajax stamps entryid, all buttons must be enabled
    for btn in panel._gbs_vote_buttons:
        assert btn.isEnabled() is True, (
            f"button {btn.property('vote_value')} must be ENABLED "
            "after _on_gbs_playlist_ready stamps entryid"
        )


def test_gbs_vote_emits_toast_when_cookies_disappear_mid_click(qtbot, tmp_path, monkeypatch):
    """60-09 / T11 (RED): cookies-None guard must emit gbs_vote_error_toast.

    Currently fails: the cookies-None branch at _on_gbs_vote_clicked line 1050
    silently rolls back + hides, but never emits gbs_vote_error_toast.
    Fix (Task 2): emit gbs_vote_error_toast with auth-expired message before returning.

    NOTE (iter-2 plan-check caveat): after Task 2's Step 2a, the button is
    DISABLED at construction time and stays disabled until entryid is stamped.
    This test stamps entryid directly AND calls setEnabled(True) on the button
    before click() so the vote handler is reached and the cookies-None branch
    is exercised.

    Implementation note: _refresh_gbs_visibility calls _on_gbs_poll_tick which
    can recurse when load_auth_context=None AND the cookie file still exists.
    We stub _on_gbs_poll_tick to a no-op so the test is isolated to the click-
    time cookies-None path, not the poll-tick recursion path.
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    # Stamp entryid directly (simulating a successful /ajax poll)
    panel._gbs_current_entryid = 1810809
    panel._last_confirmed_vote = 0
    # Simulate cookies disappearing mid-session — patch load_auth_context to return None.
    # Also stub _on_gbs_poll_tick to prevent recursion in _refresh_gbs_visibility:
    # (_refresh_gbs_visibility calls _on_gbs_poll_tick when should_show=True; if
    # load_auth_context returns None inside _on_gbs_poll_tick, it calls
    # _refresh_gbs_visibility again — infinite loop. Production avoids this because
    # the actual file removal also changes _is_gbs_logged_in(); test decouples them.)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: None)
    monkeypatch.setattr(panel, "_on_gbs_poll_tick", lambda: None)
    # Per iter-2 plan-check caveat: enable the button so click() reaches the handler
    panel._gbs_vote_buttons[2].setEnabled(True)
    # Expect gbs_vote_error_toast to fire with "session expired" in the message
    with qtbot.waitSignal(panel.gbs_vote_error_toast, timeout=1000) as blocker:
        panel._gbs_vote_buttons[2].click()
    assert "session expired" in blocker.args[0].lower(), (
        f"Expected 'session expired' in toast text, got: {blocker.args[0]!r}"
    )


# ---------- Plan 60-10: queue enumeration renderer tests (T8) ----------

def test_gbs_playlist_renders_enumerated_queue(qtbot, tmp_path, monkeypatch):
    """60-10 / T8 (RED): _on_gbs_playlist_ready must render one row per queue_rows entry.

    Passes a state dict with 3 queue_rows entries and asserts the widget count
    and D-10b row format ('{n}. {artist} - {title} [{duration}]').

    Currently FAILS: renderer reads queue_summary (ignored here), never queue_rows.
    Fix (Task 3): add queue_rows loop in _on_gbs_playlist_ready + _GBS_QUEUE_MAX_ROWS cap.
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr(
        "musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
        lambda self: None,
    )
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    panel._gbs_poll_token = 1
    state = {
        "now_playing_entryid": 99,
        "now_playing_songid": None,
        "icy_title": "Now Playing - Artist",
        "score": "5 (3 votes)",
        "user_vote": 0,
        "queue_rows": [
            {"entryid": 100, "songid": 1, "artist": "A1", "title": "T1", "duration": "3:00"},
            {"entryid": 101, "songid": 2, "artist": "A2", "title": "T2", "duration": "4:00"},
            {"entryid": 102, "songid": 3, "artist": "A3", "title": "T3", "duration": "2:30"},
        ],
        "queue_html_snippets": [],
        "removed_ids": [],
    }
    panel._on_gbs_playlist_ready(1, state)
    count = panel._gbs_playlist_widget.count()
    assert count == 5, (
        f"Expected 5 items (1 now-playing + 3 queue + 1 score); got {count}"
    )
    # D-10b format: '{n}. {artist} - {title} [{duration}]'
    assert panel._gbs_playlist_widget.item(1).text() == "1. A1 - T1 [3:00]", (
        f"Row 1 format incorrect: {panel._gbs_playlist_widget.item(1).text()!r}"
    )
    assert panel._gbs_playlist_widget.item(2).text() == "2. A2 - T2 [4:00]"
    assert panel._gbs_playlist_widget.item(3).text() == "3. A3 - T3 [2:30]"


def test_gbs_playlist_caps_queue_at_10(qtbot, tmp_path, monkeypatch):
    """60-10 / T8 / D-10a (RED): _on_gbs_playlist_ready caps queue_rows at 10 entries.

    Passes 15 queue_rows and asserts widget count == 12 (1 now-playing + 10 capped + 1 score).
    The 10th item must start with '10.'.

    Currently FAILS: no cap exists (the loop itself does not exist yet).
    Fix (Task 3): add [:_GBS_QUEUE_MAX_ROWS] slice in the queue_rows loop.
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
    panel = _construct_gbs_panel(qtbot)
    monkeypatch.setattr(
        "musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
        lambda self: None,
    )
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_gbs_station())
    panel._gbs_poll_token = 2
    queue_rows = [
        {"entryid": 1000 + i, "songid": i, "artist": f"Artist{i}", "title": f"Title{i}", "duration": "3:00"}
        for i in range(15)
    ]
    state = {
        "now_playing_entryid": 999,
        "now_playing_songid": None,
        "icy_title": "Now Playing - Test",
        "score": "3 (1 vote)",
        "user_vote": 0,
        "queue_rows": queue_rows,
        "queue_html_snippets": [],
        "removed_ids": [],
    }
    panel._on_gbs_playlist_ready(2, state)
    count = panel._gbs_playlist_widget.count()
    assert count == 12, (
        f"Expected 12 items (1 now-playing + 10 capped + 1 score); got {count}"
    )
    # The 10th queue item (index 10) must start with '10.'
    assert panel._gbs_playlist_widget.item(10).text().startswith("10."), (
        f"item(10) should start with '10.'; got: {panel._gbs_playlist_widget.item(10).text()!r}"
    )
