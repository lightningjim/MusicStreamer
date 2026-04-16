"""Linux MPRIS2 media-keys backend built on PySide6.QtDBus (Phase 41, MEDIA-02/05).

Registers ``org.mpris.MediaPlayer2.musicstreamer`` on the D-Bus session bus and
exposes two QDBusAbstractAdaptor subclasses at ``/org/mpris/MediaPlayer2``:

  _MprisRootAdaptor   — org.mpris.MediaPlayer2
  _MprisPlayerAdaptor — org.mpris.MediaPlayer2.Player

org.freedesktop.DBus.Properties is handled implicitly by QtDBus when
``@Property(...)`` decorators are declared on the adaptors. PropertiesChanged
signals are emitted manually via QDBusMessage.createSignal() on every
publish_metadata / set_playback_state call.

PySide6 ClassInfo idiom (resolved during Plan 02 implementation):
  ``@ClassInfo({"D-Bus Interface": "org.mpris.MediaPlayer2"})``
  from PySide6.QtCore import ClassInfo

  This works with QDBusAbstractAdaptor subclasses in PySide6 6.11.  The
  ClassInfo decorator accepts a plain dict and injects the key/value pair as
  Q_CLASSINFO metadata, which QtDBus reads to identify the interface name.
  Verified via smoke test:
    python -c "from PySide6.QtCore import ClassInfo; ..."
  See also: https://doc.qt.io/qtforpython-6/PySide6/QtDBus/QDBusAbstractAdaptor.html

Construction failure modes:
  - sessionBus().isConnected() == False  → raise RuntimeError
  - registerObject() fails               → raise RuntimeError
  - registerService() fails              → raise RuntimeError
  The Plan 01 factory (media_keys/__init__.py) wraps construction in
  try/except and falls back to NoOpMediaKeysBackend (D-06).
"""
from __future__ import annotations

import logging
from typing import Literal

from PySide6.QtCore import ClassInfo, Property, QMetaType, QObject, Slot
from PySide6.QtDBus import (
    QDBusAbstractAdaptor,
    QDBusArgument,
    QDBusConnection,
    QDBusMessage,
    QDBusObjectPath,
)
from PySide6.QtGui import QPixmap

from musicstreamer.media_keys._art_cache import write_cover_png
from musicstreamer.media_keys.base import MediaKeysBackend
from musicstreamer.models import Station

_log = logging.getLogger(__name__)

OBJECT_PATH = "/org/mpris/MediaPlayer2"
SERVICE_NAME = "org.mpris.MediaPlayer2.musicstreamer"
IFACE_ROOT = "org.mpris.MediaPlayer2"
IFACE_PLAYER = "org.mpris.MediaPlayer2.Player"

# MPRIS playback-status strings (capitalised per spec)
_STATE_MAP: dict[str, str] = {
    "playing": "Playing",
    "paused": "Paused",
    "stopped": "Stopped",
}


@ClassInfo({"D-Bus Interface": IFACE_ROOT})
class _MprisRootAdaptor(QDBusAbstractAdaptor):
    """Exposes the org.mpris.MediaPlayer2 interface."""

    def __init__(self, backend: "LinuxMprisBackend") -> None:
        super().__init__(backend)
        self.setAutoRelaySignals(True)
        self._backend = backend

    # ------------------------------------------------------------------ slots
    @Slot()
    def Raise(self) -> None:
        """No-op — CanRaise=false (deferred to future phase)."""

    @Slot()
    def Quit(self) -> None:
        """No-op — CanQuit=false."""

    # -------------------------------------------------------------- properties
    @Property(str)
    def Identity(self) -> str:
        return "MusicStreamer"

    @Property(bool)
    def CanRaise(self) -> bool:
        return False

    @Property(bool)
    def CanQuit(self) -> bool:
        return False

    @Property(bool)
    def HasTrackList(self) -> bool:
        return False

    @Property(str)
    def DesktopEntry(self) -> str:
        return "org.example.MusicStreamer"

    @Property("QStringList")
    def SupportedUriSchemes(self) -> list[str]:
        return ["http", "https"]

    @Property("QStringList")
    def SupportedMimeTypes(self) -> list[str]:
        return ["audio/mpeg", "audio/ogg", "audio/aac"]


@ClassInfo({"D-Bus Interface": IFACE_PLAYER})
class _MprisPlayerAdaptor(QDBusAbstractAdaptor):
    """Exposes the org.mpris.MediaPlayer2.Player interface."""

    def __init__(self, backend: "LinuxMprisBackend") -> None:
        super().__init__(backend)
        self.setAutoRelaySignals(True)
        self._backend = backend

    # ------------------------------------------------------------------ slots
    @Slot()
    def PlayPause(self) -> None:
        self._backend.play_pause_requested.emit()

    @Slot()
    def Play(self) -> None:
        self._backend.play_pause_requested.emit()

    @Slot()
    def Pause(self) -> None:
        self._backend.play_pause_requested.emit()

    @Slot()
    def Stop(self) -> None:
        self._backend.stop_requested.emit()

    @Slot()
    def Next(self) -> None:
        """No-op — CanGoNext=false (no queue concept in v2.0)."""
        self._backend.next_requested.emit()

    @Slot()
    def Previous(self) -> None:
        """No-op — CanGoPrevious=false."""
        self._backend.previous_requested.emit()

    # -------------------------------------------------------------- properties
    @Property(str)
    def PlaybackStatus(self) -> str:
        return _STATE_MAP.get(self._backend._state, "Stopped")

    @Property(str)
    def LoopStatus(self) -> str:
        return "None"

    @Property(float)
    def Rate(self) -> float:
        return 1.0

    @Property(float)
    def MinimumRate(self) -> float:
        return 1.0

    @Property(float)
    def MaximumRate(self) -> float:
        return 1.0

    @Property(bool)
    def Shuffle(self) -> bool:
        return False

    @Property(float)
    def Volume(self) -> float:
        return 1.0

    @Property("qlonglong")
    def Position(self) -> int:
        return 0

    @Property(bool)
    def CanGoNext(self) -> bool:
        return False

    @Property(bool)
    def CanGoPrevious(self) -> bool:
        return False

    @Property(bool)
    def CanSeek(self) -> bool:
        return False

    @Property(bool)
    def CanControl(self) -> bool:
        return True

    @Property(bool)
    def CanPlay(self) -> bool:
        return self._backend._station is not None

    @Property(bool)
    def CanPause(self) -> bool:
        return self._backend._station is not None

    @Property("QVariantMap")
    def Metadata(self) -> dict:
        return self._backend._build_metadata_dict()


class LinuxMprisBackend(MediaKeysBackend):
    """Linux MPRIS2 backend using PySide6.QtDBus + QDBusAbstractAdaptor.

    Registers ``org.mpris.MediaPlayer2.musicstreamer`` at
    ``/org/mpris/MediaPlayer2`` on the D-Bus session bus.

    Raises RuntimeError (not catches) if D-Bus is unavailable or
    registration fails — the Plan 01 factory degrades to NoOp (D-06).
    """

    def __init__(self, player, repo, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = player
        self._repo = repo

        # Internal state
        self._state: Literal["playing", "paused", "stopped"] = "stopped"
        self._station: Station | None = None
        self._title: str = ""
        self._art_url: str = ""

        # Create adaptors (parented to self — QtDBus picks them up)
        self._root_adaptor = _MprisRootAdaptor(self)
        self._player_adaptor = _MprisPlayerAdaptor(self)

        # D-Bus registration
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            raise RuntimeError("D-Bus session bus not connected")

        ok = bus.registerObject(
            OBJECT_PATH,
            self,
            QDBusConnection.RegisterOption.ExportAdaptors,
        )
        if not ok:
            raise RuntimeError(
                f"registerObject failed: {bus.lastError().message()}"
            )

        ok = bus.registerService(SERVICE_NAME)
        if not ok:
            raise RuntimeError(
                f"registerService failed: {bus.lastError().message()}"
            )

        self._bus = bus
        _log.debug("MPRIS2 backend registered as %s", SERVICE_NAME)

    # ----------------------------------------------------------------- public
    def publish_metadata(
        self,
        station: Station | None,
        title: str,
        cover_pixmap: QPixmap | None,
    ) -> None:
        """Update station/title/art and emit PropertiesChanged on Player interface."""
        self._station = station
        self._title = title or ""

        if cover_pixmap is None or station is None:
            self._art_url = ""
        else:
            path = write_cover_png(cover_pixmap, station.id)
            self._art_url = f"file://{path}" if path else ""

        self._emit_properties_changed({
            "Metadata": self._build_metadata_dict(),
            "CanPlay": station is not None,
            "CanPause": station is not None,
        })

    def _apply_playback_state(
        self, state: Literal["playing", "paused", "stopped"]
    ) -> None:
        """Called by base class after Literal validation; update state and notify."""
        self._state = state
        self._emit_properties_changed({
            "PlaybackStatus": _STATE_MAP[state],
        })

    def shutdown(self) -> None:
        """Unregister from D-Bus. Idempotent — safe to call multiple times."""
        try:
            bus = QDBusConnection.sessionBus()
            bus.unregisterObject(OBJECT_PATH)
            bus.unregisterService(SERVICE_NAME)
        except Exception:
            pass  # ignore errors at shutdown

    # --------------------------------------------------------------- internal
    def _build_metadata_dict(self) -> dict:
        """Build the MPRIS2 Metadata a{sv} dict for the current state."""
        if self._station is None:
            return {
                "mpris:trackid": QDBusObjectPath(
                    "/org/mpris/MediaPlayer2/NoTrack"
                )
            }

        meta: dict = {
            "mpris:trackid": QDBusObjectPath(
                f"/org/mpris/MediaPlayer2/Track/{self._station.id}"
            ),
            "xesam:title": self._title or self._station.name,
            "xesam:artist": [self._station.name],
        }
        if self._art_url:
            meta["mpris:artUrl"] = self._art_url
        return meta

    def _emit_properties_changed(
        self,
        changed: dict,
        iface: str = IFACE_PLAYER,
    ) -> None:
        """Send org.freedesktop.DBus.Properties.PropertiesChanged signal."""
        msg = QDBusMessage.createSignal(
            OBJECT_PATH,
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
        )
        # invalidated_properties must be typed 'as', not 'av'.
        # Python's [] → 'av' in PySide6; use QDBusArgument to force 'as'.
        invalidated = QDBusArgument()
        invalidated.beginArray(int(QMetaType.Type.QString))
        invalidated.endArray()
        msg.setArguments([iface, changed, invalidated])
        self._bus.send(msg)
