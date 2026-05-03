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

YouTube playback (Plan 35-06 -- supersedes the original Phase 35 spike;
amended Phase 999.9):
- _play_youtube uses yt_dlp.YoutubeDL library and resolves to a direct HLS
  URL, then feeds it to playbin3 via the queued youtube_resolved signal.
  Cookies (if present) are attached via cookiefile.
- Node.js runtime required on PATH for the EJS n-challenge solver. The
  library API does NOT auto-discover JS runtimes the way the CLI does, so
  opts must include js_runtimes={"node": {"path": None}} (Phase 999.9 fix —
  without it extract_info returns "No video formats found!" even though
  `uv run yt-dlp` works at the shell). No external player process is
  launched this phase (see 35-SPIKE-MPV.md "Superseded" section and Plan
  35-06 for the rationale that replaces the original KEEP branch).
- yt-dlp 2026.03.17+: when YouTube account cookies are detected the
  authenticated code path requires the EJS remote component to solve the
  n-challenge. opts must include remote_components={"ejs:github"} so
  yt-dlp downloads the solver script on first use; without it, all formats
  are filtered out and extract_info raises "No video formats found!" even
  though the unauthenticated (no-cookie) path works fine.
"""
from __future__ import annotations

import os
import threading

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
from PySide6.QtCore import QObject, Qt, QTimer, Signal

from musicstreamer import constants, cookie_utils, paths
from musicstreamer.constants import BUFFER_DURATION_S, BUFFER_SIZE_BYTES
from musicstreamer.eq_profile import EqBand, EqProfile, parse_autoeq
from musicstreamer.gst_bus_bridge import GstBusLoopThread
from musicstreamer.models import Station, StationStream
from musicstreamer.stream_ordering import order_streams
from musicstreamer.url_helpers import aa_normalize_stream_url


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
    cookies_cleared            = Signal(str)     # Phase 999.7: advisory toast — cookies.txt auto-cleared due to yt-dlp corruption
    elapsed_updated            = Signal(int)     # wall-clock seconds since play began (40.1-06)
    buffer_percent             = Signal(int)     # 0-100 GStreamer buffer fill; de-duped in _on_gst_buffering (47.1 D-12)
    # Internal cross-thread marshaling (43.1 follow-up fix). Bus handlers run
    # on the GstBusLoopThread (pure GLib, not a QThread), so a bare
    # `QTimer.singleShot(0, fn)` from there posts to a nonexistent Qt loop and
    # fn never runs. Using a Signal with QueuedConnection auto-marshals the
    # call onto the main thread, identical to how `title_changed` already
    # crosses the same boundary.
    _cancel_timers_requested   = Signal()        # bus-loop → main: stop failover timer
    _error_recovery_requested  = Signal()        # bus-loop → main: run _handle_gst_error_recovery
    # Worker threads (twitch/youtube resolve) have no Qt event loop, so
    # QTimer.singleShot(0, ...) from those threads posts to a nonexistent loop
    # and the callback never runs. Queued signal marshals _try_next_stream
    # onto the main thread -- same pattern as _cancel_timers_requested.
    _try_next_stream_requested = Signal()        # worker → main: advance failover queue
    # Phase 57 / WIN-03 D-12: bus-loop -> main: re-apply self._volume after every
    # transition to PLAYING (catches NULL->PLAYING from pause/resume / failover /
    # station switch AND playbin3-internal PAUSED->PLAYING auto-rebuffer recovery
    # which bypasses _set_uri entirely). D-13: single mechanism Option A —
    # property write target is self._pipeline only.
    _playbin_playing_state_reached = Signal()    # bus-loop -> main: re-apply volume on PLAYING

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Ensure the bus-loop thread is running BEFORE the bus is wired
        _bridge = _ensure_bus_bridge()

        self._pipeline = Gst.ElementFactory.make("playbin3", "player")
        self._pipeline.set_property(
            "video-sink", Gst.ElementFactory.make("fakesink", "fake-video")
        )
        audio_sink = Gst.ElementFactory.make("pulsesink", "audio-output")
        if audio_sink:
            self._pipeline.set_property("audio-sink", audio_sink)
        self._pipeline.set_property("buffer-duration", BUFFER_DURATION_S * Gst.SECOND)
        self._pipeline.set_property("buffer-size", BUFFER_SIZE_BYTES)

        # Phase 47.2 D-01: equalizer-nbands in playbin3.audio-filter slot.
        # Constructed once; bands mutated live via GstChildProxy (D-05).
        # Graceful degrade if gst-plugins-good's equalizer is missing
        # (Windows Phase 43 spike will verify DLL presence): self._eq = None
        # and all set_eq_* methods become no-ops.
        self._eq = Gst.ElementFactory.make("equalizer-nbands", "eq")
        if self._eq is not None:
            self._eq.set_property("num-bands", 10)  # placeholder; rebuilt per-profile
            self._pipeline.set_property("audio-filter", self._eq)

        # D-07 bus wiring -- sync emission MUST be enabled before add_signal_watch.
        # Order is grep-verified by the PORT-02 acceptance gate.
        bus = self._pipeline.get_bus()
        bus.enable_sync_message_emission()  # D-07 literal -- exactly 1 call in player.py
        # Phase 43.1 bugfix: marshal add_signal_watch onto the bridge thread.
        # Called inline on the main thread, the watch's GSource attaches to
        # the main thread's default MainContext -- never iterated on Windows;
        # bus handlers silently never fire (no ICY tags, no errors, no
        # buffering updates). run_sync executes on the bridge thread, whose
        # thread-default MainContext IS the one the bridge's MainLoop drives.
        _bridge.run_sync(lambda: bus.add_signal_watch())  # D-07 literal
        bus.connect("message::error", self._on_gst_error)  # async handler
        bus.connect("message::tag",   self._on_gst_tag)    # async handler
        bus.connect("message::buffering", self._on_gst_buffering)  # async handler (47.1 D-12)
        bus.connect("message::state-changed", self._on_gst_state_changed)  # Phase 57 / WIN-03 D-12
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

        # Phase 52 (D-02, D-03): EQ gain ramp timer. GUI-thread interval timer
        # that ticks _EQ_RAMP_TICKS times then stops itself in _on_eq_ramp_tick.
        # Pitfall 2: parented to self (main-thread). QA-05: bound method.
        self._eq_ramp_timer = QTimer(self)
        self._eq_ramp_timer.setInterval(self._EQ_RAMP_INTERVAL_MS)
        self._eq_ramp_timer.timeout.connect(self._on_eq_ramp_tick)
        self._eq_ramp_state: dict | None = None

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
        # 43.1 follow-up: queue bus-loop → main for timer/recovery work.
        self._cancel_timers_requested.connect(
            self._cancel_timers, Qt.ConnectionType.QueuedConnection
        )
        self._error_recovery_requested.connect(
            self._handle_gst_error_recovery, Qt.ConnectionType.QueuedConnection
        )
        # 999.8 WR-03: queue worker-thread → main failover advance.
        self._try_next_stream_requested.connect(
            self._try_next_stream, Qt.ConnectionType.QueuedConnection
        )
        # Phase 57 / WIN-03 D-12: queue bus-loop -> main re-apply on PLAYING.
        self._playbin_playing_state_reached.connect(
            self._on_playbin_state_changed, Qt.ConnectionType.QueuedConnection
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
        self._last_buffer_percent: int = -1  # 47.1 D-14: sentinel so first real 0-100 always emits

        # Phase 47.2 D-15: EQ state mirrors settings table; restored below.
        self._eq_enabled: bool = False
        self._eq_preamp_db: float = 0.0
        self._eq_profile: EqProfile | None = None

    # ------------------------------------------------------------------ #
    # Public API (legacy callback shims preserved for main_window.py)
    # ------------------------------------------------------------------ #

    @property
    def current_stream(self):
        return self._current_stream

    def set_volume(self, value: float) -> None:
        self._volume = max(0.0, min(1.0, value))
        self._pipeline.set_property("volume", self._volume)

    # ------------------------------------------------------------------ #
    # EQ public API (Phase 47.2 D-01, D-04, D-05, D-18)
    # ------------------------------------------------------------------ #

    def set_eq_enabled(self, enabled: bool) -> None:
        """Hot-toggle EQ via smooth gain ramp (Phase 52 D-02, D-05, D-06).

        The state flag flips immediately (D-06); the audio-output gains
        interpolate from current to target over _EQ_RAMP_MS in
        _EQ_RAMP_TICKS ticks. Re-toggling mid-ramp reverses from the
        current in-progress gains (D-05).
        """
        self._eq_enabled = bool(enabled)
        if self._eq is None:
            return  # graceful-degrade preserved
        self._start_eq_ramp()

    def set_eq_profile(self, profile: "EqProfile | None") -> None:
        """D-04: Rebuild element if band count differs; else mutate in place."""
        # Phase 52 T-52-01: a ramp in flight on the old element would write
        # to a stale GstChildProxy after _rebuild_eq_element. Stop it cleanly.
        self._eq_ramp_timer.stop()
        self._eq_ramp_state = None
        self._eq_profile = profile
        needed = len(profile.bands) if profile else 0
        if self._eq is not None and self._eq.get_property("num-bands") != max(1, needed):
            self._rebuild_eq_element(max(1, needed))
        self._apply_eq_state()

    def set_eq_preamp(self, preamp_db: float) -> None:
        """D-18: Uniform offset added to every band's gain (Pitfall 5: ADD, not subtract)."""
        self._eq_preamp_db = float(preamp_db)
        self._apply_eq_state()

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
        # Phase 52: cancel any in-flight EQ ramp; the pipeline going NULL
        # silences output anyway, but stopping the timer prevents a dangling
        # tick on a torn-down element.
        self._eq_ramp_timer.stop()
        self._eq_ramp_state = None
        self._streams_queue = []
        self._recovery_in_flight = False
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)

    def stop(self) -> None:
        self._cancel_timers()
        self._elapsed_timer.stop()
        # Phase 52: same rationale as pause() above.
        self._eq_ramp_timer.stop()
        self._eq_ramp_state = None
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
        # Marshal recovery onto the main thread via queued signal. Bus-loop
        # thread has no Qt event loop, so QTimer.singleShot from here vanishes.
        self._error_recovery_requested.emit()

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
        # Audio arrived -- cancel failover timer on the main thread via queued
        # signal. Bus-loop thread has no Qt event loop, so singleShot vanishes.
        self._cancel_timers_requested.emit()
        if not found:
            return
        title = _fix_icy_encoding(value)
        self.title_changed.emit(title)  # auto-queued cross-thread to main

    def _on_gst_buffering(self, bus, msg) -> None:
        """Bus-loop-thread handler: parse buffer percent, emit Qt signal.

        Runs on GstBusLoopThread (not main thread). May only emit signals,
        never touch Qt widgets directly (Pitfall 2). De-dups on unchanged
        percent (47.1 D-14) to avoid UI churn.
        """
        result = msg.parse_buffering()
        # PyGObject may flatten single-out-param to bare int OR return tuple (Pitfall 1)
        percent = result[0] if isinstance(result, tuple) else int(result)
        if percent == self._last_buffer_percent:
            return
        self._last_buffer_percent = percent
        self.buffer_percent.emit(percent)  # auto-queued cross-thread to main

    def _on_gst_state_changed(self, bus, msg) -> None:
        """Bus-loop-thread handler (Phase 57 / WIN-03 D-12).

        Filters to top-level playbin3 transitions to PLAYING, then marshals
        the volume re-apply onto the main thread via queued Signal. Pitfall 2
        (qt-glib-bus-threading.md Rule 2): bus-loop thread has no Qt event
        loop, so all property writes MUST happen on the main thread.

        Catches BOTH:
          - NULL->PLAYING (pause/resume, station switch, failover via
            _try_next_stream, YouTube/Twitch resolves via _on_youtube_resolved
            / _on_twitch_resolved -> _set_uri).
          - PAUSED->PLAYING (playbin3-internal auto-rebuffer recovery, which
            bypasses _set_uri entirely).
        """
        # Filter: child elements (decodebin3, urisourcebin, audio sink, etc.)
        # also emit state-changed on the same bus. We only care about the
        # top-level playbin3 element transition (D-12).
        if msg.src is not self._pipeline:
            return
        _old, new, _pending = msg.parse_state_changed()
        if new != Gst.State.PLAYING:
            return
        # Marshal onto main thread via queued Signal — same pattern as
        # _cancel_timers_requested / _error_recovery_requested above.
        self._playbin_playing_state_reached.emit()

    def _on_playbin_state_changed(self) -> None:
        """Main-thread slot (Phase 57 / WIN-03 D-12 + D-13).

        Re-applies the user's last-set volume to playbin3.volume on every
        transition to PLAYING. D-13 single mechanism (Option A): property
        write target is self._pipeline only. self._volume
        is the cached slider position — survives pipeline rebuilds because
        it lives on the Player, not on playbin3 (which resets the property
        on every NULL->PLAYING / PAUSED->PLAYING — diagnostic Step 2).
        """
        self._pipeline.set_property("volume", self._volume)

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
        self._last_buffer_percent = -1  # 47.1 D-14: reset so new URL's first buffer emits (Pitfall 3)
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
        uri = aa_normalize_stream_url(uri)  # WIN-01 / D-01: DI.fm HTTPS->HTTP at URI funnel
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
        youtube_resolved or youtube_resolution_failed (both queued to main).

        Phase 999.7: cookies.txt is routed through ``cookie_utils.temp_cookies_copy``
        so yt-dlp's save_cookies() side effect on ``__exit__`` never touches the
        canonical file. If the canonical file is corrupted (yt-dlp marker header
        from a previous unprotected call), it is auto-cleared and the
        ``cookies_cleared`` Signal is emitted (queued to main thread for toast).

        Phase 999.8 WR-02: wrapped in top-level try/except backstop so ANY
        unexpected error in this daemon thread surfaces as
        ``youtube_resolution_failed`` instead of silently killing the thread
        (which leaves the UI stuck with no error toast and no failover
        advance). Covers ImportError on yt_dlp, filesystem errors in the
        cookies corruption check, PermissionError from temp_cookies_copy
        __enter__, etc. The inner extract_info except stays as-is.
        """
        try:
            import yt_dlp

            # Phase 999.7 corruption check — MUST run BEFORE building opts.
            canonical = paths.cookies_path()
            if os.path.exists(canonical) and cookie_utils.is_cookie_file_corrupted(canonical):
                constants.clear_cookies()
                # cookies_cleared is emitted from this worker thread; receivers (e.g.
                # MainWindow.show_toast) must be on the main thread so Qt.AutoConnection
                # resolves to QueuedConnection. Mirrors the youtube_resolved contract above.
                self.cookies_cleared.emit(
                    "YouTube cookies cleared — re-import via Accounts menu."
                )

            opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "format": "best[protocol^=m3u8]/bestaudio/best",
                # Phase 999.9: yt-dlp's library API does NOT auto-discover JS runtimes
                # the way the CLI does. Without an explicit js_runtimes entry the YouTube
                # n-challenge solver cannot run, so extract_info returns "No video formats
                # found!" even though `uv run yt-dlp <url>` works at the shell. Node is the
                # runtime declared by RUNTIME-01; path=None lets yt-dlp resolve it via PATH.
                "js_runtimes": {"node": {"path": None}},
                # BUG-YT-COOKIES: yt-dlp 2026.03.17+ requires the EJS remote component
                # when YouTube account cookies are detected (authenticated code path).
                # Without remote_components, the n-challenge solving is skipped and ALL
                # formats are filtered out — "No video formats found!" — even though
                # the unauthenticated (no-cookie) path still resolves fine.
                # Enabling ejs:github lets yt-dlp download the solver script on first use.
                "remote_components": {"ejs:github"},
            }

            # Phase 999.7 Pitfall 1: yt_dlp.YoutubeDL MUST nest INSIDE
            # temp_cookies_copy so yt-dlp's save_cookies() on __exit__ writes to
            # the temp path, not canonical. Unlinking the temp after yt-dlp closes
            # is handled by the context manager's finally.
            info = None
            with cookie_utils.temp_cookies_copy() as cookiefile:
                if cookiefile is not None:
                    opts["cookiefile"] = cookiefile
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
        except Exception as e:  # noqa: BLE001 — daemon worker must surface ALL failures
            self.youtube_resolution_failed.emit(f"youtube resolve crashed: {e!r}")

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
        # 999.8 WR-01: top-level try/except is a backstop so ANY unexpected
        # error in this daemon thread surfaces as playback_error + failover
        # advance instead of silently killing the thread (which leaves the
        # UI stuck in NULL state with no error toast). Covers Streamlink()
        # constructor, set_option() API renames/typos, property access on
        # streams["best"], and any import errors from the narrow imports.
        from streamlink.session import Streamlink
        from streamlink.exceptions import NoPluginError, PluginError

        try:
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
                session.set_option(
                    "twitch-api-header",
                    [("Authorization", f"OAuth {token}")],
                )
            try:
                streams = session.streams(url)
            except NoPluginError:
                self.playback_error.emit("streamlink: no plugin")
                # 999.8 WR-03: worker thread has no Qt loop -- emit queued signal
                # instead of QTimer.singleShot so failover actually advances.
                self._try_next_stream_requested.emit()
                return
            except PluginError as e:
                if "No playable streams" in str(e) or "offline" in str(e).lower():
                    channel = url.rstrip("/").split("/")[-1]
                    self.offline.emit(channel)
                    return
                self.playback_error.emit(f"streamlink: {e}")
                # 999.8 WR-03: see note above.
                self._try_next_stream_requested.emit()
                return
            if not streams or "best" not in streams:
                channel = url.rstrip("/").split("/")[-1]
                self.offline.emit(channel)
                return
            # Success -- queued emission marshals back to main thread
            self.twitch_resolved.emit(streams["best"].url)
        except Exception as e:  # noqa: BLE001 — daemon worker must surface ALL failures
            self.playback_error.emit(f"twitch resolve crashed: {e!r}")
            self._try_next_stream_requested.emit()

    def _on_twitch_resolved(self, resolved_url: str) -> None:
        """Runs on main thread (connected via Qt.QueuedConnection in __init__)."""
        self._set_uri(resolved_url)
        self._failover_timer.start(BUFFER_DURATION_S * 1000)

    # ------------------------------------------------------------------ #
    # EQ internals (Phase 47.2)
    # ------------------------------------------------------------------ #

    _EQ_BAND_TYPE = {"PK": 0, "LSC": 1, "HSC": 2}  # Pitfall 3: enum starts at 0

    # Phase 52 (D-02): smooth gain ramp on EQ toggle (40ms / 8 ticks of 5ms).
    # Eliminates the IIR-coefficient-discontinuity click on equalizer-nbands
    # band-gain mutation. dB-linear lerp.
    _EQ_RAMP_MS = 40
    _EQ_RAMP_TICKS = 8
    _EQ_RAMP_INTERVAL_MS = 5  # _EQ_RAMP_MS // _EQ_RAMP_TICKS

    def _apply_eq_state(self) -> None:
        """Write band properties for the current (profile, enabled, preamp) state.

        Bypass semantics (D-05): if no element, no profile, or disabled, every
        band gain is zeroed -- producing unity passthrough without rebuilding
        the pipeline.
        """
        if self._eq is None:
            return
        if self._eq_profile is None or not self._eq_enabled:
            for i in range(self._eq.get_children_count()):
                self._eq.get_child_by_index(i).set_property("gain", 0.0)
            return
        for i, b in enumerate(self._eq_profile.bands):
            if i >= self._eq.get_children_count():
                break
            band = self._eq.get_child_by_index(i)
            band.set_property("freq", float(b.freq_hz))
            # Pitfall 4: GStreamer bandwidth is Hz, AutoEQ Q is quality factor.
            band.set_property("bandwidth", float(b.freq_hz) / max(float(b.q), 0.01))
            # Pitfall 5: ADD preamp (usually negative) -- do NOT subtract abs().
            band.set_property("gain", float(b.gain_db) + self._eq_preamp_db)
            band.set_property("type", self._EQ_BAND_TYPE.get(b.filter_type, 0))

    # ------------------------------------------------------------------ #
    # Phase 52: EQ smooth gain ramp (D-02, D-03, D-04, D-05)
    # ------------------------------------------------------------------ #

    def _capture_current_gains(self) -> list[float]:
        """Read live per-band gains from the equalizer element (D-05).

        Authoritative source for ramp start_gain. Used both on fresh ramp
        start and on mid-ramp reverse-from-current.
        """
        n = self._eq.get_children_count()
        return [
            float(self._eq.get_child_by_index(i).get_property("gain"))
            for i in range(n)
        ]

    def _compute_target_gains(self) -> list[float]:
        """Compute per-band target gains from current (_eq_enabled,
        _eq_profile, _eq_preamp_db) state (D-04).

        Bypass (disabled or no profile) -> [0.0] * n. Profile-applied ->
        b.gain_db + preamp_db per band (Pitfall 5: ADD), padded with 0.0
        to children_count when profile has fewer bands.
        """
        n = self._eq.get_children_count()
        if self._eq_profile is None or not self._eq_enabled:
            return [0.0] * n
        gains = [0.0] * n
        for i, b in enumerate(self._eq_profile.bands):
            if i >= n:
                break
            # Pitfall 5: ADD preamp (do NOT subtract abs).
            gains[i] = float(b.gain_db) + self._eq_preamp_db
        return gains

    def _start_eq_ramp(self) -> None:
        """Begin or reverse a gain ramp toward the current target state.

        Fresh ramp: capture live start gains, write freq/bandwidth/type
        ONCE (Pitfall 4: bandwidth=Hz, not Q), seed ramp_state, start timer.
        In-progress ramp (D-05 reverse-from-current): re-capture live gains
        as new start_gain, replace target_gain, reset tick_index, keep timer
        running.
        """
        if self._eq is None:
            return
        target = self._compute_target_gains()
        start = self._capture_current_gains()
        # On fresh ramp into the profile-applied path, write the static
        # band properties (freq/bandwidth/type) once. Bypass path leaves
        # them untouched (matches existing _apply_eq_state bypass branch).
        if (
            self._eq_ramp_state is None
            and self._eq_profile is not None
            and self._eq_enabled
        ):
            n = self._eq.get_children_count()
            for i, b in enumerate(self._eq_profile.bands):
                if i >= n:
                    break
                band = self._eq.get_child_by_index(i)
                band.set_property("freq", float(b.freq_hz))
                # Pitfall 4: bandwidth (Hz) = freq_hz / max(Q, 0.01).
                band.set_property(
                    "bandwidth", float(b.freq_hz) / max(float(b.q), 0.01)
                )
                band.set_property(
                    "type", self._EQ_BAND_TYPE.get(b.filter_type, 0)
                )
        self._eq_ramp_state = {
            "start_gain": start,
            "target_gain": target,
            "tick_index": 0,
        }
        if not self._eq_ramp_timer.isActive():
            self._eq_ramp_timer.start()

    def _on_eq_ramp_tick(self) -> None:
        """Per-tick gain interpolation; final tick commits exact target (D-02)."""
        state = self._eq_ramp_state
        if self._eq is None or state is None:
            self._eq_ramp_timer.stop()
            self._eq_ramp_state = None
            return
        state["tick_index"] += 1
        k = state["tick_index"]
        n = self._eq.get_children_count()
        target = state["target_gain"]
        start = state["start_gain"]
        if k >= self._EQ_RAMP_TICKS:
            # Final tick: commit exact target (no lerp residual).
            for i in range(n):
                t_i = target[i] if i < len(target) else 0.0
                self._eq.get_child_by_index(i).set_property("gain", t_i)
            self._eq_ramp_timer.stop()
            self._eq_ramp_state = None
            return
        t = float(k) / float(self._EQ_RAMP_TICKS)
        for i in range(n):
            s_i = start[i] if i < len(start) else 0.0
            t_i = target[i] if i < len(target) else 0.0
            g = s_i + (t_i - s_i) * t
            self._eq.get_child_by_index(i).set_property("gain", g)

    def _rebuild_eq_element(self, num_bands: int) -> None:
        """D-04 + Pitfall 1: num-bands realloc unreliable; rebuild the whole element.

        Mirrors the pause() NULL-transition idiom at lines 199-206.
        """
        self._pipeline.set_state(Gst.State.READY)
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
        self._eq = Gst.ElementFactory.make("equalizer-nbands", "eq")
        if self._eq is not None:
            self._eq.set_property("num-bands", num_bands)
            self._pipeline.set_property("audio-filter", self._eq)

    def restore_eq_from_settings(self, repo) -> None:
        """D-15: Load eq_active_profile, eq_enabled, eq_preamp_db from settings.

        Called from MainWindow/Player owner AFTER repo is available. Not called
        from __init__ because Player construction precedes the repo parameter.
        Silent on errors -- the EQ just stays disabled.
        """
        import os
        active = repo.get_setting("eq_active_profile", "")
        enabled = repo.get_setting("eq_enabled", "0") == "1"
        try:
            preamp = float(repo.get_setting("eq_preamp_db", "0.0"))
        except (TypeError, ValueError):
            preamp = 0.0
        self._eq_preamp_db = preamp
        if active:
            path = os.path.join(paths.eq_profiles_dir(), active)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    self._eq_profile = parse_autoeq(fh.read())
            except (OSError, ValueError):
                self._eq_profile = None
            if self._eq_profile is not None:
                needed = len(self._eq_profile.bands)
                if self._eq is not None and self._eq.get_property("num-bands") != max(1, needed):
                    self._rebuild_eq_element(max(1, needed))
        self._eq_enabled = enabled and self._eq_profile is not None
        self._apply_eq_state()
