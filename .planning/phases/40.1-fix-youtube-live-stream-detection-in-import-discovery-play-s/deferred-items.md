# Deferred Items — Phase 40.1

## Pre-existing failures (out of scope for 40.1-04)

- `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode` — fails on HEAD independent of Plan 04 changes. The filter strip now starts collapsed (commit `db3f1bd` era), so `_search_box.isVisibleTo(panel)` is False in Stations mode too. Test pre-dates the collapse and needs to expand the strip before asserting, OR the test needs to be rewritten against `_filter_strip.isVisible()` after the toggle. Logged for future cleanup.
