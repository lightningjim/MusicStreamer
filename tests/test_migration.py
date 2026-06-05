"""Tests for musicstreamer.migration — first-launch non-destructive migration."""
import os

import pytest

from musicstreamer import migration, paths
import musicstreamer.flatpak_first_launch as ffl


@pytest.fixture(autouse=True)
def _reset_root_override():
    saved = paths._root_override
    saved_legacy = migration._LEGACY_LINUX
    saved_flatpak_info = ffl._FLATPAK_INFO
    paths._root_override = None
    yield
    paths._root_override = saved
    migration._LEGACY_LINUX = saved_legacy
    ffl._FLATPAK_INFO = saved_flatpak_info


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


def test_migration_sandboxed_skips_copy(tmp_path):
    """T-86.1-01: When sandboxed, run_migration() creates dest + marker but copies ZERO files.

    Sandboxed src != dest divergent-path scenario: the narrow :ro host mount makes
    _LEGACY_LINUX point to host data (cookies.txt, musicstreamer.sqlite3) while
    paths.data_dir() resolves to the sandbox path.  Without the sandbox guard the
    existing _copy_tree_nondestructive branch would silently ingest 0600 secrets.

    This test asserts:
      - marker file exists after run_migration()
      - dest dir exists (buffer_log ordering invariant — __main__.py:199)
      - dest contains NO cookies.txt (secret not copied)
      - dest contains NO musicstreamer.sqlite3 (db not copied)
    """
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    # Place host secrets + db in src (the :ro mount path)
    (src / "cookies.txt").write_bytes(b"SUPER_SECRET")
    (src / "musicstreamer.sqlite3").write_bytes(b"DBDATA")

    # Simulate being inside the Flatpak sandbox: monkeypatch _FLATPAK_INFO to an
    # existing file so is_sandboxed() returns True.
    info_file = tmp_path / "flatpak-info"
    info_file.write_text("[Application]\nname=io.github.kcreasey.MusicStreamer\n")
    ffl._FLATPAK_INFO = str(info_file)

    paths._root_override = str(dst)
    migration._LEGACY_LINUX = str(src)

    migration.run_migration()

    # Marker must exist (buffer_log ordering invariant)
    assert os.path.exists(paths.migration_marker()), "migration marker must be written when sandboxed"
    # Dest dir must exist (buffer_log ordering invariant)
    assert os.path.isdir(str(dst)), "dest dir must exist when sandboxed"
    # Secrets must NOT have been copied
    assert not (dst / "cookies.txt").exists(), "cookies.txt must NOT be copied into sandbox"
    assert not (dst / "musicstreamer.sqlite3").exists(), "musicstreamer.sqlite3 must NOT be copied into sandbox"
