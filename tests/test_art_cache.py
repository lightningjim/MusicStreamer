"""Tests for musicstreamer.media_keys._art_cache rename + migration (Phase 43.1 D-04)."""
from __future__ import annotations

import os
import pytest

import musicstreamer.paths as paths


def _reset_migration_sentinel():
    """Reset the module-level migration flag between tests (it's one-shot per process)."""
    import musicstreamer.media_keys._art_cache as ac
    ac._migration_attempted = False


def test_cover_path_uses_media_art(tmp_path, monkeypatch):
    """cover_path_for_station returns a path under media-art/ (not mpris-art/)."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    _reset_migration_sentinel()
    from musicstreamer.media_keys._art_cache import cover_path_for_station

    result = cover_path_for_station(42)
    assert result.endswith(os.path.join("media-art", "42.png"))
    assert "mpris-art" not in result
    assert os.path.isdir(os.path.dirname(result))


def test_mpris_art_migrates_to_media_art(tmp_path, monkeypatch):
    """If legacy mpris-art/ exists and media-art/ does not, first access renames it."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    _reset_migration_sentinel()

    legacy = os.path.join(paths.user_cache_dir(), "mpris-art")
    os.makedirs(legacy, exist_ok=True)
    # Seed a marker file so we can confirm the rename preserved contents.
    marker = os.path.join(legacy, "99.png")
    with open(marker, "wb") as f:
        f.write(b"legacy-marker")

    from musicstreamer.media_keys._art_cache import cover_path_for_station
    _ = cover_path_for_station(42)  # triggers migration

    new_dir = os.path.join(paths.user_cache_dir(), "media-art")
    assert os.path.isdir(new_dir)
    assert not os.path.isdir(legacy)
    assert os.path.isfile(os.path.join(new_dir, "99.png"))


def test_migration_skipped_if_new_dir_exists(tmp_path, monkeypatch):
    """If media-art/ already exists, legacy mpris-art/ is left untouched."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    _reset_migration_sentinel()

    legacy = os.path.join(paths.user_cache_dir(), "mpris-art")
    new = os.path.join(paths.user_cache_dir(), "media-art")
    os.makedirs(legacy, exist_ok=True)
    os.makedirs(new, exist_ok=True)

    from musicstreamer.media_keys._art_cache import cover_path_for_station
    _ = cover_path_for_station(42)

    assert os.path.isdir(legacy), "legacy dir must be preserved when new dir already exists"
    assert os.path.isdir(new)


def test_migration_swallows_errors(tmp_path, monkeypatch):
    """os.rename failure must not propagate — PNGs regenerate on next publish."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    _reset_migration_sentinel()

    import musicstreamer.media_keys._art_cache as ac

    def boom(*args, **kwargs):
        raise PermissionError("simulated rename failure")

    # Set up a legacy dir so the migration code path attempts os.rename
    os.makedirs(os.path.join(paths.user_cache_dir(), "mpris-art"), exist_ok=True)
    monkeypatch.setattr(ac.os, "rename", boom)

    # Must NOT raise
    result = ac.cover_path_for_station(42)
    assert result.endswith(os.path.join("media-art", "42.png"))


@pytest.mark.parametrize("bad_id", ["../evil", "42", 3.14, None])
def test_type_error_guard_preserved(tmp_path, monkeypatch, bad_id):
    """T-41-09: non-int station_id still rejected (guard carried over from Phase 41)."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    _reset_migration_sentinel()
    from musicstreamer.media_keys._art_cache import cover_path_for_station

    with pytest.raises(TypeError):
        cover_path_for_station(bad_id)
