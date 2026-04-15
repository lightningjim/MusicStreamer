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

from musicstreamer.media_keys.base import MediaKeysBackend, NoOpMediaKeysBackend

__all__ = ["create", "MediaKeysBackend", "NoOpMediaKeysBackend"]

_log = logging.getLogger(__name__)


def create(player, repo) -> MediaKeysBackend:
    """Platform factory stub — returns NoOpMediaKeysBackend unconditionally.

    Replaced by the real dispatcher in Task 2 (41-01 Plan, Task 2).
    """
    return NoOpMediaKeysBackend()
