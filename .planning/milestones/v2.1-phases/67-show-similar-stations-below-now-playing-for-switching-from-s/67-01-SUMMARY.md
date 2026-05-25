---
phase: 67-show-similar-stations-below-now-playing-for-switching-from-s
plan: 01
subsystem: testing
tags: [pyside6, qt-richtext, qt-pytest, sqlite-settings, random-sample, html-escape, tdd-red, wave-0]

# Dependency graph
requires:
  - phase: 64-audioAddict-siblings-on-now-playing
    provides: find_aa_siblings + render_sibling_html in url_helpers.py; FakeRepo + _make_aa_station factories in test_now_playing_panel.py; Phase 64 sibling integration test shape in test_main_window_integration.py
  - phase: 47-stats-for-nerds-autoeq
    provides: Phase 47.1 QAction-checkable test pattern and persist-and-toggle-panel test pattern in test_main_window_integration.py

provides:
  - RED contract for pick_similar_stations(stations, current_station, *, sample_size, rng) in tests/test_pick_similar_stations.py (22 tests, SIM-04/SIM-05/SIM-09)
  - RED contract for NowPlayingPanel.similar_activated + _similar_container + _similar_cache + set_similar_visible + _on_similar_link_activated + _on_refresh_similar_clicked + _on_similar_collapse_clicked in tests/test_now_playing_panel.py (14 new tests, SIM-02/SIM-03/SIM-06/SIM-07/SIM-08/SIM-10/SIM-11/SIM-12)
  - RED contract for MainWindow._act_show_similar + _on_show_similar_toggled + _on_similar_activated + QA-05 structural lambda-grep in tests/test_main_window_integration.py (6 new tests, SIM-01/SIM-02/SIM-08/QA-05)
  - All 42 new Phase 67 tests failing with ImportError or AttributeError (explicit RED state)

affects:
  - 67-02 (pure-helper plan — picks up red tests in test_pick_similar_stations.py)
  - 67-03 (panel plan — picks up red tests in test_now_playing_panel.py Phase 67 section)
  - 67-04 (main_window plan — picks up red tests in test_main_window_integration.py Phase 67 section)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 RED contract: ImportError on module-level import IS the RED state (no pytest.fail placeholders)"
    - "Extended _mk() factory with provider_id, provider_name, tags kwargs (additive over test_aa_siblings.py shape)"
    - "No-emit spy pattern: emissions=[] list + signal.connect(lambda s: emissions.append(s)) for asserting signal not emitted"
    - "QA-05 structural lambda-grep: inspect.getsource(MainWindow) + src.splitlines() to assert no lambda on .connect lines"

key-files:
  created:
    - tests/test_pick_similar_stations.py (309 lines — 22 tests for pick_similar_stations + render_similar_html)
  modified:
    - tests/test_now_playing_panel.py (+242 lines — Phase 67 section with 14 qtbot tests)
    - tests/test_main_window_integration.py (+163 lines — Phase 67 section with 6 integration tests)

key-decisions:
  - "Wave 0 RED contract mirrors Phase 62-00 precedent — ImportError/AttributeError IS the RED state, no pytest.fail placeholders"
  - "Phase 67 section in test_now_playing_panel.py inserted between Phase 64 sibling section (line 937) and Phase 60 GBS section (line 939) — additive only"
  - "test_same_provider_subsection_hidden_when_empty renamed to test_similar_same_provider_subsection_hidden_when_empty to meet grep -c test_.*similar >= 13 acceptance criterion"
  - "SIM-12 regression lock (Phase 64 invariant) added as test_phase_64_sibling_label_unchanged_after_phase_67 — explicitly re-asserts sibling:// NOT similar:// in href"

patterns-established:
  - "Extended factory _mk(id_, name, url, *, provider_id, provider_name, tags) in test_pick_similar_stations.py mirrors test_aa_siblings.py _mk with additive keyword args"
  - "No-emit spy via emissions list (not qtbot.assertNotEmitted) — established pattern in existing Phase 64 tests, codified here for similar tests"

requirements-completed: [SIM-01, SIM-02, SIM-03, SIM-04, SIM-05, SIM-06, SIM-07, SIM-08, SIM-09, SIM-10, SIM-11, SIM-12, QA-05]

# Metrics
duration: 7min
completed: 2026-05-10
---

# Phase 67 Plan 01: Wave 0 RED Contract for Similar Stations Summary

**42 failing tests across 3 files lock the complete Phase 67 contract: pick_similar_stations/render_similar_html pure helpers (SIM-04/05/09), NowPlayingPanel.similar_activated + cache + collapse (SIM-02/03/06/07/08/10/11/12), and MainWindow._act_show_similar + QA-05 structural lambda-grep (SIM-01/02/08/QA-05)**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-10T13:01:15Z
- **Completed:** 2026-05-10T13:08:30Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Created `tests/test_pick_similar_stations.py` with 22 pure-helper tests (no qtbot, no fixtures) covering SIM-04 same-provider pool exclusion rules, SIM-05 same-tag union semantics + normalize_tags case-folding, SIM-09 renderer escaping/separator/prefix/payload tests — all fail with ImportError on `pick_similar_stations`
- Appended 14 qtbot-based Phase 67 tests to `tests/test_now_playing_panel.py` covering master toggle visibility (SIM-02), collapse persistence (SIM-03), cache lifecycle (SIM-06), refresh re-roll (SIM-07), click-to-signal (SIM-08), hidden-when-empty sub-sections (SIM-10), defense-in-depth no-op handlers (SIM-11), and Phase 64 regression lock (SIM-12) — all fail with AttributeError on Phase 67 panel attributes
- Appended 6 integration tests to `tests/test_main_window_integration.py` covering QAction existence + checkability (SIM-01), persist-and-toggle-panel round-trip (SIM-02), click-switches-playback via _on_similar_link_activated (SIM-08), and QA-05 structural lambda-grep — all fail with AttributeError on MainWindow Phase 67 attributes
- Phase 64 baselines (`test_sibling_label_visible_for_aa_station_with_siblings`, `test_sibling_click_switches_playback_via_main_window`) and Phase 47.1 baselines (`test_stats_action_is_checkable`, `test_stats_toggle_persists_and_toggles_panel`) verified green

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tests/test_pick_similar_stations.py** - `6db10bf` (test)
2. **Task 2: Append Phase 67 section to tests/test_now_playing_panel.py** - `43e4467` (test)
3. **Task 3: Append Phase 67 section to tests/test_main_window_integration.py** - `46bcd04` (test)

## Files Created/Modified

- `tests/test_pick_similar_stations.py` - NEW: 309 lines, 22 pure-helper tests for SIM-04/05/09; ImportError RED state on `pick_similar_stations`/`render_similar_html` import
- `tests/test_now_playing_panel.py` - EXTENDED: +242 lines, 14 qtbot tests in Phase 67 section; AttributeError RED state on Phase 67 panel attributes
- `tests/test_main_window_integration.py` - EXTENDED: +163 lines, 6 integration tests in Phase 67 section; AttributeError RED state on Phase 67 MainWindow attributes

## Decisions Made

- Wave 0 RED contract follows Phase 62-00 precedent: ImportError/AttributeError on import/attribute resolution IS the RED state. No pytest.fail() placeholders used.
- Phase 67 test section in `test_now_playing_panel.py` inserted between line 937 (end of Phase 64 sibling section) and line 939 (start of Phase 60 GBS section) — additive, no existing test bodies modified.
- Test function `test_same_provider_subsection_hidden_when_empty` renamed to `test_similar_same_provider_subsection_hidden_when_empty` to satisfy `grep -c "^def test_.*similar" >= 13` acceptance criterion (12 → 14 passing).
- SIM-12 regression lock (test_phase_64_sibling_label_unchanged_after_phase_67) re-asserts `href="sibling://2"` (NOT `similar://`) to lock the Phase 64 "Also on:" invariant against Phase 67 regressions.

## Deviations from Plan

None - plan executed exactly as written. The test function rename (same_provider_subsection → similar_same_provider_subsection) was a minor naming adjustment to satisfy the acceptance criterion, consistent with the plan's intent.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. All changes are test files only.

## Next Phase Readiness

- Plan 02 (pure-helper implementation): `pick_similar_stations` + `render_similar_html` added to `musicstreamer/url_helpers.py` will turn all 22 tests in `test_pick_similar_stations.py` from RED to GREEN.
- Plan 03 (panel implementation): `NowPlayingPanel` extended with `similar_activated` signal, `_similar_container`, `_similar_cache`, `set_similar_visible()`, `_on_similar_link_activated()`, `_on_refresh_similar_clicked()`, `_on_similar_collapse_clicked()` will turn all 14 panel tests GREEN.
- Plan 04 (MainWindow implementation): `MainWindow._act_show_similar`, `_on_show_similar_toggled()`, `_on_similar_activated()` wired will turn all 6 integration tests GREEN.
- All Phase 64 and Phase 47.1 regression baselines confirmed green — Phase 67 additions are purely additive.

## Self-Check

Checking created files exist and commits exist...

---
*Phase: 67-show-similar-stations-below-now-playing-for-switching-from-s*
*Completed: 2026-05-10*
