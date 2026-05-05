"""Tests for musicstreamer.desktop_install — Phase 61 / D-09 / BUG-08.

Linux-CI safe — uses tmp_path to redirect both the install marker
(paths._root_override) and the XDG install destinations
(XDG_DATA_HOME env var). No display server or D-Bus required.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from musicstreamer import desktop_install, paths


@pytest.fixture(autouse=True)
def _redirect_paths(tmp_path, monkeypatch):
    """Redirect XDG_DATA_HOME + paths._root_override under tmp_path."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg_data"))
    saved = paths._root_override
    paths._root_override = str(tmp_path / "data")
    try:
        yield
    finally:
        paths._root_override = saved


@pytest.fixture
def fake_bundled(tmp_path, monkeypatch):
    """Fake bundled .desktop + icon under tmp_path so tests don't depend
    on the repo packaging/ being present at test time."""
    bundled_desktop = tmp_path / "bundled.desktop"
    bundled_desktop.write_text(
        "[Desktop Entry]\nName=MusicStreamer\nType=Application\n"
    )
    bundled_icon = tmp_path / "bundled.png"
    bundled_icon.write_bytes(b"\x89PNG\r\n\x1a\nFAKE")
    monkeypatch.setattr(desktop_install, "_BUNDLED_DESKTOP", bundled_desktop)
    monkeypatch.setattr(desktop_install, "_BUNDLED_ICON", bundled_icon)
    return bundled_desktop, bundled_icon


def test_first_launch_installs_files(tmp_path, fake_bundled):
    """Phase 61 / 61-03-01: ensure_installed() writes .desktop + icon + marker."""
    # Pre-condition: ensure platform is Linux (no early-return).
    # This test is run on Linux CI; explicit assertion documents the gate.
    assert sys.platform.startswith("linux"), "Test requires Linux platform"

    desktop_install.ensure_installed()

    xdg = tmp_path / "xdg_data"
    expected_desktop = (
        xdg / "applications" / "org.lightningjim.MusicStreamer.desktop"
    )
    expected_icon = (
        xdg / "icons" / "hicolor" / "256x256" / "apps"
        / "org.lightningjim.MusicStreamer.png"
    )
    marker = Path(paths.data_dir()) / ".desktop-installed-v1"

    assert expected_desktop.exists(), f".desktop not installed: {expected_desktop}"
    assert expected_icon.exists(), f"icon not installed: {expected_icon}"
    assert marker.exists(), f"marker not written: {marker}"


def test_idempotent_via_marker(tmp_path, fake_bundled):
    """Phase 61 / 61-03-02: marker prevents re-install even if files were deleted."""
    if not sys.platform.startswith("linux"):
        pytest.skip("desktop_install is Linux-only")

    desktop_install.ensure_installed()
    xdg = tmp_path / "xdg_data"
    desktop_path = (
        xdg / "applications" / "org.lightningjim.MusicStreamer.desktop"
    )
    assert desktop_path.exists()

    # Simulate user manually deleting the installed file.
    desktop_path.unlink()
    assert not desktop_path.exists()

    # Second call: marker says "done", so this is a no-op.
    desktop_install.ensure_installed()

    # The .desktop is NOT recreated because the marker short-circuits.
    assert not desktop_path.exists(), (
        "Idempotency violated: marker present but .desktop was re-installed"
    )


def test_no_op_off_linux(monkeypatch, fake_bundled):
    """Phase 61 / 61-03-03: ensure_installed() is a no-op on non-Linux."""
    monkeypatch.setattr(desktop_install.sys, "platform", "win32")

    desktop_install.ensure_installed()

    # No marker, no install — fully no-op.
    marker = Path(paths.data_dir()) / ".desktop-installed-v1"
    assert not marker.exists(), "Marker written despite non-Linux platform"


def test_existing_files_preserved(tmp_path, fake_bundled):
    """Phase 61 / 61-03-04: D-11 additive — does NOT overwrite user-modified files."""
    if not sys.platform.startswith("linux"):
        pytest.skip("desktop_install is Linux-only")

    xdg = tmp_path / "xdg_data"
    apps = xdg / "applications"
    apps.mkdir(parents=True)
    pre_existing = apps / "org.lightningjim.MusicStreamer.desktop"
    pre_existing.write_text("USER MODIFIED CONTENT")

    desktop_install.ensure_installed()

    # The user's file is preserved verbatim.
    assert pre_existing.read_text() == "USER MODIFIED CONTENT", (
        "ensure_installed() clobbered an existing user-modified .desktop"
    )


def test_cache_hooks_called_best_effort(monkeypatch, fake_bundled):
    """Phase 61 / 61-03-05: D-13 best-effort hooks are invoked."""
    if not sys.platform.startswith("linux"):
        pytest.skip("desktop_install is Linux-only")

    calls = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)

        class _R:
            returncode = 0
            stderr = ""

        return _R()

    monkeypatch.setattr(desktop_install.subprocess_utils, "_run", fake_run)
    desktop_install.ensure_installed()

    cmd0_names = [c[0] for c in calls]
    assert "update-desktop-database" in cmd0_names, (
        f"update-desktop-database not invoked. Calls: {calls}"
    )
    assert "gtk-update-icon-cache" in cmd0_names, (
        f"gtk-update-icon-cache not invoked. Calls: {calls}"
    )


def test_missing_cache_tool_does_not_raise(monkeypatch, fake_bundled):
    """Phase 61 / 61-03-06: missing cache tool is caught; install still succeeds."""
    if not sys.platform.startswith("linux"):
        pytest.skip("desktop_install is Linux-only")

    def fake_run(cmd, *args, **kwargs):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(desktop_install.subprocess_utils, "_run", fake_run)

    # Must not raise.
    desktop_install.ensure_installed()

    # The install itself succeeded — only the cache refresh failed.
    # Marker IS still written because _do_install() completed cleanly
    # (the cache hooks are inside _best_effort which catches the error).
    marker = Path(paths.data_dir()) / ".desktop-installed-v1"
    assert marker.exists(), (
        "Marker missing despite successful install (cache hook failure "
        "should not prevent marker write)"
    )
