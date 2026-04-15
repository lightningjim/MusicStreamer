"""musicstreamer.media_keys — platform media-key backend package (Phase 41).

Public API:
  create(player, repo) -> MediaKeysBackend
      Platform factory. Selects the appropriate backend based on sys.platform.
      Never raises — all failure modes return NoOpMediaKeysBackend (D-06).

  MediaKeysBackend   — abstract base class (D-02 signal + method surface)
  NoOpMediaKeysBackend — silent fallback (D-06)
"""
from __future__ import annotations

import logging
import sys

from musicstreamer.media_keys.base import MediaKeysBackend, NoOpMediaKeysBackend

__all__ = ["create", "MediaKeysBackend", "NoOpMediaKeysBackend"]

_log = logging.getLogger(__name__)


def create(player, repo) -> MediaKeysBackend:
    """Platform factory — selects OS media-session backend at runtime.

    Dispatch logic:
      - Linux  → lazy-import mpris2.LinuxMprisBackend (Plan 02); falls back to
                 NoOp if not yet installed or construction fails (ImportError /
                 any Exception)
      - win32  → lazy-import smtc.create_windows_backend; catches
                 NotImplementedError (stub until Phase 43.1) and falls back
      - other  → NoOp immediately

    All failure modes return NoOpMediaKeysBackend() — app startup must never
    block on media keys (D-06 / T-41-01).
    """
    if sys.platform.startswith("linux"):
        try:
            from musicstreamer.media_keys.mpris2 import LinuxMprisBackend  # type: ignore[import]
            return LinuxMprisBackend(player, repo)
        except Exception as e:
            _log.warning("Media keys disabled (Linux MPRIS2 unavailable): %s", e)
            return NoOpMediaKeysBackend()

    if sys.platform == "win32":
        try:
            from musicstreamer.media_keys.smtc import create_windows_backend
            return create_windows_backend(player, repo)
        except Exception as e:
            _log.warning("Media keys disabled (Windows SMTC unavailable): %s", e)
            return NoOpMediaKeysBackend()

    _log.warning("Media keys disabled: unsupported platform %r", sys.platform)
    return NoOpMediaKeysBackend()
