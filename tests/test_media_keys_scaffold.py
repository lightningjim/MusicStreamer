"""Tests for the musicstreamer.media_keys scaffold (Phase 41, Plan 01).

Tests 1-4 cover Task 1 (base.py + __init__.py stubs).
Tests 5-9 cover Task 2 (create() platform factory + smtc.py stub).

Uses pytest-qt qtbot fixture (offscreen Qt via conftest.py QT_QPA_PLATFORM=offscreen).
No live D-Bus session is required.
"""
from __future__ import annotations

import sys

import pytest


# ---------------------------------------------------------------------------
# Task 1 tests — abstract base + NoOp
# ---------------------------------------------------------------------------

def test_noop_instantiates_and_methods_return_none(qtbot):
    """Test 1: NoOpMediaKeysBackend() instantiates; all three abstract methods return None."""
    from musicstreamer.media_keys import NoOpMediaKeysBackend
    backend = NoOpMediaKeysBackend()
    # QObject, not QWidget — do not call qtbot.addWidget
    assert backend.publish_metadata(None, "title", None) is None
    assert backend.set_playback_state("playing") is None
    assert backend.shutdown() is None


def test_signal_observable_via_qtbot(qtbot):
    """Test 2: play_pause_requested signal is observable via qtbot.waitSignal."""
    from musicstreamer.media_keys import NoOpMediaKeysBackend
    backend = NoOpMediaKeysBackend()
    # QObject, not QWidget — do not call qtbot.addWidget
    with qtbot.waitSignal(backend.play_pause_requested, timeout=1000):
        backend.play_pause_requested.emit()


def test_invalid_playback_state_raises_value_error(qtbot):
    """Test 3: set_playback_state("invalid") raises ValueError."""
    from musicstreamer.media_keys import NoOpMediaKeysBackend
    backend = NoOpMediaKeysBackend()
    # QObject, not QWidget — do not call qtbot.addWidget
    with pytest.raises(ValueError):
        backend.set_playback_state("invalid")


def test_media_keys_backend_importable(qtbot):
    """Test 4: MediaKeysBackend (true abstract) is importable without raising."""
    from musicstreamer.media_keys import MediaKeysBackend
    # Importing and accessing the class itself must not raise.
    assert issubclass(MediaKeysBackend, object)


# ---------------------------------------------------------------------------
# Task 2 tests — create() factory + smtc.py stub
# ---------------------------------------------------------------------------

def test_create_returns_media_keys_backend_on_linux(qtbot):
    """Test 5: On Linux, create(None, None) returns a MediaKeysBackend instance."""
    from musicstreamer.media_keys import create, MediaKeysBackend
    backend = create(None, None)
    # QObject, not QWidget — do not call qtbot.addWidget
    assert isinstance(backend, MediaKeysBackend)


def test_create_returns_noop_on_win32(monkeypatch, qtbot):
    """Test 6: When sys.platform is 'win32', create() returns NoOpMediaKeysBackend."""
    monkeypatch.setattr(sys, "platform", "win32")
    from musicstreamer.media_keys import create, NoOpMediaKeysBackend
    backend = create(None, None)
    # QObject, not QWidget — do not call qtbot.addWidget
    assert isinstance(backend, NoOpMediaKeysBackend)


def test_create_returns_noop_on_freebsd(monkeypatch, qtbot):
    """Test 7: When sys.platform is 'freebsd', create() returns NoOpMediaKeysBackend."""
    monkeypatch.setattr(sys, "platform", "freebsd")
    from musicstreamer.media_keys import create, NoOpMediaKeysBackend
    backend = create(None, None)
    # QObject, not QWidget — do not call qtbot.addWidget
    assert isinstance(backend, NoOpMediaKeysBackend)


def test_smtc_create_windows_backend_raises_not_implemented():
    """Test 8: smtc.create_windows_backend raises NotImplementedError with '43.1'."""
    from musicstreamer.media_keys.smtc import create_windows_backend
    with pytest.raises(NotImplementedError) as exc_info:
        create_windows_backend(None, None)
    assert "43.1" in str(exc_info.value)


def test_no_winrt_in_sys_modules():
    """Test 9: Importing musicstreamer.media_keys does not pull in winrt."""
    import musicstreamer.media_keys  # noqa: F401 — ensure it's imported
    assert all(not m.startswith("winrt") for m in sys.modules)


# ---------------------------------------------------------------------------
# T-41-09: cover_path_for_station rejects non-int station_id (path traversal guard)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_id", [
    "../evil",
    "42",
    3.14,
    None,
])
def test_cover_path_for_station_rejects_non_int(tmp_path, monkeypatch, bad_id):
    """T-41-09: cover_path_for_station raises TypeError for any non-int station_id.

    station.id is an int SQLite PK — the path-traversal guard ensures callers
    cannot inject path components via a string like '../evil'.
    Does not import PySide6.QtDBus.
    """
    import musicstreamer.paths as paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys._art_cache import cover_path_for_station

    with pytest.raises(TypeError):
        cover_path_for_station(bad_id)
