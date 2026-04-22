"""Tests for musicstreamer.media_keys.smtc (Phase 43.1).

Linux-only unit tests. All winrt interactions are mocked via sys.modules
injection. Real Windows integration is UAT on the Win11 VM (Plan 06).
"""
from __future__ import annotations

import sys
import tomllib
import types
import unittest.mock as mock  # noqa: F401
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# -------------------------------------------------------------------------
# Shared mock-winrt fixtures (used by Plans 43.1-03, 04, 05 tests)
# -------------------------------------------------------------------------

_WINRT_MODULES = [
    "winrt",
    "winrt.windows",
    "winrt.windows.media",
    "winrt.windows.media.playback",
    "winrt.windows.storage",
    "winrt.windows.storage.streams",
    "winrt.windows.foundation",
]


def _namespace(**kwargs):
    ns = types.SimpleNamespace()
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


def _build_winrt_stubs():
    """Construct a minimal winrt namespace tree with the symbols smtc.py imports."""
    # Enum-ish namespaces -- sentinels so `btn == SystemMediaTransportControlsButton.PLAY` works
    button = _namespace(
        PLAY="PLAY",
        PAUSE="PAUSE",
        STOP="STOP",
        NEXT="NEXT",
        PREVIOUS="PREVIOUS",
        RECORD="RECORD",
        FAST_FORWARD="FAST_FORWARD",
        REWIND="REWIND",
        CHANNEL_UP="CHANNEL_UP",
        CHANNEL_DOWN="CHANNEL_DOWN",
    )
    status = _namespace(
        PLAYING="PLAYING",
        PAUSED="PAUSED",
        STOPPED="STOPPED",
        CLOSED="CLOSED",
        CHANGING="CHANGING",
    )
    playback_type = _namespace(
        MUSIC="MUSIC",
        VIDEO="VIDEO",
        IMAGE="IMAGE",
        UNKNOWN="UNKNOWN",
    )

    media = types.ModuleType("winrt.windows.media")
    media.MediaPlaybackStatus = status
    media.MediaPlaybackType = playback_type
    media.SystemMediaTransportControlsButton = button

    # MediaPlayer class -- each instance has .system_media_transport_controls,
    # .command_manager, and .close()
    def _make_media_player_instance():
        smtc = MagicMock(name="SystemMediaTransportControls")
        smtc.add_button_pressed = MagicMock(return_value=object())  # sentinel token
        smtc.display_updater = MagicMock(name="DisplayUpdater")
        smtc.display_updater.music_properties = MagicMock(name="MusicDisplayProperties")
        smtc.display_updater.music_properties.title = ""
        smtc.display_updater.music_properties.artist = ""
        cmd_mgr = MagicMock(name="CommandManager")
        cmd_mgr.is_enabled = True  # default; __init__ should flip to False
        mp = MagicMock(name="MediaPlayer")
        mp.system_media_transport_controls = smtc
        mp.command_manager = cmd_mgr
        return mp

    playback = types.ModuleType("winrt.windows.media.playback")
    playback.MediaPlayer = MagicMock(side_effect=_make_media_player_instance)

    storage_streams = types.ModuleType("winrt.windows.storage.streams")
    storage_streams.InMemoryRandomAccessStream = MagicMock(name="InMemoryRandomAccessStream")
    storage_streams.DataWriter = MagicMock(name="DataWriter")
    storage_streams.RandomAccessStreamReference = MagicMock(name="RandomAccessStreamReference")

    foundation = types.ModuleType("winrt.windows.foundation")

    winrt_pkg = types.ModuleType("winrt")
    winrt_pkg.windows = types.ModuleType("winrt.windows")
    winrt_pkg.windows.media = media
    winrt_pkg.windows.storage = types.ModuleType("winrt.windows.storage")
    winrt_pkg.windows.storage.streams = storage_streams
    winrt_pkg.windows.foundation = foundation

    return {
        "winrt": winrt_pkg,
        "winrt.windows": winrt_pkg.windows,
        "winrt.windows.media": media,
        "winrt.windows.media.playback": playback,
        "winrt.windows.storage": winrt_pkg.windows.storage,
        "winrt.windows.storage.streams": storage_streams,
        "winrt.windows.foundation": foundation,
    }


@pytest.fixture
def mock_winrt_modules(monkeypatch):
    """Install a minimal winrt namespace in sys.modules for the duration of the test."""
    stubs = _build_winrt_stubs()
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)

    # Force smtc.py to re-import with the stubs in place
    monkeypatch.delitem(sys.modules, "musicstreamer.media_keys.smtc", raising=False)
    monkeypatch.delitem(sys.modules, "musicstreamer.media_keys", raising=False)

    yield stubs


# -------------------------------------------------------------------------
# Task 1: pyproject.toml [windows] optional-deps group
# -------------------------------------------------------------------------

def test_pyproject_has_windows_optional_deps():
    """D-05: [project.optional-dependencies].windows lists the four pywinrt packages."""
    # Locate pyproject.toml at the repo root — use this file's path as anchor.
    repo_root = Path(__file__).resolve().parent.parent
    pyproject = repo_root / "pyproject.toml"
    assert pyproject.is_file(), f"expected pyproject.toml at {pyproject}"

    with open(pyproject, "rb") as f:
        data = tomllib.load(f)

    optional = data["project"]["optional-dependencies"]
    assert "windows" in optional, "expected [project.optional-dependencies].windows group (D-05)"

    windows_deps = set(optional["windows"])
    expected = {
        "winrt-Windows.Media.Playback",
        "winrt-Windows.Media",
        "winrt-Windows.Storage.Streams",
        "winrt-Windows.Foundation",
    }
    missing = expected - windows_deps
    assert not missing, f"[windows] group missing packages: {sorted(missing)}"


# -------------------------------------------------------------------------
# Task 2: smtc.py Linux-importable + ImportError fallback
# -------------------------------------------------------------------------

def test_smtc_module_linux_importable():
    """D-06: smtc.py imports cleanly on Linux with no winrt in sys.modules."""
    # Fresh import path — remove any prior import to prove module-scope is winrt-free.
    for mod in list(sys.modules):
        if mod == "musicstreamer.media_keys.smtc":
            del sys.modules[mod]

    import musicstreamer.media_keys.smtc as smtc  # noqa: F401

    # Module-scope must not pull in any winrt namespace.
    assert all(not m.startswith("winrt") for m in sys.modules), (
        "smtc.py imported winrt at module scope (violates D-06)"
    )


def test_create_windows_backend_import_error_on_linux():
    """D-07: On Linux (no winrt wheels), create_windows_backend raises ImportError."""
    import pytest
    from musicstreamer.media_keys.smtc import create_windows_backend

    with pytest.raises(ImportError) as exc_info:
        create_windows_backend(None, None)

    msg = str(exc_info.value)
    assert "windows" in msg.lower() or "winrt" in msg.lower(), (
        f"ImportError message should hint at winrt install: {msg!r}"
    )


def test_factory_falls_back_to_noop_on_linux(monkeypatch):
    """D-07 end-to-end: with sys.platform='win32' on Linux (no winrt),
    the factory catches ImportError and returns NoOpMediaKeysBackend."""
    import pytest
    monkeypatch.setattr(sys, "platform", "win32")

    # Clear cached module so the factory's lazy import re-runs cleanly.
    for mod in list(sys.modules):
        if mod == "musicstreamer.media_keys" or mod == "musicstreamer.media_keys.smtc":
            del sys.modules[mod]

    from musicstreamer.media_keys import create, NoOpMediaKeysBackend
    backend = create(None, None)
    assert isinstance(backend, NoOpMediaKeysBackend), (
        f"expected NoOp fallback, got {type(backend).__name__}"
    )


# -------------------------------------------------------------------------
# Task 2 (Plan 43.1-03): WindowsMediaKeysBackend class tests
# -------------------------------------------------------------------------

def test_backend_init_configures_smtc(mock_winrt_modules, qtbot):
    """MEDIA-03: __init__ creates MediaPlayer, disables command_manager, enables play/pause/stop."""
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend

    backend = WindowsMediaKeysBackend(None, None)

    # Pitfall #1: command_manager.is_enabled must be False
    assert backend._media_player.command_manager.is_enabled is False
    # SMTC button enables
    assert backend._smtc.is_play_enabled is True
    assert backend._smtc.is_pause_enabled is True
    assert backend._smtc.is_stop_enabled is True
    assert backend._smtc.is_next_enabled is False
    assert backend._smtc.is_previous_enabled is False
    # Pitfall #7 (UAT 2026-04-21): must explicitly set is_enabled=True or the
    # session is hidden from the Win+V overlay even though buttons are configured
    assert backend._smtc.is_enabled is True
    # Pitfall #4: token must be stored
    assert backend._smtc.add_button_pressed.called
    assert backend._bp_token is not None
    # Initial state
    assert backend._state == "stopped"


def test_play_button_emits_play_pause_signal(mock_winrt_modules, qtbot):
    """MEDIA-04: PLAY button routes to play_pause_requested signal."""
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend

    backend = WindowsMediaKeysBackend(None, None)
    args = MagicMock()
    args.button = backend._button_enum.PLAY

    with qtbot.waitSignal(backend.play_pause_requested, timeout=500):
        backend._on_button_pressed(sender=None, args=args)


def test_pause_button_emits_play_pause_signal(mock_winrt_modules, qtbot):
    """MEDIA-04: PAUSE button routes to play_pause_requested signal."""
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend

    backend = WindowsMediaKeysBackend(None, None)
    args = MagicMock()
    args.button = backend._button_enum.PAUSE

    with qtbot.waitSignal(backend.play_pause_requested, timeout=500):
        backend._on_button_pressed(sender=None, args=args)


def test_stop_button_emits_stop_signal(mock_winrt_modules, qtbot):
    """MEDIA-04: STOP button routes to stop_requested signal."""
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend

    backend = WindowsMediaKeysBackend(None, None)
    args = MagicMock()
    args.button = backend._button_enum.STOP

    with qtbot.waitSignal(backend.stop_requested, timeout=500):
        backend._on_button_pressed(sender=None, args=args)


def test_unknown_button_logged_no_crash(mock_winrt_modules, qtbot, caplog):
    """MEDIA-04: unknown buttons are logged at DEBUG and swallowed; no signals emitted."""
    import logging
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend

    backend = WindowsMediaKeysBackend(None, None)
    args = MagicMock()
    args.button = backend._button_enum.CHANNEL_UP

    caplog.set_level(logging.DEBUG, logger="musicstreamer.media_keys.smtc")

    # Must not raise and must not emit signals
    with qtbot.assertNotEmitted(backend.play_pause_requested):
        with qtbot.assertNotEmitted(backend.stop_requested):
            backend._on_button_pressed(None, args)

    # Should have a debug log mentioning the button
    assert any("CHANNEL_UP" in r.message or "not handled" in r.message for r in caplog.records), (
        f"expected DEBUG log about unknown button; got: {[r.message for r in caplog.records]}"
    )


def test_button_handler_swallows_exceptions(mock_winrt_modules, qtbot, caplog):
    """T-43.1-04: exceptions in _on_button_pressed are swallowed + logged at WARNING."""
    import logging
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend

    backend = WindowsMediaKeysBackend(None, None)

    # Make args.button raise on access
    args = MagicMock()
    type(args).button = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))

    caplog.set_level(logging.WARNING, logger="musicstreamer.media_keys.smtc")

    # Must not propagate the exception
    backend._on_button_pressed(None, args)

    assert any(
        "SMTC button handler raised" in r.message for r in caplog.records
    ), f"expected WARNING log; got: {[r.message for r in caplog.records]}"


def test_apply_playback_state_playing(mock_winrt_modules, qtbot):
    """D-10: set_playback_state('playing') maps to MediaPlaybackStatus.PLAYING."""
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend

    backend = WindowsMediaKeysBackend(None, None)
    backend.set_playback_state("playing")

    assert backend._smtc.playback_status == backend._status_enum.PLAYING
    assert backend._state == "playing"


def test_apply_playback_state_paused(mock_winrt_modules, qtbot):
    """D-10: set_playback_state('paused') maps to MediaPlaybackStatus.PAUSED."""
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend

    backend = WindowsMediaKeysBackend(None, None)
    backend.set_playback_state("paused")

    assert backend._smtc.playback_status == backend._status_enum.PAUSED
    assert backend._state == "paused"


def test_apply_playback_state_stopped(mock_winrt_modules, qtbot):
    """D-10: set_playback_state('stopped') maps to MediaPlaybackStatus.STOPPED."""
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend

    backend = WindowsMediaKeysBackend(None, None)
    backend.set_playback_state("stopped")

    assert backend._smtc.playback_status == backend._status_enum.STOPPED
    assert backend._state == "stopped"


def test_apply_playback_state_rejects_invalid(mock_winrt_modules, qtbot):
    """Base class Literal validation raises ValueError for unknown state strings."""
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend

    backend = WindowsMediaKeysBackend(None, None)

    with pytest.raises(ValueError):
        backend.set_playback_state("unknown")


# -------------------------------------------------------------------------
# Plan 04: publish_metadata + thumbnail (MEDIA-05, D-03 revised, D-08)
# -------------------------------------------------------------------------

from musicstreamer.models import Station  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402


def _make_station(station_id=42, name="Test Station"):
    return Station(
        id=station_id,
        name=name,
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
    )


def test_publish_metadata_sets_music_properties(mock_winrt_modules, qtbot, tmp_path, monkeypatch):
    """MEDIA-05 / D-08: music_properties.title + artist populated from station + ICY title."""
    import musicstreamer.paths as paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))

    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend
    backend = WindowsMediaKeysBackend(None, None)
    station = _make_station(7, "Jazz FM")

    backend.publish_metadata(station, "Miles Davis - Kind of Blue", None)

    mp = backend._smtc.display_updater.music_properties
    assert mp.title == "Miles Davis - Kind of Blue"
    assert mp.artist == "Jazz FM"


def test_publish_metadata_music_type(mock_winrt_modules, qtbot, tmp_path, monkeypatch):
    """D-08: DisplayUpdater.type set to MediaPlaybackType.MUSIC."""
    import musicstreamer.paths as paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))

    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend
    backend = WindowsMediaKeysBackend(None, None)
    station = _make_station()

    backend.publish_metadata(station, "title", None)

    assert backend._smtc.display_updater.type == backend._type_enum.MUSIC


def test_publish_metadata_calls_update(mock_winrt_modules, qtbot, tmp_path, monkeypatch):
    """D-08: display_updater.update() called exactly once per publish_metadata."""
    import musicstreamer.paths as paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))

    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend
    backend = WindowsMediaKeysBackend(None, None)
    station = _make_station()

    backend.publish_metadata(station, "title", None)

    du = backend._smtc.display_updater
    assert du.update.called
    assert du.update.call_count == 1


def test_thumbnail_from_in_memory_stream(mock_winrt_modules, qtbot, tmp_path, monkeypatch, qapp):
    """D-03 revised: thumbnail wraps PNG bytes via InMemoryRandomAccessStream + create_from_stream."""
    import musicstreamer.paths as paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))

    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend
    backend = WindowsMediaKeysBackend(None, None)
    station = _make_station(9, "Soma")

    pixmap = QPixmap(10, 10)
    pixmap.fill(Qt.GlobalColor.red)

    backend.publish_metadata(station, "title", pixmap)

    stream_mod = sys.modules["winrt.windows.storage.streams"]
    assert stream_mod.InMemoryRandomAccessStream.called, (
        "InMemoryRandomAccessStream must be instantiated (D-03 revised)"
    )
    assert stream_mod.DataWriter.called, "DataWriter must wrap the stream"
    assert stream_mod.RandomAccessStreamReference.create_from_stream.called, (
        "create_from_stream must receive the populated stream"
    )

    # The thumbnail must be the return_value of create_from_stream
    assert backend._smtc.display_updater.thumbnail is (
        stream_mod.RandomAccessStreamReference.create_from_stream.return_value
    )


def test_thumbnail_failure_clears_to_none(mock_winrt_modules, qtbot, tmp_path, monkeypatch, qapp):
    """D-07: thumbnail-write failures are swallowed; thumbnail set to None."""
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend
    backend = WindowsMediaKeysBackend(None, None)
    station = _make_station()

    # Force write_cover_png to return None (simulates QPixmap save failure)
    monkeypatch.setattr(
        "musicstreamer.media_keys.smtc.write_cover_png",
        lambda *a, **kw: None,
    )

    pixmap = QPixmap(10, 10)
    pixmap.fill(Qt.GlobalColor.red)

    # Must not raise
    backend.publish_metadata(station, "title", pixmap)

    assert backend._smtc.display_updater.thumbnail is None

    # Second scenario: write_cover_png returns a bogus path, open() raises
    backend._smtc.display_updater.thumbnail = "SENTINEL"  # prove it gets cleared
    monkeypatch.setattr(
        "musicstreamer.media_keys.smtc.write_cover_png",
        lambda *a, **kw: str(tmp_path / "does-not-exist.png"),
    )
    backend.publish_metadata(station, "title", pixmap)
    assert backend._smtc.display_updater.thumbnail is None


def test_publish_metadata_none_station_clears(mock_winrt_modules, qtbot, tmp_path, monkeypatch):
    """MEDIA-05: publish_metadata(None, '', None) clears music_properties + thumbnail without raising."""
    import musicstreamer.paths as paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))

    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend
    backend = WindowsMediaKeysBackend(None, None)
    station = _make_station(3, "Test")

    # First publish real metadata
    backend.publish_metadata(station, "some title", None)

    # Then clear
    backend.publish_metadata(None, "", None)

    mp = backend._smtc.display_updater.music_properties
    assert mp.title == ""
    assert mp.artist == ""
    assert backend._smtc.display_updater.thumbnail is None
    assert backend._station is None
    assert backend._title == ""
    # update() called twice total
    assert backend._smtc.display_updater.update.call_count == 2


# -------------------------------------------------------------------------
# Plan 05: shutdown() + idempotency + factory fallback end-to-end
# -------------------------------------------------------------------------

def test_shutdown_detaches_handler_and_closes(mock_winrt_modules, qtbot):
    """D-09: shutdown detaches button_pressed handler, disables SMTC, closes MediaPlayer."""
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend
    backend = WindowsMediaKeysBackend(None, None)

    token = backend._bp_token
    smtc = backend._smtc
    mp = backend._media_player

    backend.shutdown()

    smtc.remove_button_pressed.assert_called_once_with(token)
    assert smtc.is_enabled is False
    mp.close.assert_called_once()
    assert backend._shutdown_complete is True


def test_shutdown_idempotent(mock_winrt_modules, qtbot):
    """D-09: shutdown() called twice does not raise; second call is a no-op."""
    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend
    backend = WindowsMediaKeysBackend(None, None)

    backend.shutdown()
    backend.shutdown()  # must not raise

    assert backend._smtc.remove_button_pressed.call_count == 1
    assert backend._media_player.close.call_count == 1


def test_shutdown_continues_on_partial_failure(mock_winrt_modules, qtbot, caplog):
    """A failure in step 1 (remove_button_pressed) does not skip steps 2 and 3."""
    import logging
    caplog.set_level(logging.DEBUG, logger="musicstreamer.media_keys.smtc")

    from musicstreamer.media_keys.smtc import WindowsMediaKeysBackend
    backend = WindowsMediaKeysBackend(None, None)

    backend._smtc.remove_button_pressed.side_effect = RuntimeError("simulated detach error")

    backend.shutdown()  # must not raise

    assert backend._smtc.is_enabled is False, "step 2 should run despite step 1 failure"
    assert backend._media_player.close.called, "step 3 should run despite step 1 failure"
    assert backend._shutdown_complete is True

    messages = [r.getMessage() for r in caplog.records]
    assert any("remove_button_pressed" in m for m in messages), (
        f"expected DEBUG log about remove_button_pressed failure, got: {messages}"
    )


def test_end_to_end_factory_fallback_on_win32_without_winrt(monkeypatch, caplog):
    """D-07 closed-loop: sys.platform='win32' + no winrt -> factory returns NoOp + logs warning."""
    import logging
    caplog.set_level(logging.WARNING, logger="musicstreamer.media_keys")

    monkeypatch.setattr(sys, "platform", "win32")

    # Force clean re-import so the factory's lazy `from .smtc import ...` runs fresh.
    for mod in list(sys.modules):
        if mod.startswith("musicstreamer.media_keys"):
            del sys.modules[mod]

    from musicstreamer.media_keys import create, NoOpMediaKeysBackend
    backend = create(None, None)

    assert isinstance(backend, NoOpMediaKeysBackend), (
        f"expected NoOp fallback on Linux, got {type(backend).__name__}"
    )

    # T-43.1-03: log message should be the fixed install-hint, not stack trace
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert warnings, "expected WARNING-level log from factory fallback"
    combined = " ".join(r.getMessage() for r in warnings).lower()
    assert "windows" in combined or "winrt" in combined or "smtc" in combined, (
        f"warning should hint at Windows/winrt/SMTC: {combined!r}"
    )
