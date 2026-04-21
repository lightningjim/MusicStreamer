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
