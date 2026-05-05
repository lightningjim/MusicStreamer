"""Phase 61 / D-09: First-launch .desktop + icon self-install for Linux.

Mirrors ``migration.run_migration()`` — one-shot guarded by a marker file
under ``~/.local/share/musicstreamer/`` (or whatever ``paths.data_dir()``
resolves to, including ``_root_override`` for tests). Idempotent: no-op on
subsequent launches.

Best-effort post-install hooks (D-13): ``update-desktop-database`` and
``gtk-update-icon-cache`` are called via subprocess if available. Failure
does NOT block app startup — both tools are designed to be optional and
GNOME Shell falls back to inotify (``GAppInfoMonitor``) for ``.desktop``
discovery and a directory scan for icon resolution.

No-op on non-Linux platforms (``sys.platform.startswith("linux")`` gate —
inverse of ``__main__._set_windows_aumid``'s Windows-only guard).

Future-proofing note (T-61-03-06 / RESEARCH §Security Domain):
A future phase that bumps the bundled ``Exec=`` line or the icon should
also bump the marker version (``.desktop-installed-v2``) so existing
installs re-run and pick up the new content.

PyInstaller note (RESEARCH §Pitfall 5): ``_BUNDLED_DESKTOP`` and
``_BUNDLED_ICON`` use ``Path(__file__).parent.parent`` to find
``packaging/linux/...`` relative to the package source. This works for
``uv run`` from a source checkout (the only Linux deployment path today).
A future Linux PyInstaller spec would need to declare
``Tree('packaging/linux', prefix='packaging/linux')`` to keep these
bundled-asset paths resolvable post-bundle.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from musicstreamer import constants, paths, subprocess_utils

_log = logging.getLogger(__name__)

# Bundled-asset locations relative to the package root. Module-level so
# tests can monkeypatch via ``monkeypatch.setattr(desktop_install,
# "_BUNDLED_DESKTOP", ...)``.
_PACKAGE_ROOT = Path(__file__).parent.parent  # musicstreamer/ -> repo root
_BUNDLED_DESKTOP = _PACKAGE_ROOT / "packaging" / "linux" / f"{constants.APP_ID}.desktop"
_BUNDLED_ICON = _PACKAGE_ROOT / "packaging" / "linux" / f"{constants.APP_ID}.png"

# XDG icon-theme bucket (RESEARCH §Open Question #4: 256x256 single-bucket
# is the GNOME Shell default; the force-quit dialog displays icons at
# 32-64px and downscales cleanly).
_ICON_BUCKET = "256x256"


def _xdg_data_home() -> Path:
    """``$XDG_DATA_HOME`` with the freedesktop fallback to ``~/.local/share``."""
    env = os.environ.get("XDG_DATA_HOME")
    if env:
        return Path(env)
    return Path.home() / ".local" / "share"


def _install_marker() -> Path:
    """Marker under ``paths.data_dir()`` (respects ``_root_override`` test hook)."""
    return Path(paths.data_dir()) / ".desktop-installed-v1"


def ensure_installed() -> None:
    """Run the self-install if the marker is absent. No-op otherwise.

    Linux-only — early-returns on non-Linux platforms.
    """
    if not sys.platform.startswith("linux"):
        return

    marker = _install_marker()
    if marker.exists():
        _log.debug("desktop_install: marker present, skipping (%s)", marker)
        return

    try:
        _do_install()
    except Exception as exc:  # noqa: BLE001 — fail-soft; log and proceed
        _log.warning(
            "desktop_install failed (will retry next launch): %s", exc
        )
        return

    _write_marker(marker)
    _log.info("desktop_install complete (marker: %s)", marker)


def _do_install() -> None:
    """Atomic install of .desktop file + icon to XDG paths."""
    xdg = _xdg_data_home()

    # 1. .desktop file -> ~/.local/share/applications/<app_id>.desktop
    desktop_dst = xdg / "applications" / f"{constants.APP_ID}.desktop"
    desktop_dst.parent.mkdir(parents=True, exist_ok=True)
    if not desktop_dst.exists():
        _atomic_copy(_BUNDLED_DESKTOP, desktop_dst)
        _log.info("Installed .desktop file: %s", desktop_dst)

    # 2. Icon -> ~/.local/share/icons/hicolor/256x256/apps/<app_id>.png
    icon_dst = (
        xdg / "icons" / "hicolor" / _ICON_BUCKET / "apps"
        / f"{constants.APP_ID}.png"
    )
    icon_dst.parent.mkdir(parents=True, exist_ok=True)
    if not icon_dst.exists():
        _atomic_copy(_BUNDLED_ICON, icon_dst)
        _log.info("Installed icon: %s", icon_dst)

    # 3. Best-effort cache hooks (D-13). Failure is fine -- caches will
    #    rebuild next time the user logs out/in or runs the tool manually.
    _best_effort(["update-desktop-database", str(desktop_dst.parent)])
    _best_effort(
        ["gtk-update-icon-cache", "--quiet", str(xdg / "icons" / "hicolor")]
    )


def _atomic_copy(src: Path, dst: Path) -> None:
    """Copy src -> dst via tmp + rename (POSIX atomic when on the same fs).

    ``shutil.copy2`` preserves mode bits; ``os.replace`` is atomic and
    works cross-platform (matches the discipline in
    ``musicstreamer/cookie_utils.py``). ``os.replace`` does NOT follow
    symlinks at the destination (T-61-03-02 mitigation).
    """
    with tempfile.NamedTemporaryFile(
        dir=str(dst.parent), prefix=f".{dst.name}.", delete=False
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        shutil.copy2(src, tmp_path)
        os.replace(tmp_path, dst)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _best_effort(cmd: list[str]) -> None:
    """Run ``cmd``; log failure but never raise.

    ``cmd`` is a ``list[str]`` (no shell=True), so no shell-injection
    risk even if XDG paths contain unusual characters
    (RESEARCH §Security Domain T-61-03-03).

    Routed through ``subprocess_utils._run`` for PKG-03 compliance —
    bare blocking subprocess calls are forbidden anywhere else in
    ``musicstreamer/`` (see ``tests/test_pkg03_compliance.py``).
    """
    try:
        result = subprocess_utils._run(
            cmd, capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            _log.debug(
                "%s exit %d: %s",
                cmd[0], result.returncode, result.stderr.strip()
            )
    except FileNotFoundError:
        _log.debug("%s not found on PATH -- skipping cache refresh", cmd[0])
    except subprocess.TimeoutExpired:
        _log.debug("%s timed out -- skipping", cmd[0])
    except Exception as exc:  # noqa: BLE001
        _log.debug("%s raised %s -- skipping", cmd[0], exc)


def _write_marker(marker: Path) -> None:
    """Atomically write the install marker (mirrors ``migration._write_marker``)."""
    marker.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=str(marker.parent),
        prefix=f".{marker.name}.",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(
            f"desktop install v1 complete; app_id={constants.APP_ID}\n"
        )
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, marker)
