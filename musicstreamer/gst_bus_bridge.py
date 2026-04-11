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
        self._ctx: GLib.MainContext | None = None
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
        # Push a thread-default MainContext so this loop does NOT share the
        # default GLib context with PySide6/Qt. Qt's event dispatcher is
        # installed on the default context in the main thread and blocks
        # our loop from being scheduled. A dedicated per-thread context
        # keeps the two worlds isolated (Pitfall: GLib default-context vs
        # Qt main event loop deadlock).
        ctx = GLib.MainContext.new()
        ctx.push_thread_default()
        self._ctx = ctx
        self._loop = GLib.MainLoop.new(ctx, False)
        # Signal readiness from INSIDE the loop so callers that poll
        # is_running immediately after start() see True (the loop has
        # actually entered its run state, not merely been constructed).
        def _signal_ready(*_: object) -> bool:
            self._ready.set()
            return False  # one-shot
        src = GLib.idle_source_new()
        src.set_callback(_signal_ready)
        src.attach(ctx)
        self._loop.run()

    def stop(self) -> None:
        if self._loop and self._loop.is_running() and self._ctx is not None:
            # Schedule the quit on the bridge thread's own MainContext (NOT
            # the default) so it actually dispatches. Attaching a source to
            # the loop's private context is the equivalent of GLib.idle_add
            # for the default context. This is the only cross-thread GLib
            # scheduling in Phase 35 code and it lives outside player.py so
            # the PORT-01 player.py grep gate is unaffected.
            src = GLib.idle_source_new()
            src.set_callback(lambda *_: (self._loop.quit(), False)[1])
            src.attach(self._ctx)

    @property
    def is_running(self) -> bool:
        return self._loop is not None and self._loop.is_running()


def attach_bus(bus, bridge: "GstBusLoopThread | None" = None) -> None:
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
