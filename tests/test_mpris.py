"""Tests for MprisService MPRIS2 D-Bus service — runs without a live D-Bus session."""
import sys
import types
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Build fake dbus and gi.repository.GLib modules BEFORE importing MprisService.
# We do this at module level so all tests share one import.
# ---------------------------------------------------------------------------

def _make_dbus_mocks():
    dbus_mod = types.ModuleType("dbus")

    class _Str(str): pass
    class _Bool(int): pass
    class _Double(float): pass
    class _Int64(int): pass
    class _ObjectPath(str): pass

    def _Array(items=None, signature=None):
        return list(items or [])

    def _Dictionary(d=None, signature=None):
        return dict(d or {})

    dbus_mod.String = _Str
    dbus_mod.Boolean = _Bool
    dbus_mod.Double = _Double
    dbus_mod.Int64 = _Int64
    dbus_mod.ObjectPath = _ObjectPath
    dbus_mod.Array = _Array
    dbus_mod.Dictionary = _Dictionary

    class _DBusException(Exception): pass
    dbus_mod.DBusException = _DBusException

    exceptions_mod = types.ModuleType("dbus.exceptions")
    exceptions_mod.DBusException = _DBusException
    dbus_mod.exceptions = exceptions_mod

    service_mod = types.ModuleType("dbus.service")

    class _BusName:
        def __init__(self, name, bus):
            self.name = name

    service_mod.BusName = _BusName

    class _ServiceObject:
        def __init__(self, bus, path):
            self._bus = bus
            self._path = path

    service_mod.Object = _ServiceObject

    def method(iface, in_signature="", out_signature=""):
        def decorator(fn):
            return fn
        return decorator

    def signal(iface, signature=""):
        def decorator(fn):
            return fn
        return decorator

    service_mod.method = method
    service_mod.signal = signal
    dbus_mod.service = service_mod

    mainloop_mod = types.ModuleType("dbus.mainloop")
    glib_mod = types.ModuleType("dbus.mainloop.glib")
    glib_mod.DBusGMainLoop = MagicMock()
    mainloop_mod.glib = glib_mod
    dbus_mod.mainloop = mainloop_mod

    return dbus_mod, service_mod, mainloop_mod, glib_mod, exceptions_mod


def _make_gi_mocks():
    """Build a fake gi.repository module with a mock GLib."""
    mock_glib = MagicMock()
    mock_glib.idle_add = MagicMock()

    # Build gi.repository fake
    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")
    repo_mod = types.ModuleType("gi.repository")
    repo_mod.GLib = mock_glib
    gi_mod.repository = repo_mod
    return gi_mod, repo_mod, mock_glib


_dbus_mock, _service_mock, _mainloop_mock, _glib_mock, _exc_mock = _make_dbus_mocks()
_gi_mod, _repo_mod, _module_glib = _make_gi_mocks()

_MODULE_PATCHES = {
    "dbus": _dbus_mock,
    "dbus.service": _service_mock,
    "dbus.mainloop": _mainloop_mock,
    "dbus.mainloop.glib": _glib_mock,
    "dbus.exceptions": _exc_mock,
    "gi.repository.GLib": _module_glib,
}

# Remove any stale musicstreamer.mpris import before doing the one-time import
for _mod in list(sys.modules.keys()):
    if _mod.startswith("musicstreamer.mpris"):
        del sys.modules[_mod]

with patch.dict("sys.modules", _MODULE_PATCHES):
    import musicstreamer.mpris as _mpris_mod

# Expose module-level names for test use
MprisService = _mpris_mod.MprisService
MPRIS_IFACE = _mpris_mod.MPRIS_IFACE
MPRIS_PLAYER_IFACE = _mpris_mod.MPRIS_PLAYER_IFACE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_window(paused=False, station=None, icy=None, status="Stopped"):
    w = MagicMock()
    w._paused = paused
    w._current_station = station
    w._last_cover_icy = icy
    w._playback_status.return_value = status
    return w


def _make_service(window=None):
    if window is None:
        window = _make_window()
    svc = MprisService.__new__(MprisService)
    svc._window = window
    return svc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_playpause_dispatches():
    """PlayPause() calls GLib.idle_add with window._toggle_pause."""
    window = _make_window(status="Playing")
    window._current_station = MagicMock(name="station")
    svc = _make_service(window)

    mock_glib = MagicMock()
    with patch.object(_mpris_mod, "GLib", mock_glib):
        svc.PlayPause()

    mock_glib.idle_add.assert_called_once_with(window._toggle_pause)


def test_stop_dispatches():
    """Stop() calls GLib.idle_add with window._stop."""
    window = _make_window(status="Playing")
    svc = _make_service(window)

    mock_glib = MagicMock()
    with patch.object(_mpris_mod, "GLib", mock_glib):
        svc.Stop()

    mock_glib.idle_add.assert_called_once_with(window._stop)


def test_next_noop():
    """Next() does not raise and does not call any window methods."""
    window = _make_window()
    svc = _make_service(window)

    mock_glib = MagicMock()
    with patch.object(_mpris_mod, "GLib", mock_glib):
        svc.Next()

    window._toggle_pause.assert_not_called()
    window._stop.assert_not_called()
    mock_glib.idle_add.assert_not_called()


def test_previous_noop():
    """Previous() does not raise and does not call any window methods."""
    window = _make_window()
    svc = _make_service(window)

    mock_glib = MagicMock()
    with patch.object(_mpris_mod, "GLib", mock_glib):
        svc.Previous()

    window._toggle_pause.assert_not_called()
    window._stop.assert_not_called()
    mock_glib.idle_add.assert_not_called()


def test_getall_player_stopped():
    """GetAll(Player) returns PlaybackStatus=Stopped, CanGoNext/CanGoPrevious=False when no station."""
    window = _make_window(status="Stopped", station=None)
    svc = _make_service(window)

    props = svc.GetAll(MPRIS_PLAYER_IFACE)

    assert str(props["PlaybackStatus"]) == "Stopped"
    assert bool(props["CanGoNext"]) is False
    assert bool(props["CanGoPrevious"]) is False


def test_getall_player_playing():
    """GetAll(Player) returns PlaybackStatus=Playing, CanPlay/CanPause=True when station set."""
    station = MagicMock()
    station.name = "Di.fm"
    window = _make_window(status="Playing", station=station)
    svc = _make_service(window)

    props = svc.GetAll(MPRIS_PLAYER_IFACE)

    assert str(props["PlaybackStatus"]) == "Playing"
    assert bool(props["CanPlay"]) is True
    assert bool(props["CanPause"]) is True


def test_getall_root():
    """GetAll(root) returns Identity=MusicStreamer, CanRaise=True, HasTrackList=False."""
    window = _make_window()
    svc = _make_service(window)

    props = svc.GetAll(MPRIS_IFACE)

    assert str(props["Identity"]) == "MusicStreamer"
    assert bool(props["CanRaise"]) is True
    assert bool(props["HasTrackList"]) is False


def test_build_metadata_with_station():
    """Metadata includes xesam:title with station name and mpris:trackid when station is set."""
    station = MagicMock()
    station.name = "Lofi Girl"
    window = _make_window(station=station, icy="Artist - Song")
    svc = _make_service(window)

    meta = svc._build_metadata()

    assert str(meta["xesam:title"]) == "Lofi Girl"
    assert "mpris:trackid" in meta
    assert "CurrentTrack" in str(meta["mpris:trackid"])


def test_build_metadata_no_station():
    """Metadata has trackid /NoTrack when no station is active."""
    window = _make_window(station=None, icy=None)
    svc = _make_service(window)

    meta = svc._build_metadata()

    assert "NoTrack" in str(meta["mpris:trackid"])


def test_raise_presents_window():
    """Raise() calls window.present via GLib.idle_add."""
    window = _make_window()
    svc = _make_service(window)

    mock_glib = MagicMock()
    with patch.object(_mpris_mod, "GLib", mock_glib):
        svc.Raise()

    mock_glib.idle_add.assert_called_once_with(window.present)
