"""OAuth diagnostic logger — Phase 999.3 D-10/D-11.

Persistent rotating log for OAuth subprocess outcomes. Never contains
tokens, URLs, or query strings (T-999.3-03). 0o600 permissions.
"""
from __future__ import annotations

import json
import logging
import os
import time
from logging.handlers import RotatingFileHandler

_SCRUB_PATTERNS = (
    "://",            # any URL
    "access_token",   # fragment key
)
_SCRUB_PREFIXES = ("state=", "code=", "token=")
_MAX_DETAIL_LEN = 200


def _scrub(detail: str) -> str:
    """Return detail, or ``<scrubbed>`` if it trips any scrub rule.

    Rules (T-999.3-03):
    - len > 200 chars
    - contains ``://`` (any URL)
    - contains ``access_token`` (OAuth fragment key)
    - starts with ``state=``, ``code=``, or ``token=``
    """
    if not isinstance(detail, str):
        return "<scrubbed>"
    if len(detail) > _MAX_DETAIL_LEN:
        return "<scrubbed>"
    for p in _SCRUB_PATTERNS:
        if p in detail:
            return "<scrubbed>"
    for pfx in _SCRUB_PREFIXES:
        if detail.startswith(pfx):
            return "<scrubbed>"
    return detail


class OAuthLogger:
    """Rotating-file OAuth event logger with scrub guard and 0o600 perms.

    Lazy — file is not created until the first ``log_event`` call. On
    first write, permissions are tightened to 0o600 (T-40-03 parity).

    Rotation is size-based: ``maxBytes=64*1024, backupCount=2`` — the
    log writer keeps at most 3 files (``oauth.log``, ``oauth.log.1``,
    ``oauth.log.2``); ``oauth.log.3`` is never created.
    """

    def __init__(self, log_path: str) -> None:
        self._log_path = log_path
        # Unique logger name per instance (id()) so tests can create
        # multiple OAuthLoggers without handler bleed-through.
        self._logger = logging.getLogger(f"musicstreamer.oauth.{id(self)}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        # D-10: size-rotated, 64KB, backupCount=2
        handler = RotatingFileHandler(
            log_path,
            maxBytes=64 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)
        self._chmod_done = False

    def log_event(self, event: dict) -> None:
        """Write one scrubbed JSON line for ``event``.

        ``event`` keys are defensively coerced: ts→float, category→str[:64],
        detail→scrubbed str, provider→str[:32]. Unknown keys are dropped.
        """
        scrubbed = {
            "ts": float(event.get("ts", time.time())),
            "category": str(event.get("category", "Unknown"))[:64],
            "detail": _scrub(str(event.get("detail", ""))),
            "provider": str(event.get("provider", ""))[:32],
        }
        self._logger.info(json.dumps(scrubbed, separators=(",", ":")))
        # T-40-03 parity: tighten perms once the file exists on disk.
        if not self._chmod_done and os.path.exists(self._log_path):
            os.chmod(self._log_path, 0o600)
            self._chmod_done = True
