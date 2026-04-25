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

import os
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


def test_which_node_falls_back_to_fnm_default_alias(monkeypatch, tmp_path):
    """GUI launches (.desktop) miss fnm shims; fall back to ~/.local/share/fnm/aliases/default/bin/node."""
    from musicstreamer import runtime_check

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("shutil.which", lambda _name: None)

    fake_home = tmp_path / "home"
    node_bin = fake_home / ".local" / "share" / "fnm" / "aliases" / "default" / "bin" / "node"
    node_bin.parent.mkdir(parents=True)
    node_bin.write_text("#!/bin/sh\n")
    node_bin.chmod(0o755)

    monkeypatch.setattr(os.path, "expanduser", lambda p: str(fake_home) if p == "~" else p)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    assert runtime_check._which_node() == str(node_bin)


def test_which_node_falls_back_to_nvm_highest_version(monkeypatch, tmp_path):
    from musicstreamer import runtime_check

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("shutil.which", lambda _name: None)

    fake_home = tmp_path / "home"
    for version in ("v18.20.0", "v22.5.1", "v20.10.0"):
        bin_path = fake_home / ".nvm" / "versions" / "node" / version / "bin" / "node"
        bin_path.parent.mkdir(parents=True)
        bin_path.write_text("#!/bin/sh\n")
        bin_path.chmod(0o755)

    monkeypatch.setattr(os.path, "expanduser", lambda p: str(fake_home) if p == "~" else p)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    result = runtime_check._which_node()
    assert result is not None
    assert result.endswith("v22.5.1/bin/node")


def test_which_node_returns_none_when_no_version_manager(monkeypatch, tmp_path):
    from musicstreamer import runtime_check

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("shutil.which", lambda _name: None)
    monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path) if p == "~" else p)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    assert runtime_check._which_node() is None
