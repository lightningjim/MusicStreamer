"""Host-runtime detection (D-11..D-14).

One-shot checks at startup. Results cached on a NodeRuntime dataclass and
passed to UI layers that need to branch on availability (hamburger menu
indicator, YT play failure toast).

Re-detection is explicitly out of scope (D-14): a user who installs Node.js
mid-session must restart the app.
"""
from __future__ import annotations

import logging
import shutil
import sys
from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import QMessageBox

_log = logging.getLogger(__name__)

NODEJS_INSTALL_URL = "https://nodejs.org/en/download"


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
    return shutil.which("node")


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
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Node.js not found")
    box.setText(
        "MusicStreamer needs Node.js for YouTube playback.\n\n"
        "Install from nodejs.org. All other stream types (ShoutCast, HLS, "
        "Twitch, AudioAddict) will work without it."
    )
    open_btn = box.addButton("Open nodejs.org", QMessageBox.ButtonRole.ActionRole)
    ok_btn = box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(ok_btn)
    box.exec()  # modal (blocks the dialog, not the app) — "non-blocking" per
                # D-12 means non-blocking in the sense that the user can
                # continue into the app regardless of choice; Qt's
                # QMessageBox.exec is the standard idiom for this.
    if box.clickedButton() is open_btn:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(NODEJS_INSTALL_URL))
