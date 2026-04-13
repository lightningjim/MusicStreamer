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

    def __init__(self) -> None:
        super().__init__()
        self.set_volume_calls: List[float] = []
        self.stop_called: bool = False
        self.pause_called: bool = False
        self.play_calls: List[Station] = []

    def set_volume(self, v: float) -> None:
        self.set_volume_calls.append(v)

    def stop(self) -> None:
        self.stop_called = True

    def pause(self) -> None:
        self.pause_called = True

    def play(self, station, **kwargs) -> None:
        self.play_calls.append(station)


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
