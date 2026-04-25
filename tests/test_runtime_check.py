"""Tests for musicstreamer.runtime_check (Phase 44, RUNTIME-01).

Covers the NodeRuntime detection contract:
  - check_node() returns NodeRuntime(available=True, path=...) when _which_node
    locates an executable.
  - check_node() returns NodeRuntime(available=False, path=None) when _which_node
    returns None.
  - On win32, _which_node() prefers node.exe explicitly to dodge CPython issue
    #109590 (extensionless shim returned before node.exe).

These tests are RED until Plan 02 lands musicstreamer/runtime_check.py.
"""
from __future__ import annotations

import sys
from unittest.mock import patch


def test_check_node_available(monkeypatch):
    # Lazy import: musicstreamer.runtime_check lands in Plan 02 (Wave 1).
    # Keeps collection green; tests still RED-fail at execution until Plan 02.
    from musicstreamer import runtime_check
    monkeypatch.setattr(runtime_check, "_which_node", lambda: "/usr/bin/node")
    nr = runtime_check.check_node()
    assert nr.available is True
    assert nr.path == "/usr/bin/node"


def test_check_node_absent(monkeypatch):
    from musicstreamer import runtime_check
    monkeypatch.setattr(runtime_check, "_which_node", lambda: None)
    nr = runtime_check.check_node()
    assert nr.available is False
    assert nr.path is None


def test_which_node_prefers_exe_on_windows(monkeypatch):
    """CPython issue #109590 guard — Windows must probe node.exe first."""
    from musicstreamer import runtime_check
    monkeypatch.setattr(sys, "platform", "win32")
    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda name: (
            r"C:\Program Files\nodejs\node.exe" if name == "node.exe" else None
        )
        assert (
            runtime_check._which_node()
            == r"C:\Program Files\nodejs\node.exe"
        )
        mock_which.assert_called_with("node.exe")
