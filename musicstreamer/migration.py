"""First-launch data migration helper (PORT-06, D-14..D-16).

Behaviour:

* On Linux, ``platformdirs.user_data_dir("musicstreamer")`` resolves to the
  same path as the v1.5 hard-coded location (``~/.local/share/musicstreamer``),
  so this is effectively a no-op — we just write a marker file so subsequent
  launches short-circuit immediately.
* On Windows / macOS (or anywhere the legacy Linux path differs from the
  platformdirs root) we **non-destructively** copy any legacy files into the
  new root using ``shutil.copy2`` to preserve mode bits — important for the
  ``cookies.txt`` and ``twitch-token.txt`` files which are 0600.
* The marker file (``.platformdirs-migrated``) makes the helper idempotent:
  re-invocations are a single ``os.path.exists`` check.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from musicstreamer import paths

# Module-level so tests can monkeypatch it to point at a tmp directory.
_LEGACY_LINUX = os.path.expanduser("~/.local/share/musicstreamer")


def run_migration() -> None:
    marker = paths.migration_marker()
    if os.path.exists(marker):
        return

    dest = paths.data_dir()
    os.makedirs(dest, exist_ok=True)

    src = _LEGACY_LINUX
    # Same path → nothing to copy. Linux v1.5 → v2.0 is this branch.
    if os.path.isdir(src) and os.path.realpath(src) == os.path.realpath(dest):
        _write_marker(marker)
        return

    if os.path.isdir(src):
        _copy_tree_nondestructive(src, dest)

    _write_marker(marker)


def _copy_tree_nondestructive(src: str, dst: str) -> None:
    """Copy files from ``src`` into ``dst`` without overwriting existing dest files.

    Uses ``shutil.copy2`` to preserve mode bits — security-critical for the
    0600 cookies/token files.
    """
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_dir = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target_dir, exist_ok=True)
        for f in files:
            s = os.path.join(root, f)
            d = os.path.join(target_dir, f)
            if not os.path.exists(d):
                shutil.copy2(s, d)


def _write_marker(path: str) -> None:
    Path(path).write_text("platformdirs migration complete\n")
