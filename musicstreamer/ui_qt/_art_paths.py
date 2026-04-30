"""Shared resolver for station_art_path → absolute filesystem path and the
unified station-icon loader.

``station_art_path`` is stored as a relative path under ``paths.data_dir()``
(e.g. ``"assets/12/station_art.png"``). ``QPixmap(path)`` resolves relative
paths against CWD, which silently returns null. The helpers below normalize
to an absolute path before load and wrap QPixmapCache + fallback so every
UI surface renders station logos consistently.

Public API:
    abs_art_path(rel_or_abs)   — resolve a relative art path to absolute
    load_station_icon(station) — QPixmapCache-backed QIcon with fallback
    FALLBACK_ICON              — resource path to the generic fallback icon

The module is underscore-prefixed to mark it internal-to-ui_qt; the functions
and constant are the public surface.
"""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap, QPixmapCache

from musicstreamer import paths
from musicstreamer.ui_qt._theme import STATION_ICON_SIZE
# Side-effect import: registers :/icons/ resource prefix before QPixmap lookups.
from musicstreamer.ui_qt import icons_rc  # noqa: F401


FALLBACK_ICON = ":/icons/audio-x-generic-symbolic.svg"


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


def load_station_icon(station, size: int = STATION_ICON_SIZE) -> QIcon:
    """Return a QPixmapCache-backed QIcon for ``station`` with fallback.

    Resolution order:
        1. station.station_art_path (resolved via abs_art_path) loaded as QPixmap.
        2. If that yields a null pixmap (missing/unreadable file), fall back to
           FALLBACK_ICON.

    Cache key is ``f"station-logo:{abs_path or FALLBACK_ICON}"`` keyed on the
    resolved absolute path so the same logo referenced as relative vs. absolute
    hits the same cache entry (D-03).

    Parameters
    ----------
    station : Station
        Any object exposing ``.station_art_path`` (Optional[str]).
    size : int, default 32
        Target pixel bound. Pixmap is scaled to fit ``size`` × ``size`` with
        aspect ratio preserved.
    """
    rel = getattr(station, "station_art_path", None)
    abs_path = abs_art_path(rel)
    load_path = abs_path or FALLBACK_ICON
    key = f"station-logo:{load_path}"

    pix = QPixmap()
    if not QPixmapCache.find(key, pix):
        src = QPixmap(load_path)
        if src.isNull():
            src = QPixmap(FALLBACK_ICON)
        scaled = src.scaled(
            size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        # Paint onto a transparent square canvas so QIcon stores a perfectly
        # square pixmap with the logo centered and pillarbox/letterbox
        # transparent. Eliminates any platform-style ambiguity about how a
        # non-square decoration pixmap is centered inside a 32x32 cell.
        # Phase 54 / D-04 (transparent bars) / D-05 (edge-to-edge longer axis).
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        x = (size - scaled.width()) // 2
        y = (size - scaled.height()) // 2
        painter.drawPixmap(QPoint(x, y), scaled)
        painter.end()
        QPixmapCache.insert(key, pix)
    return QIcon(pix)
