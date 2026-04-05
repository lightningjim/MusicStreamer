"""MPRIS2 D-Bus service for MusicStreamer.

Registers org.mpris.MediaPlayer2.MusicStreamer on the session bus so OS media
keys (play/pause, stop) and playerctl can control playback.

All D-Bus method handlers dispatch to the GTK main thread via GLib.idle_add()
to avoid threading issues (T-20-04).
"""
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

# Must be called before any SessionBus() instantiation (Pitfall 1 in RESEARCH.md)
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

MPRIS_IFACE = "org.mpris.MediaPlayer2"
MPRIS_PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
MPRIS_OBJECT_PATH = "/org/mpris/MediaPlayer2"
BUS_NAME = "org.mpris.MediaPlayer2.MusicStreamer"
PROPS_IFACE = "org.freedesktop.DBus.Properties"


class MprisService(dbus.service.Object):
    """MPRIS2 D-Bus service object implementing root and Player interfaces."""

    def __init__(self, window):
        self._window = window
        bus = dbus.SessionBus()
        self._bus_name = dbus.service.BusName(BUS_NAME, bus)
        super().__init__(bus, MPRIS_OBJECT_PATH)

    # ------------------------------------------------------------------ #
    # org.mpris.MediaPlayer2 (root interface)
    # ------------------------------------------------------------------ #

    @dbus.service.method(MPRIS_IFACE, in_signature="", out_signature="")
    def Raise(self):
        """Bring the application window to the foreground."""
        GLib.idle_add(self._window.present)

    @dbus.service.method(MPRIS_IFACE, in_signature="", out_signature="")
    def Quit(self):
        """No-op — CanQuit is False."""
        pass

    # ------------------------------------------------------------------ #
    # org.mpris.MediaPlayer2.Player interface
    # ------------------------------------------------------------------ #

    @dbus.service.method(MPRIS_PLAYER_IFACE, in_signature="", out_signature="")
    def PlayPause(self):
        """Toggle pause/resume — mirrors the in-app pause button."""
        GLib.idle_add(self._window._toggle_pause)

    @dbus.service.method(MPRIS_PLAYER_IFACE, in_signature="", out_signature="")
    def Play(self):
        """Resume if paused; no-op if stopped or already playing."""
        if getattr(self._window, "_paused", False):
            GLib.idle_add(self._window._toggle_pause)

    @dbus.service.method(MPRIS_PLAYER_IFACE, in_signature="", out_signature="")
    def Pause(self):
        """Pause if currently playing; no-op otherwise."""
        status = self._window._playback_status()
        if status == "Playing":
            GLib.idle_add(self._window._toggle_pause)

    @dbus.service.method(MPRIS_PLAYER_IFACE, in_signature="", out_signature="")
    def Stop(self):
        """Stop playback — mirrors the in-app stop button."""
        GLib.idle_add(self._window._stop)

    @dbus.service.method(MPRIS_PLAYER_IFACE, in_signature="", out_signature="")
    def Next(self):
        """No-op — CanGoNext is False (D-09)."""
        pass

    @dbus.service.method(MPRIS_PLAYER_IFACE, in_signature="", out_signature="")
    def Previous(self):
        """No-op — CanGoPrevious is False (D-09)."""
        pass

    # ------------------------------------------------------------------ #
    # org.freedesktop.DBus.Properties interface
    # ------------------------------------------------------------------ #

    @dbus.service.method(PROPS_IFACE, in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        return self._get_all(interface).get(prop, dbus.String(""))

    @dbus.service.method(PROPS_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self._get_all(interface)

    @dbus.service.signal(PROPS_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        """Signal emitted when player properties change."""
        pass

    def emit_properties_changed(self, props: dict):
        """Emit a PropertiesChanged signal for the Player interface."""
        self.PropertiesChanged(
            MPRIS_PLAYER_IFACE,
            props,
            dbus.Array([], signature="s"),
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _get_all(self, interface: str) -> dict:
        if interface == MPRIS_IFACE:
            return self._get_all_root()
        if interface == MPRIS_PLAYER_IFACE:
            return self._get_all_player()
        return {}

    def _get_all_root(self) -> dict:
        return {
            "CanQuit": dbus.Boolean(False),
            "CanRaise": dbus.Boolean(True),
            "HasTrackList": dbus.Boolean(False),
            "Identity": dbus.String("MusicStreamer"),
            "DesktopEntry": dbus.String("org.example.MusicStreamer"),
            "SupportedUriSchemes": dbus.Array(["http", "https"], signature="s"),
            "SupportedMimeTypes": dbus.Array(
                ["audio/mpeg", "audio/ogg", "audio/aac"], signature="s"
            ),
        }

    def _get_all_player(self) -> dict:
        st = self._window._current_station
        return {
            "PlaybackStatus": dbus.String(self._window._playback_status()),
            "LoopStatus": dbus.String("None"),
            "Rate": dbus.Double(1.0),
            "Shuffle": dbus.Boolean(False),
            "Metadata": self._build_metadata(),
            "Volume": dbus.Double(1.0),
            "Position": dbus.Int64(0),
            "MinimumRate": dbus.Double(1.0),
            "MaximumRate": dbus.Double(1.0),
            "CanGoNext": dbus.Boolean(False),
            "CanGoPrevious": dbus.Boolean(False),
            "CanPlay": dbus.Boolean(st is not None),
            "CanPause": dbus.Boolean(st is not None),
            "CanSeek": dbus.Boolean(False),
            "CanControl": dbus.Boolean(True),
        }

    def _build_metadata(self) -> dict:
        st = self._window._current_station
        icy = getattr(self._window, "_last_cover_icy", None) or ""
        if st:
            return dbus.Dictionary(
                {
                    "mpris:trackid": dbus.ObjectPath(
                        "/org/mpris/MediaPlayer2/CurrentTrack"
                    ),
                    "xesam:title": dbus.String(st.name),
                    "xesam:artist": dbus.Array([dbus.String(icy)], signature="s"),
                },
                signature="sv",
            )
        return dbus.Dictionary(
            {"mpris:trackid": dbus.ObjectPath("/org/mpris/MediaPlayer2/NoTrack")},
            signature="sv",
        )
