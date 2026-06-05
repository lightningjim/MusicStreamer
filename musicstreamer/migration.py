"""First-launch data migration helper (PORT-06, D-14..D-16).

Behaviour:

* When running **inside the Flatpak sandbox** (``is_sandboxed()`` True):
  create the dest dir and write the migration marker so the
  ``buffer_log.install_buffer_events_handler`` ordering invariant at
  ``__main__.py:199`` is satisfied, but perform ZERO file copies — host
  secrets (``cookies.txt``, ``twitch-token.txt``) must not enter the sandbox
  without user consent.  The import wizard (Plan 02) is the sole path for
  host data to enter the sandbox (T-86.1-01 mitigation).
* On Linux (native, non-Flatpak), ``platformdirs.user_data_dir("musicstreamer")``
  resolves to the same path as the v1.5 hard-coded location
  (``~/.local/share/musicstreamer``), so this is effectively a no-op — we
  just write a marker file so subsequent launches short-circuit immediately.
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

    # Sandbox guard (T-86.1-01): when running inside the Flatpak sandbox,
    # src != dest because XDG_DATA_HOME is remapped to ~/.var/app/…/data.
    # Without this guard _copy_tree_nondestructive would silently ingest
    # 0600 host secrets (cookies.txt, twitch-token.txt) into the sandbox
    # without user consent.  Skip ALL copying; the import wizard (Plan 02)
    # is the sole path for host data to enter the sandbox.
    # The dest dir and marker are still created so the buffer_log ordering
    # invariant at __main__.py:199 is preserved (DATA_DIR must exist after
    # run_migration() returns).
    from musicstreamer.flatpak_first_launch import is_sandboxed  # late import keeps module cheap

    if is_sandboxed():
        _write_marker(marker)
        return

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
