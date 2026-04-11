"""Cross-platform subprocess.Popen wrapper (PKG-03 pre-stage for Phase 44).

Currently a thin passthrough on Linux/macOS. On Windows it adds
``creationflags=subprocess.CREATE_NO_WINDOW`` so child processes (mpv,
yt-dlp, streamlink) don't pop a console window when launched from a
PySide6 GUI built with pythonw.

This module exists so the future Windows port (Phase 44) only needs to
touch one file when adding platform-specific subprocess flags. Phase 35
introduces it solely for ``musicstreamer.player._play_youtube``'s mpv
launcher path (KEEP_MPV branch -- see 35-SPIKE-MPV.md).
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any


def popen(cmd: list[str], **kwargs: Any) -> subprocess.Popen:
    """Launch a subprocess with platform-appropriate defaults.

    On Windows, adds CREATE_NO_WINDOW to creationflags so no console
    window appears for GUI-spawned children. On other platforms this is
    a direct passthrough to ``subprocess.Popen``.
    """
    if sys.platform == "win32":
        flags = kwargs.pop("creationflags", 0)
        flags |= subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        kwargs["creationflags"] = flags
    return subprocess.Popen(cmd, **kwargs)
