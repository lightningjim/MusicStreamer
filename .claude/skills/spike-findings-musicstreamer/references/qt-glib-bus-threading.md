# Qt ↔ GLib Thread Interop: GStreamer Bus Handlers in a PySide6 App

Validated during Phase 43.1 (Windows Media Keys / SMTC). Two cross-platform correctness rules discovered together while debugging Windows-only bus-handler failure, then validated by reproducing a latent Linux regression after the first fix.

Both rules apply to any MusicStreamer code that wires a GStreamer bus into a Qt application.

---

## Rule 1 — `bus.add_signal_watch()` MUST run on the thread whose thread-default MainContext is iterated

### Failure mode (Windows)

`bus.add_signal_watch()` called inline on the Qt main thread attaches its `GSource` to the main thread's **default MainContext**. On Windows no one iterates the default MainContext (PySide6 does not integrate GLib with `QEventLoop`). Result: bus handlers for `message::error`, `message::tag`, `message::buffering` silently **never fire**. No ICY titles, no error-driven failover, no buffering UI — pipeline just plays silently if the stream happens to work and stays frozen if it doesn't.

On Linux, the same code usually worked by coincidence: on most distros the default MainContext is iterated by PyGObject's default loop integration, so handlers dispatched on main. The Windows failure only exposed the latent fragility.

### Correct pattern

Marshal `add_signal_watch()` onto the thread whose `MainLoop.run()` is iterating *that* thread's thread-default MainContext. Project convention: a single `GstBusLoopThread` daemon per process (`musicstreamer/gst_bus_bridge.py`), with a `run_sync(callable)` helper that executes a callable on the bridge thread via a `GLib.idle_add` + `Event` handshake.

```python
from musicstreamer.gst_bus_bridge import GstBusLoopThread

_bridge = _ensure_bus_bridge()  # module-level singleton, start()'d lazily
bus = pipeline.get_bus()
bus.enable_sync_message_emission()           # D-07: BEFORE add_signal_watch
_bridge.run_sync(lambda: bus.add_signal_watch())
bus.connect("message::error", self._on_gst_error)
bus.connect("message::tag",   self._on_gst_tag)
bus.connect("message::buffering", self._on_gst_buffering)
```

Order matters. `bus.enable_sync_message_emission()` must be called before `add_signal_watch()`. `push_thread_default` from the main thread **will not work** (it raises the GLib `acquired_context` assertion because the bridge's loop already acquired that context); only marshaling the `add_signal_watch` call onto the bridge thread itself satisfies GLib's contract.

### Anti-pattern

```python
bus.add_signal_watch()                       # attaches to WHATEVER MainContext main is currently bound to
                                             # — on Windows, that context is never iterated → DEAD SILENCE
```

### Fix commit

`5827062 fix(43.1): marshal add_signal_watch onto the bridge thread` (via `musicstreamer/gst_bus_bridge.py::GstBusLoopThread.run_sync`).

---

## Rule 2 — `QTimer.singleShot(0, callable)` from a non-Qt thread SILENTLY DROPS

### Failure mode (Windows + Linux once Rule 1 is applied)

`QTimer.singleShot(0, fn)` posts `fn` to the **calling thread's** Qt event loop. When the calling thread is the GLib bus-loop thread — a pure `GLib.MainLoop`, not a `QThread`, with no `QEventLoop` running — there is nothing to dispatch the timer. The call returns successfully; the callable silently never runs.

This is distinct from Qt `Signal.emit(...)` with `AutoConnection` / `QueuedConnection`, which correctly queues across threads because the signal machinery looks at the **receiver's** thread affinity, not the current thread's event loop.

In Phase 43.1 this manifested as every Shoutcast/Icecast stream dying at exactly 10 s:
- `_on_gst_tag` (bus-loop thread) called `QTimer.singleShot(0, self._cancel_timers)` to cancel the `BUFFER_DURATION_S = 10` failover timer when ICY data arrived.
- The singleShot vanished. The cancel never ran.
- The failover timer fired at 10 s. `_on_timeout` → `_try_next_stream` → `pipeline.set_state(NULL)` → "Stream exhausted" toast.

Symptom was cross-OS. Pre-Rule-1-fix, Windows appeared to have a different bug (no bus handlers at all); post-fix, both OSes exhibited the 10 s death because bus handlers now reliably dispatched on the bridge thread — so `singleShot`-from-bridge-thread was now reliably broken everywhere.

### Diagnostic tell

The GStreamer debug log shows a clean external `unlock()` → `stop()` → `dispose()` teardown at the stop instant — **no error message**. If you see error-less external teardowns on a timer-ish cadence, suspect a silently-dropped singleShot.

### Correct pattern

Add a `Signal()` on the `QObject` whose slot you want to invoke, connect it in `__init__` with `Qt.ConnectionType.QueuedConnection`, and emit it from the bus handler:

```python
class Player(QObject):
    # Class-level Signals (Pitfall 4 — MUST be class-scope, not instance)
    _cancel_timers_requested  = Signal()   # bus-loop → main: stop failover timer
    _error_recovery_requested = Signal()   # bus-loop → main: run recovery

    def __init__(self, parent=None):
        super().__init__(parent)
        ...
        self._cancel_timers_requested.connect(
            self._cancel_timers, Qt.ConnectionType.QueuedConnection
        )
        self._error_recovery_requested.connect(
            self._handle_gst_error_recovery, Qt.ConnectionType.QueuedConnection
        )

    def _on_gst_tag(self, bus, msg):                  # ← bus-loop thread
        self._cancel_timers_requested.emit()          # correctly marshals to main
        ...

    def _on_gst_error(self, bus, msg):                # ← bus-loop thread
        self._error_recovery_requested.emit()         # correctly marshals to main
```

Once execution reaches the main thread via the queued signal, nested `QTimer.singleShot(0, ...)` calls inside the slot are fine — they post to main's own event loop and dispatch as expected.

### Anti-pattern

```python
def _on_gst_tag(self, bus, msg):                      # ← bus-loop thread
    ...
    QTimer.singleShot(0, self._cancel_timers)         # ← SILENTLY DROPS
```

### Fix commit

`f1333ed fix(43.1): marshal bus-loop → main via queued Signal, not QTimer.singleShot`.

### Rule of thumb

> Any `QTimer` / `QWidget` / Qt-affined state change invoked from a GStreamer bus handler **must** go through a queued Qt `Signal`. Never pass a bare callable to `QTimer.singleShot` from a non-`QThread` thread. Reserve `QTimer.singleShot(0, ...)` for main-thread → main-thread deferral only.

Cross-thread `Signal.emit()` is correct — the title-update path (`self.title_changed.emit(title)` from the same bus handler) has always worked. The bug was specifically the bare-callable `singleShot`.
