"""Tests for the Linux MPRIS2 backend — cover-art cache (Tests 1-5) and
LinuxMprisBackend (Tests 6-12).

Run unit tests only (no D-Bus integration):
    uv run --with pytest --with pytest-qt pytest tests/test_media_keys_mpris2.py -v -m "not integration"

Run integration tests (requires session bus + playerctl):
    uv run --with pytest --with pytest-qt pytest tests/test_media_keys_mpris2.py::test_playerctl_lists_service -v
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest
from PySide6.QtCore import Qt
from PySide6.QtDBus import QDBusAbstractAdaptor, QDBusConnection
from PySide6.QtGui import QPixmap

import musicstreamer.paths as paths
from musicstreamer.models import Station


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_station(station_id: int = 42, name: str = "Test Station") -> Station:
    return Station(
        id=station_id,
        name=name,
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
    )


def _red_pixmap(w: int = 10, h: int = 10) -> QPixmap:
    px = QPixmap(w, h)
    px.fill(Qt.GlobalColor.red)
    return px


# ===========================================================================
# Task 1: _art_cache tests (Tests 1-5)
# ===========================================================================


def test_cover_path_for_station_returns_correct_path_and_creates_dir(tmp_path, monkeypatch):
    """Test 1: cover_path_for_station(42) returns .../mpris-art/42.png and parent exists."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys._art_cache import cover_path_for_station

    result = cover_path_for_station(42)
    assert result.endswith(os.path.join("mpris-art", "42.png"))
    assert os.path.isdir(os.path.dirname(result))


def test_write_cover_png_none_pixmap_returns_none(tmp_path, monkeypatch):
    """Test 2: write_cover_png(None, 42) returns None without creating a file."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys._art_cache import cover_path_for_station, write_cover_png

    result = write_cover_png(None, 42)
    assert result is None
    assert not os.path.exists(cover_path_for_station(42))


def test_write_cover_png_valid_pixmap_creates_file(tmp_path, monkeypatch, qapp):
    """Test 3: write_cover_png with valid pixmap returns path, file exists, > 50 bytes."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys._art_cache import write_cover_png

    px = _red_pixmap()
    result = write_cover_png(px, 42)

    assert result is not None
    assert result.endswith(os.path.join("mpris-art", "42.png"))
    assert os.path.isfile(result)
    assert os.path.getsize(result) > 50


def test_write_cover_png_overwrites_same_file(tmp_path, monkeypatch, qapp):
    """Test 4: Calling write_cover_png twice for same station_id overwrites in place — no second file."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys._art_cache import cover_path_for_station, write_cover_png

    px1 = _red_pixmap()
    px2 = QPixmap(10, 10)
    px2.fill(Qt.GlobalColor.blue)

    write_cover_png(px1, 42)
    write_cover_png(px2, 42)

    art_dir = os.path.dirname(cover_path_for_station(42))
    files_in_dir = os.listdir(art_dir)
    assert files_in_dir == ["42.png"], f"Expected only 42.png, got {files_in_dir}"


def test_write_cover_png_respects_root_override(tmp_path, monkeypatch, qapp):
    """Test 5: With _root_override set, cache dir is under tmp_path (no writes to real ~/.cache)."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys._art_cache import cover_path_for_station, write_cover_png

    px = _red_pixmap()
    result = write_cover_png(px, 99)

    assert result is not None
    assert result.startswith(str(tmp_path)), (
        f"Expected path under {tmp_path}, got {result}"
    )
    assert os.path.isfile(result)


# ===========================================================================
# Task 2: LinuxMprisBackend tests (Tests 6-12)
# ===========================================================================

BUS_AVAILABLE = QDBusConnection.sessionBus().isConnected()
skip_if_no_bus = pytest.mark.skipif(
    not BUS_AVAILABLE, reason="no D-Bus session bus"
)


@skip_if_no_bus
def test_linux_mpris_backend_constructs(tmp_path, monkeypatch, qapp):
    """Test 6: LinuxMprisBackend constructs and registers the MPRIS2 service."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys.mpris2 import LinuxMprisBackend

    backend = LinuxMprisBackend(None, None)
    try:
        # Service should be registered on the bus
        bus = QDBusConnection.sessionBus()
        registered = bus.interface().registeredServiceNames().value()
        assert "org.mpris.MediaPlayer2.musicstreamer" in registered
    finally:
        backend.shutdown()


@skip_if_no_bus
def test_linux_mpris_backend_publish_metadata(tmp_path, monkeypatch, qapp):
    """Test 7: publish_metadata updates station/title/art_url, file is created."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys.mpris2 import LinuxMprisBackend

    station = _make_station(station_id=7, name="Jazz FM")
    px = _red_pixmap()

    backend = LinuxMprisBackend(None, None)
    try:
        backend.publish_metadata(station, "Miles Davis - Kind of Blue", px)

        assert backend._station is station
        assert backend._title == "Miles Davis - Kind of Blue"
        assert backend._art_url.startswith("file://")
        art_file = backend._art_url[len("file://"):]
        assert os.path.isfile(art_file)
    finally:
        backend.shutdown()


@skip_if_no_bus
def test_linux_mpris_backend_publish_metadata_none(tmp_path, monkeypatch, qapp):
    """Test 8: publish_metadata(None, '', None) -> metadata dict has only NoTrack trackid."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys.mpris2 import LinuxMprisBackend
    from PySide6.QtDBus import QDBusObjectPath

    backend = LinuxMprisBackend(None, None)
    try:
        backend.publish_metadata(None, "", None)

        meta = backend._build_metadata_dict()
        assert "mpris:trackid" in meta
        assert isinstance(meta["mpris:trackid"], QDBusObjectPath)
        assert "NoTrack" in meta["mpris:trackid"].path()
        assert backend._art_url == ""
    finally:
        backend.shutdown()


@skip_if_no_bus
def test_linux_mpris_backend_set_playback_state(tmp_path, monkeypatch, qapp):
    """Test 9: set_playback_state updates _state; bogus state raises ValueError."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys.mpris2 import LinuxMprisBackend

    backend = LinuxMprisBackend(None, None)
    try:
        backend.set_playback_state("playing")
        assert backend._state == "playing"

        backend.set_playback_state("paused")
        assert backend._state == "paused"

        backend.set_playback_state("stopped")
        assert backend._state == "stopped"

        with pytest.raises(ValueError):
            backend.set_playback_state("bogus")
    finally:
        backend.shutdown()


@pytest.mark.integration
@skip_if_no_bus
def test_playerctl_lists_service(tmp_path, monkeypatch, qapp):
    """Test 10: After construction, 'playerctl --list-all' lists 'musicstreamer'."""
    if shutil.which("playerctl") is None:
        pytest.skip("playerctl not installed")

    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys.mpris2 import LinuxMprisBackend

    backend = LinuxMprisBackend(None, None)
    try:
        result = subprocess.run(
            ["playerctl", "--list-all"],
            capture_output=True, text=True, timeout=2,
        )
        assert "musicstreamer" in result.stdout, (
            f"Expected 'musicstreamer' in playerctl output, got: {result.stdout!r}"
        )
    finally:
        backend.shutdown()


@skip_if_no_bus
def test_linux_mpris_backend_slot_play_pause_emits_signal(tmp_path, monkeypatch, qtbot, qapp):
    """Test 11: Invoking the player adaptor's PlayPause slot emits play_pause_requested."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys.mpris2 import LinuxMprisBackend

    backend = LinuxMprisBackend(None, None)
    try:
        with qtbot.waitSignal(backend.play_pause_requested, timeout=1000):
            backend._player_adaptor.PlayPause()
    finally:
        backend.shutdown()


@skip_if_no_bus
def test_linux_mpris_backend_shutdown_idempotent(tmp_path, monkeypatch, qapp):
    """Test 12: shutdown() called twice does not raise."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys.mpris2 import LinuxMprisBackend

    backend = LinuxMprisBackend(None, None)
    backend.shutdown()
    backend.shutdown()  # must not raise
