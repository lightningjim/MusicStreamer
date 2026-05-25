---
phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt
plan: 02
subsystem: player-cycle-state-machine
tags: [phase-62, bug-09, gstreamer, qt-threading, tdd-green, cross-thread-signals]

# Dependency graph
requires:
  - phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt
    plan: 00
    provides: "8 RED Player integration tests in tests/test_player_underrun.py — Pitfall 1/2/3, D-02/D-03/D-07, T-62-01, T-62-02"
  - phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt
    plan: 01
    provides: "_BufferUnderrunTracker pure-logic class + _CycleClose dataclass + module-level _log logger in musicstreamer/player.py"
provides:
  - "Player class wired with cycle state machine: 3 Signals + dwell QTimer + tracker instance + _current_station_id + 4 main-thread slots + bus-handler extensions + terminator force-closes + shutdown_underrun_tracker public method"
  - "Structured INFO log line ('buffer_underrun ...') with all 9 fields and %r-quoted station_name + url (T-62-01 mitigation), at TWO sites: _on_underrun_cycle_closed and shutdown_underrun_tracker"
  - "Pitfall 2 contract: _underrun_cycle_opened / _underrun_cycle_closed connect with Qt.ConnectionType.QueuedConnection — bus-loop emits, main-thread slots own all Qt-affined work (QTimer.start/stop, _log.info)"
  - "T-62-02 ordering invariant: _try_next_stream calls tracker.force_close('failover') BEFORE tracker.bind_url(new_url); close record carries OLD url"
affects: [62-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bus-loop → main queued Signal pattern reused verbatim from Phase 43.1 / WIN-03 D-12 — same Qt.ConnectionType.QueuedConnection, same class-level Signal declaration, same bound-method connect"
    - "Per-URL state reset adjacent to existing 47.1 D-14 _last_buffer_percent=-1 reset — single load-bearing block at _try_next_stream re-bind site (Pitfall 3)"
    - "Synchronous log write on shutdown path (Pitfall 4) — bypasses queued Signal because closeEvent → QApplication.quit() may drain the queue before slots run; mirrors MediaKeysBackend.shutdown() instinct"

key-files:
  created: []
  modified:
    - "musicstreamer/player.py — +122 lines across 12 insertion sites: 1167 → 1289 lines"

key-decisions:
  - "Phase 62-02 / Single-task atomic landing: the cross-cutting cycle state machine (12 insertion sites) was deliberately landed in a single commit — splitting into 2a/2b would land a half-machine where, e.g., _on_gst_buffering observes percent transitions but no terminator force-closes them on pause/stop/failover, leaving integration-test failure modes harder to triage. The 8-test pytest gate is the integration safety net; 95/95 across the regression suite confirms the choice."
  - "Phase 62-02 / W2 symmetric station_id clear in play_stream: SC #1 (logged with cause attribution and timestamp — enough to diagnose intermittent reports) requires station_id and station_name to be CONSISTENT in the close-record log line. Original plan had station_id capture only in play(); play_stream() clears _current_station_name='' but kept _current_station_id stale from a prior play() call, which would emit station_name='' station_id=<stale-non-zero> on a manual-stream session underrun. Added the symmetric self._current_station_id = 0 clear (Insertion Site 5b)."
  - "Phase 62-02 / Both log sites mirror format string: _on_underrun_cycle_closed (queued slot) and shutdown_underrun_tracker (synchronous) use the IDENTICAL 9-field format string with station_name=%r url=%r. This is intentional duplication — refactoring to a private _format_underrun_log helper would be a project-first deviation (no precedent in player.py for log-format helpers); the 2 grep gate satisfies T-62-01 invariant."

requirements-completed: []  # BUG-09 closes after Plan 03 lands MainWindow + __main__.py wiring

# Metrics
duration: 4min
completed: 2026-05-08
---

# Phase 62 Plan 02: Wire _BufferUnderrunTracker into Player Summary

**Wave 1 GREEN Part 2 of 2: 12 insertion sites in `musicstreamer/player.py` (3 Signals + dwell QTimer + tracker instance + _current_station_id + 2 queued connects + play() station_id capture + play_stream() symmetric clear (W2) + pause()/stop() force-closes + _try_next_stream force_close-before-bind_url + _on_gst_error tracker hook + _on_gst_buffering observe-and-branch + 3 main-thread slots + shutdown_underrun_tracker public method) — all 8 RED integration tests in `tests/test_player_underrun.py` turned GREEN with zero regression in the 7-test tracker suite or the 80 pre-existing Player + MainWindow integration tests, T-62-01 and T-62-02 STRIDE mitigations live, D-09 invariant preserved**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-08T02:27:44Z
- **Completed:** 2026-05-08T02:31:52Z
- **Tasks:** 1 (intentionally monolithic — 12 insertion sites)
- **Files modified:** 1 (musicstreamer/player.py)

## Accomplishments

- All 8 integration tests in `tests/test_player_underrun.py` turn RED → GREEN in a single commit (verified by `pytest tests/test_player_underrun.py -x -q` exiting 0).
- Plan 01's 7 unit tests in `tests/test_player_underrun_tracker.py` still GREEN (no regression — Plan 02 is purely additive to Player; tracker class body untouched).
- 80 pre-existing tests across `tests/test_player_buffering.py`, `tests/test_player_buffer.py`, `tests/test_player.py`, `tests/test_player_pause.py`, and `tests/test_main_window_integration.py` still pass — combined regression suite is 95/95.
- T-62-01 STRIDE mitigation live: BOTH log sites (`_on_underrun_cycle_closed` queued slot AND `shutdown_underrun_tracker` synchronous path) use `station_name=%r url=%r` — `repr()` escapes embedded newlines / control characters / quotes so log-injection control sequences cannot mislead future log parsers. Test 6 (`test_cycle_close_writes_structured_log`) locks the single-quote canary `assert "station_name='Test Station'" in msg`.
- T-62-02 STRIDE ordering invariant live: `_try_next_stream` calls `self._tracker.force_close("failover")` BEFORE `self._tracker.bind_url(...)` — the close record carries the OLD URL, not the new URL's context. Test 3 (`test_try_next_stream_force_closes_with_failover_outcome`) locks the assertion `closed_records[0].url == "http://old.test/"`.
- D-09 invariant preserved: `git diff musicstreamer/constants.py | wc -l` returns 0 (`BUFFER_DURATION_S` and `BUFFER_SIZE_BYTES` untouched).
- W2 follow-through landed (symmetric `_current_station_id = 0` clear in `play_stream`) — closes the carry-forward Open Question 1 from Plan 01 about `station_id` end-to-end consistency in the structured log line.
- Pitfall 2 (qt-glib-bus-threading.md) honored at every cross-thread surface: `_underrun_cycle_opened.emit()` and `_underrun_cycle_closed.emit(record)` from `_on_gst_buffering` and `_try_next_stream` are queued; the actual Qt-affined work (`QTimer.start`/`stop`, `_log.info`) happens in main-thread slots.
- Pitfall 3 (per-URL reset) honored: `tracker.bind_url(...)` lives in the SAME block as `self._last_buffer_percent = -1` at the `_try_next_stream` re-bind site.
- Pitfall 4 (closeEvent shutdown) honored: `shutdown_underrun_tracker()` writes the log SYNCHRONOUSLY because queued slots may not run after `closeEvent` returns — same instinct as `MediaKeysBackend.shutdown()`.

## Task Commits

Each task was committed atomically (1 task, 1 commit per the plan's deliberate single-task choice):

1. **Task 1: 12 insertion sites — Signals + dwell QTimer + tracker instance + _current_station_id + queued connections + bus-handler extensions + force-closes + main-thread slots + shutdown method** — `02dc72a` (feat)

**Plan metadata:** _to be added on final docs commit_

## Files Created/Modified

- `musicstreamer/player.py` (modified, +122 lines: 1167 → 1289)
  - **Insertion 1** (3 Signals, +9 lines): `_underrun_cycle_opened`, `_underrun_cycle_closed = Signal(object)`, `underrun_recovery_started = Signal()` — placed after `_playbin_playing_state_reached`.
  - **Insertion 2** (dwell QTimer, +7 lines): `self._underrun_dwell_timer = QTimer(self); setSingleShot(True); setInterval(1500); timeout.connect(self._on_underrun_dwell_elapsed)` — placed after `_pause_volume_ramp_state` initialization.
  - **Insertion 3** (queued connects, +7 lines): two `Qt.ConnectionType.QueuedConnection` connects for `_underrun_cycle_opened` → `_on_underrun_cycle_opened` and `_underrun_cycle_closed` → `_on_underrun_cycle_closed` — placed after `_playbin_playing_state_reached.connect(...)`.
  - **Insertion 4** (tracker instance + `_current_station_id`, +6 lines): `self._tracker = _BufferUnderrunTracker()` and `self._current_station_id: int = 0` — placed after `self._last_buffer_percent: int = -1`.
  - **Insertion 5** (`play()` station_id capture, +1 line): `self._current_station_id = station.id` after `self._current_station_name = station.name`.
  - **Insertion 5b** (`play_stream()` symmetric clear / W2, +1 line): `self._current_station_id = 0` after `self._current_station_name = ""`.
  - **Insertion 6** (`pause()` force-close, +5 lines): `force_close("pause")` + emit + `_underrun_dwell_timer.stop()` before `_start_pause_volume_ramp()`.
  - **Insertion 7** (`stop()` force-close, +5 lines): `force_close("stop")` + emit + `_underrun_dwell_timer.stop()` before `_pipeline.set_state(Gst.State.NULL)`.
  - **Insertion 8** (`shutdown_underrun_tracker()` public method, +21 lines): synchronous log write on shutdown — Pitfall 4 mitigation; placed BEFORE `# Legacy callback shim` divider.
  - **Insertion 9a** (`_on_gst_error` tracker hook, +3 lines): `self._tracker.note_error_in_cycle()` BEFORE `self._error_recovery_requested.emit()`.
  - **Insertion 9b** (`_on_gst_buffering` observe + branch, +6 lines): `transition = self._tracker.observe(percent)` then emit `_underrun_cycle_opened` (OPENED) or `_underrun_cycle_closed` (record) — at end of method.
  - **Insertion 10** (`_try_next_stream` force-close + bind_url, +12 lines): `force_close("failover")` BEFORE `bind_url(...)` — T-62-02 ordering invariant.
  - **Insertion 11** (3 main-thread slots, +29 lines): `_on_underrun_cycle_opened` (`dwell_timer.start()`), `_on_underrun_cycle_closed(record)` (`stop()` + `_log.info(...)` 9-field structured), `_on_underrun_dwell_elapsed` (`underrun_recovery_started.emit()`) — placed after `_on_elapsed_tick` and BEFORE `# Failover queue` divider.

## Decisions Made

- **Single-task atomic landing.** The plan's `truths` block (W3 reviewer note) explicitly accepted this as the right call: the cycle state machine's 12 insertion sites are mutually load-bearing — bus-handler extensions need terminator force-closes for the tests to model real station-switch / pause / stop flows, and the 4 main-thread slots own all the Qt-affined state the queued Signals deliver. Splitting into 2a (Signals + tracker + bus extensions) and 2b (force-closes + slots + shutdown) would land a half-machine where 4 of the 8 tests would still fail at 2a, with the failure modes harder to read. The single 122-line commit is the cheapest atomic landing.
- **W2 symmetric station_id clear in `play_stream`.** Plan 01's Next Phase Readiness flagged `station_id` end-to-end consistency as an open seam. Plan 02 closed it: `play_stream()` already clears `_current_station_name = ""` to indicate "no station context, just a manual URL"; the matching `_current_station_id = 0` clear at the same site means the structured log line on a manual-stream session underrun emits `station_name='' station_id=0` instead of `station_name='' station_id=<stale-non-zero>`. Treating zero as the cleared sentinel mirrors the existing `_current_station_name = ""` convention exactly.
- **Both log sites mirror format string verbatim.** `_on_underrun_cycle_closed` (queued main-thread slot) and `shutdown_underrun_tracker` (synchronous closeEvent path) use the IDENTICAL 9-field format `"buffer_underrun start_ts=%.3f end_ts=%.3f duration_ms=%d min_percent=%d station_id=%d station_name=%r url=%r outcome=%s cause_hint=%s"`. Refactoring to a private helper would be a project-first deviation (no precedent in `player.py` for log-format helpers); the `grep -c "buffer_underrun "` gate at 2 is the structural invariant that catches drift.

## Deviations from Plan

### Auto-fixed Issues

None — the plan's `<action>` block prescribed verbatim insertion code for every site, and the test suite passed on first run after the 12 insertions completed. No Rule 1/2/3 surface arose during execution.

### Acceptance-Criterion Discrepancy (documented, not auto-fixed)

**1. [Documentation] `QueuedConnection` count exceeds the plan's `≥6` floor**
- **Found during:** Final acceptance-criteria gate.
- **Issue:** Plan acceptance criterion: `grep -c "Qt.ConnectionType.QueuedConnection" musicstreamer/player.py returns ≥6 (4 existing + 2 new for cycle-opened/closed)`. Actual count: 9.
- **Fix:** None applied. The plan undercounted the existing baseline — pre-Plan-02 there were 7 `QueuedConnection` sites (twitch_resolved, youtube_resolved, youtube_resolution_failed, _cancel_timers_requested, _error_recovery_requested, _try_next_stream_requested, _playbin_playing_state_reached) plus the 2 new (cycle_opened, cycle_closed) = 9 total. The `≥6` floor is satisfied.
- **Files modified:** None.
- **Impact:** None. The criterion is a sanity floor, not a hard equality gate.

**2. [Documentation] Plan's `<output>` block referenced "11 insertion sites" but acceptance criteria + truths consistently said 12**
- **Found during:** Reading the plan's bottom-of-file `<output>` block.
- **Issue:** Plan `<output>` says "All 11 insertion sites confirmed via grep gates". The plan's own `truths` lists 12 sites (including 5b for W2 / play_stream symmetric clear), and `<success_criteria>` says "12 insertion sites complete (3 Signals + 1 QTimer + 1 tracker + 1 station_id field + 2 queued connects + 1 play() capture + 1 play_stream() clear (W2) + 2 terminator force-closes (pause/stop) + 1 shutdown public method + 1 _on_gst_error tracker hook + 1 _on_gst_buffering tracker hook + 1 _try_next_stream force-close + 3 main-thread slots)" — that adds to 18 elements but 12 distinct insertion sites if you fold the 3 Signals into 1 site, the 2 queued connects into 1 site, and the 3 main-thread slots into 1 site. Counting by site (number of distinct edits to the file), the actual count is 12.
- **Fix:** None applied. Documenting here so the executor's commit message and SUMMARY.md consistently say "12 insertion sites". The `<output>` block's "11" is a stale remnant from the iteration before W2 (Insertion Site 5b for play_stream symmetric clear) was added.
- **Files modified:** None.
- **Impact:** None — the plan's `truths` and `<success_criteria>` are authoritative and both say 12.

---

**Total deviations:** 0 auto-fixed (Rule 1/2/3), 2 documented (acceptance-criterion floor undercount + stale `<output>` count)
**Impact on plan:** Zero impact on Phase 62 contract — 8/8 RED Player integration tests now GREEN, 7/7 tracker tests still GREEN, 80 pre-existing tests pass, T-62-01 and T-62-02 mitigations live, D-09 invariant preserved.

## Issues Encountered

None. The plan's `<action>` block was executable verbatim, the verification command ran clean on the first attempt, and the regression suite passed without any iteration.

## Threat Flags

None — no new I/O, no new network surface, no new file paths, no subprocess. The plan's `<threat_model>` correctly identified T-62-01 (log injection from library data) and T-62-02 (force-close-vs-bind ordering during station switch) as the only threats in scope, and both are mitigated and locked by Plan 00's Tests 3 and 6 (and they remain GREEN after this plan).

## Self-Check: PASSED

**Files verified to exist:**
- `musicstreamer/player.py` — FOUND (1289 lines, +122 net from Plan 01 baseline)

**Module attributes verified to exist:**
- `Player._underrun_cycle_opened` — FOUND (`Signal()`, queued)
- `Player._underrun_cycle_closed` — FOUND (`Signal(object)`, queued)
- `Player.underrun_recovery_started` — FOUND (`Signal()`, main → MainWindow)
- `Player._underrun_dwell_timer` — FOUND (after instantiation; `QTimer`, singleShot, 1500ms interval)
- `Player._tracker` — FOUND (after instantiation; `_BufferUnderrunTracker`)
- `Player._current_station_id` — FOUND (after instantiation; `int`)
- `Player.shutdown_underrun_tracker` — FOUND (callable)

**Commits verified to exist:**
- `02dc72a` — FOUND (Task 1: `feat(62-02): GREEN — wire _BufferUnderrunTracker into Player`)

**Verification gates passed:**
- 8/8 integration tests GREEN (`pytest tests/test_player_underrun.py -x -q`)
- 7/7 tracker tests still GREEN (`pytest tests/test_player_underrun_tracker.py -x -q`)
- 80 pre-existing tests still pass (`pytest tests/test_player_buffering.py tests/test_player_buffer.py tests/test_player.py tests/test_player_pause.py tests/test_main_window_integration.py -x -q`) — combined: 95/95
- All 21 acceptance-criterion grep gates pass (3 Signals × 1 each, QTimer + interval × 1, tracker + station_id, W2 play_stream symmetric clear, QueuedConnection ≥ 6 [actual 9], 4 force_close outcomes, 3 tracker method calls, 4 slot/method definitions, log format strings × 2)
- D-09 invariant: `git diff musicstreamer/constants.py | wc -l` returns 0 (constants.py 0-line diff)

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

**Ready for Plan 03 — Wave 2 GREEN: MainWindow + __main__.py wiring.** Plan 03 completes the BUG-09 deliverable by:

1. **Connect `Player.underrun_recovery_started` queued** in `MainWindow.__init__` adjacent to the existing `buffer_percent.connect(...)` and `cookies_cleared.connect(self.show_toast)` connections (around `main_window.py:274` per Plan 00 reading). Use `Qt.ConnectionType.QueuedConnection` to keep the policy uniform across all bus-derived Signals.
2. **Add `_on_underrun_recovery_started` slot with 10s cooldown gate (D-08).** Cooldown clock is wall-clock-based via `time.monotonic()`. State: `self._last_underrun_toast_ts: float | None = None`. On first call: emit `show_toast("Buffering…")` (U+2026 ellipsis per D-06) and stamp `_last_underrun_toast_ts = time.monotonic()`. On subsequent calls within 10000ms: silently skip. After 10s: allow next toast.
3. **Call `self._player.shutdown_underrun_tracker()` in `MainWindow.closeEvent` BEFORE the existing `self._media_keys.shutdown()` call (D-03 / Pitfall 4).** Synchronous log write — queued slots will not survive the `QApplication.quit()` that follows `closeEvent`.
4. **Add `import time` at the top of `main_window.py`** if not already imported (Plan 00's Test 1 issue note flagged this — `monkeypatch.setattr("musicstreamer.ui_qt.main_window.time.monotonic", ...)` requires the import to bind).
5. **Bump `musicstreamer.player` logger to INFO in `__main__.py`** alongside the existing `logging.basicConfig(level=logging.WARNING)` — `logging.getLogger("musicstreamer.player").setLevel(logging.INFO)`. Pitfall 5 (per Plan 00 Test 5): basicConfig stays at WARNING (don't bump global level — would surface other modules' chatter).

**Open carry-forward — verify before Plan 03:** The 5 RED MainWindow tests in `tests/test_main_window_underrun.py` are still RED. They will turn GREEN as Plan 03 lands. The 8 Plan 02 tests in `tests/test_player_underrun.py` are GREEN; the 7 Plan 01 tracker tests in `tests/test_player_underrun_tracker.py` are GREEN.

**Blockers/concerns:**
- None. The Player surface is now fully instrumented; Plan 03 is pure MainWindow + `__main__.py` work with no additional player.py edits planned.

---
*Phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt*
*Completed: 2026-05-08*
