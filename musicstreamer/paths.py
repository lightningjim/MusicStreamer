"""Single source of truth for MusicStreamer data paths.

All data-file locations route through this module so that:

1. Tests can monkeypatch ``_root_override`` to redirect every accessor at
   a temporary directory without touching ``$HOME``.
2. The on-disk root is rooted at ``platformdirs.user_data_dir("musicstreamer")``,
   which collapses to ``~/.local/share/musicstreamer`` on Linux but resolves
   to the OS-appropriate location on Windows / macOS for v2.0.

This module is **pure**: importing it (or calling any accessor) does NOT
create directories or otherwise touch the filesystem. Directory creation
is the responsibility of ``musicstreamer.assets.ensure_dirs`` and
``musicstreamer.migration.run_migration``.
"""
from __future__ import annotations

import os

import platformdirs

# Test hook: when set to a string, every accessor below resolves under this
# directory instead of the platformdirs default. Tests assign this directly
# (no setter function — keep it simple).
_root_override: str | None = None


def _root() -> str:
    if _root_override is not None:
        return _root_override
    return platformdirs.user_data_dir("musicstreamer")


def data_dir() -> str:
    return _root()


def db_path() -> str:
    return os.path.join(_root(), "musicstreamer.sqlite3")


def assets_dir() -> str:
    return os.path.join(_root(), "assets")


def cookies_path() -> str:
    return os.path.join(_root(), "cookies.txt")


def twitch_token_path() -> str:
    return os.path.join(_root(), "twitch-token.txt")


def gbs_cookies_path() -> str:
    """Phase 60 D-04 (ladder #3 LOCKED): GBS.FM session cookies file.

    Mirrors the YouTube cookies path shape. Pure — does not create the
    directory. Caller writes with 0o600 perms (Phase 999.7 convention).
    """
    return os.path.join(_root(), "gbs-cookies.txt")


def oauth_log_path() -> str:
    """Phase 999.3 D-10: path to the persistent OAuth diagnostic log."""
    return os.path.join(_root(), "oauth.log")


def accent_css_path() -> str:
    return os.path.join(_root(), "accent.css")


def migration_marker() -> str:
    return os.path.join(_root(), ".platformdirs-migrated")


def user_cache_dir() -> str:
    """Return the per-user cache directory for MusicStreamer.

    When ``_root_override`` is set (test mode), returns
    ``{_root_override}/cache`` so tests don't pollute the real cache.
    Otherwise delegates to ``platformdirs.user_cache_dir("musicstreamer")``
    which resolves to ``~/.cache/musicstreamer`` on Linux.
    """
    if _root_override is not None:
        return os.path.join(_root_override, "cache")
    return platformdirs.user_cache_dir("musicstreamer")


def eq_profiles_dir() -> str:
    """Return the directory holding imported AutoEQ profiles (Phase 47.2 D-12).

    Pure — does NOT create the directory. Callers use
    ``os.makedirs(paths.eq_profiles_dir(), exist_ok=True)`` before writing.
    """
    return os.path.join(_root(), "eq-profiles")
