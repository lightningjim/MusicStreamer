"""Tests for musicstreamer.media_keys.smtc (Phase 43.1).

Linux-only unit tests. All winrt interactions are mocked via sys.modules
injection. Real Windows integration is UAT on the Win11 VM (Plan 06).
"""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path


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
