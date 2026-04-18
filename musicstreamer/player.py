"""GStreamer player backend -- QObject + Qt signals (Phase 35 / PORT-01, PORT-02, PORT-09).

Thread model:
- Player lives on the thread that constructed it (the Qt main thread under
  QCoreApplication.exec()). All QTimer objects, all signal connections, and
  the pipeline state-changes happen on that thread.
- GStreamer bus signal watches (message::error, message::tag) are dispatched
  by a GstBusLoopThread daemon thread running GLib.MainLoop. Handlers run on
  THAT thread and emit Qt signals -- cross-thread emission is auto-queued.
- Twitch and YouTube resolvers run on ad-hoc threading.Thread workers because
  they make blocking HTTP calls; they emit Qt signals when done.

YouTube playback (Plan 35-06 -- supersedes the original Phase 35 spike):
- _play_youtube uses yt_dlp.YoutubeDL library with the EJS JS challenge
  solver (extractor_args youtubepot-jsruntime.remote_components=ejs:github)
  to resolve the direct HLS URL, then feeds it to playbin3 via the queued
  youtube_resolved signal. Cookies (if present) are attached via cookiefile.
- Node.js runtime required on PATH for yt-dlp EJS. No external player
  process is launched this phase (see 35-SPIKE-MPV.md "Superseded" section
  and Plan 35-06 for the rationale that replaces the original KEEP branch).
"""
from __future__ import annotations

import os
import threading

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
from PySide6.QtCore import QObject, Qt, QTimer, Signal

from musicstreamer import paths
from musicstreamer.constants import BUFFER_DURATION_S, BUFFER_SIZE_BYTES
from musicstreamer.gst_bus_bridge import GstBusLoopThread
from musicstreamer.models import Station, StationStream
from musicstreamer.stream_ordering import order_streams


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
    title_changed              = Signal(str)     # ICY title (after encoding fix)
    failover                   = Signal(object)  # StationStream | None
    offline                    = Signal(str)     # Twitch channel name
    twitch_resolved            = Signal(str)     # internal: resolved Twitch HLS URL -- queued back to main thread
    youtube_resolved           = Signal(str)     # internal: resolved YouTube HLS URL -- queued back to main thread
    youtube_resolution_failed  = Signal(str)     # internal: yt-dlp error message -- queued back to main thread
    playback_error             = Signal(str)     # GStreamer error text
    elapsed_updated            = Signal(int)     # wall-clock seconds since play began (40.1-06)

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

        # Elapsed-time display (v1.5 parity; v2.0 Qt-port regression fix,
        # Plan 40.1-06). Wall-clock seconds since the user pressed play --
        # does NOT reset on failover (transparent to the user). Main-thread
        # QTimer; emits once per second while the pipeline is intended to
        # be PLAYING. Kept OUT of _cancel_timers so bus-handler failover
        # recovery does not pause the elapsed counter.
        self._elapsed_seconds: int = 0
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._on_elapsed_tick)

        # Internal: twitch_resolved / youtube_resolved / youtube_resolution_failed
        # are emitted from worker threads; queued connections marshal the slot
        # calls to this (main) thread.
        self.twitch_resolved.connect(
            self._on_twitch_resolved, Qt.ConnectionType.QueuedConnection
        )
        self.youtube_resolved.connect(
            self._on_youtube_resolved, Qt.ConnectionType.QueuedConnection
        )
        self.youtube_resolution_failed.connect(
            self._on_youtube_resolution_failed, Qt.ConnectionType.QueuedConnection
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
        self._twitch_resolve_attempts: int = 0
        self._recovery_in_flight: bool = False  # gap-05: coalesce cascading bus errors per URL

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
        self._recovery_in_flight = False
        self._install_legacy_callbacks(on_title, on_failover, on_offline)
        self._current_station_name = station.name
        self._is_first_attempt = True
        self._twitch_resolve_attempts = 0

        if not station.streams:
            self.title_changed.emit("(no streams configured)")
            return

        # Build ordered stream queue: preferred quality first, then rest in order_streams order (Phase 47)
        streams_by_position = order_streams(station.streams)
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
        self._recovery_in_flight = False
        self._is_first_attempt = True
        self._try_next_stream()

    def pause(self) -> None:
        """Stop audio output without clearing station context (D-04)."""
        self._cancel_timers()
        self._elapsed_timer.stop()
        self._streams_queue = []
        self._recovery_in_flight = False
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)

    def stop(self) -> None:
        self._cancel_timers()
        self._elapsed_timer.stop()
        self._elapsed_seconds = 0
        self._streams_queue = []
        self._recovery_in_flight = False
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)

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
        # Gap-05 fix: coalesce cascading bus errors for a single failing URL.
        # playbin3 may emit N errors (source + demuxer + decoder) during
        # pipeline teardown for one broken stream. Without this guard each
        # error would pop the next queue entry, draining the queue in
        # milliseconds and yielding a spurious "Stream exhausted".
        # See .planning/debug/stream-exhausted-premature.md for the trace.
        if self._recovery_in_flight:
            return
        self._recovery_in_flight = True
        self._cancel_timers()
        if self._current_stream and "twitch.tv" in self._current_stream.url:
            if self._twitch_resolve_attempts < 1:
                self._twitch_resolve_attempts += 1
                self._play_twitch(self._current_stream.url)
                # Defer the clear so any already-queued singleShot recoveries
                # for the OLD URL still see the guard set and no-op; errors
                # from the NEW URL (not yet started) will see the cleared
                # guard and trigger a fresh recovery.
                QTimer.singleShot(0, self._clear_recovery_guard)
                return
        self._try_next_stream()
        QTimer.singleShot(0, self._clear_recovery_guard)

    def _clear_recovery_guard(self) -> None:
        """Main-thread slot: release the recovery guard after the current
        failover advance is armed. Scheduled by _handle_gst_error_recovery
        via QTimer.singleShot(0, ...) so it runs after any already-queued
        recovery callbacks from the old URL have drained."""
        self._recovery_in_flight = False

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
        """Cancel pending failover timeout."""
        self._failover_timer.stop()

    def _on_timeout(self) -> None:
        """Failover timeout: no audio arrived within BUFFER_DURATION_S seconds."""
        self._try_next_stream()

    def _on_elapsed_tick(self) -> None:
        """1Hz tick: increment counter and emit elapsed_updated(seconds)."""
        self._elapsed_seconds += 1
        self.elapsed_updated.emit(self._elapsed_seconds)

    # ------------------------------------------------------------------ #
    # Failover queue
    # ------------------------------------------------------------------ #

    def _try_next_stream(self) -> None:
        """Pop next stream from queue and attempt playback. On empty queue,
        emit failover(None)."""
        self._pipeline.set_state(Gst.State.NULL)
        # Wait for NULL to complete so playbin3's internal streamsynchronizer
        # fully resets before we reconfigure.  Without this, rapid
        # teardown→replay (e.g. YouTube resolve failure → failover) can leave
        # duplicate pad names in streamsynchronizer, triggering GStreamer
        # CRITICAL assertions that abort the process.
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
        if not self._streams_queue:
            # All streams exhausted
            self.failover.emit(None)
            return
        stream = self._streams_queue.pop(0)
        self._current_stream = stream
        # Notify about failover attempt (not on first play)
        if not self._is_first_attempt:
            self.failover.emit(stream)
        if self._is_first_attempt:
            # Seed the elapsed-time timer ONLY on a fresh user-initiated play.
            # Failover keeps the counter running (transparent to the user).
            self._elapsed_seconds = 0
            self._elapsed_timer.start()
        self._is_first_attempt = False
        url = stream.url.strip()
        if "youtube.com" in url or "youtu.be" in url:
            self._play_youtube(url)
        elif "twitch.tv" in url:
            self._play_twitch(url)
        else:
            self._set_uri(url)
            # Arm failover timeout for direct GStreamer URIs
            self._failover_timer.start(BUFFER_DURATION_S * 1000)

    def _set_uri(self, uri: str) -> None:
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
        self._pipeline.set_property("uri", uri)
        self._pipeline.set_state(Gst.State.PLAYING)

    # ------------------------------------------------------------------ #
    # YouTube -- yt_dlp library API with EJS JS challenge solver (Plan 35-06)
    # ------------------------------------------------------------------ #

    def _play_youtube(self, url: str) -> None:
        """Resolve YouTube URL via yt_dlp library on a worker thread (EJS JS
        challenge solver + cookies if available), then play the resolved HLS
        URL through playbin3 via the queued youtube_resolved signal.

        Requires a Node.js runtime on PATH for yt-dlp's EJS solver.
        """
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
        # Fallback title shows the station name immediately while the resolver runs.
        if self._current_station_name:
            self.title_changed.emit(self._current_station_name)
        threading.Thread(
            target=self._youtube_resolve_worker, args=(url,), daemon=True
        ).start()

    def _youtube_resolve_worker(self, url: str) -> None:
        """Call yt_dlp.YoutubeDL.extract_info on a worker thread. Emits
        youtube_resolved or youtube_resolution_failed (both queued to main)."""
        import yt_dlp

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "best[protocol^=m3u8]/bestaudio/best",
            "extractor_args": {
                "youtubepot-jsruntime": {"remote_components": ["ejs:github"]},
            },
        }
        cookies = paths.cookies_path()
        if os.path.exists(cookies):
            opts["cookiefile"] = cookies
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            self.youtube_resolution_failed.emit(str(e))
            return
        resolved = (info or {}).get("url") or ""
        if not resolved:
            formats = (info or {}).get("formats") or []
            if formats:
                resolved = formats[-1].get("url") or ""
        if not resolved:
            self.youtube_resolution_failed.emit("No video formats returned")
            return
        self.youtube_resolved.emit(resolved)

    def _on_youtube_resolved(self, resolved_url: str) -> None:
        """Main-thread handler: hand the resolved HLS URL to playbin3 and arm
        the failover timer like any other direct stream."""
        self._set_uri(resolved_url)
        self._failover_timer.start(BUFFER_DURATION_S * 1000)

    def _on_youtube_resolution_failed(self, msg: str) -> None:
        """Main-thread handler: surface the error and advance the failover
        queue."""
        self.playback_error.emit(f"YouTube resolve failed: {msg}")
        self._try_next_stream()

    # ------------------------------------------------------------------ #
    # Twitch -- streamlink library API (D-18)
    # ------------------------------------------------------------------ #

    def _play_twitch(self, url: str) -> None:
        """Resolve Twitch URL via streamlink library on a worker thread, then
        set the resolved HLS URL on playbin3 via the queued twitch_resolved
        signal."""
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
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
