"""Shared resolver for station_art_path → absolute filesystem path.

station_art_path is stored as a relative path under paths.data_dir()
(e.g. "assets/12/station_art.png"). QPixmap(path) resolves relative paths
against CWD, which silently returns null. This helper normalizes to an
absolute path before load.

Public: abs_art_path(rel_or_abs) — used by now_playing_panel,
station_list_panel, and edit_station_dialog. The module itself is
underscore-prefixed to mark it internal-to-ui_qt; the function is public.
"""
from __future__ import annotations

import os
from typing import Optional

from musicstreamer import paths


def abs_art_path(rel_or_abs: Optional[str]) -> Optional[str]:
    """Resolve a station_art_path to an absolute filesystem path.

    Returns None for falsy input. Absolute paths pass through unchanged.
    Relative paths are resolved against paths.data_dir().
    """
    if not rel_or_abs:
        return None
    if os.path.isabs(rel_or_abs):
        return rel_or_abs
    return os.path.join(paths.data_dir(), rel_or_abs)
