# Deferred Items — Phase 68 Plan 04

## Pre-existing test failures (out of scope per deviation rules)

### test_refresh_recent_updates_list (tests/test_station_list_panel.py)
**Failure:** `assert 4 == 3` — `_populate_recent` uses `list_recently_played(5)` (limit 5) but the test adds a new entry and expects only 3 rows returned via `list_recently_played(n=3)`. The mismatch is pre-existing.
**Cause:** `_populate_recent` hardcodes limit 5 instead of the test's expected 3.
**Action needed:** Change `list_recently_played(5)` to `list_recently_played(3)` or align the test limit with the implementation.

### test_filter_strip_hidden_in_favorites_mode (tests/test_station_list_panel.py)
**Failure:** `isVisibleTo(panel)` check fails after switching to Favorites page.
**Cause:** Pre-existing failure; the `QStackedWidget` page-switching interaction with `isVisibleTo` is broken.
**Action needed:** Investigate page 0 vs page 1 visibility semantics on the offscreen platform.

Both failures existed before Plan 04 and are not related to Phase 68 changes.
