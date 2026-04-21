"""Windows SMTC media-keys backend (Phase 43.1, MEDIA-03/04/05).

Implements the Windows leaf of the musicstreamer.media_keys factory using
winrt-Windows.Media.Playback. The abstract base class, signal surface,
cover-art PNG helper, and MainWindow wiring were all built in Phase 41
-- this module replaces the NotImplementedError stub.

Import guard contract (CONTEXT D-06):
  All winrt imports live inside function/method bodies. Module scope is
  pure Python so the file stays importable on Linux for test discovery
  and factory introspection.

Failure fallback contract (CONTEXT D-07):
  If winrt wheels are not installed, `create_windows_backend` raises
  ImportError which the outer factory in media_keys/__init__.py catches
  and degrades to NoOpMediaKeysBackend -- app startup never blocks.

Installation: `pip install -e ".[windows]"` inside the conda-forge
Windows env (see .planning/phases/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md
and .claude/skills/spike-findings-musicstreamer/SKILL.md).
"""
from __future__ import annotations

import logging

from musicstreamer.media_keys.base import MediaKeysBackend

_log = logging.getLogger(__name__)

_INSTALL_HINT = (
    "Windows media keys unavailable -- install with "
    '`pip install -e ".[windows]"` inside the Windows env.'
)


def create_windows_backend(player, repo) -> MediaKeysBackend:
    """Construct the Windows SMTC backend, or raise ImportError on missing wheels.

    D-06: winrt imports happen inside this function body so smtc.py stays
    Linux-importable. D-07: any ImportError (or other Exception) propagates
    to the factory in media_keys/__init__.py which falls back to
    NoOpMediaKeysBackend.
    """
    try:
        # Deferred imports: triggers ImportError on Linux / Windows without
        # the [windows] extras. These names are also re-imported inside
        # WindowsMediaKeysBackend.__init__ to keep each entry point
        # self-contained.
        from winrt.windows.media.playback import MediaPlayer  # noqa: F401, PLC0415
        from winrt.windows.media import (  # noqa: F401, PLC0415
            MediaPlaybackStatus,
            MediaPlaybackType,
            SystemMediaTransportControlsButton,
        )
    except ImportError as exc:
        raise ImportError(_INSTALL_HINT) from exc

    # Plan 43.1-03 lands WindowsMediaKeysBackend(player, repo). Until then,
    # raise so any caller on a winrt-enabled machine still surfaces the
    # unfinished state loudly rather than returning a broken stub.
    raise ImportError(
        "WindowsMediaKeysBackend pending (Plan 43.1-03 replaces this line "
        "with `return WindowsMediaKeysBackend(player, repo)`)"
    )
