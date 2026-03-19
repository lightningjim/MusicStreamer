import subprocess
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib
from musicstreamer.models import Station


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
        self._yt_proc = None

    def _on_gst_error(self, bus, msg):
        err, debug = msg.parse_error()
        print(f"GStreamer ERROR: {err}\n  debug: {debug}")

    def play(self, station: Station, on_title: callable):
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
        on_title(title)
