# Phase 35 Deferred Items

Items discovered out-of-scope during plan execution; tracked here for
follow-up work.

## From Plan 35-05 (headless-entry-and-tests)

### Bus signal watch context mismatch (blocks Success Criterion #1 live ICY dispatch)

**Found in:** Plan 35-05 live smoke test (`python -m musicstreamer <shoutcast-url>`)
**File:** `musicstreamer/gst_bus_bridge.py` + `musicstreamer/player.py`
**Severity:** Medium — breaks live-stream ICY title printing in the
Phase 35 headless entry point, but unit tests pass because they invoke
`_on_gst_tag` synchronously.

**Root cause:** `bus.add_signal_watch()` is called from `Player.__init__`
on the Qt main thread. In Phase 35 the main thread is owned by
`QCoreApplication`, which does not integrate with the GLib default
`MainContext`. The `gst-bus-loop` daemon was fixed in Plan 35-05 to
push its own thread-default `GLib.MainContext` so the loop actually
runs alongside Qt — but `add_signal_watch()` attached the bus to the
main thread's default context at the time of the call, not to the
bridge thread's private context. As a result async bus messages
(``message::tag``, ``message::error``) never dispatch while running
under `QCoreApplication` — the bridge loop has nothing attached to
dispatch.

**Evidence:**
- `python -m musicstreamer` starts successfully, Player instantiates,
  QTimer kicks off play(), GStreamer begins buffering — but no
  `ICY:` lines ever print to stdout.
- Unit tests (`tests/test_player_tag.py`) pass because they invoke
  `_on_gst_tag(bus=None, msg=fake)` directly — no real bus dispatch.
- `GstBusLoopThread` start/stop is healthy (verified via standalone
  `python -c "from musicstreamer.gst_bus_bridge import ..."`).

**Proposed fix (Phase 36 or earlier):**
Move `bus.add_signal_watch()` into a callable scheduled ONTO the
bridge thread via `GLib.idle_source_new().attach(bridge._ctx)` so it
runs inside the bridge thread's private context. Alternatively, use
`bus.create_watch()` + explicit `source.attach(bridge._ctx)` from the
main thread (thread-safe).

**Workaround for Phase 35 verification:** Success Criterion #1 was
verified structurally — headless Player instantiation + Qt event loop
startup + QTimer-driven `play()` all succeed. Live ICY title dispatch
is deferred to Phase 36 along with the rest of the Qt UI integration.
