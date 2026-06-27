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
import random
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


def _normalise_audio_codec(raw: str | None) -> str:
    """Map GStreamer TAG_AUDIO_CODEC string to Stream.codec vocabulary.

    Returns one of: 'MP3' | 'AAC' | 'FLAC' | 'OPUS' | 'OGG' | '' (unknown).
    Case-insensitive substring match. Called from _on_gst_tag (bus-loop thread);
    pure — no Qt/GStreamer imports. Phase 98.

    Mapping (per D-03 vocabulary and assumption A5):
    - 'layer 3' / 'layer3'  → 'MP3'  (MPEG-1/MPEG-2 Layer 3)
    - 'layer 2' / 'mp2'     → 'MP3'  (MP2 family maps to MP3 per A5)
    - 'aac'                 → 'AAC'
    - 'flac'                → 'FLAC'
    - exact 'opus'          → 'OPUS'
    - 'vorbis'              → 'OGG'
    - empty / None / other  → ''
    """
    if not raw:
        return ""
    s = raw.lower()
    if "layer 3" in s or "layer3" in s:
        return "MP3"
    if "layer 2" in s or "mp2" in s:
        return "MP3"
    if "aac" in s:
        return "AAC"
    if "flac" in s:
        return "FLAC"
    if s == "opus":
        return "OPUS"
    if "vorbis" in s:
        return "OGG"
    return ""


# Phase 62 / BUG-09: module logger (first logger in player.py).
# Surfaced at INFO via __main__.py per-logger setLevel — see Plan 03.
_log = logging.getLogger(__name__)

# Phase 90 D-08: staleness threshold for the "fetched-with-0 never re-fetches" trap.
# RESEARCH A1 rationale: SomaFM preroll catalogs are stable (weekly cadence);
# 7 days is long enough to avoid hammering the API on every play of a stuck
# station while short enough to self-heal within a week. Claude's Discretion.
_PREROLL_STALE_THRESHOLD_S: int = 7 * 24 * 3600


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

    def disarm_for_seek(self) -> None:
        """Disarm the tracker before a pipeline FLUSH seek (e.g. DVR seek).

        A FLUSH seek sends BUFFERING=0% immediately after the seek event,
        which would be interpreted as an underrun cycle opening if the tracker
        is already armed from the preceding fill.  Disarming forces the tracker
        to wait for the next BUFFERING=100% (post-seek fill complete) before
        watching for real underruns.

        Any open cycle is silently discarded — it is a false positive caused by
        the flush, not a real CDN hiccup.

        Threading: MUST be called from the main thread only (the same thread as
        _apply_live_dvr_seek / _on_playbin_state_changed).  Reads/writes
        _armed and _open which are also read by the bus-loop thread in
        observe().  The CPython GIL makes these bool writes atomic (Pattern 2 —
        same justification as _preroll_in_flight cross-thread reads).
        """
        self._open = False
        self._armed = False

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
    youtube_resolved           = Signal(str, bool, int)  # internal: (resolved_url, is_live, resolve_seq) -- queued back to main thread; int carries the _youtube_resolve_seq generation guard (Phase 95 / Pitfall 1)
    youtube_resolution_failed  = Signal(str, int) # internal: (msg, resolve_seq) -- queued back to main thread; int carries the per-worker generation stamp (Phase 95-04 / CR-01 fix, mirrors youtube_resolved success path)
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
    _error_recovery_requested  = Signal(int)     # bus-loop → main: run _handle_gst_error_recovery; int = _recovery_seq captured at error-POST time (Phase 95-02 generation guard)
    # Worker threads (twitch/youtube resolve) have no Qt event loop, so
    # QTimer.singleShot(0, ...) from those threads posts to a nonexistent loop
    # and the callback never runs. Queued signal marshals _try_next_stream
    # onto the main thread -- same pattern as _cancel_timers_requested.
    _try_next_stream_requested = Signal()        # worker → main: advance failover queue
    # Phase 83 D-05 / Pattern 1 — playbin3 about-to-finish fires on the GStreamer
    # streaming thread. Marshal to main via queued Signal so the disconnect +
    # _try_next_stream() call runs on the QThread (per qt-glib-bus-threading
    # Rule 2; Phase 43.1 fix commit f1333ed).
    #
    # CR-01 / WR-03 (Phase 83 code review): the signal carries the preroll
    # sequence number captured at about-to-finish-callback time. The main-
    # thread slot only acts if the sequence still matches _preroll_seq —
    # this defends against (a) a queued bus-error preroll recovery already
    # having advanced the queue (CR-01 double-pop), and (b) a stale slot
    # from a prior play()/stop() lifecycle arriving on a new station's
    # state (WR-03 cross-lifecycle leak).
    _preroll_about_to_finish_requested = Signal(int)
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
    # Phase 78 / BUG-09 Commit A: cumulative cycle counter for stats-for-nerds row.
    # Emitted from _on_underrun_cycle_closed (main-thread slot — the receiving end
    # of the queued _underrun_cycle_closed connection above). Both emitter and
    # receiver (MainWindow → NowPlayingPanel) are on the main thread, so the wire
    # uses DirectConnection (default) — qt-glib-bus-threading.md Pitfall 2 satisfied.
    underrun_count_changed    = Signal(int)      # main → MainWindow → NowPlayingPanel.set_underrun_count
    # Phase 84 / D-12 / BUG-09 Commit B: adaptive buffer-duration state Signal.
    # Emitted from main-thread paths only (`_maybe_grow_buffer_duration` and
    # `_reset_buffer_duration_to_baseline`, both invoked from main-thread slots:
    # `_on_underrun_cycle_closed`, `_try_next_stream`, `_on_preroll_about_to_finish`).
    # Receiver (MainWindow → NowPlayingPanel.set_buffer_duration in Plan 84-03)
    # is on the main thread, so the wire uses DirectConnection (default) —
    # qt-glib-bus-threading.md Pitfall 2 satisfied; 84-RESEARCH §Pattern 3.
    # Mirrors the Phase 78 underrun_count_changed shape one-for-one (84-PATTERNS §1).
    # WR-02 (Phase 84 code review): payload is (seconds, is_adapted) — slot derives
    # the "(adapted)" suffix from is_adapted, NOT by comparing seconds against
    # BUFFER_DURATION_S. Decouples the panel from the static baseline so future
    # bumps to BUFFER_DURATION_S can't collide with growth-step values (e.g. if the
    # baseline ever becomes 60s, growth-step-1 also lands at 60s — an int-only
    # Signal could not disambiguate baseline vs grown).
    buffer_duration_changed   = Signal(int, bool)   # (seconds, is_adapted) — main → MainWindow → NowPlayingPanel.set_buffer_duration

    # Phase 84 / D-11 / WR-03 (Phase 84 code review): adaptive growth schedule.
    # Class-level tuple so the cap-guard ties to len() (no separate magic number)
    # and the schedule is surfaced as one searchable constant. _growth_step indexes
    # this BEFORE incrementing: step 0 → _GROWTH_SCHEDULE[0] = 60; step 1 → [1] = 120.
    # When _growth_step == len(_GROWTH_SCHEDULE), the cap is held (no further growth).
    _GROWTH_SCHEDULE = (60, 120)

    # BUG-YT-LIVE-BUFFER / D-02: seconds to seek behind the live edge on YouTube
    # live HLS streams.  RFC 8216 positions hlsdemux2 only 3 * targetduration (6 s
    # for YouTube's 2 s segments) behind the live edge.  At that position the
    # effective download buffer is ~0-6 s — any CDN hiccup ≥ 1 segment-publish
    # period (2 s) starves it completely.  After the pipeline prerolls we issue a
    # one-shot SEEK_TYPE_END seek of -_LIVE_DVR_SEEK_OFFSET_S so GStreamer
    # repositions to (live_edge - hold_back - offset) ≈ live_edge - 36 s, backed by
    # the YouTube DVR window (7200 s of content always available).  This gives a
    # genuine ~30 s cushion of already-published segments against CDN hiccups.
    _LIVE_DVR_SEEK_OFFSET_S: int = 30

    # Phase 70 / DS-01: streaming/bus thread → main: persist sample_rate_hz / bit_depth
    # for the playing stream. Emitted with QueuedConnection on the receiver side
    # (MainWindow wires the slot in Plan 70-05 — qt-glib-bus-threading.md Rule 2).
    audio_caps_detected = Signal(int, int, int)  # stream_id, rate_hz, bit_depth
    audio_format_detected = Signal(int, str, int)  # stream_id, codec_norm, bitrate_kbps  (Phase 98)

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
        # Phase 16 invariant + Phase 84 / D-11 freshening:
        # GST_PLAY_FLAG_BUFFERING (0x100) is mandatory. Without it, playbin3
        # bypasses queue2 entirely on live HTTP audio — the buffer-duration /
        # buffer-size writes above are silently dropped and decodebin3's
        # internal multiqueue (~1s / ~100KB per pad) handles jitter against
        # tiny defaults, pinning the buffer-fill indicator near its
        # low-watermark (~10%). With the flag set, the property values
        # written above propagate to uridecodebin3 → urisourcebin → queue2
        # at URI-bind time (NOT mid-session — see _apply_pending_buffer_duration_to_pipeline
        # and 84-RESEARCH §D-11 for the mid-session-write fallback).
        # The literal `flags | 0x100` is regression-locked by
        # tests/test_playbin3_property_hygiene.py — do NOT change shape.
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

        # BUG-YT-LIVE-BUFFER / D-01: configure hlsdemux2 when it is added to the
        # pipeline so its internal segment-download buffer matches the user's
        # buffer-duration target.
        #
        # Background: In GStreamer >= 1.22, playbin3 selects hlsdemux2
        # (adaptivedemux2 family, rank 257) over the legacy hlsdemux (rank 256)
        # for HLS URLs.  hlsdemux2 manages its OWN internal download queue via
        # three properties (max-buffering-time, high-watermark-time,
        # low-watermark-time) that default to 30 s / 30 s / 0 s regardless of
        # playbin3.buffer-duration.  The existing Phase 84 stage-and-apply path
        # writes buffer-duration to playbin3, which propagates to
        # urisourcebin → queue2 — but queue2 is DOWNSTREAM of hlsdemux2 and
        # holds decoded audio, not compressed HLS segments.  hlsdemux2's own
        # download buffer remains at 30 s, so "raise buffer to 120 s" has no
        # effect on the live-stream underruns observed at ~63 min.
        #
        # Fix: listen for deep-element-added on the pipeline and configure
        # hlsdemux2's max-buffering-time / high-watermark-time to match
        # self._current_buffer_duration_s whenever the element is created.
        # The handler reads _current_buffer_duration_s (Python int, CPython-
        # atomic per the same justification as _preroll_in_flight cross-thread
        # reads) and writes two GObject properties — no Qt API, safe from any
        # GStreamer-internal thread.  The adaptive growth value staged by Phase
        # 84 _maybe_grow_buffer_duration IS picked up here automatically because
        # _apply_pending_buffer_duration_to_pipeline() (which updates
        # _current_buffer_duration_s) runs BEFORE _set_uri → set_state(PLAYING)
        # which triggers element creation and therefore this callback.
        self._pipeline.connect("deep-element-added", self._on_deep_element_added)

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
        # Phase 83 — malformed-preroll EOS bridge (live-spike Q3 RESOLVED).
        # IN-02 (Phase 83 code review): _on_gst_eos_during_preroll is the
        # ONLY message::eos handler in the entire codebase. The name implies
        # it is preroll-specific, but it is wired to ALL EOS messages — the
        # handler itself early-returns when _preroll_in_flight is False, so
        # behavior is correct. A future maintainer searching for EOS
        # handling for non-preroll streams will not find a separate handler
        # because there is no separate handler — this IS the one and only
        # EOS path. If a non-preroll EOS contract is ever needed (e.g.
        # live-stream-disconnect detection), it must be added INSIDE this
        # method's `if not self._preroll_in_flight: return` branch.
        bus.connect("message::eos", self._on_gst_eos_during_preroll)
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
        # Phase 83 D-05 / Pattern 1 — queue streaming-thread → main for preroll handoff.
        self._preroll_about_to_finish_requested.connect(
            self._on_preroll_about_to_finish, Qt.ConnectionType.QueuedConnection
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
        # Phase 98 (gap-closure redesign): accumulate-and-emit-on-change codec/
        # bitrate detection. _codec_tag_armed_for_stream_id is the stream we are
        # currently detecting for (0 = none); it stays set for the stream's whole
        # lifetime so codec/bitrate fields that arrive across SEPARATE tag messages
        # are all captured (FLAC sends its bitrate later than its codec — gap #2).
        # The accumulator never downgrades a known codec back to '' (YouTube
        # re-sends codec-less tags — gap G-01). Emission is de-duplicated on
        # _codec_detect_last so a stable stream stops emitting (no QueuedConnection
        # storm / FLAC lockup — gap G-02). A corrected bitrate arriving later
        # clears a false amber mismatch (gap #3). The accumulator is read on the
        # bus-loop thread and reset on main at stream-start; the arm-id read is
        # CPython-atomic (same justification as _preroll_in_flight).
        self._codec_tag_armed_for_stream_id: int = 0
        self._codec_detect_codec: str = ""
        self._codec_detect_bitrate: int = 0
        self._codec_detect_last: tuple = (None, None)

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

        # Phase 83 D-12 / D-13 / D-07 / T-83-10 — SomaFM preroll state.
        # Set/cleared on the main thread. _preroll_in_flight is read cross-thread
        # by _on_gst_tag (Pattern 2 — Python bool read is atomic in CPython).
        self._preroll_in_flight: bool = False
        self._last_preroll_played_at: Optional[float] = None  # D-12 throttle (monotonic; resets per launch)
        self._preroll_handler_id: int = 0  # 0 = no handler connected
        # CR-01 / WR-03 (Phase 83 code review): monotonic preroll-attempt
        # counter. Bumped by _start_preroll (new handoff opens) and by
        # _handle_gst_error_recovery's preroll branch (in-flight handoff
        # cancelled). The about-to-finish streaming-thread callback captures
        # _preroll_seq at emit time; the main-thread slot ignores any
        # delivery whose stamp != _preroll_seq. Cross-thread int read is
        # atomic in CPython (same justification as _preroll_in_flight).
        self._preroll_seq: int = 0
        # Phase 95 / Pitfall 1: monotonic YouTube-resolve generation counter,
        # mirroring _preroll_seq. Bumped by play() and invalidate_for_edit() so
        # any in-flight resolution started BEFORE an edit/restart no-ops when it
        # finally delivers (the worker captures _youtube_resolve_seq at spawn
        # time; _on_youtube_resolved rejects deliveries whose stamp !=
        # _youtube_resolve_seq). Cross-thread int read is atomic in CPython
        # (same justification as _preroll_seq / _preroll_in_flight).
        self._youtube_resolve_seq: int = 0
        # Phase 95-02 / gap-closure: monotonic error-recovery generation counter,
        # mirroring _preroll_seq and _youtube_resolve_seq. Bumped at the TOP of
        # play() (every restart, including invalidate_for_edit's self.play(station)
        # delegation) so any _error_recovery_requested POSTED before the restart is
        # stale. The bus-thread captures self._recovery_seq at emit time
        # (_on_gst_error) and carries it on the Signal payload; the main-thread
        # slot (_handle_gst_error_recovery) rejects deliveries whose stamp !=
        # current _recovery_seq. Cross-thread int read is atomic in CPython
        # (same justification as _preroll_seq / _preroll_in_flight).
        # D-04/D-05 no-restart branches of invalidate_for_edit do NOT bump this —
        # they leave the current generation valid so a legitimate same-session
        # recovery still toasts.
        self._recovery_seq: int = 0
        # Phase 95-03 / gap-closure: YouTube-resolve-in-flight gate. Set to True
        # ONLY when a YouTube resolve worker is spawned in _play_youtube; cleared
        # (seq-matched) ONLY when the CURRENT generation's resolution settles in
        # _on_youtube_resolved (success) or _on_youtube_resolution_failed (failure).
        # Consulted before failover.emit(None) in _try_next_stream and as an
        # early-return in _handle_gst_error_recovery so a bus error arriving during
        # the async resolve window never declares spurious exhaustion on the
        # transiently-empty queue. CPython-atomic bool read (same as _preroll_in_flight).
        # Additive to the _recovery_seq (95-02) and _youtube_resolve_seq (95-01) guards;
        # NOT a generation counter — a plain bool cleared on settle.
        self._youtube_resolve_in_flight: bool = False
        # Phase 95-04: _youtube_resolve_in_flight_seq (instance-attribute stamp) removed.
        # Staleness is now keyed off the carried seq on the youtube_resolution_failed
        # Signal (str, int) — the same pattern used by youtube_resolved (str, bool, int).
        # The overwrite-prone instance attribute is gone; no cross-call mutation risk.
        self._backfill_in_flight: set[int] = set()  # D-13 single-flight guard (T-83-10)

        # Phase 62 / BUG-09: cycle-tracker instance + station_id field.
        # Tracker mirrors Phase 47.1 D-14 sentinel reset lifecycle (Pitfall 3 —
        # bind_url is called from _try_next_stream alongside _last_buffer_percent reset).
        # _current_station_id mirrors _current_station_name for log-line context.
        self._tracker = _BufferUnderrunTracker()
        self._current_station_id: int = 0
        # Phase 78 / BUG-09 Commit A: cumulative cycle count (resets per launch,
        # CONTEXT.md Discretion — the file sink from Plan 78-01 is the persistent record).
        # Type-annotated zero — Pitfall 3 (never rely on set-on-first-write semantics).
        # See _growth_step block below for the Phase 84 / D-11 sibling state
        # (both are BUG-09 cycle-related cumulative state; IN-02 cross-ref).
        self._underrun_event_count: int = 0

        # Phase 84 / D-11 / BUG-09 Commit B: adaptive buffer-duration growth state.
        # Per playbin3 source inspection (84-RESEARCH §D-11), mid-session writes to
        # buffer-duration are silent no-ops; state is STAGED at cycle_close and APPLIED
        # at the next URI bind (_try_next_stream + _on_preroll_about_to_finish, BEFORE
        # the set_property("uri", ...) call). All three fields type-annotated per
        # Pattern S-3 / Pitfall 3 — never rely on set-on-first-write semantics.
        self._growth_step: int = 0                                     # 0=baseline, 1=60s, 2=120s (cap)
        self._current_buffer_duration_s: int = BUFFER_DURATION_S       # mirrors stats-for-nerds row
        self._pending_buffer_duration_s: int | None = None             # staged for next URI bind
        # WR-04 (Phase 84 code review): tracks the last buffer-duration value we
        # actually wrote to playbin3. Used by _apply_pending to skip redundant
        # property writes when the staged value matches what playbin3 already
        # holds — keeps the call-trace clean and avoids per-URL-bind no-op
        # writes (the common case post-CR-02 where reset stages baseline on
        # every station change). Seeded with the value written at __init__.
        self._last_applied_buffer_duration_s: int = BUFFER_DURATION_S

        # BUG-YT-LIVE-BUFFER / D-02: one-shot flag requesting a DVR seek after the
        # YouTube live pipeline first reaches PLAYING state.  Set by
        # _on_youtube_resolved when is_live=True; cleared by _apply_live_dvr_seek()
        # in the _on_playbin_state_changed main-thread slot.  Only True during the
        # brief window between _on_youtube_resolved and the first PLAYING transition.
        self._pending_live_dvr_seek: bool = False

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
        # Phase 95-02: bump the recovery generation so any _error_recovery_requested
        # that was POSTED (from the bus thread) BEFORE this restart is now stale.
        # Any delivery carrying the old _recovery_seq will no-op in
        # _handle_gst_error_recovery, preventing the spurious "Stream exhausted"
        # toast against the freshly-emptied queue of the new (async-resolving) URL.
        # invalidate_for_edit's restart branch delegates to play() (D-01), so
        # this single bump covers every restart path — no redundant bump elsewhere.
        self._recovery_seq += 1
        # Phase 95-04 / CR-01: bump the YouTube resolve generation on every restart
        # (not only on edits via invalidate_for_edit) so a plain station A->B switch
        # also invalidates an in-flight A-resolve for BOTH the success guard
        # (_on_youtube_resolved :2072) and the failure guard (_on_youtube_resolution_failed).
        # invalidate_for_edit bumps _youtube_resolve_seq before delegating here, so
        # the edit path double-bumps; that is harmless (monotonic counter, equality
        # compare at both ends, no off-by-one risk) — do NOT de-duplicate it.
        self._youtube_resolve_seq += 1
        # WR-02 (Phase 83 code review): tear down any leaked preroll handler
        # from a prior play()/stop() sequence so this play() starts from a
        # clean preroll state. Without this, a second SomaFM station play
        # after a stop() during a still-in-flight preroll would attach a
        # SECOND about-to-finish handler (the old connect-id was never
        # disconnected), causing double-pop of _streams_queue at the next
        # about-to-finish. Also unblocks the _on_gst_tag:787 ICY suppression
        # that would otherwise freeze Now Playing on the station name for a
        # subsequent non-SomaFM station. Mirror of stop()'s cleanup so the
        # invariant holds even when stop() was not called between plays.
        if self._preroll_in_flight or self._preroll_handler_id:
            self._preroll_seq += 1
            if self._preroll_handler_id:
                try:
                    self._pipeline.disconnect(self._preroll_handler_id)
                except (TypeError, RuntimeError):
                    pass
                self._preroll_handler_id = 0
            self._preroll_in_flight = False
        self._install_legacy_callbacks(on_title, on_failover, on_offline)
        self._current_station_name = station.name
        self._current_station_id = station.id   # Phase 62: log-line context
        self._is_first_attempt = True
        self._twitch_resolve_attempts = 0

        if not station.streams:
            self.title_changed.emit("(no streams configured)")
            return

        # Phase 82 D-01/D-03: honor per-station sticky preferred stream.
        # Explicit user pick (station.preferred_stream_id) wins over programmatic
        # preferred_quality hint per RESEARCH.md RQ4 precedence rule. If the id
        # is stale (no matching stream in station.streams), fall through to the
        # preferred_quality / order_streams default — D-05 "preferred first, not only".
        streams_by_position = order_streams(station.streams)
        preferred_by_id = None
        preferred_stream_id = getattr(station, "preferred_stream_id", None)
        if preferred_stream_id is not None:
            preferred_by_id = next(
                (s for s in station.streams if s.id == preferred_stream_id), None
            )

        preferred = preferred_by_id  # may be None
        if preferred is None and preferred_quality:
            preferred = next(
                (s for s in streams_by_position if s.quality == preferred_quality),
                None,
            )

        if preferred:
            queue = [preferred] + [s for s in streams_by_position if s is not preferred]
        else:
            queue = list(streams_by_position)

        self._streams_queue = queue
        # Phase 83 D-11 / D-12 / D-13 — SomaFM preroll gate.
        # The literal "SomaFM" is the drift-guard pin (Phase 74 D-02 CamelCase
        # convention; Phase 83 D-14 test pins this literal in non-comment lines).
        #
        # WR-05 (Phase 83 code review) — throttle semantics. D-12 explicitly
        # chose "throttle on most-recent ATTEMPTED preroll" (timestamp set at
        # preroll START in _start_preroll, not at handoff completion). The
        # consequence: if the user starts a SomaFM station, hits Stop within
        # 1 second (preroll never completes handoff), then plays a different
        # SomaFM station, the second preroll is suppressed for the full 10-
        # minute window even though no full preroll was ever heard.
        #
        # This is INTENTIONAL — moving the timestamp update into the about-
        # to-finish slot is the D-12 anti-pattern ("rapid replay would let a
        # second preroll start"). The drift-guard test
        # test_throttle_timestamp_set_on_start pins this behavior; do NOT
        # refactor the timestamp update into _on_preroll_about_to_finish
        # without revisiting D-12. Test test_wr05_throttle_documents_attempted_semantics
        # explicitly locks the start-attempt semantics so a "fix" that moves
        # the timestamp to handoff fails loudly.
        # Phase 90 D-03: throttle-skip probe (additive — no state change).
        # Separate read-only check fires ONLY for the suppress path (when
        # the combined gate below short-circuits on throttle). DO NOT
        # restructure the existing gate condition below this block.
        if (
            station.provider_name == "SomaFM"
            and self._last_preroll_played_at is not None
            and time.monotonic() - self._last_preroll_played_at <= 600
        ):
            logging.getLogger("musicstreamer.preroll").info(
                "preroll_skipped_throttle station_name=%r station_id=%d remaining_s=%.0f",
                station.name, station.id,
                600 - (time.monotonic() - self._last_preroll_played_at),
            )
        if (
            station.provider_name == "SomaFM"
            and (self._last_preroll_played_at is None
                 or time.monotonic() - self._last_preroll_played_at > 600)
        ):
            urls = list(getattr(station, "prerolls", []) or [])
            if urls:
                preroll_url = random.choice(urls)        # D-06 — UNCHANGED
                logging.getLogger("musicstreamer.preroll").info(
                    "preroll_start station_name=%r station_id=%d url=%r",
                    station.name, station.id, preroll_url,
                )
                self._start_preroll(preroll_url)
                return  # _on_preroll_about_to_finish triggers _try_next_stream
            elif (
                getattr(station, "prerolls_fetched_at", None) is None
                and station.id not in self._backfill_in_flight
            ):
                # D-13 lazy backfill; non-blocking. Worker discards station.id from
                # _backfill_in_flight in its finally clause (T-83-10 single-flight).
                logging.getLogger("musicstreamer.preroll").info(
                    "preroll_skipped_empty station_name=%r station_id=%d reason=unfetched",
                    station.name, station.id,
                )
                self._backfill_in_flight.add(station.id)
                threading.Thread(
                    target=self._preroll_backfill_worker,
                    args=(station.id, station.name),
                    daemon=True,
                ).start()
            else:
                # D-04 / Pitfall 5: fetched, genuinely-empty channel.
                logging.getLogger("musicstreamer.preroll").info(
                    "preroll_skipped_empty station_name=%r station_id=%d reason=fetched_empty",
                    station.name, station.id,
                )
                # D-08 (Phase 90): close the "fetched-with-0 never re-fetches" trap.
                # Fires ONLY when fetched_at IS NOT NULL (mutually exclusive with D-13
                # branch above which requires fetched_at IS NULL). Worker discards
                # station.id from _backfill_in_flight in its finally (T-83-10 D-09).
                if (
                    getattr(station, "prerolls_fetched_at", None) is not None
                    and int(time.time()) - station.prerolls_fetched_at > _PREROLL_STALE_THRESHOLD_S
                    and station.id not in self._backfill_in_flight
                ):
                    self._backfill_in_flight.add(station.id)
                    threading.Thread(
                        target=self._preroll_backfill_worker,
                        args=(station.id, station.name),
                        daemon=True,
                    ).start()
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
        # Phase 95-04 / CR-01: clear the YouTube-resolve-in-flight gate on stop() so
        # a gate stranded True by a prior _play_youtube (e.g. user stops before the
        # worker delivers) does not silently suppress future failover.emit(None).
        # Also bump _youtube_resolve_seq so a YouTube worker still in flight when
        # stop() is called has its seq superseded; its late failure delivery carries
        # the old seq, is rejected as stale, and does NOT reach _try_next_stream to
        # emit a spurious failover(None) into the stopped player (closes IN-01).
        self._youtube_resolve_in_flight = False
        self._youtube_resolve_seq += 1
        # WR-02 (Phase 83 code review): tear down any in-flight preroll
        # cleanly so a subsequent play() does not inherit a leaked handler-id
        # (which would fire double about-to-finish slots — one for the dead
        # handler attached during the prior preroll, one for the new
        # connect) and a stale _preroll_in_flight = True (which would
        # suppress ICY titles on the next non-SomaFM station via the
        # _on_gst_tag:787 guard). _preroll_seq is bumped so any queued
        # about-to-finish slot from the dead preroll arrives stale (CR-01
        # contract).
        if self._preroll_in_flight or self._preroll_handler_id:
            self._preroll_seq += 1
            if self._preroll_handler_id:
                try:
                    self._pipeline.disconnect(self._preroll_handler_id)
                except (TypeError, RuntimeError):
                    pass
                self._preroll_handler_id = 0
            self._preroll_in_flight = False
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

        WR-05 (Phase 84 code review): also increments _underrun_event_count
        so the cumulative cycle counter symmetric with _on_underrun_cycle_closed
        (which the comment block there calls out as "every NON-SHUTDOWN outcome";
        this method handles the shutdown outcome's counter parity). No emit is
        performed here: receivers (MainWindow → NowPlayingPanel) are being torn
        down during closeEvent; the in-process counter is what matters, the
        durable record is the file-sink log line written above.
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
            # WR-05: count parity with _on_underrun_cycle_closed. NO emit (Signal
            # receivers are torn down during closeEvent and any queued slot
            # would race the QApplication.quit() that follows).
            self._underrun_event_count += 1
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
        # Phase 95-02: carry the recovery generation captured at POST time.
        # An int read on the bus thread is atomic in CPython (same justification
        # as _preroll_seq / _preroll_about_to_finish_requested). The stamp is
        # compared at RUN time in _handle_gst_error_recovery to reject stale
        # (pre-restart) deliveries.
        self._error_recovery_requested.emit(self._recovery_seq)

    def _handle_gst_error_recovery(self, recovery_seq: int = -1) -> None:
        # Phase 95-02 generation guard — MUST sit ABOVE the _recovery_in_flight
        # coalescing check so a stale pre-restart recovery never reaches
        # _try_next_stream() with the freshly-emptied queue.
        #
        # The two-part guard:
        #   (a) `recovery_seq != -1` — the -1 sentinel is the default for no-arg
        #       direct callers (tests, internal calls without a stamp). It means
        #       "no explicit generation → treat as current → SKIP the staleness
        #       check". This preserves every existing direct test caller even when
        #       play() has already bumped _recovery_seq to ≥1 before the no-arg
        #       call (a default of 0 would evaluate `0 != 1` → True → early-return
        #       and regress those tests).
        #   (b) `recovery_seq != self._recovery_seq` — an explicitly-stamped
        #       delivery whose stamp < current was POSTED before the most recent
        #       play()/invalidate restart; the OLD exhausted stream's error. Ignoring
        #       it prevents the spurious "Stream exhausted" toast against the
        #       freshly-emptied queue of the new (still-resolving) URL. A genuine
        #       current-generation exhaustion's error is posted AFTER the restart,
        #       so its stamp == _recovery_seq and it falls through to _try_next_stream.
        if recovery_seq != -1 and recovery_seq != self._recovery_seq:
            return
        # Gap-05 fix: coalesce cascading bus errors for a single failing URL.
        # playbin3 may emit N errors (source + demuxer + decoder) during
        # pipeline teardown for one broken stream. Without this guard each
        # error would pop the next queue entry, draining the queue in
        # milliseconds and yielding a spurious "Stream exhausted".
        # See .planning/debug/stream-exhausted-premature.md for the trace.
        if self._recovery_in_flight:
            return
        # Phase 95-03: YouTube-resolve-in-flight gate. While the CURRENT generation's
        # YouTube resolution is still pending, a pipeline error recovery is pointless
        # (the new URI has not been handed to playbin3 yet). Early-return WITHOUT
        # setting _recovery_in_flight so a later legitimate recovery after the gate
        # clears is not coalesced away by the _recovery_in_flight guard above.
        # Placed AFTER the _recovery_seq (95-02) and _recovery_in_flight (Gap-05)
        # guards so V11/V12/V13 (which leave _youtube_resolve_in_flight=False) are
        # unaffected; only the new V14 scenario (gate set + current-seq delivery) is
        # early-returned here.
        if self._youtube_resolve_in_flight:
            return
        self._recovery_in_flight = True
        self._cancel_timers()
        # Phase 83 D-09 — preroll error path. Don't retry a different preroll;
        # immediately advance to the station's actual stream. No second preroll
        # selection — user experience is "slightly faster intro than expected."
        #
        # CR-01: bump _preroll_seq so any queued about-to-finish slot from the
        # NOW-dead preroll arrives stale and no-ops at the seq check, instead
        # of popping _streams_queue a second time and clobbering the stream
        # _try_next_stream is about to start below.
        if self._preroll_in_flight:
            self._preroll_seq += 1
            if self._preroll_handler_id:
                try:
                    self._pipeline.disconnect(self._preroll_handler_id)
                except (TypeError, RuntimeError):
                    pass
                self._preroll_handler_id = 0
            self._preroll_in_flight = False
            self._try_next_stream()
            QTimer.singleShot(0, self._clear_recovery_guard)
            return
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

    def _arm_codec_detect_for_stream(self, stream_id: int) -> None:
        """Phase 98 gap-closure: (re)arm codec/bitrate detection for a stream.

        Idempotent per stream: when ``stream_id`` is already the armed stream the
        accumulated codec/bitrate state is preserved — a rebuffer PLAYING
        transition must NOT wipe what we already detected. A genuinely new stream
        id clears the accumulator so detection starts fresh. Called from every
        stream-start boundary: ``_set_uri`` (direct streams), the gapless preroll
        handoff (SomaFM), and ``_on_playbin_state_changed`` (PLAYING transitions).
        Main-thread only.
        """
        if stream_id and stream_id == self._codec_tag_armed_for_stream_id:
            return
        self._codec_tag_armed_for_stream_id = stream_id
        self._codec_detect_codec = ""
        self._codec_detect_bitrate = 0
        self._codec_detect_last = (None, None)

    def _on_gst_tag(self, bus, msg) -> None:
        taglist = msg.parse_tag()
        found_title, value = taglist.get_string(Gst.TAG_TITLE)
        # Audio arrived -- cancel failover timer on the main thread via queued
        # signal. Bus-loop thread has no Qt event loop, so singleShot vanishes.
        self._cancel_timers_requested.emit()
        # Phase 83 D-07 — suppress preroll's m4a title tag so Now Playing keeps
        # showing the station name through the ~5s ID. Set on main in Player.play
        # (before set_uri to the preroll URL) and cleared in _on_preroll_about_to_finish
        # (also main). This read is cross-thread; Python bool read is atomic. Worst
        # case (Pitfall 2 — m4a tag arrives between disconnect and flag clear) is
        # one frame of preroll title leaked, ~30ms, acceptable per D-07's
        # "no UI flicker" intent (not "zero leak").
        # Phase 98 Critical Sequencing: preroll guard moved BEFORE codec block and
        # the title early-return so it covers both paths (98-PATTERNS.md Critical
        # Sequencing Note).
        if self._preroll_in_flight:
            return

        # --- Phase 98 (gap-closure): accumulate codec/bitrate across tags ---
        # Codec and bitrate frequently arrive in SEPARATE tag messages and a
        # stream re-sends partial tags; merge them into a per-stream accumulator
        # and emit only when the merged (codec, bitrate) actually changes. This
        # captures FLAC's late bitrate (gap #2), lets a corrected bitrate clear a
        # false amber mismatch (gap #3), never blanks a known codec with a later
        # codec-less tag (gap G-01), and de-dups so a stable stream stops emitting
        # (no main-thread emit storm / FLAC lockup, gap G-02).
        if self._codec_tag_armed_for_stream_id:
            sid = self._codec_tag_armed_for_stream_id
            found_codec, raw_codec = taglist.get_string(Gst.TAG_AUDIO_CODEC)
            found_nb, nb_bps = taglist.get_uint(Gst.TAG_NOMINAL_BITRATE)
            found_b, b_bps = taglist.get_uint(Gst.TAG_BITRATE)
            codec_this = _normalise_audio_codec(raw_codec if found_codec else None)
            bitrate_this = 0
            if found_nb and nb_bps > 0:
                bitrate_this = nb_bps // 1000  # Pitfall 4: integer division
            elif found_b and b_bps > 0:
                bitrate_this = b_bps // 1000
            # Merge: never downgrade a known field back to empty/zero.
            if codec_this:
                self._codec_detect_codec = codec_this
            if bitrate_this:
                self._codec_detect_bitrate = bitrate_this
            current = (self._codec_detect_codec, self._codec_detect_bitrate)
            if (self._codec_detect_codec or self._codec_detect_bitrate) and (
                current != self._codec_detect_last
            ):
                self._codec_detect_last = current
                self.audio_format_detected.emit(
                    sid, self._codec_detect_codec, self._codec_detect_bitrate
                )

        # --- existing title path (unchanged) ---
        if not found_title:
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
        # Phase 98 Pattern 1b: keep codec/bitrate detection armed for the current
        # stream on each PLAYING transition. _arm_codec_detect_for_stream is
        # idempotent — it preserves the accumulator for the SAME stream (a rebuffer
        # must not re-detect from scratch) and only resets it for a new stream.
        if self._current_stream:
            self._arm_codec_detect_for_stream(self._current_stream.id)
        # BUG-YT-LIVE-BUFFER / D-02: one-shot DVR seek for YouTube live streams.
        # Pipeline is now in PLAYING state (preroll complete; seek range valid).
        if self._pending_live_dvr_seek:
            self._pending_live_dvr_seek = False
            self._apply_live_dvr_seek()

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
        """Failover timeout: no audio arrived within BUFFER_DURATION_S seconds.

        WR-01 (Phase 83 code review): _start_preroll arms this same timer as
        a watchdog for stuck/dead preroll URLs. If the timer fires while a
        preroll is in flight, we must perform the same cleanup as the bus-
        error preroll branch (CR-01: bump _preroll_seq, disconnect handler,
        clear flag) BEFORE calling _try_next_stream — otherwise the handler
        stays connected and a late about-to-finish callback from the dead
        preroll could pop the queue a second time (the same race CR-01
        defends against on the bus-error path).
        """
        if self._preroll_in_flight:
            self._preroll_seq += 1  # CR-01: invalidate any in-flight queued slot
            if self._preroll_handler_id:
                try:
                    self._pipeline.disconnect(self._preroll_handler_id)
                except (TypeError, RuntimeError):
                    pass
                self._preroll_handler_id = 0
            self._preroll_in_flight = False
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
        # Phase 78 / BUG-09 Commit A: increment + emit on EVERY NON-SHUTDOWN
        # cycle close (recovered / failover / stop / pause — mirrors the
        # file-sink one-line-per-cycle semantics per CONTEXT <specifics>).
        # Note: shutdown cycles route through shutdown_underrun_tracker, which
        # also increments this counter directly (no emit there — receivers
        # are torn down at app close). See WR-05.
        self._underrun_event_count += 1
        self.underrun_count_changed.emit(self._underrun_event_count)
        # Phase 84 / D-11 + CR-01 (Phase 84 code review): growth fires ONLY on
        # actual queue2 recovery, NOT on user terminators (pause/stop) or
        # queue-advancement events (failover/preroll). User input must not
        # penalise the next session's startup latency.
        if record.outcome == "recovered":
            self._maybe_grow_buffer_duration()

    def _maybe_grow_buffer_duration(self) -> None:
        """Phase 84 / D-11 / BUG-09 Commit B — STAGE next adaptive
        buffer-duration value after an in-session underrun cycle close.

        Schedule: 30s → 60s → 120s (cap at len(_GROWTH_SCHEDULE)). The
        schedule itself is the class-level tuple ``Player._GROWTH_SCHEDULE``
        (WR-03 — Phase 84 code review): replacing the prior dict-literal
        lookup ties the cap-guard to the schedule's length (no separate
        magic number) and surfaces the schedule for future tuning. The
        prior dict form raised KeyError off-by-one if the cap-guard were
        ever refactored incorrectly; the tuple form keeps the failure
        mode "no-op at cap" by gating with ``>= len(...)`` before indexing.

        Per 84-RESEARCH §D-11 Resolution: the mid-session
        ``set_property("buffer-duration", N)`` write is a silent no-op for
        the currently-playing stream on playbin3 — the value is staged on
        ``_pending_buffer_duration_s`` here and applied at the next URI
        bind by ``_apply_pending_buffer_duration_to_pipeline``. UI mirror
        (``_current_buffer_duration_s``) updates immediately so the
        stats-for-nerds row reflects the new target as soon as the
        underrun cycle closes.

        Cap-guard: subsequent cycle_close at the cap is a no-op (no
        spurious Signal re-emit — Pitfall 3 / Pattern S-3 invariant).
        """
        if self._growth_step >= len(self._GROWTH_SCHEDULE):
            return  # cap held — no further growth, no Signal re-emit
        new_s = self._GROWTH_SCHEDULE[self._growth_step]  # index BEFORE increment
        self._growth_step += 1
        self._pending_buffer_duration_s = new_s
        self._current_buffer_duration_s = new_s
        # WR-02: is_adapted=True — any growth-step write is by definition adapted.
        self.buffer_duration_changed.emit(new_s, True)

    def _on_underrun_dwell_elapsed(self) -> None:
        """Main-thread QTimer.timeout slot (Phase 62 / D-07). Cycle has been
        open ≥ 1500ms; notify MainWindow to consider showing the toast
        (cooldown gated there, D-08)."""
        self.underrun_recovery_started.emit()

    # ------------------------------------------------------------------ #
    # Failover queue
    # ------------------------------------------------------------------ #

    def _apply_pending_buffer_duration_to_pipeline(self) -> None:
        """Phase 84 / D-11 / BUG-09 Commit B — APPLY any staged
        buffer-duration to playbin3 BEFORE the next URI bind.

        Per 84-RESEARCH §D-11 Resolution: mid-session writes to playbin3's
        ``buffer-duration`` property are silent no-ops on the active
        uridecodebin3/urisourcebin/queue2 chain. Writing the property
        BEFORE the ``set_property("uri", ...)`` causes
        ``uridecodebin3.new_source_handler`` to read the updated value
        from playbin3's struct field and propagate it down at URI-bind
        time — this is the canonical fallback shape.

        No-op when ``_pending_buffer_duration_s is None`` (no growth or
        reset has staged a value since the last apply).

        NOTE: ``buffer-size`` is NOT adaptive in this phase — only
        ``buffer-duration`` grows (CONTEXT D-11). The dash-form
        ``"buffer-duration"`` property string is MANDATORY — Wave 0
        hygiene gate bans the underscore form ``"buffer_duration"``.
        """
        if self._pending_buffer_duration_s is None:
            return
        # WR-04 (Phase 84 code review): idempotency guard — skip the actual
        # property write when the staged value equals what playbin3 already
        # holds, but still clear the pending stage. After CR-02 reorder, reset
        # stages baseline at every station change; without this guard, the
        # common no-prior-growth path would re-write the baseline value on
        # every URL bind (harmless but call-trace noise). _last_applied is
        # seeded with the BUFFER_DURATION_S written at __init__ (player.py
        # near line 327) so the first post-init no-growth station change
        # correctly skips.
        if self._pending_buffer_duration_s != self._last_applied_buffer_duration_s:
            self._pipeline.set_property(
                "buffer-duration", self._pending_buffer_duration_s * Gst.SECOND
            )
            self._last_applied_buffer_duration_s = self._pending_buffer_duration_s
        self._pending_buffer_duration_s = None

    def _reset_buffer_duration_to_baseline(self) -> None:
        """Phase 84 / D-11 / BUG-09 Commit B — per-URL reset of adaptive
        buffer-duration state back to the BUFFER_DURATION_S baseline.

        Mirrors Phase 47.1 D-14 sentinel reset and Phase 62 D-04
        ``_underrun_armed`` per-URL reset lifecycle (84-RESEARCH §D-11).
        Each new station / preroll-handoff URL starts fresh; growth does
        not leak across station changes.

        Pitfall 3 / Pattern S-3 invariant: early-return when already at
        baseline — never emit a spurious Signal that would cause the
        stats-for-nerds row to "twitch" at every URL bind even when no
        growth happened.

        On reset, ``_pending_buffer_duration_s`` is set to
        ``BUFFER_DURATION_S`` (NOT ``None``) so the baseline value is
        written to playbin3 at the next ``_apply_pending`` call —
        flushes any prior growth value that may have been applied to a
        previous URL session.
        """
        if (
            self._growth_step == 0
            and self._current_buffer_duration_s == BUFFER_DURATION_S
        ):
            return  # already at baseline — no Signal re-emit (Pitfall 3)
        self._growth_step = 0
        self._current_buffer_duration_s = BUFFER_DURATION_S
        self._pending_buffer_duration_s = BUFFER_DURATION_S
        # WR-02: is_adapted=False — baseline reset is never the adapted state.
        self.buffer_duration_changed.emit(BUFFER_DURATION_S, False)

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
            # Phase 95-03: while a YouTube resolve is in flight the queue is
            # transiently empty — do NOT declare exhaustion. The pending resolve
            # will either _set_uri (success) or legitimately exhaust (failure,
            # after the gate clears in _on_youtube_resolution_failed).
            if self._youtube_resolve_in_flight:
                return
            # All streams exhausted
            self.failover.emit(None)
            return
        stream = self._streams_queue.pop(0)
        self._current_stream = stream
        self._last_buffer_percent = -1  # 47.1 D-14: reset so new URL's first buffer emits (Pitfall 3)
        # Phase 84 / D-11 per-URL reset + CR-02 (Phase 84 code review): reset
        # MUST run BEFORE the apply so the BASELINE value (not the prior URL's
        # grown value) is what reaches playbin3 at this URI bind. _try_next_stream
        # is the station-change boundary per CONTEXT D-11 ("each new station starts
        # fresh"); reset stages _pending = BUFFER_DURATION_S and apply then writes it.
        # If the order were reversed (apply → reset), the apply would push the prior
        # URL's grown value (e.g. 60s) to playbin3 for the new station, and the
        # baseline would only land at the NEXT _try_next_stream call.
        self._reset_buffer_duration_to_baseline()
        # Phase 84 / D-11: apply staged buffer-duration BEFORE binding the new URI.
        # uridecodebin3.new_source_handler reads playbin3.buffer_duration at URI-bind
        # time; missing this ordering means the staged value is silently ignored.
        self._apply_pending_buffer_duration_to_pipeline()
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
            self._failover_timer.start(self._current_buffer_duration_s * 1000)

    def _set_uri(self, uri: str) -> None:
        # Phase 95-04 / CR-01: _set_uri is the direct/non-YouTube URI funnel.
        # Clear the in-flight gate here so a YouTube->direct restart mid-resolve cannot
        # leave the gate stranded True. _on_youtube_resolved already clears the gate
        # before calling _set_uri (:2076), so this is an idempotent no-op for the
        # success path; it only matters for the direct-stream-restart path that bypasses
        # _play_youtube entirely. The _try_next_stream gate consult runs BEFORE _set_uri,
        # so clearing here does not suppress a legitimate gate-guarded wait.
        self._youtube_resolve_in_flight = False
        uri = aa_normalize_stream_url(uri)  # WIN-01 / D-01: DI.fm HTTPS->HTTP at URI funnel
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
        self._pipeline.set_property("uri", uri)
        # Phase 98: arm codec/bitrate detection for the new stream BEFORE
        # set_state(PLAYING) (gap G-03 / code-review WR-01). Arming after PLAYING
        # left a window where a new-stream tag was accumulated under the PREVIOUS
        # stream's id, painting a false mismatch in the panel. Arming first means
        # any tag the bus-loop thread sees for this pipeline carries the correct id.
        self._arm_codec_detect_for_stream(
            self._current_stream.id if self._current_stream else 0
        )
        self._pipeline.set_state(Gst.State.PLAYING)
        # Phase 70 / DS-01: install a fresh caps watch on the new pipeline lifecycle.
        # MUST happen AFTER set_state(PLAYING) so playbin3 starts negotiating streams.
        self._arm_caps_watch_for_current_stream()

    # ------------------------------------------------------------------ #
    # Phase 83 — SomaFM preroll cluster (D-05, D-09, D-12; live-spike Q3 bridge)
    # ------------------------------------------------------------------ #

    def _start_preroll(self, preroll_url: str) -> None:
        """Phase 83 D-05 / D-12. Main-thread call. Wires playbin3 to play
        ``preroll_url``, attaches a one-shot about-to-finish handler that
        schedules the station-stream handoff via queued Signal.

        ``_last_preroll_played_at`` is set HERE (preroll START), not in the
        about-to-finish slot — D-12 explicit anti-pattern is "update on
        handoff" (rapid replay would let a second preroll start).

        CR-01 / WR-03: bumps ``_preroll_seq`` so any in-flight queued
        about-to-finish slot from a prior preroll arrives stale and no-ops
        at the seq check (idempotent re-entry guard).

        IN-03 (Phase 83 code review) — PRECONDITION: callers must invoke
        ``self._cancel_timers()`` and reset ``self._streams_queue`` /
        ``self._recovery_in_flight`` before calling this method. ``play()``
        is the only current caller and satisfies this contract at lines
        543-545. ``play()``'s WR-02 fix also performs the leaked-preroll-
        handler cleanup defensively before reaching here. If a new caller
        (e.g. a "retry preroll" feature) is added, it must satisfy the
        same hygiene or this method will: (a) leak a failover-timer arm
        on top of any prior failover timer (now harmless thanks to the
        WR-01 arm below, which restarts a single-shot QTimer either way),
        (b) overwrite ``_preroll_handler_id`` losing the old connect-id
        (the WR-02 defensive cleanup in ``play()`` and ``stop()`` handles
        this for current callers; new callers must call into the same
        path or replicate it).
        """
        self._preroll_seq += 1  # CR-01 / WR-03: invalidate any stale queued slot
        self._preroll_in_flight = True
        self._last_preroll_played_at = time.monotonic()
        self._preroll_handler_id = self._pipeline.connect(
            "about-to-finish", self._on_preroll_about_to_finish_callback
        )
        self._set_uri(preroll_url)
        # WR-01 (Phase 83 code review): arm the failover-timeout watchdog
        # so a stuck/dead preroll URL falls through to the station's actual
        # stream after BUFFER_DURATION_S. Without this, a silently down
        # preroll leaves the UI showing 0:00 indefinitely — only bus-error
        # or EOS would eventually recover, but neither fires for connection
        # hangs (regression vs. pre-Phase 83 _try_next_stream:1087 arm).
        # _on_timeout above routes through the preroll-cleanup branch
        # (disconnect + flag clear + seq bump) before advancing.
        self._failover_timer.start(self._current_buffer_duration_s * 1000)

    def _on_preroll_about_to_finish_callback(self, pipeline) -> None:
        """Phase 83 D-05 / Pattern 1 — GStreamer streaming-thread callback.
        ONLY emits the queued Signal. NEVER call set_property or any Qt API
        from this body (qt-glib-bus-threading Rule 2; Phase 43.1 f1333ed).

        CR-01 / WR-03: capture ``_preroll_seq`` at emit time and pass it
        through the queued Signal. The main-thread slot rejects deliveries
        whose stamp no longer matches the current ``_preroll_seq``
        (handoff cancelled by bus-error recovery, or this slot belongs to
        a prior play()/stop() lifecycle). Cross-thread int read is atomic
        in CPython."""
        self._preroll_about_to_finish_requested.emit(self._preroll_seq)

    def _on_preroll_about_to_finish(self, expected_seq: int = 0) -> None:
        """Phase 83 D-05 (UAT-corrected) — main-thread slot wired via
        QueuedConnection.

        Performs a GAPLESS URI handoff on playbin3's still-PLAYING pipeline:
        pops _streams_queue[0], mirrors _try_next_stream's bookkeeping
        (tracker bind, failover-timer arm, _last_buffer_percent reset,
        elapsed-timer first-attempt seeding), and sets the next URI via a
        plain pipeline.set_property("uri", ...) — NO set_state(NULL), NO
        set_state(PLAYING). playbin3 plays the preroll to EOS and transitions
        seamlessly to the station stream.

        For YouTube/Twitch URLs (which require async resolution via
        _play_youtube / _play_twitch), the slot falls back to the legacy
        _try_next_stream() path — the gapless set_property idiom only works
        for URLs playbin3 can stream directly.

        For empty _streams_queue (defensive), falls back to
        _try_next_stream() which emits failover(None) as today.

        CR-01 / WR-03 cross-thread race guards (Phase 83 code review):

        1. ``expected_seq != self._preroll_seq``: a parallel slot already
           ran (bus-error preroll recovery in _handle_gst_error_recovery
           bumped the seq, or this delivery belongs to a prior preroll
           lifecycle). Return immediately — the queue must NOT be popped
           a second time (would replace the in-progress stream mid-track).

        2. ``not self._preroll_in_flight``: same condition expressed
           through the existing flag — defense in depth. ``stop()`` and
           the bus-error path both clear this; we must respect that.

        ``expected_seq`` has a default of 0 so test paths that call this
        slot directly (synchronously, bypassing the queued Signal) work
        unchanged: ``_preroll_seq`` is 0 at construction and remains 0
        unless ``_start_preroll`` runs; if tests do call ``play()`` →
        ``_start_preroll`` first, ``_preroll_seq`` becomes >= 1 and the
        guard would reject a manual direct call to the slot. Such tests
        already pass ``_preroll_seq`` implicitly (covered by Phase 83
        regression — see test_player.py).
        """
        if expected_seq != self._preroll_seq:
            return  # CR-01: stale slot — bus-error or new preroll superseded this one
        if not self._preroll_in_flight:
            return  # CR-01 defense in depth — flag already cleared by parallel path
        if self._preroll_handler_id:
            try:
                self._pipeline.disconnect(self._preroll_handler_id)
            except (TypeError, RuntimeError):
                pass  # already disconnected (e.g. bus-error path took it)
            self._preroll_handler_id = 0
        self._preroll_in_flight = False
        # Phase 90 D-03: log handoff completion (additive — before queue check).
        logging.getLogger("musicstreamer.preroll").info(
            "preroll_handoff_complete station_name=%r station_id=%d",
            self._current_station_name, self._current_station_id,
        )
        # Empty-queue defensive: fall back to legacy path (emits failover(None)).
        if not self._streams_queue:
            self._try_next_stream()
            return
        head_url = self._streams_queue[0].url.strip()
        # Async-resolution providers cannot use the gapless set_property idiom
        # (playbin3 needs a streamable URL, not a YouTube/Twitch page URL).
        # Fall back to the legacy _try_next_stream path which dispatches to
        # _play_youtube / _play_twitch.
        if (
            "youtube.com" in head_url
            or "youtu.be" in head_url
            or "twitch.tv" in head_url
        ):
            self._try_next_stream()
            return
        # Gapless URI handoff for direct HTTP(S) streams (the SomaFM ICE-relay
        # case — D-11 provider gate guarantees this codepath only fires for
        # SomaFM, and SomaFM streams are direct HTTP(S) URLs).
        stream = self._streams_queue.pop(0)
        self._current_stream = stream
        # Phase 98 gap-closure (SomaFM): the gapless handoff swaps the URI with no
        # set_state(NULL/PLAYING) and no _set_uri call, so neither _set_uri nor
        # _on_playbin_state_changed arms codec detection for the real stream. Arm
        # it here or the Stats-for-Nerds rows never populate after a preroll jingle.
        self._arm_codec_detect_for_stream(stream.id)
        self._last_buffer_percent = -1  # Pitfall 3 — mirror _try_next_stream:1056
        # Force-close any cycle on the OUTGOING URL with a "preroll" outcome
        # (distinguish from "failover" so analytics see this is a gapless
        # handoff, not a stream-error failover). Ordering load-bearing:
        # close record must carry the OLD url; bind to NEW url comes after.
        prior_close = self._tracker.force_close("preroll")
        if prior_close is not None:
            self._underrun_cycle_closed.emit(prior_close)
        self._tracker.bind_url(
            station_id=self._current_station_id,
            station_name=self._current_station_name,
            url=stream.url,
        )
        self._underrun_dwell_timer.stop()
        # Elapsed-timer first-attempt seeding (mirror of _try_next_stream:1073-1077).
        # Without this block the user-facing elapsed-time display freezes at 0
        # across the preroll→stream handoff (analytics regression). The preroll
        # path enters this slot with _is_first_attempt == True; neither
        # _start_preroll nor _on_preroll_about_to_finish_callback touches it.
        if self._is_first_attempt:
            self._elapsed_seconds = 0
            self._elapsed_timer.start()
        self._is_first_attempt = False
        # Phase 84 / D-11: apply staged buffer-duration BEFORE the gapless URI swap
        # (Pitfall 2 — SomaFM users hit gapless preroll handoff hourly; missing this
        # site silently regresses adaptive growth across every preroll cycle).
        # CR-02 (Phase 84 code review): do NOT call _reset_buffer_duration_to_baseline
        # here. Preroll → station-stream handoff is the SAME logical user session
        # (one station, two URLs); per CONTEXT D-11 "each new station starts fresh"
        # the reset is per-station-change semantics, NOT per-URI-bind. Resetting
        # here would erase adaptive growth at every SomaFM hourly preroll cycle,
        # defeating Commit B's intent for the SomaFM cluster (3 of 5 long events
        # per harvest-week data summary).
        self._apply_pending_buffer_duration_to_pipeline()
        # Gapless: set URI on the still-PLAYING pipeline. NO set_state(NULL),
        # NO set_state(PLAYING) — playbin3 transitions to the new URI at the
        # preroll's EOS automatically. This is the canonical playbin3 gapless
        # idiom; live-spike (2026-05-22 Linux GStreamer 1.28.2) confirms
        # about-to-finish + plain set_property("uri", ...) works under the
        # MusicStreamer playbin3 configuration (83-RESEARCH §Q1 RESOLVED).
        self._pipeline.set_property("uri", aa_normalize_stream_url(stream.url))
        # WR-04 (Phase 83 code review): re-arm the caps watch on the post-
        # handoff stream. The gapless URI swap deliberately does NOT cycle
        # set_state(NULL → PLAYING), so the _on_playbin_state_changed
        # Pattern 1b path (which normally calls _arm_caps_watch_for_current_stream)
        # does not fire. Without this explicit arm, _current_stream is now
        # set but the pad watch from _start_preroll's _set_uri call is
        # still bound to a stream_id that no longer matches — so audio
        # caps for the SomaFM stream are never reported and the stats-for-
        # nerds row shows "Unknown rate / Unknown depth" for the entire
        # session. Idempotent: the method disconnects any prior watch
        # before arming a fresh one.
        self._arm_caps_watch_for_current_stream()
        # Arm failover-timeout watchdog for the new URL (mirrors
        # _try_next_stream:1087 — BUFFER_DURATION_S window before we give up
        # and advance through _streams_queue).
        self._failover_timer.start(self._current_buffer_duration_s * 1000)

    def _on_gst_eos_during_preroll(self, bus, msg) -> None:
        """Phase 83 — malformed-preroll EOS bridge (live-spike Q3 RESOLVED).

        On the GstBusLoopThread. Bridges the (rare) case where a preroll
        reaches EOS WITHOUT firing about-to-finish first — e.g. a 0-byte
        response, a truncated m4a, or a non-decodable container. The
        live-spike (2026-05-22 Linux GStreamer 1.28.2) confirms this path
        is NOT reached on the normal happy path (about-to-finish fires at
        +7.849s before EOS), so this handler is defense-in-depth only.

        When ``_preroll_in_flight is False``, returns immediately so that
        today's EOS semantics (i.e. none on the streaming/looping path)
        are unchanged. When True, emits the existing
        ``_try_next_stream_requested`` queued Signal — the SAME fall-through
        Signal D-09's bus-error path uses — which marshals to main, runs
        ``_try_next_stream()``, and advances to ``_streams_queue[0]``.

        Plain-bool cross-thread read of ``_preroll_in_flight`` is atomic in
        CPython (mirrors ``_on_gst_tag``'s guard read; Pattern 2).
        """
        if not self._preroll_in_flight:
            return
        # Same fall-through path as D-09 bus-error. _try_next_stream_requested
        # is the existing class-level Signal wired with QueuedConnection in
        # __init__ (Phase 82 / 43.1 pattern); the handler does NOT itself touch
        # the pipeline, the handler-id, or the flag (those are main-thread
        # concerns; qt-glib-bus-threading Rule 2).
        self._try_next_stream_requested.emit()

    # ------------------------------------------------------------------ #
    # BUG-YT-LIVE-BUFFER: hlsdemux2 internal buffer configuration + DVR seek
    # ------------------------------------------------------------------ #

    def _apply_live_dvr_seek(self) -> None:
        """BUG-YT-LIVE-BUFFER / D-02 — one-shot DVR-window seek for YouTube
        live HLS streams.

        Called from _on_playbin_state_changed (main thread) once per YouTube
        live stream startup, immediately after the pipeline first reaches
        PLAYING state (i.e. after hlsdemux2 has parsed the manifest and
        preroll is complete — the seek range is valid at this point).

        Root cause (D-02): RFC 8216 §6.3.3 requires hlsdemux2 to start
        playback no closer than 3 * targetduration from the live edge.  For
        YouTube's 2 s segments: hold_back = 6 s.  In steady-state live-edge
        tracking the effective download buffer is only ~0-6 s — any CDN
        hiccup ≥ one segment-publish period (2 s) drains it to 0.

        Fix: issue a GStreamer SEEK_TYPE_END seek of -_LIVE_DVR_SEEK_OFFSET_S
        nanoseconds.  GStreamer's adaptivedemux2 translates SEEK_TYPE_END with
        a negative offset to (range_stop + offset) where range_stop is the
        hold_back position (live_edge - hold_back).  The result for YouTube:

            seek_pos = (live_edge - 6 s) - 30 s = live_edge - 36 s

        YouTube's DVR window exposes 7200 s of content — the seek lands well
        within bounds.  hlsdemux2 immediately downloads the 30 s of already-
        published segments at the new position, filling the download buffer to
        ~30 s.  Any CDN hiccup up to ~30 s is absorbed without a BUFFERING=0%
        event.  After consuming those 30 s, the player resumes live-edge
        tracking (hlsdemux2 "catches up" via faster-than-realtime download).

        Threading: MUST run on the main thread (called only from the queued
        _on_playbin_state_changed slot).  pipeline.seek() is safe from the
        main thread.

        Tradeoff: audio content is ~36 s older than the true live edge.  For
        a lofi radio station this latency is imperceptible.
        """
        offset_ns = self._LIVE_DVR_SEEK_OFFSET_S * Gst.SECOND
        # BUG-YT-LIVE-BUFFER / D-02: disarm the underrun tracker BEFORE seeking.
        # The FLUSH seek sends BUFFERING=0% on the bus immediately; if the
        # tracker is already armed (from the initial BUFFERING=100%), it would
        # open a false underrun cycle.  Disarming forces the tracker to wait for
        # the next BUFFERING=100% (post-seek re-fill) before watching for real
        # underruns.  Also reset _last_buffer_percent so de-dup doesn't swallow
        # the post-seek 0% message.
        self._tracker.disarm_for_seek()
        self._last_buffer_percent = -1
        ok = self._pipeline.seek(
            1.0,                           # rate
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            Gst.SeekType.END,              # start relative to live range_stop
            -offset_ns,                    # negative → before the live edge
            Gst.SeekType.NONE,             # no explicit stop
            0,
        )
        if ok:
            _log.info(
                "live HLS DVR seek applied: %.0f s behind hold-back position",
                self._LIVE_DVR_SEEK_OFFSET_S,
            )
        else:
            _log.warning(
                "live HLS DVR seek failed (seek range may not be ready yet)"
            )

    def _on_deep_element_added(self, pipeline, sub_bin, element) -> None:
        """GObject signal handler — fires on the thread that adds each child
        element to the playbin3 hierarchy.

        BUG-YT-LIVE-BUFFER / D-01: detects hlsdemux2 (and any future
        adaptivedemux2-family element whose factory name contains "hlsdemux")
        and sets max-buffering-time + high-watermark-time to match the
        current buffer-duration target.

        Threading invariant: this callback fires from GStreamer-internal
        threads (typically the thread that calls set_state, which is the Qt
        main thread for our _set_uri callers, but may be a GStreamer streaming
        thread for dynamically-added uridecodebin3 children). The handler
        MUST NOT touch Qt APIs. It only writes two GObject properties on the
        newly-added GStreamer element — safe from any thread (GLib GObject
        property writes are thread-safe for simple scalar types). Reading
        self._current_buffer_duration_s is a CPython-atomic int read per the
        same justification as _preroll_in_flight cross-thread reads (Pattern
        2 in qt-glib-bus-threading.md).
        """
        factory = element.get_factory()
        if factory is None:
            return
        name = factory.get_name()
        # Cover "hlsdemux2" and any future adaptivedemux2-family HLS element
        # whose factory name contains "hlsdemux".  Deliberately not matching
        # the legacy "hlsdemux" (rank 256 < hlsdemux2 rank 257) — it does not
        # expose these properties and should not be active when hlsdemux2 is
        # available.
        if "hlsdemux2" not in name:
            return
        target_ns = self._current_buffer_duration_s * Gst.SECOND
        try:
            element.set_property("max-buffering-time", target_ns)
            element.set_property("high-watermark-time", target_ns)
            _log.debug(
                "hlsdemux2 buffer configured: max-buffering-time=%.0fs "
                "high-watermark-time=%.0fs",
                self._current_buffer_duration_s,
                self._current_buffer_duration_s,
            )
        except Exception as exc:  # noqa: BLE001 — GObject property write; defensive
            _log.warning("hlsdemux2 buffer config failed: %s", exc)

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
        # Phase 95 / Pitfall 1: capture the current resolve generation at spawn
        # time and carry it through to the queued youtube_resolved Signal so a
        # resolution started before an edit/restart no-ops on delivery.
        seq = self._youtube_resolve_seq
        # Phase 95-03: set the in-flight gate BEFORE spawning the worker (on the
        # main thread) so there is no race between the worker delivery and the gate
        # check. Phase 95-04: the instance-attribute stamp (_youtube_resolve_in_flight_seq)
        # is removed; staleness is now carried on the Signal payload (youtube_resolution_failed
        # Signal(str, int)) — the same pattern as the success path (youtube_resolved).
        self._youtube_resolve_in_flight = True
        threading.Thread(
            target=self._youtube_resolve_worker, args=(url, seq), daemon=True
        ).start()

    def _youtube_resolve_worker(self, url: str, seq: int = 0) -> None:
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
                    self.youtube_resolution_failed.emit(str(e), seq)  # Phase 95-04: carry seq
                    return

            resolved = (info or {}).get("url") or ""
            if not resolved:
                formats = (info or {}).get("formats") or []
                if formats:
                    resolved = formats[-1].get("url") or ""
            if not resolved:
                self.youtube_resolution_failed.emit("No video formats returned", seq)  # Phase 95-04: carry seq
                return
            is_live = bool((info or {}).get("is_live", False))
            self.youtube_resolved.emit(resolved, is_live, seq)
        except Exception as e:  # noqa: BLE001 — daemon worker must surface ALL failures
            self.youtube_resolution_failed.emit(f"youtube resolve crashed: {e!r}", seq)  # Phase 95-04: carry seq

    def _on_youtube_resolved(self, resolved_url: str, is_live: bool, seq: int = 0) -> None:
        """Main-thread handler: hand the resolved HLS URL to playbin3 and arm
        the failover timer like any other direct stream.

        BUG-YT-LIVE-BUFFER / D-02: sets _pending_live_dvr_seek for live streams
        so _on_playbin_state_changed will issue a one-shot DVR-window seek after
        the pipeline first prerolls.  This positions playback ~30 s behind the
        live edge (see _apply_live_dvr_seek / _LIVE_DVR_SEEK_OFFSET_S).

        Phase 95 / Pitfall 1 / V5: ``seq`` is the resolve generation captured at
        worker-spawn time. Any delivery whose stamp != the current
        ``_youtube_resolve_seq`` is stale (an edit/restart superseded it) and is
        ignored so the OLD resolved URL never clobbers ``_set_uri``. Defaults to
        0 so synchronous test calls (no prior play()) still pass the guard,
        mirroring the _preroll_seq idiom.
        """
        if seq != self._youtube_resolve_seq:
            return  # Phase 95: stale resolution — an edit/restart superseded it
        # Phase 95-03: current generation settled (success) — clear the in-flight gate.
        # Placed AFTER the seq guard so a stale delivery never clears a fresh gate.
        self._youtube_resolve_in_flight = False
        self._pending_live_dvr_seek = is_live
        self._set_uri(resolved_url)
        self._failover_timer.start(self._current_buffer_duration_s * 1000)

    def _on_youtube_resolution_failed(self, msg: str, seq: int = -1) -> None:
        """Main-thread handler: surface the error and advance the failover queue.

        Phase 95-04 / CR-01: rewritten to use the CARRIED per-worker generation
        stamp (``seq``) instead of the overwrite-prone instance attribute
        ``_youtube_resolve_in_flight_seq`` (now removed). Mirrors the staleness
        guard pattern in ``_on_youtube_resolved``:

          - ``seq == -1`` (default): no-arg / direct test callers — pass the guard
            unconditionally (same idiom as ``_on_youtube_resolved``'s ``seq=0``
            default which is never != 0 without a prior restart).
          - ``seq != -1 and seq != self._youtube_resolve_seq``: stale generation
            (a newer edit/restart/stop superseded this worker) — early return;
            do NOT clear the fresh gate and do NOT call ``_try_next_stream``.
          - ``seq == self._youtube_resolve_seq``: current generation — clear the
            gate BEFORE ``_try_next_stream`` so legitimate exhaustion
            (empty queue → ``failover(None)``) is still reachable.

        The ``-1`` sentinel lets unit tests call the slot without a seq argument
        and still pass the guard (mirrors V16c / the original V14/V15 bool-poke
        tests that directly call the handler without going through the Signal).
        """
        # Phase 95-04: carried-seq staleness guard (mirrors _on_youtube_resolved).
        # A stale delivery belongs to an old generation superseded by a newer
        # edit/restart/stop; do NOT clear the fresh gate and do NOT call
        # _try_next_stream (which would emit spurious failover(None) on the new
        # generation's transiently-empty queue).
        if seq != -1 and seq != self._youtube_resolve_seq:
            return  # stale generation — superseded
        # Current generation (or no-arg caller) failed: clear the gate BEFORE
        # _try_next_stream so the legitimate exhaustion path is reachable.
        self._youtube_resolve_in_flight = False
        self.playback_error.emit(f"YouTube resolve failed: {msg}")
        self._try_next_stream()

    # ------------------------------------------------------------------ #
    # Phase 95 -- stream-edit invalidation (D-01..D-05 + YT resolve-seq guard)
    # ------------------------------------------------------------------ #

    def invalidate_for_edit(self, station: "Station", is_playing: bool) -> None:
        """Invalidate stale player state after a station's streams were edited.

        Called on the MAIN thread from MainWindow._sync_now_playing_station for
        every committed edit. The Player decides the action so id-match logic
        lives in one place (RESEARCH "pass-and-let-player-decide"):

          - D-01/D-03 (V1): the currently-playing stream's URL changed (or the
            playing stream was deleted, Q2/V10) while audio is live -> re-issue
            ``self.play(station)`` (the full rebuild path: _cancel_timers,
            _streams_queue reset, _is_first_attempt, order_streams, no-streams
            guard) so the FIRST play uses the new URL.
          - D-02 (V2) / same-URL (V4): only metadata changed on the playing
            stream -> no-op beyond the generation bump; audio continues.
          - D-04 (V3): a NON-playing stream of the playing station changed ->
            invalidate ``_streams_queue`` so later failover rebuilds from fresh
            URLs, but do NOT restart audio / set_state(NULL).
          - D-05 (V6): the player last loaded this station but is not playing
            (idle/paused/stopped) -> clear ``_streams_queue``/``_current_stream``
            so the next play() rebuilds fresh; do NOT restart audio.
          - Different station the player never loaded -> no-op beyond the bump.

        URL comparison uses raw ``.strip()`` equality on the STORED
        ``StationStream.url`` (Pitfall 3 — never the resolved playbin3 URI).
        """
        # Always bump the resolve generation first: any in-flight YouTube
        # resolution from BEFORE this edit now no-ops (D-03 / V5 race guard).
        # Harmless for metadata-only edits (no resolution is pending then).
        self._youtube_resolve_seq += 1

        # Not the station the player last loaded -> nothing playing-related to
        # invalidate here; that station's next play() already rebuilds fresh.
        if self._current_station_id != station.id:
            return

        playing = self._current_stream
        # No playing stream recorded -> treat as not-playing for this station:
        # clear any stale queue so the next play() rebuilds fresh (D-05).
        if playing is None:
            self._streams_queue = []
            return

        # Locate the playing stream in the updated station by id.
        match = next((s for s in station.streams if s.id == playing.id), None)
        playing_changed = (
            match is None  # deleted (Q2/V10)
            or match.url.strip() != (playing.url or "").strip()  # URL changed
        )

        if playing_changed:
            if is_playing:
                # D-01 / Q2 / V10: restart immediately on the new URL. Reuse the
                # full rebuild path; the surviving stream is picked for the
                # deleted case, and play()'s no-streams guard handles all-deleted.
                self.play(station)
            else:
                # D-05 / Pitfall 2: idle/paused/stopped — no audio to interrupt.
                # Clear cached state so the next play() rebuilds from fresh DB.
                self._streams_queue = []
                self._current_stream = None
            return

        # Playing stream URL UNCHANGED.
        if is_playing:
            # Did a DIFFERENT (non-playing) stream change? Coarse check: if any
            # stream other than the playing one differs in URL, or the stream
            # set changed, invalidate the queue so later failover rebuilds fresh
            # (D-04). Do NOT restart audio.
            others_changed = len(station.streams) != len(self._streams_queue) or any(
                (s.url or "").strip()
                != next(
                    ((q.url or "") for q in self._streams_queue if q.id == s.id), None
                )
                for s in station.streams
                if s.id != playing.id
            )
            if others_changed:
                self._streams_queue = []
            # else: D-02 metadata-only / V4 same-URL -> no-op beyond the bump.
        # is_playing False with unchanged playing-stream URL: nothing to do
        # beyond the generation bump (next play() rebuilds fresh anyway).

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
        self._failover_timer.start(self._current_buffer_duration_s * 1000)

    # ------------------------------------------------------------------ #
    # Phase 83 — SomaFM preroll backfill (D-13 daemon worker, Pattern 4)
    # ------------------------------------------------------------------ #

    def _preroll_backfill_worker(self, station_id: int, station_name: str) -> None:
        """Phase 83 D-13 daemon backfill worker (Pattern 4 thread-local Repo).

        Fetches SomaFM channels.json off the main thread, matches the
        upstream channel by title (Pitfall 3 option 1), opens its own
        ``Repo`` via ``db_connect()`` (Pattern 4 — never share the main-thread
        Repo across threads), inserts ``station_prerolls`` rows + sets
        ``prerolls_fetched_at``. Silent on all failures (D-04). Single-flight
        via ``self._backfill_in_flight`` (T-83-10) — discarded in finally so
        a later play retries on a fresh attempt.

        Per Pitfall 3: matches by title because Phase 74 does not persist
        the SomaFM slug. A user-renamed station silently never gets a
        preroll (acceptable per D-04 silent failure caps).
        """
        from musicstreamer.soma_import import fetch_channels
        from musicstreamer.repo import db_connect, Repo
        try:
            channels = fetch_channels()
            match = next(
                (c for c in channels if c.get("title") == station_name), None
            )
            preroll_urls = list((match or {}).get("preroll_urls", []) or [])
            if len(preroll_urls) > 50:
                preroll_urls = preroll_urls[:50]  # T-83-02 double-defense
            con = db_connect()
            try:
                repo = Repo(con)
                for pos, url in enumerate(preroll_urls, start=1):
                    try:
                        repo.insert_preroll(station_id, url, pos)
                    except ValueError:
                        # URL-scheme rejection from Plan 83-01; skip and continue.
                        continue
                # D-04: mark fetched regardless of count (legitimately-empty
                # channels must not re-trigger backfill on every Play).
                repo.set_prerolls_fetched_at(station_id, int(time.time()))
            finally:
                con.close()
        except Exception as exc:  # noqa: BLE001 — D-04 silent failure path
            _log.warning(
                "Phase 83 preroll backfill failed for station %d (%r): %s",
                station_id, station_name, exc,
            )
        finally:
            # WR-03: cross-thread mutation. add()/membership-test run on the main
            # thread (play()); this discard() runs on the daemon worker thread.
            # set.discard / set.add / `in` are each atomic under CPython's GIL
            # (Pattern 2 — same justification as the _preroll_in_flight / _preroll_seq
            # cross-thread reads), so the set never corrupts. The check-then-add in
            # play() is not lock-held, but both schedule sites run on the main thread
            # and cannot race each other; the only cross-thread writer is this discard,
            # whose worst case is a benign duplicate worker if it fires before a
            # second play's check. This relies on schedule staying main-thread-only.
            self._backfill_in_flight.discard(station_id)

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
