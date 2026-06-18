---
phase: 90-somafm-preroll-instrumentation
plan: "01"
subsystem: preroll-logging
tags: [logging, preroll, somafm, diagnostics]
dependency_graph:
  requires: []
  provides: [musicstreamer.preroll logger substrate, preroll_events_log_path(), install_preroll_events_handler()]
  affects: [musicstreamer/paths.py, musicstreamer/__main__.py]
tech_stack:
  added: []
  patterns: [RotatingFileHandler idempotent-install, named-logger isolation, Pitfall-5-propagate-parity, Pitfall-6-setLevel-INFO]
key_files:
  created:
    - musicstreamer/preroll_log.py
    - tests/test_preroll_events_log.py
  modified:
    - musicstreamer/paths.py
    - musicstreamer/__main__.py
    - tests/test_paths.py
decisions:
  - "log.setLevel(logging.INFO) added before addHandler to guard against NOTSET swallowing events (Pitfall 6)"
  - "propagate left at default True to preserve stderr parity (Pitfall 5)"
  - "install_preroll_events_handler() placed after install_buffer_events_handler() in __main__.py — both after run_migration() per Pitfall 1"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-18"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 3
requirements_satisfied: [SOMA-PRE-01]
---

# Phase 90 Plan 01: Preroll Event Logging Substrate Summary

**One-liner:** Size-rotated RotatingFileHandler on named logger `musicstreamer.preroll` writing `preroll-events.log`, wired at startup after migration, with full TDD mirror of the Phase 78 buffer_log pattern.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add preroll_events_log_path() and Wave 0 test mirror (RED) | 982a5b0b | musicstreamer/paths.py, tests/test_paths.py, tests/test_preroll_events_log.py |
| 2 | Create preroll_log.py and wire idempotent install in __main__.py (GREEN) | e1e70b9f | musicstreamer/preroll_log.py, musicstreamer/__main__.py |

## What Was Built

### `musicstreamer/preroll_log.py` (new)
Installs a `RotatingFileHandler(maxBytes=1_048_576, backupCount=3, encoding="utf-8")` on the `musicstreamer.preroll` named logger. Strict mirror of `buffer_log.py` with three substitutions: function name, path call, logger name. Added `log.setLevel(logging.INFO)` per Pitfall 6 (named loggers default to NOTSET). Idempotent via `baseFilename` comparison loop (Pitfall 7). `propagate` left at default `True` (Pitfall 5).

### `musicstreamer/paths.py` (extended)
Added `preroll_events_log_path()` immediately after `buffer_events_log_path()` (line 70), returning `os.path.join(_root(), "preroll-events.log")`. Docstring cites Phase 90 D-04. No change to `_root()` or `_root_override`.

### `musicstreamer/__main__.py` (extended)
Added import and call to `install_preroll_events_handler()` immediately after `install_buffer_events_handler()` (line 261), with a comment block mirroring the Phase 78 style. Both installs remain post-`migration.run_migration()` per Pitfall 1.

### `tests/test_preroll_events_log.py` (new)
5-test structural mirror of `tests/test_buffer_events_log.py` targeting `musicstreamer.preroll` / `preroll-events.log`: handler-attached, emit-writes-line, rotation-at-1MB, never-creates-backup-4, record-reaches-both-sinks. `_clean_preroll_handlers` autouse fixture snapshots and restores logger handlers/level.

### `tests/test_paths.py` (extended)
Added `test_preroll_events_log_path_returns_correct_path` and `test_preroll_events_log_path_respects_root_override` mirroring the buffer-log path test pair.

## Verification Results

```
19 passed, 1 warning in 0.25s
```
- `tests/test_preroll_events_log.py` — 5/5 GREEN
- `tests/test_paths.py -k preroll` — 2/2 GREEN
- All 14 existing path tests still pass (no regressions)

## Acceptance Criteria

- [x] `grep -q "def preroll_events_log_path" musicstreamer/paths.py` PASS
- [x] `.venv/bin/python -m pytest tests/test_paths.py -k preroll -q` — 2 PASS
- [x] `grep -q "musicstreamer.preroll" tests/test_preroll_events_log.py` PASS
- [x] `grep -q "log.setLevel(logging.INFO)" musicstreamer/preroll_log.py` PASS
- [x] `grep -c "propagate = False" musicstreamer/preroll_log.py` returns 0
- [x] `grep -c "install_preroll_events_handler" musicstreamer/__main__.py` returns 2
- [x] install_preroll_events_handler() call appears after run_migration() (line 270 vs 250)
- [x] `grep -c "requests" musicstreamer/preroll_log.py` returns 0 (no probe/network code)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — this is a pure substrate plan. No data is hardcoded or placeholder. The `preroll-events.log` file will be populated in Plans 02/03 when gate log calls are injected into `player.py`.

## SOMA-PRE-03 Deferral (Explicit)

SOMA-PRE-03 (30s network probe + preroll-probe.log) is deferred to conditional Phase 90b per D-01. No probe, no `requests` import, no network-listening harness was built in this plan. This is documented per plan objective.

## Threat Surface Scan

T-90-02 mitigated: `RotatingFileHandler(maxBytes=1_048_576, backupCount=3)` caps disk to ~4MB — identical to buffer_log.py. T-90-01 (Information Disclosure) accepted: diagnostic data only, no credentials/PII. No new threat surface introduced beyond what the plan's threat model documented.

## TDD Gate Compliance

- RED gate commit: `982a5b0b` — `test(90-01): add preroll_events_log_path() and Wave 0 test mirror (RED)`
- GREEN gate commit: `e1e70b9f` — `feat(90-01): create preroll_log.py and wire idempotent install in __main__.py`

Both TDD gate commits present and in correct order.

## Self-Check: PASSED

- [x] `musicstreamer/preroll_log.py` — EXISTS
- [x] `musicstreamer/paths.py` — preroll_events_log_path() function present
- [x] `musicstreamer/__main__.py` — install_preroll_events_handler wired
- [x] `tests/test_preroll_events_log.py` — 5 tests, all GREEN
- [x] `tests/test_paths.py` — 2 new preroll tests, all GREEN
- [x] Commit 982a5b0b — exists (Task 1 RED)
- [x] Commit e1e70b9f — exists (Task 2 GREEN)
