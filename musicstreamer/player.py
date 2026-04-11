"""GStreamer player backend -- QObject + Qt signals (Phase 35 / PORT-01, PORT-02, PORT-09).

Thread model:
- Player lives on the thread that constructed it (the Qt main thread under
  QCoreApplication.exec()). All QTimer objects, all signal connections, and
  the pipeline state-changes happen on that thread.
- GStreamer bus signal watches (message::error, message::tag) are dispatched
  by a GstBusLoopThread daemon thread running GLib.MainLoop. Handlers run on
  THAT thread and emit Qt signals -- cross-thread emission is auto-queued.
- Twitch resolver runs on an ad-hoc threading.Thread worker because it makes
  blocking HTTP calls; it emits Qt signals when done.

Spike branch (per .planning/phases/35-backend-isolation/35-SPIKE-MPV.md):
- Decision = KEEP_MPV. _play_youtube retains the mpv subprocess launcher
  because yt_dlp library + cookies fails on YouTube live streams (case c).
- All timers (failover, YouTube poll, cookie-retry) use QTimer instead of
  any GLib timer source. Subprocess launches route through
  musicstreamer._popen to pre-stage the Windows port (PKG-03).
"""
from __future__ import annotations

import glob as _glob
import os
import shutil
import tempfile
import threading
import time

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
from PySide6.QtCore import QObject, Qt, QTimer, Signal

from musicstreamer import paths
from musicstreamer._popen import popen as _popen
from musicstreamer.constants import BUFFER_DURATION_S, BUFFER_SIZE_BYTES, YT_MIN_WAIT_S
from musicstreamer.gst_bus_bridge import GstBusLoopThread
from musicstreamer.models import Station, StationStream


# Module-level bus bridge -- one per process. Started lazily on first Player().
_BUS_BRIDGE: GstBusLoopThread | None = None


def _ensure_bus_bridge() -> GstBusLoopThread:
    global _BUS_BRIDGE
    if _BUS_BRIDGE is None:
        _BUS_BRIDGE = GstBusLoopThread()
        _BUS_BRIDGE.start()
    return _BUS_BRIDGE


def _fix_icy_encoding(s: str) -> str:
    """Re-encode latin-1 mojibake back to proper UTF-8."""
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


class Player(QObject):
    # Class-level Signals (Pitfall 4 -- MUST be at class scope, not instance)
    title_changed   = Signal(str)       # ICY title (after encoding fix)
    failover        = Signal(object)    # StationStream | None
    offline         = Signal(str)       # Twitch channel name
    twitch_resolved = Signal(str)       # internal: resolved HLS URL -- queued back to main thread
    playback_error  = Signal(str)       # GStreamer error text
    elapsed_updated = Signal(int)       # seconds since playback start (Phase 30 reserved)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Ensure the bus-loop thread is running BEFORE the bus is wired
        _ensure_bus_bridge()

        self._pipeline = Gst.ElementFactory.make("playbin3", "player")
        self._pipeline.set_property(
            "video-sink", Gst.ElementFactory.make("fakesink", "fake-video")
        )
        audio_sink = Gst.ElementFactory.make("pulsesink", "audio-output")
        if audio_sink:
            self._pipeline.set_property("audio-sink", audio_sink)
        self._pipeline.set_property("buffer-duration", BUFFER_DURATION_S * Gst.SECOND)
        self._pipeline.set_property("buffer-size", BUFFER_SIZE_BYTES)

        # D-07 bus wiring -- sync emission MUST be enabled before add_signal_watch.
        # Order is grep-verified by the PORT-02 acceptance gate.
        bus = self._pipeline.get_bus()
        bus.enable_sync_message_emission()  # D-07 literal -- exactly 1 call in player.py
        bus.add_signal_watch()              # async watch, dispatched by bridge thread
        bus.connect("message::error", self._on_gst_error)  # async handler
        bus.connect("message::tag",   self._on_gst_tag)    # async handler
        # NOTE: no sync-message handler is registered -- it would stall the
        # GStreamer streaming thread (Pitfall 5). Both handlers above run on
        # the GstBusLoopThread daemon and may only emit Qt signals.

        # QTimer objects -- constructed on the main thread (Pitfall 2)
        self._failover_timer = QTimer(self)
        self._failover_timer.setSingleShot(True)
        self._failover_timer.timeout.connect(self._on_timeout)

        self._yt_poll_timer = QTimer(self)
        self._yt_poll_timer.setInterval(1000)
        self._yt_poll_timer.timeout.connect(self._yt_poll_cb)

        # Internal: twitch_resolved is emitted from a worker thread; queued
        # connection marshals the slot call to this (main) thread.
        self.twitch_resolved.connect(
            self._on_twitch_resolved, Qt.ConnectionType.QueuedConnection
        )

        # Legacy callback shims (set via play/play_stream) -- kept so the
        # current GTK main_window.py works unchanged this phase.
        self._on_title_cb = None
        self._on_failover_cb = None
        self._on_offline_cb = None

        # Runtime state -- same fields as the pre-rewrite player.py
        self._volume: float = 1.0
        self._streams_queue: list = []
        self._current_stream: StationStream | None = None
        self._current_station_name: str = ""
        self._is_first_attempt: bool = True
        self._yt_attempt_start_ts: float | None = None
        self._twitch_resolve_attempts: int = 0
        self._yt_proc = None
        self._yt_cookie_tmp: str | None = None

        # Clean up any stale cookie temp files from previous crashed sessions
        for stale in _glob.glob(os.path.join(tempfile.gettempdir(), "ms_cookies_*.txt")):
            try:
                os.unlink(stale)
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    # Public API (legacy callback shims preserved for main_window.py)
    # ------------------------------------------------------------------ #

    @property
    def current_stream(self):
        return self._current_stream

    def set_volume(self, value: float) -> None:
        self._volume = max(0.0, min(1.0, value))
        self._pipeline.set_property("volume", self._volume)

    def play(self, station: Station, on_title=None, preferred_quality: str = "",
             on_failover=None, on_offline=None) -> None:
        # Cancel any in-progress failover from previous play
        self._cancel_timers()
        self._streams_queue = []
        self._install_legacy_callbacks(on_title, on_failover, on_offline)
        self._current_station_name = station.name
        self._is_first_attempt = True
        self._twitch_resolve_attempts = 0

        if not station.streams:
            self.title_changed.emit("(no streams configured)")
            return

        # Build ordered stream queue: preferred quality first, then rest in position order
        streams_by_position = sorted(station.streams, key=lambda s: s.position)
        preferred = None
        if preferred_quality:
            preferred = next(
                (s for s in streams_by_position if s.quality == preferred_quality),
                None,
            )

        if preferred:
            queue = [preferred] + [s for s in streams_by_position if s is not preferred]
        else:
            queue = list(streams_by_position)

        self._streams_queue = queue
        self._try_next_stream()

    def play_stream(self, stream: StationStream, on_title=None,
                    on_failover=None, on_offline=None) -> None:
        """Manually play a specific stream, bypassing the failover queue (D-08)."""
        self._cancel_timers()
        self._install_legacy_callbacks(on_title, on_failover, on_offline)
        self._current_station_name = ""
        self._streams_queue = [stream]
        self._is_first_attempt = True
        self._try_next_stream()

    def pause(self) -> None:
        """Stop audio output without clearing station context (D-04)."""
        self._cancel_timers()
        self._streams_queue = []
        self._stop_yt_proc()
        self._pipeline.set_state(Gst.State.NULL)

    def stop(self) -> None:
        self._cancel_timers()
        self._streams_queue = []
        self._stop_yt_proc()
        self._pipeline.set_state(Gst.State.NULL)

    # ------------------------------------------------------------------ #
    # Legacy callback shim -- lets main_window.py keep its old signature
    # ------------------------------------------------------------------ #

    def _install_legacy_callbacks(self, on_title, on_failover, on_offline) -> None:
        # Disconnect any previous shims before wiring new ones
        if self._on_title_cb is not None:
            try:
                self.title_changed.disconnect(self._on_title_cb)
            except (RuntimeError, TypeError):
                pass
        if self._on_failover_cb is not None:
            try:
                self.failover.disconnect(self._on_failover_cb)
            except (RuntimeError, TypeError):
                pass
        if self._on_offline_cb is not None:
            try:
                self.offline.disconnect(self._on_offline_cb)
            except (RuntimeError, TypeError):
                pass

        self._on_title_cb = on_title
        self._on_failover_cb = on_failover
        self._on_offline_cb = on_offline

        if on_title is not None:
            self.title_changed.connect(on_title)
        if on_failover is not None:
            self.failover.connect(on_failover)
        if on_offline is not None:
            self.offline.connect(on_offline)

    # ------------------------------------------------------------------ #
    # GStreamer bus handlers -- run on the GLib bus-loop thread.
    # They MUST NOT touch QTimer or any Qt-affined state directly; they
    # only emit Qt signals, which are auto-queued cross-thread.
    # ------------------------------------------------------------------ #

    def _on_gst_error(self, bus, msg) -> None:
        err, debug = msg.parse_error()
        self.playback_error.emit(f"{err} | {debug}")
        # Route recovery through a queued slot so QTimer work happens on the
        # main thread, not the bus-loop thread.
        QTimer.singleShot(0, self._handle_gst_error_recovery)

    def _handle_gst_error_recovery(self) -> None:
        self._cancel_timers()
        if self._current_stream and "twitch.tv" in self._current_stream.url:
            if self._twitch_resolve_attempts < 1:
                self._twitch_resolve_attempts += 1
                self._play_twitch(self._current_stream.url)
                return
        self._try_next_stream()

    def _on_gst_tag(self, bus, msg) -> None:
        taglist = msg.parse_tag()
        found, value = taglist.get_string(Gst.TAG_TITLE)
        # Cancel the failover timer -- audio data arrived, stream is working.
        # QTimer.stop() can only be called on the owning thread, so route it
        # through a zero-delay singleShot to marshal onto the main thread.
        QTimer.singleShot(0, self._cancel_timers)
        if not found:
            return
        title = _fix_icy_encoding(value)
        self.title_changed.emit(title)  # auto-queued cross-thread to main

    # ------------------------------------------------------------------ #
    # Timer helpers -- main-thread only
    # ------------------------------------------------------------------ #

    def _cancel_timers(self) -> None:
        """Cancel pending failover timeout and YouTube poll timer."""
        self._failover_timer.stop()
        self._yt_poll_timer.stop()
        self._yt_attempt_start_ts = None

    def _on_timeout(self) -> None:
        """Failover timeout: no audio arrived within BUFFER_DURATION_S seconds."""
        self._try_next_stream()

    # ------------------------------------------------------------------ #
    # Failover queue
    # ------------------------------------------------------------------ #

    def _try_next_stream(self) -> None:
        """Pop next stream from queue and attempt playback. On empty queue,
        emit failover(None)."""
        self._pipeline.set_state(Gst.State.NULL)
        if not self._streams_queue:
            # All streams exhausted
            self.failover.emit(None)
            return
        stream = self._streams_queue.pop(0)
        self._current_stream = stream
        # Notify about failover attempt (not on first play)
        if not self._is_first_attempt:
            self.failover.emit(stream)
        self._is_first_attempt = False
        url = stream.url.strip()
        if "youtube.com" in url or "youtu.be" in url:
            self._play_youtube(url)
        elif "twitch.tv" in url:
            self._play_twitch(url)
        else:
            self._stop_yt_proc()
            self._set_uri(url)
            # Arm failover timeout for direct GStreamer URIs
            self._failover_timer.start(BUFFER_DURATION_S * 1000)

    def _set_uri(self, uri: str) -> None:
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.set_property("uri", uri)
        self._pipeline.set_state(Gst.State.PLAYING)

    # ------------------------------------------------------------------ #
    # YouTube -- KEEP_MPV branch (per 35-SPIKE-MPV.md)
    # ------------------------------------------------------------------ #

    def _open_mpv_log(self, url: str, phase: str):
        """Open the mpv diagnostic log in append mode and write a header.
        Returns an open file handle (caller closes after Popen inherits it)
        or None if the log cannot be opened."""
        try:
            data_dir = paths.data_dir()
            os.makedirs(data_dir, exist_ok=True)
            log_path = os.path.join(data_dir, "mpv.log")
            fh = open(log_path, "a", buffering=1)
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            fh.write(f"\n===== {ts} [{phase}] {url} =====\n")
            fh.flush()
            return fh
        except OSError:
            return None

    def _play_youtube(self, url: str) -> None:
        """[SPIKE=KEEP_MPV] Launch mpv subprocess (with cookies if available)
        and poll for exit via QTimer. mpv handles yt-dlp extraction, auth, and
        HLS internally. Cookie-retry one-shot is a QTimer.singleShot."""
        self._stop_yt_proc()
        self._pipeline.set_state(Gst.State.NULL)

        env = os.environ.copy()
        local_bin = os.path.expanduser("~/.local/bin")
        if local_bin not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")

        cmd = ["mpv", "--no-video", "--really-quiet", f"--volume={int(self._volume * 100)}"]
        ytdl_path = shutil.which("yt-dlp", path=env.get("PATH"))
        if ytdl_path:
            cmd.append(f"--script-opts=ytdl_hook-ytdl_path={ytdl_path}")

        cookies_src = paths.cookies_path()
        self._yt_cookie_tmp = None
        if os.path.exists(cookies_src):
            try:
                fd, self._yt_cookie_tmp = tempfile.mkstemp(suffix=".txt", prefix="ms_cookies_")
                os.close(fd)
                shutil.copy2(cookies_src, self._yt_cookie_tmp)
                cmd.append(f"--ytdl-raw-options=cookies={self._yt_cookie_tmp}")
            except OSError:
                self._yt_cookie_tmp = None
        cmd.append(url)

        log_fh = self._open_mpv_log(url, "initial")
        self._yt_proc = _popen(
            cmd,
            stdout=log_fh, stderr=log_fh,
            env=env,
        )
        if log_fh is not None:
            log_fh.close()
        self._yt_attempt_start_ts = time.monotonic()

        # Fallback title shows the station name immediately while mpv warms up
        if self._current_station_name:
            self.title_changed.emit(self._current_station_name)

        # D-05: retry without cookies if mpv exits immediately (corrupted cookies).
        # Uses QTimer.singleShot for the one-shot delay (main-thread only).
        retry_state = {"url": url, "cmd": cmd, "env": env}
        QTimer.singleShot(2000, lambda: self._check_cookie_retry(retry_state))

        # Arm YouTube poll timer to detect process failure (1 Hz polling).
        self._yt_poll_timer.start()

    def _check_cookie_retry(self, state: dict) -> None:
        """Run 2s after mpv launch: if mpv exited immediately AND we used a
        cookie file, retry once without cookies (corrupted-cookie recovery)."""
        if not (self._yt_cookie_tmp and self._yt_proc and self._yt_proc.poll() is not None):
            return
        import sys
        print("mpv exited immediately with cookies, retrying without", file=sys.stderr)
        self._cleanup_cookie_tmp()
        cmd_no_cookies = [a for a in state["cmd"] if not a.startswith("--ytdl-raw-options=cookies=")]
        retry_log_fh = self._open_mpv_log(state["url"], "cookie-retry")
        self._yt_proc = _popen(
            cmd_no_cookies,
            stdout=retry_log_fh, stderr=retry_log_fh,
            env=state["env"],
        )
        if retry_log_fh is not None:
            retry_log_fh.close()
        self._yt_attempt_start_ts = time.monotonic()

    def _yt_poll_cb(self) -> None:
        """Poll mpv subprocess for exit. YT_MIN_WAIT_S failover window
        preserved from Phase 33 / FIX-07 / D-01. Called by QTimer on the main
        thread at 1 Hz."""
        if self._yt_proc is None:
            self._yt_poll_timer.stop()
            return
        exit_code = self._yt_proc.poll()
        elapsed = 0.0
        if self._yt_attempt_start_ts is not None:
            elapsed = time.monotonic() - self._yt_attempt_start_ts
        if exit_code is None:
            # Still running. If we've crossed the window, treat as success (D-03).
            if elapsed >= YT_MIN_WAIT_S:
                self._yt_poll_timer.stop()
                self._yt_attempt_start_ts = None
            return  # else keep polling
        # mpv has exited. Defer failover until the window closes (D-01, D-02).
        if elapsed < YT_MIN_WAIT_S:
            return  # keep polling -- sit idle until window elapses
        # Window elapsed AND exited.
        self._yt_poll_timer.stop()
        self._yt_attempt_start_ts = None
        if exit_code != 0:
            self._try_next_stream()

    def _stop_yt_proc(self) -> None:
        if self._yt_proc:
            if self._yt_proc.poll() is None:
                self._yt_proc.terminate()
            self._yt_proc = None
        self._cleanup_cookie_tmp()

    def _cleanup_cookie_tmp(self) -> None:
        if self._yt_cookie_tmp and os.path.exists(self._yt_cookie_tmp):
            os.unlink(self._yt_cookie_tmp)
        self._yt_cookie_tmp = None

    # ------------------------------------------------------------------ #
    # Twitch -- streamlink library API (D-18)
    # ------------------------------------------------------------------ #

    def _play_twitch(self, url: str) -> None:
        """Resolve Twitch URL via streamlink library on a worker thread, then
        set the resolved HLS URL on playbin3 via the queued twitch_resolved
        signal."""
        self._pipeline.set_state(Gst.State.NULL)
        threading.Thread(
            target=self._twitch_resolve_worker, args=(url,), daemon=True
        ).start()

    def _twitch_resolve_worker(self, url: str) -> None:
        from streamlink.session import Streamlink
        from streamlink.exceptions import NoPluginError, PluginError

        session = Streamlink()
        token = ""
        try:
            with open(paths.twitch_token_path()) as fh:
                token = fh.read().strip()
        except OSError:
            pass
        if token:
            # Scope the header to the Twitch plugin only -- NOT global
            # http-header (RESEARCH.md Pitfall 6).
            session.set_plugin_option(
                "twitch", "api-header",
                [("Authorization", f"OAuth {token}")],
            )
        try:
            streams = session.streams(url)
        except NoPluginError:
            self.playback_error.emit("streamlink: no plugin")
            QTimer.singleShot(0, self._try_next_stream)
            return
        except PluginError as e:
            if "No playable streams" in str(e) or "offline" in str(e).lower():
                channel = url.rstrip("/").split("/")[-1]
                self.offline.emit(channel)
                return
            self.playback_error.emit(f"streamlink: {e}")
            QTimer.singleShot(0, self._try_next_stream)
            return
        if not streams or "best" not in streams:
            channel = url.rstrip("/").split("/")[-1]
            self.offline.emit(channel)
            return
        # Success -- queued emission marshals back to main thread
        self.twitch_resolved.emit(streams["best"].url)

    def _on_twitch_resolved(self, resolved_url: str) -> None:
        """Runs on main thread (connected via Qt.QueuedConnection in __init__)."""
        self._set_uri(resolved_url)
        self._failover_timer.start(BUFFER_DURATION_S * 1000)
