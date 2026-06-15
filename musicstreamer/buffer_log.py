"""Buffer-event diagnostic file sink — Phase 78 / BUG-09 Commit A.

Installs a size-rotated ``RotatingFileHandler`` on the ``musicstreamer.player``
logger so every Phase 62 ``buffer_underrun ...`` INFO line ALSO lands at
``~/.local/share/musicstreamer/buffer-events.log`` regardless of launch context
(terminal vs ``.desktop``).

Rotation parameters (D-02): ``maxBytes=1_048_576, backupCount=3`` — total disk
cap ~4 MB. Path source (D-03): ``paths.buffer_events_log_path()``; the file
uses default permissions (no credential-grade chmod — diagnostic data, not
credentials; deliberate departure from oauth_log.py's tightening pattern).

The install function is idempotent (Pitfall 7) — a second call is a no-op when
a ``RotatingFileHandler`` for the same ``baseFilename`` is already attached.

The handler is attached to the **named** logger ``musicstreamer.player`` only;
the root logger / ``basicConfig(WARNING)`` global stays untouched (Phase 62
Pitfall 5). With ``propagate=True`` (default), the same INFO record continues
to reach the existing stderr handler — both sinks receive the same record.

Caller responsibility (Pitfall 1): directory existence is guaranteed by
``musicstreamer.migration.run_migration()``; ``__main__._run_gui`` installs the
handler AFTER migration returns, so ``RotatingFileHandler``'s eager open never
hits ``FileNotFoundError``.

Phase 87 extension: ``install_gbs_marquee_handler()`` installs a parallel
``RotatingFileHandler`` on the ``musicstreamer.gbs_marquee`` named logger.
GBS marquee + themed-day events share ``buffer-events.log`` via this named
logger; consumers filter by message prefix ``gbs.marquee.*`` /
``gbs.themed_day.*``.  Both handlers are idempotent and use the same D-02
rotation parameters.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from musicstreamer import paths


def install_buffer_events_handler() -> None:
    """Attach a ``RotatingFileHandler`` to the ``musicstreamer.player`` logger.

    Idempotent (Pitfall 7): if a ``RotatingFileHandler`` whose ``baseFilename``
    matches ``paths.buffer_events_log_path()`` is already attached, return
    without adding a second handler.

    Handler shape (D-02): ``maxBytes=1_048_576``, ``backupCount=3``,
    ``encoding="utf-8"``. Formatter: ``"%(asctime)s %(message)s"`` so each
    file line is independently date-stampable.

    Leaves ``musicstreamer.player.propagate`` at its default ``True`` so the
    existing stderr handler from ``basicConfig(WARNING)`` keeps receiving the
    record (Pitfall 5 stderr-parity invariant).
    """
    path = paths.buffer_events_log_path()
    log = logging.getLogger("musicstreamer.player")
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler) and h.baseFilename == path:
            return  # already installed — short-circuit
    handler = RotatingFileHandler(
        path,
        maxBytes=1_048_576,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(handler)


def install_gbs_marquee_handler() -> None:
    """Attach a ``RotatingFileHandler`` to the ``musicstreamer.gbs_marquee`` logger.

    GBS marquee + themed-day events share ``buffer-events.log`` via the named
    logger ``musicstreamer.gbs_marquee``; consumers filter by message prefix
    ``gbs.marquee.*`` / ``gbs.themed_day.*``.

    Idempotent (Pitfall 7): if a ``RotatingFileHandler`` whose ``baseFilename``
    matches ``paths.buffer_events_log_path()`` is already attached, return
    without adding a second handler.

    Handler shape (D-02): ``maxBytes=1_048_576``, ``backupCount=3``,
    ``encoding="utf-8"``. Formatter: ``"%(asctime)s %(message)s"`` so each
    file line is independently date-stampable.

    Leaves ``musicstreamer.gbs_marquee.propagate`` at its default ``True`` so
    the existing stderr handler from ``basicConfig(WARNING)`` keeps receiving
    the record (Pitfall 5 stderr-parity invariant).
    """
    path = paths.buffer_events_log_path()
    log = logging.getLogger("musicstreamer.gbs_marquee")
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler) and h.baseFilename == path:
            return  # already installed — short-circuit
    handler = RotatingFileHandler(
        path,
        maxBytes=1_048_576,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(handler)
