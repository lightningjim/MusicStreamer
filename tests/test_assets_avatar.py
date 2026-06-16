"""Unit tests for musicstreamer.assets.write_channel_avatar (Phase 89 D-12).

Uses paths._root_override = str(tmp_path) for filesystem isolation.
"""
import os
import pytest
import musicstreamer.paths as paths
import musicstreamer.assets as assets


@pytest.fixture(autouse=True)
def isolate_paths(tmp_path):
    """Redirect every paths accessor to tmp_path; restore after test."""
    paths._root_override = str(tmp_path)
    yield
    paths._root_override = None


def test_write_channel_avatar_creates_file_and_returns_relative_path(tmp_path):
    """D-12: write returns 'assets/channel-avatars/<id>.png' relative to data_dir."""
    rel = assets.write_channel_avatar(12, b"<pngbytes>")
    assert rel == os.path.join("assets", "channel-avatars", "12.png")
    # File must exist at the absolute location
    abs_path = os.path.join(str(tmp_path), rel)
    assert os.path.isfile(abs_path)
    assert open(abs_path, "rb").read() == b"<pngbytes>"


def test_write_channel_avatar_overwrite_atomic_no_tmp_remains(tmp_path):
    """D-12: second write atomically overwrites; no .tmp file remains in the dir."""
    assets.write_channel_avatar(12, b"<firstbytes>")
    assets.write_channel_avatar(12, b"<newbytes>")
    avatar_dir = paths.channel_avatars_dir()
    files = os.listdir(avatar_dir)
    # Only the final .png should be present — no .png.tmp left behind
    assert files == ["12.png"], f"unexpected files in dir: {files}"
    final_path = os.path.join(avatar_dir, "12.png")
    assert open(final_path, "rb").read() == b"<newbytes>"


def test_write_channel_avatar_failure_cleans_up_tmp(tmp_path, monkeypatch):
    """D-12 / T-89-01: on simulated write failure, no .tmp file is left behind."""
    import tempfile as _tempfile

    real_mkstemp = _tempfile.mkstemp

    def failing_mkstemp(**kwargs):
        """Create the temp file, then raise to simulate a write error."""
        fd, tmp = real_mkstemp(**kwargs)
        # Close the fd so os.write mock can trigger the failure path
        # We'll patch os.write to raise instead
        return fd, tmp

    original_os_write = os.write

    def raising_os_write(fd, data):
        original_os_write(fd, data[:0])  # write nothing
        raise OSError("simulated disk full")

    monkeypatch.setattr(os, "write", raising_os_write)

    with pytest.raises(OSError, match="simulated disk full"):
        assets.write_channel_avatar(12, b"<pngbytes>")

    # No .tmp file must remain
    avatar_dir = paths.channel_avatars_dir()
    if os.path.isdir(avatar_dir):
        leftover = [f for f in os.listdir(avatar_dir) if f.endswith(".png.tmp")]
        assert leftover == [], f".tmp files left behind after failure: {leftover}"
