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
  opts must include js_runtimes={"node": {"path": <abs-path-or-None>}} (Phase
  999.9 fix — without it extract_info returns "No video formats found!" even
  though `uv run yt-dlp` works at the shell; Phase 79 / BUG-11 threads the
  resolved absolute path through yt_dlp_opts.build_js_runtimes so .desktop
  launches don't fall back to yt-dlp's own PATH lookup). No external player process is
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

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
from PySide6.QtCore import QObject, Qt, QTimer, Signal

from musicstreamer import constants, cookie_utils, paths, yt_dlp_opts
from musicstreamer.runtime_check import NodeRuntime
from musicstreamer.constants import BUFFER_DURATION_S, BUFFER_SIZE_BYTES
from musicstreamer.eq_profile import EqBand, EqProfile, parse_autoeq
from musicstreamer.gst_bus_bridge import GstBusLoopThread
from musicstreamer.hi_res import bit_depth_from_format
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


# Phase 62 / BUG-09: module logger (first logger in player.py).
# Surfaced at INFO via __main__.py per-logger setLevel — see Plan 03.
_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------- #
# Phase 62 / BUG-09: buffer-underrun cycle state machine.
#
# Pure-Python helper class (no Qt, no GStreamer) so it is unit-testable
# without instantiating Player. Player constructs one instance, drives
# observe(percent) from _on_gst_buffering, drives force_close(outcome)
# from terminator hooks (pause / stop / _try_next_stream / closeEvent).
#
# RESEARCH.md Architecture Pattern 1; PATTERNS.md §1i.
# ---------------------------------------------------------------------- #


@dataclass(frozen=True)
class _CycleClose:
    """Record emitted when an underrun cycle closes (D-02).

    Carries every field needed by the structured INFO log line in
    Player._on_underrun_cycle_closed. Frozen so the record cannot be
    mutated after the cycle's terminator decided the outcome.
    """
    start_ts: float
    end_ts: float
    duration_ms: int
    min_percent: int
    station_id: int
    station_name: str
    url: str
    outcome: str           # recovered | failover | stop | pause | shutdown
    cause_hint: str        # unknown | network


class _BufferUnderrunTracker:
    """Cycle state machine for buffer-underrun events (Phase 62 / BUG-09).

    Pure: no Qt, no GStreamer. Returns sentinels / records; the caller
    (Player) wires them to Signals and log writes.

    Lifecycle (D-04 mirrors Phase 47.1 D-14 sentinel reset):
      - bind_url() establishes per-URL context and clears all state.
      - observe(percent) drives the cycle state machine:
          - while unarmed, percent==100 flips arm to True (initial fill complete);
          - while armed but no cycle open, percent<100 opens a cycle;
          - while a cycle is open, percent<100 updates min_percent;
          - while a cycle is open, percent==100 closes naturally (outcome='recovered').
      - force_close(outcome) closes any open cycle on terminator events
        (pause / stop / failover / shutdown).
      - note_error_in_cycle() flips cause_hint to 'network' if a cycle is open
        (D-02 Discretion: minimal cause attribution this phase).
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._reset_per_url()

    def _reset_per_url(self) -> None:
        """Called by bind_url; mirrors Phase 47.1 D-14 sentinel reset (Pitfall 3)."""
        self._armed: bool = False
        self._open: bool = False
        self._start_ts: float = 0.0
        self._min_percent: int = 100
        self._station_id: int = 0
        self._station_name: str = ""
        self._url: str = ""
        self._cause_hint: str = "unknown"

    def bind_url(self, station_id: int, station_name: str, url: str) -> None:
        """Bind tracker to a new URL — clears arm + cycle state (D-04 / Pitfall 3)."""
        self._reset_per_url()
        self._station_id = station_id
        self._station_name = station_name
        self._url = url

    def observe(self, percent: int) -> Optional[object]:
        """Drive the cycle state machine on a BUFFERING bus message.

        Reads the clock on every call (one tick per observe). The clock is
        the single source of truth for timestamps; consuming it uniformly
        keeps duration_ms deterministic when callers inject a list-clock.

        Returns:
          - None: no transition (initial fill, in-cycle update, or no-op).
          - "OPENED": a new cycle just opened (D-01 / D-04). Caller emits
            _underrun_cycle_opened so the main thread arms the dwell timer.
          - _CycleClose: a cycle just closed naturally at percent==100
            (D-02). Caller emits _underrun_cycle_closed so the main thread
            cancels the dwell timer and writes the structured log line.
        """
        now = self._clock()
        if not self._armed:
            if percent == 100:
                self._armed = True
            return None
        if not self._open:
            if percent < 100:
                self._open = True
                self._start_ts = now
                self._min_percent = percent
                return "OPENED"
            return None
        # Cycle is open.
        if percent < 100:
            if percent < self._min_percent:
                self._min_percent = percent
            return None
        # percent == 100 → natural close
        return self._close_with_now("recovered", now)

    def force_close(self, outcome: str) -> Optional[_CycleClose]:
        """Force-close any open cycle on a terminator event (D-03).

        Returns the close record if a cycle was open; None if already closed
        (idempotent guard — calling force_close twice is safe).
        """
        if not self._open:
            return None
        return self._close_with_now(outcome, self._clock())

    def note_error_in_cycle(self) -> None:
        """D-02 / Discretion: flip cause_hint to 'network' if a cycle is open.

        Called from Player._on_gst_error before _error_recovery_requested.emit().
        Bus-loop thread is fine — tracker has no Qt.
        """
        if self._open:
            self._cause_hint = "network"

    def _close_with_now(self, outcome: str, end_ts: float) -> _CycleClose:
        """Build the close record using the supplied end_ts, then reset
        cycle-level state. The caller is responsible for consuming the
        clock exactly once (observe() does this at function entry,
        force_close() does it inline) — keeps clock reads deterministic.

        Keeps armed=True (still on the same URL — bind_url is the only path
        that clears arm). After close, force_close on the same cycle returns
        None until observe(<100) opens a new cycle.
        """
        record = _CycleClose(
            start_ts=self._start_ts,
            end_ts=end_ts,
            duration_ms=int((end_ts - self._start_ts) * 1000),
            min_percent=self._min_percent,
            station_id=self._station_id,
            station_name=self._station_name,
            url=self._url,
            outcome=outcome,
            cause_hint=self._cause_hint,
        )
        # Reset cycle-level state but keep armed=True (still on the same URL).
        self._open = False
        self._start_ts = 0.0
        self._min_percent = 100
        self._cause_hint = "unknown"
        return record


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

    # Phase 62 / BUG-09: buffer-underrun cycle Signals.
    # _underrun_cycle_opened / _underrun_cycle_closed are bus-loop → main
    # queued (Pitfall 2 — bus handlers may only emit Signals).
    # underrun_recovery_started is main → MainWindow (D-07 dwell elapsed).
    _underrun_cycle_opened    = Signal()         # bus-loop → main: arm dwell timer
    _underrun_cycle_closed    = Signal(object)   # bus-loop → main: log + cancel dwell (object = _CycleClose)
    underrun_recovery_started = Signal()         # main → MainWindow: show_toast (D-07)

    # Phase 70 / DS-01: streaming/bus thread → main: persist sample_rate_hz / bit_depth
    # for the playing stream. Emitted with QueuedConnection on the receiver side
    # (MainWindow wires the slot in Plan 70-05 — qt-glib-bus-threading.md Rule 2).
    audio_caps_detected = Signal(int, int, int)  # stream_id, rate_hz, bit_depth

    def __init__(self, parent: QObject | None = None, *, node_runtime: "NodeRuntime | None" = None) -> None:
        super().__init__(parent)
        self._node_runtime = node_runtime

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
        # Without GST_PLAY_FLAG_BUFFERING (0x100), playbin3 bypasses queue2 on live
        # HTTP audio sources — buffer-duration/buffer-size above are silently ignored
        # and decodebin3's internal multiqueue (~1s/100KB per pad) handles jitter
        # instead, pinning the buffer-fill indicator near its low-watermark (~10%).
        flags = self._pipeline.get_property("flags")
        self._pipeline.set_property("flags", flags | 0x100)

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

        # Phase 57 / WIN-03 D-15: pause-volume ramp timer. Mirrors the EQ ramp
        # construction directly above (Pitfall 2 — main-thread, parented to self).
        # Composes with Plan 57-03's bus-message re-apply: this ramp runs PRE-NULL,
        # the re-apply runs POST-PLAYING; disjoint write windows on the same
        # playbin3.volume property surface.
        self._pause_volume_ramp_timer = QTimer(self)
        self._pause_volume_ramp_timer.setInterval(self._PAUSE_VOLUME_RAMP_INTERVAL_MS)
        self._pause_volume_ramp_timer.timeout.connect(self._on_pause_volume_ramp_tick)
        self._pause_volume_ramp_state: dict | None = None

        # Phase 62 / D-07: 1500ms dwell timer.
        # Pitfall 2: parented to self → main thread.
        # QA-05: bound-method timeout, no lambda.
        self._underrun_dwell_timer = QTimer(self)
        self._underrun_dwell_timer.setSingleShot(True)
        self._underrun_dwell_timer.setInterval(1500)
        self._underrun_dwell_timer.timeout.connect(self._on_underrun_dwell_elapsed)

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
        # Phase 62 / Pitfall 2: queue bus-loop → main for cycle-opened/closed.
        self._underrun_cycle_opened.connect(
            self._on_underrun_cycle_opened, Qt.ConnectionType.QueuedConnection
        )
        self._underrun_cycle_closed.connect(
            self._on_underrun_cycle_closed, Qt.ConnectionType.QueuedConnection
        )

        # Phase 70 / DS-01 + qt-glib-bus-threading.md Rule 2:
        # audio_caps_detected is emitted from the streaming thread; receiver
        # (MainWindow._on_audio_caps_detected) connects with QueuedConnection
        # in Plan 70-05.  Player does NOT self-connect (no repo handle — Pitfall 9).
        self._caps_pad = None               # cached audio-pad ref for disconnect on next _set_uri
        self._caps_handler_id: int = 0      # GObject handler-id from pad.connect(); 0 = not connected
        self._caps_armed_for_stream_id: int = 0  # per-URL one-shot guard; 0 = disarmed (Pitfall 6)

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

        # Phase 62 / BUG-09: cycle-tracker instance + station_id field.
        # Tracker mirrors Phase 47.1 D-14 sentinel reset lifecycle (Pitfall 3 —
        # bind_url is called from _try_next_stream alongside _last_buffer_percent reset).
        # _current_station_id mirrors _current_station_name for log-line context.
        self._tracker = _BufferUnderrunTracker()
        self._current_station_id: int = 0

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
        self._current_station_id = station.id   # Phase 62: log-line context
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
        self._current_station_id = 0   # Phase 62 / W2: mirror the empty/zero sentinel of _current_station_name
        self._streams_queue = [stream]
        self._recovery_in_flight = False
        self._is_first_attempt = True
        self._try_next_stream()

    def pause(self) -> None:
        """Stop audio output without clearing station context (D-04).

        Phase 57 / WIN-03 D-15: fades playbin3.volume to 0 across an 8-tick
        ramp BEFORE set_state(NULL) — masks the audible pop on Windows
        wasapi2sink (cross-platform; Linux pulsesink benefits the same way).
        The final ramp tick is what actually calls set_state(NULL) +
        get_state(CLOCK_TIME_NONE). Plan 57-03's bus-message handler
        re-applies self._volume on the post-resume PLAYING transition, so
        the user perceives: smooth fade-out, brief silence (rebuild gap),
        instant restore at slider position.
        """
        self._cancel_timers()
        self._elapsed_timer.stop()
        # Phase 52: cancel any in-flight EQ ramp; the pipeline going NULL
        # silences output anyway, but stopping the timer prevents a dangling
        # tick on a torn-down element.
        self._eq_ramp_timer.stop()
        self._eq_ramp_state = None
        self._streams_queue = []
        self._recovery_in_flight = False
        # Phase 62 / D-03: force-close any open underrun cycle as outcome=pause.
        prior_close = self._tracker.force_close("pause")
        if prior_close is not None:
            self._underrun_cycle_closed.emit(prior_close)
        self._underrun_dwell_timer.stop()
        # Phase 57 / WIN-03 D-15: arm the volume fade-down ramp; the final
        # tick performs set_state(NULL) + get_state(CLOCK_TIME_NONE).
        self._start_pause_volume_ramp()

    def stop(self) -> None:
        self._cancel_timers()
        self._elapsed_timer.stop()
        # Phase 52: same rationale as pause() above.
        self._eq_ramp_timer.stop()
        self._eq_ramp_state = None
        # Phase 57 / WIN-03 D-15: cancel any in-flight pause-volume ramp.
        self._pause_volume_ramp_timer.stop()
        self._pause_volume_ramp_state = None
        self._elapsed_seconds = 0
        self._streams_queue = []
        self._recovery_in_flight = False
        # Phase 62 / D-03: force-close any open underrun cycle as outcome=stop.
        prior_close = self._tracker.force_close("stop")
        if prior_close is not None:
            self._underrun_cycle_closed.emit(prior_close)
        self._underrun_dwell_timer.stop()
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)

    def shutdown_underrun_tracker(self) -> None:
        """Phase 62 / D-03 + Pitfall 4: force-close any open underrun cycle as
        outcome=shutdown. Called from MainWindow.closeEvent BEFORE
        super().closeEvent(event) so in-flight cycles still write their log line.

        SYNCHRONOUS log write (not via _underrun_cycle_closed queued Signal):
        closeEvent is followed by QApplication.quit(); queued slots may never
        run. Same instinct as MediaKeysBackend.shutdown() at main_window.py:355.
        """
        prior_close = self._tracker.force_close("shutdown")
        if prior_close is not None:
            _log.info(
                "buffer_underrun "
                "start_ts=%.3f end_ts=%.3f duration_ms=%d min_percent=%d "
                "station_id=%d station_name=%r url=%r outcome=%s cause_hint=%s",
                prior_close.start_ts, prior_close.end_ts,
                prior_close.duration_ms, prior_close.min_percent,
                prior_close.station_id, prior_close.station_name,
                prior_close.url, prior_close.outcome, prior_close.cause_hint,
            )
        self._underrun_dwell_timer.stop()

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
        # Phase 62 / D-02 Discretion: cause_hint flips to 'network' if a cycle
        # is open. Bus-loop thread is fine — tracker has no Qt.
        self._tracker.note_error_in_cycle()
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

        Phase 62 / BUG-09: extended with cycle state machine. Tracker output
        dispatched via queued Signals (Pitfall 2 — bus-loop has no Qt event loop).
        """
        result = msg.parse_buffering()
        # PyGObject may flatten single-out-param to bare int OR return tuple (Pitfall 1)
        percent = result[0] if isinstance(result, tuple) else int(result)
        if percent == self._last_buffer_percent:
            return
        self._last_buffer_percent = percent
        self.buffer_percent.emit(percent)  # auto-queued cross-thread to main
        # Phase 62 / D-01..D-04: cycle state machine.
        transition = self._tracker.observe(percent)
        if transition == "OPENED":
            self._underrun_cycle_opened.emit()              # queued → main: arm dwell timer
        elif transition is not None:                         # closed naturally (recovered)
            self._underrun_cycle_closed.emit(transition)    # queued → main: log + cancel dwell

    # ------------------------------------------------------------------ #
    # Phase 70 / DS-01: GStreamer audio-sink-pad caps detection.
    #
    # Threading invariant (Phase 43.1 Pitfall 2 / qt-glib-bus-threading.md Rule 2):
    # _on_caps_negotiated runs on the GStreamer STREAMING THREAD (not the Qt main
    # thread). It MUST ONLY call self.audio_caps_detected.emit(...). It must
    # NEVER touch Qt widgets, call repo methods, or mutate self._pipeline
    # properties — those actions silently fail or corrupt state on a non-QThread.
    #
    # _arm_caps_watch_for_current_stream is called from BOTH _set_uri (installs
    # the async notify::caps watch) AND _on_playbin_state_changed (Pattern 1b
    # main-thread synchronous read path for streams whose caps are already
    # negotiated at PLAYING transition).
    # ------------------------------------------------------------------ #

    def _arm_caps_watch_for_current_stream(self) -> None:
        """Disconnect any prior pad watch, then arm a fresh notify::caps listener.

        Called from _set_uri (async path) and _on_playbin_state_changed
        (Pattern 1b sync path).  Idempotent: disconnects before arming.
        """
        # Disconnect prior watch so stale handlers don't fire against a dead pad.
        if self._caps_pad is not None and self._caps_handler_id:
            try:
                self._caps_pad.disconnect(self._caps_handler_id)
            except (TypeError, Exception):
                pass
        self._caps_pad = None
        self._caps_handler_id = 0

        if self._current_stream is None:
            return

        # Arm one-shot guard with the stream_id that triggered this call
        # (Pitfall 6: pair future emit with the URL currently being set up).
        self._caps_armed_for_stream_id = self._current_stream.id

        # playbin3 (unlike legacy playbin 1.x) does not expose a `get-audio-pad`
        # action signal. Use the audio-sink property — the pulsesink we set in
        # __init__ — and probe its static sink pad, which receives the
        # negotiated post-decode caps. Defensive: handle missing sink, missing
        # pad, or unexpected pipeline shape by silently disabling caps detection
        # for this stream (UI falls back to D-03 cold-start defaults).
        try:
            audio_sink = self._pipeline.get_property("audio-sink")
        except Exception:
            audio_sink = None
        if audio_sink is None:
            return
        try:
            pad = audio_sink.get_static_pad("sink")
        except Exception:
            pad = None
        if pad is None:
            # Audio sink pad not available yet; notify::caps will arrive later.
            return
        self._caps_pad = pad
        self._caps_handler_id = pad.connect("notify::caps", self._on_caps_negotiated)
        # Synchronous one-shot: if caps are already negotiated, emit immediately
        # and disarm.  If not yet stable, the GObject handler above covers it.
        self._on_caps_negotiated(pad, None)

    def _on_caps_negotiated(self, pad, _pspec) -> None:
        """Streaming-thread handler — MUST emit a queued Signal, never touch
        Qt widgets or self._pipeline directly (Phase 43.1 Pitfall 2 /
        qt-glib-bus-threading.md Rule 2).

        Connected via QueuedConnection on the RECEIVER side (MainWindow in
        Plan 70-05) so cross-thread delivery is automatic.
        """
        if not self._caps_armed_for_stream_id:
            return  # already emitted for this URL (Pitfall 6 one-shot disarm)
        caps = pad.get_current_caps()
        if caps is None or caps.get_size() == 0:
            return  # caps not yet stable (Pitfall 1 — wait for next fire)
        s = caps.get_structure(0)
        # Defensive dual-path rate extraction (RESEARCH Pattern 1 lines 290-295).
        # GstStructure.get_int returns (found: bool, value: int) in PyGObject;
        # fall back to dict-style access for environments where the binding differs.
        rate = 0
        _rate_found = False
        if hasattr(s, "get_int"):
            try:
                result = s.get_int("rate")
                if isinstance(result, tuple) and len(result) == 2:
                    rate_ok, rate_val = result
                    if rate_ok:
                        rate = int(rate_val)
                        _rate_found = True
                elif isinstance(result, int):
                    rate = result
                    _rate_found = True
            except (TypeError, ValueError):
                pass
        if not _rate_found:
            try:
                rate = int(s["rate"])
            except (KeyError, TypeError, ValueError):
                rate = 0
        # Defensive format string extraction (RESEARCH Pattern 1 lines 296-299).
        try:
            fmt = s.get_string("format") or s["format"]
        except (KeyError, TypeError):
            fmt = ""
        depth = bit_depth_from_format(fmt or "")
        if rate <= 0 or depth <= 0:
            return  # ignore unknown / incomplete caps (T-06 guard)
        # Disarm one-shot guard BEFORE emit so a re-entrant call from a
        # synchronous context cannot trigger a second emission (Pitfall 6).
        sid = self._caps_armed_for_stream_id
        self._caps_armed_for_stream_id = 0
        self.audio_caps_detected.emit(sid, rate, depth)  # queued → main thread

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

        Phase 70 / Pattern 1b: also calls _arm_caps_watch_for_current_stream
        here so that streams whose caps are already negotiated at PLAYING
        (most HTTP audio) are captured via the synchronous get_current_caps()
        path.  Idempotent: the method disconnects any prior watch before arming.
        """
        self._pipeline.set_property("volume", self._volume)
        # Pattern 1b: synchronous one-shot caps read on the main thread.
        self._arm_caps_watch_for_current_stream()

    # ------------------------------------------------------------------ #
    # Timer helpers -- main-thread only
    # ------------------------------------------------------------------ #

    def _cancel_timers(self) -> None:
        """Cancel pending failover timeout and any in-flight pause-volume ramp."""
        self._failover_timer.stop()
        # Phase 57 / WIN-03 CR-01: also cancel an in-flight pause-volume ramp
        # so a station switch / failover within the ramp's ~40ms window doesn't
        # let the ramp's final tick fire set_state(NULL) on a pipeline the
        # caller has just transitioned back to PLAYING.
        self._pause_volume_ramp_timer.stop()
        self._pause_volume_ramp_state = None

    def _on_timeout(self) -> None:
        """Failover timeout: no audio arrived within BUFFER_DURATION_S seconds."""
        self._try_next_stream()

    def _on_elapsed_tick(self) -> None:
        """1Hz tick: increment counter and emit elapsed_updated(seconds)."""
        self._elapsed_seconds += 1
        self.elapsed_updated.emit(self._elapsed_seconds)

    def _on_underrun_cycle_opened(self) -> None:
        """Main-thread slot (Phase 62 / D-07). Arms the 1500ms dwell QTimer.

        Idempotent — start() on a running timer resets the interval, which
        is the right behavior if a cycle re-opens before the previous one
        completed (rare but possible on rapid station churn).
        """
        self._underrun_dwell_timer.start()

    def _on_underrun_cycle_closed(self, record) -> None:
        """Main-thread slot (Phase 62 / D-02). Cancels in-flight dwell timer
        (silent recovery, D-07) and writes the structured log line at INFO.

        T-62-01 mitigation: station_name and url are %r-quoted, so embedded
        newlines / control chars / quotes from library data cannot inject
        spurious log lines or break grep-based diagnosis.
        """
        self._underrun_dwell_timer.stop()    # idempotent
        _log.info(
            "buffer_underrun "
            "start_ts=%.3f end_ts=%.3f duration_ms=%d min_percent=%d "
            "station_id=%d station_name=%r url=%r outcome=%s cause_hint=%s",
            record.start_ts, record.end_ts, record.duration_ms, record.min_percent,
            record.station_id, record.station_name, record.url,
            record.outcome, record.cause_hint,
        )

    def _on_underrun_dwell_elapsed(self) -> None:
        """Main-thread QTimer.timeout slot (Phase 62 / D-07). Cycle has been
        open ≥ 1500ms; notify MainWindow to consider showing the toast
        (cooldown gated there, D-08)."""
        self.underrun_recovery_started.emit()

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
        # Phase 62 / D-03 + T-62-02: force-close any cycle on the OUTGOING URL
        # with outcome=failover BEFORE binding the tracker to the NEW URL.
        # Ordering is load-bearing: the close record must carry the OLD url.
        prior_close = self._tracker.force_close("failover")
        if prior_close is not None:
            self._underrun_cycle_closed.emit(prior_close)   # queued → main: log + cancel dwell
        # Phase 62 / D-04: bind tracker to NEW URL (mirror of D-14 sentinel reset, Pitfall 3).
        self._tracker.bind_url(
            station_id=self._current_station_id,
            station_name=self._current_station_name,
            url=stream.url,
        )
        self._underrun_dwell_timer.stop()
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
        # Phase 70 / DS-01: install a fresh caps watch on the new pipeline lifecycle.
        # MUST happen AFTER set_state(PLAYING) so playbin3 starts negotiating streams.
        self._arm_caps_watch_for_current_stream()

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

            node_path = self._node_runtime.path if self._node_runtime else None
            _log.info("youtube resolve: node_path=%s", node_path)

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
                # Phase 79 / BUG-11: pass the resolved absolute path so .desktop-launched
                # instances (with stripped PATH) don't fall back to yt-dlp's own PATH lookup.
                "js_runtimes": yt_dlp_opts.build_js_runtimes(self._node_runtime),
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

    # Phase 57 / WIN-03 D-15: pause-volume ramp constants. QTimer-driven fade-down
    # of playbin3.volume from self._volume -> 0 across the NULL transition window.
    # 40ms total / 8 ticks of 5ms — same cadence as the EQ ramp; verified to be
    # below wasapi2sink's audible threshold and above Qt's main-thread tick
    # granularity. Final tick writes 0 to playbin3.volume AND calls set_state(NULL).
    _PAUSE_VOLUME_RAMP_MS = 40
    _PAUSE_VOLUME_RAMP_TICKS = 8
    _PAUSE_VOLUME_RAMP_INTERVAL_MS = 5  # _PAUSE_VOLUME_RAMP_MS // _PAUSE_VOLUME_RAMP_TICKS

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

    # ------------------------------------------------------------------ #
    # Phase 57 / WIN-03 D-15: pause-volume fade-down ramp
    # ------------------------------------------------------------------ #

    def _start_pause_volume_ramp(self) -> None:
        """Begin the pause-volume fade-down (D-15).

        Captures the current playbin3.volume as the ramp start (D-05
        reverse-from-current — if a ramp is already in flight, the read
        picks up the current ramped value, not self._volume). Target is
        always 0. Seeds ramp_state and starts the timer. The final tick
        (in _on_pause_volume_ramp_tick) is what calls set_state(NULL).

        If the ramp is already in flight, calling this restarts from the
        CURRENT live volume — mirrors Phase 52 D-05 (reverse / re-bracket
        mid-ramp without re-attacking from self._volume).
        """
        # Read the LIVE volume — if a previous ramp is in flight this
        # returns the partially-faded value, not self._volume.
        try:
            start = float(self._pipeline.get_property("volume"))
        except (TypeError, AttributeError):
            # Defensive: torn-down or mock pipeline returning non-float.
            start = float(self._volume)
        self._pause_volume_ramp_state = {
            "start_volume": start,
            "target_volume": 0.0,
            "tick_index": 0,
        }
        if not self._pause_volume_ramp_timer.isActive():
            self._pause_volume_ramp_timer.start()

    def _on_pause_volume_ramp_tick(self) -> None:
        """Per-tick volume interpolation; final tick commits volume=0
        AND performs set_state(NULL) + get_state(CLOCK_TIME_NONE) (D-15).

        Mirrors _on_eq_ramp_tick — k/_PAUSE_VOLUME_RAMP_TICKS
        interpolation factor, final-tick exact-target commit, state-cleanup.
        """
        state = self._pause_volume_ramp_state
        if state is None:
            self._pause_volume_ramp_timer.stop()
            return
        state["tick_index"] += 1
        k = state["tick_index"]
        target = state["target_volume"]
        start = state["start_volume"]
        if k >= self._PAUSE_VOLUME_RAMP_TICKS:
            # Final tick: commit exact 0 to playbin3.volume, then perform
            # the actual NULL teardown that pause() used to do inline.
            self._pipeline.set_property("volume", target)
            self._pause_volume_ramp_timer.stop()
            self._pause_volume_ramp_state = None
            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
            return
        t = float(k) / float(self._PAUSE_VOLUME_RAMP_TICKS)
        v = start + (target - start) * t
        self._pipeline.set_property("volume", v)

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
