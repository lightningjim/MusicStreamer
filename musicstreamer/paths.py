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


def accent_css_path() -> str:
    return os.path.join(_root(), "accent.css")


def migration_marker() -> str:
    return os.path.join(_root(), ".platformdirs-migrated")
