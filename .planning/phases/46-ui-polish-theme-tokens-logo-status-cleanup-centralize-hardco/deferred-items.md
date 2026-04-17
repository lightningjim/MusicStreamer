# Phase 46 Deferred Items

Items discovered during execution that are out of scope for Phase 46 plans.

## Pre-existing Test Failures

### `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode`

- **Discovered:** Plan 46-01 regression sweep, 2026-04-17
- **Status:** Pre-existing failure (confirmed reproducible on clean Phase 46 base
  `383618e` with no Phase 46 code changes applied).
- **Reference:** PROJECT.md notes "399 passing, 1 pre-existing failure" as of
  Phase 42 completion — this is that one.
- **Error:** `_search_box.isVisibleTo(panel)` returns False in Stations mode when
  the widget is not shown with `panel.show()` + `qtbot.waitExposed()`. Likely an
  off-screen/non-exposed widget visibility quirk, not a behavioral bug.
- **Not related to Phase 46:** Plan 46-01 only adds a `from ... _theme import
  STATION_ICON_SIZE` import and substitutes `QSize(32, 32)` → `QSize(STATION_ICON_SIZE,
  STATION_ICON_SIZE)` in this file. Neither change touches the filter-strip or
  search-box visibility code paths.
- **Owner:** Future dedicated test-infra fix (may fold into Phase 47/48).
