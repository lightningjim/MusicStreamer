import os
import shutil
import subprocess
import tempfile
import time
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib
from musicstreamer.models import Station
from musicstreamer.constants import BUFFER_DURATION_S, BUFFER_SIZE_BYTES, COOKIES_PATH


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
        self._pipeline.set_property("buffer-duration", BUFFER_DURATION_S * Gst.SECOND)
        self._pipeline.set_property("buffer-size", BUFFER_SIZE_BYTES)
        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self._on_gst_error)
        bus.connect("message::tag", self._on_gst_tag)
        self._yt_proc = None
        self._yt_cookie_tmp = None
        self._on_title = None
        self._volume = 1.0
        # Clean up stale temp cookie files from previous crashed sessions
        import glob
        for stale in glob.glob(os.path.join(tempfile.gettempdir(), "ms_cookies_*.txt")):
            try:
                os.unlink(stale)
            except OSError:
                pass

    def set_volume(self, value: float):
        clamped = max(0.0, min(1.0, value))
        self._volume = clamped
        self._pipeline.set_property("volume", clamped)

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
        url = ""
        if station.streams:
            url = (station.streams[0].url or "").strip()
        if not url:
            on_title("(no streams configured)")
            return
        if "youtube.com" in url or "youtu.be" in url:
            self._play_youtube(url, station.name, on_title)
        else:
            self._stop_yt_proc()
            self._set_uri(url, station.name, on_title)

    def pause(self):
        """Stop audio output without clearing station context (D-04)."""
        self._on_title = None
        self._stop_yt_proc()
        self._pipeline.set_state(Gst.State.NULL)

    def stop(self):
        self._on_title = None
        self._stop_yt_proc()
        self._pipeline.set_state(Gst.State.NULL)

    def _cleanup_cookie_tmp(self):
        if self._yt_cookie_tmp and os.path.exists(self._yt_cookie_tmp):
            os.unlink(self._yt_cookie_tmp)
        self._yt_cookie_tmp = None

    def _stop_yt_proc(self):
        if self._yt_proc:
            if self._yt_proc.poll() is None:
                self._yt_proc.terminate()
            self._yt_proc = None
        self._cleanup_cookie_tmp()

    def _play_youtube(self, url: str, fallback_name: str, on_title: callable):
        self._stop_yt_proc()
        self._pipeline.set_state(Gst.State.NULL)
        # mpv handles yt-dlp extraction, auth, and HLS internally
        env = os.environ.copy()
        local_bin = os.path.expanduser("~/.local/bin")
        if local_bin not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
        cmd = ["mpv", "--no-video", "--really-quiet", f"--volume={int(self._volume * 100)}"]
        ytdl_path = shutil.which("yt-dlp", path=env.get("PATH"))
        if ytdl_path:
            cmd.append(f"--script-opts=ytdl_hook-ytdl_path={ytdl_path}")
        self._yt_cookie_tmp = None
        if os.path.exists(COOKIES_PATH):
            try:
                fd, self._yt_cookie_tmp = tempfile.mkstemp(suffix=".txt", prefix="ms_cookies_")
                os.close(fd)
                shutil.copy2(COOKIES_PATH, self._yt_cookie_tmp)
                cmd.append(f"--ytdl-raw-options=cookies={self._yt_cookie_tmp}")
            except OSError:
                self._yt_cookie_tmp = None
        cmd.append(url)
        self._yt_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=env,
        )
        on_title(fallback_name)
        # D-05: retry without cookies if mpv exits immediately (corrupted cookies)
        time.sleep(2)
        if self._yt_cookie_tmp and self._yt_proc.poll() is not None:
            import sys
            print("mpv exited immediately with cookies, retrying without", file=sys.stderr)
            self._cleanup_cookie_tmp()
            cmd_no_cookies = [a for a in cmd if not a.startswith("--ytdl-raw-options=cookies=")]
            self._yt_proc = subprocess.Popen(
                cmd_no_cookies,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env,
            )

    def _set_uri(self, uri: str, title: str, on_title: callable):
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.set_property("uri", uri)
        self._pipeline.set_state(Gst.State.PLAYING)
