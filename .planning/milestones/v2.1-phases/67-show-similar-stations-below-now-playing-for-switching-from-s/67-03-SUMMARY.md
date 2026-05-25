---
phase: 67
plan: "03"
subsystem: ui_qt/now_playing_panel
tags: [pyside6, qt-richtext, qt-pytest, sqlite-settings, html-escape, hidden-when-empty, qa-05, tdd-green]
dependency_graph:
  requires: [67-01, 67-02]
  provides: [NowPlayingPanel.similar_activated, NowPlayingPanel.set_similar_visible, NowPlayingPanel._similar_container, NowPlayingPanel._similar_cache, NowPlayingPanel._refresh_similar_stations, NowPlayingPanel._on_similar_link_activated, NowPlayingPanel._on_refresh_similar_clicked, NowPlayingPanel._on_similar_collapse_clicked]
  affects: [musicstreamer/ui_qt/now_playing_panel.py, tests/test_now_playing_panel.py]
tech_stack:
  added: []
  patterns:
    - "isHidden() for explicit hide-state in headless tests (isVisible() returns False when parent not shown)"
    - "pick_similar_stations + render_similar_html imported as multi-line from block alongside Phase 64 helpers"
    - "Cache hit/miss keyed by station.id; pop on refresh-button click; stale-OK (click-time defense)"
    - "Five-guard chain on _on_similar_link_activated mirrors Phase 64 _on_sibling_link_activated"
    - "set_similar_visible mirrors set_stats_visible (Phase 47.1) single-delegation pattern"
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py (+299 lines, 5 new methods, 1 new signal, 1 cache attr, 11 widget attrs, 1 bind_station call)
    - tests/test_now_playing_panel.py (+3 lines: updated test_panel_does_not_reimplement_aa_detection for Phase 67 expanded import)
decisions:
  - "Tasks 1+2 committed atomically: Task 1 alone causes AttributeError at panel construction (clicked.connect resolves bound method eagerly, not at emission time)"
  - "Used isHidden() instead of isVisible() in _on_similar_collapse_clicked to correctly toggle collapse state in headless Qt test environment"
  - "Updated test_panel_does_not_reimplement_aa_detection to check find_aa_siblings + render_sibling_html individually rather than as exact substring (Phase 67 multi-line import broke the exact-string match)"
metrics:
  duration: "19 minutes"
  completed: "2026-05-10T13:26:45Z"
  tasks: 2
  files_modified: 2
---

# Phase 67 Plan 03: NowPlayingPanel Similar Stations Widget Surface Summary

Similar Stations section wired into NowPlayingPanel: master-toggle container, collapsible header (▾/▸ + ↻ refresh), same-provider and same-tag sub-sections with in-memory cache and five-guard click handler emitting `similar_activated(Station)`. Turns 14 RED tests GREEN.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1+2 (atomic) | Add Phase 67 imports, signal, cache, widget tree, bind_station hook + 5 methods | 07d988b | musicstreamer/ui_qt/now_playing_panel.py (+299), tests/test_now_playing_panel.py (+3) |

## Verification Results

- `tests/test_now_playing_panel.py -k similar`: 14 tests — all passed (RED → GREEN)
- `tests/test_now_playing_panel.py` (full): 113 tests — all passed (Phase 64 + Phase 47.1 + Phase 60 + Phase 60.3 baselines preserved)
- `tests/test_pick_similar_stations.py`: 22 tests — all passed (Plan 02 baseline preserved)
- `test_sibling_label_visible_for_aa_station_with_siblings`: PASSED (Phase 64 baseline)
- `test_phase_64_sibling_label_unchanged_after_phase_67`: PASSED (SIM-12 lock)

## Acceptance Criteria Verification

- `similar_activated = Signal(object)`: 1 ✓
- `self._similar_cache: dict[int, tuple[list, list]] = {}`: 1 ✓
- `self._similar_container = QWidget`: 1 ✓
- `self._similar_body = QWidget`: 1 ✓
- `self._similar_collapse_btn = QPushButton`: 1 ✓
- `self._similar_refresh_btn = QToolButton`: 1 ✓
- `self._same_provider_subsection = QWidget`: 1 ✓
- `self._same_tag_subsection = QWidget`: 1 ✓
- `self._same_provider_links_label` count: 5 (≥3) ✓
- `self._same_tag_links_label` count: 5 (≥3) ✓
- `self._refresh_similar_stations()` call: 1 ✓
- `linkActivated.connect(self._on_similar_link_activated)`: 2 ✓
- `clicked.connect(self._on_similar_collapse_clicked)`: 1 ✓
- `clicked.connect(self._on_refresh_similar_clicked)`: 1 ✓
- `lambda` count: 3 (all in comments; no new lambda in production wiring) ✓ QA-05
- `from musicstreamer.url_helpers import` block: 1 ✓
- `pick_similar_stations`: 3 (import + docstring + call) ✓
- `render_similar_html`: 3 (import + 2 calls) ✓
- `def set_similar_visible(self, visible: bool)`: 1 ✓
- `def _refresh_similar_stations(self)`: 1 ✓
- `def _on_similar_link_activated(self, href: str)`: 1 ✓
- `def _on_refresh_similar_clicked(self)`: 1 ✓
- `def _on_similar_collapse_clicked(self)`: 1 ✓
- `self.similar_activated.emit(`: 1 ✓
- `prefix = "similar://"`: 1 ✓
- `self._similar_cache.pop(`: 1 ✓
- `self._repo.set_setting("similar_stations_collapsed"`: 1 ✓
- `show_provider=False`: 1 ✓
- `show_provider=True`: 1 ✓

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used isHidden() instead of isVisible() for collapse toggle**
- **Found during:** Task 2 test run (test_similar_collapse_persists)
- **Issue:** `_on_similar_collapse_clicked` used `not self._similar_body.isVisible()` which returns False in headless Qt tests because isVisible() checks effective visibility (requires top-level window to be shown). The toggle logic wrote "0" (expanded) when it should write "1" (collapsed).
- **Fix:** Changed to `self._similar_body.isHidden()` which checks the explicit hide flag independent of parent window visibility.
- **Files modified:** `musicstreamer/ui_qt/now_playing_panel.py`
- **Commit:** 07d988b

**2. [Rule 1 - Bug] Updated Phase 64 import-lock test for Phase 67 expanded import**
- **Found during:** Full test suite run after Task 1+2
- **Issue:** `test_panel_does_not_reimplement_aa_detection` checked for exact substring `"from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html"`. Phase 67 changed to a multi-line import block, breaking this test.
- **Fix:** Updated assertion to check `find_aa_siblings`, `render_sibling_html`, and `musicstreamer.url_helpers` individually (still verifies both Phase 64 helpers are imported, while accommodating the Phase 67 extension).
- **Files modified:** `tests/test_now_playing_panel.py`
- **Commit:** 07d988b

**3. [Rule 1 - Bug] Tasks 1+2 committed atomically (not separately as planned)**
- **Found during:** Task 1 execution
- **Issue:** The plan assumed `clicked.connect(self._on_similar_collapse_clicked)` resolves the bound method at signal-emission time. In Python, `self._method_name` is resolved immediately at connect() call time, not lazily. Panel construction raises AttributeError when _on_similar_collapse_clicked doesn't exist yet.
- **Fix:** Implemented both tasks before committing. The plan explicitly noted "The two tasks together form the atomic Plan 03 unit" — committed as one feat commit.
- **Commit:** 07d988b

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns. All new code is in-process panel widgets:
- `similar_activated` signal: in-process only, same trust level as `sibling_activated`
- `_on_similar_link_activated` five-guard chain: T-67-03-01/02 mitigated per plan threat register
- `_refresh_similar_stations` repo.list_stations defense: T-67-03-03 mitigated
- `set_setting` unwrapped: T-67-03-04 accepted per plan
- `render_similar_html` escaping: T-67-03-05 mitigated (inherited from Plan 02)
- All QA-05 connections via bound methods: T-67-03-06 mitigated

## Known Stubs

None. All 5 new methods are fully implemented and wired to the test corpus.

## TDD Gate Compliance

This plan is `type: execute` with tasks having `tdd="true"` attributes. Due to the atomic dependency between Tasks 1 and 2 (Task 1 alone causes AttributeError at panel construction), the RED/GREEN gates were merged into a single feat commit. The 14 tests were confirmed RED before this plan (confirmed via 67-01-SUMMARY.md which documents their AttributeError RED state) and are GREEN after this commit.

1. RED state: confirmed in 67-01-SUMMARY.md — all 14 similar panel tests failed with AttributeError (Phase 67 attributes not yet present)
2. GREEN commit: `feat(67-03)` 07d988b — 14 tests pass

## Self-Check: PASSED

Files exist:
- `musicstreamer/ui_qt/now_playing_panel.py` — FOUND ✓
- `tests/test_now_playing_panel.py` — FOUND ✓

Commits exist:
- 07d988b — FOUND ✓
