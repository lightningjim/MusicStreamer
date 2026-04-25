"""Tests for musicstreamer.single_instance (Phase 44, PKG-04).

Uses pytest-qt qtbot fixture (offscreen Qt via conftest.py).
Monkeypatches SERVER_NAME so parallel tests do not collide on the named pipe
(Windows) / unix socket (Linux).

These tests are RED until Plan 02 lands musicstreamer/single_instance.py with
the QLocalServer-backed acquire_or_forward() factory + activate_requested signal.
Per-test unique SERVER_NAME isolation is mandatory.
"""
from __future__ import annotations

import pytest


def test_first_instance_acquires_server(qtbot, monkeypatch):
    """First call returns a server bound to the configured SERVER_NAME."""
    # Lazy import: musicstreamer.single_instance lands in Plan 02 (Wave 1).
    # Keeping the import inside the test keeps collection green so Plan 01's
    # --collect-only verification can see this scaffold; the test still RED-fails
    # at execution until Plan 02 is in place.
    from musicstreamer import single_instance
    monkeypatch.setattr(single_instance, "SERVER_NAME", "test-mstream-single-inst-a")
    server = single_instance.acquire_or_forward()
    assert server is not None
    server.close()


def test_second_instance_forwards_and_first_sees_activate(qtbot, monkeypatch):
    """Second acquire returns None and the first instance's activate_requested fires."""
    from musicstreamer import single_instance
    monkeypatch.setattr(single_instance, "SERVER_NAME", "test-mstream-single-inst-b")

    first = single_instance.acquire_or_forward()
    assert first is not None

    with qtbot.waitSignal(first.activate_requested, timeout=1000):
        second = single_instance.acquire_or_forward()
        assert second is None

    first.close()
