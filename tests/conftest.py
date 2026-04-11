"""pytest-qt session configuration.

Sets the Qt platform plugin to ``offscreen`` so tests run headless on CI
and on headless dev boxes. Must happen BEFORE any PySide6 import.

Also provides an autouse fixture that stubs
``musicstreamer.player._ensure_bus_bridge`` so tests which instantiate
``Player`` never spin up the real GLib.MainLoop daemon thread. The bus
bridge is exercised by dedicated tests for ``gst_bus_bridge.py`` only.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _stub_bus_bridge(monkeypatch):
    """Replace _ensure_bus_bridge with a MagicMock so Player() construction
    never starts the real GLib.MainLoop daemon thread in unit tests."""
    try:
        import musicstreamer.player as _player_mod
    except ImportError:
        return
    monkeypatch.setattr(
        _player_mod, "_ensure_bus_bridge", lambda: MagicMock()
    )
