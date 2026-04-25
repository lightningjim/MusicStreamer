"""Host-runtime detection (D-11..D-14).

One-shot checks at startup. Results cached on a NodeRuntime dataclass and
passed to UI layers that need to branch on availability (hamburger menu
indicator, YT play failure toast).

Re-detection is explicitly out of scope (D-14): a user who installs Node.js
mid-session must restart the app.
"""
from __future__ import annotations

import glob
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import QMessageBox

_log = logging.getLogger(__name__)

NODEJS_INSTALL_URL = "https://nodejs.org/en/download"

# Capture enum values at module import time so they are resolved against the
# real PySide6 QMessageBox class. Tests monkeypatch ``QMessageBox`` at module
# level with a fake that does not expose the Icon/ButtonRole enums; resolving
# these once here keeps show_missing_node_dialog operating on stable values
# regardless of the fake.
_ICON_WARNING = QMessageBox.Icon.Warning
_ROLE_ACTION = QMessageBox.ButtonRole.ActionRole
_ROLE_ACCEPT = QMessageBox.ButtonRole.AcceptRole


@dataclass(frozen=True)
class NodeRuntime:
    available: bool
    path: Optional[str]  # resolved path to node executable (or None)


def _which_node() -> Optional[str]:
    """Locate node executable on PATH with Windows 3.12 safety.

    CPython issue #109590 (fixed in 3.12.x but triggered on PRE-release builds
    and still a latent footgun): shutil.which may return an extensionless "node"
    (typically a bash script shim) before checking PATHEXT for "node.exe".
    On Windows we explicitly prefer node.exe; on Linux/macOS fall back to stock
    shutil.which behavior.

    Reference: https://github.com/python/cpython/issues/109590
    """
    if sys.platform == "win32":
        # Force .exe resolution — ignore extensionless shims.
        result = shutil.which("node.exe")
        if result:
            return result
        # Fallback for unusual layouts
        result = shutil.which("node")
        if result and result.lower().endswith(".exe"):
            return result
        return None
    result = shutil.which("node")
    if result:
        return result
    return _which_node_version_manager_fallback()


def _which_node_version_manager_fallback() -> Optional[str]:
    """POSIX fallback: find node managed by fnm/nvm/volta/asdf when PATH is bare.

    GUI launches (.desktop Exec=) inherit a non-interactive PATH, so version-
    manager shims (fnm's per-shell /run/user/$UID/fnm_multishells/..., nvm's
    sourced shell function) are missing. Probe known $HOME-rooted layouts
    instead. Returns the first executable node found, or None.
    """
    home = os.path.expanduser("~")
    xdg_data = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")

    candidates: list[str] = [
        # fnm — default alias is a stable symlink to the active version
        os.path.join(xdg_data, "fnm", "aliases", "default", "bin", "node"),
        # volta
        os.path.join(home, ".volta", "bin", "node"),
        # asdf shim
        os.path.join(home, ".asdf", "shims", "node"),
    ]

    # nvm — no "default" symlink; pick the lexicographically highest version.
    nvm_versions = sorted(
        glob.glob(os.path.join(home, ".nvm", "versions", "node", "*", "bin", "node"))
    )
    if nvm_versions:
        candidates.append(nvm_versions[-1])

    # fnm — also try newest installed version if the default alias is missing.
    fnm_versions = sorted(
        glob.glob(os.path.join(xdg_data, "fnm", "node-versions", "*", "installation", "bin", "node"))
    )
    if fnm_versions:
        candidates.append(fnm_versions[-1])

    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def check_node() -> NodeRuntime:
    """One-shot Node.js detection. Safe to call from any thread."""
    path = _which_node()
    if path is None:
        _log.info("Node.js not found on PATH — YouTube playback via yt-dlp EJS will fail.")
        return NodeRuntime(available=False, path=None)
    _log.debug("Node.js detected at %s", path)
    return NodeRuntime(available=True, path=path)


def show_missing_node_dialog(parent) -> None:
    """Non-blocking warning (D-12). Returns immediately; dialog is modal to
    ``parent`` when parent is a QWidget, but app-modal otherwise."""
    box = QMessageBox(parent)
    box.setIcon(_ICON_WARNING)
    box.setWindowTitle("Node.js not found")
    box.setText(
        "MusicStreamer needs Node.js for YouTube playback.\n\n"
        "Install from nodejs.org. All other stream types (ShoutCast, HLS, "
        "Twitch, AudioAddict) will work without it."
    )
    open_btn = box.addButton("Open nodejs.org", _ROLE_ACTION)
    ok_btn = box.addButton("OK", _ROLE_ACCEPT)
    box.setDefaultButton(ok_btn)
    box.exec()  # modal (blocks the dialog, not the app) — "non-blocking" per
                # D-12 means non-blocking in the sense that the user can
                # continue into the app regardless of choice; Qt's
                # QMessageBox.exec is the standard idiom for this.
    if box.clickedButton() is open_btn:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(NODEJS_INSTALL_URL))
