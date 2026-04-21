"""Cover-art PNG cache for OS media session metadata (Phase 41 D-04 + Phase 43.1 D-04 rename mpris-art/ → media-art/).

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

# One-shot migration sentinel: set to True on first call to _migrate_legacy_cache_dir
# so subsequent cover_path_for_station calls skip the legacy-dir probe entirely.
_migration_attempted: bool = False


def _migrate_legacy_cache_dir(cache_root: str) -> None:
    """Best-effort one-shot migration of mpris-art/ → media-art/.

    Called lazily on the first invocation of cover_path_for_station per process.
    Any OSError during os.rename is swallowed — PNGs are regenerated on the
    next publish_metadata call if migration fails.
    """
    global _migration_attempted
    if _migration_attempted:
        return
    _migration_attempted = True

    legacy = os.path.join(cache_root, "mpris-art")
    new = os.path.join(cache_root, "media-art")
    if os.path.isdir(legacy) and not os.path.exists(new):
        try:
            os.rename(legacy, new)
        except OSError as exc:
            _log.debug("_art_cache: mpris-art → media-art migration skipped: %s", exc)


def cover_path_for_station(station_id: int) -> str:
    """Return the absolute PNG path for *station_id*, creating the parent dir.

    The path is stable: ``{user_cache_dir}/media-art/{station_id}.png``.
    The ``media-art/`` directory is created with ``exist_ok=True`` so this
    function is idempotent and safe to call repeatedly.
    """
    if not isinstance(station_id, int):
        raise TypeError(f"station_id must be int, got {type(station_id).__name__}")
    _migrate_legacy_cache_dir(paths.user_cache_dir())
    art_dir = os.path.join(paths.user_cache_dir(), "media-art")
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
