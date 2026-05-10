---
phase: 68
plan: 01
subsystem: tests
tags: [pyside6, qt-pytest, fixtures, no-network, red-contract, wave-0]
dependency_graph:
  requires: []
  provides:
    - RED test contract for musicstreamer.aa_live helpers
    - RED test contract for NowPlayingPanel Phase 68 surface
    - RED test contract for StationListPanel Phase 68 chip surface
    - RED test contract for StationFilterProxyModel Phase 68 live filter
    - RED test contract for MainWindow Phase 68 poll lifecycle
  affects:
    - tests/test_aa_live.py
    - tests/test_now_playing_panel.py
    - tests/test_station_list_panel.py
    - tests/test_station_filter_proxy.py
    - tests/test_main_window_integration.py
tech_stack:
  added: []
  patterns:
    - Wave 0 RED contract first (Phases 65, 67 precedent)
    - Fixture-driven pure unit tests (tests/fixtures/aa_live/*.json)
    - ImportError as collection-time RED state for entire test module
    - AttributeError as individual test RED state for panel/proxy/window tests
key_files:
  created:
    - tests/test_aa_live.py
    - tests/fixtures/aa_live/events_no_live.json
    - tests/fixtures/aa_live/events_with_live.json
    - tests/fixtures/aa_live/events_multiple_live.json
    - tests/fixtures/aa_live/events_aliased_channel.json
  modified:
    - tests/test_now_playing_panel.py
    - tests/test_station_list_panel.py
    - tests/test_station_filter_proxy.py
    - tests/test_main_window_integration.py
decisions:
  - Wave 0 RED contract follows Phase 65/67 precedent: all tests written before production code
  - Four JSON fixtures created with fixed UTC timestamps to avoid brittle time-sensitive test arithmetic
  - events_with_live.json includes two-channel show to test multi-channel one-show mapping
  - FakeRepo variant _FakeRepoWithSettings added to test_station_list_panel.py Phase 68 section for get_setting support (existing FakeRepo doesn't have this method)
  - test_parse_live_map_event_in_window asserts both 'house' and 'lounge' keys since the fixture's live event has two channels
metrics:
  duration_minutes: 6
  completed_date: "2026-05-10"
  tasks_completed: 3
  tasks_total: 3
  files_created: 5
  files_modified: 4
---

# Phase 68 Plan 01: Wave 0 RED Contract for Live Stream Detection Summary

## One-Liner

Full RED test corpus for DI.fm live-show detection: 21 pure-helper tests (ImportError) + 30 widget/proxy/integration tests (AttributeError) across 5 test files with 4 realistic JSON event fixtures.

## What Was Done

This plan created the complete Wave 0 RED contract for Phase 68. All new tests fail immediately because the production code (Plans 02-05) does not exist yet. This is intentional — the tests are executable specifications that Plans 02-05 must turn GREEN.

### Task 1: tests/test_aa_live.py + 4 JSON fixtures

Created `tests/test_aa_live.py` with 21 pure-helper tests covering:
- ICY pattern detection (P-01/P-02/P-03): 7 tests for `detect_live_from_icy`
- Events parser (A-02): 6 tests for `_parse_live_map` using pinned UTC timestamps
- HTTP layer (A-04): 3 tests for `fetch_live_map` error handling via `unittest.mock.patch`
- Channel key derivation (A-06): 5 tests for `get_di_channel_key`

The `from musicstreamer.aa_live import ...` import line produces a `ModuleNotFoundError` at collection time, creating a single collection-time failure that covers all 21 tests simultaneously.

Four JSON fixtures in `tests/fixtures/aa_live/`:
- `events_no_live.json`: 3 events all starting 2026-06-01+, well beyond test pinned dates
- `events_with_live.json`: 1 live event (2026-05-10 11:00-13:00 UTC) with 2 channels + 1 future event
- `events_multiple_live.json`: 3 concurrent live events on trance/progressive/house channels
- `events_aliased_channel.json`: 1 live event with channel key `classictechno` (alias round-trip test)

### Task 2: Extend test_now_playing_panel.py + test_station_list_panel.py

Appended `# === Phase 68: Live Stream Detection (DI.fm) ===` sections to both files.

`test_now_playing_panel.py` — 14 new tests:
- Badge existence/visibility (U-01/U-04/C-01/C-03)
- Toast transitions (T-01a/b/c)
- Pitfall 5 duplicate toast prevention
- T-03 no-toast-for-non-bound-channel
- Ordering guard (C-01/Pitfall 4: `_refresh_live_status` before `_refresh_gbs_visibility`)
- C-02 title-change hook
- Poll loop lifecycle (B-03/N-01)

`test_station_list_panel.py` — 3 new tests (with a local `_FakeRepoWithSettings` class since the file's existing `FakeRepo` lacks `get_setting`):
- F-01/F-07 chip hidden without key
- F-07/N-03 chip visible with key
- N-03 reactive `set_live_chip_visible()` toggle

### Task 3: Extend test_station_filter_proxy.py + test_main_window_integration.py

`test_station_filter_proxy.py` — 7 new tests:
- F-02 `set_live_only` filter functionality
- F-03 AND-composition with provider chip
- F-04 empty tree when chip on but no live channels
- Pitfall 7 no-invalidate when chip off
- `has_active_filter` extension
- `clear_all` extension

`test_main_window_integration.py` — 6 new tests:
- B-03 poll loop starts/skips in `__init__`
- B-04 `_check_and_start_aa_poll` post-dialog hook
- T-01/QA-05 `live_status_toast` wired to `show_toast`
- QA-05 structural no-lambda assertion
- B-03 closeEvent stops poll

## Deviations from Plan

### Auto-applied: FakeRepo variant for StationListPanel tests

**Found during:** Task 2

**Issue:** The existing `FakeRepo` in `test_station_list_panel.py` does not implement `get_setting()`. Plan 03's `StationListPanel` will call `repo.get_setting("audioaddict_listen_key", "")` during construction for chip visibility. The Phase 68 tests need a repo with this method.

**Fix:** Added `_FakeRepoWithSettings` class within the Phase 68 section of `test_station_list_panel.py`. This is a superset of the existing `FakeRepo` plus `get_setting`/`set_setting` support. The existing `FakeRepo` and all existing tests are unchanged.

**Files modified:** `tests/test_station_list_panel.py` (Phase 68 section only)

**Commit:** d443726

### Minor: test_parse_live_map_event_in_window asserts both house and lounge

**Found during:** Task 1 fixture design

**Issue:** The plan specified the test should assert `_parse_live_map(events, now=now) == {"house": "Deeper Shades of House"}`. However, the `events_with_live.json` fixture (required for `test_parse_live_map_multi_channel_one_show`) includes a second channel `"lounge"` on the same show. This means the correct assertion is `{"house": "...", "lounge": "..."}`.

**Fix:** The test asserts the dict with both keys, which is the correct contract for the parser. The `multi_channel_one_show` test separately asserts the multi-channel behavior.

**Impact:** None on the RED state; Plan 02 implementation must match this contract.

## Regression Verification

| Test | Result |
|------|--------|
| `test_sibling_label_visible_for_aa_station_with_siblings` (Phase 64) | PASSED |
| `test_multi_select_and_between_or_within` (Phase 38) | PASSED |

## Stub Tracking

None. This plan creates test files only — no production code, no data flow, no UI rendering.

## Threat Flags

None. No production code modified.

## Self-Check: PASSED

### Created files exist:
- tests/test_aa_live.py: FOUND
- tests/fixtures/aa_live/events_no_live.json: FOUND
- tests/fixtures/aa_live/events_with_live.json: FOUND
- tests/fixtures/aa_live/events_multiple_live.json: FOUND
- tests/fixtures/aa_live/events_aliased_channel.json: FOUND

### Commits exist:
- 59b8a6b: tests(68-01): RED contract for aa_live helpers + 4 fixtures
- d443726: tests(68-01): RED contract for NowPlayingPanel + StationListPanel Phase 68 surface
- 0e9421e: tests(68-01): RED contract for StationFilterProxy + MainWindow Phase 68 wiring
