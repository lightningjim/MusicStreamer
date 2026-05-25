---
phase: 82-twitch-only-station-still-tries-to-play-youtube-stream-first
plan: "03"
subsystem: ui
tags: [phase-82, ui, persistence, preferred-stream, drift-guard, tdd]
dependency_graph:
  requires:
    - stations.preferred_stream_id column (Plan 82-01)
    - Repo.set_preferred_stream(station_id, stream_id) (Plan 82-01)
    - FakeRepo.set_preferred_stream no-op in test_stream_picker.py (Plan 82-01)
  provides:
    - _on_stream_selected calls self._repo.set_preferred_stream(station.id, stream.id) after play_stream
    - FakeRepo call-recorder in test_stream_picker.py for behavioral assertions
    - 4 behavioral tests pinning D-02 invariants + 1 drift-guard
  affects:
    - musicstreamer/ui_qt/now_playing_panel.py (_on_stream_selected write path)
    - tests/test_stream_picker.py (FakeRepo upgrade + 5 new tests)
tech_stack:
  added: []
  patterns:
    - FakeRepo call-recorder pattern (set_preferred_stream_calls list)
    - Non-comment source-grep drift-guard (Phase 51/55/61/63/81 precedent)
    - blockSignals invariant test (bind_station must not trigger persistence)
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py
    - tests/test_stream_picker.py
decisions:
  - "multi_stream_station fixture extended with streams=MULTI_STREAMS so behavioral tests can reference multi_stream_station.streams[N].id directly (fixture was streams=[] by default)"
  - "FakeRepo __init__ already existed; set_preferred_stream_calls field appended alongside existing _favorites field"
metrics:
  duration: "~4 min"
  completed: "2026-05-22T13:15:57Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 82 Plan 03: UI Persistence Hookup (_on_stream_selected) Summary

Inserts a two-line `self._repo.set_preferred_stream(self._station.id, s.id)` call into `now_playing_panel.py:_on_stream_selected` after `play_stream(s)`, upgrades the inline FakeRepo in `test_stream_picker.py` from a no-op to a call-recorder, and adds 4 behavioral tests + 1 drift-guard.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (feat) | Insert set_preferred_stream call into _on_stream_selected | ecf2a011 | musicstreamer/ui_qt/now_playing_panel.py |
| 2 (test) | Upgrade FakeRepo to call-recorder + add behavioral tests + drift-guard | 310405f | tests/test_stream_picker.py |

## Output Spec Confirmations

**Exact line range of the 2-line insertion in now_playing_panel.py:**
- Line 1289: `if self._station is not None:`
- Line 1290: `    self._repo.set_preferred_stream(self._station.id, s.id)`
  (Inserted after `self._player.play_stream(s)` at line 1288, before `break` at line 1291)

**FakeRepo upgrade:** `set_preferred_stream_calls: list = []` was appended to the existing `__init__` (alongside `_favorites`). No new `__init__` was required.

**test_now_playing_panel.py FakeRepo:** Confirmed unchanged — retains the Plan 82-01 no-op `set_preferred_stream` only. No Phase 82 behavioral tests were added to that file.

**Test count:** 4 behavioral tests + 1 drift-guard in `tests/test_stream_picker.py`:
1. `test_on_stream_selected_persists_preferred_stream_id` — picking stream[1] records exactly 1 call with correct args
2. `test_bind_station_does_not_persist_preferred_stream_id` — blockSignals invariant, bind_station records 0 calls
3. `test_on_stream_selected_with_invalid_index_does_not_persist` — early-return guard, index=-1 records 0 calls
4. `test_on_stream_selected_persists_even_when_reselecting_default` — D-02, 2 calls on pick+repick
5. `test_set_preferred_stream_drift_guard_now_playing_panel` — non-comment grep pins literal

**End-to-end repro closure (Lofi Girl, pick Twitch, press Play again):**
Combining Plans 82-01 + 82-02 + 82-03 fully closes the bug:
- Plan 82-01: `preferred_stream_id` column + `Repo.set_preferred_stream()` write path
- Plan 82-03 (this plan): `_on_stream_selected` writes the pick via `set_preferred_stream` each time the user changes the dropdown
- Plan 82-02: `Player.play(station)` reads `station.preferred_stream_id` and selects that stream instead of defaulting to position=1

## Deviations from Plan

**1. [Rule 2 - Enhancement] Extended multi_stream_station fixture with streams=MULTI_STREAMS**
- **Found during:** Task 2 implementation
- **Issue:** The plan's behavioral test code referenced `multi_stream_station.streams[1].id` but the original fixture created `Station` without a `streams` argument (defaulting to `[]`). Index access would raise IndexError.
- **Fix:** Added a re-declaration of `multi_stream_station` after `MULTI_STREAMS` is defined, setting `streams=MULTI_STREAMS`. The original declaration (before `MULTI_STREAMS`) is shadowed.
- **Files modified:** tests/test_stream_picker.py
- **Commit:** 310405f

## Verification Results

- `grep -v '^\s*#' now_playing_panel.py | grep -c set_preferred_stream` → **1** (drift-guard passes)
- `uv run pytest tests/test_stream_picker.py -k "preferred_stream or set_preferred_stream or persist" -q` → **5 passed** (all new tests)
- `uv run pytest tests/test_stream_picker.py -x -q` → **13 passed** (8 original + 5 new; FakeRepo upgrade did not break pre-existing tests)
- `uv run pytest tests/test_now_playing_panel.py -x -q` → **142 passed** (Plan 82-01 no-op shield still absorbs new call)
- D-07 invariant: no QIcon, QToolTip, QAction, or pin-icon additions in now_playing_panel.py diff

## Known Stubs

None — the persistence call is fully wired. `_on_stream_selected` writes on every valid stream pick.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. The `s.id` value is an integer sourced from DB-backed stream records (not user-typed text); `self._station.id` is the bound Station's integer PK. Both flow through parameterized SQL in `Repo.set_preferred_stream` (Plan 82-01). D-07 silent UX confirmed (no new visible attack surface).

## Self-Check: PASSED

- `musicstreamer/ui_qt/now_playing_panel.py`: `self._repo.set_preferred_stream(self._station.id, s.id)` present at line 1290 (1 occurrence)
- `musicstreamer/ui_qt/now_playing_panel.py`: `self._player.play_stream(s)` unchanged at line 1288 (1 occurrence, D-04 invariant)
- `tests/test_stream_picker.py`: `set_preferred_stream_calls` list field present in FakeRepo.__init__
- `tests/test_stream_picker.py`: `def set_preferred_stream` is a call-recorder (not no-op)
- `tests/test_stream_picker.py`: 5 new tests present (4 behavioral + 1 drift-guard)
- Commits ecf2a011 and 310405f verified in git log
