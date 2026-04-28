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
    def __init__(self, settings: Optional[dict] = None) -> None:
        self._settings = dict(settings or {})
        self._favorites: list = []

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
