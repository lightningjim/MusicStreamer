---
phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame
plan: 01
subsystem: audio-playback
tags: [failover, ordering, pure-function, dataclass, tdd]

requires:
  - phase: 39-core-dialogs
    provides: StationStream dataclass baseline (fields url/label/quality/position/stream_type/codec)
provides:
  - "StationStream.bitrate_kbps: int = 0 field on the dataclass (D-01)"
  - "musicstreamer/stream_ordering.py pure module with codec_rank + order_streams (D-08, D-09)"
  - "tests/test_stream_ordering.py with 18 test cases covering PB-03..PB-11"
affects: [47-02-repo-player, 47-03-ui-imports-settings]

tech-stack:
  added: []
  patterns:
    - "Pure-function ordering module (no DB/UI coupling, parallels url_helpers.py)"
    - "Purity guard via sorted() + partition comprehension (never list.sort in-place)"
    - "RED/GREEN TDD cycle with atomic test/feat commits"

key-files:
  created:
    - musicstreamer/stream_ordering.py
    - tests/test_stream_ordering.py
  modified:
    - musicstreamer/models.py

key-decisions:
  - "Unknown bitrates (bitrate_kbps <= 0) partition LAST, sort among themselves by position asc (D-07)"
  - "codec_rank normalizes via (codec or '').strip().upper() for None-safety + whitespace tolerance"
  - "Dataclass field placed AFTER codec to preserve positional compat with existing call sites"

patterns-established:
  - "Pure ordering module: top-level musicstreamer/X.py, zero Qt/GStreamer/DB imports, sorted() only"
  - "Table-driven pytest.mark.parametrize for codec_rank rank matrix"
  - "Dedicated purity guard test: list(streams) copy before call, equality check after"

requirements-completed: []

duration: 2m
completed: 2026-04-18
---

# Phase 47 Plan 01: Stream Ordering Foundation Summary

**Pure failover ordering module (`stream_ordering.py`) with `codec_rank` + `order_streams`, plus `StationStream.bitrate_kbps: int = 0` field — zero coupling to DB, Qt, or GStreamer, 18 tests green.**

## Performance

- **Duration:** 2m 20s
- **Started:** 2026-04-18T16:33:24Z
- **Completed:** 2026-04-18T16:35:44Z
- **Tasks:** 2
- **Files modified:** 1 (models.py)
- **Files created:** 2 (stream_ordering.py, tests/test_stream_ordering.py)

## Accomplishments

- `StationStream.bitrate_kbps: int = 0` added after `codec` field — backward-compatible at every existing call site
- `codec_rank(codec) -> int` implements FLAC=3 > AAC=2 > MP3=1 > other=0 (case-insensitive, whitespace-tolerant, None-safe)
- `order_streams(streams) -> list[StationStream]` sorts by `(codec_rank desc, bitrate_kbps desc, position asc)` and partitions unknown bitrates to the end in position order
- Purity guard enforced: partition + `sorted()` only, no `list.sort()`; `test_does_not_mutate_input` confirms input list is untouched
- 18 test cases pass (10 parametrized `codec_rank` cases + 8 `order_streams` scenarios covering PB-03..PB-09 and PB-11)
- Wave-1 foundation is ready; plans 47-02 and 47-03 can import `order_streams` and construct `StationStream(bitrate_kbps=...)` immediately

## Task Commits

Each task was committed atomically:

1. **Task 1: Add bitrate_kbps to StationStream dataclass** — `598214c` (feat)
2. **Task 2 RED: Failing tests for stream_ordering** — `0db752c` (test)
3. **Task 2 GREEN: Implement stream_ordering module** — `4a4fa19` (feat)

_TDD cycle: RED (0db752c) → GREEN (4a4fa19). No REFACTOR commit — implementation was minimal and idiomatic at GREEN._

## Files Created/Modified

- `musicstreamer/models.py` — Added `bitrate_kbps: int = 0` field to `StationStream` dataclass (line 21)
- `musicstreamer/stream_ordering.py` — New pure module exporting `codec_rank` and `order_streams`; 42 lines, zero Qt/GStreamer/DB/sqlite imports
- `tests/test_stream_ordering.py` — 87 lines, 9 test functions, one `pytest.mark.parametrize` matrix over `codec_rank`

## Decisions Made

- **Purity over speed:** used partition comprehension + two `sorted()` calls rather than a single `sorted()` with a tuple key that encodes unknown-last. Slightly more code, zero risk of a key-math sign flip biting us later.
- **None-safe codec_rank:** `(codec or "").strip().upper()` handles `None`, empty string, and stray whitespace in one expression.
- **Dataclass field placement:** appended after `codec` to keep existing positional `StationStream(...)` constructions compatible with the plan's D-01 direction.

## Deviations from Plan

None — plan executed exactly as written. RED phase produced the expected `ModuleNotFoundError`; GREEN phase produced 18 passing tests on first run; no refactor was necessary.

## Issues Encountered

- **Pre-existing test environment issues** surfaced during the Task 1 full-suite verification: 25 pre-existing failures (not caused by this plan). Confirmed via `git stash` revert that failures reproduce without our edits. Logged in `deferred-items.md`:
  - `yt_dlp` module not installed (affects 6 test modules at collection)
  - `pytest-qt`'s `qtbot.mouseClick` hits `AttributeError: 'NoneType' object has no attribute 'QTest'` (affects ~15 Qt widget tests)
  
  Both are environmental (not code bugs), out of scope for this plan. The 18 tests added by this plan are pure-Python with no Qt or `yt_dlp` dependency and pass cleanly.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **47-02 (repo + player)** can now:
  - Import `order_streams` from `musicstreamer.stream_ordering`
  - Persist `bitrate_kbps` through repo `insert_stream` / `update_stream` / `list_streams` hydration
  - Swap `sorted(station.streams, key=lambda s: s.position)` in player.py:166 for `order_streams(station.streams)`
- **47-03 (UI + imports + settings)** can now:
  - Construct `StationStream(bitrate_kbps=X)` in AA/RadioBrowser import paths
  - Add the Bitrate column to `edit_station_dialog.py::streams_table`
  - Extend `settings_export.py` 7→8 column round-trip

No blockers.

## Self-Check: PASSED

- `musicstreamer/stream_ordering.py` — FOUND
- `tests/test_stream_ordering.py` — FOUND
- `musicstreamer/models.py` line 21 `bitrate_kbps: int = 0` — FOUND
- Commit `598214c` — FOUND (feat: add bitrate_kbps field)
- Commit `0db752c` — FOUND (test: RED)
- Commit `4a4fa19` — FOUND (feat: GREEN)
- 18 tests pass (`pytest tests/test_stream_ordering.py`)
- Purity guard grep (`.sort(` in module) — 0 matches
- Coupling guard grep (Qt/GStreamer/sqlite/repo imports in module) — 0 matches

---

*Phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame*
*Completed: 2026-04-18*
