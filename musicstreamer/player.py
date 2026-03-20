import subprocess
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib
from musicstreamer.models import Station


def _fix_icy_encoding(s: str) -> str:
    """Re-encode latin-1 mojibake back to proper UTF-8."""
    try:
        return s.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


class Player:
    def __init__(self):
        self._pipeline = Gst.ElementFactory.make("playbin3", "player")
        self._pipeline.set_property(
            "video-sink", Gst.ElementFactory.make("fakesink", "fake-video")
        )
        audio_sink = Gst.ElementFactory.make("pulsesink", "audio-output")
        if audio_sink:
            self._pipeline.set_property("audio-sink", audio_sink)
        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self._on_gst_error)
        bus.connect("message::tag", self._on_gst_tag)
        self._yt_proc = None
        self._on_title = None

    def _on_gst_error(self, bus, msg):
        err, debug = msg.parse_error()
        print(f"GStreamer ERROR: {err}\n  debug: {debug}")

    def _on_gst_tag(self, bus, msg):
        taglist = msg.parse_tag()
        found, value = taglist.get_string(Gst.TAG_TITLE)
        if not found:
            return
        title = _fix_icy_encoding(value)
        if self._on_title:
            GLib.idle_add(self._on_title, title)

    def play(self, station: Station, on_title: callable):
        self._on_title = on_title
        url = (station.url or "").strip()
        if not url:
            on_title("(no URL set)")
            return
        if "youtube.com" in url or "youtu.be" in url:
            self._play_youtube(url, station.name, on_title)
        else:
            self._stop_yt_proc()
            self._set_uri(url, station.name, on_title)

    def stop(self):
        self._on_title = None
        self._stop_yt_proc()
        self._pipeline.set_state(Gst.State.NULL)

    def _stop_yt_proc(self):
        if self._yt_proc and self._yt_proc.poll() is None:
            self._yt_proc.terminate()
            self._yt_proc = None

    def _play_youtube(self, url: str, fallback_name: str, on_title: callable):
        self._stop_yt_proc()
        self._pipeline.set_state(Gst.State.NULL)
        # mpv handles yt-dlp extraction, auth, and HLS internally
        self._yt_proc = subprocess.Popen(
            ["mpv", "--no-video", "--really-quiet", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        on_title(fallback_name)

    def _set_uri(self, uri: str, title: str, on_title: callable):
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.set_property("uri", uri)
        self._pipeline.set_state(Gst.State.PLAYING)
