"""Tests for musicstreamer.paths — pure path resolution helper."""
import os

import platformdirs
import pytest

from musicstreamer import paths


@pytest.fixture(autouse=True)
def _reset_root_override():
    """Ensure each test starts with a clean override and restores after."""
    saved = paths._root_override
    paths._root_override = None
    yield
    paths._root_override = saved


def test_data_dir_uses_platformdirs_default():
    paths._root_override = None
    assert paths.data_dir() == platformdirs.user_data_dir("musicstreamer")


def test_root_override_redirects_all_accessors(tmp_path):
    paths._root_override = str(tmp_path)
    root = str(tmp_path)
    assert paths.data_dir() == root
    assert paths.db_path() == os.path.join(root, "musicstreamer.sqlite3")
    assert paths.assets_dir() == os.path.join(root, "assets")
    assert paths.cookies_path() == os.path.join(root, "cookies.txt")
    assert paths.twitch_token_path() == os.path.join(root, "twitch-token.txt")
    assert paths.accent_css_path() == os.path.join(root, "accent.css")
    assert paths.migration_marker() == os.path.join(root, ".platformdirs-migrated")


def test_paths_do_no_io_on_import(tmp_path):
    """Re-importing the module must not create any directories under the override root."""
    import importlib

    paths._root_override = str(tmp_path)
    before = set(os.listdir(tmp_path))
    importlib.reload(paths)
    # reload resets _root_override to None — set again and probe
    paths._root_override = str(tmp_path)
    # Calling accessors must also be pure (no mkdir).
    paths.data_dir()
    paths.db_path()
    paths.assets_dir()
    paths.cookies_path()
    paths.twitch_token_path()
    paths.accent_css_path()
    paths.migration_marker()
    after = set(os.listdir(tmp_path))
    assert before == after


def test_db_path_filename(tmp_path):
    paths._root_override = str(tmp_path)
    assert os.path.basename(paths.db_path()) == "musicstreamer.sqlite3"


def test_eq_profiles_dir_honors_root_override(monkeypatch, tmp_path):
    """Phase 47.2 D-12: eq-profiles dir resolves under the override root."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    assert paths.eq_profiles_dir() == os.path.join(str(tmp_path), "eq-profiles")


def test_eq_profiles_dir_does_not_create_directory(monkeypatch, tmp_path):
    """Purity contract: helper returns a string; it does NOT mkdir."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    result = paths.eq_profiles_dir()
    assert os.path.exists(result) is False
