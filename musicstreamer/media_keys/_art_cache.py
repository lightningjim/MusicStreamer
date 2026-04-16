"""Cover-art PNG cache for MPRIS2 metadata publishing (Phase 41, D-04).

Provides two public functions:

    cover_path_for_station(station_id) -> str
        Returns the stable file path for a station's cover art PNG,
        creating the parent directory on demand.

    write_cover_png(pixmap, station_id) -> str | None
        Serializes a QPixmap to PNG at the stable path.  Returns the
        absolute path on success, None if the pixmap is null or the
        save fails.

D-04 contract: same file path is used for every publish of the same
station_id — no tmp-file churn, file is overwritten in place on update.
"""
from __future__ import annotations

import logging
import os

from PySide6.QtGui import QPixmap

import musicstreamer.paths as paths

_log = logging.getLogger(__name__)


def cover_path_for_station(station_id: int) -> str:
    """Return the absolute PNG path for *station_id*, creating the parent dir.

    The path is stable: ``{user_cache_dir}/mpris-art/{station_id}.png``.
    The ``mpris-art/`` directory is created with ``exist_ok=True`` so this
    function is idempotent and safe to call repeatedly.
    """
    if not isinstance(station_id, int):
        raise TypeError(f"station_id must be int, got {type(station_id).__name__}")
    art_dir = os.path.join(paths.user_cache_dir(), "mpris-art")
    os.makedirs(art_dir, exist_ok=True)
    return os.path.join(art_dir, f"{station_id}.png")


def write_cover_png(pixmap: QPixmap | None, station_id: int) -> str | None:
    """Serialize *pixmap* to PNG at the stable per-station path.

    Returns:
        Absolute path to the written PNG on success.
        None if *pixmap* is None, isNull(), or if the save fails.
    """
    if pixmap is None or pixmap.isNull():
        return None

    path = cover_path_for_station(station_id)
    ok = pixmap.save(path, "PNG")
    if not ok:
        _log.warning("write_cover_png: QPixmap.save() failed for station %d at %s", station_id, path)
        return None
    return path
