---
phase: 90-somafm-preroll-instrumentation
plan: "02"
subsystem: preroll-logging
tags: [logging, preroll, somafm, diagnostics, instrumentation, auto-staleness]
dependency_graph:
  requires: [90-01 (musicstreamer.preroll logger substrate)]
  provides: [preroll event log calls at gate + handoff, D-08 auto-staleness branch, _PREROLL_STALE_THRESHOLD_S]
  affects: [musicstreamer/player.py, tests/test_player.py]
tech_stack:
  added: []
  patterns: [additive-log-injection, D-08-staleness-threshold, Pattern-4-thread-local-Repo, TDD-RED-GREEN]
key_files:
  created: []
  modified:
    - musicstreamer/player.py
    - tests/test_player.py
decisions:
  - "preroll_skipped_throttle probe added as a SEPARATE read-only if-block BEFORE the combined gate (no restructuring of existing gate condition per D-10)"
  - "D-08 auto-staleness branch placed inside the else (fetched-empty) branch — mutually exclusive with D-13 unfetched branch by structural position"
  - "_PREROLL_STALE_THRESHOLD_S = 7 * 24 * 3600 (RESEARCH A1: SomaFM catalog weekly cadence; 7 days self-heals within one cycle without API hammering)"
  - "No set_property calls added anywhere; buffer-duration -> uri ordering (D-11) unaffected"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-18"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 2
requirements_satisfied: [SOMA-PRE-01, SOMA-PRE-04, SOMA-PRE-05, SOMA-PRE-06]
---

# Phase 90 Plan 02: Preroll Gate Instrumentation + D-08 Auto-Staleness Summary

**One-liner:** Additive logging at 5 SomaFM preroll decision points (`preroll_start`, `preroll_skipped_throttle`, `preroll_skipped_empty` x2, `preroll_handoff_complete`) plus the D-08 staleness re-fetch branch that closes the "fetched-with-0 never re-fetches" trap — zero behavior change, all 17 Phase 84 D-11 buffer-ordering tests GREEN.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Add failing log-emission and staleness tests | 34af876f | tests/test_player.py (+7 tests) |
| 1+2 GREEN | Inject preroll event log calls + D-08 auto-staleness branch | e13383e1 | musicstreamer/player.py (+55 lines) |

## What Was Built

### `musicstreamer/player.py` (extended — additive only)

**Module-level constant (D-08):**
```python
_PREROLL_STALE_THRESHOLD_S: int = 7 * 24 * 3600  # Phase 90 D-08
```
Added after `_log = logging.getLogger(__name__)`. RESEARCH A1 rationale cited in comment.

**`_try_next_stream` preroll gate — 4 log calls injected:**

1. `preroll_skipped_throttle`: a **separate read-only if-block** before the combined gate (per 90-PATTERNS.md §Pattern 1). Fires only when throttle is active. No state mutation, does NOT restructure the existing gate condition (D-10 compliance).

2. `preroll_start`: added between `preroll_url = random.choice(urls)` (D-06 — unchanged) and `self._start_preroll(preroll_url)`. Logs the chosen URL verbatim.

3. `preroll_skipped_empty reason=unfetched`: added inside the `elif prerolls_fetched_at is None` branch before the `threading.Thread` call.

4. `preroll_skipped_empty reason=fetched_empty` + **D-08 auto-staleness sub-condition**: the implicit comment-only `else` branch was made explicit with `else:` and given both the log call and the staleness sub-condition. Mutual exclusivity with D-13 (unfetched branch) is structural: the else branch can only execute when `prerolls_fetched_at is not None`.

**`_on_preroll_about_to_finish` — 1 log call injected:**

5. `preroll_handoff_complete`: added after `self._preroll_in_flight = False` and before the `if not self._streams_queue:` check (per 90-PATTERNS.md §Pattern handoff). Logs `_current_station_name` / `_current_station_id`.

**Zero behavior change guarantee:**
- No `set_property` call added anywhere.
- The `buffer-duration` → `uri` ordering in `_on_preroll_about_to_finish` (Phase 84 D-11, lines ~1640+) is entirely downstream of the new log call — unaffected.
- `random.choice(urls)` selection expression unchanged (D-06).

### `tests/test_player.py` (extended — TDD)

Added 7 new tests at the bottom of the file:

**Phase 90 log-emission tests (SOMA-PRE-01):**
- `test_preroll_log_start_event_includes_url_and_station` — asserts `preroll_start` emitted with `station_name=`, `station_id=`, `url=` matching one of the preroll URLs (D-06).
- `test_preroll_log_skipped_throttle_event` — asserts `preroll_skipped_throttle` emitted with `station_name=`, `station_id=`, `remaining_s=` when throttle window active.
- `test_preroll_log_skipped_empty_fetched` — asserts `preroll_skipped_empty reason=fetched_empty` emitted when `prerolls_fetched_at` set but `prerolls==[]`.
- `test_preroll_log_handoff_complete_event` — asserts `preroll_handoff_complete` emitted in `_on_preroll_about_to_finish` with `station_name=` and `station_id=`.

**Phase 90 D-08 staleness tests (SOMA-PRE-04):**
- `test_auto_staleness_refetch_triggers_for_old_empty_station` — verifies daemon Thread started with `_preroll_backfill_worker` target and station added to `_backfill_in_flight` when age > threshold.
- `test_auto_staleness_no_refetch_when_prerolls_exist` — verifies staleness branch does NOT fire when station has prerolls (plays preroll instead).
- `test_auto_staleness_no_refetch_when_recently_fetched` — verifies no re-fetch when age <= threshold.

**Helper infrastructure added:**
- `_ListHandler(_logging.Handler)` — in-memory log capture for test assertions.
- `_capture_preroll_log()` context manager — attaches `_ListHandler` to `musicstreamer.preroll`, sets level INFO, cleans up on exit.

## Verification Results

```
47 passed, 29 deselected, 1 warning in 0.77s
```

- `tests/test_player_buffer_growth.py` — 17/17 GREEN (SOMA-PRE-05 Phase 84 D-11 buffer-ordering regression gate)
- `tests/test_player.py -k "preroll or throttle or drift_guard"` — 30/30 GREEN
- `tests/test_player.py -k "staleness"` — 3/3 GREEN
- `tests/test_player.py -k "preroll_log"` — 4/4 GREEN

## Acceptance Criteria

- [x] `grep -c "preroll_start\|preroll_skipped_throttle\|preroll_skipped_empty\|preroll_handoff_complete" musicstreamer/player.py` returns 5 (>= 4)
- [x] `grep -q "random.choice(urls)" musicstreamer/player.py` PASS (D-06 unchanged)
- [x] `grep -q "preroll_start.*url=" musicstreamer/player.py` PASS
- [x] `grep -q "_PREROLL_STALE_THRESHOLD_S" musicstreamer/player.py` PASS — value `7 * 24 * 3600`
- [x] `getattr(station, "prerolls_fetched_at", None) is not None` check present in D-08 branch (mutual exclusivity with D-13)
- [x] `.venv/bin/python -m pytest tests/test_player_buffer_growth.py -q` exits 0 (17 GREEN, SOMA-PRE-05)
- [x] `.venv/bin/python -m pytest tests/test_player.py -k staleness -q` exits 0 (3 GREEN)
- [x] `.venv/bin/python -m pytest tests/test_player.py -k "preroll or drift_guard" -q` exits 0 (28 GREEN)
- [x] No `set_property` call in any added code block (D-11 ordering guard)

## Deviations from Plan

None — plan executed exactly as written. The `else:` clause was made explicit (from an implicit comment-only branch) as required by the plan to support both the `fetched_empty` log and the D-08 staleness sub-condition.

## Known Stubs

None. All 5 log event names are wired to real decision points. The `preroll_error` event (reserved per plan) is intentionally not wired — documented as a future extension.

## SOMA-PRE-03 Deferral (Explicit)

SOMA-PRE-03 (30s network probe + preroll-probe.log) is deferred to conditional Phase 90b. No probe, no `requests` import was added.

## Threat Surface Scan

- T-90-03 (URL tampering via re-fetch): mitigated — D-08 staleness branch calls `_preroll_backfill_worker` which calls `repo.insert_preroll`, which has Phase 83 T-83-01 URL-scheme gate rejecting non-HTTP(S) URLs. No bypass.
- T-90-04 (DoS via repeated re-fetch): mitigated — `_backfill_in_flight` single-flight + 7-day threshold gate; worker discards id in finally.
- T-90-05 (SQLite write from daemon thread): mitigated — D-08 branch reuses existing `_preroll_backfill_worker` which follows Pattern 4 (thread-local `db_connect()` inside worker, `con.close()` in finally).
- No new threat surface introduced beyond the plan's threat model.

## TDD Gate Compliance

- RED gate commit: `34af876f` — `test(90-02): add failing RED tests for preroll log events and D-08 auto-staleness`
- GREEN gate commit: `e13383e1` — `feat(90-02): inject preroll event log calls + D-08 auto-staleness re-fetch branch`

Both TDD gate commits present and in correct order. All 7 RED tests confirmed failing before GREEN commit.

## Self-Check: PASSED

- [x] `musicstreamer/player.py` — 5 event names wired (preroll_start, preroll_skipped_throttle, preroll_skipped_empty x2, preroll_handoff_complete)
- [x] `musicstreamer/player.py` — `_PREROLL_STALE_THRESHOLD_S = 7 * 24 * 3600` present at line 88
- [x] `musicstreamer/player.py` — D-08 staleness branch with `is not None` guard present
- [x] `tests/test_player.py` — 7 new tests (4 log-emission + 3 staleness)
- [x] Commit 34af876f — exists (RED gate)
- [x] Commit e13383e1 — exists (GREEN gate)
- [x] tests/test_player_buffer_growth.py — 17 passed (SOMA-PRE-05 regression gate)
