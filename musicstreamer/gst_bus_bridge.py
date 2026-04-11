"""GStreamer bus -> Qt main thread bridge (Phase 35 / PORT-02 / D-07).

Runs a GLib.MainLoop on a daemon thread so GStreamer's bus signal watches
fire even though the main thread runs Qt's event loop. Handlers installed
via bus.connect(...) after attach_bus() run on THAT thread and must emit
Qt signals (queued connection, cross-thread) to reach the main thread.

D-07 contract (literal from CONTEXT.md):
- bus.enable_sync_message_emission() MUST be called on each pipeline bus.
- Async bus.add_signal_watch() dispatches handlers on the bridge thread's
  GLib.MainLoop. Sync message handlers (bus.connect for the sync signal)
  are explicitly NOT registered -- they would stall the GStreamer streaming
  thread (RESEARCH.md Pitfall 5).

Thread-safety contract:
- Emitting a Qt Signal from any thread is safe -- Qt auto-selects a queued
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
        # Use the default main context -- simpler than pushing a thread-default,
        # and sufficient because this process has no other GLib code that would
        # race on the default context (RESEARCH.md anti-patterns section).
        self._loop = GLib.MainLoop.new(None, False)
        # Signal readiness from INSIDE the loop so callers that poll
        # is_running immediately after start() see True (the loop has
        # actually entered its run state, not merely been constructed).
        def _signal_ready() -> bool:
            self._ready.set()
            return False  # one-shot
        GLib.idle_add(_signal_ready)
        self._loop.run()

    def stop(self) -> None:
        if self._loop and self._loop.is_running():
            # quit from inside the loop via an idle source -- the only
            # GLib.idle_add call permitted in Phase 35 code (it lives outside
            # player.py so PORT-01's player.py grep gate is unaffected).
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

    DO NOT register a handler for the sync message signal -- sync handlers
    run on the GStreamer streaming thread and must return instantly
    (Pitfall 5). This helper intentionally does not expose such a hook.
    """
    bus.enable_sync_message_emission()  # D-07 literal -- also a PORT-02 gate
    bus.add_signal_watch()               # async watch, dispatched on bridge thread
