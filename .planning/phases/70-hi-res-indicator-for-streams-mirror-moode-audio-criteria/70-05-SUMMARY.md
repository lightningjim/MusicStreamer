---
phase: 70
plan: "05"
subsystem: main-window
tags: [main-window, signal-fanout, repo-write, threading, tdd-green]
dependency_graph:
  requires: [70-01, 70-02, 70-04]
  provides: [MainWindow.quality_map_changed, MainWindow._on_audio_caps_detected]
  affects: [now_playing_panel, station_list_panel]
tech_stack:
  added: []
  patterns:
    - "Phase 70 / DS-01 / Pitfall 9 Option A: MainWindow owns the queued slot (Player has no repo handle)"
    - "Phase 50 D-04 / Pitfall 4: DB-write-before-UI-refresh strict ordering"
    - "Phase 68 live_map_changed Signal(object) pattern replicated for quality_map_changed"
    - "hasattr-guarded fan-out for forward compat with Wave 3 plans 70-06 / 70-09"
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/main_window.py
    - tests/test_main_window_integration.py
decisions:
  - "Signal(object) instead of Signal(dict): PySide6 silently fails to copy-convert Python dict via typed Signal; Signal(object) is the established pattern from Phase 68 live_map_changed (Rule 1 auto-fix)"
  - "_on_audio_caps_detected uses repo.con.execute for lightweight station_id lookup to avoid iterating all stations just to find the owning station_id (T-70-13 parameterized SELECT)"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-12"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 2
---

# Phase 70 Plan 05: MainWindow audio_caps_detected fan-out Summary

MainWindow gains the `_on_audio_caps_detected` slot that persists GStreamer-detected sample_rate_hz / bit_depth to the DB and fans out a quality_map refresh to NowPlayingPanel and StationListPanel, honoring the Phase 50 D-04 DB-write-before-UI-refresh invariant.

## What Was Built

`MainWindow` grows by ~90 lines covering one new Signal, one new slot, one new instance field, two new wiring lines in `__init__`, and a `best_tier_for_station` import. The FakePlayer test double gains `audio_caps_detected = Signal(int, int, int)`. Eight new Phase 70 tests land in `test_main_window_integration.py`.

### Key additions to `musicstreamer/ui_qt/main_window.py`

- `quality_map_changed = Signal(object)` declared at class scope adjacent to existing class-level attributes. (Note: `Signal(object)` not `Signal(dict)` — see Deviations.)
- `self._last_quality_payload: dict[int, tuple[int, int]] = {}` initialized in `__init__` for idempotency deduplication.
- `self._player.audio_caps_detected.connect(self._on_audio_caps_detected, Qt.ConnectionType.QueuedConnection)` wired in `__init__` adjacent to the Phase 68 `live_map_changed` wiring block.
- `_on_audio_caps_detected(self, stream_id, rate_hz, bit_depth)` slot with strict 6-step ordering:
  1. Idempotency check (cache lookup)
  2. DB write FIRST: parameterized `SELECT station_id FROM station_streams WHERE id=?` → fetch full row → `repo.update_stream(... sample_rate_hz=rate_hz, bit_depth=bit_depth)`
  3. Update `_last_quality_payload` cache
  4. Rebuild `quality_map = {st.id: best_tier_for_station(st) for st in repo.list_stations()}`
  5. `hasattr`-guarded fan-out to `now_playing._refresh_quality_badge()` and `station_panel.update_quality_map(quality_map)`
  6. `self.quality_map_changed.emit(quality_map)` — non-blocking, last

### Security (threat model coverage)

- T-70-13: `SELECT station_id FROM station_streams WHERE id=?` — parameterized, no interpolation.
- T-70-14: Stream deleted between caps-emit and slot-fire — explicit `None` check on both lookups; clean no-op with no cache update.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Signal(dict) silently fails in PySide6 — changed to Signal(object)**
- **Found during:** Task 1 (test execution)
- **Issue:** PySide6 emits `_pythonToCppCopy: Cannot copy-convert ... (dict) to C++` when a `Signal(dict)` is emitted with a Python dict; the signal fires but connected slots receive an empty dict or the emission silently drops. The plan spec said `Signal(dict)` but Phase 68's `live_map_changed = Signal(object)` is the correct PySide6 pattern.
- **Fix:** Changed `quality_map_changed = Signal(dict)` to `quality_map_changed = Signal(object)` with a comment explaining the rationale.
- **Files modified:** `musicstreamer/ui_qt/main_window.py`
- **Commit:** 7db1366

## Test Results

- **197 tests** pass across `test_hi_res.py`, `test_repo.py`, `test_stream_ordering.py`, `test_main_window_integration.py`
- **8 new Phase 70 tests** added to `test_main_window_integration.py`:
  - `test_quality_map_changed_signal_exists_on_class` — class-scope Signal presence
  - `test_audio_caps_detected_connect_wired` — `audio_caps_detected.connect` + `QueuedConnection` in `__init__`
  - `test_on_audio_caps_detected_db_write_before_fanout` — lexical ordering invariant via `inspect.getsourcelines`
  - `test_on_audio_caps_detected_writes_db_and_emits_quality_map` — end-to-end DB write + quality_map emission
  - `test_on_audio_caps_detected_idempotent` — second emit with same args is no-op
  - `test_on_audio_caps_detected_stream_deleted_race` — T-70-14 deleted-stream race
  - `test_on_audio_caps_detected_fanout_guarded_pre_70_06` — hasattr guard pre-Plan 70-06
  - `test_last_quality_payload_initialized_in_init` — cache initialized as empty dict

## Known Stubs

None — the slot is fully functional. `_refresh_quality_badge` and `update_quality_map` fan-out calls are `hasattr`-guarded because they land in Wave 3 Plans 70-06 and 70-09 respectively; the slot is correct and complete today, just waiting for those methods to be defined.

## Threat Flags

No new unplanned threat surface introduced. All DB writes go through `repo.update_stream` (parameterized SQL per Plan 70-02). The `repo.con.execute` SELECT for station_id lookup uses a parameterized query binding `stream_id` as int.

## Self-Check
