---
phase: 68-add-feature-for-detecting-live-performance-streams-di-fm-and
reviewed: 2026-05-10T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - musicstreamer/aa_live.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/station_filter_proxy.py
  - musicstreamer/ui_qt/station_list_panel.py
  - tests/test_aa_live.py
  - tests/test_now_playing_panel.py
  - tests/test_main_window_integration.py
  - tests/test_station_filter_proxy.py
  - tests/test_station_list_panel.py
findings:
  blocker: 4
  warning: 7
  info: 4
  total: 15
status: issues_found
---

# Phase 68: Code Review Report

**Reviewed:** 2026-05-10
**Depth:** standard
**Files Reviewed:** 10 (5 source + 5 test)
**Status:** issues_found

## Summary

Phase 68 adds DI.fm live-performance-stream detection via the AudioAddict events
endpoint plus an ICY-prefix fallback. The architecture (pure-Python `aa_live`
module + `_AaLiveWorker(QThread)` polled by an adaptive timer + filter-proxy
"Live now" chip) is sound, the QA-05 lambda contract is honored on every Phase
68 connection, and the Pitfall 7 invalidate-only-when-active guard in the
proxy is correctly implemented and locked by tests.

However, several **correctness defects** survived implementation:

1. **`_parse_live_map` will raise on naive ISO-8601 strings** — `events_no_live`
   fixture happens to pin one of the few date forms `datetime.fromisoformat`
   tolerates, but real AA payloads with naive `Z`-suffixed timestamps will
   crash the parser silently into an empty dict on every poll cycle (BL-01).
2. **No `wait()` on the AA worker during shutdown** — `closeEvent` stops the
   QTimer but does not wait for an in-flight `_AaLiveWorker` to finish; on
   Linux this races with QObject destruction and produces "QThread: Destroyed
   while thread is still running" warnings or crashes (BL-02).
3. **`get_di_channel_key` will crash on `streams[0].url` when `streams[0]` has
   no `.url` attribute** — the `streams` guard checks list emptiness but not
   stream object shape (BL-03).
4. **`_check_and_start_aa_poll` silently re-arms the immediate-tick timer**
   even when poll is already active, defeating the cadence guard and causing
   double-poll on every dialog close (BL-04).

The Warning findings cover bind-time toast suppression edge cases, fan-out
ordering risk, the panel's unconditional `self.show()` during construction,
and a few defensive-guard issues. Info items are minor: dead code, duplicated
url-helpers imports, and a stale comment line reference.

## Blockers

### BL-01: `_parse_live_map` will raise (silently → empty dict) on AA's actual `Z`-suffixed UTC timestamps

**File:** `musicstreamer/aa_live.py:77-82`
**Issue:** `datetime.fromisoformat(start_raw)` is used to parse `start_at` /
`end_at` from the events payload. Prior to Python 3.11, `fromisoformat` does
**not** accept the trailing-`Z` ISO-8601 form (`"2026-05-10T11:00:00Z"`). The
AudioAddict events API has been observed to return naive `Z` suffixes — every
fixture in the test suite happens to use the explicit `+00:00` offset, which
masks the failure. Even on Python 3.11+, the broader `fromisoformat`
acceptance is restricted: `"2026-05-10T11:00:00.000Z"` plus a milliseconds
fraction was only added in 3.11.

The `except (ValueError, TypeError)` swallows the failure silently per the
A-04 contract — but the visible symptom is **"live_map is always empty"** for
the entire user base, with zero diagnostic surface. The "silent failure" path
becomes a "silent feature unavailability" path.

A second related defect: when `start` parses as naive (no offset) and `end`
parses as aware (offset present), the comparison `start <= now < end` raises
`TypeError: can't compare offset-naive and offset-aware datetimes`. The
`except (ValueError, TypeError)` covers this for the loop, but the result is
again silent feature unavailability.

**Fix:** Normalize timestamps before comparison. Use `datetime.fromisoformat`
with the `Z`→`+00:00` substitution that has been the canonical workaround
since the Python 3.7 era, and force aware UTC if a naive datetime slipped
through:

```python
def _parse_iso8601_utc(raw: str) -> Optional[datetime]:
    """Best-effort parse of an AA ISO-8601 timestamp into a UTC-aware datetime."""
    if not raw:
        return None
    # AA payloads have been observed with both '+00:00' and 'Z' suffixes.
    # datetime.fromisoformat only accepts 'Z' on Python 3.11+.
    s = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        # AA contract is UTC; treat naive as UTC rather than rejecting.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

# In _parse_live_map:
start = _parse_iso8601_utc(start_raw)
end = _parse_iso8601_utc(end_raw)
if start is None or end is None:
    continue
if start <= now < end:
    ...
```

Add a regression test fixture with a `Z`-suffixed timestamp:
```python
def test_parse_live_map_accepts_z_suffix():
    events = [{
        "id": 1,
        "start_at": "2026-05-10T11:00:00Z",
        "end_at": "2026-05-10T13:00:00Z",
        "show": {"name": "Z-suffix Show", "channels": [{"key": "house"}]},
    }]
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    assert _parse_live_map(events, now=now) == {"house": "Z-suffix Show"}
```

---

### BL-02: `closeEvent` does not `wait()` for the in-flight `_AaLiveWorker`, racing with QObject destruction

**File:** `musicstreamer/ui_qt/main_window.py:497-504`,
`musicstreamer/ui_qt/now_playing_panel.py:1515-1523`,
`musicstreamer/ui_qt/now_playing_panel.py:1525-1544`
**Issue:** `MainWindow.closeEvent` calls `self.now_playing.stop_aa_poll_loop()`,
which only stops the QTimer — the `_AaLiveWorker(QThread)` may still be inside
its `run()` invoking `urllib.request.urlopen(timeout=15)`. When Qt then tears
down the panel, the QThread instance is destroyed while the OS thread is
still executing inside the synchronous urllib call. Qt prints
`QThread: Destroyed while thread is still running` and on Linux can SIGABRT.

The 15-second `_REQUEST_TIMEOUT_S` makes this a 15-second window every time
the user closes the app during a poll. The "lazy stop" docstring claim
(`"Does not interrupt an in-flight worker — the worker's run() completes
naturally; its finished/error signal will fire and be ignored"`) is false:
the QThread C++ object is being destroyed, not "completing naturally."

The fix shape used elsewhere in the codebase for similar workers
(`_GbsPollWorker`, etc.) is a `wait()` with a bounded timeout in the close
path; Phase 68's worker omits this entirely.

**Fix:** Add a bounded `wait()` in `stop_aa_poll_loop` (or a dedicated
`shutdown_aa_poll` method) that the `closeEvent` path drives:

```python
def stop_aa_poll_loop(self) -> None:
    """..."""
    if self._aa_poll_timer is not None:
        self._aa_poll_timer.stop()
    # Phase 68: wait for any in-flight worker before returning so closeEvent
    # does not race with QObject destruction. _REQUEST_TIMEOUT_S is 15 s in
    # aa_live.py; cap our wait at that + 1 s slack.
    worker = self._aa_live_worker
    if worker is not None and worker.isRunning():
        worker.wait(16_000)
```

Add an integration test:
```python
def test_close_during_in_flight_poll_does_not_crash(qtbot, fake_player, fake_repo):
    fake_repo._settings["audioaddict_listen_key"] = "k"
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    # Force a slow worker to be in-flight
    ... (mock fetch_live_map to sleep 1 s)
    w.close()  # must not emit "QThread: Destroyed while thread is still running"
```

---

### BL-03: `get_di_channel_key` will crash if `streams[0]` lacks a `.url` attribute

**File:** `musicstreamer/aa_live.py:140-149`
**Issue:** The function checks `streams = getattr(station, "streams", None) or []`
and `if not streams: return None` — but then accesses `streams[0].url`
unconditionally. If `streams[0]` is a malformed object (e.g. a dict from a
test double, a `None` slot left by a partial DB row, or a future model change
that introduces an optional `.url`), the call raises `AttributeError`.

The function is called from `_AaLiveWorker.run()` indirectly (via
`_reschedule_aa_poll → get_di_channel_key(self._station)`) on the **main
thread**, but `_refresh_live_status` also calls `get_di_channel_key` from
inside a try/except that catches `Exception`. The proxy's
`filterAcceptsRow` (station_filter_proxy.py:130-141) calls the equivalent
chain via direct `_aa_channel_key_from_url` lookups — same shape, but inside
`_aa_channel_key_from_url`'s own try/except.

The crash will manifest in `_reschedule_aa_poll`
(now_playing_panel.py:1579-1582) which is **not** inside a try/except. A
single bad station (legacy DB row, third-party import, etc.) bound at the
moment of poll-tick reschedule will kill the timer chain.

**Fix:** Defensive `getattr` on the URL access:

```python
def get_di_channel_key(station) -> Optional[str]:
    streams = getattr(station, "streams", None) or []
    if not streams:
        return None
    url = getattr(streams[0], "url", None)
    if not url:
        return None
    if not _is_aa_url(url):
        return None
    ...
```

---

### BL-04: `_check_and_start_aa_poll` re-fires an immediate poll on every dialog close

**File:** `musicstreamer/ui_qt/main_window.py:453-475`,
`musicstreamer/ui_qt/now_playing_panel.py:1493-1513`
**Issue:** `_check_and_start_aa_poll` runs on **every** `AccountsDialog` and
`ImportDialog` close (via `_open_accounts_dialog` line 925 and
`_open_import_dialog` line 894). When the listen key was already saved at
construction time, the call path is:

```
_check_and_start_aa_poll
    has_key = True
    if not is_aa_poll_active(): ...   # currently True, so this branch is correctly skipped
    set_live_chip_visible(True)       # idempotent — fine
```

So far so good. **But** when `is_aa_poll_active()` is `False` because a
previous poll cycle's `_reschedule_aa_poll` has just rescheduled the timer
and the fired-but-not-rescheduled-yet window is hit (single-shot,
`isActive()` returns `False` between fire and reschedule), the call
re-executes `start_aa_poll_loop`, which calls `self._aa_poll_timer.start(0)`.
This **resets the existing timer** to fire immediately, effectively
truncating the adaptive cadence to "fire every time the user opens any
dialog." For users who frequently open AccountsDialog / ImportDialog (the
common path during stream curation), this means the AA endpoint is hit
multiple times per minute instead of once every 60 s / 5 min.

Additionally, in the `_AaLiveWorker.isRunning()` branch
(now_playing_panel.py:1533-1535), `_on_aa_poll_tick` calls
`_reschedule_aa_poll` immediately — but that schedules `60_000` or `300_000`
ms. If the in-flight worker finishes 100 ms later and `_on_aa_live_ready`
fires, that handler calls `_reschedule_aa_poll` **again**, racing the
already-scheduled timer. The second `start(60_000)` cancels the first per
QTimer semantics, so the cadence is effectively reset by every successful
poll completion — which is the intent — but the early reschedule in
`_on_aa_poll_tick` is then redundant. Worse: if `_on_aa_live_ready` arrives
**before** the first `_reschedule_aa_poll` runs (queued-connection ordering
is not strictly guaranteed against same-thread direct calls), you can get
two pending rescheduled fires.

**Fix:** Add an `is_aa_poll_active()` short-circuit at the top of
`start_aa_poll_loop` instead of relying on `not isActive()` (which is True
during the brief inter-tick window):

```python
def start_aa_poll_loop(self) -> None:
    if not bool(self._repo.get_setting("audioaddict_listen_key", "")):
        return
    if self._aa_poll_timer is not None:
        # Already constructed — only restart if truly stopped (not just
        # mid-tick between single-shot fires).
        return
    self._aa_poll_timer = QTimer(self)
    self._aa_poll_timer.setSingleShot(True)
    self._aa_poll_timer.timeout.connect(self._on_aa_poll_tick)
    self._aa_poll_timer.start(0)
```

Track an explicit `_aa_poll_running: bool` if the inter-fire window matters.
Also remove the redundant `_reschedule_aa_poll` call in the
already-running branch of `_on_aa_poll_tick` — the natural reschedule from
`_on_aa_live_ready` / `_on_aa_live_error` is sufficient and keeps cadence
ownership in one place.

## Warnings

### WR-01: `_first_bind_check` is cleared in `_refresh_live_status` even when no transition fires — masking second-bind T-01a

**File:** `musicstreamer/ui_qt/now_playing_panel.py:1471-1474`
**Issue:** The flag is unconditionally cleared at the bottom of the try
block. Consider this sequence:

1. User binds DI.fm "House" (not currently live). `_first_bind_check=True`,
   `is_live=False`, `was_live=False` → no toast, flag cleared.
2. Poll cycle returns `{"house": "Show A"}`. `is_live=True`, `was_live=False`,
   `_first_bind_check=False` → emits **T-01b** ("Live show starting") instead
   of **T-01a** ("Now live: ... on House").

This is incorrect per CONTEXT.md T-01a/b/c: T-01b is reserved for
"off → on mid-listen" — but this is the first time the user has seen the
live show on the bound station. The CONTEXT.md test
`test_off_to_on_transition_toast` (line 2874) relies on this exact path,
which is why the bug ships green.

There is room to argue this is the intended design — once the station is
bound and not-yet-live, every subsequent off→on is "mid-listen" by
definition. If so, this warning is a docstring/CONTEXT inconsistency rather
than a defect; either way the bind-flag semantics deserve one sentence of
clarification.

**Fix:** If T-01b is the desired toast for "bound, then went live during the
listening session," add a note to `_refresh_live_status`'s docstring saying
the bind-flag only suppresses **duplicate immediate re-evaluation** — once
the first cycle completes, every later transition is treated as mid-listen.
If T-01a is the desired toast in the bind→poll→live sequence, gate the
clear on `is_live`:

```python
if is_live:
    self._first_bind_check = False
self._live_show_active = is_live
```

---

### WR-02: T-01b emits "Live show starting" without the station name — toast goes to user with no station context

**File:** `musicstreamer/ui_qt/now_playing_panel.py:1459-1464`
**Issue:** Compare:

```python
# T-01a — bind to already-live
f"Now live: {show_name} on {station_name}"
# T-01c — on -> off
f"Live show ended on {station_name}"
# T-01b — off -> on mid-listen
f"Live show starting: {show_name}"   # ← no station_name
```

If the user is listening to "House" and DI.fm "Trance" goes live, the toast
"Live show starting: ..." would imply Trance is starting **on the bound
station**. That is in fact what happens here (`_refresh_live_status` only
fires for the bound station — see T-03 lock at
test_now_playing_panel.py:2914) — but the toast text is ambiguous if the
user has multiple AA windows / stations in mind. T-01a includes
"on {station}", T-01c includes "on {station}", T-01b drops it.

Minor UX consistency bug.

**Fix:**
```python
self.live_status_toast.emit(
    f"Live show starting on {station_name}: {show_name}"
    if show_name
    else f"Live show starting on {station_name}"
)
```

Update `test_off_to_on_transition_toast` to assert the station name is in
the toast.

---

### WR-03: `live_map_changed` fan-out emits the **same dict instance** — mutations downstream will corrupt panel cache

**File:** `musicstreamer/ui_qt/now_playing_panel.py:1553-1558`
**Issue:** `self._live_map = live_map if isinstance(live_map, dict) else {}`
stores the worker-emitted dict by reference, then `live_map_changed.emit(self._live_map)` forwards the same reference. `MainWindow._on_live_map_changed`
(main_window.py:442-451) forwards to `station_panel.update_live_map`, which
in turn calls `self._proxy.set_live_map(live_map)`. The proxy
(station_filter_proxy.py:68) takes `set(live_map.keys())` — read-only, OK
today. But any future consumer that **mutates** the dict (e.g. adds a
synthetic "always-live" entry for testing, normalizes keys to lowercase
in-place, etc.) will silently corrupt the panel's cache, breaking the next
`_refresh_live_status` against the bound station.

This is a "ticking timebomb" type defect: it works today and will break the
next time a contributor adds a write to the downstream consumer.

**Fix:** Defensive copy at the panel boundary:

```python
def _on_aa_live_ready(self, live_map: dict) -> None:
    self._live_map = dict(live_map) if isinstance(live_map, dict) else {}
    self._refresh_live_status()
    self.live_map_changed.emit(dict(self._live_map))   # immutable view
    self._reschedule_aa_poll()
```

---

### WR-04: `set_live_chip_visible(False)` while chip is currently checked toggles **without invalidating the proxy** — stuck filter remains via `_live_only=True`?

**File:** `musicstreamer/ui_qt/station_list_panel.py:574-587`
**Issue:** The docstring claims "If the chip is currently checked when
hidden, also turns it off so the proxy returns to showing all stations."
The implementation calls `self._live_chip.setChecked(False)`, which
**does** fire `toggled` → `_on_live_chip_toggled` →
`_proxy.set_live_only(False)`. So the chip's own toggled signal handles
the proxy update.

However, there's a subtle bug: `setChecked(False)` only fires `toggled` if
the new state differs from the current state. If `_live_chip.isChecked()`
returns True but the previous toggle never fully propagated (e.g.,
StateProperty drift on one of the unpolish/polish cycles), the
`isChecked() == False` shortcut would skip the proxy invalidate. This is
defensive territory, but the safer path is to **always** call
`set_live_only(False)` directly when hiding:

**Fix:**
```python
def set_live_chip_visible(self, visible: bool) -> None:
    self._live_chip.setVisible(visible)
    if not visible:
        # Defensive: forcibly turn off the live-only filter even if Qt's
        # toggled signal didn't fire (chipState drift, multiple-fire dedup, etc.).
        if self._live_chip.isChecked():
            self._live_chip.setChecked(False)
        self._proxy.set_live_only(False)   # belt-and-suspenders
```

---

### WR-05: `_AaLiveWorker.run()` has a broad `except Exception` wrapping `fetch_live_map` — but `fetch_live_map` already swallows everything

**File:** `musicstreamer/ui_qt/now_playing_panel.py:120-128`,
`musicstreamer/aa_live.py:107-121`
**Issue:** `fetch_live_map` has a `except Exception: return {}` at the
bottom, so the worker's `try/except Exception → emit error` path is dead
code: `_fetch(self._slug)` will always return a dict, never raise.

The worker's `error` signal is consequently never emitted in production —
`_on_aa_live_error` slot is dead. This is fine on the safety side but
misleading on intent: a reviewer reading the worker would assume errors
get an `error` signal path; they don't.

The defensive try/except is harmless, but the `error` signal and
`_on_aa_live_error` slot can be removed without behavior change, or
`fetch_live_map`'s belt-and-suspenders catch (lines 118-121) can be
removed and the worker's handler can become the truth.

**Fix:** Either delete the worker's try/except (and the `error` signal +
`_on_aa_live_error` slot) since `fetch_live_map` is already total, or
remove `fetch_live_map`'s `except Exception` so genuine bugs in the parser
(e.g. a future regression in `_parse_live_map`) actually surface as worker
errors. The latter is preferred — the silent catch in `fetch_live_map`
hides bugs from the worker which is meant to be the safety net.

---

### WR-06: `StationListPanel.__init__` calls `self.show()` unconditionally — side effect during construction

**File:** `musicstreamer/ui_qt/station_list_panel.py:338-344`
**Issue:** The comment justifies this as a workaround for
`_live_chip.isVisible()` returning False on unrealized widgets. But calling
`self.show()` from `__init__` means the panel becomes window-visible the
moment it is constructed — **before** the parent splitter is added to
`MainWindow` and **before** `setCentralWidget` is called. On X11 this is
visible as a momentary stray top-level window flashing on screen during
startup; on Wayland (the project's deployment target per MEMORY.md) the
behavior depends on the compositor.

The integration tests pass because `qtbot.addWidget` reparents the panel
under a hidden host. In production, `MainWindow` constructs
`StationListPanel(...parent=self._splitter)` (main_window.py:269), so the
panel has a parent at construction time — but `show()` on a parented
widget does still trigger a show event. The flash risk is small, but the
side effect from `__init__` is a code smell.

The actual bug being worked around (chip's `isVisible()` returning False
on unrealized widget) only matters in **tests** that assert on
`isVisible()`. In production, `MainWindow.show()` realizes the whole
hierarchy. Better to fix the test invariant than to add a side-effecting
`self.show()` in production code.

**Fix:** Replace `isVisible()` assertions in tests with `not isHidden()`
checks (the same pattern used in
test_now_playing_panel.py:2845/2858) and remove the `self.show()` call
from `__init__`. Or, if the realized-state check is structurally
necessary in tests, do it in the test fixture (`panel.show()` after
construction) rather than in production code.

---

### WR-07: `_on_aa_poll_tick` skip path leaves `_aa_live_worker` reference stale, defeating SYNC-05 retention

**File:** `musicstreamer/ui_qt/now_playing_panel.py:1525-1544`
**Issue:** When the previous worker is still running (`isRunning()` true),
the slot reschedules and returns **without nulling the worker reference**.
This is correct in isolation — the SYNC-05 retention slot is meant to keep
the running worker alive — but the very next `_on_aa_poll_tick` invocation
will check `isRunning()` again. If the worker finished between the two
ticks but `_on_aa_live_ready` hasn't run yet (queued connection latency),
`isRunning()` returns False → a **new worker** is constructed and the
**old finished/error signals** still emit into `_on_aa_live_ready` first,
followed by the new one. Both will write to `self._live_map` and both will
call `_reschedule_aa_poll`.

The "double-rescheduled" outcome is the same defect surface as BL-04.
The fix is the same: make rescheduling owned by exactly one path
(`_on_aa_live_ready` / `_on_aa_live_error` only) and remove the
short-circuit reschedule from `_on_aa_poll_tick`.

**Fix:** See BL-04 fix; this is the same root cause from a different angle.

## Info

### IN-01: Duplicate import of `_aa_channel_key_from_url` etc. in proxy

**File:** `musicstreamer/ui_qt/station_filter_proxy.py:127-131`
**Issue:** The lazy import inside `filterAcceptsRow` is justified by the
comment "matches the existing in-method import idiom used elsewhere in
the codebase to keep proxy module imports minimal and avoid any potential
circular-import risk via the panels." But the proxy module does not
import either panel, so the circular-import risk does not exist in
practice. The same imports already happen at module load time in
`aa_live.py` (line 23-27) and `now_playing_panel.py` (line 55-60). The
in-method import only adds a small per-row overhead during filtering.

**Fix:** Hoist to module-top imports. The "circular import" risk
referenced in the comment does not apply here.

---

### IN-02: `fetch_live_map`'s `except (json.JSONDecodeError, ValueError)` is partially redundant

**File:** `musicstreamer/aa_live.py:116`
**Issue:** `json.JSONDecodeError` is a subclass of `ValueError`, so
catching both is equivalent to catching `ValueError`. Harmless, but
indicates the author wasn't aware of the subclass relationship — worth a
docstring tweak or a code simplification.

**Fix:** `except ValueError:` (covers both).

---

### IN-03: Stale line-reference in comment

**File:** `musicstreamer/ui_qt/now_playing_panel.py:298-300`
**Issue:** The comment references "_gbs_poll_worker at line 425" — a
hard-coded line number that has already drifted (the actual `_gbs_poll_worker`
declaration is at line 518 today). This is exactly the IN-02 / "refer to
symbols, not line numbers" advice from Plan 06 cited later in the same
file. The comment is self-defeating.

**Fix:** Change to "mirrors `_gbs_poll_worker`'s SYNC-05 retention slot".

---

### IN-04: `tests/test_main_window_integration.py:1331` rebinds `w.show_toast` to a lambda — violates the same QA-05 spirit the test asserts

**File:** `tests/test_main_window_integration.py:1325-1333`
**Issue:** `test_live_status_toast_wired_to_show_toast` writes:

```python
w.show_toast = lambda t, d=3000: toasts.append(t) or original(t, d)
```

This is a test-only helper, not a Qt connection — so it doesn't violate
QA-05 directly. But the lambda's `or original(t, d)` idiom is fragile: if
`toasts.append(t)` ever returns truthy (it doesn't — `list.append` returns
`None`), `original(...)` would be skipped silently. Use a proper helper
function for clarity:

**Fix:**
```python
def fake_show_toast(t, d=3000):
    toasts.append(t)
    original(t, d)
w.show_toast = fake_show_toast
```

---

_Reviewed: 2026-05-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
