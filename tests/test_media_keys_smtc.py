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
