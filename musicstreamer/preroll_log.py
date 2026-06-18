"""Preroll-event diagnostic file sink — Phase 90 / SOMA-PRE-01.

Installs a size-rotated ``RotatingFileHandler`` on the ``musicstreamer.preroll``
logger so every preroll gate INFO line ALSO lands at
``~/.local/share/musicstreamer/preroll-events.log`` regardless of launch context
(terminal vs ``.desktop``).

Rotation parameters (D-02): ``maxBytes=1_048_576, backupCount=3`` — total disk
cap ~4 MB. Path source (D-04): ``paths.preroll_events_log_path()``; the file
uses default permissions (no credential-grade chmod — diagnostic data, not
credentials; mirrors buffer_log.py deliberate departure from oauth_log.py's
tightening pattern).

The install function is idempotent (Pitfall 7) — a second call is a no-op when
a ``RotatingFileHandler`` for the same ``baseFilename`` is already attached.

The handler is attached to the **named** logger ``musicstreamer.preroll`` only;
the root logger / ``basicConfig(WARNING)`` global stays untouched (Pitfall 5).
With ``propagate=True`` (default), the same INFO record continues to reach the
existing stderr handler — both sinks receive the same record.

Caller responsibility (Pitfall 1): directory existence is guaranteed by
``musicstreamer.migration.run_migration()``; ``__main__._run_gui`` installs the
handler AFTER migration returns, so ``RotatingFileHandler``'s eager open never
hits ``FileNotFoundError``.

The logger level is set to INFO (Pitfall 6) because named loggers default to
NOTSET, which would swallow INFO lines before they reach any handler.
``propagate`` is left at its default True (Pitfall 5 stderr-parity invariant).
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from musicstreamer import paths


def install_preroll_events_handler() -> None:
    """Attach a ``RotatingFileHandler`` to the ``musicstreamer.preroll`` logger.

    Idempotent (Pitfall 7): if a ``RotatingFileHandler`` whose ``baseFilename``
    matches ``paths.preroll_events_log_path()`` is already attached, return
    without adding a second handler.

    Handler shape (D-02): ``maxBytes=1_048_576``, ``backupCount=3``,
    ``encoding="utf-8"``. Formatter: ``"%(asctime)s %(message)s"`` so each
    file line is independently date-stampable.

    Sets ``musicstreamer.preroll.level`` to ``INFO`` (Pitfall 6 — named logger
    defaults to NOTSET and would swallow INFO gate events).

    Leaves ``musicstreamer.preroll.propagate`` at its default ``True`` so the
    existing stderr handler from ``basicConfig(WARNING)`` keeps receiving the
    record (Pitfall 5 stderr-parity invariant).
    """
    path = paths.preroll_events_log_path()
    log = logging.getLogger("musicstreamer.preroll")
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler) and h.baseFilename == path:
            return  # already installed — short-circuit
    log.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        path,
        maxBytes=1_048_576,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(handler)
