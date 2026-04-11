---
phase: 35-backend-isolation
plan: 04
type: execute
wave: 3
depends_on: [35-01, 35-02, 35-03]
files_modified:
  - musicstreamer/gst_bus_bridge.py
  - musicstreamer/player.py
autonomous: true
requirements: [PORT-01, PORT-02, PORT-09]
must_haves:
  truths:
    - "Player is a QObject subclass with class-level typed Signals for title_changed, failover, offline, playback_error, elapsed_updated, twitch_resolved"
    - "GStreamer bus messages reach Player via a GLib.MainLoop daemon thread that re-emits Qt signals — no GLib.idle_add remains in player.py"
    - "Failover timer, YouTube poll timer, and cookie-retry one-shot use QTimer instead of GLib.timeout_add"
    - "_play_twitch() uses streamlink.Streamlink().streams(url) — no subprocess invocation of streamlink"
    - "_play_youtube() either (a) uses yt_dlp library + playbin3 if spike passed, or (b) retains subprocess + a minimal _popen helper if spike failed — but in EITHER case no GLib.idle_add / timeout_add / source_remove remains"
  artifacts:
    - path: "musicstreamer/gst_bus_bridge.py"
      provides: "GstBusLoopThread — GLib.MainLoop daemon thread wrapper + attach_bus() helper"
      exports: ["GstBusLoopThread", "attach_bus"]
      min_lines: 30
    - path: "musicstreamer/player.py"
      provides: "Player(QObject) with typed Qt signals"
      contains: "class Player(QObject)"
  key_links:
    - from: "musicstreamer/player.py"
      to: "PySide6.QtCore.QObject"
      via: "class inheritance"
      pattern: "class Player\\(QObject\\)"
    - from: "musicstreamer/player.py"
      to: "musicstreamer.gst_bus_bridge.GstBusLoopThread"
      via: "daemon thread started in __init__"
      pattern: "GstBusLoopThread"
    - from: "musicstreamer/player.py"
      to: "streamlink.session.Streamlink"
      via: "library API for Twitch HLS resolution"
      pattern: "Streamlink|streamlink\\.session"
    - from: "musicstreamer/player.py"
      to: "PySide6.QtCore.QTimer"
      via: "failover/poll/cookie-retry timers"
      pattern: "QTimer"
---

<objective>
Convert `musicstreamer/player.py` into a `QObject` subclass with typed Qt signals, bridge the GStreamer bus to the Qt main thread via a `GLib.MainLoop` daemon thread (PORT-02 / D-07), replace every `GLib.idle_add` / `GLib.timeout_add` / `GLib.source_remove` call with Qt signals or `QTimer`, and port `_play_twitch()` from subprocess to `streamlink.Streamlink().streams(url)` (D-18). The `_play_youtube()` path is rewritten per the Plan 35-01 spike decision recorded in `35-SPIKE-MPV.md`.

Purpose: Satisfy PORT-01, PORT-02, and the player-side of PORT-09. This is the heaviest plan in Phase 35 — it owns the core threading bridge rewrite.

Output:
- NEW `musicstreamer/gst_bus_bridge.py` — `GstBusLoopThread` class wrapping `GLib.MainLoop` on a daemon thread, plus an `attach_bus(bus)` helper that wires sync-emission + async watch per D-07.
- REWRITE `musicstreamer/player.py` — class inherits from `QObject`, class-level `Signal` declarations, QTimer-based timers, library-API `_play_twitch`, spike-branched `_play_youtube`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/35-backend-isolation/35-CONTEXT.md
@.planning/phases/35-backend-isolation/35-RESEARCH.md
@.planning/phases/35-backend-isolation/35-SPIKE-MPV.md
@musicstreamer/player.py
@musicstreamer/paths.py
@musicstreamer/constants.py

<interfaces>
<!-- RESEARCH.md Pattern 1 — Player QObject shape -->
```python
from PySide6.QtCore import QObject, Signal, Slot, QTimer, Qt

class Player(QObject):
    # Class-level Signals (required by Qt — instance attrs silently do nothing, Pitfall 4)
    title_changed    = Signal(str)       # ICY title
    failover         = Signal(object)    # StationStream | None
    offline          = Signal(str)       # Twitch channel name
    twitch_resolved  = Signal(str)       # internal: resolved HLS URL
    playback_error   = Signal(str)       # GStreamer error text
    elapsed_updated  = Signal(int)       # seconds since playback started

    def __init__(self, parent: QObject | None = None): ...
```

<!-- RESEARCH.md Pattern 2 — GstBusLoopThread shape -->
```python
# musicstreamer/gst_bus_bridge.py
import threading
from gi.repository import GLib

class GstBusLoopThread:
    def __init__(self): ...
    def start(self): ...   # spawns daemon thread running its own GLib.MainContext
    def stop(self): ...    # GLib.idle_add(loop.quit) from outside

def attach_bus(bus) -> None:
    # D-07 recipe: sync emission ON, async watch handlers only (Pitfall 5)
    bus.enable_sync_message_emission()
    bus.add_signal_watch()
```

<!-- RESEARCH.md Pattern 7 — streamlink library -->
```python
from streamlink.session import Streamlink
from streamlink.exceptions import NoPluginError, PluginError
session = Streamlink()
session.set_plugin_option("twitch", "api-header", [("Authorization", f"OAuth {token}")])
streams = session.streams(url)
best_url = streams["best"].url
```

<!-- RESEARCH.md "Signal-by-signal mapping" table — EVERY GLib call in current player.py has a direct replacement -->
<!-- See 35-RESEARCH.md for the complete mapping -->

<!-- Current player.py external API (callers in main_window.py must keep working) -->
<!-- play(station, on_title, preferred_quality="", on_failover=None, on_offline=None) -->
<!-- play_stream(stream, on_title, on_failover=None, on_offline=None) -->
<!-- pause(), stop(), set_volume(value), current_stream (property) -->
<!-- The on_title / on_failover / on_offline callbacks are what main_window.py uses. -->
<!-- Backward-compat shim: play/play_stream accept the old callback args and internally self.title_changed.connect(on_title) if provided. -->
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create GstBusLoopThread + attach_bus helper in gst_bus_bridge.py</name>
  <files>musicstreamer/gst_bus_bridge.py</files>
  <read_first>.planning/phases/35-backend-isolation/35-RESEARCH.md (Pattern 2 + Pitfall 3 + Pitfall 5 + Open Question #1), .planning/phases/35-backend-isolation/35-CONTEXT.md (D-07 — literal requirement), musicstreamer/player.py (lines 33-36 — current bus wiring)</read_first>
  <action>
Create `musicstreamer/gst_bus_bridge.py`. The module's contract (per D-07 and RESEARCH.md Open Question #1 recommendation):

Given a GStreamer bus, expose a helper that:
  (a) calls `bus.enable_sync_message_emission()` — LITERAL D-07 requirement, also grepped by PORT-02 acceptance gate,
  (b) attaches async `bus.add_signal_watch()` so watched signals are dispatched on whatever GLib main loop is running (the bridge thread's loop in our case),
  (c) does NOT register any sync message handlers (`bus.connect("sync-message", ...)` is forbidden here — sync handlers run on the GStreamer streaming thread and would stall the pipeline per Pitfall 5).

Callers of `attach_bus(bus)` then call `bus.connect("message::error", ...)` and `bus.connect("message::tag", ...)` separately — those are ASYNC watch connections (not sync), and they dispatch on the bridge thread's main loop. This satisfies D-07 literally (sync emission is enabled) while avoiding the streaming-thread stall pitfall (no sync handlers are wired).

Exact implementation:

```python
"""GStreamer bus → Qt main thread bridge (Phase 35 / PORT-02 / D-07).

Runs a GLib.MainLoop on a daemon thread so GStreamer's bus signal watches
fire even though the main thread runs Qt's event loop. Handlers installed
via bus.connect(...) after attach_bus() run on THAT thread and must emit
Qt signals (queued connection, cross-thread) to reach the main thread.

D-07 contract (literal from CONTEXT.md):
- bus.enable_sync_message_emission() MUST be called on each pipeline bus.
- Async bus.add_signal_watch() dispatches handlers on the bridge thread's
  GLib.MainLoop. Sync message handlers (bus.connect("sync-message", ...))
  are explicitly NOT registered — they would stall the GStreamer streaming
  thread (RESEARCH.md Pitfall 5).

Thread-safety contract:
- Emitting a Qt Signal from any thread is safe — Qt auto-selects a queued
  connection when source/target thread affinities differ.
- All QTimer objects must be constructed on the main thread, not here.
- attach_bus(bus) must be called AFTER GstBusLoopThread.start() so the loop
  exists to dispatch watched events.
"""
from __future__ import annotations
import threading
from gi.repository import GLib


class GstBusLoopThread:
    """Daemon-thread GLib.MainLoop. Start once per process, stop at shutdown."""

    def __init__(self) -> None:
        self._loop: GLib.MainLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    def start(self, timeout: float = 2.0) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="gst-bus-loop", daemon=True
        )
        self._thread.start()
        if not self._ready.wait(timeout=timeout):
            raise RuntimeError("GstBusLoopThread failed to start within timeout")

    def _run(self) -> None:
        # Use the default main context — simpler than pushing a thread-default,
        # and sufficient because this process has no other GLib code that would
        # race on the default context (RESEARCH.md anti-patterns section).
        self._loop = GLib.MainLoop.new(None, False)
        self._ready.set()
        self._loop.run()

    def stop(self) -> None:
        if self._loop and self._loop.is_running():
            # quit from inside the loop via an idle source
            GLib.idle_add(self._loop.quit)

    @property
    def is_running(self) -> bool:
        return self._loop is not None and self._loop.is_running()


def attach_bus(bus) -> None:
    """Wire a GStreamer bus to the bridge-thread main loop per D-07.

    Call ORDER matters: sync emission must be enabled before add_signal_watch()
    so that tag/error events emitted before the first watch dispatch are still
    captured.

    After this returns, callers should register async handlers via
    bus.connect("message::error", ...) / bus.connect("message::tag", ...).
    Those handlers run on the bridge thread and must only emit Qt signals.

    DO NOT call bus.connect("sync-message", ...) — sync handlers run on the
    GStreamer streaming thread and must return instantly (Pitfall 5). This
    helper intentionally does not expose a sync-handler hook.
    """
    bus.enable_sync_message_emission()  # D-07 literal — also a PORT-02 gate
    bus.add_signal_watch()               # async watch, dispatched on bridge thread
```

Note: this module has ONE call to `GLib.idle_add` — inside `GstBusLoopThread.stop()`, purely to quit the loop from outside. That is the ONLY `GLib.idle_add` call permitted in Phase 35 code, and it is NOT in `player.py` so it does not violate PORT-01.
  </action>
  <verify>
    <automated>python -c "
from musicstreamer.gst_bus_bridge import GstBusLoopThread, attach_bus
t = GstBusLoopThread()
t.start()
assert t.is_running
t.stop()
assert callable(attach_bus)
print('ok')
" </automated>
  </verify>
  <acceptance_criteria>
- `test -f musicstreamer/gst_bus_bridge.py` exits 0
- `grep -q "class GstBusLoopThread" musicstreamer/gst_bus_bridge.py` matches
- `grep -q "GLib.MainLoop" musicstreamer/gst_bus_bridge.py` matches
- `grep -q "daemon=True" musicstreamer/gst_bus_bridge.py` matches
- `grep -q "threading.Event" musicstreamer/gst_bus_bridge.py` matches
- `grep -q "def attach_bus" musicstreamer/gst_bus_bridge.py` matches
- `grep -q "enable_sync_message_emission" musicstreamer/gst_bus_bridge.py` matches (D-07 literal gate)
- `grep -q "add_signal_watch" musicstreamer/gst_bus_bridge.py` matches
- `! grep -q 'bus.connect("sync-message"' musicstreamer/gst_bus_bridge.py` (no sync handler — Pitfall 5)
- Python smoke: constructing + start + is_running + stop completes without error and `attach_bus` is importable
  </acceptance_criteria>
  <done>GstBusLoopThread exists, starts a daemon thread with a GLib.MainLoop, and can be stopped cleanly. `attach_bus(bus)` helper enables sync message emission and attaches the async signal watch, satisfying D-07 literally without registering any sync handlers.</done>
</task>

<task type="auto">
  <name>Task 2: Rewrite player.py as QObject + Signals + QTimer + library APIs</name>
  <files>musicstreamer/player.py</files>
  <read_first>musicstreamer/player.py (full file), musicstreamer/gst_bus_bridge.py, .planning/phases/35-backend-isolation/35-RESEARCH.md (Patterns 1, 2, 6, 7; Pitfalls 2, 4, 5, 6; Signal-by-signal mapping table), .planning/phases/35-backend-isolation/35-CONTEXT.md (D-07 literal), .planning/phases/35-backend-isolation/35-SPIKE-MPV.md (Decision line — determines _play_youtube strategy)</read_first>
  <action>
Full rewrite of `musicstreamer/player.py`. Use this skeleton as a baseline and fill in every method faithfully to current behavior (failover semantics, cookie-retry window, YT_MIN_WAIT_S delay, Twitch OAuth header path, non-destructive cookie file copy, etc.).

**Pre-step — Read the spike decision.** Open `.planning/phases/35-backend-isolation/35-SPIKE-MPV.md` and find the `**Decision:**` line. If it says `DROP_MPV`, implement path A below. If `KEEP_MPV`, implement path B. Record the branch chosen in the summary.

**Bus wiring contract (D-07 — MANDATORY):** In `Player.__init__`, the per-pipeline bus setup MUST use `gst_bus_bridge.attach_bus(bus)` OR inline the equivalent call sequence. Either way, `bus.enable_sync_message_emission()` MUST appear in `player.py` (one call per pipeline construction) immediately before `bus.add_signal_watch()`. This is a literal D-07 / PORT-02 requirement and is grep-verified. Per Pitfall 5, do NOT register a `sync-message` handler — only the async `message::error` and `message::tag` connects.

**Skeleton (both branches share 80% of the code):**

```python
"""GStreamer player backend — QObject + Qt signals (Phase 35 / PORT-01, PORT-02, PORT-09).

Thread model:
- Player lives on the thread that constructed it (the Qt main thread under
  QCoreApplication.exec()). All QTimer objects, all signal connections, and
  the pipeline state-changes happen on that thread.
- GStreamer bus signal watches (message::error, message::tag) are dispatched
  by a GstBusLoopThread daemon thread running GLib.MainLoop. Handlers run on
  THAT thread and emit Qt signals — cross-thread emission is auto-queued.
- Twitch resolver and yt-dlp extractor run on ad-hoc threading.Thread workers
  because they make blocking HTTP calls; they emit Qt signals when done.
"""
from __future__ import annotations

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
from musicstreamer.constants import BUFFER_DURATION_S, BUFFER_SIZE_BYTES, YT_MIN_WAIT_S
from musicstreamer.gst_bus_bridge import GstBusLoopThread, attach_bus
from musicstreamer.models import Station, StationStream


# Module-level bus bridge — one per process. Started lazily on first Player().
_BUS_BRIDGE: GstBusLoopThread | None = None


def _ensure_bus_bridge() -> GstBusLoopThread:
    global _BUS_BRIDGE
    if _BUS_BRIDGE is None:
        _BUS_BRIDGE = GstBusLoopThread()
        _BUS_BRIDGE.start()
    return _BUS_BRIDGE


def _fix_icy_encoding(s: str) -> str:
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


class Player(QObject):
    # Class-level Signals (Pitfall 4 — MUST be at class scope)
    title_changed   = Signal(str)       # ICY title (after encoding fix)
    failover        = Signal(object)    # StationStream | None
    offline         = Signal(str)       # Twitch channel name
    twitch_resolved = Signal(str)       # internal: resolved HLS URL — queued back to main thread
    playback_error  = Signal(str)       # GStreamer error text
    elapsed_updated = Signal(int)       # seconds since playback start (Phase 30 reserved)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Ensure the bus-loop thread is running BEFORE attach_bus()
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

        # D-07 bus wiring — sync emission MUST be enabled before add_signal_watch.
        # Order is grep-verified by PORT-02 acceptance gate.
        bus = self._pipeline.get_bus()
        bus.enable_sync_message_emission()  # D-07 literal — exactly 1 call in player.py
        bus.add_signal_watch()              # async watch, dispatched by bridge thread
        bus.connect("message::error", self._on_gst_error)  # async handler
        bus.connect("message::tag",   self._on_gst_tag)    # async handler
        # NOTE: no bus.connect("sync-message", ...) — sync handlers would stall
        # the streaming thread (Pitfall 5). All handlers above are async watch
        # handlers dispatched on the GstBusLoopThread main loop.

        # QTimer objects — constructed on the main thread (Pitfall 2)
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

        # Legacy callback shims (set via play/play_stream) — kept so
        # main_window.py (still alive this phase) works unchanged.
        self._on_title_cb = None
        self._on_failover_cb = None
        self._on_offline_cb = None

        # Runtime state — same fields as current player.py
        self._volume: float = 1.0
        self._streams_queue: list = []
        self._current_stream: StationStream | None = None
        self._current_station_name: str = ""
        self._is_first_attempt: bool = True
        self._yt_attempt_start_ts: float | None = None
        self._twitch_resolve_attempts: int = 0
        self._yt_proc = None            # only used if KEEP_MPV path active
        self._yt_cookie_tmp = None

        # Clean up any stale cookie temp files from previous crashed sessions
        import glob as _glob
        for stale in _glob.glob(os.path.join(tempfile.gettempdir(), "ms_cookies_*.txt")):
            try:
                os.unlink(stale)
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    # Public API (callback shims preserved for main_window.py)
    # ------------------------------------------------------------------ #

    @property
    def current_stream(self):
        return self._current_stream

    def set_volume(self, value: float) -> None:
        self._volume = max(0.0, min(1.0, value))
        self._pipeline.set_property("volume", self._volume)

    def play(self, station, on_title=None, preferred_quality: str = "",
             on_failover=None, on_offline=None) -> None:
        self._cancel_timers()
        self._install_legacy_callbacks(on_title, on_failover, on_offline)
        self._current_station_name = station.name
        self._is_first_attempt = True
        self._twitch_resolve_attempts = 0
        if not station.streams:
            self._emit_title("(no streams configured)")
            return
        streams_by_position = sorted(station.streams, key=lambda s: s.position)
        preferred = next(
            (s for s in streams_by_position if s.quality == preferred_quality),
            None,
        ) if preferred_quality else None
        if preferred:
            queue = [preferred] + [s for s in streams_by_position if s is not preferred]
        else:
            queue = list(streams_by_position)
        self._streams_queue = queue
        self._try_next_stream()

    def play_stream(self, stream, on_title=None, on_failover=None, on_offline=None) -> None:
        self._cancel_timers()
        self._install_legacy_callbacks(on_title, on_failover, on_offline)
        self._current_station_name = ""
        self._streams_queue = [stream]
        self._is_first_attempt = True
        self._try_next_stream()

    def pause(self) -> None:
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
    # Legacy callback shim — lets main_window.py keep its old signature
    # ------------------------------------------------------------------ #

    def _install_legacy_callbacks(self, on_title, on_failover, on_offline) -> None:
        # Disconnect any previous shims before wiring new ones
        if self._on_title_cb is not None:
            try: self.title_changed.disconnect(self._on_title_cb)
            except (RuntimeError, TypeError): pass
        if self._on_failover_cb is not None:
            try: self.failover.disconnect(self._on_failover_cb)
            except (RuntimeError, TypeError): pass
        if self._on_offline_cb is not None:
            try: self.offline.disconnect(self._on_offline_cb)
            except (RuntimeError, TypeError): pass

        self._on_title_cb = on_title
        self._on_failover_cb = on_failover
        self._on_offline_cb = on_offline

        if on_title is not None:
            self.title_changed.connect(on_title)
        if on_failover is not None:
            self.failover.connect(on_failover)
        if on_offline is not None:
            self.offline.connect(on_offline)

    def _emit_title(self, title: str) -> None:
        self.title_changed.emit(title)

    # ------------------------------------------------------------------ #
    # GStreamer bus handlers — run on the GLib bus-loop thread.
    # They MUST NOT touch QTimer or any Qt-affined state directly; they
    # only emit Qt signals, which are auto-queued cross-thread.
    # ------------------------------------------------------------------ #

    def _on_gst_error(self, bus, msg) -> None:
        err, debug = msg.parse_error()
        self.playback_error.emit(f"{err} | {debug}")
        # Route recovery through a signal → slot so QTimer work happens on the
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
        # Cancel the failover timer — audio data arrived, stream is working.
        # QTimer.stop() can only be called on the owning thread, so route it
        # through a zero-delay singleShot to marshal onto the main thread.
        QTimer.singleShot(0, self._cancel_timers)
        if not found:
            return
        title = _fix_icy_encoding(value)
        self.title_changed.emit(title)  # queued, auto-marshaled to main thread

    # ------------------------------------------------------------------ #
    # Timer helpers — main-thread only
    # ------------------------------------------------------------------ #

    def _cancel_timers(self) -> None:
        self._failover_timer.stop()
        self._yt_poll_timer.stop()
        self._yt_attempt_start_ts = None

    def _on_timeout(self) -> None:
        self._try_next_stream()

    # ------------------------------------------------------------------ #
    # Failover queue
    # ------------------------------------------------------------------ #

    def _try_next_stream(self) -> None:
        self._pipeline.set_state(Gst.State.NULL)
        if not self._streams_queue:
            self.failover.emit(None)
            return
        stream = self._streams_queue.pop(0)
        self._current_stream = stream
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
            self._failover_timer.start(BUFFER_DURATION_S * 1000)

    def _set_uri(self, uri: str) -> None:
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.set_property("uri", uri)
        self._pipeline.set_state(Gst.State.PLAYING)

    # ------------------------------------------------------------------ #
    # YouTube — branches on spike decision
    # ------------------------------------------------------------------ #

    # PATH A (DROP_MPV): _play_youtube resolves via yt_dlp library then _set_uri
    def _play_youtube(self, url: str) -> None:
        """[SPIKE=DROP_MPV] Resolve via yt_dlp library on a worker thread,
        then hand the direct URL to playbin3 via the queued twitch_resolved
        signal pattern. [SPIKE=KEEP_MPV] Launch mpv subprocess with cookies
        and poll for exit (current behavior, but via QTimer instead of
        GLib.timeout_add)."""
        # ... implementation per spike decision — see below ...
        ...

    # PATH A helper
    def _yt_resolve_worker(self, url: str, cookies: str | None) -> None:
        import yt_dlp
        opts = {
            "quiet": True, "no_warnings": True, "skip_download": True,
            "format": "best[protocol^=m3u8]/best",
        }
        if cookies and os.path.exists(cookies):
            opts["cookiefile"] = cookies
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            self.playback_error.emit(f"yt-dlp: {e}")
            QTimer.singleShot(0, self._try_next_stream)
            return
        direct = info.get("url") or (info.get("formats") or [{}])[-1].get("url")
        if not direct:
            self.playback_error.emit("yt-dlp: no playable URL")
            QTimer.singleShot(0, self._try_next_stream)
            return
        # Route back to main thread
        self.twitch_resolved.emit(direct)  # reuses the resolved-URL slot

    # PATH B helper (KEEP_MPV)
    def _yt_poll_cb(self) -> None:
        """Poll mpv subprocess for exit. YT_MIN_WAIT_S failover window preserved
        from Phase 33 / FIX-07. Called by QTimer on main thread."""
        if self._yt_proc is None:
            self._yt_poll_timer.stop()
            return
        exit_code = self._yt_proc.poll()
        elapsed = 0.0 if self._yt_attempt_start_ts is None else (
            time.monotonic() - self._yt_attempt_start_ts
        )
        if exit_code is None:
            if elapsed >= YT_MIN_WAIT_S:
                self._yt_poll_timer.stop()
                self._yt_attempt_start_ts = None
            return
        if elapsed < YT_MIN_WAIT_S:
            return  # keep polling
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
    # Twitch — streamlink library API
    # ------------------------------------------------------------------ #

    def _play_twitch(self, url: str) -> None:
        """Resolve Twitch URL via streamlink library on a worker thread, then
        set the resolved HLS URL on playbin3 via queued twitch_resolved signal."""
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
            # Scope the header to Twitch gql API only — NOT global http-header
            # (RESEARCH.md Pitfall 6).
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
        # Success — queued emission marshals back to main thread
        self.twitch_resolved.emit(streams["best"].url)

    def _on_twitch_resolved(self, resolved_url: str) -> None:
        """Runs on main thread (connected via Qt.QueuedConnection in __init__)."""
        self._set_uri(resolved_url)
        self._failover_timer.start(BUFFER_DURATION_S * 1000)
```

**Spike-branch implementation for `_play_youtube`:**

- **DROP_MPV branch (A):** replace the method body with a worker-thread call to `_yt_resolve_worker(url, paths.cookies_path())`. Delete `_stop_yt_proc`'s subprocess handling (but keep `_cleanup_cookie_tmp` — still used for the stale-cookie-file sweep in `__init__`). Delete `_yt_poll_cb`. Emit a fallback title via `self.title_changed.emit(self._current_station_name)` before dispatching the worker so the UI updates immediately. Do NOT introduce `_popen()`.

- **KEEP_MPV branch (B):** keep the full `_play_youtube` subprocess launch logic from current `player.py` lines 251-305, but route EVERY timer through QTimer:
  - `GLib.timeout_add(2000, _check_cookie_retry)` → `QTimer.singleShot(2000, self._check_cookie_retry)`
  - `GLib.timeout_add(1000, self._yt_poll_cb)` → `self._yt_poll_timer.start()` (interval set to 1000 in __init__)
  - Keep the fallback title emission (`self.title_changed.emit(fallback_name)`)
  - Subprocess launch stays via `subprocess.Popen` — create a new helper `musicstreamer/_popen.py` with a single `popen(cmd, **kwargs)` function that adds `creationflags=subprocess.CREATE_NO_WINDOW` on Windows (`sys.platform == "win32"`) and is a passthrough on Linux. Pre-stages PKG-03 for Phase 44.
  - Use `paths.cookies_path()` and `paths.data_dir()` for the cookie copy and mpv log path (no more `from musicstreamer.constants import DATA_DIR` inside the method).

Both branches MUST end with `grep -qE "GLib\\.(idle_add|timeout_add|source_remove)" musicstreamer/player.py` returning nothing.

**Critical: leave the `title_changed`/`failover`/`offline` signal names as the new contract.** `main_window.py` consumes them via the legacy `on_title=` kwarg shim — no changes to `main_window.py` this plan. (Plan 35-05 will rewrite the GTK tests, and Phase 36 will delete `main_window.py` entirely.)
  </action>
  <verify>
    <automated>! grep -qE "GLib\.(idle_add|timeout_add|source_remove)|DBusGMainLoop|import dbus" musicstreamer/player.py && grep -q "class Player(QObject)" musicstreamer/player.py && grep -q "from PySide6.QtCore" musicstreamer/player.py && grep -q "Signal(str)" musicstreamer/player.py && grep -q "GstBusLoopThread" musicstreamer/player.py && [ "$(grep -c 'bus\.enable_sync_message_emission' musicstreamer/player.py)" = "1" ] && ! grep -qE "subprocess.run\(\\[.streamlink" musicstreamer/player.py && python -c "from musicstreamer.player import Player; import inspect; assert Player.title_changed is not None; assert Player.failover is not None; assert Player.offline is not None; print('ok')"</automated>
  </verify>
  <acceptance_criteria>
- `grep -q "^class Player(QObject):" musicstreamer/player.py` matches
- `grep -qE "^\s+title_changed\s*=\s*Signal" musicstreamer/player.py` matches (class-level signal, not instance)
- `grep -qE "^\s+failover\s*=\s*Signal" musicstreamer/player.py` matches
- `grep -qE "^\s+offline\s*=\s*Signal" musicstreamer/player.py` matches
- `grep -qE "^\s+playback_error\s*=\s*Signal" musicstreamer/player.py` matches
- `grep -q "from PySide6.QtCore import" musicstreamer/player.py` matches
- `grep -q "QTimer" musicstreamer/player.py` matches
- `grep -q "GstBusLoopThread" musicstreamer/player.py` matches
- `grep -q "from streamlink" musicstreamer/player.py` matches
- **`[ "$(grep -c 'bus\.enable_sync_message_emission' musicstreamer/player.py)" = "1" ]` — D-07 literal gate, EXACTLY 1 match required (one pipeline, one call)**
- **`grep -nE "enable_sync_message_emission|add_signal_watch" musicstreamer/player.py` — sync emission line number MUST be lower than add_signal_watch line number (order matters)**
- `! grep -q 'bus.connect("sync-message"' musicstreamer/player.py` (no sync handlers — Pitfall 5)
- `! grep -qE "GLib\.idle_add|GLib\.timeout_add|GLib\.source_remove" musicstreamer/player.py` (FORBIDDEN PATTERNS)
- `! grep -qE "^import dbus|^from dbus|DBusGMainLoop" musicstreamer/player.py`
- `! grep -qE "subprocess\.(run|Popen)\(\[.streamlink" musicstreamer/player.py` (streamlink is library-only now)
- `grep -q "Qt.ConnectionType.QueuedConnection" musicstreamer/player.py` matches (explicit queued connection for twitch_resolved self-slot)
- Python smoke: `python -c "from musicstreamer.player import Player; Player.title_changed; Player.failover"` exits 0
- If spike=DROP_MPV: `! grep -qE "subprocess\.Popen.*mpv|\"mpv\"" musicstreamer/player.py`
- If spike=KEEP_MPV: `test -f musicstreamer/_popen.py` AND `grep -q "CREATE_NO_WINDOW" musicstreamer/_popen.py`
  </acceptance_criteria>
  <done>player.py is a QObject with typed Qt signals; bus wiring calls `bus.enable_sync_message_emission()` exactly once immediately before `bus.add_signal_watch()` (D-07 literal); all timer/thread-marshaling uses Qt primitives; streamlink is library-API; YouTube path follows the spike decision. Zero GLib cross-thread calls remain.</done>
</task>

</tasks>

<verification>
Forbidden-pattern sweeps MUST all return empty:
1. `grep -E "GLib\.(idle_add|timeout_add|source_remove)" musicstreamer/player.py` → empty
2. `grep -E "^import dbus|^from dbus|DBusGMainLoop" musicstreamer/player.py` → empty
3. `grep -E "subprocess\.(run|Popen)\(\[.streamlink" musicstreamer/player.py` → empty (streamlink library-only)
4. `grep 'bus.connect("sync-message"' musicstreamer/player.py` → empty (no sync handlers, Pitfall 5)
5. `grep 'bus.connect("sync-message"' musicstreamer/gst_bus_bridge.py` → empty

Required-pattern gates (D-07 literal):
- `grep -c "bus\.enable_sync_message_emission" musicstreamer/player.py` → exactly `1`
- `grep -q "enable_sync_message_emission" musicstreamer/gst_bus_bridge.py` → matches
- Source order in `player.py`: `enable_sync_message_emission` line < `add_signal_watch` line

Plus: `grep -c "Signal(" musicstreamer/player.py` must be ≥ 6 (six class-level typed signals).

The pytest-qt signal-based tests land in Plan 35-05 — this plan does NOT run the full test suite because most existing tests use GLib-based mocks that only work against the old player.py. Smoke-only import check + grep gates are the acceptance bar here.
</verification>

<success_criteria>
1. `musicstreamer/gst_bus_bridge.py` exists, exports `GstBusLoopThread` + `attach_bus`, and passes its smoke test. `attach_bus` calls `bus.enable_sync_message_emission()` and `bus.add_signal_watch()` (in that order) and registers NO sync handlers.
2. `musicstreamer/player.py` inherits from `QObject` with class-level Signals for title/failover/offline/playback_error/twitch_resolved/elapsed_updated.
3. `musicstreamer/player.py` calls `bus.enable_sync_message_emission()` exactly once, immediately before `bus.add_signal_watch()`, satisfying D-07 literally and PORT-02 grep gate.
4. Zero `GLib.idle_add`, `GLib.timeout_add`, `GLib.source_remove` in `player.py`.
5. Zero `dbus-python` imports in `player.py`.
6. `_play_twitch` uses `streamlink.Streamlink().streams(url)` — no subprocess.
7. `_play_youtube` implements the spike-decided branch (DROP_MPV or KEEP_MPV) with all timers on QTimer.
8. `python -c "from musicstreamer.player import Player"` imports cleanly under Python with PySide6 + gi installed.
</success_criteria>

<output>
After completion, create `.planning/phases/35-backend-isolation/35-04-SUMMARY.md` recording: (a) spike branch chosen, (b) signal contract summary for downstream plans, (c) known-failing tests list (most tests using the old GLib-mocking pattern will now fail — Plan 35-05 rewrites them).
</output>
