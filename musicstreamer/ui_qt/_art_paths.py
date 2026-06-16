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
    THUMB_FILENAME             — constant filename for pre-scaled thumbnails
    _thumb_path_for(abs_source) — derive sibling thumb path (D-05)
    _is_thumb_fresh(source, thumb) — mtime staleness check (D-06)
    _generate_thumb(source, thumb, station_id, callback) — daemon worker (D-02, D-04)

The module is underscore-prefixed to mark it internal-to-ui_qt; the functions
and constant are the public surface.
"""
from __future__ import annotations

import os
import tempfile
import threading
from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap, QPixmapCache

from musicstreamer import paths
from musicstreamer.ui_qt._theme import STATION_ICON_SIZE
# Side-effect import: registers :/icons/ resource prefix before QPixmap lookups.
from musicstreamer.ui_qt import icons_rc  # noqa: F401


FALLBACK_ICON = ":/icons/audio-x-generic-symbolic.svg"
THUMB_FILENAME = "station_art.thumb.png"


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


def _thumb_path_for(abs_source_path: str) -> str:
    """Return the sibling thumbnail path for a source logo (D-05).

    The thumbnail is always stored as ``THUMB_FILENAME`` in the same directory
    as the source logo, e.g. ``assets/12/station_art.thumb.png`` for a source
    at ``assets/12/station_art.png``.
    """
    return os.path.join(os.path.dirname(abs_source_path), THUMB_FILENAME)


def _is_thumb_fresh(source_path: str, thumb_path: str) -> bool:
    """Return True iff the thumbnail is at least as new as the source logo (D-06).

    Returns False on any OSError (missing source or missing thumb).
    """
    try:
        return os.stat(thumb_path).st_mtime >= os.stat(source_path).st_mtime
    except OSError:
        return False


def _generate_thumb(
    source_path: str,
    thumb_path: str,
    station_id: int,
    callback,
) -> None:
    """Spawn a daemon thread that scales source_path to 96px and writes it atomically (D-02, D-04).

    The worker calls ``callback(station_id, source_path, thumb_path)`` on success
    or ``callback(station_id, source_path, None)`` on any failure (null image,
    write error, unexpected exception).

    CR-01: the worker uses QImage only — QPixmap is NOT thread-safe and must
    never be constructed off the main thread (see gbs_marquee.py line 468).
    The atomic write uses mkstemp + os.replace so readers see either the old
    complete file or the new complete file, never a partial write (T-94-04).
    """

    def _worker():
        try:
            img = QImage(source_path)
            if img.isNull():
                callback(station_id, source_path, None)
                return

            # Scale to 96px longest axis, preserve aspect ratio (D-04).
            scaled = img.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            thumb_dir = os.path.dirname(thumb_path)
            os.makedirs(thumb_dir, exist_ok=True)

            # Atomic write: mkstemp in the same directory guarantees a same-fs
            # rename so os.replace is POSIX-atomic (T-94-04).
            fd, tmp = tempfile.mkstemp(dir=thumb_dir, suffix=".thumb.tmp.png")
            try:
                os.close(fd)
                if scaled.save(tmp, "PNG"):
                    os.replace(tmp, thumb_path)
                    callback(station_id, source_path, thumb_path)
                else:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                    callback(station_id, source_path, None)
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                callback(station_id, source_path, None)
        except Exception:
            callback(station_id, source_path, None)

    threading.Thread(target=_worker, daemon=True).start()


def load_station_icon(
    station, size: int = STATION_ICON_SIZE, on_thumb_needed=None
) -> QIcon:
    """Return a QPixmapCache-backed QIcon for ``station`` with fallback.

    Phase 94 thumb fast path: when a 96px pre-scaled thumbnail exists on disk
    and is fresher than the source logo (D-06), it is loaded directly instead
    of decoding the full-resolution source (D-02). On a thumb miss or stale
    thumb, the fallback icon is returned immediately and ``on_thumb_needed``
    is called to trigger async generation (D-02, D-04, D-05).

    Resolution order (QPixmapCache miss, abs_path present):
        1. Thumb exists and is fresh -> src = QPixmap(thumb_path) (96px fast path).
        2. Thumb missing or stale -> src = QPixmap(FALLBACK_ICON); call
           on_thumb_needed(station.id, abs_path, thumb_path) if provided and
           station.id is not None.
        3. abs_path is None (no station_art_path) -> src = QPixmap(FALLBACK_ICON);
           no on_thumb_needed call (Pitfall 5 — no worker spawned for icon-less stations).

    Cache key is ``f"station-logo:{abs_path or FALLBACK_ICON}"`` keyed on the
    resolved-then-joined absolute path string (NOT the thumb path). This matches
    the eviction key used by edit_station_dialog._invalidate_cache_for. Note:
    paths are joined via ``os.path.join`` but NOT canonicalized (no
    ``os.path.normpath`` / ``os.path.realpath``), so callers passing a
    non-canonical relative form (e.g. ``./assets/1/logo.png`` vs
    ``assets/1/logo.png``) may not hit a previously-cached entry for the
    equivalent canonical path. Once a given string is used, subsequent calls
    with the same string hit the same cache entry (D-03). WR-03 / Phase 54 review.

    Parameters
    ----------
    station : Station
        Any object exposing ``.station_art_path`` (Optional[str]).
    size : int, default 32
        Target pixel bound. Pixmap is scaled to fit ``size`` × ``size`` with
        aspect ratio preserved.
    on_thumb_needed : callable(station_id: int, source_abs_path: str, thumb_abs_path: str) | None
        Called when the thumb is missing or stale. The caller (typically
        StationTreeModel) uses this to enqueue async thumb generation without
        re-entering this function. Default None preserves the existing 2-arg
        call signature at all existing call sites.
    """
    rel = getattr(station, "station_art_path", None)
    abs_path = abs_art_path(rel)
    load_path = abs_path or FALLBACK_ICON
    key = f"station-logo:{load_path}"

    pix = QPixmap()
    if not QPixmapCache.find(key, pix):
        if abs_path is not None:
            thumb_path = _thumb_path_for(abs_path)
            if _is_thumb_fresh(abs_path, thumb_path):
                # Thumb is fresh: use 96px thumbnail (fast path, D-02).
                src = QPixmap(thumb_path)
            elif on_thumb_needed is not None:
                # Thumb missing/stale and a consumer wants async generation:
                # D-03 (locked) — return FALLBACK immediately (zero full-res
                # decode on the paint path), enqueue async generation.  When
                # the worker lands, _on_thumb_landing evicts the cache entry and
                # emits dataChanged so Qt re-queries data(DecorationRole) which
                # then hits the fresh-thumb fast path (96px decode only).
                # This keeps the first scroll smooth: no blocking I/O per row.
                src = QPixmap(FALLBACK_ICON)
                if getattr(station, "id", None) is not None:
                    on_thumb_needed(station.id, abs_path, thumb_path)
            else:
                # Legacy 2-arg callers (favorites_view, station_list_panel):
                # no thumb consumer, load the source logo directly (original behavior).
                src = QPixmap(load_path)
        else:
            src = QPixmap(FALLBACK_ICON)
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
        # Carry the source pixmap's devicePixelRatio onto the canvas so QIcon
        # does not nearest-neighbor up-scale our output on HiDPI displays
        # (Wayland fractional, macOS Retina, Windows 1.5x/2x). Without this
        # the new transparent canvas defaults to DPR=1.0 and Qt blurs the
        # logo on >1.0 DPR rows. CR-01 / Phase 54 review.
        pix.setDevicePixelRatio(scaled.devicePixelRatio())
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        x = (size - scaled.width()) // 2
        y = (size - scaled.height()) // 2
        painter.drawPixmap(QPoint(x, y), scaled)
        painter.end()
        QPixmapCache.insert(key, pix)
    return QIcon(pix)
