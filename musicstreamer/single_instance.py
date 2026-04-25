"""Single-instance enforcement via QLocalServer/QLocalSocket (D-08, D-09).

First instance calls acquire_or_forward() and receives a running QLocalServer
(kept alive for the app lifetime). Subsequent launches connect to that server,
send the literal bytes b"activate\\n", and exit cleanly. The first instance's
newConnection handler raises and focuses the main window.

On Windows QLocalSocket uses a named pipe under the hood — no socket file
to clean up (removeServer is a no-op on Windows). On Linux, removeServer
deletes a stale socket file so a crashed prior instance does not block us.

Lifetime: signal connections use bound methods only (QA-05). Incoming
sockets are parented to the server (``socket.setParent(self)``) so their
lifetime is tied to it, and ``readyRead`` dispatches via ``QObject.sender()``
rather than a captured-lambda. This avoids a deleteLater-then-readyRead
race that segfaults pytest-qt's event-loop processing during teardown.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

_log = logging.getLogger(__name__)

SERVER_NAME = "org.lightningjim.MusicStreamer.single-instance"  # D-08
_CONNECT_TIMEOUT_MS = 500  # plenty for a local named pipe / AF_UNIX socket


class SingleInstanceServer(QObject):
    """Wraps a QLocalServer and emits ``activate_requested`` on each incoming
    activation message. Keep a reference for the app lifetime — dropping it
    closes the server and breaks single-instance enforcement.
    """

    activate_requested = Signal()

    def __init__(self, server: QLocalServer, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server = server
        self._server.newConnection.connect(self._on_new_connection)

    def _on_new_connection(self) -> None:
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        # Parent the socket to self so its lifetime is tied to this server
        # — prevents a deleteLater-then-readyRead race that segfaults
        # pytest-qt event processing during teardown.
        socket.setParent(self)
        # QA-05 compliant: bound method, no captured lambda. We resolve the
        # signaling socket at handler time via QObject.sender().
        socket.readyRead.connect(self._on_socket_ready)
        socket.disconnected.connect(socket.deleteLater)

    def _on_socket_ready(self) -> None:
        socket = self.sender()
        if not isinstance(socket, QLocalSocket):
            return
        self._drain(socket)

    def _drain(self, socket: QLocalSocket) -> None:
        data = bytes(socket.readAll()).strip()
        if data == b"activate":
            self.activate_requested.emit()
        socket.disconnectFromServer()

    def close(self) -> None:
        self._server.close()


def acquire_or_forward() -> Optional[SingleInstanceServer]:
    """Try to become the single instance.

    Returns:
        SingleInstanceServer if this process is the first/sole instance.
        None if another instance was running — caller should sys.exit(0) immediately.

    MUST be called after QApplication has been constructed (QLocalServer
    needs the event loop to emit newConnection).
    """
    # Probe: if a prior instance is running, connect + send "activate" + exit.
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if socket.waitForConnected(_CONNECT_TIMEOUT_MS):
        socket.write(b"activate\n")
        socket.flush()
        socket.waitForBytesWritten(_CONNECT_TIMEOUT_MS)
        socket.disconnectFromServer()
        _log.info("Another instance is running — forwarded activation and exiting.")
        return None

    # No server answered — either we are first, or a stale socket file blocks us
    # (Linux only). removeServer is safe to call unconditionally; it's a no-op
    # on Windows (Pitfall 2 — stale Unix socket cleanup).
    QLocalServer.removeServer(SERVER_NAME)

    server = QLocalServer()
    # SocketOption.UserAccessOption restricts the socket to the current user on
    # Unix (irrelevant on Windows named pipes, but harmless).
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(SERVER_NAME):
        # Extremely unlikely after removeServer — log and proceed
        # single-instance-less rather than crash the app.
        _log.warning(
            "QLocalServer.listen failed: %s — continuing without single-instance guard.",
            server.errorString(),
        )
        return None

    return SingleInstanceServer(server)


def raise_and_focus(window) -> None:
    """Bring ``window`` to the foreground in response to an activate request.

    On Windows, Qt's ``activateWindow()`` alone is often blocked by focus-steal
    prevention. We call ``showNormal()`` (undoes minimize), ``raise_()``
    (Z-order), and ``activateWindow()`` (focus). If focus-steal blocks the
    raise, ``FlashWindowEx`` falls back to flashing the taskbar icon (D-09).
    """
    # Restore from minimize if needed
    window.showNormal()
    window.raise_()
    window.activateWindow()

    if sys.platform == "win32":
        # FlashWindowEx fallback — if focus-steal blocks activateWindow, at
        # least flash the taskbar so the user sees the app wants attention.
        # FLASHW_ALL | FLASHW_TIMERNOFG = flash caption + tray until fg, then
        # stop.
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(window.winId())
            FLASHW_ALL = 0x00000003
            FLASHW_TIMERNOFG = 0x0000000C

            class FLASHWINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT),
                    ("hwnd", wintypes.HWND),
                    ("dwFlags", wintypes.DWORD),
                    ("uCount", wintypes.UINT),
                    ("dwTimeout", wintypes.DWORD),
                ]

            fwi = FLASHWINFO(
                cbSize=ctypes.sizeof(FLASHWINFO),
                hwnd=hwnd,
                dwFlags=FLASHW_ALL | FLASHW_TIMERNOFG,
                uCount=3,
                dwTimeout=0,
            )
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(fwi))
        except Exception as exc:  # pragma: no cover
            _log.debug("FlashWindowEx fallback failed: %s", exc)
