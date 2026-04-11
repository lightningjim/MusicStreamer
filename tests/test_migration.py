"""Tests for musicstreamer.migration — first-launch non-destructive migration."""
import os

import pytest

from musicstreamer import migration, paths


@pytest.fixture(autouse=True)
def _reset_root_override():
    saved = paths._root_override
    saved_legacy = migration._LEGACY_LINUX
    paths._root_override = None
    yield
    paths._root_override = saved
    migration._LEGACY_LINUX = saved_legacy


def test_migration_same_path_writes_marker_and_returns(tmp_path):
    paths._root_override = str(tmp_path)
    migration._LEGACY_LINUX = str(tmp_path)
    migration.run_migration()
    assert os.path.exists(paths.migration_marker())


def test_migration_different_path_copies_nondestructive(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "musicstreamer.sqlite3").write_bytes(b"DB")
    paths._root_override = str(dst)
    migration._LEGACY_LINUX = str(src)

    migration.run_migration()

    # dest copied
    assert (dst / "musicstreamer.sqlite3").read_bytes() == b"DB"
    # marker present
    assert os.path.exists(paths.migration_marker())
    # src not deleted (non-destructive)
    assert (src / "musicstreamer.sqlite3").exists()


def test_migration_idempotent_via_marker(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "musicstreamer.sqlite3").write_bytes(b"DB")
    paths._root_override = str(dst)
    migration._LEGACY_LINUX = str(src)

    write_calls = {"n": 0}
    real_write = migration._write_marker

    def spy(p):
        write_calls["n"] += 1
        real_write(p)

    migration._write_marker = spy
    try:
        migration.run_migration()
        migration.run_migration()
    finally:
        migration._write_marker = real_write

    assert write_calls["n"] == 1


def test_migration_preserves_existing_dest_files(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "cookies.txt").write_bytes(b"OLD")
    (dst / "cookies.txt").write_bytes(b"KEEP")
    paths._root_override = str(dst)
    migration._LEGACY_LINUX = str(src)

    migration.run_migration()

    assert (dst / "cookies.txt").read_bytes() == b"KEEP"
    assert os.path.exists(paths.migration_marker())


def test_migration_copy_preserves_mode_bits(tmp_path):
    """Security: cookies.txt and twitch-token.txt must keep 0600 perms across copy."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    secret = src / "twitch-token.txt"
    secret.write_text("token")
    os.chmod(secret, 0o600)
    paths._root_override = str(dst)
    migration._LEGACY_LINUX = str(src)

    migration.run_migration()

    copied = dst / "twitch-token.txt"
    assert copied.exists()
    assert (os.stat(copied).st_mode & 0o777) == 0o600
