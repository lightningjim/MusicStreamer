# Phase 62: Audio Buffer Underrun Resilience — Research

**Researched:** 2026-05-07
**Domain:** GStreamer playbin3 BUFFERING semantics; Qt/PySide6 cross-thread state machines; structured stdlib logging
**Confidence:** HIGH (project-internal patterns) / HIGH (GStreamer BUFFERING semantics) / MEDIUM (`buffering-mode` field surface in PyGObject — see Open Questions)

## Summary

Phase 62 ships **instrumentation only**. Every architectural decision is already locked in `62-CONTEXT.md` (D-01..D-09) — this research's job is to confirm those decisions are implementable on the project's existing surface and to surface the small set of design micro-choices the planner still has to make.

Three findings drive the plan shape:

1. **GStreamer's BUFFERING message IS the underrun signal — there is no separate `GST_MESSAGE_BUFFERING_HIGH/LOW`.** `[VERIFIED: gst-docs/buffering.md]` The application is supposed to PAUSE on `percent < 100` and resume on `percent == 100`. CONTEXT D-01 already encodes this exactly. We need ONE bus subscription site (the existing `_on_gst_buffering` at `player.py:448`), no new bus wiring.
2. **The cycle state machine has six fields, four predicates, and one terminator-fan-in.** Wrapped in a small `_BufferUnderrunTracker` helper class it stays self-contained; flat-on-Player it adds ~6 attributes to `__init__`. RESEARCH recommends the helper class — pure, injectable clock, easy to unit-test without instantiating `Player`.
3. **All four threading constraints are already solved precedents in this codebase.** Queued Signals from bus-loop → main (`_cancel_timers_requested`, `_error_recovery_requested`, `_playbin_playing_state_reached` at `player.py:89-101`); pre-built `QTimer` parented to `self` (`player.py:148-180`, four instances); per-URL state reset at `player.py:545`; bound-method connect (QA-05). The new code is structurally identical to existing wiring — no novel patterns.

**Primary recommendation:** Implement `_BufferUnderrunTracker` as a tiny pure class (~80 lines, no Qt, injectable clock); wire it into `Player` via three thin call-sites (`_on_gst_buffering`, `_try_next_stream`/`stop`/`pause`, `closeEvent`-driven shutdown). Add ONE new class-level Signal `underrun_recovery_started` (queued to MainWindow). Bump `__main__.py:222` `logging.basicConfig` to also include INFO for `musicstreamer.player`. Use key=value single-line log format. Defer the optional `_underrun_event_count` stats-for-nerds row — adds churn for a diagnostic that already lives in the log.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Underrun trigger definition (D-01..D-04)**
- **D-01:** An underrun event is any `GST_MESSAGE_BUFFERING` with `percent < 100` while the URL's tracker is **armed** (D-04). The existing `_on_gst_buffering` handler at `player.py:448` is the single observation site; no new bus subscriptions.
- **D-02:** Coalesce to **one event per recovery cycle**. The cycle opens on the first `percent < 100` post-arming and closes on the first `percent == 100` thereafter (or on a terminator, D-03). Exactly one structured log line is written at close, carrying `{start_ts, end_ts, duration_ms, min_percent, station_id, station_name, url, outcome, cause_hint}`. The cycle's `min_percent` is updated on every BUFFERING message during the open window; the rest of the fields are captured at open and finalized at close.
- **D-03:** **Force-close on terminator events** with `outcome` tag. Hooks: `_try_next_stream` (→ `failover`), `stop()` (→ `stop`), `pause()` (→ `pause`), explicit `set_state(NULL)` paths inside `_try_next_stream` (→ `failover`, dedup with above), and process shutdown / `closeEvent` (→ `shutdown`). Natural close at `percent == 100` uses outcome `recovered`. No watchdog timeout in this phase.
- **D-04:** **Arm on first `percent == 100` per URL.** New per-URL state `_underrun_armed: bool = False`, reset to `False` inside `_try_next_stream` at the same site that already resets `_last_buffer_percent = -1` (Phase 47.1 D-14). Inside `_on_gst_buffering`, the first `percent == 100` flips arm to `True`. While unarmed, `percent < 100` is the initial fill — observed but not opened as a cycle. Lifecycle mirrors Phase 47.1's sentinel reset exactly.

**Recovery indicator UX (D-05..D-08)**
- **D-05:** Toast-only indicator. No new always-visible chrome. Phase 47.1 stats-for-nerds bar continues to honor its hamburger-menu toggle and is NOT auto-shown during a cycle.
- **D-06:** Toast text `Buffering…` (U+2026 ellipsis). Exactly one toast per cycle. No recovery / "back-to-normal" toast.
- **D-07:** Dwell threshold = 1500 ms. Cycle open starts a `QTimer.singleShot(1500, …)` on the main thread. If the cycle closes before the timer fires, cancel the timer — no toast, still log.
- **D-08:** Toast cooldown = 10 000 ms. Wall-clock-based; persists across station changes. Subsequent cycles within the cooldown window still log normally — only the user-facing toast is debounced.

**Phase 16 invariant (D-09)**
- **D-09:** `BUFFER_DURATION_S = 10` and `BUFFER_SIZE_BYTES = 10 * 1024 * 1024` MUST NOT be modified. Behavior fix is deferred to a follow-up phase, gated on observed root cause from collected logs.

### Claude's Discretion (research recommendations below)

- **Cause-attribution depth:** keep `cause_hint='unknown'` end-to-end this phase; only flip to `'network'` when `_on_gst_error` has fired in the same cycle. Recommendation: SHIP THE MINIMUM. CPU-sampling, clock-skew, decoder-stall heuristics are premature without observed log data.
- **Log sink:** stdlib `logging.getLogger(__name__)` at INFO. Bump `__main__.py:222` `logging.basicConfig` so INFO surfaces for `musicstreamer.player`. Recommendation: use `logging.getLogger("musicstreamer.player").setLevel(logging.INFO)` after the basicConfig — leaves WARNING the project-wide default but lets player INFO through (see "Logging Integration" below).
- **Per-cycle log format:** key=value single-line. Recommendation: see "Code Examples §1".
- **Underrun counter on stats-for-nerds:** DEFER. See "Stats-for-nerds counter" below — the log already carries the count via wc -l on the structured line; UI surface adds churn for a diagnostic already accessible via grep.

### Deferred Ideas (OUT OF SCOPE)

- **Behavior fix (success criterion #3)** — buffer-duration/size adjustment, reconnect logic, low-watermark threshold tuning, smarter underrun recovery. Follow-up phase, gated on observed log data.
- **Cause attribution beyond outcome + duration + min_percent** — CPU sampling, wall-clock-vs-pipeline-clock skew detection, decoder-vs-network discrimination.
- **File-based log sink** — dedicated `~/.local/share/musicstreamer/buffer-events.log` ring file with rotation.
- **In-app log viewer / hamburger menu "Show buffer events…"**
- **Auto-show stats-for-nerds buffer bar during a cycle** — explicitly rejected.
- **Recovery / "back-to-normal" affirmative toast** — explicitly rejected.
- **Watchdog cycle timeout** — explicitly rejected.
- **30 s cooldown variant** — considered, rejected in favor of 10 s.
- **Underrun counter in stats-for-nerds row** — Discretion-deferred.
- **Throttled-network repro fixture** — fix is deferred, fixture is not needed yet.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUG-09 | Intermittent audio dropouts/stutters when the GStreamer buffer can't keep up are observable, attributable, and (once root-caused) mitigated. | This phase ships instrumentation. Standard stack confirms `message::buffering` with `percent < 100` IS the underrun signal `[VERIFIED: gst-docs]`. Cycle state machine is the standard pattern (see Architecture Patterns §1). The behavior-fix half of BUG-09 is deferred to a follow-up per D-09. |

---

## Project Constraints (from CLAUDE.md)

- **Routing:** GStreamer/PyInstaller/Qt-GLib threading work routes to `Skill("spike-findings-musicstreamer")`. Specifically `references/qt-glib-bus-threading.md` Pitfalls 1, 2, 3 are binding for this phase. `[CITED: ./CLAUDE.md]`
- **Deployment target:** Linux Wayland (GNOME Shell), DPR=1.0; never X11; no HiDPI/fractional scaling. `[CITED: $HOME/.claude/projects/.../MEMORY.md]` — Toast and QTimer behavior is already verified on this surface (Phase 47.1).
- **Origin remote:** QNAP Gitea with server-side push mirror to GitHub — treat all pushes as public. `[CITED: MEMORY.md]` Log lines must NOT carry secrets (cookies, API keys). The fields locked in D-02 (`station_id, station_name, url, outcome, cause_hint, ...`) are user-facing strings already; no auth tokens leak.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| BUFFERING bus-message observation | Player (bus-loop thread) | — | Already the single observation site for `_on_gst_buffering`; bus handlers belong on the bridge thread (Pitfall 2) |
| Cycle state machine (open/close/min/arm) | Player (bus-loop thread for updates) | Player (main thread for terminator force-close) | State updates triggered from bus messages run on bus-loop; terminator hooks (`pause`/`stop`/`_try_next_stream`) already run on main; cycle data structure is shared but writes are inherently serialized through D-04 arm gate + Qt's main-thread terminator hooks |
| Dwell timer (1500 ms threshold) | Player (main thread) | — | `QTimer` parented to `Player` per Pitfall 2; armed via queued Signal from bus-loop slot |
| Toast emission gate (10 s cooldown) | MainWindow (main thread) | — | `show_toast` lives on MainWindow; cooldown bookkeeping co-locates with the consumer; Player just emits a Signal, no UI knowledge |
| Structured log write | Player (main thread or bus-loop — see below) | — | Stdlib `logging` is thread-safe; can write from either thread. RECOMMENDATION: write from the thread that triggers cycle close, which is bus-loop for `recovered` and main for terminators. Both are safe. |
| Underrun counter (deferred) | Player (counter) → NowPlayingPanel (display) | — | Same shape as Phase 47.1 buffer-percent — Signal(int) + slot, would consume `QFormLayout` extension at `now_playing_panel.py:1377` |

---

## Standard Stack

### Core (already in pyproject)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyGObject (`gi.repository.Gst`) | 1.x via system / conda-forge | GStreamer bindings | `[VERIFIED]` Existing project dep at `player.py:38`; `Gst.Message.parse_buffering()` returns `int OR (int,)` per PyGObject convention `[CITED: lazka.github.io/pgi-docs/Gst-1.0/classes/Message.html]` |
| PySide6.QtCore | already pinned | QObject, QTimer, Signal, Qt.ConnectionType | `[VERIFIED]` Existing project dep |
| stdlib `logging` | bundled | Structured log lines | `[VERIFIED]` 14 modules already use `_log = logging.getLogger(__name__)` (grep result) |
| stdlib `time.monotonic` | bundled | Cooldown wall-clock for toast suppression | `[ASSUMED]` — not yet used in the codebase, but is the stdlib idiom for monotonically-increasing seconds (immune to wall-clock jumps) |
| pytest + pytest-qt | `>=9` / `>=4` (pyproject lines 28-29) | Test framework | `[VERIFIED]` Established harness pattern (`tests/test_player_buffering.py`) |

**No new dependencies are required.** Every library this phase needs is already pinned and exercised by existing tests.

**Version verification:**
```bash
# PyGObject and Gst are system/conda-forge — pinned via runtime not pyproject.
# pytest pinning verified at pyproject.toml lines 28-29.
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Per-Player flat attributes for cycle state | Small `_BufferUnderrunTracker` helper class | Flat: 6 new `self._underrun_*` fields in `__init__`, 4 predicates inlined into `_on_gst_buffering` and terminator hooks. Class: cleaner separation, injectable clock, unit-testable without instantiating `Player`. **Recommend the class** — see Pattern 1 below. |
| `time.monotonic()` for cooldown | `QDateTime.currentMSecsSinceEpoch()` | `time.monotonic()` is wall-clock-jump-immune, deterministic in tests via `monkeypatch.setattr("time.monotonic", lambda: 1234.0)`. `QDateTime` carries a Qt dep that's already loaded but is harder to mock cleanly. |
| `time.monotonic()` for cooldown | A dedicated `QTimer` + `setSingleShot(10_000)` flag flip | Adds a 4th timer to Player; a single float comparison is simpler. **Recommend `time.monotonic()`**. |
| Pre-built `QTimer` + `start()/stop()` for dwell | `QTimer.singleShot(1500, slot)` from main-thread queued slot | Either works on main thread. Pre-built mirrors the project's `_failover_timer` / `_eq_ramp_timer` / `_pause_volume_ramp_timer` convention (4 instances at `player.py:148-180`); enables `isActive()` checks; allows cancelling without lambda gymnastics. **Recommend pre-built `QTimer(self)`** for consistency. |
| key=value log format | JSON one-liner | JSON is easier to parse with `jq`. key=value is easier to grep with `awk -F=`. Existing codebase uses `_log.warning("blah %s for %r: %s", a, b, c)` style — neither structured. RECOMMENDATION: key=value because grep is the diagnosis tool here, not a log-aggregation pipeline. |

---

## Architecture Patterns

### System Architecture Diagram

```
GstBusLoopThread                                Main Qt Thread
─────────────────                                ──────────────

playbin3 bus
   │
   │ message::buffering (percent)
   ▼
_on_gst_buffering(bus, msg)
   │
   ├── parse percent  (Pitfall 1: tuple-or-int)
   │
   ├── tracker.observe(percent, ts) ───────┐
   │     │                                 │
   │     ├── armed gate (D-04)             │
   │     │   first 100 → flip armed=True   │
   │     │                                 │
   │     ├── opens cycle on first <100     │
   │     │   while armed                   │
   │     │                                 │
   │     ├── updates min_percent           │
   │     │                                 │
   │     └── closes cycle on next 100      │
   │         → returns CycleClose record   │
   │                                       │
   ├── if cycle just opened:               │
   │     emit _underrun_cycle_opened ──────┼──→ slot starts QTimer.singleShot(1500, …)
   │     (queued Signal — Pitfall 2)       │
   │                                       │
   └── if cycle just closed (recovered):   │     ┌──────────────────────────────────┐
         emit _underrun_cycle_closed ──────┼──→  │  on cycle CLOSE:                  │
         (carrying record + outcome)       │     │   - if dwell timer active → stop  │
                                           │     │   - log structured line @ INFO    │
                                           │     └──────────────────────────────────┘
                                           │
Main-thread terminator hooks               │
  pause()                                  │     ┌──────────────────────────────────┐
  stop()                                   │     │  on dwell-timer FIRE:              │
  _try_next_stream()                       │     │    - emit underrun_recovery_      │
  closeEvent()  (via MainWindow)           │     │       started (queued)            │
     │                                     │     │  → MainWindow slot:               │
     ▼                                     │     │    - check now - last_toast_ts >  │
  tracker.force_close(outcome)             │     │       10s cooldown                │
     │                                     │     │    - show_toast("Buffering…")     │
     └─→ if cycle was open:                │     │    - update last_toast_ts         │
           - cancel dwell timer            │     └──────────────────────────────────┘
           - log structured line @ INFO    │
                                           │
```

**Data-flow trace (single underrun cycle that triggers a toast):**

1. Stream is playing. `_on_gst_buffering` receives `percent=100` → `tracker.observe(100, t0)` → arm flips to `True`. (D-04)
2. Network hiccup. `_on_gst_buffering` receives `percent=80` → `tracker.observe(80, t1)` → opens cycle (start_ts=t1, min_percent=80). Emits `_underrun_cycle_opened` (queued Signal). Main-thread slot starts dwell `QTimer(1500)`.
3. `percent=60` → `tracker.observe(60, t2)` → updates min_percent=60. No new emit (already open).
4. Dwell timer fires at t1 + 1500ms. Slot emits `underrun_recovery_started`. MainWindow checks cooldown (`now - last_toast_ts > 10.0`), passes, calls `show_toast("Buffering…")`.
5. `percent=100` → `tracker.observe(100, t3)` → closes cycle. Emits `_underrun_cycle_closed` carrying `{start_ts=t1, end_ts=t3, duration_ms=t3-t1, min_percent=60, station_id, station_name, url, outcome='recovered', cause_hint='unknown'}`. Main-thread slot writes structured log line at INFO; cancels dwell timer (already fired — no-op).

**Sub-1.5s recovery:** In step 4, if `percent=100` arrives BEFORE the dwell timer fires, `tracker.observe(100, …)` closes the cycle in step 5 directly. The slot for `_underrun_cycle_closed` cancels the still-active dwell timer (no toast). Log line still written — silent recovery.

**Force-close (terminator):** User clicks pause. `pause()` → `tracker.force_close('pause')`. If a cycle is open, returns CycleClose with `outcome='pause'`. Slot writes log line, cancels dwell timer.

### Recommended Project Structure

```
musicstreamer/
├── player.py                              # MODIFIED
│   ├── module-level _log = logging.getLogger(__name__)   # NEW (first logger in file)
│   ├── class _BufferUnderrunTracker                       # NEW (~80 lines, no Qt)
│   └── class Player(QObject)
│       ├── new Signal: underrun_recovery_started          # NEW
│       ├── new Signal: _underrun_cycle_opened             # NEW (internal queued)
│       ├── new Signal: _underrun_cycle_closed             # NEW (internal queued)
│       ├── new attr: self._tracker = _BufferUnderrunTracker(...)
│       ├── new attr: self._underrun_dwell_timer (QTimer)
│       ├── new attr: self._last_underrun_toast_ts: float | None = None  # if cooldown lives on Player
│       ├── _on_gst_buffering — extended with tracker.observe(...)
│       ├── _try_next_stream — adds tracker.force_close('failover')
│       ├── pause — adds tracker.force_close('pause')
│       └── stop — adds tracker.force_close('stop')
├── ui_qt/main_window.py                   # MODIFIED
│   ├── connect player.underrun_recovery_started → _on_underrun_recovery_started (queued)
│   ├── new attr: self._last_underrun_toast_ts: float = 0.0   # if cooldown lives on MainWindow
│   ├── new slot: _on_underrun_recovery_started — show_toast + cooldown gate
│   └── closeEvent — calls player.shutdown_underrun_tracker() (or similar)
├── __main__.py                            # 1-line change
│   └── line 222: extend basicConfig OR add logging.getLogger("musicstreamer.player").setLevel(INFO)
└── (constants.py UNCHANGED — D-09 invariant)

tests/
├── test_player_underrun_tracker.py        # NEW — pure unit tests on _BufferUnderrunTracker
├── test_player_underrun.py                # NEW — Player-level integration (queued Signal emit)
└── test_main_window_underrun.py           # NEW (or extend existing test_main_window.py)
```

### Pattern 1: Helper class for the cycle state machine (RECOMMENDED)

**What:** A small pure Python class (~80 lines, no Qt, no GStreamer) that owns the cycle state. `Player` constructs one, calls `observe(percent, ts)` from the bus handler, calls `force_close(outcome, ts)` from terminators. Both methods return either `None` (no transition) or a `CycleEvent` that the caller acts on.

**When to use:** When the state machine has more than 3 transitions and ≥ 2 call sites. Phase 62 has 4 inputs (observe, force_close × 4 outcomes) → qualifies.

**Tradeoff vs. flat attributes:**

| Aspect | Helper class | Flat attributes |
|--------|--------------|-----------------|
| Lines added to `Player.__init__` | 1 (`self._tracker = _BufferUnderrunTracker(...)`) | ~6 (six fields) |
| Lines added to `_on_gst_buffering` | ~3 (call observe, branch on return) | ~15 (inline logic) |
| Unit-testability | Direct — no Qt, no Player, no MagicMock pipeline | Indirect — must instantiate Player with mocked pipeline |
| Injectable clock for tests | Yes — pass `clock=lambda: 100.0` to constructor | No — `time.monotonic()` calls inline; need monkeypatch |
| Cohesion | High | Low (state spread across `Player`) |
| Risk of hand-rolling | Low — class is ≤ 80 lines | Medium — easy to forget the arm gate or min_percent update |

**Recommended class shape:**

```python
# Source: project convention (mirrors existing helper patterns like _ArtistPageParser in gbs_api.py)
import time
from dataclasses import dataclass
from typing import Callable, Optional

@dataclass(frozen=True)
class _CycleClose:
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
    """Cycle state machine for buffer-underrun events (Phase 62).

    Pure: no Qt, no GStreamer. Emits return values; caller wires them
    to Signals / log writes.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._reset_per_url()

    def _reset_per_url(self) -> None:
        """Called by Player from the same site as _last_buffer_percent = -1
        (D-04 mirrors Phase 47.1 D-14)."""
        self._armed: bool = False
        self._open: bool = False
        self._start_ts: float = 0.0
        self._min_percent: int = 100
        self._station_id: int = 0
        self._station_name: str = ""
        self._url: str = ""
        self._cause_hint: str = "unknown"

    # Called by Player at _try_next_stream when binding a new URL.
    def bind_url(self, station_id: int, station_name: str, url: str) -> None:
        self._reset_per_url()
        self._station_id = station_id
        self._station_name = station_name
        self._url = url

    # Bus-handler call site.
    # Returns "OPENED" sentinel (or a small dataclass) the caller uses to
    # decide whether to emit _underrun_cycle_opened. Returns _CycleClose
    # on natural close. Returns None otherwise.
    def observe(self, percent: int) -> Optional[object]:
        if not self._armed:
            if percent == 100:
                self._armed = True
            return None
        if not self._open:
            if percent < 100:
                self._open = True
                self._start_ts = self._clock()
                self._min_percent = percent
                return "OPENED"
            return None
        # cycle is open
        if percent < 100:
            if percent < self._min_percent:
                self._min_percent = percent
            return None
        # percent == 100 → close
        return self._close("recovered")

    # Terminator call site.
    def force_close(self, outcome: str) -> Optional[_CycleClose]:
        if not self._open:
            return None
        return self._close(outcome)

    def note_error_in_cycle(self) -> None:
        """Called from _on_gst_error before _try_next_stream advances the queue.
        D-02 / Discretion: cause_hint flips to 'network' if an error has
        fired during the open cycle."""
        if self._open:
            self._cause_hint = "network"

    def _close(self, outcome: str) -> _CycleClose:
        end_ts = self._clock()
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
        # Reset cycle-level state but KEEP armed=True (still on same URL).
        self._open = False
        self._start_ts = 0.0
        self._min_percent = 100
        self._cause_hint = "unknown"
        return record
```

**Why this shape:**

- `clock=time.monotonic` is the default; tests inject a list-driven fake clock. Mirrors how `monkeypatch.setattr` is used in `tests/test_pls_fetch_token_monotonically_increments` (referenced in grep above).
- `observe()` returns sentinels (`None | "OPENED" | _CycleClose`). The caller (Player) is responsible for emitting the right Signal in response. This keeps the tracker free of Qt entirely.
- `bind_url()` is the single per-URL reset point — it's called from `_try_next_stream` at the same site that resets `_last_buffer_percent = -1` (line 545). One reset block, two reset operations.
- `note_error_in_cycle()` is the surface for the optional `cause_hint='network'` heuristic (D-02 / Discretion). Wiring is a single line in `_on_gst_error`.

### Pattern 2: Cross-thread queued Signal for cycle events (BINDING — Pitfall 2)

**What:** Bus handlers run on `GstBusLoopThread`, NOT a `QThread` and with no Qt event loop. They MUST NOT touch `QTimer` or call any Qt-affined slot directly. They emit Qt Signals connected with `Qt.ConnectionType.QueuedConnection`, which auto-marshal to the receiver's main thread.

**Source pattern (already established at `player.py:89-101, 195-208`):**

```python
# Source: musicstreamer/player.py:89-101 (existing _cancel_timers_requested pattern)
class Player(QObject):
    # NEW class-level Signals (Pitfall 4: must be class-scope, not instance)
    _underrun_cycle_opened     = Signal()         # bus-loop → main: arm dwell timer
    _underrun_cycle_closed     = Signal(object)   # bus-loop → main: write log line + cancel dwell
                                                  #   (object = _CycleClose dataclass)
    underrun_recovery_started  = Signal()         # main → MainWindow: show_toast (queued anyway,
                                                  #   harmless cross-tier)

    def __init__(self, ...):
        ...
        # Same shape as _cancel_timers_requested.connect(...) at line 195-197
        self._underrun_cycle_opened.connect(
            self._on_underrun_cycle_opened, Qt.ConnectionType.QueuedConnection
        )
        self._underrun_cycle_closed.connect(
            self._on_underrun_cycle_closed, Qt.ConnectionType.QueuedConnection
        )
```

**Why this pattern is binding (not optional):**

- `references/qt-glib-bus-threading.md` Pitfall 2 (cited in CLAUDE.md routing): `QTimer.singleShot(0, fn)` from a non-QThread silently drops. The fix commit `f1333ed` proves this is a real, observed regression in this codebase.
- Existing precedents (`_cancel_timers_requested`, `_error_recovery_requested`, `_try_next_stream_requested`, `_playbin_playing_state_reached`) — every bus-loop → main hop in the file uses queued Signals.

### Pattern 3: Pre-built QTimer parented to self (RECOMMENDED — matches project convention)

**What:** Construct the dwell timer in `Player.__init__` parented to `self`, single-shot, interval 1500ms. Connect `timeout` to the slot. The bus-handler-driven slot calls `.start()` to arm and `.stop()` to cancel.

**Source pattern (project has 4 instances at `player.py:148-180`):**

```python
# Source: musicstreamer/player.py:149-151 (_failover_timer template)
self._underrun_dwell_timer = QTimer(self)        # parented to self → main thread (Pitfall 2)
self._underrun_dwell_timer.setSingleShot(True)
self._underrun_dwell_timer.setInterval(1500)
self._underrun_dwell_timer.timeout.connect(self._on_underrun_dwell_elapsed)
```

**Why pre-built over `QTimer.singleShot(1500, slot)`:**

| Pre-built `QTimer(self)` | `QTimer.singleShot(1500, slot)` |
|--------------------------|----------------------------------|
| Matches `_failover_timer` / `_eq_ramp_timer` / `_pause_volume_ramp_timer` (4 instances) | Inconsistent with project convention |
| `isActive()` exposes "is the dwell currently armed?" cleanly | Requires a separate `self._dwell_armed: bool` flag |
| `.stop()` cancels on the close path | `singleShot` cancellation requires capturing the QTimer reference manually |
| Idempotent re-call: `start()` resets the interval — open-then-immediately-open does the right thing | Each call queues another fire — would need explicit cancellation |

### Pattern 4: Cooldown via `time.monotonic()` on MainWindow

**What:** Cooldown is a single float comparison — no extra timer.

```python
# Source: stdlib idiom; project-first usage (no prior `time.monotonic` callsite found)
import time

class MainWindow(QMainWindow):
    def __init__(self, ...):
        ...
        self._last_underrun_toast_ts: float = 0.0
        self._UNDERRUN_TOAST_COOLDOWN_S: float = 10.0   # D-08 wall-clock-based

    def _on_underrun_recovery_started(self) -> None:    # queued slot from Player
        now = time.monotonic()
        if now - self._last_underrun_toast_ts < self._UNDERRUN_TOAST_COOLDOWN_S:
            return
        self.show_toast("Buffering…")             # D-06 U+2026
        self._last_underrun_toast_ts = now
```

**Where the cooldown bookkeeping lives:** RECOMMEND **MainWindow**, not Player. The cooldown is a UI concern (suppress the toast); Player should not know about UI debouncing. Player's job is "tell MainWindow: a cycle exceeded the dwell threshold." MainWindow owns the toast surface and therefore the toast-suppression policy.

**Test injection:** `monkeypatch.setattr("musicstreamer.ui_qt.main_window.time.monotonic", lambda: 1234.0)` in tests.

### Anti-Patterns to Avoid

- **`QTimer.singleShot(1500, slot)` from `_on_gst_buffering`** — silently drops (Pitfall 2). MUST emit queued Signal first; arm timer in main-thread slot.
- **Touching `self._underrun_dwell_timer.start()` from `_on_gst_buffering`** — same Pitfall 2 violation. The bus handler may only emit Signals.
- **Using a self-capturing lambda for the new connect** — QA-05 violation. Use bound method `self._on_underrun_recovery_started`.
- **Forgetting per-URL reset on `_try_next_stream`** — Pitfall 3. The `_underrun_armed = False` reset MUST go in the same block as `_last_buffer_percent = -1` (line 545). With the helper class: call `self._tracker.bind_url(station_id, station_name, url)` in that block.
- **Logging from inside `_on_gst_buffering` before the queued Signal lands on main** — stdlib `logging` IS thread-safe, but the project's discipline is "bus handlers may only emit Signals" (Pitfall 2 generalization). Log from the main-thread slot for `_underrun_cycle_closed` to keep that invariant.
- **Modifying `BUFFER_DURATION_S` or `BUFFER_SIZE_BYTES` in `constants.py`** — D-09 is binding; ROADMAP success criterion #4 explicitly forbids it without an explicit decision in CONTEXT.md (which is not taken).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-thread bus-loop → main marshalling | Custom `queue.Queue` + `QTimer(50)` polling | Qt `Signal` with `Qt.ConnectionType.QueuedConnection` | The project's existing pattern (4 precedents); validated against Pitfall 2 |
| Wall-clock-jump-immune cooldown | Python `datetime.datetime.now()` differences | `time.monotonic()` | `time.monotonic()` is unaffected by NTP corrections, DST, manual clock changes |
| Structured log formatting | Hand-rolled `f"{key}={value} "` repeated 9 times | Single `_log.info(template, **fields)` with stable template | Logging.Formatter doesn't help with key=value; one canonical line in one place |
| Cycle state machine | Inline boolean dance in `_on_gst_buffering` | `_BufferUnderrunTracker` helper class | 4 inputs × 3 transitions × 5 terminator outcomes — high enough surface for a class |
| BUFFERING percent parsing | Hand-rolling `msg.get_structure().get_value("buffer-percent")` | `msg.parse_buffering()` (already used at `player.py:455-457`) | Pitfall 1 already handled at the existing site (`result[0] if isinstance(result, tuple) else int(result)`); reuse the same idiom |

**Key insight:** Every primitive this phase needs is either already in the codebase or in stdlib. There is no library to add. The risk surface is wiring discipline (Pitfalls 1/2/3), not algorithmic complexity.

---

## Common Pitfalls

### Pitfall 1: `parse_buffering()` returns int OR tuple depending on PyGObject version

**What goes wrong:** PyGObject sometimes flattens single-out-param returns to bare int, sometimes returns a 1-tuple. `[VERIFIED: tests/test_player_buffering.py:21-27]` codifies both shapes. New code in the cycle state machine MUST tolerate both.

**Why it happens:** GLib introspection's PyGObject binding behaves differently across distro versions; cross-OS bundles compound the variance.

**How to avoid:** Reuse the existing parser at `player.py:457`:
```python
percent = result[0] if isinstance(result, tuple) else int(result)
```
Don't add a second parser; the cycle tracker should consume the int that's already extracted.

**Warning signs:** A unit test passing on Linux but failing on Windows with `TypeError: '<' not supported between instances of 'tuple' and 'int'`.

### Pitfall 2: Bus handlers cannot touch QTimer / QWidget — must emit queued Signals

**What goes wrong:** `_on_gst_buffering` runs on `GstBusLoopThread`. Calling `self._underrun_dwell_timer.start()` directly from there is a QTimer access from a non-QThread → undefined behavior (Pitfall 2 cousins). `QTimer.singleShot(1500, slot)` silently drops.

**Why it happens:** The bridge thread iterates a `GLib.MainLoop`, not a `QEventLoop`. Qt timer machinery posts to the calling thread's event loop — there isn't one.

**How to avoid:** Bus handler emits `_underrun_cycle_opened` (Signal). Main-thread slot connected with `Qt.ConnectionType.QueuedConnection` arms the timer.

**Warning signs:** Toast never appears even though tracker logs show cycles opening. Check whether `_underrun_dwell_timer.isActive()` ever flips True.

### Pitfall 3: Per-URL reset must mirror Phase 47.1 D-14 exactly

**What goes wrong:** New URLs inherit `_underrun_armed=True` from the previous URL. The first `<100` on the new URL is treated as an underrun cycle — but it's actually the initial fill. Spurious log lines and a toast on every station change.

**Why it happens:** Forgetting to reset arm state in the same block at `player.py:545`.

**How to avoid:** Call `self._tracker.bind_url(...)` IMMEDIATELY adjacent to `self._last_buffer_percent = -1` in `_try_next_stream`. Phase 47.1 D-14 sentinel reset is the exact precedent — copy the pattern verbatim.

**Warning signs:** Tests show "Buffering…" toast firing on a station change before any real network hiccup. Or: log lines appear for cycles that close with `min_percent` near 0 immediately after a new station starts.

### Pitfall 4: Forgetting the `closeEvent` shutdown hook

**What goes wrong:** App is killed mid-cycle. The open cycle never closes. No log line is written for the in-flight underrun. (Minor diagnostic gap, not a crash.)

**Why it happens:** D-03 lists `shutdown` as a terminator outcome but the natural call site (`MainWindow.closeEvent`) is one-shot and not analogous to `pause/stop/_try_next_stream`.

**How to avoid:** Add `self._player.shutdown_underrun_tracker()` (or equivalent) call at top of `MainWindow.closeEvent`, before `super().closeEvent(event)`. Existing closeEvent already has a precedent of calling `self._media_keys.shutdown()` (line 355).

**Warning signs:** None at runtime — silent gap. Manifests as "phase 62 logs the user's most interesting underruns (pre-shutdown crashes) less reliably than mid-session ones."

### Pitfall 5: Bumping `logging.basicConfig` to INFO globally pollutes other modules

**What goes wrong:** Phase 62 wants INFO from `musicstreamer.player`. Bumping `logging.basicConfig(level=logging.INFO)` globally turns on chatter from `aa_import`, `gbs_api`, `mpris2`, etc. — most of which have INFO statements that were silenced by the WARNING default.

**Why it happens:** `basicConfig` is global; per-logger levels need a separate call.

**How to avoid:** Keep `basicConfig(level=logging.WARNING)` and ADD one line:
```python
logging.basicConfig(level=logging.WARNING)
logging.getLogger("musicstreamer.player").setLevel(logging.INFO)   # Phase 62 / BUG-09
```

**Warning signs:** stderr suddenly shows AA image fetch logs, GBS API logs, etc. that were never visible before. Means the `getLogger(...).setLevel(INFO)` was not scoped correctly.

---

## Code Examples

Verified patterns from existing code, with citations.

### Example 1: Single-line key=value structured log

```python
# Source: project-first format; key=value chosen over JSON for grep-ability.
# Field set is non-negotiable per D-02.
_log.info(
    "buffer_underrun "
    "start_ts=%.3f end_ts=%.3f duration_ms=%d min_percent=%d "
    "station_id=%d station_name=%r url=%r outcome=%s cause_hint=%s",
    record.start_ts, record.end_ts, record.duration_ms, record.min_percent,
    record.station_id, record.station_name, record.url,
    record.outcome, record.cause_hint,
)
```

**Sample output:**
```
INFO musicstreamer.player: buffer_underrun start_ts=12345.678 end_ts=12347.234 duration_ms=1556 min_percent=42 station_id=27 station_name='SomaFM Drone Zone' url='http://ice4.somafm.com/dronezone-128-mp3' outcome=recovered cause_hint=unknown
```

**Why `%r` for station_name and url:** Quotes them (handles spaces and special chars), and escapes embedded quotes — safe to grep with `awk -F'station_name=' '{print $2}'`.

### Example 2: Bus-handler integration (extends existing `_on_gst_buffering`)

```python
# Source: extends musicstreamer/player.py:448-461 — adds tracker.observe call after percent dedup.
def _on_gst_buffering(self, bus, msg) -> None:
    """Bus-loop-thread handler: parse buffer percent, emit Qt signal.

    Extended Phase 62 (BUG-09): drives _BufferUnderrunTracker cycle
    state machine. Tracker output dispatched via queued Signals
    (Pitfall 2 — bus-loop has no Qt event loop).
    """
    result = msg.parse_buffering()
    percent = result[0] if isinstance(result, tuple) else int(result)
    if percent == self._last_buffer_percent:
        return
    self._last_buffer_percent = percent
    self.buffer_percent.emit(percent)  # 47.1 contract — unchanged

    # Phase 62 cycle state machine (D-01..D-04)
    transition = self._tracker.observe(percent)
    if transition == "OPENED":
        self._underrun_cycle_opened.emit()             # queued → main: arm dwell timer
    elif transition is not None:                        # closed naturally
        self._underrun_cycle_closed.emit(transition)    # queued → main: log + cancel dwell
```

### Example 3: Main-thread cycle-opened slot (arms dwell timer)

```python
# Source: project pattern from musicstreamer/player.py:430 (_clear_recovery_guard idiom)
def _on_underrun_cycle_opened(self) -> None:
    """Main-thread slot. Arms the 1500ms dwell timer (D-07).

    QTimer is parented to self (main thread). start() is idempotent —
    if for any reason this lands while the timer is still active, the
    interval just resets, which is the correct behavior.
    """
    self._underrun_dwell_timer.start()
```

### Example 4: Main-thread cycle-closed slot (cancels dwell + logs)

```python
def _on_underrun_cycle_closed(self, record) -> None:
    """Main-thread slot. Writes structured log line; cancels in-flight
    dwell timer (cycle closed before 1500ms — silent recovery, D-07)."""
    self._underrun_dwell_timer.stop()    # idempotent — no-op if already fired/inactive
    _log.info(
        "buffer_underrun "
        "start_ts=%.3f end_ts=%.3f duration_ms=%d min_percent=%d "
        "station_id=%d station_name=%r url=%r outcome=%s cause_hint=%s",
        record.start_ts, record.end_ts, record.duration_ms, record.min_percent,
        record.station_id, record.station_name, record.url,
        record.outcome, record.cause_hint,
    )
```

### Example 5: Dwell-elapsed slot (emits `underrun_recovery_started`)

```python
def _on_underrun_dwell_elapsed(self) -> None:
    """Main-thread QTimer.timeout slot (D-07). Cycle has been open for 1500ms;
    notify MainWindow to consider showing the toast (cooldown gated there, D-08)."""
    self.underrun_recovery_started.emit()
```

### Example 6: MainWindow cooldown-gated toast slot

```python
# Source: project pattern from musicstreamer/ui_qt/main_window.py:280
#   self._player.cookies_cleared.connect(self.show_toast)
# Phase 62 adds a wrapper slot because the cooldown gate goes between Signal and toast.
import time

class MainWindow(QMainWindow):
    _UNDERRUN_TOAST_COOLDOWN_S: float = 10.0   # D-08

    def __init__(self, ...):
        ...
        self._last_underrun_toast_ts: float = 0.0
        # Phase 62: queued connection for completeness; same thread is fine but
        # explicit queueing keeps the policy "Player Signals are queued to MainWindow"
        # (matches all neighboring connects).
        self._player.underrun_recovery_started.connect(
            self._on_underrun_recovery_started, Qt.ConnectionType.QueuedConnection
        )

    def _on_underrun_recovery_started(self) -> None:
        """D-08 cooldown-gated toast. Wall-clock-based, persists across station changes."""
        now = time.monotonic()
        if now - self._last_underrun_toast_ts < self._UNDERRUN_TOAST_COOLDOWN_S:
            return
        self.show_toast("Buffering…")    # D-06 — U+2026 ellipsis
        self._last_underrun_toast_ts = now
```

### Example 7: Per-URL reset in `_try_next_stream` (Pitfall 3)

```python
# Source: musicstreamer/player.py:543-545 — adds tracker.bind_url adjacent to existing
# _last_buffer_percent reset (Phase 47.1 D-14 / Pitfall 3 mirror).
stream = self._streams_queue.pop(0)
self._current_stream = stream
self._last_buffer_percent = -1   # 47.1 D-14 — UNCHANGED
# Phase 62 / D-04: tracker arm-state reset uses the SAME lifecycle hook.
# Force-close any cycle that was open on the OUTGOING URL with outcome=failover (D-03).
prior_close = self._tracker.force_close("failover")
if prior_close is not None:
    self._underrun_cycle_closed.emit(prior_close)   # async log write on main
self._tracker.bind_url(
    station_id=self._current_station.id if self._current_station else 0,
    station_name=self._current_station_name,
    url=stream.url,
)
```

### Example 8: Pure unit test for `_BufferUnderrunTracker` (no Qt, no Player)

```python
# Source: tests/test_player_underrun_tracker.py — NEW
def test_unarmed_initial_fill_does_not_open_cycle():
    clock = iter([10.0, 11.0, 12.0])
    t = _BufferUnderrunTracker(clock=lambda: next(clock))
    t.bind_url(1, "Test", "http://x/")
    # Initial fill: percent climbs from 0 to 100 — must NOT open a cycle (D-04 unarmed gate)
    assert t.observe(0) is None
    assert t.observe(50) is None
    assert t.observe(100) is None    # arms here

def test_armed_drop_then_recover_returns_close_record():
    # Use a dict so we can step the clock deterministically.
    times = [10.0, 11.0, 11.5, 13.0]   # [arm, open, mid-cycle, close]
    it = iter(times)
    t = _BufferUnderrunTracker(clock=lambda: next(it))
    t.bind_url(7, "DI.fm Ambient", "http://prem2.di.fm/ambient")
    t.observe(100)                     # arms
    assert t.observe(80) == "OPENED"   # opens cycle at t=11.0
    assert t.observe(60) is None       # min_percent updates, no transition
    record = t.observe(100)            # closes at t=13.0
    assert record.outcome == "recovered"
    assert record.duration_ms == 2000
    assert record.min_percent == 60
    assert record.station_id == 7
    assert record.url == "http://prem2.di.fm/ambient"

def test_force_close_returns_record_with_outcome():
    t = _BufferUnderrunTracker(clock=iter([10.0, 11.0, 12.5]).__next__)
    t.bind_url(1, "Test", "http://x/")
    t.observe(100)
    t.observe(70)                       # opens
    record = t.force_close("pause")
    assert record.outcome == "pause"
    assert record.duration_ms == 1500
```

---

## Runtime State Inventory

> Phase 62 is greenfield instrumentation — no rename, no refactor of stored data. This section is included for completeness but every category is "None."

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by inspecting `musicstreamer/repo.py` schema; no `buffer_*` rows exist or are added by this phase | None |
| Live service config | None — no external services (Datadog, n8n, Tailscale) referenced by this codebase | None |
| OS-registered state | None — no Task Scheduler / launchd / systemd dependencies introduced; existing AUMID + .desktop already established by Phases 56 / 61 | None |
| Secrets / env vars | None — log lines deliberately exclude any credential-bearing field (no cookies, no auth tokens). url field is the playback URL which the user already entered themselves | None |
| Build artifacts | None — no `.egg-info`, no compiled binary, no installer registry interaction | None |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python `logging` | structured log lines | ✓ | stdlib | — |
| `time.monotonic()` | cooldown wall-clock | ✓ | stdlib (Python 3.3+) | — |
| PySide6 `QObject`/`QTimer`/`Signal` | dwell timer + queued Signals | ✓ | already pinned | — |
| PyGObject `Gst.Message.parse_buffering()` | reuse of existing parser | ✓ | already in use at `player.py:457` | — |
| pytest + pytest-qt | tests | ✓ | `>=9` / `>=4` (pyproject lines 28-29) | — |
| `monkeypatch` (pytest fixture) | inject fake clock into MainWindow time.monotonic | ✓ | bundled with pytest | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

This phase has zero new dependencies and zero environment risk.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=9 + pytest-qt >=4 (pyproject.toml lines 28-29) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (line 50) |
| Quick run command | `pytest tests/test_player_underrun_tracker.py tests/test_player_underrun.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUG-09 | Underrun event opens cycle on first `<100` while armed (D-01, D-04) | unit | `pytest tests/test_player_underrun_tracker.py::test_armed_drop_opens_cycle -x` | ❌ Wave 0 |
| BUG-09 | Initial fill (`<100` while unarmed) does NOT open cycle (D-04) | unit | `pytest tests/test_player_underrun_tracker.py::test_unarmed_initial_fill_does_not_open_cycle -x` | ❌ Wave 0 |
| BUG-09 | Arm flips on first `100` per URL (D-04) | unit | `pytest tests/test_player_underrun_tracker.py::test_first_100_arms_tracker -x` | ❌ Wave 0 |
| BUG-09 | Cycle close at `100` returns `_CycleClose(outcome='recovered')` with correct duration_ms + min_percent (D-02) | unit | `pytest tests/test_player_underrun_tracker.py::test_armed_drop_then_recover_returns_close_record -x` | ❌ Wave 0 |
| BUG-09 | Force-close on terminator returns record with outcome ∈ {failover, stop, pause, shutdown} (D-03) | unit | `pytest tests/test_player_underrun_tracker.py::test_force_close_returns_record_with_outcome -x` | ❌ Wave 0 |
| BUG-09 | Per-URL reset clears arm + open state (D-04 / Pitfall 3) | unit | `pytest tests/test_player_underrun_tracker.py::test_bind_url_resets_state -x` | ❌ Wave 0 |
| BUG-09 | `cause_hint` flips to 'network' if `note_error_in_cycle` fires during open cycle (D-02 Discretion) | unit | `pytest tests/test_player_underrun_tracker.py::test_cause_hint_network_after_error -x` | ❌ Wave 0 |
| BUG-09 | `_on_gst_buffering` emits `_underrun_cycle_opened` on transition (Pitfall 2 — queued Signal) | integration | `pytest tests/test_player_underrun.py::test_buffering_drop_emits_cycle_opened -x` | ❌ Wave 0 |
| BUG-09 | `_on_gst_buffering` emits `_underrun_cycle_closed` on natural recover with full record payload | integration | `pytest tests/test_player_underrun.py::test_buffering_recover_emits_cycle_closed -x` | ❌ Wave 0 |
| BUG-09 | `_try_next_stream` force-closes open cycle with outcome=failover before binding new URL | integration | `pytest tests/test_player_underrun.py::test_try_next_stream_force_closes_with_failover_outcome -x` | ❌ Wave 0 |
| BUG-09 | `pause()` force-closes open cycle with outcome=pause | integration | `pytest tests/test_player_underrun.py::test_pause_force_closes_with_pause_outcome -x` | ❌ Wave 0 |
| BUG-09 | `stop()` force-closes open cycle with outcome=stop | integration | `pytest tests/test_player_underrun.py::test_stop_force_closes_with_stop_outcome -x` | ❌ Wave 0 |
| BUG-09 | Cycle close path writes structured log line at INFO with all 9 fields | integration | `pytest tests/test_player_underrun.py::test_cycle_close_writes_structured_log -x` (uses `caplog`) | ❌ Wave 0 |
| BUG-09 | Dwell timer fires `underrun_recovery_started` after 1500ms (D-07) | integration | `pytest tests/test_player_underrun.py::test_dwell_timer_fires_after_threshold -x` (drives `_underrun_dwell_timer.timeout.emit()` synchronously, mirrors `test_elapsed_timer_emits_seconds_while_playing` at `tests/test_player.py:54`) | ❌ Wave 0 |
| BUG-09 | Sub-1500ms recovery cancels dwell timer; toast Signal NOT emitted | integration | `pytest tests/test_player_underrun.py::test_sub_dwell_recovery_silent -x` | ❌ Wave 0 |
| BUG-09 | MainWindow `_on_underrun_recovery_started` shows toast on first call (D-06) | integration | `pytest tests/test_main_window_underrun.py::test_first_call_shows_toast -x` | ❌ Wave 0 |
| BUG-09 | MainWindow cooldown suppresses 2nd toast within 10s (D-08, monkeypatched `time.monotonic`) | integration | `pytest tests/test_main_window_underrun.py::test_second_call_within_cooldown_suppressed -x` | ❌ Wave 0 |
| BUG-09 | MainWindow allows toast after cooldown elapses | integration | `pytest tests/test_main_window_underrun.py::test_toast_after_cooldown_allowed -x` | ❌ Wave 0 |
| BUG-09 | D-09 invariant: `BUFFER_DURATION_S == 10` and `BUFFER_SIZE_BYTES == 10MB` (existing test at `test_player_buffer.py:30-35`) | unit | `pytest tests/test_player_buffer.py::test_buffer_duration_constant tests/test_player_buffer.py::test_buffer_size_constant -x` | ✅ exists |

### Sampling Rate
- **Per task commit:** `pytest tests/test_player_underrun_tracker.py tests/test_player_underrun.py tests/test_main_window_underrun.py -x -q` (~1-2s — pure unit + mocked Player + qtbot)
- **Per wave merge:** `pytest -x -q` (full suite, ~current 76 test files baseline)
- **Phase gate:** Full suite green before `/gsd-verify-work`. UAT for SC #2 (toast appears under repro) is the human gate — see Open Question 2 about repro fixture.

### Wave 0 Gaps
- [ ] `tests/test_player_underrun_tracker.py` — pure unit tests on `_BufferUnderrunTracker` (~7 tests, no Qt fixture needed). Mirrors `tests/test_stream_ordering.py` shape (pure-logic test file).
- [ ] `tests/test_player_underrun.py` — Player-level integration: feed `_fake_buffering_msg` (mirrors `tests/test_player_buffering.py:21-27` helper), assert queued Signal emissions and log content. ~8 tests.
- [ ] `tests/test_main_window_underrun.py` — MainWindow cooldown gate using `time.monotonic` monkeypatch. ~3 tests. May land as new section in `tests/test_main_window.py` instead — planner decides based on file size at planning time.
- [ ] No framework install needed — pytest + pytest-qt already pinned.

### Test seam recommendation

**Use the existing `make_player(qtbot)` harness** at `tests/test_player_buffering.py:8-18`. It mocks the GStreamer pipeline factory and lets us feed `_fake_buffering_msg(percent)` objects directly to `_on_gst_buffering`. This gives us:

- No real GStreamer pipeline → no flaky network dep.
- Direct call into the bus handler → exercises Pitfall 1 path.
- `qtbot.waitSignal(player._underrun_cycle_opened, timeout=1000)` → asserts queued emission completes.
- `caplog` fixture for log assertions.

The `_BufferUnderrunTracker` itself is pure Python with no Qt — testable WITHOUT pytest-qt, just plain pytest. The injectable clock makes timing assertions deterministic.

---

## Stats-for-nerds counter (Discretion — recommendation)

CONTEXT.md Discretion floats an optional `_underrun_event_count: int` on `Player`, exposed via the Phase 47.1 `_build_stats_widget` `QFormLayout` as "Underruns: N".

**Recommendation: DEFER.**

**Rationale:**

- **Counter already exists in the log.** `grep -c "buffer_underrun " /var/log/musicstreamer.log` answers "how many cycles" instantly. The diagnostic value is zero new.
- **UI test churn cost.** `now_playing_panel.py:1377` `_build_stats_widget` returns the form; adding a row means: new `QLabel`, new `setText` slot, new `set_underrun_count` method, new test in `tests/test_now_playing_panel.py` covering visibility + initial state + update on Signal, plus a new `Player.underrun_count_changed = Signal(int)` and a wire-up in `MainWindow.__init__`. Per CONTEXT.md Discretion, this is exactly the "churn to UI tests" we should avoid.
- **The toast IS the user-facing surface.** Stats-for-nerds is hidden by default (Phase 47.1 D-05). A counter behind a hidden toggle for an event the user already saw via toast adds no signal.
- **Easy to add later.** Phase 47.1 D-09 explicitly designed `QFormLayout` to make future stats `form.addRow(...)` one-liners. If Phase 62 follow-up phase decides the count is genuinely useful (e.g., "show me how many underruns in this listening session"), the addition is cheap then.

**If the planner decides to ship it anyway:** the wiring is `Player._underrun_event_count: int = 0` incremented at every cycle close (alongside the log write); class-level `Signal` `underrun_count_changed = Signal(int)` emitted; `NowPlayingPanel.set_underrun_count(int)` slot adds a row to `_build_stats_widget`. Total: ~25 lines + 4 tests. Plan accordingly if you change the recommendation.

---

## Logging Integration

**Recommendation:** keep the `__main__.py:222` `basicConfig(level=logging.WARNING)` line UNCHANGED. Add ONE new line directly after it:

```python
# Source: musicstreamer/__main__.py:222 — extends with one new line
logging.basicConfig(level=logging.WARNING)
logging.getLogger("musicstreamer.player").setLevel(logging.INFO)   # Phase 62 / BUG-09 — surface buffer-underrun cycle close lines
```

**Why scoped (not global INFO):**
- Pitfall 5 (above) — global INFO turns on chatter from `gbs_api.py`, `aa_import.py`, `mpris2.py`, etc. that's been silenced for two years.
- Per-logger override is the stdlib idiom — clean, explicit, one-line.
- Other loggers (e.g., `musicstreamer.gbs_api`) keep their existing WARNING default. No regression.

**For tests:** use `caplog.set_level(logging.INFO, logger="musicstreamer.player")` or just `caplog.records` after `caplog.set_level(logging.INFO)`. pytest's `caplog` is the standard way to assert on log content.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Polling-based buffer monitoring (read pipeline state every N ms) | Event-driven `message::buffering` bus subscription | Phase 47.1 (2026-04-18) | Already in place; this phase reuses |
| Inline state machines flat on `Player` | Helper classes parented in same module (e.g., gbs_api parsers) | Phase 60 / 60.1 / 60.2 (2026-05-04) | Latest convention; Phase 62 adopts |
| `QTimer.singleShot(0, slot)` from worker threads | Queued `Signal` with `Qt.ConnectionType.QueuedConnection` | Phase 43.1 (2026-04-23) | Pitfall 2; mandatory |
| Hand-rolled `Signal()` lifetime via `Optional[Signal]` instance attrs | Class-level Signals on `QObject` subclass | Phase 35 (2026-04-11) — Pitfall 4 | Mandatory |

**Deprecated/outdated:**
- Setting `bus.add_signal_watch()` on the main thread → use `_bridge.run_sync(lambda: bus.add_signal_watch())` (Phase 43.1 fix `5827062`).
- `QTimer.singleShot(...)` from a non-`QThread` → use queued `Signal.emit()` (Phase 43.1 fix `f1333ed`).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `time.monotonic()` is the right cooldown clock for D-08's "wall-clock-based" requirement | Standard Stack / Pattern 4 | Low — alternatives (`time.time`, `QDateTime.currentMSecsSinceEpoch`) all work; `monotonic` is just the safest. CONTEXT.md says "wall-clock-based" but the user-intent is "real-time-debouncing across station changes" — `monotonic` satisfies that perfectly. If the user actually needs civil time (e.g. "show last underrun timestamp in 'HH:MM' to user"), that's a different ask not in scope. |
| A2 | Single key=value structured log line is more useful than JSON for diagnosis | Standard Stack / Code Examples §1 | Low — both formats convey the same info. If the planner / user prefer JSON, swap the format string with `json.dumps({...})`. The field set (D-02) is the locked part; format isn't. |
| A3 | Bumping per-logger level (not global) is the right scope adjustment to surface INFO from `musicstreamer.player` | Logging Integration | Low — stdlib-canonical; verified by reading Python `logging` Howto. Risk: forgot to set the level somewhere → surfaces as "INFO logs missing in stderr." Easy to detect manually. |
| A4 | The MainWindow cooldown bookkeeping should live on MainWindow, not Player | Pattern 4 | Low — moving it to Player is a one-method refactor if the planner disagrees. Player-side is also defensible (encapsulates "don't spam toast" behind the Signal). I recommend MainWindow because the toast IS a UI concern. |
| A5 | The `_underrun_event_count` stats-for-nerds row should be deferred | Stats-for-nerds counter | Low — pure UX call; the user/planner can override with a 25-line addition. |
| A6 | `parse_buffering_stats()` (which exposes `Gst.BufferingMode`) is NOT needed this phase | Open Questions §1 | Low-medium — see Open Question 1. The mode might be useful for cause attribution, but D-02 / Discretion explicitly defers cause-attribution beyond `unknown` / `network`. |

---

## Open Questions (RESOLVED)

1. **Should `cause_hint` ever be populated from `Gst.BufferingMode` (live / stream / download / timeshift)?**
   - What we know: `parse_buffering_stats()` returns `(mode, avg_in, avg_out, buffering_left)` `[CITED: lazka.github.io/pgi-docs Gst-1.0 Message]`. The mode could in principle distinguish "live stream" (low-latency, no DOWNLOAD mode) from "download-and-play" (cached). Most internet radio streams are live-streaming with `BUFFERING_STREAM` mode.
   - What's unclear: Whether the mode varies across the streams MusicStreamer plays (SHOUTcast/Icecast/HLS-via-yt-dlp/Twitch-HLS) in a way that's diagnostically useful.
   - **Status:** RESOLVED — **skip this phase**. CONTEXT.md Discretion says "Premature without observed root cause." Add `parse_buffering_stats()` only if the follow-up behavior-fix phase needs it. Reflected in plans: no `parse_buffering_stats()` call anywhere in Plans 01/02/03.

2. **Is a network-throttle repro fixture needed for Phase 62 verification, or only for the deferred behavior-fix phase?**
   - What we know: CONTEXT.md says "Test repro for criterion #3 ... is deferred to a follow-up phase." Criterion #3 is the BEHAVIOR FIX, not instrumentation. Criterion #1 (logging) and #2 (toast) are the only ones in scope here.
   - What's unclear: Whether SC #2 ("non-spammy visible indicator when buffering recovery is in progress") demands a live repro to demonstrate the toast actually appears under real-world stutter, or whether unit tests of the dwell-timer-fires-after-1500ms path are sufficient.
   - **Status:** RESOLVED — **Unit tests are sufficient for SC #2 verification.** The toast wiring is a Signal connection — if the unit test for "MainWindow shows toast on first call" passes and the integration test for "dwell timer fires after 1500ms" passes, then a real underrun > 1500ms WILL produce a toast. UAT can be human-driven on the dev box (`tc qdisc add dev wlan0 root netem delay 500ms loss 5%` if the user wants a forced repro), but that's UAT theatre, not test-suite scope. Reflected in plans: Plan 00 authors `test_dwell_timer_fires_after_threshold` and `test_first_call_shows_toast` as the SC #2 verification surface.

3. **Where exactly is the `closeEvent` shutdown hook (D-03 outcome=`shutdown`)?**
   - What we know: `MainWindow.closeEvent` at `main_window.py:352-358` exists and already calls `self._media_keys.shutdown()`. There's no `Player.shutdown()` method today.
   - What's unclear: Whether to add `Player.shutdown()` (mirroring `_media_keys.shutdown()`) or just call `self._player._tracker.force_close('shutdown')` directly from `closeEvent`. The latter pokes a private attribute; the former adds a public method.
   - **Status:** RESOLVED — **Add `Player.shutdown_underrun_tracker(self)` public method** (or just `Player.shutdown()` — small API expansion is fine). Call from `closeEvent` BEFORE `super().closeEvent(event)`. Keeps test surface clean (`player.shutdown_underrun_tracker()` is asserted, not `player._tracker.force_close('shutdown')`). Reflected in plans: Plan 02 Insertion Site 8 adds the public method; Plan 03 Insertion Site 6 wires it into `closeEvent` BEFORE `_media_keys.shutdown()`.

4. **Does the `cause_hint='network'` heuristic require the `_handle_gst_error_recovery` guard to ALSO call `tracker.note_error_in_cycle()`?**
   - What we know: `_on_gst_error` runs on bus-loop thread (`player.py:399-404`), emits `_error_recovery_requested` queued Signal. `_handle_gst_error_recovery` runs on main thread (`player.py:406-428`), calls `_try_next_stream` which fires the failover terminator force-close.
   - What's unclear: At which point should the cause_hint flip happen? Before `force_close('failover')` is called, the cycle would close as `outcome='failover' cause_hint='unknown'`. We want `cause_hint='network'` for these cases.
   - **Status:** RESOLVED — **call `self._tracker.note_error_in_cycle()` from `_on_gst_error` directly** (bus-loop thread is fine; tracker has no Qt). Sets the flag BEFORE the queued recovery hop reaches `_try_next_stream`. The `force_close('failover')` then reads `cause_hint='network'`. Reflected in plans: Plan 02 Insertion Site 9a adds the `note_error_in_cycle()` call inside `_on_gst_error` BEFORE `_error_recovery_requested.emit()`.

---

## Sources

### Primary (HIGH confidence)
- `musicstreamer/player.py` (1004 lines, full file read) — Player class structure, bus handlers, queued Signal precedents at lines 89-101 and 195-208, QTimer pattern at 148-180, per-URL reset at 545
- `musicstreamer/ui_qt/main_window.py` (lines 240-400 + grep) — show_toast at 344, signal-wiring patterns at 271-296, closeEvent at 352-358
- `musicstreamer/ui_qt/now_playing_panel.py` (lines 1370-1408) — `_build_stats_widget` `QFormLayout` extension point
- `musicstreamer/constants.py` (full read) — D-09 invariant constants verified at line 54-56
- `musicstreamer/__main__.py:222` — `logging.basicConfig` site verified
- `musicstreamer/models.py` (full read) — `Station.id`, `Station.name` field names verified for log format
- `tests/test_player_buffering.py` (82 lines, full read) — `make_player`, `_fake_buffering_msg` test seam pattern
- `tests/test_player_buffer.py` (52 lines, full read) — `_GST_SECOND` constant pattern, D-09 invariant tests already exist
- `tests/test_player_pause.py` (lines 1-90) — terminator-force-close test shape (`_pipeline.set_state.assert_called_with`)
- `tests/test_player.py` (lines 1-120) — synchronous QTimer drive pattern (`p._elapsed_timer.timeout.emit()` step-driver)
- `.claude/skills/spike-findings-musicstreamer/SKILL.md` (full read)
- `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` (full read) — Pitfalls 1, 2, 3 verified
- `.planning/phases/62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt/62-CONTEXT.md` (full read) — D-01..D-09 + Discretion verbatim above
- `.planning/milestones/v2.0-phases/47.1-stats-for-nerds-buffer-indicator/47.1-CONTEXT.md` (full read) — D-12 buffer_percent contract, D-14 sentinel reset

### Secondary (MEDIUM confidence)
- [Buffering — gst-docs/markdown/additional/design/buffering.md](https://github.com/GStreamer/gst-docs/blob/master/markdown/additional/design/buffering.md) — verified via WebFetch: BUFFERING is the underrun signal; low/high watermarks drive percent; `buffering-mode` field exists in message structure
- [GstMessage — GStreamer documentation](https://gstreamer.freedesktop.org/documentation/gstreamer/gstmessage.html) — verified via WebSearch: `parse_buffering()` percent semantics 0-100, "100 = complete"
- [Gst.Message PyGObject reference (lazka pgi-docs)](https://lazka.github.io/pgi-docs/Gst-1.0/classes/Message.html) — verified via WebFetch: `parse_buffering()` returns int via tuple convention; `parse_buffering_stats()` returns 4-tuple (mode, avg_in, avg_out, buffering_left)

### Tertiary (LOW confidence — needs validation)
- None this phase. Every recommendation traces to either (a) verified GStreamer/PyGObject docs, or (b) a code-line citation in this codebase, or (c) an explicit Pitfall in the project's own threading skill file.

---

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — every dep already pinned and exercised
- Architecture (cycle state machine, queued Signals, dwell timer): **HIGH** — every pattern has 2+ existing precedents in this codebase
- GStreamer BUFFERING semantics: **HIGH** — verified against gst-docs source repo + PyGObject API docs
- Logging integration: **HIGH** — stdlib canonical, 14 existing `_log = getLogger(__name__)` precedents
- Pitfalls: **HIGH** — Pitfalls 1/2/3 have fix commits in git history (`5827062`, `f1333ed`)
- `Gst.BufferingMode` for cause attribution: **MEDIUM** — exists in API but Discretion explicitly defers; treat as reserved capacity
- Cooldown idiom (`time.monotonic`): **MEDIUM** — stdlib-canonical, but project-first usage; risk is purely "we set a precedent that future phases might mimic"
- Stats-for-nerds counter recommendation: **MEDIUM** — judgment call on UI test churn vs. log-grep adequacy

**Research date:** 2026-05-07
**Valid until:** 2026-06-06 (30 days — GStreamer/PyGObject/PySide6 are stable; project conventions stable)
