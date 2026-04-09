import os
import shutil
import subprocess
import tempfile
import threading
import time
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib
from musicstreamer.models import Station, StationStream
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
        # Failover state
        self._streams_queue: list = []
        self._failover_timer_id: int | None = None
        self._yt_poll_timer_id: int | None = None
        self._on_failover = None
        self._current_stream: StationStream | None = None
        self._current_station_name: str = ""
        self._is_first_attempt: bool = True
        self._twitch_resolve_attempts: int = 0
        self._on_offline = None
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
        self._cancel_failover_timer()
        if self._current_stream and "twitch.tv" in self._current_stream.url:
            if self._twitch_resolve_attempts < 1:
                self._twitch_resolve_attempts += 1
                self._play_twitch(self._current_stream.url)
                return
        self._try_next_stream()

    def _on_gst_tag(self, bus, msg):
        taglist = msg.parse_tag()
        found, value = taglist.get_string(Gst.TAG_TITLE)
        # Cancel the failover timer — audio data arrived, stream is working
        self._cancel_failover_timer()
        if not found:
            return
        title = _fix_icy_encoding(value)
        if self._on_title:
            GLib.idle_add(self._on_title, title)

    def _cancel_failover_timer(self):
        """Cancel pending failover timeout and YouTube poll timer."""
        if self._failover_timer_id is not None:
            GLib.source_remove(self._failover_timer_id)
            self._failover_timer_id = None
        if self._yt_poll_timer_id is not None:
            GLib.source_remove(self._yt_poll_timer_id)
            self._yt_poll_timer_id = None

    def _on_timeout_cb(self) -> bool:
        """Failover timeout: no audio arrived within BUFFER_DURATION_S seconds."""
        self._failover_timer_id = None
        self._try_next_stream()
        return False  # Do not repeat

    def _try_next_stream(self):
        """Pop next stream from queue and attempt playback. On empty queue, call on_failover(None)."""
        self._pipeline.set_state(Gst.State.NULL)
        if not self._streams_queue:
            # All streams exhausted
            if self._on_failover:
                GLib.idle_add(self._on_failover, None)
            return
        stream = self._streams_queue.pop(0)
        self._current_stream = stream
        # Notify about failover attempt (not on first play)
        if not self._is_first_attempt and self._on_failover:
            GLib.idle_add(self._on_failover, stream)
        self._is_first_attempt = False
        url = stream.url.strip()
        if "youtube.com" in url or "youtu.be" in url:
            self._play_youtube(url, self._current_station_name, self._on_title)
        elif "twitch.tv" in url:
            self._play_twitch(url)
        else:
            self._stop_yt_proc()
            self._set_uri(url, self._current_station_name, self._on_title)
        # Arm the failover timeout (not for YouTube or Twitch — they arm their own timing)
        if "youtube.com" not in url and "youtu.be" not in url and "twitch.tv" not in url:
            self._failover_timer_id = GLib.timeout_add(
                BUFFER_DURATION_S * 1000, self._on_timeout_cb
            )

    def play(self, station: Station, on_title: callable,
             preferred_quality: str = "",
             on_failover: callable = None,
             on_offline: callable = None):
        # Cancel any in-progress failover from previous play
        self._cancel_failover_timer()
        self._streams_queue = []
        self._on_title = on_title
        self._on_failover = on_failover
        self._on_offline = on_offline
        self._current_station_name = station.name
        self._is_first_attempt = True
        self._twitch_resolve_attempts = 0

        if not station.streams:
            on_title("(no streams configured)")
            return

        # Build ordered stream queue: preferred quality first, then rest in position order
        streams_by_position = sorted(station.streams, key=lambda s: s.position)
        preferred = None
        if preferred_quality:
            preferred = next((s for s in streams_by_position if s.quality == preferred_quality), None)

        if preferred:
            queue = [preferred] + [s for s in streams_by_position if s is not preferred]
        else:
            queue = list(streams_by_position)

        self._streams_queue = queue
        self._try_next_stream()

    def play_stream(self, stream: StationStream, on_title: callable,
                    on_failover: callable = None,
                    on_offline: callable = None):
        """Manually play a specific stream, bypassing the failover queue (D-08)."""
        self._cancel_failover_timer()
        self._on_title = on_title
        self._on_failover = on_failover
        self._on_offline = on_offline
        self._streams_queue = [stream]
        self._is_first_attempt = True
        self._try_next_stream()

    def pause(self):
        """Stop audio output without clearing station context (D-04)."""
        self._cancel_failover_timer()
        self._streams_queue = []
        self._on_title = None
        self._stop_yt_proc()
        self._pipeline.set_state(Gst.State.NULL)

    def stop(self):
        self._cancel_failover_timer()
        self._streams_queue = []
        self._on_failover = None
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

    def _yt_poll_cb(self) -> bool:
        """Poll the YouTube mpv process for failure. Triggers failover if process exited non-zero."""
        if self._yt_proc is None:
            self._yt_poll_timer_id = None
            return False
        exit_code = self._yt_proc.poll()
        if exit_code is not None and exit_code != 0:
            self._yt_poll_timer_id = None
            self._try_next_stream()
            return False
        if exit_code is not None:
            # Exited cleanly (exit 0) — not a failure
            self._yt_poll_timer_id = None
            return False
        return True  # Still running, keep polling

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
        if on_title:
            on_title(fallback_name)
        # D-05: retry without cookies if mpv exits immediately (corrupted cookies)
        # Use a one-shot timer to avoid blocking the GLib main thread.
        def _check_cookie_retry():
            if self._yt_cookie_tmp and self._yt_proc and self._yt_proc.poll() is not None:
                import sys
                print("mpv exited immediately with cookies, retrying without", file=sys.stderr)
                self._cleanup_cookie_tmp()
                cmd_no_cookies = [a for a in cmd if not a.startswith("--ytdl-raw-options=cookies=")]
                self._yt_proc = subprocess.Popen(
                    cmd_no_cookies,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env=env,
                )
            return False  # one-shot
        GLib.timeout_add(2000, _check_cookie_retry)
        # Arm YouTube poll timer to detect process failure (BUFFER_DURATION_S timeout)
        # Poll every 1000ms; GLib.timeout_add with return True repeats
        self._yt_poll_timer_id = GLib.timeout_add(1000, self._yt_poll_cb)

    def _set_uri(self, uri: str, title: str, on_title: callable):
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.set_property("uri", uri)
        self._pipeline.set_state(Gst.State.PLAYING)

    def _play_twitch(self, url: str):
        """Resolve Twitch URL via streamlink, then play HLS URI via GStreamer."""
        self._pipeline.set_state(Gst.State.NULL)
        env = os.environ.copy()
        local_bin = os.path.expanduser("~/.local/bin")
        if local_bin not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")

        def _resolve():
            result = subprocess.run(
                ["streamlink", "--stream-url", url, "best"],
                capture_output=True, text=True, env=env,
            )
            resolved = result.stdout.strip()
            output = result.stdout + result.stderr
            if result.returncode == 0 and resolved.startswith("http"):
                GLib.idle_add(self._on_twitch_resolved, resolved)
            elif "No playable streams found" in output:
                GLib.idle_add(self._on_twitch_offline, url)
            else:
                GLib.idle_add(self._on_twitch_error)

        threading.Thread(target=_resolve, daemon=True).start()

    def _on_twitch_resolved(self, resolved_url: str) -> bool:
        self._set_uri(resolved_url, self._current_station_name, self._on_title)
        return False

    def _on_twitch_offline(self, url: str) -> bool:
        channel = url.rstrip("/").split("/")[-1]
        if self._on_offline:
            self._on_offline(channel)
        return False

    def _on_twitch_error(self) -> bool:
        self._try_next_stream()
        return False
